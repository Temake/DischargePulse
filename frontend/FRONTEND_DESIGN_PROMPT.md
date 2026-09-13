# DischargePulse Frontend Build Prompt
> Paste everything below into a fresh Claude Code session opened in `Temi/frontend`.
> This version intentionally prioritizes product design over visual effects. The existing landing page screenshots are the reference for what to improve: remove the repetitive "AI dashboard" look, reduce pills/bevels/monospace labels, and make the interface feel like a serious healthcare operations product.

---

## ROLE

You are a senior product designer and design engineer shipping the frontend for **DischargePulse**, an autonomous post-acute placement agent for the CALL-E hackathon.

You are not designing a futuristic AI website.

You are designing a **credible healthcare operations product** that happens to use an autonomous agent.

The finished product should feel:

- premium
- calm
- precise
- editorial
- operational
- trustworthy
- intentionally designed
- visually distinctive without being loud

A hospital operations director should immediately understand what the product does. A design-literate judge should remember the product because of its **clarity, composition and interaction design**, not because it has gradients, glowing borders, animated pills or a wall of dashboard cards.

### PRIMARY DESIGN DIRECTIVE

**Do not make this look like an AI-generated landing page.**

The current implementation has too many recognizable "AI design" signals:

- excessive rounded cards
- pill-shaped labels everywhere
- oversized hero typography with generic split-screen composition
- floating glass/bezel containers
- too much blue accent
- monospace eyebrows on almost every section
- dashboard screenshots presented as decorative hero art
- repeated card grids
- excessive borders
- decorative animation
- generic bento layouts
- "AI agent" visual language
- too many small status chips
- excessive use of uppercase micro-labels
- everything being placed inside a container
- visual hierarchy created mainly through borders and pills

**Actively remove these patterns.**

Use the product's actual workflow, data and contradiction story as the visual identity.

The strongest design idea is:

> **The agent does the phone work. The human owns the decision.**

The interface should feel like an operations tool, not an AI demo.

---

# STEP 0: INSPECT BEFORE BUILDING

Before writing or changing UI code:

1. Read:
   - `.agents/skills/design-taste-frontend/SKILL.md`
   - `.agents/skills/high-end-visual-design/SKILL.md`
   - `.claude/skills/ui-ux-pro-max/...` as available in the repository

2. Inspect the existing frontend and identify:
   - what already works
   - what is visually repetitive
   - which components can be reused
   - which sections should be redesigned rather than cosmetically restyled

3. Inspect the current landing page in a browser at:
   - 375px
   - 768px
   - 1024px
   - 1440px

4. Do not assume that following a design skill literally produces good design.
   Use the skills as constraints and references, then make independent design decisions.

5. If a 21st.dev component conflicts with the product's visual language, **do not use it**.

### IMPORTANT

21st.dev is a component library, not the design system.

Never assemble the page from a collection of visually unrelated 21st components.

If a component looks obviously like a copied demo after theming, rebuild that part natively.

Use 21st.dev for useful interaction primitives, not for visual identity.

---

# STEP 1: PRODUCT TRUTH

DischargePulse is an autonomous post-acute placement agent built for the CALL-E hackathon.

A hospital patient is ready for discharge but needs a skilled nursing facility. A case manager normally spends **3 to 5 hours per placement** checking:

- beds
- insurance
- clinical capabilities
- admissions availability
- phone menus
- receptionists
- coordinators
- stale directory information

DischargePulse runs the repetitive verification loop:

**Plan → Act → Observe → Reason → Re-Plan → Human Gate**

The agent:

1. filters facilities
2. ranks candidates
3. places outbound calls
4. receives structured results and transcripts
5. checks hard constraints separately from soft preferences
6. detects contradictions
7. replans when necessary
8. stops when it has a verified match
9. waits for a human decision

The agent **never sends a referral or books transport**.

The human gate is part of the product.

---

## Demo scenario

Patient `10482`:

- 71F
- Aetna Medicare Advantage PPO
- post hip arthroplasty
- wound VAC
- IV ceftriaxone
- family ZIP `94110`
- radius starts at 15 miles and can expand to 30

Facilities:

- `SNF-002` Golden Gate Skilled Nursing: eliminated because it is out of network
- `SNF-001` Bayview Post-Acute Center: directory says wound VAC available, but the call reveals the night nurse is not signed off
- `SNF-004` Bayview Peninsula Campus: called because SNF-001 names it as a sister campus; requirements are confirmed

The important product moment is:

> **The directory says one thing. The phone call says another. The agent catches the contradiction before the patient arrives.**

---

# STEP 2: HONESTY RULES

These are product rules, not optional copy guidance.

Never invent:

- customers
- hospital logos
- testimonials
- adoption numbers
- clinical validation
- HIPAA compliance
- certifications
- referrals sent
- fax transmissions
- fake recordings
- fake live audio
- fake call progress
- fake metrics

Allowed numbers:

- 3 to 5 hours
- 6 concurrent calls
- 20-call ceiling
- 15 → 30 miles
- 4 verification states
- 0 referrals sent without approval
- score 0 to 100
- values read from the API

All data is synthetic.

Use:

> **Audit-ready prototype using synthetic healthcare data.**

Calls must clearly say `LIVE` or `REPLAY`.

Replay means a recorded real role-play call, not fabricated UI activity.

---

# STEP 3: DESIGN DIRECTION

## The visual thesis

DischargePulse should look closer to:

**modern enterprise healthcare software + editorial information design + aviation/operations control**

and NOT:

**AI startup landing page + SaaS template + futuristic dashboard.**

Think:

- restrained
- asymmetric
- quiet
- spacious where explanation matters
- dense where operations matter
- strong typography
- excellent alignment
- subtle surfaces
- meaningful dividers
- selective color
- real data as decoration
- interaction as visual identity

### Do not chase "premium" with effects.

Premium comes from:

- spacing
- typography
- proportion
- hierarchy
- consistency
- restraint
- good empty space
- precise alignment
- interaction quality

---

# STEP 4: VISUAL SYSTEM

## Color

Keep the existing Clinical Cobalt palette, but **use cobalt sparingly**.

```css
--color-bg: #F5F6F4;
--color-surface: #FFFFFF;
--color-surface-2: #ECEEEB;
--color-ink: #0F1214;
--color-ink-muted: #5A6166;
--color-hairline: #DDE0DC;
--color-accent: #2447D6;
--color-accent-tint: #E6EBFB;
```

Dark theme:

```css
--color-bg: #0C0F11;
--color-surface: #13171A;
--color-surface-2: #1A1F22;
--color-ink: #E8EBE9;
--color-ink-muted: #9AA2A7;
--color-hairline: #262C30;
--color-accent: #6D8BFF;
--color-accent-tint: #18214A;
```

Semantic colors:

```text
confirmed: #0E7A4F
not_confirmed: #B26A00
explicitly_unavailable: #B4233C
unknown: #8A9096
```

### Color usage rule

Most of the page should be neutral.

Cobalt should identify:

- primary actions
- the current agent phase
- selected navigation
- important interactive states

Do not tint every card blue.

Do not use gradients.

Do not use glow.

Do not use purple.

Do not use neon.

---

## Typography

Use Geist / Geist Mono if already installed and appropriate.

But **stop using monospace as a decorative design language**.

Geist Mono is for:

- IDs
- timestamps
- scores
- call IDs
- API values
- technical data

Do not use monospace for:

- every eyebrow
- every heading
- section labels
- normal explanatory copy

Normal product copy should use Geist.

### Typography hierarchy

Landing:

- Display: large but not absurd
- Section headings: 48 to 64px desktop
- Body: 17 to 20px
- Supporting text: 14 to 16px

App:

- Page title: 24 to 32px
- Body: 14 to 15px
- Data: 13 to 14px
- IDs: Geist Mono

Avoid making every section headline huge.

---

# STEP 5: SHAPE LANGUAGE

This is one of the biggest changes from the previous implementation.

### Reduce rounded containers.

Use:

- 0 to 4px radius for editorial sections and data surfaces
- 8px for controls
- 10 to 12px for important panels
- 16px maximum for major app surfaces

Do not use 20 to 28px radius everywhere.

### Do not use "double bezel" as a default visual language.

The previous hero shell looked like a product mockup sitting inside another product mockup.

Replace this with a **single clean frame** or an edge-to-edge operational scene.

Use a bezel only if it materially improves hierarchy.

### Pills

Pills are reserved for:

- status
- mode
- compact metadata

Do not make every label a pill.

### Cards

A card must have a reason to exist.

Prefer:

- open compositions
- sections separated by whitespace
- hairlines
- tables
- editorial blocks
- anchored data
- asymmetric columns

over:

- 6 identical rounded cards

---

# STEP 6: LAYOUT PRINCIPLES

Use a strong editorial grid.

Default desktop container:

```text
max-width: 1280px
padding: 32px to 48px
```

But do not force every section into the same container.

Allow:

- full-bleed sections
- narrow reading columns
- asymmetric 5/7 and 4/8 splits
- edge-aligned data
- intentional overflow
- large negative space

### Important

**Do not center the hero.**

But also do not force every section into a split layout.

Composition should change based on the story.

---

# STEP 7: LANDING PAGE

The landing page is the most important redesign.

It should feel like a **product narrative**, not a collection of UI sections.

## 1. Navigation

Simple floating navigation is acceptable, but make it quieter.

Desktop:

```text
DischargePulse          How it works   The contradiction   Safety   FAQ     Open console
```

Use one restrained floating container.

Do not animate the navbar excessively.

No shrinking spectacle.

No floating glass effect.

Mobile uses a simple sheet/menu.

---

# 2. HERO

### Objective

Explain the product in 5 seconds and immediately show that this is a real operational workflow.

### Composition

Use a **70/30 editorial split**, not a generic 50/50 SaaS hero.

Left:

```text
The agent makes
the placement calls.

You make the decision.
```

Then:

> DischargePulse checks post-acute facilities by phone, verifies the requirements that matter, catches contradictions in stale directory data, and stops before a referral is sent.

Primary CTA:

**Open the console**

Secondary:

**Watch a recorded run**

Right:

Show a **live operational slice**, not a fake dashboard screenshot.

The visual should be one carefully composed run timeline:

```text
PLAN
94110 · 15 mi
3 facilities considered

↓

ACT
Bayview Post-Acute
Golden Gate Skilled Nursing

↓

OBSERVE
Wound VAC
Directory: available
Call: unavailable

↓

REASON
CONTRADICTION
Facility disqualified
```

Then allow the final verified facility to enter the scene.

### Critical change

Do NOT put this inside multiple nested rounded cards.

Make the operational data feel like a real piece of software.

Use:

- one surface
- one vertical rule
- strong typography
- subtle background
- real data
- selective animation

The hero should look more like an **operator's work surface** than a marketing mockup.

---

# 3. PROBLEM

Do not make this another giant text reveal section.

Use a narrow editorial composition.

Example:

> A directory said Bayview could take a wound VAC patient.

Then below:

> The night nurse was not signed off.

Then:

> The mistake is small in a directory. It is not small at discharge.

On the side:

**3 to 5 hours**

`typical phone work per placement`

Use typography and whitespace.

No card.

No decorative animation.

---

# 4. HOW THE LOOP WORKS

This is the signature interaction.

Use a **vertical operational timeline**, not a giant circular futuristic loop.

Desktop:

```text
01 PLAN
Filter and rank facilities

02 ACT
Place concurrent calls

03 OBSERVE
Turn calls into structured findings

04 REASON
Check hard constraints

05 RE-PLAN
Adapt when reality changes

06 HUMAN GATE
Stop and ask
```

A thin vertical line connects the phases.

The active phase moves as the user scrolls.

To the right, show the corresponding real artifact.

For example:

```text
PLAN

3 facilities within 15 mi
of 94110

SNF-002
Out of network
```

Then:

```text
OBSERVE

wound_vac
NO

staffed_bed
YES
```

Then:

```text
REASON

CONTRADICTION
SNF-001

Directory ≠ call
```

The visual identity should come from the changing evidence.

No glowing circle.

No rotating radar.

No decorative beam unless it communicates the actual sister-facility relationship.

---

# 5. THE CONTRADICTION

This is the visual centerpiece.

Make this section feel almost like an investigation.

Desktop:

```text
THE DIRECTORY

Wound VAC
Available

Source
Directory

Last updated
...

────────────────────

THE CALL

Wound VAC
Unavailable

Source
Admissions call

────────────────────

VERDICT

SNF-001 disqualified.
```

Use an asymmetric split.

The contradiction should be obvious without needing animation.

A draggable comparison can exist, but it should be subtle.

The key interaction:

**dragging reveals the evidence relationship.**

Label clearly:

> Example scenario · Synthetic Patient #10482

Do not use a generic comparison-slider visual with giant rounded cards.

---

# 6. RE-PLANNING

Use the existing Radius Map, but redesign it as a **technical diagram**.

No geographic map.

No radar sweep.

No rotating animation.

Show:

```text
family ZIP
   │
15 mi
   │
SNF-001 ×
   │
named sister
   ↓
SNF-004 ✓
```

When the agent expands from 15 to 30 miles, the ring changes subtly.

The important animation is the **change in decision**, not the movement itself.

---

# 7. CAPABILITIES

Do not use a conventional bento grid.

Use a **large editorial feature with smaller supporting facts**.

Main feature:

### The agent checks what the directory cannot.

Show:

```text
HARD CONSTRAINTS

Payer
Staffed bed
Wound VAC
IV infusion
Isolation
Bariatric
```

Side facts:

- Typed results
- Call provenance
- Budget guard
- Evidence vs ownership
- Adaptive calls

These can be separated by hairlines rather than six floating cards.

---

# 8. HUMAN GATE

This should be one of the strongest sections.

Large statement:

> **The agent found the bed.  
> It does not get to send the referral.**

Under it, show the actual proposal:

```text
BAYVIEW PENINSULA CAMPUS

Score       94
Payer       Confirmed
Bed         Confirmed
Wound VAC   Confirmed
IV          Confirmed

Coordinator
...

Direct fax
...

[ Review placement ]
```

Clicking opens the same approval sheet used in the app.

The important thing is restraint.

Do not make the approval interaction feel like a flashy modal demo.

It should feel consequential.

---

# 9. PROVENANCE + SAFETY

Avoid three cards.

Use a split editorial section:

Left:

A real recorded event trace.

Right:

```text
SYNTHETIC DATA
All patient and facility data is synthetic.

CONSENTING ROLE-PLAYERS
Calls are answered by consenting role-players.

RECORDED CALLS
Replay means a recorded real role-play call.
```

Use a small "audit" feeling without pretending this is a certified audit system.

---

# 10. NUMBERS

Do not animate giant numbers as a gimmick.

Use a restrained horizontal strip:

```text
3 to 5 hrs
phone work

6
concurrent calls

20
call ceiling

0
referrals sent without approval
```

Hairlines and typography are enough.

---

# 11. FAQ

Simple.

No giant accordion cards.

Use a two-column layout:

left: heading and short explanation

right: questions separated by hairlines.

---

# 12. FINAL CTA

Do not use a giant blue rounded banner.

Use a strong editorial closing:

> **Let the agent make the calls.  
> Keep the decision human.**

Button:

**Watch the agent work**

Secondary:

**Open the console**

Accent tint can be used very lightly.

---

# 13. FOOTER

Minimal.

Do not use an enormous decorative wordmark.

Use:

```text
DischargePulse

Product
Architecture
Runbook
API

Synthetic healthcare data only.
Built for the CALL-E hackathon.
```

---

# STEP 8: APPLICATION DESIGN

The application can be denser than the landing page.

It should feel like **real operations software**.

Do not make it visually identical to the marketing site.

Landing = editorial and spacious.

App = dense and functional.

---

## APP SHELL

Sidebar:

```text
Runs
Start a run
Cases
Facilities
System
```

Use a quiet navigation rail.

Avoid excessive icons.

Top bar:

- breadcrumb
- telephony mode
- budget
- theme
- command palette

Do not put everything inside pills.

---

# STEP 9: LIVE RUN PAGE

This is the actual product.

Build it before polishing the landing page.

Desktop structure:

```text
CASE / RUN HEADER
────────────────────────────────────────

PLAN → ACT → OBSERVE → REASON → RE-PLAN → HUMAN GATE

┌──────────────┬───────────────────────────────┬──────────────┐
│ PATIENT      │ CALLS                         │ REASONING    │
│              │                               │              │
│ REQUIREMENTS │ FACILITY A                    │ EVENT TRACE  │
│              │ FACILITY B                    │              │
│ CURRENT PLAN │ FACILITY C                    │ SELECTED     │
│              │                               │ CALL         │
│ RADIUS       │ BED INTELLIGENCE              │ TRANSCRIPT   │
│              │ MATRIX                        │              │
└──────────────┴───────────────────────────────┴──────────────┘
```

### Key rule

This page must look like a **workbench**, not a dashboard made from cards.

Use:

- dense rows
- tables
- hairlines
- aligned columns
- sticky headers
- subtle surfaces
- strong whitespace between functional groups

---

# STEP 10: AGENT CHOREOGRAPHY

The backend contract is authoritative.

Never invent events.

The WebSocket sends:

- `hello`
- `plan`
- `act`
- `observe`
- `reason`
- `replan`
- `awaiting_approval`
- `complete`
- `run`

Important backend truths:

- no mid-call progress events
- calls run concurrently
- observe events arrive after the batch
- real durations are available
- transcript turns are available after observation
- evaluations are appended after a batch is reasoned over
- no live audio stream
- approval records a decision only
- referral packet dispatch is not implemented
- runs live in memory
- backend restart clears runs

Therefore:

**Do not fake ringing, phone menus, speaking, typing, thinking or audio activity.**

---

# STEP 11: CALL LANES

Call lanes should look like **rows in an operations system**, not cards.

Example:

```text
Bayview Post-Acute Center       REPLAY
SNF-001                         01:58

Wound VAC        unavailable
Staffed bed      confirmed
IV infusion      unknown

CALL-E · call_123
Transcript · 14 turns
```

During a call:

```text
Bayview Post-Acute Center       LIVE
01:12 · calling
```

Only the elapsed timer changes.

Only the LIVE indicator may pulse.

No fake waveform.

No fake activity indicator.

---

# STEP 12: BED INTELLIGENCE

Use a table.

Columns:

```text
Facility | Payer | Bed | Wound VAC | IV | Isolation | Score | Disposition
```

Cells use:

- glyph
- short text
- evidence on hover/focus

Do not turn every cell into a colorful badge.

The table should resemble serious operations software.

---

# STEP 13: REASONING TRACE

A chronological evidence feed.

Each row:

```text
REASON
09:41:22

Bayview Post-Acute Center
Directory claim conflicts with call finding.

→ Facility disqualified
```

Use phase labels sparingly.

The content is more important than decorative styling.

---

# STEP 14: CONTRADICTION BANNER

This is an important exception state.

Use a strong amber treatment, but not a huge alert card.

```text
CONTRADICTION DETECTED

Directory
Wound VAC available

Call
Wound VAC unavailable

Resolution
Live information overrides the stale directory claim.
```

The banner should feel like an important operational finding.

---

# STEP 15: TRANSCRIPT

Make transcripts feel like evidence.

Not a chat application.

Use speaker labels, timestamps and turns.

```text
00:18  ADMISSIONS
We can take the patient.

00:31  AGENT
Is the wound VAC staffed overnight?

00:44  ADMISSIONS
Not on the night shift.
```

Playback is allowed, but clearly labeled:

**Playback of recorded call**

Never imply live audio.

---

# STEP 16: APPROVAL

Approval is a decision surface.

Use:

- proposal
- evidence
- decision
- note

Primary action:

**Approve placement**

Secondary:

**Decline**

Supporting text:

> This records your decision. Referral packet dispatch is not built into this prototype.

Do not use celebratory confetti.

Do not use success animations that imply the referral was sent.

---

# STEP 17: OTHER APP PAGES

Implement:

- `/runs/new`
- `/runs`
- `/runs/:runId`
- `/cases`
- `/cases/:caseId`
- `/runs/:runId/calls/:facilityId`
- `/facilities`
- `/facilities/:facilityId`
- `/system`
- `/console`
- `*`

The detailed data contract from the backend remains authoritative.

---

# STEP 18: START A RUN

The Start Run page should feel like a configuration console.

Avoid a wizard.

Use:

```text
CASE

TELEPHONY

LIMITS

REVIEW
```

with a persistent summary.

Controls should be compact and functional.

Do not turn every option into a large visual card.

---

# STEP 19: RUN HISTORY

Use a serious table.

Columns:

```text
Status
Case
Mode
Calls
Cycles
Started
Duration
Outcome
```

Use subtle row highlighting for active runs.

---

# STEP 20: CASES

Cases should be list-first.

Do not use two large cards.

Example:

```text
10482
71F · Aetna Medicare Advantage PPO
Wound VAC · IV ceftriaxone
15 → 30 mi

10483
...
```

---

# STEP 21: FACILITIES

The directory should make the product thesis obvious.

The most important comparison is:

**Directory claim vs phone finding**

Use a table with a side sheet.

Do not make the directory a generic CRUD page.

---

# STEP 22: SYSTEM

System status should be quiet.

Use a structured status page:

```text
API
Operational

Telephony
Replay

Live calls
Unavailable

Call budget
7 / 20

Recorded calls
...

Synthetic data
Yes
```

No giant dashboard tiles.

---

# STEP 23: MOTION

Motion exists to explain change.

Use:

```ts
export const ease = {
  out: [0.16, 1, 0.3, 1],
  inOut: [0.65, 0, 0.35, 1],
} as const

export const spring = {
  snappy: { type: "spring", stiffness: 420, damping: 34 },
  soft: { type: "spring", stiffness: 140, damping: 22 },
} as const

export const dur = {
  micro: 0.18,
  ui: 0.28,
  reveal: 0.6,
} as const
```

### Motion rules

Good:

- active phase transition
- new call row appearing
- contradiction arriving
- queue changing
- radius expanding
- approval surface opening
- route cross-fade
- evidence being revealed

Bad:

- floating cards
- infinite gradients
- rotating objects
- pulsing borders
- decorative beams
- fake typing
- fake audio
- endless counters
- parallax everywhere

If removing an animation makes the UI clearer, remove it.

---

# STEP 24: 21ST.DEV RULES

Use 21st components selectively.

Before installing:

1. search
2. inspect 1 to 2 alternatives
3. choose only if it fits
4. install
5. remove unnecessary variants
6. replace colors
7. replace typography
8. replace radii
9. replace shadows
10. remove demo copy
11. integrate into the product's visual language

### Strong rule

**If the component is recognizable as a 21st.dev demo after integration, it has not been redesigned enough.**

Do not collect components.

Use fewer components, better integrated.

---

# STEP 25: TECHNICAL REQUIREMENTS

Current stack:

- React 19
- TypeScript
- Vite 8
- Tailwind v4
- framer-motion 13.2.0
- React Router
- TanStack Query
- shadcn
- Sonner
- Phosphor Icons

Use Context7 before relying on unfamiliar library APIs.

Use graphify before answering backend-contract questions.

Use the TypeScript API mirror in:

`src/api/types.ts`

Do not rename backend fields.

Remove:

- `lucide-react`
- `motion/react`
- Next.js-specific imports

Keep:

- `framer-motion`

---

# STEP 26: FILE STRUCTURE

```text
src/
  routes/
  landing/
    sections/
  app/
    shell/
  agent/
    LoopTrack
    CallLanes
    CallLane
    ReasoningTrace
    BedIntelligenceMatrix
    RadiusMap
    ContradictionBanner
    TranscriptPlayback
    ApprovalSheet
    RunPlayback
    useRunTimeline
  components/
    ui/
  lib/
  api/
  hooks/
```

Reuse the agent components between the landing page and the application wherever possible.

---

# STEP 27: LANDING DATA

The landing page must use a real recorded replay.

Use:

`landing/data/run-snapshot.json`

If a suitable recorded run does not exist:

**do not fabricate one.**

Instead, create the structural UI and clearly identify the missing real snapshot during delivery.

---

# STEP 28: RESPONSIVE DESIGN

Do not simply stack desktop cards on mobile.

At 375px:

- simplify navigation
- keep hierarchy
- use horizontal scrolling only where the data genuinely requires it
- convert complex tables into readable per-facility sections
- preserve the evidence relationship
- keep approval action visible

At 768px:

- reduce column count
- preserve asymmetric composition where useful

At 1024px:

- transition from desktop workbench to stacked operational sections

At 1440px:

- use whitespace deliberately
- do not stretch content to fill the viewport

---

# STEP 29: ACCESSIBILITY

Required:

- contrast ≥ 4.5:1
- visible focus
- 44px touch targets
- correct keyboard interaction
- correct ARIA
- skip link
- screen-reader progress announcements
- reduced motion equivalent
- state never communicated by color alone
- tables usable on keyboard
- dialogs and sheets keyboard accessible
- command palette accessible
- compare interaction accessible

---

# STEP 30: COPY RULES

Copy should sound like a product team wrote it.

Use:

- concrete verbs
- short sentences
- plain language
- specific evidence

Avoid:

- seamless
- revolutionize
- elevate
- unleash
- next-gen
- empower
- supercharge
- AI-powered as a headline
- intelligent solutions
- frictionless
- game-changing

Never use an em dash character.

No emojis.

---

# STEP 31: PRE-DELIVERY VISUAL AUDIT

Before finishing, inspect the actual rendered product.

Ask:

### Does every section look like it belongs to the same product?

### Are there too many cards?

### Are there too many pills?

### Are there too many rounded corners?

### Are there too many blue elements?

### Is monospace being used as decoration?

### Does the hero look like a generic AI startup?

### Does the app look like a dashboard template?

### Is animation explaining state or just showing off?

### Can I remove 20% of the visual elements and make the page better?

### Does the contradiction feel like the product's identity?

### Does the human gate feel consequential?

### Can a hospital operator understand the interface without knowing AI terminology?

If any answer is poor, redesign before delivery.

---

# STEP 32: BUILD ORDER

1. Inspect the current implementation and screenshots.
2. Write a short **Design Read** explaining:
   - audience
   - visual direction
   - what is being removed from the current design
   - why the new direction fits DischargePulse
3. Build tokens and typography.
4. Build the app shell.
5. Build API and stream plumbing.
6. Build the Live Run page.
7. Test against a real replay run.
8. Build Run Playback.
9. Build Runs, Cases, Facilities and System.
10. Build the landing page by reusing the real agent components.
11. Run the responsive audit.
12. Run accessibility audit.
13. Run visual slop audit.
14. Run:
   - `npm run build`
   - `npm run lint`
15. Run `graphify update .`.

---

# STEP 33: DELIVERY REPORT

Finish with:

## Design decisions

Explain the major visual decisions and what was intentionally removed.

## 21st components

| Area | Component | Why | What changed |
|---|---|---|---|

Do not force a 21st component into a section merely to populate this table.

## Agent choreography

| Event | UI reaction | Motion |
|---|---|---|

Every reaction must correspond to a real backend event.

## Known gaps

List any missing real data, backend limitation or implementation limitation honestly.

---

# FINAL INSTRUCTION

Do not optimize for how impressive the code looks.

Optimize for how convincing the **product** feels.

The best version of DischargePulse should make someone think:

> "This looks like software someone could actually operate."

Not:

> "This looks like an AI landing page."

The interface should communicate one idea repeatedly and clearly:

**The agent handles the repetitive work.  
The evidence stays visible.  
The human keeps the decision.**
