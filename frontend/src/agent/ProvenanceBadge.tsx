import type { AnswersSource, CallMode } from '@/api/types'
import { callModeLabel } from '@/lib/labels'
import { cn } from '@/lib/utils'

/**
 * Where a call came from. One of the few pill-like marks in the product,
 * because provenance is the thing a reviewer must never miss.
 *
 *   LIVE      a real CALL-E call. Carries the only pulsing dot, and only while
 *             the call is actually in flight.
 *   REPLAY    a recorded call served from a cassette.
 *   SCRIPTED  no call placed; answers from the test scenario.
 *
 * A LIVE call can still carry simulated attendant answers; that is stamped
 * separately so neither fact hides the other.
 */
export function ProvenanceBadge({
  mode,
  answersSource,
  inFlight = false,
  className,
}: {
  mode: CallMode
  answersSource?: AnswersSource | null
  inFlight?: boolean
  className?: string
}) {
  const live = mode === 'live'
  const simulatedAnswers = answersSource === 'simulated' && mode !== 'scripted'

  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      <span
        className={cn(
          'inline-flex h-5 items-center gap-1.5 rounded-edge border px-1.5 font-mono text-[10.5px] font-medium tracking-[0.06em]',
          live ? 'border-accent/40 text-accent' : 'border-hairline text-ink-muted',
        )}
      >
        {live ? (
          <span
            className={cn('size-1.5 rounded-full bg-accent', inFlight && 'motion-safe:animate-pulse')}
            aria-hidden="true"
          />
        ) : null}
        {callModeLabel[mode]}
      </span>
      {simulatedAnswers ? (
        <span className="inline-flex h-5 items-center rounded-edge border border-not-confirmed/40 px-1.5 text-[11px] font-medium text-not-confirmed">
          Simulated answers
        </span>
      ) : null}
    </span>
  )
}
