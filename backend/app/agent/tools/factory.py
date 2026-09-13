"""Actuator selection.

This is the seam. The agent asks for a `TelephonyActuator` and gets one; it never
learns which. Swapping live for replay changes nothing above this module.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from app.agent.tools.budget import budget
from app.agent.tools.calle_actuator import CalleActuator, TelephonyConfigError
from app.agent.tools.replay_actuator import ReplayActuator
from app.agent.tools.simulated_attendant import (
    ScriptedAttendantActuator,
    SimulatedAttendantActuator,
)
from app.agent.tools.telephony import TelephonyActuator
from app.config import TelephonyMode, settings
from app.models.schemas import CallObservation, Facility, PatientCase

log = logging.getLogger(__name__)


class HybridActuator:
    """Dials a chosen subset live and replays the rest.

    The demo configuration: a handful of genuinely live legs on numbers you own,
    with recorded cassettes covering the wider fan-out. The contradiction and the
    re-plan trigger should sit on live legs so the closed loop is demonstrably
    driven by a real conversation.
    """

    mode_label = "hybrid"

    def __init__(
        self,
        live_facility_ids: Iterable[str],
        live: TelephonyActuator | None = None,
        replay: TelephonyActuator | None = None,
    ) -> None:
        self._live_ids = set(live_facility_ids)
        self._live = live or CalleActuator()
        self._replay = replay or ReplayActuator()

    async def call_facility(
        self,
        facility: Facility,
        patient: PatientCase,
        objective: str | None = None,
        result_schema: dict[str, Any] | None = None,
    ) -> CallObservation:
        live_wanted = facility.facility_id in self._live_ids

        if live_wanted and budget.remaining <= 0:
            log.warning(
                "Budget exhausted - falling back to cassette for %s", facility.name
            )
            live_wanted = False

        actuator = self._live if live_wanted else self._replay
        return await actuator.call_facility(facility, patient, objective, result_schema)


def build_actuator(
    mode: TelephonyMode | None = None,
    live_facility_ids: Iterable[str] | None = None,
    replay_latency_seconds: float = 0.0,
) -> TelephonyActuator:
    """Construct the actuator for the requested mode.

    Falls back to replay - never silently to live - if credentials are missing,
    so an unconfigured environment can never spend call credit by accident.
    """
    if live_facility_ids:
        return HybridActuator(
            live_facility_ids,
            replay=ReplayActuator(latency_seconds=replay_latency_seconds),
        )

    resolved = (mode or settings.telephony_mode)
    if resolved is TelephonyMode.AUTO:
        resolved = settings.resolve_mode()

    if resolved is TelephonyMode.LIVE:
        try:
            return CalleActuator()
        except TelephonyConfigError as exc:
            log.error("Cannot run live (%s) - falling back to replay", exc)
            return ReplayActuator(latency_seconds=replay_latency_seconds)

    if resolved is TelephonyMode.SIMULATED:
        try:
            return SimulatedAttendantActuator()
        except TelephonyConfigError as exc:
            # Falls back to the free, no-call mode - never the other way.
            log.error("Cannot place calls (%s) - falling back to scripted", exc)
            return ScriptedAttendantActuator()

    if resolved is TelephonyMode.SCRIPTED:
        return ScriptedAttendantActuator()

    return ReplayActuator(latency_seconds=replay_latency_seconds)
