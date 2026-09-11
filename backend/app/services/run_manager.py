"""Background placement runs and their live event streams.

A run is started by an HTTP request but takes minutes when calls are live, so it
executes as a background task. Its events fan out through a `RunChannel` to any
number of WebSocket subscribers.

The channel keeps its full history. A console that connects after the run has
started - or reconnects after a dropped socket - first receives everything it
missed, then the live tail. Without that, a browser refresh mid-run would show a
half-empty cognitive loop.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.agent.placement_agent import PlacementAgent
from app.agent.tools.budget import CallBudget, budget as default_budget
from app.agent.tools.calle_actuator import TelephonyConfigError
from app.agent.tools.factory import build_actuator
from app.agent.tools.telephony import TelephonyActuator
from app.config import TelephonyMode, settings
from app.data.synthetic_data import (
    FACILITIES_BY_ID,
    PLACEHOLDER_PHONE,
    get_patient,
)
from app.models.schemas import (
    AgentEvent,
    AgentPhase,
    ApprovalStatus,
    PlacementRun,
    RunStatus,
)

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Errors the API layer maps onto HTTP status codes
# ---------------------------------------------------------------------------


class RunNotFound(LookupError):
    pass


class RunConflict(RuntimeError):
    """The request is valid but clashes with current state (HTTP 409)."""


class RunRejected(ValueError):
    """The request cannot be honoured as asked (HTTP 422)."""


# ---------------------------------------------------------------------------
# Request and record models
# ---------------------------------------------------------------------------


class StartRunRequest(BaseModel):
    case_id: str
    mode: TelephonyMode | None = Field(
        default=None,
        description="Telephony mode. Defaults to TELEPHONY_MODE from .env.",
    )
    live_facility_ids: list[str] = Field(
        default_factory=list,
        description="Dial these facilities live and replay the rest (hybrid).",
    )
    max_cycles: int = Field(default=4, ge=1, le=10)
    max_calls: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Ceiling on calls for this run. Required for all-live runs.",
    )
    replay_latency_seconds: float = Field(
        default=0.0,
        ge=0.0,
        le=30.0,
        description="Simulated per-call delay when replaying, for demo pacing.",
    )


class RunRecord(BaseModel):
    """A placement run plus the bookkeeping the API needs around it."""

    run_id: str
    case_id: str
    telephony: str
    live_facility_ids: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    run: PlacementRun

    @property
    def spends_live_calls(self) -> bool:
        return self.telephony in {"live", "hybrid"}


# ---------------------------------------------------------------------------
# Event fan-out
# ---------------------------------------------------------------------------

# Sentinel pushed onto subscriber queues when the channel closes.
_CLOSED = object()


class RunChannel:
    """Fan-out of one run's messages to many subscribers, with full history."""

    def __init__(self) -> None:
        self._history: list[dict[str, Any]] = []
        self._subscribers: set[asyncio.Queue] = set()
        self.closed = False

    def publish(self, message: dict[str, Any]) -> None:
        if self.closed:
            return
        self._history.append(message)
        for queue in self._subscribers:
            queue.put_nowait(message)

    def subscribe(self) -> tuple[asyncio.Queue, list[dict[str, Any]]]:
        """Register a subscriber and return the backlog it missed.

        Safe without a lock: there is no await between copying the history and
        registering the queue, so no message can slip between the two.
        """
        queue: asyncio.Queue = asyncio.Queue()
        backlog = list(self._history)
        if self.closed:
            queue.put_nowait(_CLOSED)
        else:
            self._subscribers.add(queue)
        return queue, backlog

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for queue in self._subscribers:
            queue.put_nowait(_CLOSED)
        self._subscribers.clear()

    @staticmethod
    def is_closed_marker(message: object) -> bool:
        return message is _CLOSED


def event_message(event: AgentEvent) -> dict[str, Any]:
    return {"type": "event", "event": event.model_dump(mode="json")}


def run_message(record: RunRecord) -> dict[str, Any]:
    return {"type": "run", "run": record.model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Run manager
# ---------------------------------------------------------------------------

ActuatorFactory = Callable[[StartRunRequest], TelephonyActuator]


def default_actuator_factory(request: StartRunRequest) -> TelephonyActuator:
    return build_actuator(
        mode=request.mode,
        live_facility_ids=request.live_facility_ids or None,
        replay_latency_seconds=request.replay_latency_seconds,
    )


class RunManager:
    """Starts, tracks, and resolves placement runs."""

    def __init__(
        self,
        actuator_factory: ActuatorFactory = default_actuator_factory,
        call_budget: CallBudget | None = None,
    ) -> None:
        self._actuator_factory = actuator_factory
        self._budget = call_budget or default_budget
        self._records: dict[str, RunRecord] = {}
        self._channels: dict[str, RunChannel] = {}
        self._tasks: set[asyncio.Task] = set()

    # -- queries ------------------------------------------------------------

    @property
    def budget(self) -> CallBudget:
        return self._budget

    def get(self, run_id: str) -> RunRecord:
        if run_id not in self._records:
            raise RunNotFound(run_id)
        return self._records[run_id]

    def channel(self, run_id: str) -> RunChannel:
        if run_id not in self._channels:
            raise RunNotFound(run_id)
        return self._channels[run_id]

    def list(self) -> list[RunRecord]:
        return sorted(
            self._records.values(), key=lambda r: r.started_at, reverse=True
        )

    # -- start --------------------------------------------------------------

    def _validate_live(self, request: StartRunRequest, telephony: str) -> None:
        """Refuse any run that could spend call credit it should not.

        A stray click in the console must never be able to drain the budget or
        dial a number nobody is standing by to answer.
        """
        if telephony not in {"live", "hybrid"}:
            return

        active = [
            r
            for r in self._records.values()
            if r.spends_live_calls and not r.run.status.is_terminal
        ]
        if active:
            raise RunConflict(
                f"Run {active[0].run_id} is already placing live calls. One live "
                f"run at a time - the demo line can only answer one call."
            )

        if telephony == "hybrid":
            for fid in request.live_facility_ids:
                facility = FACILITIES_BY_ID.get(fid)
                if facility is None:
                    raise RunRejected(f"Unknown facility id: {fid}")
                if facility.phone == PLACEHOLDER_PHONE:
                    raise RunRejected(
                        f"{facility.name} has no demo receiver number, so it "
                        f"cannot be dialed live. Set DEMO_PHONE_PRIMARY / "
                        f"DEMO_PHONE_SECONDARY."
                    )
            worst_case = len(request.live_facility_ids)
        else:
            if request.max_calls is None:
                raise RunRejected(
                    "All-live runs must set max_calls, so the run has a hard "
                    "ceiling on the credit it can spend."
                )
            worst_case = request.max_calls

        if worst_case > self._budget.remaining:
            raise RunRejected(
                f"This run could place {worst_case} live call(s) but only "
                f"{self._budget.remaining} remain in the budget."
            )

    def start(self, request: StartRunRequest) -> RunRecord:
        try:
            patient = get_patient(request.case_id)
        except KeyError as exc:
            raise RunNotFound(request.case_id) from exc

        try:
            actuator = self._actuator_factory(request)
        except TelephonyConfigError as exc:
            raise RunRejected(str(exc)) from exc

        telephony = getattr(actuator, "mode_label", "unknown")

        # build_actuator falls back to replay when live credentials are
        # missing. That is right for a CLI, but a console that asked for live
        # calls must be told, not quietly handed recordings.
        wants_live = request.mode is TelephonyMode.LIVE or bool(
            request.live_facility_ids
        )
        if wants_live and telephony not in {"live", "hybrid"}:
            raise RunRejected(
                "Live telephony was requested but is unavailable - check "
                "CALLE_API_KEY. Nothing was dialed."
            )

        self._validate_live(request, telephony)

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        record = RunRecord(
            run_id=run_id,
            case_id=patient.case_id,
            telephony=telephony,
            live_facility_ids=list(request.live_facility_ids),
            run=PlacementRun(case_id=patient.case_id),
        )
        channel = RunChannel()
        self._records[run_id] = record
        self._channels[run_id] = channel

        agent = PlacementAgent(
            actuator,
            event_sink=lambda event: channel.publish(event_message(event)),
            max_cycles=request.max_cycles,
            max_calls=request.max_calls,
        )

        task = asyncio.create_task(self._execute(record, channel, agent, patient))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        log.info(
            "Started %s for case %s (telephony=%s)",
            run_id,
            patient.case_id,
            telephony,
        )
        return record

    async def _execute(
        self,
        record: RunRecord,
        channel: RunChannel,
        agent: PlacementAgent,
        patient,
    ) -> None:
        try:
            await agent.run(patient, record.run)
        except asyncio.CancelledError:
            record.run.status = RunStatus.FAILED
            record.run.error = "Run cancelled (server shutting down)."
            raise
        except Exception as exc:  # noqa: BLE001 - a run must never die silently
            log.exception("Run %s failed", record.run_id)
            record.run.status = RunStatus.FAILED
            record.run.error = f"{type(exc).__name__}: {exc}"
        finally:
            if record.run.status is not RunStatus.AWAITING_APPROVAL:
                record.finished_at = _now()
            channel.publish(run_message(record))
            # A run awaiting approval stays open: connected consoles should
            # see the case manager's decision arrive.
            if record.run.status.is_terminal:
                channel.close()

    # -- human-in-the-loop decision ----------------------------------------

    def decide(
        self,
        run_id: str,
        *,
        approve: bool,
        decided_by: str,
        note: str | None = None,
    ) -> RunRecord:
        record = self.get(run_id)
        run = record.run

        if run.status is not RunStatus.AWAITING_APPROVAL or run.proposal is None:
            raise RunConflict(
                f"Run {run_id} is {run.status.value}; only a run awaiting "
                f"approval can be approved or declined."
            )

        proposal = run.proposal
        proposal.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.DECLINED
        proposal.decided_by = decided_by
        proposal.decided_at = _now()
        proposal.decision_note = note

        run.status = RunStatus.APPROVED if approve else RunStatus.DECLINED
        record.finished_at = _now()

        verb = "approved" if approve else "declined"
        event = AgentEvent(
            cycle=run.cycles_used,
            phase=AgentPhase.COMPLETE,
            message=(
                f"Placement at {proposal.facility_name} {verb} by {decided_by}."
                + (f" Note: {note}" if note else "")
            ),
            facility_id=proposal.facility_id,
            payload={"decision": verb, "decided_by": decided_by},
        )
        run.events.append(event)

        channel = self._channels[run_id]
        channel.publish(event_message(event))
        channel.publish(run_message(record))
        channel.close()
        return record

    # -- lifecycle ----------------------------------------------------------

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        for channel in self._channels.values():
            channel.close()
