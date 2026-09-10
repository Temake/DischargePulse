"""Cassette replay actuator.

Returns previously recorded real calls instead of dialing. Used for development,
tests, and as the fallback leg of a hybrid demo sweep. Costs no call credit and
is deterministic, so the agent loop can be exercised hundreds of times without
touching the live budget.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agent.tools import cassette
from app.models.schemas import (
    CallMode,
    CallObservation,
    CallOutcome,
    Facility,
    PatientCase,
)

log = logging.getLogger(__name__)


class ReplayActuator:
    """Serves `CallObservation`s from recorded cassettes."""

    mode_label = "replay"

    def __init__(self, latency_seconds: float = 0.0, strict: bool = False) -> None:
        # A little latency makes the console's concurrent-call animation read
        # naturally during a recorded demo. Zero in tests.
        self._latency = latency_seconds
        # strict=True turns a missing cassette into an error instead of an
        # UNREACHED observation - useful in tests to catch fixture drift.
        self._strict = strict

    async def call_facility(
        self,
        facility: Facility,
        patient: PatientCase,
        objective: str | None = None,
        result_schema: dict[str, Any] | None = None,
    ) -> CallObservation:
        if self._latency:
            await asyncio.sleep(self._latency)

        observation = cassette.load(patient.case_id, facility.facility_id)

        if observation is None:
            if self._strict:
                raise FileNotFoundError(
                    f"No cassette for case {patient.case_id} / "
                    f"{facility.facility_id}. Record one with a live call first."
                )
            log.warning(
                "No cassette for %s / %s - returning unreached observation",
                patient.case_id,
                facility.facility_id,
            )
            return CallObservation(
                facility_id=facility.facility_id,
                phone=facility.phone,
                mode=CallMode.REPLAY,
                outcome=CallOutcome.NO_ANSWER,
                failure_code="cassette_missing",
                failure_message=(
                    f"No recorded call for {facility.name} on case "
                    f"{patient.case_id}."
                ),
            )

        log.info("Replaying cassette for %s (%s)", facility.name, observation.call_id)
        return observation
