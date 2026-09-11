# DischargePulse: Autonomous Post-Acute Placement Agent

> **CALL-E Hackathon Submission** — *Your Code Is Calling*

DischargePulse is an autonomous agentic healthcare operations system that
eliminates the post-acute discharge bottleneck. It replaces 3–5 hours of manual
phone tag with a closed-loop `Plan → Act → Observe → Reason → Re-Plan` cycle,
using CALL-E as a goal-driven telephone actuator.

---

## 🌟 Key Highlights

* **Autonomous Telephony Actuator:** CALL-E is a first-class agent tool conducting goal-driven, adaptive calls with post-acute admissions departments.
* **Closed-Loop Cognitive Cycle:** Continuous `Plan → Act → Observe → Reason → Re-Plan` with radius expansion, sister-facility queueing, and early stopping.
* **Hard Constraints vs. Soft Preferences:** Mandatory care requirements (Wound VAC, IV infusion, payer network, staffed bed) evaluated separately from optimisation preferences (distance, CMS rating).
* **Contradiction Detection:** Flags when live phone intelligence contradicts stale directory data — *"Directory says Wound VAC available; live call confirms the night nurse lacks certification."*
* **Human-in-the-Loop Governance:** The agent searches, calls, reasons and drafts. It never dispatches a referral or transport without a case manager's explicit approval.
* **Audit-Ready Prototype:** Operates entirely on synthetic, de-identified data (Synthetic Patient #10482).

---

## 🔌 How CALL-E is used

One `TelephonyActuator` interface, two implementations, injected at the edge:

| Implementation | Behaviour |
| --- | --- |
| `CalleActuator` | Real outbound calls via the CALL-E Calls API |
| `ReplayActuator` | Replays *recorded real calls* from cassettes — free and deterministic |

Planner, reasoning engine, scoring and UI are identical in both modes. There is
no demo-only code path anywhere above the actuator seam, and every observation is
stamped `LIVE` or `REPLAY` with its CALL-E `call_id` so provenance is visible in
the UI and auditable after the fact.

Requirements are turned into a CALL-E `result_schema` at runtime, so CALL-E
returns typed JSON (`wound_vac: "yes" | "no" | "unknown"`) rather than a
transcript the app has to parse.

---

## 📚 Documentation

* [`ARCHITECTURE.md`](./ARCHITECTURE.md) — system architecture, components, data schemas.
* [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) — engineering plan and verification strategy.
* [`docs/DEMO_RUNBOOK.md`](./docs/DEMO_RUNBOOK.md) — call budget, role-play scripts, recording sequence.

---

## 🚀 Quickstart

### Prerequisites
* Python 3.10+ (tested on 3.14)
* Node.js 18+
* A CALL-E API key from the [CALL-E dashboard](https://docs.heycall-e.com/authentication)

### 1. Configure

```bash
cp .env.example .env
```

Set `CALLE_API_KEY`. Leave `TELEPHONY_MODE=replay` until you are ready to spend
call credit.

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install --only-binary=:all: -r requirements.txt
```

> Install with `--only-binary=:all:`. On Python 3.13+, older pins fall back to
> building `pydantic-core` from source, which needs a Rust toolchain.

### 3. Verify CALL-E connectivity

Before anything else, confirm a real call works end to end:

```bash
python scripts/hello_call.py --to +1XXXXXXXXXX             # dry run, free
python scripts/hello_call.py --to +1XXXXXXXXXX --execute   # spends 1 call
```

Dial only a phone you own or are authorised to call.

### 4. Record cassettes

Turn real calls into a free, deterministic replay set:

```bash
python scripts/record_cassettes.py --case 10482 --execute
```

### 5. Tests

```bash
python -m pytest tests/ -q
```

### 6. API server

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Interactive docs at `http://localhost:8000/docs`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Telephony mode, live availability, budget, cassette count |
| `GET` | `/api/budget` | Live call budget: spent / ceiling / remaining |
| `GET` | `/api/patients` · `/api/patients/{case_id}` | Synthetic discharge cases |
| `GET` | `/api/facilities` | Facility directory, nearest first, with a `dialable` flag |
| `POST` | `/api/runs` | Start a placement run in the background (202) |
| `GET` | `/api/runs` · `/api/runs/{run_id}` | Run summaries · full live snapshot |
| `POST` | `/api/runs/{run_id}/approve` · `/decline` | The human-in-the-loop gate |
| `WS` | `/ws/runs/{run_id}` | Live event stream for one run |

The WebSocket sends `hello` on connect, replays every `event` the client
missed, then streams live ones, and sends a full `run` snapshot on each state
change. It closes once the run is terminal; a run awaiting approval stays open
so the case manager's decision arrives live.

Live runs are guarded server-side: all-live runs must set `max_calls`, no run may
exceed the remaining budget, hybrid live legs must have a demo receiver, only one
live run may be in flight, and a live request is refused — never silently
replayed — when CALL-E credentials are missing.

---

## 🔒 Safety & data policy

* **Synthetic data only.** No real patient, facility, or phone number appears in this repository.
* **Role-played receivers.** Demo calls go to numbers the developers own, answered by people who agreed to play an admissions coordinator. The agent is never pointed at real clinical staff.
* **De-identified on the call.** The voice agent refers to "a 71-year-old female patient" and is instructed to neither state nor accept a name, DOB, or MRN.
* **No autonomous commitments.** The call prompt forbids agreeing to or scheduling an admission; placement is a human decision.
* **Budget ceiling.** Every live dial passes a persisted hard limit, so a runaway loop cannot drain call credit.
