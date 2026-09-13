"""Telephony actuator contract.

The agent never imports a concrete actuator. It depends on `TelephonyActuator`,
and either `CalleActuator` (real outbound calls) or `ReplayActuator` (recorded
cassettes) is injected at the edge. Planner, reasoning engine, scoring and UI are
byte-identical in both modes - there is no demo-only branch anywhere above this
line.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.config import settings
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

# The demo dials stand-in lines, never real facilities: a CALL-E Inbound Goal we
# configured to answer as an admissions coordinator, or CALL-E's shared demo
# hotline. Recorded so the console and cassettes can say the facility side was
# scripted. The outbound prompt is unaffected - it is the production prompt.
CALLE_DEMO_HOTLINE = "+12763229632"


def is_stand_in_line(phone: str) -> bool:
    """True when this number is one of our configured stand-in answerers."""
    configured = {
        settings.demo_phone_primary,
        settings.demo_phone_secondary,
        CALLE_DEMO_HOTLINE,
    }
    return bool(phone) and phone in {n for n in configured if n}


# ---------------------------------------------------------------------------
# Region routing
# ---------------------------------------------------------------------------

# CALL-E only dials supported destinations, and the recipient's `region` drives
# routing and compliance checks. Sending the wrong one earns an
# `unsupported_region` rejection, so derive it from the number rather than
# assuming US.  Source: https://docs.heycall-e.com/regions
CALLING_CODE_TO_REGION: dict[str, str] = {
    "971": "AE", "880": "BD", "504": "HN", "968": "OM", "966": "SA",
    "886": "TW", "380": "UA", "358": "FI", "353": "IE", "264": "NA",
    "258": "MZ", "254": "KE", "237": "CM", "234": "NG", "233": "GH",
    "267": "BW", "216": "TN", "972": "IL",
    "94": "LK", "92": "PK", "90": "TR", "84": "VN", "81": "JP",
    "66": "TH", "65": "SG", "63": "PH", "62": "ID", "61": "AU",
    "60": "MY", "55": "BR", "52": "MX", "49": "DE", "48": "PL",
    "44": "GB", "34": "ES", "33": "FR", "31": "NL", "27": "ZA",
    "20": "EG", "91": "IN",
    "1": "US",
}

# Regions where English is not the primary supported language.
_NON_ENGLISH_DEFAULT: dict[str, str] = {
    "TR": "tr-TR",
    "VN": "vi-VN",
    "JP": "ja-JP",
    "FR": "fr-FR",
    "PL": "pl-PL",
}

UNSUPPORTED_REGION = None


def region_for_phone(phone: str) -> str | None:
    """Infer the CALL-E region code from an E.164 number.

    Returns None when the calling code is not in CALL-E's coverage table, which
    is a signal to refuse the dial rather than spend credit on a rejection.
    """
    if not phone.startswith("+"):
        return None

    digits = phone[1:]
    # Longest prefix wins: +1 must not shadow +234.
    for length in (3, 2, 1):
        code = digits[:length]
        if code in CALLING_CODE_TO_REGION:
            return CALLING_CODE_TO_REGION[code]
    return None


def locale_for_region(region: str | None) -> str:
    """Default BCP 47 locale for a region. English unless the region is not."""
    if not region:
        return "en-US"
    return _NON_ENGLISH_DEFAULT.get(region, f"en-{region}")


def recipient_for(phone: str, region: str | None = None, locale: str | None = None) -> dict[str, Any]:
    """Build a CALL-E recipient entry with routing derived from the number."""
    resolved_region = region or region_for_phone(phone)
    return {
        "phones": [phone],
        "region": resolved_region,
        "locale": locale or locale_for_region(resolved_region),
    }


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

Identify yourself at the start as an automated assistant calling from hospital case management about a skilled nursing referral, confirm you have reached {facility.name}, and ask to be connected to admissions. {extension_hint}If a receptionist deflects or offers to take a message, politely ask whether anyone in admissions is available now, since you need bed availability for a discharge today.

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
