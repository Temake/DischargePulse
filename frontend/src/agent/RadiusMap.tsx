import { m, useReducedMotion } from 'framer-motion'

import type { Facility, FacilityEvaluation, PatientCase, PlacementPlan } from '@/api/types'
import { dispositionLabel } from '@/lib/labels'
import { miles } from '@/lib/format'
import { ease } from '@/lib/motion'
import { cn } from '@/lib/utils'
import { sourceName } from './runSelectors'

type RowState = 'match' | 'disqualified' | 'follow_up' | 'unreached' | 'queued' | 'excluded' | 'outside' | 'idle'

const MARK: Record<RowState, { glyph: string; tone: string; word: (e?: FacilityEvaluation) => string }> = {
  match: { glyph: '✓', tone: 'text-confirmed', word: () => dispositionLabel.match_verified },
  disqualified: { glyph: '×', tone: 'text-unavailable', word: () => dispositionLabel.disqualified },
  follow_up: { glyph: '!', tone: 'text-not-confirmed', word: () => dispositionLabel.needs_follow_up },
  unreached: { glyph: '?', tone: 'text-unknown', word: () => dispositionLabel.unreached },
  queued: { glyph: '○', tone: 'text-accent', word: () => 'In queue' },
  excluded: { glyph: '–', tone: 'text-ink-muted', word: () => 'Excluded' },
  outside: { glyph: '–', tone: 'text-ink-muted', word: () => 'Outside radius' },
  idle: { glyph: '·', tone: 'text-ink-muted', word: () => 'Not yet planned' },
}

/**
 * Distance diagram, not a map.
 *
 * One row per facility, a mark at its true distance from the family zip along
 * a 0 to max-radius axis. The directory carries distance, not coordinates, so
 * nothing here claims to know direction. The vertical rule is the search
 * radius; when the agent widens it, the rule moves and rows change state. The
 * change in decision is the point, not the movement.
 */
export function RadiusMap({
  patient,
  facilities,
  plans,
  evaluations,
  className,
  compact = false,
}: {
  patient: Pick<PatientCase, 'family_zip' | 'search_radius_miles' | 'max_radius_miles'>
  facilities: Facility[]
  plans: PlacementPlan[]
  evaluations: FacilityEvaluation[]
  className?: string
  compact?: boolean
}) {
  const reduce = useReducedMotion()
  const max = Math.max(patient.max_radius_miles, ...facilities.map((f) => f.distance_miles))
  const latest = plans[plans.length - 1]
  const radius = latest?.radius_miles ?? patient.search_radius_miles
  const firstPlan = plans[0]
  const queued = new Set(plans.flatMap((p) => p.queue))
  const byId = new Map(evaluations.map((e) => [e.facility_id, e]))
  const pct = (value: number) => `${Math.min(100, (value / max) * 100)}%`

  // Who named whom: sister leads are call evidence, keyed by the facility named.
  const namedBy = new Map<string, FacilityEvaluation>()
  for (const evaluation of evaluations) {
    for (const lead of evaluation.sister_facility_leads) if (!namedBy.has(lead)) namedBy.set(lead, evaluation)
  }

  const rows = [...facilities].sort((a, b) => a.distance_miles - b.distance_miles)

  const stateOf = (facility: Facility): RowState => {
    const evaluation = byId.get(facility.facility_id)
    if (evaluation) {
      return evaluation.disposition === 'match_verified'
        ? 'match'
        : evaluation.disposition === 'disqualified'
          ? 'disqualified'
          : evaluation.disposition === 'needs_follow_up'
            ? 'follow_up'
            : 'unreached'
    }
    if (queued.has(facility.facility_id)) return 'queued'
    if (!firstPlan) return 'idle'
    if (facility.distance_miles > radius) return 'outside'
    return 'excluded'
  }

  return (
    <figure className={cn('text-[13px]', className)}>
      <figcaption className="sr-only">
        Facilities by distance from zip {patient.family_zip}. Search radius {miles(radius)}, cap {miles(patient.max_radius_miles)}.
      </figcaption>

      {/* Axis */}
      <div className={cn('grid gap-x-3', compact ? 'grid-cols-[4.5rem_1fr]' : 'grid-cols-[5.5rem_1fr]')}>
        <div className="text-[12px] text-ink-muted">
          <span className="font-mono">{patient.family_zip}</span>
        </div>
        <div className="relative h-5 font-mono text-[11px] tabular-nums text-ink-muted" aria-hidden="true">
          <span className="absolute left-0">0</span>
          <m.span
            className="absolute -translate-x-1/2 font-medium text-accent"
            initial={false}
            animate={{ left: pct(radius) }}
            transition={reduce ? { duration: 0 } : { duration: 0.7, ease: ease.inOut }}
          >
            {radius}
          </m.span>
          <span className="absolute right-0">{patient.max_radius_miles} mi</span>
        </div>
      </div>

      <ol className="relative">
        {rows.map((facility) => {
          const state = stateOf(facility)
          const evaluation = byId.get(facility.facility_id)
          const mark = MARK[state]
          const lead = namedBy.get(facility.facility_id)
          const reason = firstPlan?.excluded[facility.facility_id]
          const dim = state === 'excluded' || state === 'outside' || state === 'idle'
          return (
            <li
              key={facility.facility_id}
              className={cn(
                'grid items-center gap-x-3 border-t border-hairline py-2',
                compact ? 'grid-cols-[4.5rem_1fr]' : 'grid-cols-[5.5rem_1fr]',
              )}
            >
              <div className="min-w-0">
                <p className={cn('font-mono text-[12px]', dim ? 'text-ink-muted' : 'text-ink')}>{facility.facility_id}</p>
                <p className="font-mono text-[11px] tabular-nums text-ink-muted">{miles(facility.distance_miles)}</p>
              </div>
              <div className="min-w-0">
                <div className="relative h-4" aria-hidden="true">
                  <span className="absolute inset-x-0 top-1/2 h-px bg-hairline" />
                  {/* The search radius, drawn through the track only so it never crosses a label. */}
                  <m.span
                    className="absolute -inset-y-1 w-px bg-accent/70"
                    initial={false}
                    animate={{ left: pct(radius) }}
                    transition={reduce ? { duration: 0 } : { duration: 0.7, ease: ease.inOut }}
                  />
                  <span
                    className={cn(
                      'absolute top-1/2 -translate-x-1/2 -translate-y-1/2 font-semibold leading-none transition-colors duration-300',
                      mark.tone,
                      state === 'match' ? 'text-[15px]' : 'text-[14px]',
                    )}
                    style={{ left: pct(facility.distance_miles) }}
                  >
                    {mark.glyph === '·' ? <span className="block size-1.5 rounded-full bg-ink-muted/60" /> : mark.glyph}
                  </span>
                </div>
                <p className={cn('mt-0.5 truncate text-[12px]', dim ? 'text-ink-muted' : mark.tone)}>
                  {mark.word(evaluation)}
                  {state === 'excluded' && reason ? <span className="text-ink-muted">: {reason}</span> : null}
                  {lead && !compact ? (
                    <span className="text-ink-muted"> · named by {sourceName(lead).toLowerCase()} at {lead.facility_id}</span>
                  ) : null}
                </p>
                {lead && compact ? (
                  <p className="truncate text-[12px] text-ink-muted">↳ named at {lead.facility_id}</p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
    </figure>
  )
}
