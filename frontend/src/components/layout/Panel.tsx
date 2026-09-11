import type { ReactNode } from 'react'

interface PanelProps {
  title: string
  children?: ReactNode
  className?: string
}

/** Presentational card used by every console panel. */
export function Panel({ title, children, className = '' }: PanelProps) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white p-4 ${className}`}>
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </h2>
      {children}
    </section>
  )
}
