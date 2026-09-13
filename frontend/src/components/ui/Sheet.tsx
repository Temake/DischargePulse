import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, m, useReducedMotion } from 'framer-motion'
import { X } from '@phosphor-icons/react'

import { dur, ease } from '@/lib/motion'
import { cn } from '@/lib/utils'
import { IconButton } from './Button'

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Keeps Tab inside `container`, closes on Escape, and restores focus on unmount. */
export function useDialogFocus(open: boolean, container: React.RefObject<HTMLElement | null>, onClose: () => void) {
  const closeRef = useRef(onClose)
  useEffect(() => {
    closeRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const node = container.current
    const first = node?.querySelector<HTMLElement>('[data-autofocus]') ?? node
    first?.focus()

    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        closeRef.current()
        return
      }
      if (event.key !== 'Tab' || !node) return
      const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null)
      if (items.length === 0) return
      const head = items[0]
      const tail = items[items.length - 1]
      if (event.shiftKey && document.activeElement === head) {
        event.preventDefault()
        tail.focus()
      } else if (!event.shiftKey && document.activeElement === tail) {
        event.preventDefault()
        head.focus()
      }
    }

    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previous?.focus?.()
    }
  }, [open, container])
}

/**
 * Side sheet. Used for the approval decision, facility detail and the mobile
 * navigation. Slides in from the right edge; one surface, no nested frames.
 */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  side = 'right',
  width = 'max-w-[560px]',
}: {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
  side?: 'right' | 'left'
  width?: string
}) {
  const panel = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const descId = useId()
  const reduce = useReducedMotion()
  useDialogFocus(open, panel, onClose)

  const offset = side === 'right' ? '100%' : '-100%'

  return createPortal(
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-overlay">
          <m.div
            className="absolute inset-0 bg-[#0c0f11]/35"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: dur.ui }}
            onClick={onClose}
            aria-hidden="true"
          />
          <m.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={description ? descId : undefined}
            tabIndex={-1}
            initial={reduce ? { opacity: 0 } : { x: offset }}
            animate={reduce ? { opacity: 1 } : { x: 0 }}
            exit={reduce ? { opacity: 0 } : { x: offset }}
            transition={{ duration: 0.36, ease: ease.out }}
            className={cn(
              'absolute inset-y-0 flex w-full flex-col bg-surface shadow-overlay outline-none',
              side === 'right' ? 'right-0 border-l border-hairline' : 'left-0 border-r border-hairline',
              width,
            )}
          >
            <header className="flex items-start justify-between gap-4 border-b border-hairline px-5 py-4 sm:px-6">
              <div className="min-w-0">
                <h2 id={titleId} className="text-lg font-semibold tracking-[-0.01em]">
                  {title}
                </h2>
                {description ? (
                  <div id={descId} className="mt-1 text-sm text-ink-muted">
                    {description}
                  </div>
                ) : null}
              </div>
              <IconButton onClick={onClose} aria-label="Close" className="-mr-2 -mt-1">
                <X size={18} />
              </IconButton>
            </header>
            <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
            {footer ? <footer className="border-t border-hairline px-5 py-4 sm:px-6">{footer}</footer> : null}
          </m.div>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  )
}
