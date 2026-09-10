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
from app.agent.reasoning_engine import ReasoningEngine, rank_evaluations
from app.agent.tools.telephony import (
    TelephonyActuator,
    build_result_schema,
    build_task_prompt,
)
from app.config import settings
from app.data.synthetic_data import FACILITIES_BY_ID
from app.models.schemas import (
    AgentEvent,
    AgentPhase,
    CallObservation,
    Disposition,
    FacilityEvaluation,
    PatientCase,
    PlacementPlan,
    PlacementProposal,
    PlacementRun,
    ReplanTrigger,
    RunStatus,
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
    ) -> None:
        self._actuator = actuator
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

    async def run(self, patient: PatientCase) -> PlacementRun:
        run = PlacementRun(case_id=patient.case_id)

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
            leads = self._collect_leads(evaluations, called)
            if leads:
                pending_plan = self._planner.plan_sister_facilities(
                    patient,
                    leads,
                    cycle=cycle + 1,
                    radius_miles=radius,
                    exclude_ids=called,
                )
                await self._emit(
                    run,
                    AgentEvent(
                        cycle=cycle,
                        phase=AgentPhase.REPLAN,
                        message=pending_plan.rationale,
                        trigger=ReplanTrigger.SISTER_FACILITY_LEAD,
                        payload={"queue": pending_plan.queue},
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

        return self._finish_without_match(run)

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
                message=(
                    f"Placing {len(facilities)} concurrent call(s): "
                    f"{', '.join(f.name for f in facilities)}"
                ),
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
            await self._emit(
                run,
                AgentEvent(
                    cycle=cycle,
                    phase=AgentPhase.OBSERVE,
                    message=(
                        f"{facility.name}: {observation.summary}"
                        if observation.summary
                        else f"{facility.name}: {observation.outcome.value}"
                    ),
                    facility_id=facility.facility_id,
                    payload={
                        "mode": observation.mode.value,
                        "call_id": observation.call_id,
                        "provider_call_id": observation.provider_call_id,
                        "duration_seconds": observation.duration_seconds,
                        "structured_result": observation.structured_result,
                        "transcript_turns": len(observation.transcript_turns),
                    },
                ),
            )

            evaluation = self._engine.evaluate(patient, facility, observation)
            evaluations.append(evaluation)
            await self._emit(run, self._reason_event(evaluation, cycle))

        return evaluations

    def _reason_event(
        self, evaluation: FacilityEvaluation, cycle: int
    ) -> AgentEvent:
        if evaluation.contradictions:
            headline = evaluation.contradictions[0]
            message = (
                f"{evaluation.facility_name}: directory said "
                f"'{headline.directory_says}' but the call said "
                f"'{headline.call_says}'"
            )
        elif evaluation.disposition is Disposition.MATCH_VERIFIED:
            message = (
                f"{evaluation.facility_name}: all hard requirements confirmed "
                f"(score {evaluation.match_score})"
            )
        elif evaluation.disposition is Disposition.UNREACHED:
            message = f"{evaluation.facility_name}: not reached"
        else:
            failed = ", ".join(c.value for c in evaluation.disqualifying_codes)
            message = f"{evaluation.facility_name}: failed on {failed}"

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
                "contradictions": [
                    c.model_dump(mode="json") for c in evaluation.contradictions
                ],
            },
        )

    # -- re-planning --------------------------------------------------------

    def _collect_leads(
        self, evaluations: list[FacilityEvaluation], called: set[str]
    ) -> list[str]:
        leads: list[str] = []
        for evaluation in evaluations:
            for lead in evaluation.sister_facility_leads:
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

        run.proposal = PlacementProposal(
            case_id=patient.case_id,
            facility_id=best.facility_id,
            facility_name=best.facility_name,
            match_score=best.match_score,
            evaluation=best,
        )
        run.status = RunStatus.AWAITING_APPROVAL

        await self._emit(
            run,
            AgentEvent(
                cycle=cycle,
                phase=AgentPhase.AWAITING_APPROVAL,
                message=(
                    f"Referral packet drafted for {best.facility_name}. "
                    f"Case manager approval required before anything is sent."
                ),
                facility_id=best.facility_id,
            ),
        )

    def _finish_without_match(self, run: PlacementRun) -> PlacementRun:
        run.status = RunStatus.NO_MATCH_FOUND
        run.events.append(
            AgentEvent(
                cycle=run.cycles_used,
                phase=AgentPhase.COMPLETE,
                message=(
                    f"No verified match after {run.calls_placed} call(s). "
                    f"Escalating to the case manager with the full call record."
                ),
            )
        )
        return run
