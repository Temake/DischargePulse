"""Tests for the planner and the closed Plan/Act/Observe/Reason/Re-Plan loop.

The whole loop runs against `ScriptedActuator`, so these exercise the real
agent - real planner, real reasoning engine, real re-planning - with no phone,
no cassettes and no network.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agent.placement_agent import PlacementAgent
from app.agent.planner import PlacementPlanner
from app.data.synthetic_data import get_patient
from app.models.schemas import (
    AgentPhase,
    CallOutcome,
    Disposition,
    ReplanTrigger,
    RunStatus,
)
from tests.conftest import ScriptedActuator, answers, make_observation


def run_agent(actuator, patient, **kwargs):
    agent = PlacementAgent(actuator, **kwargs)
    return asyncio.run(agent.run(patient))


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class TestPlanner:
    def test_plan_only_includes_facilities_in_radius(self, patient):
        plan = PlacementPlanner().build_plan(patient, radius_miles=15)

        assert "SNF-001" in plan.queue      # 4.2 mi
        assert "SNF-004" not in plan.queue  # 18.6 mi
        assert "SNF-004" in plan.excluded

    def test_queue_is_ranked_by_soft_preferences(self, patient):
        plan = PlacementPlanner().build_plan(patient, radius_miles=15)

        # SNF-001 is nearest and a preferred partner.
        assert plan.queue[0] == "SNF-001"

    def test_out_of_network_facilities_are_pruned_before_calling(self, patient):
        """SNF-002 takes Kaiser and Medicare; the patient is Aetna."""
        plan = PlacementPlanner().build_plan(patient, radius_miles=15)

        assert "SNF-002" not in plan.queue
        assert "Aetna" in plan.excluded["SNF-002"]

    def test_already_called_facilities_are_not_requeued(self, patient):
        plan = PlacementPlanner().build_plan(
            patient, radius_miles=15, exclude_ids={"SNF-001"}
        )

        assert "SNF-001" not in plan.queue

    def test_radius_expands_stepwise_up_to_the_cap(self, patient):
        planner = PlacementPlanner()

        assert planner.next_radius(patient, 15) == 30  # capped at max
        assert planner.next_radius(patient, 30) is None

    def test_widening_the_radius_reveals_new_facilities(self, patient):
        planner = PlacementPlanner()
        narrow = planner.build_plan(patient, radius_miles=15)
        wide = planner.build_plan(patient, radius_miles=30)

        assert set(narrow.queue) < set(wide.queue)

    def test_sister_facility_plan_ignores_the_radius(self, patient):
        """A warm lead outranks the radius rule that would exclude it."""
        plan = PlacementPlanner().plan_sister_facilities(
            patient, ["SNF-004"], cycle=2, radius_miles=15
        )

        assert plan.queue == ["SNF-004"]

    def test_sister_plan_skips_facilities_already_called(self, patient):
        plan = PlacementPlanner().plan_sister_facilities(
            patient, ["SNF-004"], cycle=2, radius_miles=15, exclude_ids={"SNF-004"}
        )

        assert plan.queue == []


# ---------------------------------------------------------------------------
# The demo narrative, end to end
# ---------------------------------------------------------------------------


class TestDemoNarrative:
    """SNF-001 contradicts its directory record and names its sister campus,
    which turns out to be the match. This is the story the video tells."""

    @pytest.fixture
    def actuator(self):
        return ScriptedActuator(
            {
                "SNF-001": answers(
                    bed="yes",
                    wound_vac="no",
                    wound_vac_detail=(
                        "Our wound care nurse is out this week and the night "
                        "nurse isn't signed off on the VAC."
                    ),
                    sister="Bayview Peninsula Campus",
                ),
                "SNF-003": answers(bed="no"),
                "SNF-004": answers(coordinator="Marcus", fax="555-0198"),
            }
        )

    def test_agent_reaches_a_verified_match(self, actuator, patient):
        run = run_agent(actuator, patient)

        assert run.status is RunStatus.AWAITING_APPROVAL
        assert run.proposal is not None
        assert run.proposal.facility_id == "SNF-004"

    def test_agent_calls_the_sister_facility_it_was_told_about(
        self, actuator, patient
    ):
        run_agent(actuator, patient)

        assert "SNF-001" in actuator.calls
        assert "SNF-004" in actuator.calls
        assert actuator.calls.index("SNF-001") < actuator.calls.index("SNF-004")

    def test_out_of_network_facility_is_never_called(self, actuator, patient):
        run_agent(actuator, patient)

        assert "SNF-002" not in actuator.calls

    def test_contradiction_is_recorded_on_the_run(self, actuator, patient):
        run = run_agent(actuator, patient)

        assert len(run.contradictions) >= 1
        wound = next(c for c in run.contradictions if c.code.value == "wound_vac")
        assert "signed off" in (wound.quote or "")

    def test_contradiction_disqualifies_the_facility(self, actuator, patient):
        run = run_agent(actuator, patient)
        evaluation = run.evaluation_for("SNF-001")

        assert evaluation.disposition is Disposition.DISQUALIFIED

    def test_loop_emits_every_phase(self, actuator, patient):
        run = run_agent(actuator, patient)
        phases = {e.phase for e in run.events}

        assert AgentPhase.PLAN in phases
        assert AgentPhase.ACT in phases
        assert AgentPhase.OBSERVE in phases
        assert AgentPhase.REASON in phases
        assert AgentPhase.REPLAN in phases
        assert AgentPhase.AWAITING_APPROVAL in phases

    def test_sister_lead_is_the_replan_trigger(self, actuator, patient):
        run = run_agent(actuator, patient)
        triggers = [e.trigger for e in run.events if e.trigger]

        assert ReplanTrigger.SISTER_FACILITY_LEAD in triggers

    def test_a_spoken_lead_is_labelled_as_call_evidence(self, actuator, patient):
        run = run_agent(actuator, patient)
        replan = next(
            e for e in run.events if e.trigger is ReplanTrigger.SISTER_FACILITY_LEAD
        )

        assert replan.payload["source"] == "call"
        assert "named on the call" in replan.message

    def test_run_stops_at_the_human_gate(self, actuator, patient):
        """The agent proposes. It never places."""
        run = run_agent(actuator, patient)

        assert run.status is RunStatus.AWAITING_APPROVAL
        assert run.proposal.status.value == "pending"
        assert run.proposal.packet_path is None


# ---------------------------------------------------------------------------
# Re-planning behaviours
# ---------------------------------------------------------------------------


class TestReplanning:
    def test_early_stop_skips_remaining_facilities(self, patient):
        """A verified match ends the sweep; no further credit is spent."""
        actuator = ScriptedActuator(
            {"SNF-001": answers(), "SNF-003": answers()}
        )
        run = run_agent(actuator, patient, max_concurrent_calls=1)

        assert run.status is RunStatus.AWAITING_APPROVAL
        assert actuator.calls == ["SNF-001"]
        triggers = [e.trigger for e in run.events if e.trigger]
        assert ReplanTrigger.EARLY_STOP_MATCH_FOUND in triggers

    def test_radius_expands_when_nothing_in_range_qualifies(self, patient):
        actuator = ScriptedActuator(
            {
                "SNF-001": answers(bed="no", sister="none"),
                "SNF-003": answers(bed="no"),
                "SNF-004": answers(bed="no"),
                "SNF-006": answers(),
            }
        )
        run = run_agent(actuator, patient)
        triggers = [e.trigger for e in run.events if e.trigger]

        assert ReplanTrigger.NO_BEDS_IN_RADIUS in triggers
        assert "SNF-006" in actuator.calls  # 27.9 mi, only reachable at 30

    def test_no_match_anywhere_ends_without_a_proposal(self, patient):
        actuator = ScriptedActuator(
            {
                fid: answers(bed="no", sister="none")
                for fid in ["SNF-001", "SNF-003", "SNF-004", "SNF-006"]
            }
        )
        run = run_agent(actuator, patient)

        assert run.status is RunStatus.NO_MATCH_FOUND
        assert run.proposal is None
        assert run.events[-1].phase is AgentPhase.COMPLETE

    def test_unreachable_facilities_do_not_stop_the_loop(self, patient):
        """A no-answer is a dead end for that facility, not for the run."""
        actuator = ScriptedActuator(
            {
                "SNF-001": make_observation(
                    "SNF-001", outcome=CallOutcome.NO_ANSWER, structured_result=None
                ),
                "SNF-003": answers(),
            }
        )
        run = run_agent(actuator, patient, max_concurrent_calls=2)

        assert run.status is RunStatus.AWAITING_APPROVAL
        assert run.proposal.facility_id == "SNF-003"
        assert run.evaluation_for("SNF-001").disposition is Disposition.UNREACHED

    def test_a_raising_call_does_not_abort_the_sweep(self, patient):
        class Exploding(ScriptedActuator):
            async def call_facility(self, facility, patient, objective=None, result_schema=None):
                self.calls.append(facility.facility_id)
                if facility.facility_id == "SNF-001":
                    raise RuntimeError("carrier rejected the call")
                return await super().call_facility(
                    facility, patient, objective, result_schema
                )

        actuator = Exploding({"SNF-003": answers()})
        run = run_agent(actuator, patient, max_concurrent_calls=2)

        assert run.status is RunStatus.AWAITING_APPROVAL
        assert run.proposal.facility_id == "SNF-003"

    def test_cycle_ceiling_is_respected(self, patient):
        actuator = ScriptedActuator(
            {fid: answers(bed="no", sister="none") for fid in ["SNF-001", "SNF-003"]}
        )
        run = run_agent(actuator, patient, max_cycles=1, max_concurrent_calls=1)

        assert run.cycles_used == 1
        assert len(actuator.calls) == 1

    def test_per_run_call_ceiling_is_respected(self, patient):
        actuator = ScriptedActuator(
            {
                fid: answers(bed="no", sister="none")
                for fid in ["SNF-001", "SNF-003", "SNF-004", "SNF-006"]
            }
        )
        run = run_agent(actuator, patient, max_calls=2, max_concurrent_calls=1)

        assert run.calls_placed <= 2
        assert len(actuator.calls) <= 2

    def test_concurrency_limit_caps_each_wave(self, patient):
        actuator = ScriptedActuator(
            {fid: answers(bed="no", sister="none") for fid in ["SNF-001", "SNF-003"]}
        )
        run = run_agent(actuator, patient, max_cycles=1, max_concurrent_calls=2)

        act = next(e for e in run.events if e.phase is AgentPhase.ACT)
        assert len(act.payload["facility_ids"]) <= 2

    def test_no_facility_is_called_twice(self, patient):
        actuator = ScriptedActuator(
            {
                fid: answers(bed="no", sister="Bayview Peninsula Campus")
                for fid in ["SNF-001", "SNF-003", "SNF-004", "SNF-006"]
            }
        )
        run_agent(actuator, patient)

        assert len(actuator.calls) == len(set(actuator.calls))


# ---------------------------------------------------------------------------
# Event streaming
# ---------------------------------------------------------------------------


class TestEventStream:
    def test_events_are_pushed_to_the_sink_as_they_happen(self, patient):
        seen = []
        actuator = ScriptedActuator({"SNF-001": answers()})
        agent = PlacementAgent(actuator, event_sink=seen.append)
        run = asyncio.run(agent.run(patient))

        assert seen
        assert len(seen) == len(run.events)

    def test_async_sinks_are_awaited(self, patient):
        seen = []

        async def sink(event):
            seen.append(event)

        actuator = ScriptedActuator({"SNF-001": answers()})
        agent = PlacementAgent(actuator, event_sink=sink)
        asyncio.run(agent.run(patient))

        assert seen

    def test_observe_events_carry_call_provenance(self, patient):
        """The UI badges LIVE vs REPLAY from this payload."""
        actuator = ScriptedActuator({"SNF-001": answers()})
        run = run_agent(actuator, patient)

        observe = next(e for e in run.events if e.phase is AgentPhase.OBSERVE)
        assert observe.payload["mode"] in {"live", "replay"}
        assert observe.payload["call_id"]
        assert observe.payload["provider_call_id"]

    def test_plan_events_explain_exclusions(self, patient):
        actuator = ScriptedActuator({"SNF-001": answers()})
        run = run_agent(actuator, patient)

        plan = next(e for e in run.events if e.phase is AgentPhase.PLAN)
        assert "SNF-002" in plan.payload["excluded"]


# ---------------------------------------------------------------------------
# Lead provenance
# ---------------------------------------------------------------------------


class TestLeadProvenance:
    """Regression: a real call to CALL-E's test line answered 'unknown' to
    everything and named no sister facility, yet the console reported a
    'sister facility lead from a live call'. Directory ownership data must
    never be presented as something said on a call."""

    @pytest.fixture
    def unhelpful_call(self):
        return ScriptedActuator(
            {
                "SNF-001": answers(
                    payer="unknown",
                    bed="unknown",
                    wound_vac="unknown",
                    iv="unknown",
                    coordinator="",
                    fax="",
                    sister="none",
                ),
            }
        )

    def test_directory_lead_is_labelled_as_directory_data(self, unhelpful_call, patient):
        run = run_agent(unhelpful_call, patient)
        replan = next(
            e for e in run.events if e.trigger is ReplanTrigger.SISTER_FACILITY_LEAD
        )

        assert replan.payload["source"] == "directory"
        assert "not confirmed on a call" in replan.message
        assert "named on the call" not in replan.message

    def test_directory_lead_is_still_followed_as_a_fallback(self, unhelpful_call, patient):
        run_agent(unhelpful_call, patient)

        assert "SNF-004" in unhelpful_call.calls

    def test_no_event_claims_call_evidence_that_does_not_exist(
        self, unhelpful_call, patient
    ):
        run = run_agent(unhelpful_call, patient)

        assert not any("named on the call" in e.message for e in run.events)

    def test_unanswered_questions_read_as_follow_up_not_failure(
        self, unhelpful_call, patient
    ):
        """'unknown' means nobody would commit - not that the facility said no."""
        run = run_agent(unhelpful_call, patient)
        reason = next(
            e
            for e in run.events
            if e.phase is AgentPhase.REASON and e.facility_id == "SNF-001"
        )

        assert reason.payload["disposition"] == "needs_follow_up"
        assert "needs follow-up" in reason.message
        assert "failed" not in reason.message
        assert "ruled out" not in reason.message

    def test_an_explicit_refusal_reads_as_ruled_out(self, patient):
        """SNF-002's directory already says no wound VAC and out of network, so
        refusals matching it are a plain rule-out rather than a contradiction."""
        from app.agent.reasoning_engine import ReasoningEngine
        from app.data.synthetic_data import get_facility

        evaluation = ReasoningEngine().evaluate(
            patient,
            get_facility("SNF-002"),
            make_observation(
                "SNF-002", structured_result=answers(payer="no", wound_vac="no")
            ),
        )
        event = PlacementAgent(ScriptedActuator({}))._reason_event(evaluation, 1)

        assert not evaluation.contradictions
        assert event.message.endswith(
            "ruled out - cannot meet payer_network, wound_vac"
        )
