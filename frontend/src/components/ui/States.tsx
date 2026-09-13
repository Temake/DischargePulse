import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** Placeholder bars shaped like the rows that will replace them. */
export function SkeletonRows({ rows = 4, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('grid gap-3', className)} aria-hidden="true">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="h-4 animate-pulse rounded-edge bg-surface-2" style={{ width: `${88 - index * 9}%` }} />
      ))}
    </div>
  )
}

export function Empty({ title, children, action, className }: { title: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn('py-8', className)}>
      <p className="text-[15px] font-medium">{title}</p>
      {children ? <div className="mt-1 max-w-[60ch] text-sm text-ink-muted">{children}</div> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}

export function ErrorNote({ title, children, className }: { title: string; children?: ReactNode; className?: string }) {
  return (
    <div role="alert" className={cn('border-l-2 border-unavailable py-1 pl-4', className)}>
      <p className="text-[15px] font-medium">{title}</p>
      {children ? <div className="mt-1 text-sm text-ink-muted">{children}</div> : null}
    </div>
  )
}
