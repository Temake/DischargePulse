"""Run the placement loop end to end and print the cognitive cycle.

    cd backend
    python scripts/run_placement.py --case 10482                    # cassettes, free
    python scripts/run_placement.py --case 10482 --live SNF-001     # hybrid
    python scripts/run_placement.py --case 10482 --mode live        # all live

Replay mode costs nothing, so use it freely. Live mode spends call budget and
refuses to start if the run could exceed what remains.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.llm import build_llm_components  # noqa: E402
from app.agent.placement_agent import PlacementAgent  # noqa: E402
from app.agent.tools.budget import budget  # noqa: E402
from app.agent.tools.factory import build_actuator  # noqa: E402
from app.config import TelephonyMode, settings  # noqa: E402
from app.data.synthetic_data import get_facility, get_patient  # noqa: E402
from app.services.referral_service import write_referral_packet  # noqa: E402
from app.models.schemas import AgentEvent, AgentPhase, RunStatus  # noqa: E402

PHASE_GLYPH = {
    AgentPhase.PLAN: "PLAN     ",
    AgentPhase.ACT: "ACT      ",
    AgentPhase.OBSERVE: "OBSERVE  ",
    AgentPhase.REASON: "REASON   ",
    AgentPhase.REPLAN: "RE-PLAN  ",
    AgentPhase.AWAITING_APPROVAL: "APPROVAL ",
    AgentPhase.COMPLETE: "COMPLETE ",
}


def render(event: AgentEvent) -> None:
    glyph = PHASE_GLYPH.get(event.phase, event.phase.value.upper())
    print(f"  [{event.cycle}] {glyph} {event.message}")

    mode = event.payload.get("mode")
    if mode:
        call_id = event.payload.get("call_id") or "-"
        duration = event.payload.get("duration_seconds")
        stamp = f"{duration:.0f}s" if duration else "-"
        print(f"            provenance: {mode.upper()}  {call_id}  {stamp}")
        if event.payload.get("answers_source") == "simulated":
            print("            answers   : SIMULATED - not said on the call")

    for contradiction in event.payload.get("contradictions", []) or []:
        print(f"            !! CONTRADICTION: {contradiction['label']}")
        print(f"               directory : {contradiction['directory_says']}")
        said_by = "simulated" if event.payload.get("answers_source") == "simulated" else "live call"
        print(f"               {said_by:<9} : {contradiction['call_says']}")
        if contradiction.get("quote"):
            print(f"               quote     : \"{contradiction['quote']}\"")


async def main_async(args: argparse.Namespace) -> int:
    patient = get_patient(args.case)

    print("=" * 72)
    print(f"  DischargePulse - {patient.display_name}")
    print("=" * 72)
    print(f"  payer      : {patient.payer_plan}")
    print(f"  radius     : {patient.search_radius_miles} mi (max {patient.max_radius_miles})")
    print(f"  hard reqs  : {', '.join(r.label for r in patient.hard_requirements())}")
    print(f"  budget     : {budget.summary()}")

    mode = TelephonyMode(args.mode) if args.mode else None
    actuator = build_actuator(
        mode=mode,
        live_facility_ids=args.live,
        replay_latency_seconds=args.latency,
    )
    print(f"  telephony  : {actuator.mode_label}")
    if args.live:
        print(f"  live legs  : {', '.join(args.live)}")
    print("-" * 72)

    if args.no_llm:
        settings.llm_review_enabled = False
    reviewer, briefer = build_llm_components()
    print(f"  llm review : {'on (' + settings.llm_model + ')' if reviewer else 'off'}")

    agent = PlacementAgent(
        actuator,
        event_sink=render,
        max_cycles=args.max_cycles,
        max_calls=args.max_calls,
        reviewer=reviewer,
        briefer=briefer,
    )
    run = await agent.run(patient)

    print("-" * 72)
    print(f"  status       : {run.status.value}")
    print(f"  cycles       : {run.cycles_used}")
    print(f"  facilities   : {run.calls_placed} checked")
    print(f"  live calls   : {run.live_calls} (real CALL-E calls, credit spent)")

    if run.contradictions:
        print(f"  contradictions detected: {len(run.contradictions)}")

    if run.status is RunStatus.AWAITING_APPROVAL and run.proposal:
        p = run.proposal
        print()
        print("  PROPOSED PLACEMENT (awaiting case manager approval)")
        print(f"    facility    : {p.facility_name}")
        print(f"    match score : {p.match_score}")
        print(f"    coordinator : {p.evaluation.coordinator_name or '-'}")
        print(f"    fax         : {p.evaluation.fax_number or '-'}")
        print()
        print(f"  CASE MANAGER BRIEF ({p.brief_source}{', ' + p.brief_model if p.brief_model else ''})")
        for line in (p.brief or "").splitlines():
            print(f"    {line}")
        if args.packet:
            path = write_referral_packet(
                run_id="cli-run",
                telephony=actuator.mode_label,
                run=run,
                patient=patient,
                facility=get_facility(p.facility_id),
                path=Path(args.packet),
            )
            print()
            print(f"  referral packet (DRAFT): {path}")
        print()
        print("    Nothing has been sent. A case manager must approve the")
        print("    referral packet before it leaves this system.")
    else:
        print()
        print("  No verified match. Full call record escalated to the case manager.")

    print("=" * 72)
    print(f"  {budget.summary()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="10482")
    parser.add_argument(
        "--mode",
        choices=[m.value for m in TelephonyMode],
        help="Telephony mode. Defaults to TELEPHONY_MODE from .env.",
    )
    parser.add_argument(
        "--live",
        action="append",
        help="Facility id to dial live while everything else replays. Repeatable.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the Claude transcript review and use the template brief.",
    )
    parser.add_argument(
        "--packet",
        metavar="PATH",
        help="Write the draft referral packet PDF here when a placement is proposed.",
    )
    parser.add_argument("--max-cycles", type=int, default=4)
    parser.add_argument(
        "--max-calls",
        type=int,
        help="Ceiling on calls for this run, on top of the account budget.",
    )
    parser.add_argument(
        "--latency",
        type=float,
        default=0.0,
        help="Simulated per-call delay in replay mode, for demo pacing.",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
