"""Case-manager brief.

A short plain-language summary shown at the approval gate and printed on the
referral packet: what is proposed, why, what was ruled out, and what the case
manager should check before approving.

Claude writes it when available. Otherwise it is assembled from the evaluation,
so the packet always has one. Either way, the provenance sentence at the top is
written by code, not the model - whether answers were simulated is too important
to leave to a prompt.
"""

from __future__ import annotations

import logging

from app.agent.llm.claude import LLMBackend, LLMUnavailable
from app.models.schemas import (
    AnswersSource,
    CallMode,
    Disposition,
    FacilityEvaluation,
    PatientCase,
    PlacementRun,
    VerificationState,
)

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write short briefs for hospital case managers deciding whether to approve a skilled nursing facility placement proposed by an automated agent.

Write 120 to 180 words of plain prose in four short labelled parts: Recommendation, Why, Ruled out, Check before approving.

Use only the facts provided. Do not invent names, numbers, availability or clinical details. Do not give clinical advice. The case manager makes the decision; do not tell them to approve. If any requirement was downgraded by transcript review, or any facility needs follow-up, say so under Check before approving."""


def provenance_note(run: PlacementRun) -> str:
    """How the answers behind this proposal were obtained, stated by code."""
    observations = [e.observation for e in run.evaluations if e.observation]
    live = sum(1 for o in observations if o.mode is CallMode.LIVE)
    scripted = sum(1 for o in observations if o.mode is CallMode.SCRIPTED)
    simulated = sum(1 for o in observations if o.answers_source is AnswersSource.SIMULATED)

    parts = [f"{live} live call(s) placed"]
    if scripted:
        parts.append(f"{scripted} facility(ies) checked without a call")
    note = "Provenance: " + ", ".join(parts) + "."
    if simulated:
        note += (
            f" Facility answers for {simulated} of {len(observations)} check(s) were "
            f"SIMULATED, not said on a call - verify directly before relying on them."
        )
    return note


def _facts(patient: PatientCase, run: PlacementRun, best: FacilityEvaluation) -> str:
    lines = [
        f"Patient: {patient.display_name}, {patient.age}-year-old {patient.sex}, {patient.payer_plan}.",
        "Needs: " + "; ".join(f"{r.label} ({r.detail})" for r in patient.hard_requirements()),
        "",
        f"PROPOSED: {best.facility_name} - match score {best.match_score}/100.",
    ]
    for f in best.findings:
        quote = f' - "{f.quote}"' if f.quote else ""
        lines.append(f"  {f.label}: {f.state.value}{quote}")
    if best.coordinator_name:
        lines.append(f"  Coordinator: {best.coordinator_name}")
    if best.fax_number:
        lines.append(f"  Referral fax: {best.fax_number}")

    lines.append("")
    lines.append("OTHER FACILITIES CHECKED:")
    for e in run.evaluations:
        if e.facility_id == best.facility_id:
            continue
        failed = [f.label for f in e.findings if f.state is not VerificationState.CONFIRMED]
        detail = f" (not met: {', '.join(failed)})" if failed else ""
        lines.append(f"  {e.facility_name}: {e.disposition.value}{detail}")
        for c in e.contradictions:
            lines.append(f"    Directory said {c.directory_says}; the facility said {c.call_says}.")

    reviewed = [
        (e.facility_name, flag)
        for e in run.evaluations
        if e.review
        for flag in e.review.accepted_flags
    ]
    if reviewed:
        lines.append("")
        lines.append("DOWNGRADED BY TRANSCRIPT REVIEW:")
        for name, flag in reviewed:
            lines.append(f'  {name}: {flag.code.value} -> {flag.to_state.value} ("{flag.quote}")')

    lines.append("")
    lines.append(provenance_note(run))
    return "\n".join(lines)


def template_brief(patient: PatientCase, run: PlacementRun, best: FacilityEvaluation) -> str:
    confirmed = [f.label for f in best.findings if f.state is VerificationState.CONFIRMED]
    others = [e for e in run.evaluations if e.facility_id != best.facility_id]
    ruled_out = [e.facility_name for e in others if e.disposition is Disposition.DISQUALIFIED]
    follow_up = [
        e.facility_name for e in others
        if e.disposition in (Disposition.NEEDS_FOLLOW_UP, Disposition.UNREACHED)
    ]

    checks = ["Confirm bed availability and admission time with the coordinator directly"]
    if best.coordinator_name:
        checks[0] += f" ({best.coordinator_name})"
    if follow_up:
        checks.append(f"{', '.join(follow_up)} could not be fully verified")

    return "\n".join(
        [
            f"Recommendation: {best.facility_name} (match score {best.match_score}/100).",
            f"Why: confirmed {', '.join(confirmed) or 'no requirements'}.",
            f"Ruled out: {', '.join(ruled_out) or 'none'}.",
            "Check before approving: " + "; ".join(checks) + ".",
        ]
    )


class CaseManagerBriefer:
    """Writes the brief with Claude, falling back to the template."""

    def __init__(self, backend: LLMBackend | None) -> None:
        self._backend = backend

    async def write(
        self, patient: PatientCase, run: PlacementRun, best: FacilityEvaluation
    ) -> tuple[str, str, str | None]:
        """Return (brief, source "llm" | "template", model or None)."""
        note = provenance_note(run)

        if self._backend is not None:
            try:
                text, model = await self._backend.text(
                    system=SYSTEM_PROMPT, prompt=_facts(patient, run, best), max_tokens=16000
                )
                return f"{note}\n\n{text}", "llm", model
            except LLMUnavailable as exc:
                log.warning("Brief written from template: %s", exc)

        return f"{note}\n\n{template_brief(patient, run, best)}", "template", None
