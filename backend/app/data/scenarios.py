"""Simulated attendant answers.

The demo's stand-in facility line (a CALL-E Inbound Goal) currently answers live
calls with no audio - a platform fault reported to the organisers. So the call
is still placed for real, but the admissions coordinator's answers come from
here, and every observation built from them is labelled `answers_source =
simulated`. Nothing in this file is ever presented as something said on a call.

These facts mirror the Inbound Goal scripts in docs/INBOUND_GOAL_SETUP.md
exactly, so a simulated run gives the answers the stand-in line was configured
to give.
"""

from __future__ import annotations

from typing import Any

from app.agent.tools.telephony import NO_SISTER_FACILITY


def _answers(
    *,
    payer: str = "yes",
    bed: str = "yes",
    wound_vac: str = "yes",
    iv: str = "yes",
    wound_vac_detail: str = "",
    bed_detail: str = "",
    coordinator: str = "",
    fax: str = "",
    sister: str = NO_SISTER_FACILITY,
    earliest: str = "",
    refusal: str = "",
) -> dict[str, Any]:
    """A structured result shaped exactly like CALL-E extracts for case 10482."""
    return {
        "payer_network": payer,
        "payer_network_detail": "",
        "staffed_bed": bed,
        "staffed_bed_detail": bed_detail,
        "wound_vac": wound_vac,
        "wound_vac_detail": wound_vac_detail,
        "iv_infusion": iv,
        "iv_infusion_detail": "",
        "coordinator_name": coordinator,
        "direct_callback_number": "",
        "referral_fax_number": fax,
        "sister_facility_name": sister,
        "earliest_admission": earliest,
        "refusal_reason": refusal,
    }


# (case_id, facility_id) -> simulated attendant answers
SCENARIOS: dict[tuple[str, str], dict[str, Any]] = {
    # Dana - contradicts the directory's wound VAC claim, names the sister campus.
    ("10482", "SNF-001"): _answers(
        wound_vac="no",
        wound_vac_detail=(
            "Our wound care nurse is out this week and the night nurse isn't "
            "signed off on wound VACs, so we can't take one right now."
        ),
        coordinator="Dana",
        fax="555-0142",
        sister="Bayview Post-Acute Peninsula Campus",
        earliest="tomorrow morning",
        refusal="No wound VAC certified nurse available this week.",
    ),
    # Mission Terrace - inside the radius, full.
    ("10482", "SNF-003"): _answers(
        bed="no",
        bed_detail="We're full, no staffed beds until next week.",
        coordinator="Priya",
        refusal="No staffed bed available.",
    ),
    # Marcus - everything confirmed: the verified match.
    ("10482", "SNF-004"): _answers(
        coordinator="Marcus",
        fax="555-0198",
        earliest="within 24 hours",
    ),
}


def scenario_for(case_id: str, facility_id: str) -> dict[str, Any] | None:
    """A copy of the simulated answers, or None if this pair has no scenario."""
    answers = SCENARIOS.get((case_id, facility_id))
    return dict(answers) if answers is not None else None
