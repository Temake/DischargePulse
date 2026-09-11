# DischargePulse: System Architecture & Agent Design

DischargePulse is an autonomous, agentic healthcare operations platform that eliminates the post-acute discharge bottleneck through a closed-loop `Plan → Act → Observe → Reason → Re-Plan` cognitive cycle.

---

## 1. High-Level Architectural Diagram

```
                               DISCHARGEPULSE ARCHITECTURE
                               ───────────────────────────

 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                      FRONTEND: Case Manager Command Console (React + Vite)             │
 │  - Clinical Requirements Panel (Wound VAC, IV, Payer) - Live Waveform & Audio Player   │
 │  - Real-Time Dynamic Bed Availability Matrix         - 1-Click Packet E-Fax Dispatch   │
 │  - Agent Cognitive Loop Visualizer (Plan/Act/Reason)  - Contradiction Detection Banners │
 └───────────────────────────────────────────┬────────────────────────────────────────────┘
                                             │ HTTP REST / WebSocket (Live Events)
                                             ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                      BACKEND: FASTAPI + PYTHON AGENT CORE                              │
 │                                                                                        │
 │   ┌────────────────────────────────────────────────────────────────────────────────┐   │
 │   │                 POST-ACUTE PLACEMENT AGENT (`placement_agent.py`)              │   │
 │   │  - Owns placement goal & executes closed-loop lifecycle                        │   │
 │   │  - Concurrency management (`MAX_CONCURRENT_CALLS = 6`)                         │   │
 │   │  - Re-planning: Radius expansion, sister facility queueing, early stopping     │   │
 │   └───────┬──────────────────────▲──────────────────────────▲──────────────────────┘   │
 │           │                      │                          │                          │
 │           ▼                      │                          │                          │
 │   ┌──────────────────┐   ┌───────┴──────────────┐   ┌───────┴──────────────────────┐   │
 │   │ 1. Discharge Req │   │ 2. CALL-E Telephony  │   │ 3. Placement Reasoning &     │   │
 │   │    & Placement   │   │    Actuator Tool     │   │    Verification Engine       │   │
 │   │    Strategy      │   │    (`calle_tool.py`) │   │    - Hard/Soft verification  │   │
 │   │    Planner       │   │    - Goal prompts    │   │    - Contradiction detection │   │
 │   │    - Hard vs Soft│   │    - Fallback queries│   │    - Placement Match Score   │   │
 │   │    - Target queue│   │    - Live / Mock mode│   │    - Sister facility extractor│  │
 │   └──────────────────┘   └──────────────────────┘   └──────────────────────────────┘   │
 │                                                                                        │
 │   ┌────────────────────────────────────────────────────────────────────────────────┐   │
 │   │               DOWNSTREAM SERVICES (Triggered upon Human Approval)              │   │
 │   │  - Referral Packet PDF Compiler (De-identified clinical face-sheet)            │   │
 │   │  - Secure E-Fax Dispatch Simulator                                             │   │
 │   │  - Non-consequential Transport Coordination Request Draft                      │   │
 │   └────────────────────────────────────────────────────────────────────────────────┘   │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Agentic Loop: `Plan → Act → Observe → Reason → Re-Plan`

```
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                         THE CLOSED-LOOP RE-PLANNING CYCLE                              │
 │                                                                                        │
 │     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
 │  1. │ PLAN         │──▶2.│ ACT          │──▶3.│ OBSERVE      │──▶4.│ REASON       │──┐ │
 │     │ (Filter &    │     │ (CALL-E Goal │     │ (Extract     │     │ (Hard/Soft   │  │ │
 │     │  Prioritize) │     │  Sweep)      │     │  Transcripts)│     │  Audit)      │  │ │
 │     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘  │ │
 │            ▲                                                              │          │ │
 │            │                                                              ▼          │ │
 │            └────────────────────── 5. RE-PLAN / DECIDE ◀──────────────────┘          │ │
 │                   ├── MATCH VERIFIED ──────▶ CASE MANAGER HUMAN APPROVAL             │ │
 │                   ├── SISTER FACILITY ─────▶ QUEUE SISTER FACILITY & CALL            │ │
 │                   ├── NO BEDS IN RADIUS ───▶ EXPAND RADIUS (15mi ➔ 30mi)             │ │
 │                   └── PAYER MISMATCH ──────▶ PRUNE NETWORK & RE-FILTER               │ │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Deep Dive

### 3.1 Discharge Requirements & Placement Strategy Planner
- **Role:** Translates care team inputs into an operational search strategy.
- **Constraints Breakdown:**
  - **Hard Constraints (Must Pass):**
    - Patient Payer Network Match (e.g., Aetna Medicare Advantage PPO)
    - Immediate Staffed Bed Availability (Male/Female room match)
    - Wound VAC Therapy certified nurses on staff
    - IV Infusion capabilities (e.g., IV Ceftriaxone Q24H)
    - Contact Isolation capability (if required)
    - Bariatric equipment capacity (>350 lbs)
  - **Soft Preferences (Optimization):**
    - Geographic proximity (e.g., within 15 miles of family zip code)
    - CMS Quality Star Rating (4+ stars preferred)
    - In-network preferred partner tier
    - Direct coordinator availability

---

### 3.2 CALL-E Telephony Actuator Tool
- **Role:** Autonomous telephony actuator invoking real-time, goal-driven phone conversations.
- **Tool Interface:**
  ```python
  class CalleActuatorTool:
      async def call_facility(
          self,
          facility_id: str,
          phone_number: str,
          objective: str,
          required_information: list[str],
          fallback_questions: list[str],
          conversation_boundaries: list[str]
      ) -> CallObservationResult:
          ...
  ```
- **Adaptive Dialogue Features:**
  - Dynamically navigates IVR phone menus ("Press 2 for Admissions").
  - Identifies on-duty Admissions Coordinator by name and gets direct fax/email.
  - Recovers gracefully from initial receptionist deflections.
  - Supports dual execution: Live CALL-E telephony API and deterministic mock mode for seamless hackathon recording.

---

### 3.3 Placement Reasoning & Verification Engine
- **Role:** Evaluates call observations against care team requirements.
- **Verification States:**
  - `✓ CONFIRMED`: Verified explicitly by facility admissions staff.
  - `⚠ NOT CONFIRMED`: Ambiguous or unverified on call.
  - `✕ EXPLICITLY UNAVAILABLE`: Facility stated lack of capacity or capability.
  - `? UNKNOWN`: Not yet evaluated.
- **Contradiction Detection Engine:**
  - Evaluates static directory baseline vs. live phone intelligence.
  - *Example:* Directory says *"Wound VAC: Yes"*, but Live Call reveals *"Night nurse lacks wound VAC sign-off tonight"*.
  - System flags: `⚠ LIVE INFORMATION OVERRIDES STALE DIRECTORY DATA` and disqualifies the candidate.
- **Placement Match Score (0–100):** Weighted multi-criteria calculation based strictly on confirmed criteria and distance/rating optimization.

---

### 3.4 Human-in-the-Loop (HITL) Safety Gate
- **Role:** Maintains strict clinical and legal governance.
- **Rules:**
  1. The agent autonomously searches, calls, reasons, verifies, and prepares documents.
  2. The agent **never** executes a transfer or dispatches transport without explicit Case Manager approval.
  3. Clicking **"Approve & E-Fax Packet"** transmits the de-identified synthetic clinical packet and locks the placement.

---

## 4. Synthetic Data & Compliance
- **Data Policy:** The platform strictly uses synthetic, de-identified patient records (e.g., Synthetic Patient #10482) and simulated facility numbers.
- **Classification:** Labeled as an **"Audit-ready prototype using synthetic healthcare data."**
