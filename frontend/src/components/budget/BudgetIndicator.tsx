/**
 * Live call budget: spent / ceiling / remaining.
 * Source: GET /api/budget (also in GET /api/health).
 */
export function BudgetIndicator() {
  return (
    <div className="rounded border border-slate-200 px-3 py-1 text-xs text-slate-500">
      Call budget: —
    </div>
  )
}
