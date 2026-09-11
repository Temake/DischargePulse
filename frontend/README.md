# DischargePulse — Case Manager Command Console

React 19 + TypeScript + Vite + Tailwind CSS v4. **Scaffold only** — panels are
empty shells and the API layer is typed stubs.

```bash
npm install
npm run dev      # http://localhost:5173
```

Run the backend on `:8000` first (see the root README). Vite proxies `/api` and
`/ws` to it, so the browser stays same-origin in development.

## Layout

```
src/
  api/
    types.ts        TypeScript mirror of the backend contract (declarations only)
    client.ts       REST stubs, one per backend route
    stream.ts       WebSocket stub for /ws/runs/{run_id}
  hooks/
    useRunStream.ts stub hook over the run stream
  components/
    layout/         AppShell, Header, Panel, Placeholder
    intake/         PatientIntakePanel        — patient + hard/soft requirements
    loop/           CognitiveLoopVisualizer   — Plan/Act/Observe/Reason/Re-Plan
    matrix/         BedIntelligenceMatrix     — facilities x requirements
    contradictions/ ContradictionBanner       — live call vs stale directory
    calls/          CallTranscriptPanel, ProvenanceBadge
    approval/       ApprovalModal             — human-in-the-loop gate
    budget/         BudgetIndicator           — live call budget
```
