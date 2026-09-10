"""Day-1 smoke test: place one real CALL-E call and read the structured result.

Run this BEFORE building anything else. It answers the questions that shape the
rest of the system: does the key work, how long does a call take end to end, and
how reliable is CALL-E's structured extraction.

    cd backend
    python scripts/hello_call.py --to +15555550100            # dry run
    python scripts/hello_call.py --to +15555550100 --execute  # spends 1 call

Dial only a phone you own or are authorised to call.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.tools.budget import budget  # noqa: E402
from app.config import settings  # noqa: E402

E164_HINT = "Phone must be E.164, e.g. +15555550100"

TASK = (
    "Call {phone} on behalf of a developer testing an integration. "
    "Say you are an automated test call that will take about fifteen seconds. "
    "Ask the person two things: first, whether they can hear you clearly, and "
    "second, to say a single word of their choice so it can be checked against "
    "the transcript. Thank them and end the call."
)

RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["can_hear_clearly", "spoken_word"],
    "properties": {
        "can_hear_clearly": {
            "type": "string",
            "enum": ["yes", "no", "unknown"],
            "description": (
                "Use yes if the person clearly confirmed they could hear. Use "
                "no if they said the audio was bad. Use unknown if the call "
                "did not settle this."
            ),
        },
        "spoken_word": {
            "type": "string",
            "description": (
                "The single word the person chose to say. Empty string if they "
                "never said one."
            ),
        },
    },
}


def _preflight(phone: str, execute: bool) -> bool:
    print("=" * 68)
    print("  CALL-E connectivity smoke test")
    print("=" * 68)

    ok = True

    key = settings.calle_api_key
    if key:
        print(f"  [ok]   CALLE_API_KEY present ({key[:9]}...)")
    else:
        print("  [FAIL] CALLE_API_KEY is not set.")
        print("         Get a key from the CALL-E dashboard, then put it in .env")
        ok = False

    if phone.startswith("+") and phone[1:].isdigit() and 7 <= len(phone[1:]) <= 15:
        print(f"  [ok]   Destination {phone}")
    else:
        print(f"  [FAIL] Bad destination {phone!r}. {E164_HINT}")
        ok = False

    print(f"  [info] Budget: {budget.summary()}")
    if budget.remaining <= 0 and execute:
        print("  [FAIL] No live call budget remaining.")
        ok = False

    try:
        import calle  # noqa: F401

        print("  [ok]   calle-ai SDK importable")
    except ImportError:
        print("  [FAIL] calle-ai not installed. Run: pip install calle-ai")
        ok = False

    print("-" * 68)
    return ok


def _report(call: object) -> None:
    def get(name: str, alt: str = ""):
        if isinstance(call, dict):
            return call.get(name, call.get(alt))
        return getattr(call, name, getattr(call, alt, None) if alt else None)

    print()
    print("=" * 68)
    print("  RESULT")
    print("=" * 68)
    print(f"  call_id            : {get('id', 'call_id')}")
    print(f"  status             : {get('status')}")
    print(f"  task_completed     : {get('task_completed', 'taskCompleted')}")
    print(f"  confidence         : {get('completion_confidence', 'completionConfidence')}")
    print(f"  summary            : {get('summary')}")
    print()
    print("  structured_result  :")
    structured = get("structured_result", "structuredResult")
    print(json.dumps(structured, indent=4, default=str) if structured else "    (null)")

    evidence = get("evidence") or []
    if evidence:
        print()
        print("  evidence:")
        for item in evidence:
            print(f"    - {item}")

    recipients = get("recipients") or []
    for recipient in recipients:
        attempts = (
            recipient.get("attempts")
            if isinstance(recipient, dict)
            else getattr(recipient, "attempts", [])
        ) or []
        for attempt in attempts:
            turns = (
                attempt.get("transcript_turns")
                if isinstance(attempt, dict)
                else getattr(attempt, "transcript_turns", [])
            ) or []
            if not turns:
                continue
            print()
            print("  transcript:")
            for turn in turns:
                if isinstance(turn, dict):
                    offset, speaker, text = (
                        turn.get("offset_seconds"),
                        turn.get("speaker"),
                        turn.get("text"),
                    )
                else:
                    offset, speaker, text = (
                        getattr(turn, "offset_seconds", None),
                        getattr(turn, "speaker", ""),
                        getattr(turn, "text", ""),
                    )
                stamp = f"{offset:>4}s" if offset is not None else "    -"
                print(f"    [{stamp}] {str(speaker).upper():<7} {text}")

    print("=" * 68)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", required=True, help=f"Destination. {E164_HINT}")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually place the call. Without this flag nothing is dialed.",
    )
    parser.add_argument(
        "--save",
        metavar="PATH",
        help="Write the raw terminal payload to a JSON file for inspection.",
    )
    args = parser.parse_args()

    ready = _preflight(args.to, args.execute)

    if args.execute and not ready:
        print("\nPreflight failed. Nothing was dialed.")
        return 1

    if not args.execute:
        if not ready:
            print("\n(Preflight gaps above are fine for a dry run, but must be")
            print(" resolved before --execute will dial.)")
        print("\nDRY RUN - nothing dialed. Re-run with --execute to place the call.")
        print("\nTask that would be sent:\n")
        print(TASK.format(phone=args.to))
        print("\nresult_schema:\n")
        print(json.dumps(RESULT_SCHEMA, indent=2))
        return 0

    from calle import CalleClient

    client = CalleClient(api_key=os.environ["CALLE_API_KEY"])

    spent = budget.reserve("SMOKE-TEST", args.to, note="hello_call.py")
    print(f"\nDialing {args.to} ... (live call {spent} of {budget.ceiling})")
    print("This blocks until the call reaches a terminal state.\n")

    started = datetime.now(timezone.utc)
    call = client.calls.create_and_wait(
        task=TASK.format(phone=args.to),
        recipients=[{"phones": [args.to], "region": "US", "locale": "en-US"}],
        result_schema=RESULT_SCHEMA,
        metadata={"app": "dischargepulse", "purpose": "smoke-test"},
    )
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    _report(call)
    print(f"\n  wall clock: {elapsed:.1f}s")
    print(f"  budget    : {budget.summary()}")

    if args.save:
        payload = call if isinstance(call, dict) else getattr(call, "__dict__", str(call))
        Path(args.save).write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        print(f"  saved     : {args.save}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
