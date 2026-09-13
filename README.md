# DischargePulse: Autonomous Post-Acute Placement Agent

> **CALL-E Hackathon Submission** — *Your Code Is Calling*

DischargePulse is an autonomous agentic healthcare operations system that
eliminates the post-acute discharge bottleneck. It replaces 3–5 hours of manual
phone tag with a closed-loop `Plan → Act → Observe → Reason → Re-Plan` cycle,
using CALL-E as a goal-driven telephone actuator.

---

## 🌟 Key Highlights

* **Autonomous Telephony Actuator:** CALL-E is a first-class agent tool conducting goal-driven, adaptive calls with post-acute admissions departments, returning typed JSON rather than a transcript to parse.
* **Closed-Loop Cognitive Cycle:** Continuous `Plan → Act → Observe → Reason → Re-Plan` with radius expansion, sister-facility queueing, and early stopping.
* **Hard Constraints vs. Soft Preferences:** Mandatory care requirements (Wound VAC, IV infusion, payer network, staffed bed) evaluated separately from optimisation preferences (distance, CMS rating).
* **Contradiction Detection:** Flags when what a facility says contradicts stale directory data — *"Directory says Wound VAC available; the facility says the night nurse isn't signed off."*
* **Bounded LLM Review:** Claude reads what the facility actually said and flags caveats the yes/no answers miss. It can only make a finding **more cautious**, and only by quoting the facility **verbatim** — it can never confirm a requirement or approve a placement.
* **Human-in-the-Loop Governance:** The agent searches, calls, reasons and drafts a referral packet PDF with a plain-language brief. It never sends a referral or dispatches transport without a case manager's explicit approval.
* **Provenance on Everything:** Every answer is labelled with how it was obtained — live call, replay, simulated, or scripted — in the console, the event stream, and the referral packet.
* **Audit-Ready Prototype:** Operates entirely on synthetic, de-identified data (Synthetic Patient #10482).

---

## 🔌 How CALL-E is used

One `TelephonyActuator` interface, injected at the edge. The planner, reasoning
engine, scoring and UI are identical in every mode — there is no demo-only code
path above the actuator seam.

| Mode | Calls placed | Where the facility's answers come from |
| --- | --- | --- |
| `live` | Real CALL-E calls | Extracted from the call |
| `replay` | None | A *recorded real call*, replayed free and deterministically |
| `simulated` | **Real CALL-E calls** (real call id, real credit) | A labelled test scenario, used **only** when the call itself gave no usable answers |
| `scripted` | None | A labelled test scenario — free, for rehearsals |

Requirements are turned into a CALL-E `result_schema` at runtime, so CALL-E
returns typed JSON (`wound_vac: "yes" | "no" | "unknown"`).

Every observation carries two independent labels: `mode` (`LIVE` / `REPLAY` /
`SCRIPTED`) and `answers_source` (`call` / `simulated`). A live call with
simulated answers shows **both**. Answers genuinely extracted from a call are
never overwritten, nothing is simulated on top of a call that never connected,
and what the call really extracted is kept alongside for audit.

### Why simulated mode exists

The demo cannot call real nursing facilities with a fabricated patient. The
facility side is a stand-in: a CALL-E Inbound Goal configured to answer as an
admissions coordinator from a fixed script (see
[`docs/INBOUND_GOAL_SETUP.md`](./docs/INBOUND_GOAL_SETUP.md)), or CALL-E's
official US testing hotline provided by the hackathon organisers.

At the time of submission the stand-in line answers live calls with no audio —
a platform issue reported to the organisers — so it returns no usable answers.
Simulated mode keeps the calls real while supplying the attendant's answers from
the same script the stand-in line was configured with, and labels every one of
them. Nothing is presented as having been said on a call when it was not.

---

## 🧠 LLM transcript review and brief

The rules read CALL-E's yes / no / unknown answers. They cannot read a caveat:
*"yes, we take wound VACs, but not until Thursday"* extracts as `yes`. After each
call, Claude reviews the facility's own words and may flag a finding. Code — not
the model — decides whether a flag is applied. It must:

1. name one of the patient's hard requirements,
2. move the finding to a **more cautious** state — never towards confirmed,
3. quote the facility **verbatim** (no paraphrase, and never the hospital's own caller).

Rejected flags are kept and shown with the reason. Simulated answers are reviewed
only against the simulated statements, never against a transcript that did not
produce them.

At the approval gate Claude also writes a short plain-language brief for the
case manager. The provenance line at its top — including whether answers were
simulated — is written by code, not the model.

Both are optional. Without `ANTHROPIC_API_KEY` the review is skipped and
announced as unavailable, the rule-based agent runs unchanged, and the brief is
assembled from a template.

---

## 📚 Documentation

* [`ARCHITECTURE.md`](./ARCHITECTURE.md) — system architecture, components, data schemas.
* [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) — engineering plan and verification strategy.
* [`docs/INBOUND_GOAL_SETUP.md`](./docs/INBOUND_GOAL_SETUP.md) — configuring the stand-in facility line.
* [`docs/DEMO_RUNBOOK.md`](./docs/DEMO_RUNBOOK.md) — call budget and recording sequence.

---

## 🚀 Quickstart

### Prerequisites
* Python 3.10+ (tested on 3.14)
* Node.js 18+
* A CALL-E API key from the [CALL-E dashboard](https://docs.heycall-e.com/authentication) — only needed for `live` or `simulated` runs
* Optionally, an Anthropic API key for the LLM transcript review and brief

### 1. Configure

```bash
cp .env.example .env
```

Set `CALLE_API_KEY` and, optionally, `ANTHROPIC_API_KEY`. Leave
`TELEPHONY_MODE=replay` until you are ready to spend call credit.

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install --only-binary=:all: -r requirements.txt
```

> Install with `--only-binary=:all:`. On Python 3.13+, older pins fall back to
> building `pydantic-core` from source, which needs a Rust toolchain.

### 3. Try it without spending anything

```bash
python scripts/run_placement.py --case 10482 --mode scripted --packet packet.pdf
```

Runs the full agent loop — contradiction, sister-facility re-plan, verified
match, human gate — with no calls placed, and writes the draft referral packet.
Every answer is labelled as scripted and simulated.

### 4. Verify CALL-E connectivity

```bash
python scripts/hello_call.py --to +1XXXXXXXXXX             # dry run, free
python scripts/hello_call.py --to +1XXXXXXXXXX --execute   # spends 1 call
```

Dial only a phone you own or are authorised to call.

### 5. Real calls

```bash
python scripts/run_placement.py --case 10482 --mode simulated --packet packet.pdf
```

Places real CALL-E calls to the configured stand-in line and records them as
cassettes, so later runs can replay them for free with `--mode replay`.

### 6. Tests

```bash
python -m pytest tests/ -q
```

The suite never places a call and never reaches the Claude API.

### 7. API server

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
| `GET` | `/api/runs/{run_id}/packet` | Referral packet PDF: drafted at the gate, re-stamped on decision |
| `POST` | `/api/runs/{run_id}/approve` · `/decline` | The human-in-the-loop gate |
| `WS` | `/ws/runs/{run_id}` | Live event stream for one run |

The WebSocket sends `hello` on connect, replays every `event` the client
missed, then streams live ones, and sends a full `run` snapshot on each state
change. It closes once the run is terminal; a run awaiting approval stays open
so the case manager's decision arrives live.

Runs that place calls (`live`, `hybrid`, `simulated`) are guarded server-side:
they must set `max_calls`, may not exceed the remaining budget, hybrid live legs
must have a demo line, only one may be in flight, and a request for real calls
is refused — never silently replayed or scripted — when CALL-E credentials are
missing.

---

## 🔒 Safety & data policy

* **Synthetic data only.** No real patient or facility appears in this repository. Sample phone numbers are fictional.
* **Stand-in facility lines.** Demo calls go to a CALL-E Inbound Goal the developers configured, or CALL-E's official testing hotline — never to real clinical staff.
* **Honest provenance.** Simulated and scripted answers are labelled wherever they appear, and the wording never claims a call established something it did not.
* **De-identified on the call.** The voice agent refers to "a 71-year-old female patient" and is instructed to neither state nor accept a name, DOB, or MRN.
* **No autonomous commitments.** The call prompt forbids agreeing to or scheduling an admission; placement is a human decision.
* **Bounded model.** The LLM reviewer can only make findings more cautious, with a verbatim quote. It cannot confirm a requirement or approve a placement.
* **Budget ceiling.** Every live dial passes a persisted hard limit, so a runaway loop cannot drain call credit.

---

## ⚠️ Known limitations

* **Stand-in line audio.** The configured facility stand-in currently answers with no audio, so real-call demos use simulated attendant answers (labelled).
* **No referral transmission.** The referral packet is generated and downloadable, but e-fax dispatch and transport coordination are not implemented. The packet says so.
* **In-memory runs.** Run history lives in memory; restarting the backend clears it. Recorded cassettes and generated packets persist on disk.
