"""Discharge Requirements & Placement Strategy Planner.

Turns a patient's care-team requirements into an ordered call queue. This
component decides *who to call and in what order* - it never decides whether a
facility is clinically appropriate, and it never places a call itself.

The ordering matters more than it looks: every position in the queue is a phone
call, and calls cost time and credit. Ranking by soft preferences up front means
the first facility contacted is usually the one a case manager would have picked
anyway.
"""

from __future__ import annotations

import logging

from app.data.synthetic_data import FACILITIES, FACILITIES_BY_ID
from app.models.schemas import (
    ConstraintCode,
    Facility,
    PatientCase,
    PlacementPlan,
)

log = logging.getLogger(__name__)

# Soft-preference weights used only for pre-call ordering. Post-call scoring
# lives in the reasoning engine and uses verified evidence instead.
_DISTANCE_WEIGHT = 0.5
_RATING_WEIGHT = 0.35
_PARTNER_WEIGHT = 0.15


class PlacementPlanner:
    """Builds and re-builds the facility call queue."""

    def __init__(self, facilities: list[Facility] | None = None) -> None:
        self._facilities = facilities if facilities is not None else FACILITIES

    # -- ranking ------------------------------------------------------------

    def _priority(self, facility: Facility, patient: PatientCase) -> float:
        """Higher is better. Pure directory data - nothing verified yet."""
        span = max(patient.max_radius_miles, 1)
        proximity = max(0.0, 1.0 - (facility.distance_miles / span))
        rating = facility.cms_star_rating / 5.0
        partner = 1.0 if facility.preferred_partner else 0.0

        return (
            proximity * _DISTANCE_WEIGHT
            + rating * _RATING_WEIGHT
            + partner * _PARTNER_WEIGHT
        )

    # -- filtering ----------------------------------------------------------

    def _payer_prefilter(
        self, facility: Facility, patient: PatientCase
    ) -> str | None:
        """Exclude facilities the directory says are out of network.

        This is a cost optimisation, not a verification. The directory is known
        to go stale - that is the premise of the whole system - so this only
        prunes calls we would almost certainly waste. Anything that survives the
        prefilter still has its payer status verified on the call.
        """
        if not facility.accepted_payers:
            return None
        if patient.payer in facility.accepted_payers:
            return None
        return f"Directory lists payers {', '.join(facility.accepted_payers)}; patient is {patient.payer}"

    # -- plan construction --------------------------------------------------

    def build_plan(
        self,
        patient: PatientCase,
        cycle: int = 1,
        radius_miles: float | None = None,
        exclude_ids: set[str] | None = None,
        rationale: str = "",
    ) -> PlacementPlan:
        """Rank every facility inside the radius that has not been called yet."""
        radius = radius_miles if radius_miles is not None else patient.search_radius_miles
        already_called = exclude_ids or set()

        excluded: dict[str, str] = {}
        candidates: list[Facility] = []

        for facility in self._facilities:
            if facility.facility_id in already_called:
                continue

            if facility.distance_miles > radius:
                excluded[facility.facility_id] = (
                    f"{facility.distance_miles:.1f} mi is outside the {radius:.0f} mi radius"
                )
                continue

            payer_reason = self._payer_prefilter(facility, patient)
            if payer_reason:
                excluded[facility.facility_id] = payer_reason
                continue

            candidates.append(facility)

        candidates.sort(key=lambda f: self._priority(f, patient), reverse=True)

        return PlacementPlan(
            cycle=cycle,
            radius_miles=radius,
            queue=[f.facility_id for f in candidates],
            rationale=rationale
            or (
                f"{len(candidates)} facilities within {radius:.0f} mi of "
                f"{patient.family_zip}, ranked by proximity, CMS rating and "
                f"preferred-partner status"
            ),
            excluded=excluded,
        )

    # -- re-planning --------------------------------------------------------

    def next_radius(self, patient: PatientCase, current: float) -> float | None:
        """Widen the search. Returns None when already at the cap.

        Expansion is stepwise rather than jumping straight to the maximum: a
        wider net means longer travel for the family, so the agent only trades
        that away when the closer options are genuinely exhausted.
        """
        if current >= patient.max_radius_miles:
            return None
        return float(min(current * 2, patient.max_radius_miles))

    def plan_sister_facilities(
        self,
        patient: PatientCase,
        leads: list[str],
        cycle: int,
        radius_miles: float,
        exclude_ids: set[str] | None = None,
    ) -> PlacementPlan:
        """Queue facilities named on a call, regardless of the current radius.

        A sister facility surfaced by admissions staff is a warm lead - someone
        with direct knowledge said they may have capacity - so it outranks the
        radius rule that would otherwise exclude it.
        """
        already_called = exclude_ids or set()
        queue = [
            fid
            for fid in leads
            if fid in FACILITIES_BY_ID and fid not in already_called
        ]

        names = ", ".join(FACILITIES_BY_ID[fid].name for fid in queue)
        return PlacementPlan(
            cycle=cycle,
            radius_miles=radius_miles,
            queue=queue,
            rationale=(
                f"Sister facility lead from a live call: {names}"
                if queue
                else "No new sister facility leads"
            ),
        )


def resolve_sister_facility(name: str, known: list[Facility] | None = None) -> str | None:
    """Map a facility name heard on a call to a known facility id.

    Staff rarely say a facility's full legal name, so match on the distinctive
    words rather than the whole string.
    """
    if not name:
        return None

    candidates = known if known is not None else FACILITIES
    needle = name.lower().strip()

    for facility in candidates:
        if facility.name.lower() == needle:
            return facility.facility_id

    # Fall back to overlap on distinctive tokens only. Generic industry words
    # appear in most facility names, so matching on them would resolve a
    # misheard name to an unrelated facility - and cost a wasted call.
    stop = {
        "the", "of", "at", "and", "-",
        "center", "centre", "facility", "care", "nursing", "skilled",
        "rehabilitation", "rehab", "post", "acute", "transitional",
        "health", "healthcare", "home", "services", "living", "manor",
    }
    needle_tokens = {t for t in needle.replace("-", " ").split() if t not in stop}
    if not needle_tokens:
        return None

    best_id: str | None = None
    best_overlap = 0
    for facility in candidates:
        tokens = {
            t
            for t in facility.name.lower().replace("-", " ").split()
            if t not in stop
        }
        overlap = len(tokens & needle_tokens)
        if overlap > best_overlap:
            best_overlap, best_id = overlap, facility.facility_id

    return best_id if best_overlap >= 1 else None
