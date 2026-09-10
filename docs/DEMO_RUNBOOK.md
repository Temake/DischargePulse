# DischargePulse Demo Runbook

How to produce the submission video without burning the live call budget or
faking anything.

---

## 1. Why role-played receivers

The agent calls **numbers you own, answered by people who agreed to play an
admissions coordinator**. It never calls a real nursing facility.

That is not a workaround, it is the correct choice: pointing an autonomous
calling agent at real clinical staff with a fabricated patient would waste their
time under false pretenses. Say this out loud in the video — it reads as domain
seriousness, and it pre-empts the obvious judging question.

Everything else is real: real CALL-E calls, real telephony, real transcripts,
real structured extraction, real agent re-planning.

---

## 2. Call budget

The hackathon grants 20 free calls. The ledger in
[`budget.py`](../backend/app/agent/tools/budget.py) enforces a hard ceiling
before every dial, so a runaway re-plan loop cannot drain it.

| Purpose | Calls | When |
| --- | --- | --- |
| Connectivity smoke test (`hello_call.py`) | 2 | Day 1 |
| Cassette recording, first pass | 4 | Day 2 |
| Cassette re-records after prompt tuning | 4 | Day 3 |
| Dress rehearsal (full sweep) | 4 | Day 3 |
| Final recording take | 4 | Day 4 |
| Reserve | 2 | — |

**Never develop against live calls.** Record cassettes once, then run the loop
against them as many times as you like for free:

```bash
python scripts/record_cassettes.py --case 10482 --execute   # spends budget
TELEPHONY_MODE=replay python -m uvicorn app.main:app        # free, forever
```

Check remaining budget at any time:

```bash
python -c "from app.agent.tools.budget import budget; print(budget.summary())"
```

Request additional credit from the organisers **early** — approval has human
latency, and you want headroom to exist before you need it.

---

## 3. Receiver setup

You need two phones answered by two people (or one person answering twice).

| Slot | `.env` variable | Plays |
| --- | --- | --- |
| Primary | `DEMO_PHONE_PRIMARY` | Bayview Post-Acute Center (SNF-001) **and** Bayview Peninsula Campus (SNF-004) |
| Secondary | `DEMO_PHONE_SECONDARY` | Golden Gate Skilled Nursing (SNF-002) |

Facilities without a number attached (SNF-003, 005, 006) stay on cassettes or
return `UNREACHED`. They exist to make the radius expansion meaningful.

---

## 4. Role-play scripts

Answer naturally. Do not read these verbatim — the point is that CALL-E adapts to
a real conversation. Improvise, deflect once, make the agent work for it.

### SNF-001 — Bayview Post-Acute Center *(the contradiction)*

**Outcome: disqualified on wound VAC, offers a sister facility.**

> **Open as a receptionist.** "Bayview Post-Acute, how can I help you?"
> Make the agent ask for admissions before transferring. Pause, then come back
> as **Dana, admissions coordinator**.

Answer as follows:

| Asked about | Say |
| --- | --- |
| Payer | "Yes, we're in network for Aetna Medicare Advantage." |
| Bed | "We do have a female bed opening up — we could take an admission tomorrow." |
| IV ceftriaxone | "That's fine, we do daily IV antibiotics routinely." |
| **Wound VAC** | "Ah — here's the problem. Our wound care nurse is out this week, and the nurse on nights isn't signed off on the VAC yet. I can't take a VAC patient until she's back Monday." |
| Sister facility | "You could try our Peninsula campus in San Mateo, they have a wound nurse on staff." |
| Fax | "Sure, it's 555-0142." |
| Name | "Dana." |

**Why this leg matters:** the directory record for SNF-001 claims wound VAC is
available. This call contradicts it. That contradiction is the single most
important moment in the video — it is the thing a directory lookup cannot do and
a phone call can.

### SNF-002 — Golden Gate Skilled Nursing *(payer mismatch)*

**Outcome: disqualified on network.**

> "We're not contracted with Aetna Medicare Advantage — we're Kaiser and
> straight Medicare only."

If pressed on anything else, stay vague: "I'd have to check, but honestly if
you're Aetna it won't work here." Short call. This shows the agent pruning on a
hard constraint without wasting time.

### SNF-004 — Bayview Peninsula Campus *(the match)*

**Outcome: verified match.**

This is the call the agent places **because** SNF-001 named it. Answer yes to
everything, warmly and specifically:

| Asked about | Say |
| --- | --- |
| Payer | "Yes, same contract as our Bayview campus — Aetna Advantage is fine." |
| Bed | "We have a female bed on the rehab wing, we could admit tomorrow morning." |
| Wound VAC | "Yes — we have two nurses certified on negative pressure, one on days and one on nights." |
| IV ceftriaxone | "No problem, daily IV is routine here." |
| Fax | "555-0198, mark it attention admissions." |
| Name | "Marcus." |

---

## 5. Recording sequence

1. **Reset state** so the demo starts clean:
   ```bash
   rm -f backend/.call_budget.json     # only if you want the counter reset
   ```
2. **Start the backend and console**, with the hybrid actuator configured so
   SNF-001, SNF-002 and SNF-004 dial live and everything else replays.
3. **Get your role-players on the phones** and confirm they have their scripts.
4. **Record in one take.** The narrative writes itself:
   - Plan: 3 facilities inside 15 miles
   - Act: parallel calls go out, phones physically ring on camera
   - Observe: transcripts stream in
   - Reason: Golden Gate pruned on payer; Bayview contradicts its own directory
     record on wound VAC
   - Re-plan: sister facility queued, Peninsula called
   - Match verified → **stop at the approval gate**
5. **End on the human gate.** Do not click approve immediately — say the line:
   *"The agent found the bed. It does not get to send the referral. That's the
   case manager's call."* Then click.

---

## 6. Shot list for provenance

Judges must be able to see that calls were real. Show, don't assert:

- A phone physically ringing, on camera, as the agent dials.
- The `LIVE` badge and CALL-E `call_id` on the call card.
- The transcript filling in with turn timestamps.
- A terminal tail of the budget ledger incrementing.

The CALL-E dashboard's Call Records page matched by `provider_call_id` is the
strongest single piece of evidence — a two-second cut to it is worth more than
any amount of narration.

---

## 7. Fallback if a live call fails on the day

Cassettes are recorded real calls, so the fallback is not a fabrication. If a
leg fails mid-take:

- Cassette-backed legs render a `REPLAY` badge — leave it visible, do not hide it.
- Mention it in the video: *"this leg is a recorded call being replayed."*

Never present a replayed call as live. The badge exists so you never have to.
