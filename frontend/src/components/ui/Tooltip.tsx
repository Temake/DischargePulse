import { useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

import { cn } from '@/lib/utils'

/**
 * Hover and focus disclosure for evidence. Rendered in a portal so it is never
 * clipped by a scrolling table. The trigger is a real button, so keyboard users
 * reach it with Tab and screen readers get the content via aria-describedby.
 */
export function Tooltip({
  content,
  children,
  className,
  triggerClassName,
  label,
}: {
  content: ReactNode
  children: ReactNode
  className?: string
  triggerClassName?: string
  /** Accessible name for the trigger when its visible content is terse. */
  label?: string
}) {
  const id = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number; above: boolean } | null>(null)

  useLayoutEffect(() => {
    if (!open || !trigger.current) return
    const rect = trigger.current.getBoundingClientRect()
    const above = rect.bottom + 180 > window.innerHeight
    const left = Math.min(Math.max(12, rect.left + rect.width / 2 - 150), window.innerWidth - 312)
    setPos({ top: above ? rect.top - 8 : rect.bottom + 8, left, above })
  }, [open])

  return (
    <>
      <button
        ref={trigger}
        type="button"
        aria-describedby={open ? id : undefined}
        aria-label={label}
        className={cn('rounded-edge text-left', triggerClassName)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(event) => event.key === 'Escape' && setOpen(false)}
      >
        {children}
      </button>
      {open && pos
        ? createPortal(
            <div
              id={id}
              role="tooltip"
              style={{ top: pos.top, left: pos.left }}
              className={cn(
                'pointer-events-none fixed z-toast w-[300px] rounded-field border border-hairline bg-surface px-3 py-2.5 text-[13px] leading-snug text-ink shadow-overlay',
                pos.above && '-translate-y-full',
                className,
              )}
            >
              {content}
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
