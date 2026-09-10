"""Shared fixtures.

`ScriptedActuator` is the third implementation of the telephony contract, used
only by tests. Because the agent depends on the Protocol rather than a concrete
class, the entire loop can be driven from a dict of canned answers - no phone,
no cassettes, no network.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.models.schemas import (
    CallMode,
    CallObservation,
    CallOutcome,
    Facility,
    PatientCase,
)


def make_observation(
    facility_id: str,
    *,
    phone: str = "+15555550100",
    mode: CallMode = CallMode.REPLAY,
    outcome: CallOutcome = CallOutcome.COMPLETED,
    structured_result: dict[str, Any] | None = None,
    summary: str = "Spoke with admissions.",
    duration_seconds: float = 118.0,
) -> CallObservation:
    """Build a terminal observation shaped exactly like CALL-E returns one."""
    now = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
    return CallObservation(
        facility_id=facility_id,
        phone=phone,
        mode=mode,
        call_id=f"call_{facility_id.lower()}",
        provider_call_id=f"prov_{facility_id.lower()}",
        started_at=now,
        completed_at=now,
        duration_seconds=duration_seconds,
        outcome=outcome,
        structured_result=structured_result,
        summary=summary,
        task_completed=outcome is CallOutcome.COMPLETED,
        confidence_score=0.9,
        confidence_label="high",
    )


def answers(
    *,
    payer: str = "yes",
    bed: str = "yes",
    wound_vac: str = "yes",
    iv: str = "yes",
    coordinator: str = "Dana",
    fax: str = "555-0142",
    sister: str = "none",
    wound_vac_detail: str = "",
) -> dict[str, Any]:
    """Shorthand for a patient-10482 structured result."""
    return {
        "payer_network": payer,
        "staffed_bed": bed,
        "wound_vac": wound_vac,
        "iv_infusion": iv,
        "payer_network_detail": "",
        "staffed_bed_detail": "",
        "wound_vac_detail": wound_vac_detail,
        "iv_infusion_detail": "",
        "coordinator_name": coordinator,
        "direct_callback_number": "",
        "referral_fax_number": fax,
        "sister_facility_name": sister,
        "earliest_admission": "tomorrow morning",
        "refusal_reason": "",
    }


class ScriptedActuator:
    """Returns canned observations keyed by facility id.

    Records the call order so tests can assert on *which* facilities the agent
    chose to call and in what sequence - the thing that distinguishes an agent
    from a batch dialer.
    """

    mode_label = "scripted"

    def __init__(self, script: dict[str, dict[str, Any] | CallObservation]) -> None:
        self._script = script
        self.calls: list[str] = []

    async def call_facility(
        self,
        facility: Facility,
        patient: PatientCase,
        objective: str | None = None,
        result_schema: dict[str, Any] | None = None,
    ) -> CallObservation:
        self.calls.append(facility.facility_id)
        scripted = self._script.get(facility.facility_id)

        if isinstance(scripted, CallObservation):
            return scripted

        if scripted is None:
            return make_observation(
                facility.facility_id,
                outcome=CallOutcome.NO_ANSWER,
                structured_result=None,
                summary="No answer.",
            )

        return make_observation(
            facility.facility_id,
            phone=facility.phone,
            structured_result=scripted,
        )


@pytest.fixture
def patient():
    from app.data.synthetic_data import get_patient

    return get_patient("10482")


@pytest.fixture
def facility():
    from app.data.synthetic_data import get_facility

    return get_facility("SNF-001")
