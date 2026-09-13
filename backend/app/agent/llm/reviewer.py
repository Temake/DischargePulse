"""LLM transcript reviewer.

The rules read CALL-E's yes / no / unknown answers. They cannot read a caveat -
"yes, we take wound VACs, but not until Thursday" extracts as `yes` and would
count as confirmed for a discharge today. The reviewer reads the facility's own
words and flags findings that are more optimistic than the evidence.

It proposes; deterministic code decides. A flag is applied only when:

  1. it names one of the patient's hard requirements,
  2. it moves the finding to a MORE cautious state - never towards confirmed,
  3. its quote appears verbatim in what the facility said.

Anything else is kept as a rejected flag with the reason. So the model can make
the agent more careful, never more certain - and it cannot cite words that were
not said, or cite the hospital's own caller.

Evidence always matches where the answers came from. Answers extracted from a
real call are reviewed against that call's transcript. Simulated answers are
reviewed against the simulated statements only: the real transcript did not
produce them, so judging one by the other would be meaningless.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.agent.llm.claude import LLMBackend, LLMUnavailable
from app.agent.reasoning_engine import ReasoningEngine
from app.models.schemas import (
    AnswersSource,
    Facility,
    FacilityEvaluation,
    LLMReview,
    PatientCase,
    ReviewFlag,
    TranscriptSpeaker,
    VerificationState,
)

log = logging.getLogger(__name__)

# Higher means more confident. A flag must move a finding strictly down.
_CONFIDENCE: dict[VerificationState, int] = {
    VerificationState.CONFIRMED: 2,
    VerificationState.NOT_CONFIRMED: 1,
    VerificationState.UNKNOWN: 1,
    VerificationState.EXPLICITLY_UNAVAILABLE: 0,
}

# Short fragments like "yes" or "no" match almost any transcript, so they prove
# nothing about what was said.
MIN_QUOTE_CHARS = 12

# Answer fields that hold the facility's words rather than enum values.
_TEXT_ANSWER_SUFFIX = "_detail"
_TEXT_ANSWER_FIELDS = ("refusal_reason", "earliest_admission")

SYSTEM_PROMPT = """You review phone-call evidence for a hospital discharge-planning system. The system checks whether a skilled nursing facility can accept a patient, one hard requirement at a time.

You receive the rule-based finding for each hard requirement and the evidence of what the facility said. Your only job is to catch findings that are more optimistic than that evidence supports - for example a requirement marked confirmed when staff attached a condition, a delay, a caveat, or said something elsewhere that undercuts it.

Rules:
- Only ever propose a MORE cautious state: "not_confirmed" when the evidence is conditional, hedged or unclear, or "explicitly_unavailable" when the facility said it cannot do it. Never propose confirming anything.
- Every flag must quote the facility's own words exactly as they appear in the evidence, copied character for character. Do not paraphrase. Do not quote the hospital caller.
- Do not flag a requirement whose current state already reflects the concern.
- If the findings already match the evidence, return an empty list of flags. Most calls need none."""


def _normalise(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text.strip(" \"'.,;:!?")


def _flag_schema(codes: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "enum": codes},
                        "proposed_state": {
                            "type": "string",
                            "enum": ["not_confirmed", "explicitly_unavailable"],
                        },
                        "quote": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["code", "proposed_state", "quote", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["flags"],
        "additionalProperties": False,
    }


class TranscriptReviewer:
    """Reviews one evaluation's findings against the facility's own words."""

    def __init__(self, backend: LLMBackend, engine: ReasoningEngine | None = None) -> None:
        self._backend = backend
        self._engine = engine or ReasoningEngine()

    # -- evidence -----------------------------------------------------------

    @staticmethod
    def _evidence(evaluation: FacilityEvaluation) -> tuple[list[tuple[str, str]], str]:
        """(quotable passages as (source label, text), prompt rendering)."""
        observation = evaluation.observation
        result = observation.structured_result or {}
        simulated = observation.answers_source is AnswersSource.SIMULATED
        answers_label = "simulated answers" if simulated else "call answers"

        passages: list[tuple[str, str]] = []
        lines: list[str] = []

        if not simulated:
            lines.append("CALL TRANSCRIPT (HOSPITAL = our caller, FACILITY = facility staff; only FACILITY lines may be quoted):")
            for turn in observation.transcript_turns:
                who = {
                    TranscriptSpeaker.BOT: "HOSPITAL",
                    TranscriptSpeaker.USER: "FACILITY",
                }.get(turn.speaker, "UNKNOWN SPEAKER")
                lines.append(f"  {who}: {turn.text}")
                # Only the facility's words can support a flag.
                if turn.speaker is TranscriptSpeaker.USER:
                    passages.append(("transcript", turn.text))
        else:
            lines.append(
                "NOTE: these are simulated facility answers from a test scenario, "
                "not a recorded conversation. Review them as the facility's statements."
            )

        lines.append("")
        lines.append("FACILITY STATEMENTS EXTRACTED FROM THE CALL:" if not simulated
                     else "SIMULATED FACILITY STATEMENTS:")
        for key, value in result.items():
            if not isinstance(value, str) or not value.strip():
                continue
            if key.endswith(_TEXT_ANSWER_SUFFIX) or key in _TEXT_ANSWER_FIELDS:
                lines.append(f"  {key}: {value}")
                passages.append((answers_label, value))

        return passages, "\n".join(lines)

    @staticmethod
    def _locate(quote: str, passages: list[tuple[str, str]]) -> str:
        needle = _normalise(quote)
        if len(needle) < MIN_QUOTE_CHARS:
            return ""
        for label, text in passages:
            if needle in _normalise(text):
                return label
        return ""

    # -- review -------------------------------------------------------------

    async def review(
        self,
        patient: PatientCase,
        facility: Facility,
        evaluation: FacilityEvaluation,
    ) -> FacilityEvaluation:
        observation = evaluation.observation
        if observation is None or not observation.is_usable or not evaluation.findings:
            return evaluation

        passages, evidence = self._evidence(evaluation)
        hard_codes = [r.code.value for r in patient.hard_requirements()]
        findings_text = "\n".join(
            f"  {f.code.value} ({f.label}): {f.state.value}" for f in evaluation.findings
        )
        prompt = (
            f"Facility: {facility.name}\n"
            f"Patient needs: "
            + "; ".join(f"{r.label} ({r.detail})" for r in patient.hard_requirements())
            + f"\n\nCURRENT FINDINGS:\n{findings_text}\n\n{evidence}"
        )

        try:
            data, model = await self._backend.structured(
                system=SYSTEM_PROMPT, prompt=prompt, schema=_flag_schema(hard_codes)
            )
        except LLMUnavailable as exc:
            log.warning("Transcript review skipped for %s: %s", facility.name, exc)
            return evaluation.model_copy(
                update={
                    "review": LLMReview(
                        model=self._backend.model,
                        answers_source=observation.answers_source,
                        error=str(exc),
                    )
                }
            )

        findings = [f.model_copy() for f in evaluation.findings]
        by_code = {f.code.value: f for f in findings}
        flags: list[ReviewFlag] = []

        for raw in data.get("flags", []) or []:
            flags.append(self._judge(raw, by_code, hard_codes, passages))

        review = LLMReview(model=model, answers_source=observation.answers_source, flags=flags)
        revised = evaluation.model_copy(update={"review": review})
        if not review.accepted_flags:
            return revised
        return self._engine.rederive(patient, facility, revised, findings)

    @staticmethod
    def _judge(
        raw: dict[str, Any],
        by_code: dict,
        hard_codes: list[str],
        passages: list[tuple[str, str]],
    ) -> ReviewFlag:
        code_value = str(raw.get("code", ""))
        quote = str(raw.get("quote", ""))
        reason = str(raw.get("reason", ""))
        proposed = str(raw.get("proposed_state", ""))

        def rejected(why: str, code=None, from_state=None, to_state=None, source="") -> ReviewFlag:
            return ReviewFlag(
                code=code,
                from_state=from_state,
                to_state=to_state,
                quote=quote,
                quote_source=source,
                reason=reason,
                accepted=False,
                rejection_reason=why,
            )

        if code_value not in hard_codes or code_value not in by_code:
            return rejected(f"'{code_value}' is not one of this patient's hard requirements")

        finding = by_code[code_value]
        try:
            to_state = VerificationState(proposed)
        except ValueError:
            return rejected(f"unknown state '{proposed}'", finding.code, finding.state)

        if _CONFIDENCE[to_state] >= _CONFIDENCE[finding.state]:
            return rejected(
                f"would not make {code_value} more cautious ({finding.state.value} -> {to_state.value})",
                finding.code, finding.state, to_state,
            )

        source = TranscriptReviewer._locate(quote, passages)
        if not source:
            return rejected(
                "quote does not appear verbatim in what the facility said",
                finding.code, finding.state, to_state,
            )

        flag = ReviewFlag(
            code=finding.code,
            from_state=finding.state,
            to_state=to_state,
            quote=quote,
            quote_source=source,
            reason=reason,
            accepted=True,
        )
        finding.state = to_state
        finding.quote = quote
        finding.rationale = f"Downgraded by transcript review: {reason}"
        return flag


def review_label(evaluation: FacilityEvaluation) -> str:
    """How to name the review in a headline without overstating its evidence."""
    review = evaluation.review
    if review and review.answers_source is AnswersSource.SIMULATED:
        return "review of the simulated answers"
    return "transcript review"


__all__ = ["TranscriptReviewer", "review_label", "SYSTEM_PROMPT", "MIN_QUOTE_CHARS"]
