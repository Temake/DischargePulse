import { BudgetIndicator } from '../budget/BudgetIndicator'

export function Header() {
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">DischargePulse</h1>
        <p className="text-xs text-slate-500">
          Case Manager Command Console · audit-ready prototype using synthetic healthcare data
        </p>
      </div>
      <BudgetIndicator />
    </header>
  )
}
