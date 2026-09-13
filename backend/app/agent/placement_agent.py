"""Post-Acute Placement Agent.

Owns the placement goal and runs the closed loop:

    PLAN -> ACT -> OBSERVE -> REASON -> RE-PLAN

Re-planning is what makes this an agent rather than a batch dialer. When a call
comes back, the agent decides what the *next* call should be:

  - a verified match          -> stop early, hand to a human
  - a sister facility named   -> queue it, even outside the search radius
  - nothing left in radius    -> widen the radius and rebuild the queue
  - budget or cycles spent    -> stop and report what was learned

The agent never places a patient. It produces a proposal; a case manager
approves it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from app.agent.planner import PlacementPlanner
from app.agent.llm.brief import CaseManagerBriefer
from app.agent.llm.reviewer import TranscriptReviewer, review_label
from app.agent.reasoning_engine import ReasoningEngine, rank_evaluations
from app.agent.tools.telephony import (
    TelephonyActuator,
    build_result_schema,
    build_task_prompt,
)
from app.config import settings
from app.data.synthetic_data import FACILITIES_BY_ID, PLACEHOLDER_PHONE
from app.models.schemas import (
    AgentEvent,
    AgentPhase,
    AnswersSource,
    CallMode,
    CallObservation,
    Disposition,
    FacilityEvaluation,
    PatientCase,
    PlacementPlan,
    PlacementProposal,
    PlacementRun,
    ReplanTrigger,
    RunStatus,
    VerificationState,
)

log = logging.getLogger(__name__)

EventSink = Callable[[AgentEvent], None | Awaitable[None]]


class PlacementAgent:
    """Runs the placement loop for one patient."""

    def __init__(
        self,
        actuator: TelephonyActuator,
        planner: PlacementPlanner | None = None,
        engine: ReasoningEngine | None = None,
        event_sink: EventSink | None = None,
        max_cycles: int = 4,
        max_concurrent_calls: int | None = None,
        max_calls: int | None = None,
        reviewer: "TranscriptReviewer | None" = None,
        briefer: "CaseManagerBriefer | None" = None,
    ) -> None:
        self._actuator = actuator
        # Optional LLM roles. The reviewer can only downgrade findings; the
        # briefer only summarises. Both are skipped cleanly when absent.
        self._reviewer = reviewer
        self._briefer = briefer or CaseManagerBriefer(None)
        self._planner = planner or PlacementPlanner()
        self._engine = engine or ReasoningEngine()
        self._sink = event_sink
        self._max_cycles = max_cycles
        self._max_concurrent = (
            max_concurrent_calls
            if max_concurrent_calls is not None
            else settings.max_concurrent_calls
        )
        # A ceiling on calls per run, separate from the account-wide budget.
        self._max_calls = max_calls

    # -- events -------------------------------------------------------------

    async def _emit(self, run: PlacementRun, event: AgentEvent) -> None:
        run.events.append(event)
        log.info("[cycle %s] %s: %s", event.cycle, event.phase.value, event.message)
        if self._sink is None:
            return
        result = self._sink(event)
        if asyncio.iscoroutine(result):
            await result

    # -- main loop ----------------------------------------------------------

    async def run(
        self, patient: PatientCase, run: PlacementRun | None = None
    ) -> PlacementRun:
        # A caller may pass its own run object and read it while the loop is
        # still going - the API does this to serve live snapshots.
        run = run or PlacementRun(case_id=patient.case_id)

        radius = float(patient.search_radius_miles)
        called: set[str] = set()
        pending_plan: PlacementPlan | None = None

        for cycle in range(1, self._max_cycles + 1):
            run.cycles_used = cycle

            plan = pending_plan or self._planner.build_plan(
                patient, cycle=cycle, radius_miles=radius, exclude_ids=called
            )
            pending_plan = None
            plan.cycle = cycle
            run.plans.append(plan)

            await self._emit(
                run,
                AgentEvent(
                    cycle=cycle,
                    phase=AgentPhase.PLAN,
                    message=plan.rationale,
                    payload={
                        "queue": plan.queue,
                        "radius_miles": plan.radius_miles,
                        "excluded": plan.excluded,
                    },
                ),
            )

            if plan.is_empty:
                widened = await self._widen(run, patient, cycle, radius)
                if widened is None:
                    break
                radius = widened
                continue

            batch = self._next_batch(plan, run)
            if not batch:
                await self._emit(
                    run,
                    AgentEvent(
                        cycle=cycle,
                        phase=AgentPhase.REPLAN,
                        message="Per-run call ceiling reached; stopping.",
                        trigger=ReplanTrigger.BUDGET_EXHAUSTED,
                    ),
                )
                break

            evaluations = await self._sweep(run, patient, batch, cycle)
            called.update(batch)
            run.evaluations.extend(evaluations)

            matches = [e for e in evaluations if e.is_placeable]
            if matches:
                await self._propose(run, patient, matches, cycle)
                return run

            # No match this cycle. Decide what to try next.
            # A sister named on a call beats an ownership link from the
            # directory; the plan records which one it acted on.
            leads, source = self._collect_leads(evaluations, called), "call"
            if leads and all(
                self._speaker(e) != "the call"
                for e in evaluations
                if e.sister_facility_leads
            ):
                source = "simulated"
            if not leads:
                leads = self._collect_leads(evaluations, called, "ownership_leads")
                source = "directory"
            if leads:
                pending_plan = self._planner.plan_sister_facilities(
                    patient,
                    leads,
                    cycle=cycle + 1,
                    radius_miles=radius,
                    exclude_ids=called,
                    source=source,
                )
                await self._emit(
                    run,
                    AgentEvent(
                        cycle=cycle,
                        phase=AgentPhase.REPLAN,
                        message=pending_plan.rationale,
                        trigger=ReplanTrigger.SISTER_FACILITY_LEAD,
                        payload={"queue": pending_plan.queue, "source": source},
                    ),
                )
                continue

            remaining = [f for f in plan.queue if f not in called]
            if remaining:
                pending_plan = plan.model_copy(update={"queue": remaining})
                continue

            widened = await self._widen(run, patient, cycle, radius)
            if widened is None:
                break
            radius = widened

        return await self._finish_without_match(run)

    # -- phases -------------------------------------------------------------

    def _next_batch(self, plan: PlacementPlan, run: PlacementRun) -> list[str]:
        batch = plan.queue[: self._max_concurrent]
        if self._max_calls is None:
            return batch
        headroom = max(0, self._max_calls - run.calls_placed)
        return batch[:headroom]

    async def _sweep(
        self,
        run: PlacementRun,
        patient: PatientCase,
        facility_ids: list[str],
        cycle: int,
    ) -> list[FacilityEvaluation]:
        """Call a batch of facilities concurrently and reason over the results."""
        facilities = [FACILITIES_BY_ID[fid] for fid in facility_ids]
        schema = build_result_schema(patient)

        await self._emit(
            run,
            AgentEvent(
                cycle=cycle,
                phase=AgentPhase.ACT,
                message=self._act_message(facilities),
                payload={"facility_ids": facility_ids},
            ),
        )

        observations = await asyncio.gather(
            *(
                self._actuator.call_facility(
                    facility,
                    patient,
                    build_task_prompt(patient, facility),
                    schema,
                )
                for facility in facilities
            ),
            return_exceptions=True,
        )

        evaluations: list[FacilityEvaluation] = []

        for facility, observation in zip(facilities, observations):
            if isinstance(observation, BaseException):
                log.error("Call to %s raised: %s", facility.name, observation)
                await self._emit(
                    run,
                    AgentEvent(
                        cycle=cycle,
                        phase=AgentPhase.OBSERVE,
                        message=f"{facility.name}: call failed ({observation})",
                        facility_id=facility.facility_id,
                    ),
                )
                continue

            run.calls_placed += 1
            if observation.mode is CallMode.LIVE:
                run.live_calls += 1
            await self._emit(
                run,
                AgentEvent(
                    cycle=cycle,
                    phase=AgentPhase.OBSERVE,
                    message=self._observe_message(facility.name, observation),
                    facility_id=facility.facility_id,
                    payload={
                        "mode": observation.mode.value,
                        "stand_in_line": observation.stand_in_line,
                        "answers_source": observation.answers_source.value,
                        "simulation_note": observation.simulation_note,
                        "call_id": observation.call_id,
                        "provider_call_id": observation.provider_call_id,
                        "duration_seconds": observation.duration_seconds,
                        "structured_result": observation.structured_result,
                        "transcript_turns": len(observation.transcript_turns),
                    },
                ),
            )

            evaluation = self._engine.evaluate(patient, facility, observation)
            await self._emit(run, self._reason_event(evaluation, cycle))

            if self._reviewer is not None and observation.is_usable:
                evaluation = await self._reviewer.review(patient, facility, evaluation)
                if evaluation.review is not None:
                    await self._emit(run, self._review_event(evaluation, cycle))

            evaluations.append(evaluation)

        return evaluations

    @staticmethod
    def _review_event(evaluation: FacilityEvaluation, cycle: int) -> AgentEvent:
        review = evaluation.review
        label = review_label(evaluation)
        name = evaluation.facility_name
        accepted = review.accepted_flags
        rejected = len(review.flags) - len(accepted)

        if review.error:
            message = f"{name}: {label} unavailable ({review.error}); rule-based result stands"
        elif accepted:
            changes = "; ".join(
                f'{f.code.value} -> {f.to_state.value} ("{f.quote}")' for f in accepted
            )
            message = (
                f"{name}: {label} downgraded {changes}. Now "
                f"{evaluation.disposition.value.replace('_', ' ')}"
            )
        else:
            message = f"{name}: {label} found nothing the rules missed"
        if rejected and not review.error:
            message += f" ({rejected} unsupported flag(s) rejected)"

        return AgentEvent(
            cycle=cycle,
            phase=AgentPhase.REASON,
            message=message,
            facility_id=evaluation.facility_id,
            payload={
                "review": review.model_dump(mode="json"),
                "disposition": evaluation.disposition.value,
                "match_score": evaluation.match_score,
                "answers_source": review.answers_source.value,
            },
        )

    def _act_message(self, facilities: list) -> str:
        names = ", ".join(f.name for f in facilities)
        label = getattr(self._actuator, "mode_label", "")
        if label == "scripted":
            return f"Running {len(facilities)} scripted attendant(s), no calls placed: {names}"
        if label == "replay":
            return f"Replaying {len(facilities)} recorded call(s): {names}"
        if label == "simulated":
            live = [f for f in facilities if f.phone != PLACEHOLDER_PHONE]
            text = f"Placing {len(live)} live call(s): {', '.join(f.name for f in live) or 'none'}"
            if len(live) < len(facilities):
                text += f"; {len(facilities) - len(live)} with no demo line use a scripted attendant"
            return text
        return f"Placing {len(facilities)} concurrent call(s): {names}"

    @staticmethod
    def _speaker(evaluation: FacilityEvaluation) -> str:
        """Who a finding came from - a call, or the simulated attendant."""
        observation = evaluation.observation
        if observation and observation.answers_source is AnswersSource.SIMULATED:
            return "the simulated attendant"
        return "the call"

    @staticmethod
    def _observe_message(name: str, observation: CallObservation) -> str:
        # Simulated answers must be named as such in the headline itself, not
        # only in a payload field a console might forget to render.
        if observation.answers_source is AnswersSource.SIMULATED:
            return f"{name}: {observation.simulation_note}"
        if observation.summary:
            return f"{name}: {observation.summary}"
        return f"{name}: {observation.outcome.value}"

    def _reason_event(
        self, evaluation: FacilityEvaluation, cycle: int
    ) -> AgentEvent:
        if evaluation.contradictions:
            headline = evaluation.contradictions[0]
            message = (
                f"{evaluation.facility_name}: directory said "
                f"'{headline.directory_says}' but {self._speaker(evaluation)} said "
                f"'{headline.call_says}'"
            )
        elif evaluation.disposition is Disposition.MATCH_VERIFIED:
            message = (
                f"{evaluation.facility_name}: all hard requirements confirmed "
                f"(score {evaluation.match_score})"
            )
        elif evaluation.disposition is Disposition.UNREACHED:
            message = f"{evaluation.facility_name}: not reached"
        elif evaluation.disposition is Disposition.NEEDS_FOLLOW_UP:
            # Nothing was refused - it just never got a straight answer. Saying
            # "failed" here would tell a case manager the facility said no.
            unclear = ", ".join(c.value for c in evaluation.disqualifying_codes)
            message = (
                f"{evaluation.facility_name}: nothing refused, but could not "
                f"confirm {unclear} - needs follow-up"
            )
        else:
            refused = ", ".join(
                f.code.value
                for f in evaluation.findings
                if f.state is VerificationState.EXPLICITLY_UNAVAILABLE
            )
            message = f"{evaluation.facility_name}: ruled out - cannot meet {refused}"

        return AgentEvent(
            cycle=cycle,
            phase=AgentPhase.REASON,
            message=message,
            facility_id=evaluation.facility_id,
            trigger=(
                ReplanTrigger.CONTRADICTION_DISQUALIFIED
                if evaluation.contradictions
                and evaluation.disposition is Disposition.DISQUALIFIED
                else None
            ),
            payload={
                "disposition": evaluation.disposition.value,
                "match_score": evaluation.match_score,
                "answers_source": (
                    evaluation.observation.answers_source.value
                    if evaluation.observation
                    else None
                ),
                "contradictions": [
                    c.model_dump(mode="json") for c in evaluation.contradictions
                ],
            },
        )

    # -- re-planning --------------------------------------------------------

    def _collect_leads(
        self,
        evaluations: list[FacilityEvaluation],
        called: set[str],
        field: str = "sister_facility_leads",
    ) -> list[str]:
        leads: list[str] = []
        for evaluation in evaluations:
            for lead in getattr(evaluation, field):
                if lead not in called and lead not in leads:
                    leads.append(lead)
        return leads

    async def _widen(
        self,
        run: PlacementRun,
        patient: PatientCase,
        cycle: int,
        radius: float,
    ) -> float | None:
        wider = self._planner.next_radius(patient, radius)
        if wider is None:
            await self._emit(
                run,
                AgentEvent(
                    cycle=cycle,
                    phase=AgentPhase.REPLAN,
                    message=(
                        f"Radius already at the {patient.max_radius_miles} mi "
                        f"cap; no further expansion available."
                    ),
                    trigger=ReplanTrigger.NO_BEDS_IN_RADIUS,
                ),
            )
            return None

        await self._emit(
            run,
            AgentEvent(
                cycle=cycle,
                phase=AgentPhase.REPLAN,
                message=f"No options left within {radius:.0f} mi; expanding to {wider:.0f} mi.",
                trigger=ReplanTrigger.NO_BEDS_IN_RADIUS,
                payload={"from_miles": radius, "to_miles": wider},
            ),
        )
        return wider

    # -- termination --------------------------------------------------------

    async def _propose(
        self,
        run: PlacementRun,
        patient: PatientCase,
        matches: list[FacilityEvaluation],
        cycle: int,
    ) -> None:
        best = rank_evaluations(matches)[0]

        await self._emit(
            run,
            AgentEvent(
                cycle=cycle,
                phase=AgentPhase.REPLAN,
                message=(
                    f"Verified match at {best.facility_name}; stopping the "
                    f"sweep without calling the remaining facilities."
                ),
                facility_id=best.facility_id,
                trigger=ReplanTrigger.EARLY_STOP_MATCH_FOUND,
            ),
        )

        brief, brief_source, brief_model = await self._briefer.write(patient, run, best)
        run.proposal = PlacementProposal(
            case_id=patient.case_id,
            facility_id=best.facility_id,
            facility_name=best.facility_name,
            match_score=best.match_score,
            evaluation=best,
            brief=brief,
            brief_source=brief_source,
            brief_model=brief_model,
        )
        run.status = RunStatus.AWAITING_APPROVAL

        await self._emit(
            run,
            AgentEvent(
                cycle=cycle,
                phase=AgentPhase.AWAITING_APPROVAL,
                message=(
                    f"Placement proposed at {best.facility_name}. Case manager "
                    f"approval required before any referral is sent."
                ),
                facility_id=best.facility_id,
                payload={"brief_source": brief_source},
            ),
        )

    async def _finish_without_match(self, run: PlacementRun) -> PlacementRun:
        run.status = RunStatus.NO_MATCH_FOUND
        # Through _emit, not straight onto run.events: a live console must hear
        # that the run ended, or it waits on a spinner forever.
        await self._emit(
            run,
            AgentEvent(
                cycle=run.cycles_used,
                phase=AgentPhase.COMPLETE,
                message=(
                    f"No verified match after {run.calls_placed} call(s). "
                    f"Escalating to the case manager with the full call record."
                ),
            ),
        )
        return run
