import { useEffect, useRef } from 'react'
import { AnimatePresence, m } from 'framer-motion'
import { ArrowRight } from '@phosphor-icons/react'

import type { AgentEvent, Facility } from '@/api/types'
import { phaseLabel, triggerLabel } from '@/lib/labels'
import { time } from '@/lib/format'
import { arrive } from '@/lib/motion'
import { cn } from '@/lib/utils'

/** The facility name is shown on its own line, so drop it from the head of the message. */
function bodyOf(event: AgentEvent, name: string | null): string {
  if (name && event.message.startsWith(`${name}: `)) return event.message.slice(name.length + 2)
  return event.message
}

/**
 * What the agent did and decided, in chronological order.
 *
 * Every line is a real `AgentEvent.message`. Nothing is written for the page.
 * Rows arrive with a short fade because an event arrived; the backlog on a
 * reconnect renders without a wave of motion.
 */
export function ReasoningTrace({
  events,
  facilities,
  limit,
  onSelectFacility,
  className,
  scrollClassName,
  follow = true,
}: {
  events: AgentEvent[]
  facilities: Map<string, Facility>
  /** Show only the most recent N. */
  limit?: number
  onSelectFacility?: (facilityId: string) => void
  className?: string
  /** Makes the list its own scroll area that follows new events. */
  scrollClassName?: string
  /** Keep the newest event in view as events arrive. Off for a static trace read from the top. */
  follow?: boolean
}) {
  const shown = limit ? events.slice(-limit) : events
  const scroller = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)

  useEffect(() => {
    const node = scroller.current
    if (!node || !scrollClassName || !follow || !pinned.current) return
    node.scrollTop = node.scrollHeight
  }, [shown.length, scrollClassName, follow])

  if (shown.length === 0) {
    return <p className={cn('py-6 text-sm text-ink-muted', className)}>The trace fills in as the agent works.</p>
  }

  return (
    <div
      ref={scroller}
      className={cn(scrollClassName && 'scrollbar-thin overflow-y-auto', scrollClassName, className)}
      onScroll={(event) => {
        const node = event.currentTarget
        pinned.current = node.scrollHeight - node.scrollTop - node.clientHeight < 40
      }}
      tabIndex={scrollClassName ? 0 : undefined}
      aria-label={scrollClassName ? 'Reasoning trace' : undefined}
    >
      {/* Announcements come from RunAnnouncer, one per event, so the log itself stays quiet. */}
      <ol role="log" aria-live="off" aria-label="Agent event trace" className="divide-y divide-hairline">
        <AnimatePresence initial={false}>
          {shown.map((event, index) => {
            const facility = event.facility_id ? facilities.get(event.facility_id) : undefined
            const name = facility?.name ?? null
            const gate = event.phase === 'awaiting_approval'
            const contradiction = event.trigger === 'contradiction_disqualified'
            return (
              <m.li key={`${event.at}-${event.phase}-${event.facility_id ?? 'run'}-${index}`} {...arrive} className="py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <span className={cn('label-caps', gate ? 'text-accent' : 'text-ink-muted')}>
                    {phaseLabel[event.phase]}
                    <span className="sr-only">, cycle {event.cycle}</span>
                  </span>
                  <time dateTime={event.at} className="font-mono text-[12px] tabular-nums text-ink-muted">
                    {time(event.at)}
                  </time>
                </div>
                {event.facility_id ? (
                  onSelectFacility ? (
                    <button
                      type="button"
                      onClick={() => onSelectFacility(event.facility_id!)}
                      className="mt-1 text-left text-[14px] font-medium hover:underline hover:decoration-hairline hover:underline-offset-4"
                    >
                      {name ?? event.facility_id}
                    </button>
                  ) : (
                    <p className="mt-1 text-[14px] font-medium">{name ?? event.facility_id}</p>
                  )
                ) : null}
                <p className="mt-0.5 text-[14px] leading-snug text-ink-muted">{bodyOf(event, name)}</p>
                {event.trigger ? (
                  <p
                    className={cn(
                      'mt-1.5 inline-flex items-center gap-1.5 text-[13px] font-medium',
                      contradiction ? 'text-not-confirmed' : 'text-ink',
                    )}
                  >
                    <ArrowRight size={12} weight="bold" aria-hidden="true" />
                    {triggerLabel[event.trigger]}
                  </p>
                ) : null}
              </m.li>
            )
          })}
        </AnimatePresence>
      </ol>
    </div>
  )
}
