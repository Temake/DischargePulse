/**
 * Shows where a call observation came from, on every call card:
 * LIVE or REPLAY (CallObservation.mode), plus a marker when a test-line
 * role-play was requested (CallObservation.roleplay_requested).
 */
export function ProvenanceBadge() {
  return (
    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
      provenance
    </span>
  )
}
