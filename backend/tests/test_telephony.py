"""Tests for the telephony seam: schemas, budget, cassettes, replay.

These run entirely offline and spend no call credit. Async tests drive the event
loop with `asyncio.run` rather than a pytest plugin, so the suite has no extra
dependency.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.agent.tools import cassette
from app.agent.tools.budget import BudgetExhausted, CallBudget
from app.agent.tools.replay_actuator import ReplayActuator
from app.agent.tools.telephony import (
    CALLE_DEMO_HOTLINE,
    NO_SISTER_FACILITY,
    TRI_STATE,
    build_result_schema,
    build_task_prompt,
    is_stand_in_line,
    locale_for_region,
    recipient_for,
    region_for_phone,
)
from app.data.synthetic_data import (
    FACILITIES,
    PLACEHOLDER_PHONE,
    get_facility,
    get_patient,
)
from app.models.schemas import (
    CallMode,
    CallObservation,
    CallOutcome,
    ConstraintCode,
    ConstraintKind,
)


@pytest.fixture
def patient():
    return get_patient("10482")


@pytest.fixture
def facility():
    return get_facility("SNF-001")


@pytest.fixture
def observation(facility):
    return CallObservation(
        facility_id=facility.facility_id,
        phone="+15555550100",
        mode=CallMode.LIVE,
        call_id="call_abc123",
        provider_call_id="prov_xyz789",
        started_at=datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 9, 10, 14, 2, tzinfo=timezone.utc),
        duration_seconds=120.0,
        outcome=CallOutcome.COMPLETED,
        structured_result={
            "payer_network": "yes",
            "staffed_bed": "yes",
            "wound_vac": "no",
            "iv_infusion": "yes",
            "coordinator_name": "Dana",
        },
        summary="Bed available but no wound VAC certified nurse tonight.",
        task_completed=True,
        confidence_score=0.91,
        confidence_label="high",
        evidence=["Staff said the night nurse lacks wound VAC sign-off."],
    )


# ---------------------------------------------------------------------------
# Synthetic data integrity
# ---------------------------------------------------------------------------


class TestSyntheticData:
    def test_every_facility_and_patient_is_flagged_synthetic(self, patient):
        assert patient.synthetic
        assert all(f.synthetic for f in FACILITIES)

    def test_facility_ids_are_unique(self):
        ids = [f.facility_id for f in FACILITIES]
        assert len(ids) == len(set(ids))

    def test_patient_splits_hard_and_soft_requirements(self, patient):
        hard = patient.hard_requirements()
        soft = patient.soft_requirements()

        assert hard and soft
        assert all(r.kind is ConstraintKind.HARD for r in hard)
        assert all(r.kind is ConstraintKind.SOFT for r in soft)
        assert len(hard) + len(soft) == len(patient.requirements)

    def test_sister_facility_links_resolve(self):
        for f in FACILITIES:
            for sister_id in f.sister_facility_ids:
                assert get_facility(sister_id) is not None

    def test_seeded_contradiction_exists(self, facility):
        """SNF-001's directory claims wound VAC; the demo call contradicts it."""
        claim = facility.claim_for(ConstraintCode.WOUND_VAC)
        assert claim is not None
        assert claim.claimed_available is True

    def test_unstaffed_facilities_carry_placeholder_numbers(self):
        """Facilities without a demo receiver must not hold a dialable number."""
        for f in FACILITIES:
            assert f.phone.startswith("+")


# ---------------------------------------------------------------------------
# Result schema construction
# ---------------------------------------------------------------------------


class TestResultSchema:
    def test_schema_covers_every_hard_requirement(self, patient):
        schema = build_result_schema(patient)

        for req in patient.hard_requirements():
            assert req.code.value in schema["properties"]
            assert req.code.value in schema["required"]

    def test_soft_requirements_are_never_asked_on_the_phone(self, patient):
        """Distance and CMS rating come from the directory, not a call."""
        schema = build_result_schema(patient)

        for req in patient.soft_requirements():
            assert req.code.value not in schema["properties"]

    def test_constraint_fields_are_tri_state_enums(self, patient):
        schema = build_result_schema(patient)

        for req in patient.hard_requirements():
            field = schema["properties"][req.code.value]
            assert field["type"] == "string"
            assert field["enum"] == TRI_STATE

    def test_schema_stays_within_calle_supported_features(self, patient):
        """CALL-E rejects $ref, oneOf, anyOf, allOf and additionalProperties: true."""
        schema = build_result_schema(patient)
        unsupported = {"$ref", "oneOf", "anyOf", "allOf"}

        def walk(node):
            if isinstance(node, dict):
                assert not (unsupported & node.keys())
                if node.get("type") == "object":
                    assert node.get("additionalProperties") is False
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(schema)

    def test_schema_collects_coordinator_and_sister_facility(self, patient):
        props = build_result_schema(patient)["properties"]

        assert "coordinator_name" in props
        assert "referral_fax_number" in props
        assert NO_SISTER_FACILITY in props["sister_facility_name"]["description"]

    def test_schema_adapts_to_a_different_patient(self):
        """Patient 10483 needs isolation and bariatric capacity, not wound VAC."""
        schema = build_result_schema(get_patient("10483"))

        assert ConstraintCode.CONTACT_ISOLATION.value in schema["properties"]
        assert ConstraintCode.BARIATRIC_CAPACITY.value in schema["properties"]
        assert ConstraintCode.WOUND_VAC.value not in schema["properties"]


# ---------------------------------------------------------------------------
# Task prompt construction
# ---------------------------------------------------------------------------


class TestTaskPrompt:
    def test_prompt_names_facility_and_every_hard_requirement(self, patient, facility):
        prompt = build_task_prompt(patient, facility)

        assert facility.name in prompt
        assert patient.payer_plan in prompt
        for req in patient.hard_requirements():
            assert req.ask_as in prompt

    def test_prompt_withholds_identifiers(self, patient, facility):
        """The call is a de-identified enquiry - no name, DOB or MRN."""
        prompt = build_task_prompt(patient, facility)

        assert "do not state or invent a patient name" in prompt.lower()
        assert patient.display_name not in prompt

    def test_prompt_forbids_committing_to_an_admission(self, patient, facility):
        """The human-in-the-loop gate has to hold on the call itself."""
        prompt = build_task_prompt(patient, facility)

        assert "do not agree to, promise, or schedule an admission" in prompt.lower()

    def test_prompt_asks_for_sister_facility_on_refusal(self, patient, facility):
        assert "sister facility" in build_task_prompt(patient, facility).lower()


# ---------------------------------------------------------------------------
# Region routing
# ---------------------------------------------------------------------------


class TestRegionRouting:
    @pytest.mark.parametrize(
        "phone,expected",
        [
            ("+15555550100", "US"),
            ("+2340000000000", "NG"),
            ("+442079460000", "GB"),
            ("+910000000000", "IN"),
            ("+6500000000", "SG"),
            ("+254000000000", "KE"),
        ],
    )
    def test_region_inferred_from_calling_code(self, phone, expected):
        assert region_for_phone(phone) == expected

    def test_longer_calling_codes_win_over_shorter_ones(self):
        """+234 must not be read as +2 or shadowed by +1."""
        assert region_for_phone("+2340000000000") == "NG"
        assert region_for_phone("+15555550100") == "US"

    def test_uncovered_country_returns_none(self):
        """+7 (Russia) is not in CALL-E's coverage table."""
        assert region_for_phone("+79161234567") is None

    def test_non_e164_returns_none(self):
        assert region_for_phone("07082118322") is None

    def test_locale_defaults_to_english_for_the_region(self):
        assert locale_for_region("NG") == "en-NG"
        assert locale_for_region("US") == "en-US"

    def test_locale_respects_non_english_regions(self):
        assert locale_for_region("JP") == "ja-JP"

    def test_recipient_carries_inferred_routing(self):
        recipient = recipient_for("+2340000000000")

        assert recipient["phones"] == ["+2340000000000"]
        assert recipient["region"] == "NG"
        assert recipient["locale"] == "en-NG"

    def test_recipient_honours_explicit_overrides(self):
        recipient = recipient_for("+15555550100", region="GB", locale="en-GB")

        assert recipient["region"] == "GB"
        assert recipient["locale"] == "en-GB"


# ---------------------------------------------------------------------------
# Budget ledger
# ---------------------------------------------------------------------------


class TestCallBudget:
    def test_reserve_decrements_remaining(self, tmp_path):
        b = CallBudget(path=tmp_path / "ledger.json", ceiling=3)

        assert b.remaining == 3
        b.reserve("SNF-001", "+15555550100")
        assert b.spent == 1
        assert b.remaining == 2

    def test_ceiling_is_enforced(self, tmp_path):
        b = CallBudget(path=tmp_path / "ledger.json", ceiling=2)
        b.reserve("SNF-001", "+15555550100")
        b.reserve("SNF-002", "+15555550101")

        with pytest.raises(BudgetExhausted):
            b.reserve("SNF-003", "+15555550102")

    def test_ledger_survives_restart(self, tmp_path):
        path = tmp_path / "ledger.json"
        CallBudget(path=path, ceiling=5).reserve("SNF-001", "+15555550100")

        assert CallBudget(path=path, ceiling=5).spent == 1

    def test_check_raises_only_when_exhausted(self, tmp_path):
        b = CallBudget(path=tmp_path / "ledger.json", ceiling=1)
        b.check()
        b.reserve("SNF-001", "+15555550100")

        with pytest.raises(BudgetExhausted):
            b.check()

    def test_release_refunds_a_call_that_never_dialed(self, tmp_path):
        """An API rejection consumes no credit, so it must not consume budget."""
        b = CallBudget(path=tmp_path / "ledger.json", ceiling=20)
        b.reserve("SNF-001", "+2340000000000")
        assert b.spent == 1

        b.release(reason="unsupported_region")
        assert b.spent == 0
        assert b.remaining == 20

    def test_release_cannot_drive_the_ledger_negative(self, tmp_path):
        b = CallBudget(path=tmp_path / "ledger.json", ceiling=20)
        b.release(reason="nothing reserved")

        assert b.spent == 0

    def test_release_survives_restart(self, tmp_path):
        path = tmp_path / "ledger.json"
        b = CallBudget(path=path, ceiling=20)
        b.reserve("SNF-001", "+15555550100")
        b.release(reason="rejected")

        assert CallBudget(path=path, ceiling=20).spent == 0

    def test_ledger_records_an_audit_trail(self, tmp_path):
        path = tmp_path / "ledger.json"
        b = CallBudget(path=path, ceiling=5)
        b.reserve("SNF-001", "+15555550100", note="case 10482")

        import json

        entries = json.loads(path.read_text(encoding="utf-8"))["calls"]
        assert entries[0]["facility_id"] == "SNF-001"
        assert entries[0]["note"] == "case 10482"


# ---------------------------------------------------------------------------
# Cassettes
# ---------------------------------------------------------------------------


class TestCassettes:
    def test_round_trip_preserves_the_payload(self, observation, tmp_path):
        cassette.record(observation, "10482", directory=tmp_path)
        loaded = cassette.load("10482", observation.facility_id, directory=tmp_path)

        assert loaded is not None
        assert loaded.structured_result == observation.structured_result
        assert loaded.summary == observation.summary
        assert loaded.evidence == observation.evidence
        assert loaded.confidence_score == observation.confidence_score

    def test_replay_is_stamped_as_replay(self, observation, tmp_path):
        cassette.record(observation, "10482", directory=tmp_path)
        loaded = cassette.load("10482", observation.facility_id, directory=tmp_path)

        assert loaded.mode is CallMode.REPLAY

    def test_replay_keeps_the_original_call_identifiers(self, observation, tmp_path):
        """A replayed call must remain traceable to the live call it came from."""
        cassette.record(observation, "10482", directory=tmp_path)
        loaded = cassette.load("10482", observation.facility_id, directory=tmp_path)

        assert loaded.call_id == "call_abc123"
        assert loaded.provider_call_id == "prov_xyz789"

    def test_missing_cassette_loads_as_none(self, tmp_path):
        assert cassette.load("10482", "SNF-NOPE", directory=tmp_path) is None

    def test_corrupt_cassette_does_not_raise(self, tmp_path):
        path = cassette.cassette_path("10482", "SNF-001", directory=tmp_path)
        path.write_text("{ not json", encoding="utf-8")

        assert cassette.load("10482", "SNF-001", directory=tmp_path) is None


# ---------------------------------------------------------------------------
# Replay actuator
# ---------------------------------------------------------------------------


class TestReplayActuator:
    def test_replays_a_recorded_call(self, observation, patient, facility, monkeypatch):
        monkeypatch.setattr(
            cassette, "load", lambda *a, **k: observation.model_copy(
                update={"mode": CallMode.REPLAY}
            )
        )
        result = asyncio.run(ReplayActuator().call_facility(facility, patient))

        assert result.mode is CallMode.REPLAY
        assert result.is_usable
        assert result.structured_result["wound_vac"] == "no"

    def test_missing_cassette_yields_an_unreached_observation(
        self, patient, facility, monkeypatch
    ):
        monkeypatch.setattr(cassette, "load", lambda *a, **k: None)
        result = asyncio.run(ReplayActuator().call_facility(facility, patient))

        assert result.outcome is CallOutcome.NO_ANSWER
        assert result.failure_code == "cassette_missing"
        assert not result.is_usable

    def test_strict_mode_raises_on_a_missing_cassette(
        self, patient, facility, monkeypatch
    ):
        monkeypatch.setattr(cassette, "load", lambda *a, **k: None)

        with pytest.raises(FileNotFoundError):
            asyncio.run(ReplayActuator(strict=True).call_facility(facility, patient))

    def test_replay_never_touches_the_budget(self, patient, facility, tmp_path, monkeypatch):
        """The whole point of cassettes: exercising the loop is free."""
        monkeypatch.setattr(cassette, "load", lambda *a, **k: None)
        b = CallBudget(path=tmp_path / "ledger.json", ceiling=20)

        for _ in range(50):
            asyncio.run(ReplayActuator().call_facility(facility, patient))

        assert b.spent == 0


# ---------------------------------------------------------------------------
# Observation semantics
# ---------------------------------------------------------------------------


class TestCallObservation:
    def test_completed_call_with_a_result_is_usable(self, observation):
        assert observation.is_usable

    def test_failed_call_is_not_usable(self, observation):
        assert not observation.model_copy(
            update={"outcome": CallOutcome.FAILED}
        ).is_usable

    def test_completed_call_without_extraction_is_not_usable(self, observation):
        """CALL-E returns null structured_result when evidence was too thin."""
        assert not observation.model_copy(update={"structured_result": None}).is_usable


# ---------------------------------------------------------------------------
# Test-line role-play
# ---------------------------------------------------------------------------


class TestStandInLines:
    """The demo dials stand-in answering lines, never real facilities. The
    outbound prompt is identical either way - the scripted persona lives in a
    CALL-E Inbound Goal on the answering side - so the only thing to carry is
    the disclosure that the facility side was scripted."""

    def test_configured_demo_numbers_are_stand_ins(self):
        from app.config import settings

        if settings.demo_phone_primary:
            assert is_stand_in_line(settings.demo_phone_primary)

    def test_calle_demo_hotline_is_a_stand_in(self):
        assert is_stand_in_line(CALLE_DEMO_HOTLINE)

    def test_an_unrelated_number_is_not_a_stand_in(self):
        assert not is_stand_in_line("+14155550123")

    def test_blank_number_is_not_a_stand_in(self):
        assert not is_stand_in_line("")

    def test_prompt_carries_no_scripted_answers(self, patient, facility):
        """Nothing in the outbound prompt tells the other end what to say."""
        prompt = build_task_prompt(patient, facility)

        for banned in ["role-play", "roleplay", "pretend", "imaginary", "made-up"]:
            assert banned not in prompt.lower()

    def test_prompt_confirms_the_facility_reached(self, patient, facility):
        """Names the facility, so a wrong-number call is caught - and a stand-in
        line knows which persona is wanted."""
        prompt = build_task_prompt(patient, facility)

        assert f"confirm you have reached {facility.name}" in prompt

    def test_replayed_observation_keeps_the_stand_in_flag(self, observation, tmp_path):
        cassette.record(
            observation.model_copy(update={"stand_in_line": True}),
            "10482",
            directory=tmp_path,
        )
        loaded = cassette.load("10482", observation.facility_id, directory=tmp_path)

        assert loaded.stand_in_line is True


# ---------------------------------------------------------------------------
# Phone-number masking
# ---------------------------------------------------------------------------


class TestPhoneMasking:
    """Numbers are masked in everything serialized or logged, but the in-memory
    model keeps the full number because it is needed to dial."""

    def test_mask_format_keeps_only_a_prefix_and_suffix(self):
        from app.models.schemas import mask_phone

        assert mask_phone("+15555550100") == "+15******100"
        assert mask_phone("+2340000000000") == "+23********000"
        assert mask_phone("") == ""
        assert mask_phone(None) is None

    def test_facility_json_is_masked_but_the_model_is_not(self, facility):
        dialable = facility.model_copy(update={"phone": "+15555550100"})

        assert dialable.phone == "+15555550100"
        assert dialable.model_dump(mode="json")["phone"] == "+15******100"
        assert "+15555550100" not in dialable.model_dump_json()

    def test_observation_json_is_masked(self, observation):
        assert "+15555550100" not in observation.model_dump_json()

    def test_recorded_cassettes_never_store_the_full_number(self, observation, tmp_path):
        path = cassette.record(observation, "10482", directory=tmp_path)

        assert "+15555550100" not in path.read_text(encoding="utf-8")

    def test_budget_ledger_masks_the_number(self, tmp_path):
        ledger = CallBudget(path=tmp_path / "ledger.json", ceiling=5)
        ledger.reserve("SNF-001", "+15555550100")

        assert "+15555550100" not in (tmp_path / "ledger.json").read_text(encoding="utf-8")

    def test_the_dial_still_receives_the_full_number(self, patient, facility, tmp_path):
        """Masking must never reach the request that actually places the call."""
        from app.agent.tools.calle_actuator import CalleActuator

        sent = {}

        def create_and_wait(**kwargs):
            sent.update(kwargs)
            return {"id": "call_x", "status": "completed", "structured_result": None, "recipients": []}

        actuator = CalleActuator(
            api_key="test-key",
            budget=CallBudget(path=tmp_path / "ledger.json", ceiling=5),
            record_cassettes=False,
        )
        actuator._client.calls.create_and_wait = create_and_wait
        dialable = facility.model_copy(update={"phone": "+15555550100"})

        asyncio.run(actuator.call_facility(dialable, patient))

        assert sent["recipients"][0]["phones"] == ["+15555550100"]
