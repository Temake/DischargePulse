"""Simulated-attendant actuators.

The stand-in facility line currently answers live calls with no audio, so these
actuators let the demo run the full loop while staying honest about which parts
are real:

  SimulatedAttendantActuator  The call is REAL - dialed through CALL-E, real call
                              id, real credit. If the answering line gives no
                              usable answers, the attendant's answers are
                              simulated from app/data/scenarios.py and labelled
                              `answers_source = simulated`.

  ScriptedAttendantActuator   No call at all. Scenario answers, labelled
                              `mode = scripted`. Free, for rehearsals.

Guarantees, each covered by tests:
  - Answers genuinely extracted from a call are never overwritten.
  - Nothing is simulated on top of a call that never connected.
  - What the call really extracted is kept in `call_structured_result`.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agent.tools import cassette
from app.agent.tools.calle_actuator import CalleActuator
from app.agent.tools.telephony import TelephonyActuator
from app.config import settings
from app.data.scenarios import scenario_for
from app.data.synthetic_data import PLACEHOLDER_PHONE
from app.models.schemas import (
    AnswersSource,
    CallMode,
    CallObservation,
    CallOutcome,
    Facility,
    PatientCase,
)

log = logging.getLogger(__name__)

UNKNOWN = "unknown"

SIMULATED_NOTE = (
    "Live call placed to the stand-in facility line, which gave no usable "
    "answers (known platform audio fault). Attendant answers are simulated "
    "from the test scenario."
)
SCRIPTED_NOTE = (
    "Scripted rehearsal - no call placed. Attendant answers are simulated from "
    "the test scenario."
)
UNDIALABLE_NOTE = (
    "No demo line for this facility, so no call placed. Attendant answers are "
    "simulated from the test scenario."
)


def has_real_answers(patient: PatientCase, result: dict[str, Any] | None) -> bool:
    """Did the call itself settle at least one hard requirement?"""
    if not result:
        return False
    return any(
        str(result.get(req.code.value, UNKNOWN)).lower() != UNKNOWN
        for req in patient.hard_requirements()
    )


def _scripted_observation(
    facility: Facility, patient: PatientCase, note: str
) -> CallObservation:
    answers = scenario_for(patient.case_id, facility.facility_id)
    if answers is None:
        return CallObservation(
            facility_id=facility.facility_id,
            phone=facility.phone,
            mode=CallMode.SCRIPTED,
            outcome=CallOutcome.NO_ANSWER,
            summary="Scripted - no scenario for this facility.",
            failure_code="no_scenario",
            failure_message=f"No test scenario for {facility.name}.",
        )
    return CallObservation(
        facility_id=facility.facility_id,
        phone=facility.phone,
        mode=CallMode.SCRIPTED,
        answers_source=AnswersSource.SIMULATED,
        simulation_note=note,
        outcome=CallOutcome.COMPLETED,
        structured_result=answers,
        summary=note,
        task_completed=True,
    )


class ScriptedAttendantActuator:
    """Scenario answers with no call. Never touches the budget."""

    mode_label = "scripted"

    async def call_facility(
        self,
        facility: Facility,
        patient: PatientCase,
        objective: str | None = None,
        result_schema: dict[str, Any] | None = None,
    ) -> CallObservation:
        return _scripted_observation(facility, patient, SCRIPTED_NOTE)


class SimulatedAttendantActuator:
    """Real calls; simulated attendant answers only where the call gave none."""

    mode_label = "simulated"

    def __init__(
        self,
        live: TelephonyActuator | None = None,
        record_cassettes: bool | None = None,
    ) -> None:
        # The live actuator must not record the raw call itself: this wrapper
        # records the final, labelled observation instead.
        self._live = live or CalleActuator(record_cassettes=False)
        self._record = (
            settings.record_cassettes if record_cassettes is None else record_cassettes
        )

    async def call_facility(
        self,
        facility: Facility,
        patient: PatientCase,
        objective: str | None = None,
        result_schema: dict[str, Any] | None = None,
    ) -> CallObservation:
        # A directory entry with no demo line cannot be dialed at all - say so
        # with a scripted observation rather than pretending a call happened.
        if not facility.phone or facility.phone == PLACEHOLDER_PHONE:
            return _scripted_observation(facility, patient, UNDIALABLE_NOTE)

        observation = await self._live.call_facility(
            facility, patient, objective, result_schema
        )

        # Never simulate on top of a call that did not connect.
        if not observation.call_id or observation.outcome is not CallOutcome.COMPLETED:
            return observation

        # Answers the call genuinely produced always win.
        if has_real_answers(patient, observation.structured_result):
            self._save(observation, patient)
            return observation

        answers = scenario_for(patient.case_id, facility.facility_id)
        if answers is None:
            self._save(observation, patient)
            return observation

        simulated = observation.model_copy(
            update={
                "answers_source": AnswersSource.SIMULATED,
                "simulation_note": SIMULATED_NOTE,
                "call_structured_result": observation.structured_result,
                "structured_result": answers,
            }
        )
        log.info(
            "%s: live call %s gave no usable answers; simulated attendant applied",
            facility.name,
            observation.call_id,
        )
        self._save(simulated, patient)
        return simulated

    def _save(self, observation: CallObservation, patient: PatientCase) -> None:
        if self._record and observation.is_usable:
            path = cassette.record(observation, patient.case_id)
            log.info("Recorded cassette: %s", path.name)
