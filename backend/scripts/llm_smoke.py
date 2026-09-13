"""Live check of the LLM roles against a real Claude backend.

Sends one transcript review and one case-manager brief using the provider in
.env (LLM_PROVIDER=anthropic or bedrock), and reports exactly what came back.
Two model requests; no CALL-E calls.

    cd backend
    python scripts/llm_smoke.py

The review case has a planted caveat - the facility confirms wound VAC care "but
only once our certified nurse is back on Thursday". A working reviewer should
downgrade wound_vac with that verbatim quote. The check reports the outcome
either way; the guard rules decide what is applied, not the model.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.llm import build_llm_components  # noqa: E402
from app.agent.placement_agent import PlacementAgent  # noqa: E402
from app.agent.reasoning_engine import ReasoningEngine  # noqa: E402
from app.agent.tools.simulated_attendant import ScriptedAttendantActuator  # noqa: E402
from app.config import settings  # noqa: E402
from app.data.scenarios import scenario_for  # noqa: E402
from app.data.synthetic_data import get_facility, get_patient  # noqa: E402
from app.models.schemas import (  # noqa: E402
    CallMode,
    CallObservation,
    CallOutcome,
    TranscriptSpeaker,
    TranscriptTurn,
)

CAVEAT = "Yes, we can take the wound VAC patient, but only once our certified nurse is back on Thursday."


def caveat_observation() -> CallObservation:
    """A call whose extracted answers say yes, but whose words carry a caveat."""
    return CallObservation(
        facility_id="SNF-004",
        phone="+15555550100",
        mode=CallMode.REPLAY,
        call_id="call_llm_smoke",
        outcome=CallOutcome.COMPLETED,
        structured_result=scenario_for("10482", "SNF-004"),
        summary="Admissions confirmed availability.",
        transcript_turns=[
            TranscriptTurn(offset_seconds=3, speaker=TranscriptSpeaker.BOT,
                           text="Can you take a patient on a wound VAC for admission within 24 hours?"),
            TranscriptTurn(offset_seconds=8, speaker=TranscriptSpeaker.USER, text=CAVEAT),
            TranscriptTurn(offset_seconds=15, speaker=TranscriptSpeaker.BOT,
                           text="And IV ceftriaxone every 24 hours?"),
            TranscriptTurn(offset_seconds=18, speaker=TranscriptSpeaker.USER,
                           text="Yes, that's no problem, and we're in network with Aetna."),
        ],
    )


async def main_async() -> int:
    print("=" * 72)
    print(f"  LLM smoke test - provider={settings.llm_provider} model={settings.llm_model}")
    if settings.llm_provider == "bedrock":
        print(f"  aws region: {settings.aws_region or '(from AWS config)'}")
    print("=" * 72)

    settings.llm_review_enabled = True
    reviewer, briefer = build_llm_components()
    if reviewer is None:
        print("  LLM components could not be built - check LLM_PROVIDER and the SDK install.")
        return 1

    # -- review -------------------------------------------------------------
    patient = get_patient("10482")
    facility = get_facility("SNF-004")
    evaluation = ReasoningEngine().evaluate(patient, facility, caveat_observation())
    print(f"\n  REVIEW  (rules said: {evaluation.disposition.value})")

    reviewed = await reviewer.review(patient, facility, evaluation)
    review = reviewed.review
    if review.error:
        print(f"    FAILED: {review.error}")
        return 1

    print(f"    served by : {review.model}")
    print(f"    flags     : {len(review.flags)} ({len(review.accepted_flags)} applied)")
    for flag in review.flags:
        outcome = f"APPLIED ({flag.quote_source})" if flag.accepted else f"REJECTED - {flag.rejection_reason}"
        code = flag.code.value if flag.code else "?"
        print(f"      - {code}: {outcome}")
        print(f"        quote : \"{flag.quote}\"")
        print(f"        reason: {flag.reason}")
    print(f"    result    : {evaluation.disposition.value} -> {reviewed.disposition.value}")

    # -- brief --------------------------------------------------------------
    run = await PlacementAgent(ScriptedAttendantActuator(), briefer=briefer).run(patient)
    proposal = run.proposal
    print(f"\n  BRIEF  (source={proposal.brief_source}, model={proposal.brief_model})")
    for line in (proposal.brief or "").splitlines():
        print(f"    {line}")

    print("\n" + "=" * 72)
    if proposal.brief_source != "llm":
        print("  Brief fell back to the template - see the log line above for why.")
        return 1
    print("  Live backend OK: review and brief both served by the model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
