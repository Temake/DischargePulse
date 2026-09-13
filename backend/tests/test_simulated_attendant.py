"""Tests for the simulated-attendant actuators.

The honesty rules are the point of this module, so each gets a test:
  - a real call stays real (LIVE, call id, transcript) with answers labelled
  - answers genuinely extracted from a call are never overwritten
  - nothing is simulated on top of a call that never connected
  - what the call really extracted is preserved
  - scripted runs place no calls and spend no budget
"""

from __future__ import annotations

import asyncio

import pytest

from app.agent.placement_agent import PlacementAgent
from app.agent.tools import cassette
from app.agent.tools.budget import CallBudget
from app.agent.tools.simulated_attendant import (
    ScriptedAttendantActuator,
    SimulatedAttendantActuator,
    has_real_answers,
)
from app.data import synthetic_data
from app.data.scenarios import scenario_for
from app.models.schemas import (
    AgentPhase,
    AnswersSource,
    CallMode,
    CallObservation,
    CallOutcome,
    RunStatus,
    TranscriptSpeaker,
    TranscriptTurn,
)
from tests.conftest import answers

DIALABLE = "+15555550100"  # fictional (555-01xx)

ALL_UNKNOWN = answers(
    payer="unknown", bed="unknown", wound_vac="unknown", iv="unknown",
    coordinator="", fax="", sister="none",
)


def silent_live_call(facility_id: str, phone: str = DIALABLE) -> CallObservation:
    """Shaped like the real failures: connected, billed, nothing extracted."""
    return CallObservation(
        facility_id=facility_id,
        phone=phone,
        mode=CallMode.LIVE,
        stand_in_line=True,
        call_id=f"call_real_{facility_id.lower()}",
        provider_call_id=f"prov_{facility_id.lower()}",
        duration_seconds=81.8,
        outcome=CallOutcome.COMPLETED,
        structured_result=dict(ALL_UNKNOWN),
        summary="The call did not reach a live admissions conversation.",
        transcript_turns=[
            TranscriptTurn(offset_seconds=6, speaker=TranscriptSpeaker.BOT,
                           text="Have I reached Bayview Post-Acute Center?"),
            TranscriptTurn(offset_seconds=79, speaker=TranscriptSpeaker.USER,
                           text="There is signal interference on our call."),
        ],
    )


class FakeLive:
    """Stands in for CalleActuator; returns a scripted observation per facility."""

    mode_label = "live"

    def __init__(self, make=silent_live_call):
        self._make = make
        self.dialed: list[str] = []

    async def call_facility(self, facility, patient, objective=None, result_schema=None):
        self.dialed.append(facility.facility_id)
        return self._make(facility.facility_id)


def dial(actuator, facility, patient):
    return asyncio.run(actuator.call_facility(facility, patient))


@pytest.fixture
def dialable(facility):
    return facility.model_copy(update={"phone": DIALABLE})


# ---------------------------------------------------------------------------
# Simulated attendant over a real call
# ---------------------------------------------------------------------------


class TestSimulatedAttendant:
    def test_silent_call_gets_labelled_simulated_answers(self, dialable, patient):
        result = dial(SimulatedAttendantActuator(FakeLive(), record_cassettes=False), dialable, patient)

        assert result.answers_source is AnswersSource.SIMULATED
        assert result.structured_result == scenario_for("10482", "SNF-001")
        assert "simulated" in result.simulation_note.lower()

    def test_the_call_itself_stays_real(self, dialable, patient):
        """Only the answers change. Everything proving a call happened is kept."""
        result = dial(SimulatedAttendantActuator(FakeLive(), record_cassettes=False), dialable, patient)

        assert result.mode is CallMode.LIVE
        assert result.call_id == "call_real_snf-001"
        assert result.provider_call_id == "prov_snf-001"
        assert result.duration_seconds == 81.8
        assert result.summary == "The call did not reach a live admissions conversation."
        assert [t.text for t in result.transcript_turns][-1] == "There is signal interference on our call."

    def test_what_the_call_really_extracted_is_preserved(self, dialable, patient):
        result = dial(SimulatedAttendantActuator(FakeLive(), record_cassettes=False), dialable, patient)

        assert result.call_structured_result == ALL_UNKNOWN

    def test_real_answers_are_never_overwritten(self, dialable, patient):
        """If the stand-in line starts working, its answers win outright."""
        def real_call(fid):
            obs = silent_live_call(fid)
            return obs.model_copy(update={"structured_result": answers(bed="no")})

        result = dial(SimulatedAttendantActuator(FakeLive(real_call), record_cassettes=False), dialable, patient)

        assert result.answers_source is AnswersSource.CALL
        assert result.structured_result["staffed_bed"] == "no"
        assert result.simulation_note is None

    def test_one_real_answer_is_enough_to_keep_the_call_result(self, patient):
        partial = dict(ALL_UNKNOWN, wound_vac="no")

        assert has_real_answers(patient, partial)
        assert not has_real_answers(patient, ALL_UNKNOWN)
        assert not has_real_answers(patient, None)

    def test_nothing_is_simulated_on_a_call_that_never_connected(self, dialable, patient):
        def rejected(fid):
            return CallObservation(
                facility_id=fid, phone=DIALABLE, mode=CallMode.LIVE,
                outcome=CallOutcome.FAILED, failure_code="CalleAPIError",
                failure_message="Insufficient CALL-E balance.",
            )

        result = dial(SimulatedAttendantActuator(FakeLive(rejected), record_cassettes=False), dialable, patient)

        assert result.answers_source is AnswersSource.CALL
        assert result.structured_result is None
        assert result.outcome is CallOutcome.FAILED

    def test_facility_without_a_scenario_keeps_the_real_result(self, dialable, patient):
        other = dialable.model_copy(update={"facility_id": "SNF-006"})
        result = dial(SimulatedAttendantActuator(FakeLive(), record_cassettes=False), other, patient)

        assert result.answers_source is AnswersSource.CALL
        assert result.structured_result == ALL_UNKNOWN

    def test_undialable_facility_is_scripted_not_called(self, patient):
        live = FakeLive()
        snf003 = synthetic_data.get_facility("SNF-003")  # placeholder number
        result = dial(SimulatedAttendantActuator(live, record_cassettes=False), snf003, patient)

        assert live.dialed == []
        assert result.mode is CallMode.SCRIPTED
        assert result.answers_source is AnswersSource.SIMULATED
        assert result.call_id is None

    def test_recorded_cassette_keeps_the_labels(self, dialable, patient, tmp_path, monkeypatch):
        monkeypatch.setattr(cassette.settings, "cassette_dir", tmp_path)
        dial(SimulatedAttendantActuator(FakeLive(), record_cassettes=True), dialable, patient)

        replayed = cassette.load("10482", "SNF-001", directory=tmp_path)
        assert replayed.mode is CallMode.REPLAY
        assert replayed.answers_source is AnswersSource.SIMULATED
        assert replayed.call_id == "call_real_snf-001"
        assert replayed.call_structured_result == ALL_UNKNOWN


# ---------------------------------------------------------------------------
# Scripted attendant - no calls
# ---------------------------------------------------------------------------


class TestScriptedAttendant:
    def test_scripted_answers_are_labelled_and_place_no_call(self, facility, patient):
        result = dial(ScriptedAttendantActuator(), facility, patient)

        assert result.mode is CallMode.SCRIPTED
        assert result.answers_source is AnswersSource.SIMULATED
        assert result.call_id is None
        assert result.structured_result == scenario_for("10482", "SNF-001")

    def test_scripted_runs_never_touch_the_budget(self, facility, patient, tmp_path):
        ledger = CallBudget(path=tmp_path / "ledger.json", ceiling=20)
        for _ in range(10):
            dial(ScriptedAttendantActuator(), facility, patient)

        assert ledger.spent == 0

    def test_no_scenario_is_unreached_not_invented(self, facility, patient):
        other = facility.model_copy(update={"facility_id": "SNF-006"})
        result = dial(ScriptedAttendantActuator(), other, patient)

        assert result.outcome is CallOutcome.NO_ANSWER
        assert result.structured_result is None


# ---------------------------------------------------------------------------
# End to end: the demo story, with real calls and simulated attendants
# ---------------------------------------------------------------------------


class TestSimulatedDemoRun:
    @pytest.fixture
    def live(self, monkeypatch):
        # Give the two demo facilities a dialable line regardless of .env.
        for fid in ("SNF-001", "SNF-004"):
            f = synthetic_data.FACILITIES_BY_ID[fid]
            monkeypatch.setitem(
                synthetic_data.FACILITIES_BY_ID, fid, f.model_copy(update={"phone": DIALABLE})
            )
        return FakeLive()

    def run(self, live, patient):
        actuator = SimulatedAttendantActuator(live, record_cassettes=False)
        return asyncio.run(PlacementAgent(actuator).run(patient))

    def test_reaches_the_verified_match(self, live, patient):
        run = self.run(live, patient)

        assert run.status is RunStatus.AWAITING_APPROVAL
        assert run.proposal.facility_id == "SNF-004"

    def test_only_dialable_facilities_are_really_called(self, live, patient):
        self.run(live, patient)

        assert live.dialed == ["SNF-001", "SNF-004"]

    def test_contradiction_and_sister_lead_come_through(self, live, patient):
        run = self.run(live, patient)

        assert any(c.code.value == "wound_vac" for c in run.contradictions)
        replan = next(e for e in run.events if e.trigger and e.trigger.value == "sister_facility_lead")
        assert replan.payload["source"] == "simulated"

    def test_every_observe_event_names_simulated_answers(self, live, patient):
        """The label must be in the headline, not just a payload field."""
        run = self.run(live, patient)
        observes = [e for e in run.events if e.phase is AgentPhase.OBSERVE]

        assert observes
        for event in observes:
            assert event.payload["answers_source"] == "simulated"
            assert "simulated" in event.message.lower()

    def test_live_legs_keep_their_real_call_ids(self, live, patient):
        run = self.run(live, patient)
        observes = {e.facility_id: e for e in run.events if e.phase is AgentPhase.OBSERVE}

        assert observes["SNF-001"].payload["mode"] == "live"
        assert observes["SNF-001"].payload["call_id"] == "call_real_snf-001"
        assert observes["SNF-003"].payload["mode"] == "scripted"
        assert observes["SNF-003"].payload["call_id"] is None


# ---------------------------------------------------------------------------
# No line may claim more than happened
# ---------------------------------------------------------------------------


class TestHonestWording:
    """Regression: a scripted rehearsal printed "Placing 2 concurrent call(s)",
    "the call said", "named on the call" and "calls placed: 3" - with zero calls
    placed. Every one of those must name what really produced the answer."""

    @pytest.fixture
    def simulated_run(self, monkeypatch, patient):
        for fid in ("SNF-001", "SNF-004"):
            f = synthetic_data.FACILITIES_BY_ID[fid]
            monkeypatch.setitem(
                synthetic_data.FACILITIES_BY_ID, fid, f.model_copy(update={"phone": DIALABLE})
            )
        actuator = SimulatedAttendantActuator(FakeLive(), record_cassettes=False)
        return asyncio.run(PlacementAgent(actuator).run(patient))

    @pytest.fixture
    def scripted_run(self, patient):
        return asyncio.run(PlacementAgent(ScriptedAttendantActuator()).run(patient))

    def messages(self, run):
        return [e.message for e in run.events]

    def test_no_simulated_line_says_the_call_said_it(self, simulated_run, scripted_run):
        for run in (simulated_run, scripted_run):
            text = " ".join(self.messages(run))
            assert "the call said" not in text
            assert "named on the call" not in text
            assert "the simulated attendant said" in text
            assert "named by the simulated attendant" in text

    def test_scripted_act_says_no_calls_were_placed(self, scripted_run):
        acts = [e.message for e in scripted_run.events if e.phase is AgentPhase.ACT]

        assert acts and all("no calls placed" in m for m in acts)
        assert not any(m.startswith("Placing") for m in acts)

    def test_simulated_act_counts_only_the_real_dials(self, simulated_run):
        first_act = next(e.message for e in simulated_run.events if e.phase is AgentPhase.ACT)

        # Wave 1 is SNF-001 (dialable) and SNF-003 (no demo line).
        assert first_act.startswith("Placing 1 live call(s): Bayview Post-Acute Center")
        assert "1 with no demo line use a scripted attendant" in first_act

    def test_live_calls_counts_real_calls_only(self, simulated_run, scripted_run):
        assert simulated_run.calls_placed == 3
        assert simulated_run.live_calls == 2
        assert scripted_run.live_calls == 0

    def test_real_call_answers_still_read_as_the_call(self, patient):
        """The honest wording must not leak onto genuinely real answers."""
        from tests.conftest import ScriptedActuator

        run = asyncio.run(PlacementAgent(ScriptedActuator({
            "SNF-001": answers(wound_vac="no", sister="Bayview Peninsula Campus"),
            "SNF-004": answers(),
        })).run(patient))
        text = " ".join(self.messages(run))

        assert "the call said" in text
        assert "named on the call" in text
        assert "simulated" not in text

    def test_contradiction_resolution_does_not_claim_a_call(self, scripted_run):
        """Regression: the referral packet said "Live call intelligence overrides
        the directory record" for a scripted run with no call placed."""
        for contradiction in scripted_run.contradictions:
            assert "Live call intelligence" not in contradiction.resolution
            assert "not verified on a call" in contradiction.resolution

    def test_real_call_contradictions_keep_the_live_wording(self, patient):
        from tests.conftest import ScriptedActuator

        run = asyncio.run(PlacementAgent(ScriptedActuator({
            "SNF-001": answers(wound_vac="no", sister="none"),
        })).run(patient))

        assert run.contradictions
        assert all("Live call intelligence" in c.resolution for c in run.contradictions)
