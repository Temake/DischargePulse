"""Record facility cassettes from real CALL-E calls.

This is what makes the replay path honest: the fallback used in development,
tests, and the wider fan-out of the demo is a genuine recorded call, not
hand-written dialogue.

    cd backend
    python scripts/record_cassettes.py --case 10482                     # dry run
    python scripts/record_cassettes.py --case 10482 --facility SNF-001 --execute

Each --execute run spends one live call per facility. Only facilities with a
demo receiver number attached (DEMO_PHONE_PRIMARY / DEMO_PHONE_SECONDARY) can be
recorded; the rest are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.tools import cassette  # noqa: E402
from app.agent.tools.budget import budget  # noqa: E402
from app.agent.tools.calle_actuator import CalleActuator, TelephonyConfigError  # noqa: E402
from app.agent.tools.telephony import build_result_schema, build_task_prompt  # noqa: E402
from app.data.synthetic_data import (  # noqa: E402
    FACILITIES,
    PLACEHOLDER_PHONE,
    get_facility,
    get_patient,
)
from app.models.schemas import mask_phone  # noqa: E402


async def record_one(actuator: CalleActuator, patient, facility) -> None:
    print(f"\n--- {facility.name} ({facility.facility_id}) -> {mask_phone(facility.phone)}")
    observation = await actuator.call_facility(
        facility,
        patient,
        objective=build_task_prompt(patient, facility),
        result_schema=build_result_schema(patient),
    )

    print(f"    outcome    : {observation.outcome.value}")
    print(f"    call_id    : {observation.call_id}")
    print(f"    duration   : {observation.duration_seconds}s")
    print(f"    structured : {observation.structured_result}")

    if observation.is_usable:
        path = cassette.cassette_path(patient.case_id, facility.facility_id)
        print(f"    cassette   : {path.name}")
    else:
        print(f"    NOT RECORDED: {observation.failure_message or 'no structured result'}")


async def main_async(args: argparse.Namespace) -> int:
    patient = get_patient(args.case)

    if args.facility:
        targets = [get_facility(fid) for fid in args.facility]
    else:
        targets = list(FACILITIES)

    dialable = [f for f in targets if f.phone != PLACEHOLDER_PHONE]
    skipped = [f for f in targets if f.phone == PLACEHOLDER_PHONE]

    print("=" * 68)
    print(f"  Cassette recording - {patient.display_name}")
    print("=" * 68)
    print(f"  budget    : {budget.summary()}")
    print(f"  to record : {len(dialable)} facility call(s)")
    for f in dialable:
        existing = cassette.cassette_path(patient.case_id, f.facility_id)
        mark = "overwrite" if existing.exists() else "new"
        print(f"      - {f.facility_id:<8} {f.name:<42} {mask_phone(f.phone)}  [{mark}]")
    if skipped:
        print(f"  skipped   : {len(skipped)} without a demo receiver number")
        for f in skipped:
            print(f"      - {f.facility_id:<8} {f.name}")
    print("-" * 68)

    if not args.execute:
        print("\nDRY RUN - nothing dialed. Re-run with --execute to record.")
        print("\nTask prompt for the first target:\n")
        if dialable:
            print(build_task_prompt(patient, dialable[0]))
        return 0

    if not dialable:
        print("\nNothing to record. Set DEMO_PHONE_PRIMARY / DEMO_PHONE_SECONDARY.")
        return 1

    if len(dialable) > budget.remaining:
        print(
            f"\nRefusing to start: {len(dialable)} calls requested but only "
            f"{budget.remaining} left in budget."
        )
        return 1

    try:
        actuator = CalleActuator()
    except TelephonyConfigError as exc:
        print(f"\n{exc}")
        return 1

    # Recorded one at a time on purpose: a human is role-playing the receiving
    # end and can only answer one phone at once.
    for facility in dialable:
        await record_one(actuator, patient, facility)

    print(f"\n{budget.summary()}")
    print(f"Cassettes on disk: {len(cassette.available())}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="10482", help="Synthetic case id")
    parser.add_argument(
        "--facility",
        action="append",
        help="Facility id to record. Repeatable. Defaults to all dialable.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually place the calls. Without this flag nothing is dialed.",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
