"""Telephony actuator contract.

The agent never imports a concrete actuator. It depends on `TelephonyActuator`,
and either `CalleActuator` (real outbound calls) or `ReplayActuator` (recorded
cassettes) is injected at the edge. Planner, reasoning engine, scoring and UI are
byte-identical in both modes - there is no demo-only branch anywhere above this
line.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.models.schemas import (
    CallObservation,
    ConstraintCode,
    Facility,
    PatientCase,
)

# CALL-E prefers string enums over booleans for judgments that may be unclear,
# with an explicit `unknown` for "the call did not settle this".
TRI_STATE = ["yes", "no", "unknown"]

NO_SISTER_FACILITY = "none"


@runtime_checkable
class TelephonyActuator(Protocol):
    """Anything that can turn a facility + objective into an observation."""

    mode_label: str

    async def call_facility(
        self,
        facility: Facility,
        patient: PatientCase,
        objective: str,
        result_schema: dict[str, Any],
    ) -> CallObservation:
        ...


# ---------------------------------------------------------------------------
# Result schema construction
# ---------------------------------------------------------------------------

_FIELD_PROMPTS: dict[ConstraintCode, str] = {
    ConstraintCode.PAYER_NETWORK: (
        "Use yes only if staff confirm they are in network for the stated plan. "
        "Use no if they say they do not accept it. Use unknown if they were "
        "unsure, deferred to billing, or the topic never resolved."
    ),
    ConstraintCode.STAFFED_BED: (
        "Use yes only if staff confirm a currently staffed bed matching the "
        "patient's sex is available for admission within 24 hours. Use no if "
        "they state they are full or cannot admit in that window. Use unknown "
        "if they would not commit."
    ),
    ConstraintCode.WOUND_VAC: (
        "Use yes only if staff confirm nurses certified in negative pressure "
        "wound therapy will be on duty when the patient arrives. Use no if they "
        "say they cannot manage a wound VAC, or that no certified nurse is "
        "available on that shift. Use unknown if they were unsure."
    ),
    ConstraintCode.IV_INFUSION: (
        "Use yes only if staff confirm they can administer the stated IV "
        "antibiotic at the stated cadence. Use no if they cannot. Use unknown "
        "if unresolved."
    ),
    ConstraintCode.CONTACT_ISOLATION: (
        "Use yes only if staff confirm they can accept a patient on contact "
        "precautions. Use no if they cannot. Use unknown if unresolved."
    ),
    ConstraintCode.BARIATRIC_CAPACITY: (
        "Use yes only if staff confirm bariatric beds and lift equipment rated "
        "for the stated weight. Use no if they cannot. Use unknown if unresolved."
    ),
}


def build_result_schema(patient: PatientCase) -> dict[str, Any]:
    """Build the JSON Schema CALL-E extracts against, from the patient's needs.

    Only hard constraints become call questions - soft preferences (distance,
    CMS rating) are known from the directory and never worth a phone call.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for req in patient.hard_requirements():
        key = req.code.value
        properties[key] = {
            "type": "string",
            "enum": TRI_STATE,
            "description": (
                f"Can the facility meet this requirement: {req.label} "
                f"({req.detail}). {_FIELD_PROMPTS.get(req.code, '')}"
            ),
        }
        properties[f"{key}_detail"] = {
            "type": "string",
            "description": (
                f"Quote or closely paraphrase what staff actually said about "
                f"{req.label}. Use an empty string if it never came up."
            ),
        }
        required.append(key)

    properties.update(
        {
            "coordinator_name": {
                "type": "string",
                "description": (
                    "Name of the admissions coordinator spoken with. Empty "
                    "string if never given."
                ),
            },
            "direct_callback_number": {
                "type": "string",
                "description": (
                    "Direct callback or extension for admissions, if offered. "
                    "Empty string otherwise."
                ),
            },
            "referral_fax_number": {
                "type": "string",
                "description": (
                    "Fax number or secure email for referral packets, if "
                    "offered. Empty string otherwise."
                ),
            },
            "sister_facility_name": {
                "type": "string",
                "description": (
                    "If staff suggested another facility under the same "
                    "ownership that may have capacity, give its name. Use "
                    f"'{NO_SISTER_FACILITY}' if none was mentioned."
                ),
            },
            "earliest_admission": {
                "type": "string",
                "description": (
                    "Earliest admission window staff would commit to, in their "
                    "own words. Empty string if none given."
                ),
            },
            "refusal_reason": {
                "type": "string",
                "description": (
                    "If the facility declined, the reason in their own words. "
                    "Empty string otherwise."
                ),
            },
        }
    )

    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


# ---------------------------------------------------------------------------
# Task prompt construction
# ---------------------------------------------------------------------------


def build_task_prompt(patient: PatientCase, facility: Facility) -> str:
    """Compose the natural-language objective CALL-E runs the conversation on.

    Deliberately goal-shaped rather than scripted: CALL-E is told what must be
    established and what it may not do, then left to navigate the IVR, the
    receptionist, and the ordering of questions itself.
    """
    asks = "\n".join(
        f"  {i}. Establish {req.ask_as}."
        for i, req in enumerate(patient.hard_requirements(), start=1)
    )

    # Coverage is stated on its own line above, so keep it out of the needs list.
    needs = "; ".join(
        req.detail
        for req in patient.hard_requirements()
        if req.detail and req.code is not ConstraintCode.PAYER_NETWORK
    )

    extension_hint = (
        f"If an automated menu answers, admissions is typically option "
        f"{facility.admissions_extension}. "
        if facility.admissions_extension
        else ""
    )

    return f"""You are an automated hospital case-management assistant calling {facility.name} at {facility.phone} on behalf of a discharge planning team.

Identify yourself at the start as an automated assistant calling from hospital case management about a skilled nursing referral, and ask to be connected to admissions. {extension_hint}If a receptionist deflects or offers to take a message, politely ask whether anyone in admissions is available now, since you need bed availability for a discharge today.

This is a de-identified referral enquiry. Refer to the patient only as "a {patient.age}-year-old {patient.sex} patient". Do not state or invent a patient name, date of birth, or medical record number, and do not accept one if offered.

Clinical and coverage context you may share:
  - Insurance: {patient.payer_plan}
  - Needs: {needs}
  - Target admission: within 24 hours

You must establish all of the following before ending the call:
{asks}
  {len(patient.hard_requirements()) + 1}. Get the name of the admissions coordinator you spoke with.
  {len(patient.hard_requirements()) + 2}. Get a fax number or secure email for sending a referral packet.

If they say they have no capacity, ask whether a sister facility under the same ownership has availability, and get its name.

Boundaries:
  - Do not agree to, promise, or schedule an admission. You are gathering availability only; a human case manager makes the placement decision.
  - Do not give clinical advice or discuss treatment decisions.
  - If asked to send records, say a case manager will send a referral packet after review.
  - If the person asks to end the call or says now is a bad time, thank them and end promptly.

Be brief and professional. Aim to finish in under three minutes."""


def facility_call_metadata(facility: Facility, patient: PatientCase) -> dict[str, Any]:
    """Correlation metadata echoed back on the call and its webhooks."""
    return {
        "app": "dischargepulse",
        "case_id": patient.case_id,
        "facility_id": facility.facility_id,
        "facility_name": facility.name,
        "synthetic": "true",
    }
