"""REST routes for the Case Manager Command Console."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agent.tools import cassette
from app.config import settings
from app.data.synthetic_data import FACILITIES, PATIENTS, PLACEHOLDER_PHONE
from app.models.schemas import Facility, PatientCase
from app.services.run_manager import (
    RunManager,
    RunNotFound,
    RunRecord,
    StartRunRequest,
)

router = APIRouter(prefix="/api")


def get_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class BudgetView(BaseModel):
    spent: int
    ceiling: int
    remaining: int


class HealthView(BaseModel):
    status: str = "ok"
    telephony_mode: str
    live_available: bool
    budget: BudgetView
    cassettes: int
    synthetic_data_only: bool = True


class FacilityView(BaseModel):
    facility: Facility
    # False for directory entries with no demo receiver attached - the console
    # uses this to grey out the "dial live" toggle.
    dialable: bool


class RunSummary(BaseModel):
    run_id: str
    case_id: str
    status: str
    telephony: str
    calls_placed: int
    live_calls: int
    cycles_used: int
    started_at: Any
    finished_at: Any
    proposed_facility: str | None = None

    @classmethod
    def of(cls, record: RunRecord) -> "RunSummary":
        run = record.run
        return cls(
            run_id=record.run_id,
            case_id=record.case_id,
            status=run.status.value,
            telephony=record.telephony,
            calls_placed=run.calls_placed,
            live_calls=run.live_calls,
            cycles_used=run.cycles_used,
            started_at=record.started_at,
            finished_at=record.finished_at,
            proposed_facility=run.proposal.facility_name if run.proposal else None,
        )


class DecisionRequest(BaseModel):
    decided_by: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


def _budget_view(manager: RunManager) -> BudgetView:
    b = manager.budget
    return BudgetView(spent=b.spent, ceiling=b.ceiling, remaining=b.remaining)


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthView)
async def health(manager: RunManager = Depends(get_manager)) -> HealthView:
    return HealthView(
        telephony_mode=settings.telephony_mode.value,
        live_available=settings.can_call_live,
        budget=_budget_view(manager),
        cassettes=len(cassette.available()),
    )


@router.get("/budget", response_model=BudgetView)
async def get_budget(manager: RunManager = Depends(get_manager)) -> BudgetView:
    return _budget_view(manager)


# ---------------------------------------------------------------------------
# Synthetic reference data
# ---------------------------------------------------------------------------


@router.get("/patients", response_model=list[PatientCase])
async def list_patients() -> list[PatientCase]:
    return list(PATIENTS.values())


@router.get("/patients/{case_id}", response_model=PatientCase)
async def get_patient_case(case_id: str) -> PatientCase:
    if case_id not in PATIENTS:
        raise RunNotFound(case_id)
    return PATIENTS[case_id]


@router.get("/facilities", response_model=list[FacilityView])
async def list_facilities() -> list[FacilityView]:
    return [
        FacilityView(facility=f, dialable=f.phone != PLACEHOLDER_PHONE)
        for f in sorted(FACILITIES, key=lambda f: f.distance_miles)
    ]


# ---------------------------------------------------------------------------
# Placement runs
# ---------------------------------------------------------------------------


@router.post(
    "/runs",
    response_model=RunRecord,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_run(
    body: StartRunRequest, manager: RunManager = Depends(get_manager)
) -> RunRecord:
    """Start a placement run in the background.

    Returns immediately with the run id. Follow progress on
    `/ws/runs/{run_id}`, or poll `GET /api/runs/{run_id}`.
    """
    return manager.start(body)


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(manager: RunManager = Depends(get_manager)) -> list[RunSummary]:
    return [RunSummary.of(r) for r in manager.list()]


@router.get("/runs/{run_id}", response_model=RunRecord)
async def get_run(run_id: str, manager: RunManager = Depends(get_manager)) -> RunRecord:
    return manager.get(run_id)


@router.get(
    "/runs/{run_id}/packet",
    response_class=FileResponse,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def get_packet(run_id: str, manager: RunManager = Depends(get_manager)) -> FileResponse:
    """The referral packet PDF. Drafted when the run reaches the human gate and
    regenerated with the decision once a case manager approves or declines."""
    path = manager.packet_file(run_id)
    if path is None:
        raise RunNotFound(f"referral packet for {run_id}")
    return FileResponse(path, media_type="application/pdf", filename=f"referral-{run_id}.pdf")


@router.post("/runs/{run_id}/approve", response_model=RunRecord)
async def approve_run(
    run_id: str,
    body: DecisionRequest,
    manager: RunManager = Depends(get_manager),
) -> RunRecord:
    """The human-in-the-loop gate. Only a case manager's approval moves a
    proposed placement forward; the agent cannot call this on its own behalf."""
    return manager.decide(
        run_id, approve=True, decided_by=body.decided_by, note=body.note
    )


@router.post("/runs/{run_id}/decline", response_model=RunRecord)
async def decline_run(
    run_id: str,
    body: DecisionRequest,
    manager: RunManager = Depends(get_manager),
) -> RunRecord:
    return manager.decide(
        run_id, approve=False, decided_by=body.decided_by, note=body.note
    )
