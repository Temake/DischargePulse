"""Tests for verification, contradiction detection and scoring."""

from __future__ import annotations

import pytest

from app.agent.planner import resolve_sister_facility
from app.agent.reasoning_engine import ReasoningEngine, rank_evaluations
from app.data.synthetic_data import get_facility, get_patient
from app.models.schemas import (
    CallOutcome,
    ConstraintCode,
    Disposition,
    VerificationState,
)
from tests.conftest import answers, make_observation


@pytest.fixture
def engine():
    return ReasoningEngine()


def evaluate(engine, patient, facility_id, result):
    facility = get_facility(facility_id)
    observation = make_observation(facility_id, structured_result=result)
    return engine.evaluate(patient, facility, observation)


# ---------------------------------------------------------------------------
# Verification states
# ---------------------------------------------------------------------------


class TestVerification:
    def test_all_yes_is_a_verified_match(self, engine, patient):
        result = evaluate(engine, patient, "SNF-004", answers())

        assert result.disposition is Disposition.MATCH_VERIFIED
        assert result.is_placeable
        assert all(
            f.state is VerificationState.CONFIRMED for f in result.findings
        )

    def test_explicit_no_disqualifies(self, engine, patient):
        result = evaluate(engine, patient, "SNF-004", answers(wound_vac="no"))

        assert result.disposition is Disposition.DISQUALIFIED
        assert ConstraintCode.WOUND_VAC in result.disqualifying_codes

    def test_unknown_is_not_a_match_but_not_a_rejection(self, engine, patient):
        """Absence of a no is not a yes - it needs a human to chase."""
        result = evaluate(engine, patient, "SNF-004", answers(wound_vac="unknown"))

        assert result.disposition is Disposition.NEEDS_FOLLOW_UP
        assert not result.is_placeable

    def test_missing_field_is_treated_as_unconfirmed(self, engine, patient):
        result = answers()
        del result["wound_vac"]
        evaluation = evaluate(engine, patient, "SNF-004", result)

        finding = next(
            f for f in evaluation.findings if f.code is ConstraintCode.WOUND_VAC
        )
        assert finding.state is VerificationState.NOT_CONFIRMED

    def test_explicit_no_outranks_unknown_in_disposition(self, engine, patient):
        """A refusal disqualifies even when something else is merely unclear."""
        result = evaluate(
            engine, patient, "SNF-004", answers(wound_vac="no", iv="unknown")
        )

        assert result.disposition is Disposition.DISQUALIFIED

    def test_unreached_call_yields_no_findings(self, engine, patient):
        facility = get_facility("SNF-004")
        observation = make_observation(
            "SNF-004", outcome=CallOutcome.NO_ANSWER, structured_result=None
        )
        result = engine.evaluate(patient, facility, observation)

        assert result.disposition is Disposition.UNREACHED
        assert result.findings == []
        assert result.match_score == 0.0

    def test_only_hard_requirements_are_verified(self, engine, patient):
        """Distance and CMS rating are directory facts, not call findings."""
        result = evaluate(engine, patient, "SNF-004", answers())
        codes = {f.code for f in result.findings}

        assert ConstraintCode.DISTANCE not in codes
        assert ConstraintCode.CMS_RATING not in codes
        assert len(result.findings) == len(patient.hard_requirements())

    def test_contact_details_are_extracted(self, engine, patient):
        result = evaluate(
            engine, patient, "SNF-004", answers(coordinator="Marcus", fax="555-0198")
        )

        assert result.coordinator_name == "Marcus"
        assert result.fax_number == "555-0198"

    def test_empty_strings_become_none(self, engine, patient):
        """CALL-E uses '' for absent values; the domain uses None."""
        result = evaluate(engine, patient, "SNF-004", answers(coordinator="", fax=""))

        assert result.coordinator_name is None
        assert result.fax_number is None


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------


class TestContradictionDetection:
    def test_directory_yes_versus_call_no_is_flagged(self, engine, patient):
        """The headline case: SNF-001's directory claims wound VAC."""
        quote = "Our wound care nurse is out and nights isn't signed off."
        result = evaluate(
            engine,
            patient,
            "SNF-001",
            answers(wound_vac="no", wound_vac_detail=quote),
        )

        assert len(result.contradictions) == 1
        contradiction = result.contradictions[0]
        assert contradiction.code is ConstraintCode.WOUND_VAC
        assert "available" in contradiction.directory_says
        assert "unavailable" in contradiction.call_says
        assert contradiction.quote == quote

    def test_contradiction_disqualifies_the_facility(self, engine, patient):
        result = evaluate(engine, patient, "SNF-001", answers(wound_vac="no"))

        assert result.disposition is Disposition.DISQUALIFIED
        assert "overrides" in result.contradictions[0].resolution

    def test_directory_no_versus_call_yes_is_also_flagged(self, engine, patient):
        """A stale 'no' would have hidden a viable facility from a directory search."""
        result = evaluate(engine, patient, "SNF-002", answers(payer="yes"))

        codes = [c.code for c in result.contradictions]
        assert ConstraintCode.PAYER_NETWORK in codes

        contradiction = next(
            c for c in result.contradictions if c.code is ConstraintCode.PAYER_NETWORK
        )
        assert "stale" in contradiction.resolution.lower()

    def test_agreement_produces_no_contradiction(self, engine, patient):
        result = evaluate(engine, patient, "SNF-004", answers())

        assert result.contradictions == []

    def test_unknown_answer_is_not_a_contradiction(self, engine, patient):
        """Failure to confirm is not the same as contradicting the record."""
        result = evaluate(engine, patient, "SNF-001", answers(wound_vac="unknown"))

        assert result.contradictions == []

    def test_requirement_absent_from_directory_is_skipped(self, engine, patient):
        """SNF-002 has no bariatric claim; nothing to contradict."""
        result = evaluate(engine, patient, "SNF-002", answers())
        codes = [c.code for c in result.contradictions]

        assert ConstraintCode.BARIATRIC_CAPACITY not in codes


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    def test_full_match_scores_high(self, engine, patient):
        result = evaluate(engine, patient, "SNF-004", answers())

        assert result.match_score > 80

    def test_score_falls_as_requirements_fail(self, engine, patient):
        full = evaluate(engine, patient, "SNF-004", answers())
        partial = evaluate(engine, patient, "SNF-004", answers(wound_vac="no"))

        assert partial.match_score < full.match_score

    def test_closer_facility_outranks_distant_one_all_else_equal(
        self, engine, patient
    ):
        near = evaluate(engine, patient, "SNF-001", answers())   # 4.2 mi
        far = evaluate(engine, patient, "SNF-004", answers())    # 18.6 mi

        assert near.match_score > far.match_score

    def test_score_is_bounded(self, engine, patient):
        result = evaluate(engine, patient, "SNF-003", answers())

        assert 0.0 <= result.match_score <= 100.0

    def test_ranking_puts_placeable_matches_first(self, engine, patient):
        disqualified = evaluate(engine, patient, "SNF-001", answers(wound_vac="no"))
        matched = evaluate(engine, patient, "SNF-004", answers())

        ranked = rank_evaluations([disqualified, matched])

        assert ranked[0].facility_id == "SNF-004"

    def test_higher_score_wins_among_matches(self, engine, patient):
        near = evaluate(engine, patient, "SNF-001", answers())
        far = evaluate(engine, patient, "SNF-004", answers())

        assert rank_evaluations([far, near])[0].facility_id == "SNF-001"


# ---------------------------------------------------------------------------
# Sister facility leads
# ---------------------------------------------------------------------------


class TestSisterFacilityLeads:
    def test_name_spoken_on_the_call_resolves_to_a_facility(self, engine, patient):
        result = evaluate(
            engine,
            patient,
            "SNF-001",
            answers(bed="no", sister="Bayview Peninsula"),
        )

        assert "SNF-004" in result.sister_facility_leads

    def test_none_sentinel_yields_no_spoken_lead(self, engine, patient):
        result = evaluate(engine, patient, "SNF-002", answers(sister="none"))

        assert result.sister_facility_leads == []

    def test_ownership_links_supply_a_fallback_lead(self, engine, patient):
        """Even with no name given, SNF-001's ownership link surfaces SNF-004."""
        result = evaluate(engine, patient, "SNF-001", answers(sister="none"))

        assert result.sister_facility_leads == ["SNF-004"]

    def test_a_facility_never_leads_to_itself(self, engine, patient):
        result = evaluate(
            engine, patient, "SNF-001", answers(sister="Bayview Post-Acute Center")
        )

        assert "SNF-001" not in result.sister_facility_leads


class TestSisterFacilityResolution:
    def test_exact_name_matches(self):
        assert resolve_sister_facility("Bayview Post-Acute Center") == "SNF-001"

    def test_partial_name_matches(self):
        assert resolve_sister_facility("Peninsula Campus") == "SNF-004"

    def test_case_and_spacing_are_ignored(self):
        assert resolve_sister_facility("  golden gate skilled nursing ") == "SNF-002"

    def test_unrecognised_name_returns_none(self):
        assert resolve_sister_facility("St Elsewhere Nursing Home") is None

    def test_empty_name_returns_none(self):
        assert resolve_sister_facility("") is None

    def test_generic_words_alone_do_not_match(self):
        """'care center' appears in many names and must not pick one at random."""
        assert resolve_sister_facility("the care center") is None
