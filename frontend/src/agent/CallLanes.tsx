import { AnimatePresence, m } from 'framer-motion'
import { Link } from 'react-router'
import { ArrowRight } from '@phosphor-icons/react'

import type { Facility } from '@/api/types'
import { useNow } from '@/hooks/useNow'
import { dispositionLabel, dispositionTone, HARD_ORDER, constraintShort } from '@/lib/labels'
import { clock, plural, score, secondsBetween, shortId } from '@/lib/format'
import { arrive } from '@/lib/motion'
import { cn } from '@/lib/utils'
import type { CallLane as Lane } from './runSelectors'
import { ProvenanceBadge } from './ProvenanceBadge'
import { StateMark } from './StateChip'

/** What an in-flight leg is doing, in words that match its provenance. */
const inFlightVerb = { live: 'calling', replay: 'replaying recording', scripted: 'running scripted attendant' } as const

/**
 * One row per facility the agent dispatched.
 *
 * Calls in a batch run concurrently and their results arrive after the batch,
 * so an in-flight row shows only its elapsed time. No ringing, no phone menu,
 * no waveform: the backend reports none of that.
 */
export function CallLanes({
  lanes,
  facilities,
  selectedId,
  onSelect,
  callHref,
  timers = true,
  className,
}: {
  lanes: Lane[]
  facilities: Map<string, Facility>
  selectedId?: string | null
  onSelect?: (facilityId: string) => void
  callHref?: (facilityId: string) => string
  /** Elapsed timers on in-flight rows. Off for playback, where dispatch times are historical. */
  timers?: boolean
  className?: string
}) {
  const anyInFlight = timers && lanes.some((lane) => lane.state === 'in_flight')
  const now = useNow(anyInFlight)

  if (lanes.length === 0) {
    return (
      <p className={cn('py-6 text-sm text-ink-muted', className)}>
        No calls dispatched yet. The agent plans before it dials.
      </p>
    )
  }

  return (
    <ul className={cn('divide-y divide-hairline border-y border-hairline', className)}>
      <AnimatePresence initial={false}>
        {lanes.map((lane) => (
          <m.li key={lane.facilityId} {...arrive}>
            <CallLaneRow
              lane={lane}
              facility={facilities.get(lane.facilityId)}
              now={now}
              timer={timers}
              selected={selectedId === lane.facilityId}
              onSelect={onSelect}
              href={callHref?.(lane.facilityId)}
            />
          </m.li>
        ))}
      </AnimatePresence>
    </ul>
  )
}

export function CallLaneRow({
  lane,
  facility,
  now,
  timer = true,
  selected,
  onSelect,
  href,
}: {
  lane: Lane
  facility?: Facility
  now: number
  timer?: boolean
  selected?: boolean
  onSelect?: (facilityId: string) => void
  href?: string
}) {
  const evaluation = lane.evaluation
  const name = facility?.name ?? evaluation?.facility_name ?? lane.facilityId
  const hard = evaluation
    ? [...evaluation.findings]
        .filter((f) => f.kind === 'hard')
        .sort((a, b) => HARD_ORDER.indexOf(a.code) - HARD_ORDER.indexOf(b.code))
    : []
  const elapsed = lane.state === 'in_flight' ? secondsBetween(lane.dispatchedAt, new Date(now).toISOString()) : null

  return (
    <div
      className={cn(
        'relative grid gap-3 py-3.5 pl-3 pr-1 transition-colors',
        // An in-flight row has no findings yet, so it takes the full width.
        lane.state !== 'in_flight' && 'sm:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]',
        selected ? 'bg-surface-2/70' : onSelect && 'hover:bg-surface-2/40',
      )}
    >
      {selected ? <span className="absolute inset-y-0 left-0 w-[2px] bg-accent" aria-hidden="true" /> : null}

      <div className="min-w-0">
        <div className="flex items-start justify-between gap-3">
          {onSelect ? (
            <button
              type="button"
              onClick={() => onSelect(lane.facilityId)}
              aria-pressed={selected}
              className="min-w-0 text-left text-[15px] font-medium leading-snug after:absolute after:inset-0 after:content-[''] hover:underline hover:decoration-hairline hover:underline-offset-4"
            >
              {name}
            </button>
          ) : (
            <p className="min-w-0 text-[15px] font-medium leading-snug">{name}</p>
          )}
          <ProvenanceBadge
            mode={lane.mode ?? lane.expectedMode}
            answersSource={lane.answersSource}
            inFlight={lane.state === 'in_flight'}
            className="relative shrink-0"
          />
        </div>

        <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[13px] text-ink-muted">
          <span className="font-mono">{lane.facilityId}</span>
          <span aria-hidden="true">·</span>
          {lane.state === 'in_flight' ? (
            <span>
              {timer ? <span className="font-mono tabular-nums text-ink">{clock(elapsed)} </span> : null}
              {inFlightVerb[lane.expectedMode]}
            </span>
          ) : lane.state === 'failed' ? (
            <span className="text-unavailable">Call failed</span>
          ) : lane.durationSeconds != null ? (
            <span className="font-mono tabular-nums">{clock(lane.durationSeconds)}</span>
          ) : (
            <span>{lane.mode === 'scripted' ? 'No call placed' : 'No duration reported'}</span>
          )}
          <span aria-hidden="true">·</span>
          <span>Cycle {lane.cycle}</span>
        </p>

        {lane.state !== 'in_flight' ? (
          <p className="relative mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-ink-muted">
            {lane.callId ? (
              <span>
                CALL-E <span className="font-mono">{shortId(lane.callId, 18)}</span>
              </span>
            ) : null}
            {href ? (
              <Link
                to={href}
                className="inline-flex items-center gap-1 text-ink underline decoration-hairline underline-offset-4 hover:decoration-ink"
              >
                {lane.transcriptTurns > 0 ? `Transcript · ${plural(lane.transcriptTurns, 'turn')}` : 'Call record'}
                <ArrowRight size={12} aria-hidden="true" />
              </Link>
            ) : lane.transcriptTurns > 0 ? (
              <span>Transcript · {plural(lane.transcriptTurns, 'turn')}</span>
            ) : null}
          </p>
        ) : null}
      </div>

      <div className={cn('min-w-0', lane.state === 'in_flight' && 'hidden')}>
        {lane.state === 'in_flight' ? null : lane.state === 'failed' ? (
          <p className="text-[13px] text-ink-muted">{lane.message}</p>
        ) : evaluation ? (
          <>
            <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-[13px]">
              {hard.map((finding) => (
                <div key={finding.code} className="contents">
                  <dt className="truncate text-ink-muted">{constraintShort[finding.code]}</dt>
                  <dd>
                    <StateMark state={finding.state} size={14} />
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-2 flex items-baseline justify-between gap-3 border-t border-hairline pt-2 text-[13px]">
              <span className={cn('font-medium', dispositionTone[evaluation.disposition])}>
                {dispositionLabel[evaluation.disposition]}
              </span>
              <span className="text-ink-muted">
                Score <span className="font-mono tabular-nums text-ink">{score(evaluation.match_score)}</span>
              </span>
            </p>
          </>
        ) : (
          <p className="text-[13px] text-ink-muted">Result received. Evaluation pending.</p>
        )}
      </div>
    </div>
  )
}
