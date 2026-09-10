"""Live CALL-E telephony actuator.

Wraps the CALL-E Calls API (`calle-ai`) and normalises its terminal payload into
a `CallObservation`. This is the only module in the project that knows CALL-E
exists.

Docs: https://docs.heycall-e.com/quickstart
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.agent.tools import cassette
from app.agent.tools.budget import CallBudget, budget as default_budget
from app.agent.tools.telephony import (
    build_task_prompt,
    facility_call_metadata,
    recipient_for,
    region_for_phone,
)
from app.config import settings
from app.data.synthetic_data import PLACEHOLDER_PHONE
from app.models.schemas import (
    CallMode,
    CallObservation,
    CallOutcome,
    Facility,
    PatientCase,
    TranscriptSpeaker,
    TranscriptTurn,
)

log = logging.getLogger(__name__)


class TelephonyConfigError(RuntimeError):
    """Raised when a live call is requested but cannot legitimately be placed."""


def _field(payload: Any, *names: str, default: Any = None) -> Any:
    """Read a field from a CALL-E response.

    The Python SDK returns mapping-shaped results, but tolerate attribute access
    and camelCase so a minor SDK revision does not silently null everything out.
    """
    for name in names:
        if isinstance(payload, dict):
            if name in payload:
                return payload[name]
        elif hasattr(payload, name):
            return getattr(payload, name)
    return default


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _parse_turns(raw: Any) -> list[TranscriptTurn]:
    turns: list[TranscriptTurn] = []
    for item in raw or []:
        speaker = str(_field(item, "speaker", default="unknown") or "unknown").lower()
        turns.append(
            TranscriptTurn(
                offset_seconds=_field(item, "offset_seconds", "offsetSeconds"),
                speaker=(
                    TranscriptSpeaker(speaker)
                    if speaker in {s.value for s in TranscriptSpeaker}
                    else TranscriptSpeaker.UNKNOWN
                ),
                text=str(_field(item, "text", default="") or ""),
            )
        )
    return turns


def _first_attempt(call: Any) -> Any:
    """The first dial attempt of the first recipient, if any.

    Attempt-level data (transcript, provider id, timings) lives one level below
    the call task.
    """
    for recipient in _field(call, "recipients", default=[]) or []:
        attempts = _field(recipient, "attempts", default=[]) or []
        if attempts:
            return attempts[0]
    return None


def _recipient_result(call: Any) -> dict[str, Any] | None:
    for recipient in _field(call, "recipients", default=[]) or []:
        result = _field(recipient, "structured_result", "structuredResult")
        if result:
            return dict(result)
    return None


class CalleActuator:
    """Places real outbound calls through CALL-E."""

    mode_label = "live"

    def __init__(
        self,
        api_key: str | None = None,
        budget: CallBudget | None = None,
        record_cassettes: bool | None = None,
    ) -> None:
        key = api_key or settings.calle_api_key
        if not key:
            raise TelephonyConfigError(
                "CALLE_API_KEY is not set. Add it to .env (get one from the "
                "CALL-E dashboard) or run with TELEPHONY_MODE=replay."
            )

        try:
            from calle import CalleClient
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise TelephonyConfigError(
                "The CALL-E SDK is not installed. Run: pip install calle-ai"
            ) from exc

        self._client = CalleClient(api_key=key)
        self._budget = budget or default_budget
        self._record = (
            settings.record_cassettes if record_cassettes is None else record_cassettes
        )

    # -- api ----------------------------------------------------------------

    async def call_facility(
        self,
        facility: Facility,
        patient: PatientCase,
        objective: str | None = None,
        result_schema: dict[str, Any] | None = None,
    ) -> CallObservation:
        if facility.phone == PLACEHOLDER_PHONE or not facility.phone:
            raise TelephonyConfigError(
                f"{facility.name} has no demo receiver number. Set "
                f"DEMO_PHONE_PRIMARY / DEMO_PHONE_SECONDARY in .env to numbers "
                f"you own, or run this facility in replay mode."
            )

        if region_for_phone(facility.phone) is None:
            raise TelephonyConfigError(
                f"{facility.phone} is not in CALL-E's coverage table, so the "
                f"dial would be rejected as unsupported_region. See "
                f"https://docs.heycall-e.com/regions"
            )

        task = objective or build_task_prompt(patient, facility)

        # Reserved before the dial: a call that crashes mid-flight still spent
        # the credit.
        spent = self._budget.reserve(
            facility.facility_id, facility.phone, note=f"case {patient.case_id}"
        )
        log.info(
            "Dialing %s (%s) - live call %s of %s",
            facility.name,
            facility.phone,
            spent,
            self._budget.ceiling,
        )

        started = datetime.now(timezone.utc)
        try:
            call = await asyncio.to_thread(
                self._client.calls.create_and_wait,
                task=task,
                recipients=[recipient_for(facility.phone)],
                result_schema=result_schema,
                metadata=facility_call_metadata(facility, patient),
            )
        except Exception as exc:  # noqa: BLE001 - surface any SDK/API failure
            log.exception("CALL-E call to %s failed", facility.name)
            if type(exc).__name__ == "CalleAPIError":
                # The API refused the request, so no call was placed and no
                # credit was consumed. Refund the reservation.
                self._budget.release(reason=f"{facility.facility_id}: {exc}")
            return CallObservation(
                facility_id=facility.facility_id,
                phone=facility.phone,
                mode=CallMode.LIVE,
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                outcome=CallOutcome.FAILED,
                failure_code=type(exc).__name__,
                failure_message=str(exc),
            )

        observation = self._to_observation(call, facility, started)

        if self._record and observation.is_usable:
            path = cassette.record(observation, patient.case_id)
            log.info("Recorded cassette: %s", path.name)

        return observation

    # -- normalisation ------------------------------------------------------

    def _to_observation(
        self, call: Any, facility: Facility, started: datetime
    ) -> CallObservation:
        attempt = _first_attempt(call)
        status = str(_field(call, "status", default="completed") or "completed")

        started_at = _parse_dt(_field(attempt, "started_at", "startedAt")) or started
        completed_at = _parse_dt(
            _field(attempt, "completed_at", "completedAt")
        ) or _parse_dt(_field(call, "completed_at", "completedAt"))

        duration = None
        if started_at and completed_at:
            duration = (completed_at - started_at).total_seconds()

        confidence = _field(call, "completion_confidence", "completionConfidence") or {}

        # Task-level extraction is the primary result; recipient-level is the
        # fallback for batch-shaped responses.
        structured = _field(call, "structured_result", "structuredResult")
        structured = dict(structured) if structured else _recipient_result(call)

        try:
            outcome = CallOutcome(status)
        except ValueError:
            outcome = CallOutcome.COMPLETED

        return CallObservation(
            facility_id=facility.facility_id,
            phone=facility.phone,
            mode=CallMode.LIVE,
            call_id=_field(call, "id", "call_id", "callId"),
            provider_call_id=_field(attempt, "provider_call_id", "providerCallId"),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            outcome=outcome,
            structured_result=structured,
            summary=_field(call, "summary"),
            task_completed=_field(call, "task_completed", "taskCompleted"),
            confidence_score=_field(confidence, "score"),
            confidence_label=_field(confidence, "label"),
            evidence=list(_field(call, "evidence", default=[]) or []),
            transcript_turns=_parse_turns(
                _field(attempt, "transcript_turns", "transcriptTurns", default=[])
            ),
            failure_code=_field(call, "failure_code", "failureCode"),
            failure_message=_field(call, "failure_message", "failureMessage"),
        )
