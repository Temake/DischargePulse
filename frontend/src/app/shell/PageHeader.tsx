import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}) {
  return (
    <header className={cn('flex flex-wrap items-end justify-between gap-x-8 gap-y-4 pb-6', className)}>
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-[-0.02em] sm:text-[28px]">{title}</h1>
        {description ? <div className="mt-1.5 max-w-[68ch] text-[15px] text-ink-muted">{description}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </header>
  )
}

/** A labelled group inside a page, separated by a hairline rather than a card. */
export function PageSection({
  title,
  meta,
  children,
  className,
  id,
}: {
  title: ReactNode
  meta?: ReactNode
  children: ReactNode
  className?: string
  id?: string
}) {
  return (
    <section id={id} className={cn('border-t border-ink/15 pt-4', className)}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 pb-3">
        <h2 className="text-[15px] font-semibold">{title}</h2>
        {meta ? <div className="text-[13px] text-ink-muted">{meta}</div> : null}
      </div>
      {children}
    </section>
  )
}
