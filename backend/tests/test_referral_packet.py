"""Tests for the referral packet PDF.

Packets are written uncompressed here so their text can be searched directly.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.agent.placement_agent import PlacementAgent
from app.agent.tools.simulated_attendant import ScriptedAttendantActuator
from app.data.synthetic_data import get_facility
from app.models.schemas import (
    ApprovalStatus,
    LLMReview,
    ReviewFlag,
    AnswersSource,
    ConstraintCode,
    VerificationState,
)
from app.services.referral_service import write_referral_packet
from tests.conftest import ScriptedActuator, answers


def build(run, patient, tmp_path, name="packet.pdf"):
    path = write_referral_packet(
        run_id="run_test",
        telephony="scripted",
        run=run,
        patient=patient,
        facility=get_facility(run.proposal.facility_id),
        path=tmp_path / name,
        compress=False,
    )
    return path, path.read_bytes()


@pytest.fixture
def scripted_run(patient):
    return asyncio.run(PlacementAgent(ScriptedAttendantActuator()).run(patient))


class TestReferralPacket:
    def test_writes_a_pdf(self, scripted_run, patient, tmp_path):
        path, data = build(scripted_run, patient, tmp_path)

        assert path.exists()
        assert data.startswith(b"%PDF")

    def test_marked_synthetic_and_not_transmitted(self, scripted_run, patient, tmp_path):
        _, data = build(scripted_run, patient, tmp_path)

        assert b"SYNTHETIC" in data
        assert b"not transmitted" in data

    def test_draft_until_a_decision_is_made(self, scripted_run, patient, tmp_path):
        _, data = build(scripted_run, patient, tmp_path)

        assert b"DRAFT" in data
        assert b"APPROVED" not in data

    def test_decision_is_stamped_once_made(self, scripted_run, patient, tmp_path):
        proposal = scripted_run.proposal
        proposal.status = ApprovalStatus.APPROVED
        proposal.decided_by = "CM Rivera"
        proposal.decided_at = datetime(2026, 9, 13, 15, 30, tzinfo=timezone.utc)

        _, data = build(scripted_run, patient, tmp_path)

        assert b"APPROVED by CM Rivera" in data
        assert b"DRAFT" not in data

    def test_simulated_answers_are_labelled_in_the_packet(self, scripted_run, patient, tmp_path):
        _, data = build(scripted_run, patient, tmp_path)

        assert b"SIMULATED" in data
        assert b"no call placed" in data

    def test_markup_in_quotes_cannot_break_generation(self, patient, tmp_path):
        hostile = answers(coordinator="<b>Dana & Co</b>", wound_vac_detail="Yes <script> & 'quotes' \"here\"")
        run = asyncio.run(PlacementAgent(ScriptedActuator({"SNF-001": hostile})).run(patient))

        _, data = build(run, patient, tmp_path)

        assert data.startswith(b"%PDF")

    def test_review_flags_appear_with_their_outcome(self, scripted_run, patient, tmp_path):
        best = scripted_run.proposal.evaluation
        best.review = LLMReview(
            model="claude-opus-5",
            answers_source=AnswersSource.SIMULATED,
            flags=[
                ReviewFlag(code=ConstraintCode.STAFFED_BED, from_state=VerificationState.CONFIRMED,
                           to_state=VerificationState.NOT_CONFIRMED, quote="made up words",
                           reason="r", accepted=False, rejection_reason="quote does not appear verbatim"),
            ],
        )
        scripted_run.evaluations[-1] = best

        _, data = build(scripted_run, patient, tmp_path)

        assert b"Transcript review" in data
        assert b"Rejected" in data

    def test_a_run_without_a_proposal_is_refused(self, patient, tmp_path):
        from app.models.schemas import PlacementRun

        with pytest.raises(ValueError):
            write_referral_packet(
                run_id="x", telephony="scripted", run=PlacementRun(case_id="10482"),
                patient=patient, facility=get_facility("SNF-001"), path=tmp_path / "x.pdf",
            )
