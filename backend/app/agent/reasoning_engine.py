"""Placement Reasoning & Verification Engine.

Evaluates what a call actually established against what the care team requires.

Two rules govern everything here:

1. **Absence of a no is not a yes.** A hard requirement counts as met only when
   staff confirmed it. Silence, hedging, and "I'd have to check" all fail - they
   just fail differently from an outright no, and a case manager needs to see
   which.

2. **Live intelligence beats the directory.** When a facility's own staff
   contradict the directory record, the call wins. Detecting that gap is the
   reason this system places calls at all.
"""

from __future__ import annotations

import logging

from app.agent.planner import resolve_sister_facility
from app.models.schemas import (
    CallObservation,
    ConstraintCode,
    ConstraintFinding,
    ConstraintKind,
    Contradiction,
    Disposition,
    Facility,
    FacilityEvaluation,
    PatientCase,
    VerificationState,
)

log = logging.getLogger(__name__)

# CALL-E returns tri-state enums; map them to verification semantics.
_STATE_BY_ANSWER: dict[str, VerificationState] = {
    "yes": VerificationState.CONFIRMED,
    "no": VerificationState.EXPLICITLY_UNAVAILABLE,
    "unknown": VerificationState.NOT_CONFIRMED,
}

NO_SISTER_VALUES = {"", "none", "no", "n/a", "unknown"}

# Match score weights. Hard requirements dominate: a facility that meets every
# clinical need but sits further away still beats a closer one that cannot.
_HARD_WEIGHT = 60.0
_DISTANCE_WEIGHT = 20.0
_RATING_WEIGHT = 15.0
_PARTNER_WEIGHT = 5.0


class ReasoningEngine:
    """Turns a raw call observation into a placement decision."""

    def evaluate(
        self,
        patient: PatientCase,
        facility: Facility,
        observation: CallObservation,
    ) -> FacilityEvaluation:
        if not observation.is_usable:
            return self._unreached(facility, observation)

        result = observation.structured_result or {}
        findings = self._findings(patient, result)
        contradictions = self._contradictions(facility, findings, result)

        disqualifying = [
            f.code
            for f in findings
            if f.state is not VerificationState.CONFIRMED
        ]

        disposition = self._disposition(findings)
        score = self._score(patient, facility, findings)

        return FacilityEvaluation(
            facility_id=facility.facility_id,
            facility_name=facility.name,
            disposition=disposition,
            match_score=round(score, 1),
            findings=findings,
            contradictions=contradictions,
            disqualifying_codes=disqualifying,
            sister_facility_leads=self._sister_leads(facility, result),
            coordinator_name=_clean(result.get("coordinator_name")),
            callback_number=_clean(result.get("direct_callback_number")),
            fax_number=_clean(result.get("referral_fax_number")),
            observation=observation,
        )

    # -- verification -------------------------------------------------------

    def _findings(
        self, patient: PatientCase, result: dict
    ) -> list[ConstraintFinding]:
        findings: list[ConstraintFinding] = []

        for req in patient.hard_requirements():
            raw = result.get(req.code.value)
            answer = str(raw).strip().lower() if raw is not None else ""
            state = _STATE_BY_ANSWER.get(answer, VerificationState.NOT_CONFIRMED)
            quote = _clean(result.get(f"{req.code.value}_detail"))

            findings.append(
                ConstraintFinding(
                    code=req.code,
                    kind=ConstraintKind.HARD,
                    label=req.label,
                    state=state,
                    quote=quote,
                    rationale=_rationale(state, req.label),
                )
            )

        return findings

    def _disposition(self, findings: list[ConstraintFinding]) -> Disposition:
        """A hard requirement is met only when explicitly confirmed."""
        if any(
            f.state is VerificationState.EXPLICITLY_UNAVAILABLE for f in findings
        ):
            return Disposition.DISQUALIFIED

        if all(f.state is VerificationState.CONFIRMED for f in findings):
            return Disposition.MATCH_VERIFIED

        # Nothing was refused, but something never got a straight answer. Not a
        # match, and not a rejection either - a human should chase it.
        return Disposition.NEEDS_FOLLOW_UP

    # -- contradiction detection --------------------------------------------

    def _contradictions(
        self,
        facility: Facility,
        findings: list[ConstraintFinding],
        result: dict,
    ) -> list[Contradiction]:
        """Diff live call intelligence against the static directory record."""
        contradictions: list[Contradiction] = []

        for finding in findings:
            claim = facility.claim_for(finding.code)
            if claim is None:
                continue

            quote = finding.quote or _clean(result.get(f"{finding.code.value}_detail"))

            # Directory promises a capability the facility just denied.
            if (
                claim.claimed_available
                and finding.state is VerificationState.EXPLICITLY_UNAVAILABLE
            ):
                contradictions.append(
                    Contradiction(
                        code=finding.code,
                        label=finding.label,
                        directory_says=f"{finding.label}: available",
                        call_says=f"{finding.label}: unavailable",
                        quote=quote,
                        resolution=(
                            "Live call intelligence overrides the directory "
                            "record. Facility disqualified."
                        ),
                    )
                )

            # Directory says no, but staff confirmed it. Worth surfacing: a
            # directory-only search would have skipped a viable facility.
            elif (
                not claim.claimed_available
                and finding.state is VerificationState.CONFIRMED
            ):
                contradictions.append(
                    Contradiction(
                        code=finding.code,
                        label=finding.label,
                        directory_says=f"{finding.label}: unavailable",
                        call_says=f"{finding.label}: available",
                        quote=quote,
                        resolution=(
                            "Directory record is stale. Facility remains "
                            "eligible on this requirement."
                        ),
                    )
                )

        return contradictions

    # -- scoring ------------------------------------------------------------

    def _score(
        self,
        patient: PatientCase,
        facility: Facility,
        findings: list[ConstraintFinding],
    ) -> float:
        """0-100, computed only from confirmed evidence plus soft preferences."""
        if not findings:
            return 0.0

        confirmed = sum(
            1 for f in findings if f.state is VerificationState.CONFIRMED
        )
        hard_component = (confirmed / len(findings)) * _HARD_WEIGHT

        span = max(patient.max_radius_miles, 1)
        proximity = max(0.0, 1.0 - (facility.distance_miles / span))
        distance_component = proximity * _DISTANCE_WEIGHT

        rating_component = (facility.cms_star_rating / 5.0) * _RATING_WEIGHT
        partner_component = _PARTNER_WEIGHT if facility.preferred_partner else 0.0

        return (
            hard_component
            + distance_component
            + rating_component
            + partner_component
        )

    # -- leads --------------------------------------------------------------

    def _sister_leads(self, facility: Facility, result: dict) -> list[str]:
        """Facilities worth calling next, from the call and from ownership data."""
        leads: list[str] = []

        spoken = (result.get("sister_facility_name") or "").strip()
        if spoken.lower() not in NO_SISTER_VALUES:
            resolved = resolve_sister_facility(spoken)
            if resolved and resolved != facility.facility_id:
                leads.append(resolved)

        # Ownership links are a weaker signal than a name given on the call, so
        # they come second and never displace it.
        for sister_id in facility.sister_facility_ids:
            if sister_id not in leads:
                leads.append(sister_id)

        return leads

    # -- failure ------------------------------------------------------------

    def _unreached(
        self, facility: Facility, observation: CallObservation
    ) -> FacilityEvaluation:
        return FacilityEvaluation(
            facility_id=facility.facility_id,
            facility_name=facility.name,
            disposition=Disposition.UNREACHED,
            match_score=0.0,
            findings=[],
            observation=observation,
        )


def _clean(value: object) -> str | None:
    """Normalise CALL-E's empty-string convention to None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _rationale(state: VerificationState, label: str) -> str:
    if state is VerificationState.CONFIRMED:
        return f"Admissions staff confirmed {label.lower()}."
    if state is VerificationState.EXPLICITLY_UNAVAILABLE:
        return f"Facility stated it cannot meet {label.lower()}."
    return f"{label} was raised but never confirmed on the call."


def rank_evaluations(
    evaluations: list[FacilityEvaluation],
) -> list[FacilityEvaluation]:
    """Placeable matches first, then by score."""
    return sorted(
        evaluations,
        key=lambda e: (e.is_placeable, e.match_score),
        reverse=True,
    )
