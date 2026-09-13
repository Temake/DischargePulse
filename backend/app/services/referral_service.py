"""Referral packet PDF.

Drafted when a run reaches the human gate, so the case manager can read exactly
what would be sent before deciding; regenerated with the decision stamped on it
once they approve or decline.

The packet reports provenance as faithfully as the console does: every
requirement row says whether its answer came from a live call, a replay or a
script, whether the answer was simulated, and whether transcript review
downgraded it. It is marked synthetic throughout. It is never transmitted -
e-fax dispatch is not implemented, and the packet says so.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.schemas import (
    AnswersSource,
    ApprovalStatus,
    CallMode,
    Facility,
    FacilityEvaluation,
    PatientCase,
    PlacementRun,
    VerificationState,
)

SYNTHETIC_BANNER = (
    "SYNTHETIC TEST DATA - audit-ready prototype. Not a real patient. "
    "This packet has NOT been transmitted: e-fax dispatch is not implemented."
)

_STATE_TEXT = {
    VerificationState.CONFIRMED: "Confirmed",
    VerificationState.NOT_CONFIRMED: "Not confirmed",
    VerificationState.EXPLICITLY_UNAVAILABLE: "Unavailable",
    VerificationState.UNKNOWN: "Unknown",
}

_styles = getSampleStyleSheet()
_BODY = ParagraphStyle("body", parent=_styles["BodyText"], fontSize=9, leading=12)
_SMALL = ParagraphStyle("small", parent=_BODY, fontSize=8, leading=10)
_H1 = ParagraphStyle("h1", parent=_styles["Title"], fontSize=18, leading=22, alignment=0)
_H2 = ParagraphStyle("h2", parent=_styles["Heading2"], fontSize=12, leading=15, spaceBefore=10)
_BANNER = ParagraphStyle(
    "banner", parent=_BODY, textColor=colors.HexColor("#8A1C1C"),
    backColor=colors.HexColor("#FCEDEC"), borderPadding=6, fontSize=8.5,
)


def _p(text: object, style: ParagraphStyle = _BODY) -> Paragraph:
    """A paragraph from untrusted text. reportlab parses markup, so escape it."""
    return Paragraph(escape("" if text is None else str(text)).replace("\n", "<br/>"), style)


def _table(rows: list[list], widths: list[float], header: bool = True) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9CDD2")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF1F4")))
    table.setStyle(TableStyle(style))
    return table


def _how_obtained(evaluation: FacilityEvaluation, code) -> str:
    observation = evaluation.observation
    if observation is None:
        return "Not reached"
    how = {
        CallMode.LIVE: "Live CALL-E call",
        CallMode.REPLAY: "Replay of a recorded call",
        CallMode.SCRIPTED: "Scripted - no call placed",
    }[observation.mode]
    if observation.answers_source is AnswersSource.SIMULATED:
        how += "; answer SIMULATED"
    review = evaluation.review
    if review and any(f.code == code for f in review.accepted_flags):
        how += "; downgraded by transcript review"
    return how


def _decision_line(run: PlacementRun) -> str:
    proposal = run.proposal
    if proposal.status is ApprovalStatus.PENDING:
        return "DRAFT - awaiting case manager approval"
    verb = "APPROVED" if proposal.status is ApprovalStatus.APPROVED else "DECLINED"
    when = proposal.decided_at.strftime("%Y-%m-%d %H:%M UTC") if proposal.decided_at else ""
    return f"{verb} by {proposal.decided_by} on {when}"


def write_referral_packet(
    *,
    run_id: str,
    telephony: str,
    run: PlacementRun,
    patient: PatientCase,
    facility: Facility,
    path: Path,
    compress: bool = True,
) -> Path:
    """Render the packet for `run.proposal` to `path` and return the path."""
    proposal = run.proposal
    if proposal is None:
        raise ValueError("Run has no proposal to build a referral packet for.")

    best = proposal.evaluation
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story: list = []

    # -- header -------------------------------------------------------------
    story += [
        _p("Post-Acute Referral Packet", _H1),
        _p(f"Status: {_decision_line(run)}"),
        _p(f"Run {run_id} - generated {generated}", _SMALL),
        Spacer(1, 6),
        _p(SYNTHETIC_BANNER, _BANNER),
        Spacer(1, 4),
    ]

    # -- brief --------------------------------------------------------------
    if proposal.brief:
        source = (
            f"Written by Claude ({proposal.brief_model})"
            if proposal.brief_source == "llm"
            else "Assembled from the evaluation (no model used)"
        )
        story += [_p("Case manager brief", _H2), _p(source, _SMALL), _p(proposal.brief)]

    # -- decision -----------------------------------------------------------
    if proposal.status is not ApprovalStatus.PENDING:
        story += [_p("Decision", _H2), _p(_decision_line(run))]
        if proposal.decision_note:
            story.append(_p(f"Note: {proposal.decision_note}"))

    # -- patient ------------------------------------------------------------
    story += [
        _p("Patient (synthetic, de-identified)", _H2),
        _table(
            [
                [_p("Case"), _p(patient.display_name)],
                [_p("Age / sex"), _p(f"{patient.age} / {patient.sex}")],
                [_p("Coverage"), _p(patient.payer_plan)],
                [_p("Weight"), _p(f"{patient.weight_lbs} lbs")],
                [_p("Hospital day"), _p(patient.hospital_day)],
                [_p("Summary"), _p(patient.discharge_summary)],
            ],
            [1.4 * inch, 5.6 * inch],
            header=False,
        ),
    ]

    # -- proposed facility --------------------------------------------------
    story += [
        _p("Proposed facility", _H2),
        _table(
            [
                [_p("Facility"), _p(f"{facility.name} ({facility.facility_type})")],
                [_p("Address"), _p(f"{facility.address}, {facility.zip_code}")],
                [_p("Distance"), _p(f"{facility.distance_miles:.1f} mi from {patient.family_zip}")],
                [_p("CMS rating"), _p(f"{facility.cms_star_rating} stars")],
                [_p("Coordinator"), _p(best.coordinator_name or "-")],
                [_p("Referral fax"), _p(best.fax_number or "-")],
                [_p("Match score"), _p(f"{best.match_score} / 100")],
            ],
            [1.4 * inch, 5.6 * inch],
            header=False,
        ),
    ]

    # -- requirement verification -------------------------------------------
    rows = [[_p("Requirement"), _p("Result"), _p("What was said"), _p("How obtained")]]
    for finding in best.findings:
        rows.append(
            [
                _p(finding.label),
                _p(_STATE_TEXT[finding.state]),
                _p(finding.quote or "-", _SMALL),
                _p(_how_obtained(best, finding.code), _SMALL),
            ]
        )
    story += [
        _p("Requirement verification", _H2),
        _table(rows, [1.5 * inch, 1.0 * inch, 2.9 * inch, 1.6 * inch]),
    ]

    # -- contradictions -----------------------------------------------------
    contradictions = [(e, c) for e in run.evaluations for c in e.contradictions]
    if contradictions:
        rows = [[_p("Facility"), _p("Directory said"), _p("Facility said"), _p("Resolution")]]
        for evaluation, c in contradictions:
            said = c.call_says + (f' - "{c.quote}"' if c.quote else "")
            rows.append([_p(evaluation.facility_name), _p(c.directory_says), _p(said, _SMALL), _p(c.resolution, _SMALL)])
        story += [
            _p("Directory contradictions", _H2),
            _table(rows, [1.5 * inch, 1.3 * inch, 2.5 * inch, 1.7 * inch]),
        ]

    # -- transcript review --------------------------------------------------
    reviewed = [e for e in run.evaluations if e.review]
    if reviewed:
        story.append(_p("Transcript review", _H2))
        story.append(
            _p(
                "An LLM reviewed each call's evidence. It can only make a finding more "
                "cautious, and only when it quotes the facility's words verbatim; "
                "anything else is rejected and listed here.",
                _SMALL,
            )
        )
        rows = [[_p("Facility"), _p("Flag"), _p("Quote"), _p("Outcome")]]
        for evaluation in reviewed:
            review = evaluation.review
            if review.error:
                rows.append([_p(evaluation.facility_name), _p("-"), _p("-"), _p(f"Review unavailable: {review.error}", _SMALL)])
                continue
            if not review.flags:
                rows.append([_p(evaluation.facility_name), _p("No issues found"), _p("-"), _p(f"Model: {review.model}", _SMALL)])
            for flag in review.flags:
                change = (
                    f"{flag.code.value}: {flag.from_state.value} -> {flag.to_state.value}"
                    if flag.code and flag.from_state and flag.to_state
                    else "(invalid flag)"
                )
                outcome = (
                    f"Applied ({flag.quote_source})"
                    if flag.accepted
                    else f"Rejected: {flag.rejection_reason}"
                )
                rows.append([_p(evaluation.facility_name), _p(f"{change}\n{flag.reason}", _SMALL), _p(flag.quote, _SMALL), _p(outcome, _SMALL)])
        story.append(_table(rows, [1.4 * inch, 2.2 * inch, 2.0 * inch, 1.4 * inch]))

    # -- other facilities ---------------------------------------------------
    others = [e for e in run.evaluations if e.facility_id != best.facility_id]
    if others:
        rows = [[_p("Facility"), _p("Outcome"), _p("Not met")]]
        for e in others:
            not_met = [f.label for f in e.findings if f.state is not VerificationState.CONFIRMED]
            rows.append([_p(e.facility_name), _p(e.disposition.value.replace("_", " ")), _p(", ".join(not_met) or "-", _SMALL)])
        story += [_p("Other facilities checked", _H2), _table(rows, [2.4 * inch, 1.5 * inch, 3.1 * inch])]

    # -- provenance ---------------------------------------------------------
    rows = [[_p("Facility"), _p("Mode"), _p("Answers"), _p("Call id"), _p("Duration")]]
    for e in run.evaluations:
        o = e.observation
        if o is None:
            continue
        rows.append(
            [
                _p(e.facility_name, _SMALL),
                _p(o.mode.value.upper(), _SMALL),
                _p(o.answers_source.value.upper(), _SMALL),
                _p(o.call_id or "no call", _SMALL),
                _p(f"{o.duration_seconds:.0f}s" if o.duration_seconds else "-", _SMALL),
            ]
        )
    story += [
        _p("Provenance", _H2),
        _p(
            f"Telephony: {telephony}. Live CALL-E calls in this run: {run.live_calls}. "
            f"Facilities checked: {run.calls_placed}.",
            _SMALL,
        ),
        _table(rows, [1.9 * inch, 0.9 * inch, 1.0 * inch, 2.4 * inch, 0.8 * inch]),
    ]

    # -- footer on every page -----------------------------------------------
    def footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(
            0.75 * inch, 0.5 * inch,
            f"DischargePulse - run {run_id} - SYNTHETIC TEST DATA - not transmitted - page {doc.page}",
        )
        canvas.restoreState()

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.8 * inch,
        title=f"Referral packet - {facility.name}",
        author="DischargePulse (synthetic prototype)",
        pageCompression=1 if compress else 0,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path
