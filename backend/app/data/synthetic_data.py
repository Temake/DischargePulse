"""Synthetic, de-identified test data.

No real patient, facility, or phone number appears in this file. Facility names
are invented, and every phone number is a demo receiver you control (set via
DEMO_PHONE_PRIMARY / DEMO_PHONE_SECONDARY) or an RFC-style placeholder.

Pointing an autonomous calling agent at real nursing facilities with a fabricated
patient would occupy clinical staff under false pretenses, so the demo dials
role-played admissions lines instead.
"""

from __future__ import annotations

from app.config import settings
from app.models.schemas import (
    ConstraintCode,
    ConstraintKind,
    DirectoryClaim,
    Facility,
    PatientCase,
    Requirement,
)

# Numbers you own and have staffed with a role-player. Read through `settings`
# rather than os.environ so .env is guaranteed loaded first. Anything left unset
# falls back to a placeholder that the live actuator refuses to dial.
PLACEHOLDER_PHONE = "+10000000000"


def _phone(slot: str) -> str:
    """Resolve a demo phone slot, falling back to an undialable placeholder."""
    if slot == "primary" and settings.demo_phone_primary:
        return settings.demo_phone_primary
    if slot == "secondary" and settings.demo_phone_secondary:
        return settings.demo_phone_secondary
    return PLACEHOLDER_PHONE


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

PATIENT_10482 = PatientCase(
    case_id="10482",
    display_name="Synthetic Patient #10482",
    age=71,
    sex="female",
    payer="Aetna",
    payer_plan="Aetna Medicare Advantage PPO",
    weight_lbs=182,
    hospital_day=6,
    discharge_summary=(
        "Post-operative day 6 following left hip arthroplasty with a surgical "
        "site wound requiring negative pressure wound therapy. Completing a "
        "14-day course of IV ceftriaxone. Medically stable, cleared for "
        "skilled nursing placement. Family requests placement near 94110."
    ),
    family_zip="94110",
    search_radius_miles=15,
    max_radius_miles=30,
    requirements=[
        Requirement(
            code=ConstraintCode.PAYER_NETWORK,
            kind=ConstraintKind.HARD,
            label="Payer network",
            detail="Aetna Medicare Advantage PPO",
            ask_as="whether the facility is in network for Aetna Medicare Advantage PPO",
        ),
        Requirement(
            code=ConstraintCode.STAFFED_BED,
            kind=ConstraintKind.HARD,
            label="Staffed bed available",
            detail="Female-appropriate room, admission within 24 hours",
            ask_as=(
                "whether they have a staffed bed available for a female patient "
                "for admission within the next 24 hours"
            ),
        ),
        Requirement(
            code=ConstraintCode.WOUND_VAC,
            kind=ConstraintKind.HARD,
            label="Wound VAC therapy",
            detail="Negative pressure wound therapy, certified nursing staff",
            ask_as=(
                "whether they have nursing staff currently certified to manage "
                "a wound VAC on the shift the patient would arrive"
            ),
        ),
        Requirement(
            code=ConstraintCode.IV_INFUSION,
            kind=ConstraintKind.HARD,
            label="IV infusion",
            detail="IV ceftriaxone Q24H, 8 days remaining",
            ask_as="whether they can administer IV ceftriaxone once every 24 hours",
        ),
        Requirement(
            code=ConstraintCode.DISTANCE,
            kind=ConstraintKind.SOFT,
            label="Proximity to family",
            detail="Within 15 miles of 94110",
        ),
        Requirement(
            code=ConstraintCode.CMS_RATING,
            kind=ConstraintKind.SOFT,
            label="CMS quality rating",
            detail="4 stars or better preferred",
        ),
        Requirement(
            code=ConstraintCode.PREFERRED_PARTNER,
            kind=ConstraintKind.SOFT,
            label="Preferred network partner",
            detail="In-network preferred partner tier",
        ),
    ],
)


PATIENT_10483 = PatientCase(
    case_id="10483",
    display_name="Synthetic Patient #10483",
    age=64,
    sex="male",
    payer="UnitedHealthcare",
    payer_plan="UHC Dual Complete",
    weight_lbs=412,
    hospital_day=9,
    discharge_summary=(
        "Cellulitis with MRSA colonisation requiring contact isolation. "
        "Bariatric equipment needs above 350 lbs. Medically stable, cleared "
        "for skilled nursing placement."
    ),
    family_zip="94601",
    search_radius_miles=20,
    max_radius_miles=40,
    requirements=[
        Requirement(
            code=ConstraintCode.PAYER_NETWORK,
            kind=ConstraintKind.HARD,
            label="Payer network",
            detail="UHC Dual Complete",
            ask_as="whether the facility is in network for UnitedHealthcare Dual Complete",
        ),
        Requirement(
            code=ConstraintCode.STAFFED_BED,
            kind=ConstraintKind.HARD,
            label="Staffed bed available",
            detail="Male-appropriate room, private room required",
            ask_as="whether they have a private staffed bed available for a male patient",
        ),
        Requirement(
            code=ConstraintCode.CONTACT_ISOLATION,
            kind=ConstraintKind.HARD,
            label="Contact isolation",
            detail="MRSA contact precautions",
            ask_as="whether they can accept a patient on MRSA contact precautions",
        ),
        Requirement(
            code=ConstraintCode.BARIATRIC_CAPACITY,
            kind=ConstraintKind.HARD,
            label="Bariatric capacity",
            detail="Equipment rated above 350 lbs",
            ask_as="whether they have bariatric beds and lift equipment rated above 350 pounds",
        ),
        Requirement(
            code=ConstraintCode.DISTANCE,
            kind=ConstraintKind.SOFT,
            label="Proximity to family",
            detail="Within 20 miles of 94601",
        ),
        Requirement(
            code=ConstraintCode.CMS_RATING,
            kind=ConstraintKind.SOFT,
            label="CMS quality rating",
            detail="3 stars or better preferred",
        ),
    ],
)


PATIENTS: dict[str, PatientCase] = {
    PATIENT_10482.case_id: PATIENT_10482,
    PATIENT_10483.case_id: PATIENT_10483,
}


# ---------------------------------------------------------------------------
# Facility network
# ---------------------------------------------------------------------------


def _claims(**kwargs: bool) -> list[DirectoryClaim]:
    """Shorthand for directory claims: _claims(wound_vac=True, iv_infusion=False)."""
    return [
        DirectoryClaim(
            code=ConstraintCode(code),
            claimed_available=value,
            last_updated="2026-02-14",
        )
        for code, value in kwargs.items()
    ]


FACILITIES: list[Facility] = [
    # --- Wave 1: inside the 15-mile radius ---------------------------------
    Facility(
        facility_id="SNF-001",
        name="Bayview Post-Acute Center",
        phone=_phone("primary"),
        admissions_extension="2",
        address="1400 Mission Bay Blvd",
        zip_code="94158",
        distance_miles=4.2,
        cms_star_rating=4.0,
        preferred_partner=True,
        accepted_payers=["Aetna", "Medicare", "Blue Shield"],
        # The directory says wound VAC is available. The live call is where
        # that claim gets tested - this is the seeded contradiction.
        directory_claims=_claims(
            wound_vac=True,
            iv_infusion=True,
            staffed_bed=True,
            payer_network=True,
        ),
        sister_facility_ids=["SNF-004"],
        # Contradicts the directory's wound VAC claim and names the sister
        # campus - the two beats the agent has to react to.
        roleplay_brief=(
            "You are Dana, admissions coordinator at Bayview Post-Acute Center. "
            "You are in network with Aetna Medicare Advantage PPO. You have a "
            "staffed bed for a female patient and can admit tomorrow morning. "
            "You can give IV ceftriaxone every 24 hours. You cannot take a wound "
            "VAC right now: your wound care nurse is out this week and the night "
            "nurse is not signed off on wound VACs. Your referral fax is "
            "555-0142. Suggest your sister facility, Bayview Post-Acute Peninsula "
            "Campus in San Mateo, which may have a wound VAC certified nurse."
        ),
    ),
    Facility(
        facility_id="SNF-002",
        name="Golden Gate Skilled Nursing",
        phone=_phone("secondary"),
        admissions_extension="3",
        address="2295 Geary Blvd",
        zip_code="94115",
        distance_miles=6.8,
        cms_star_rating=3.5,
        preferred_partner=False,
        accepted_payers=["Medicare", "Kaiser"],
        directory_claims=_claims(
            wound_vac=False,
            iv_infusion=True,
            staffed_bed=True,
            payer_network=False,
        ),
    ),
    Facility(
        facility_id="SNF-003",
        name="Mission Terrace Rehabilitation",
        phone=PLACEHOLDER_PHONE,
        admissions_extension="1",
        address="5100 Mission St",
        zip_code="94112",
        distance_miles=9.1,
        cms_star_rating=4.5,
        preferred_partner=True,
        accepted_payers=["Aetna", "Medicare"],
        directory_claims=_claims(
            wound_vac=True,
            iv_infusion=True,
            staffed_bed=True,
            payer_network=True,
        ),
    ),
    # --- The sister facility surfaced on-call by SNF-001 -------------------
    Facility(
        facility_id="SNF-004",
        name="Bayview Post-Acute - Peninsula Campus",
        phone=_phone("primary"),
        admissions_extension="2",
        address="880 El Camino Real, San Mateo",
        zip_code="94402",
        distance_miles=18.6,
        cms_star_rating=4.0,
        preferred_partner=True,
        accepted_payers=["Aetna", "Medicare", "Blue Shield"],
        directory_claims=_claims(
            wound_vac=True,
            iv_infusion=True,
            staffed_bed=True,
            payer_network=True,
        ),
        sister_facility_ids=["SNF-001"],
        roleplay_brief=(
            "You are Marcus, admissions coordinator at Bayview Post-Acute "
            "Peninsula Campus. You are in network with Aetna Medicare Advantage "
            "PPO. You have a staffed bed for a female patient and can admit "
            "within 24 hours. You have wound VAC certified nurses on every shift, "
            "including nights. You can give IV ceftriaxone every 24 hours. Your "
            "referral fax is 555-0198."
        ),
    ),
    # --- Wave 2: only reachable after a radius expansion -------------------
    Facility(
        facility_id="SNF-005",
        name="Alameda Shores Care Center",
        phone=PLACEHOLDER_PHONE,
        address="1750 Park St, Alameda",
        zip_code="94501",
        distance_miles=22.4,
        cms_star_rating=3.0,
        preferred_partner=False,
        accepted_payers=["UnitedHealthcare", "Medicare"],
        directory_claims=_claims(
            wound_vac=False,
            iv_infusion=True,
            staffed_bed=True,
            contact_isolation=True,
            bariatric_capacity=True,
            payer_network=True,
        ),
    ),
    Facility(
        facility_id="SNF-006",
        name="Northgate Transitional Care",
        phone=PLACEHOLDER_PHONE,
        address="640 Northgate Dr, San Rafael",
        zip_code="94903",
        distance_miles=27.9,
        cms_star_rating=4.0,
        preferred_partner=False,
        accepted_payers=["Aetna", "UnitedHealthcare", "Medicare"],
        directory_claims=_claims(
            wound_vac=True,
            iv_infusion=True,
            staffed_bed=True,
            contact_isolation=True,
            bariatric_capacity=True,
            payer_network=True,
        ),
    ),
]


FACILITIES_BY_ID: dict[str, Facility] = {f.facility_id: f for f in FACILITIES}


def get_patient(case_id: str) -> PatientCase:
    if case_id not in PATIENTS:
        raise KeyError(f"Unknown synthetic case_id: {case_id}")
    return PATIENTS[case_id]


def get_facility(facility_id: str) -> Facility:
    if facility_id not in FACILITIES_BY_ID:
        raise KeyError(f"Unknown facility_id: {facility_id}")
    return FACILITIES_BY_ID[facility_id]


def facilities_within(radius_miles: float) -> list[Facility]:
    """Facilities inside a radius, nearest first."""
    return sorted(
        (f for f in FACILITIES if f.distance_miles <= radius_miles),
        key=lambda f: f.distance_miles,
    )


def dialable_facilities() -> list[Facility]:
    """Facilities with a real demo receiver attached.

    Used by the live actuator and by scripts that must not dial placeholders.
    """
    return [f for f in FACILITIES if f.phone != PLACEHOLDER_PHONE]
