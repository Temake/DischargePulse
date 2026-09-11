import type { ReactNode } from 'react'

/** Marks where a panel's content will go. Remove as panels are built. */
export function Placeholder({ children }: { children: ReactNode }) {
  return (
    <p className="rounded border border-dashed border-slate-300 p-3 text-sm text-slate-400">
      {children}
    </p>
  )
}
