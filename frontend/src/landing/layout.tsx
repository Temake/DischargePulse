import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** The editorial container. Sections may break out of it when the story wants to. */
export function Container({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('mx-auto w-full max-w-[1280px] px-5 sm:px-8 lg:px-12', className)}>{children}</div>
}

/** A section headline. Sized per section by the caller; most stay below display size. */
export function Headline({
  children,
  id,
  className,
  as: Tag = 'h2',
}: {
  children: ReactNode
  id?: string
  className?: string
  as?: 'h1' | 'h2'
}) {
  return (
    <Tag id={id} className={cn('text-balance font-semibold tracking-[-0.03em] text-ink', className)}>
      {children}
    </Tag>
  )
}
