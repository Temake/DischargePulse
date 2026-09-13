import { m } from 'framer-motion'

import type { AgentPhase, RunStatus } from '@/api/types'
import { LOOP_PHASES, phaseLabel } from '@/lib/labels'
import { spring } from '@/lib/motion'
import { cn } from '@/lib/utils'

const ORDER: AgentPhase[] = [...LOOP_PHASES, 'awaiting_approval']

/**
 * Where the agent is in the loop.
 *
 * Six stations on one hairline. The five loop phases share the rule; the human
 * gate sits after a break, because the loop may cycle but always exits to a
 * person. The accent bar is one shared element that slides between stations,
 * so a phase change reads as movement. Only a real event moves it.
 */
export function LoopTrack({
  phase,
  status,
  cycle,
  layoutId = 'loop-track-bar',
  className,
}: {
  phase: AgentPhase | null
  status?: RunStatus | null
  cycle?: number
  layoutId?: string
  className?: string
}) {
  // `complete` lands on the gate: either a decision was recorded or the run
  // escalated to a person without a match.
  const station: AgentPhase | null = phase === 'complete' ? 'awaiting_approval' : phase
  const activeIndex = station ? ORDER.indexOf(station) : -1
  const gateDone = status === 'approved' || status === 'declined' || status === 'no_match_found'

  return (
    <div className={cn('flex items-end gap-4', className)}>
      <ol className="grid min-w-0 flex-1 grid-cols-3 gap-y-3 sm:grid-cols-[repeat(5,minmax(0,1fr))_auto_minmax(0,1.2fr)]">
        {ORDER.map((item, index) => {
          const active = index === activeIndex
          const past = activeIndex > index
          const gate = item === 'awaiting_approval'
          return (
            <li
              key={item}
              className={cn('relative contents')}
              aria-current={active ? 'step' : undefined}
            >
              {gate ? <span className="hidden w-5 sm:block" aria-hidden="true" /> : null}
              <div className="relative pb-2.5 pr-3">
                <span
                  className={cn(
                    'block text-[13px] transition-colors duration-200',
                    active ? 'font-semibold text-accent' : past ? 'text-ink' : 'text-ink-muted',
                    gate && 'font-medium',
                  )}
                >
                  <span className="mr-1.5 font-mono text-[11px] tabular-nums text-ink-muted">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  {phaseLabel[item]}
                  {gate && gateDone ? <span className="sr-only"> (reached)</span> : null}
                </span>
                <span
                  className={cn('absolute inset-x-0 bottom-0 h-px', gate ? 'bg-ink/25' : 'bg-hairline')}
                  aria-hidden="true"
                />
                {past && !active ? (
                  <span className="absolute bottom-0 left-0 right-3 h-px bg-ink/40" aria-hidden="true" />
                ) : null}
                {active ? (
                  <m.span
                    layoutId={layoutId}
                    transition={spring.snappy}
                    className="absolute bottom-0 left-0 right-3 h-[2px] bg-accent"
                    aria-hidden="true"
                  />
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
      {cycle ? (
        <p className="hidden shrink-0 pb-2.5 text-[13px] text-ink-muted sm:block">
          Cycle <span className="font-mono tabular-nums text-ink">{cycle}</span>
        </p>
      ) : null}
    </div>
  )
}
