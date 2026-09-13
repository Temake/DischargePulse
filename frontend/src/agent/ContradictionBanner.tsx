import { m } from 'framer-motion'
import { WarningDiamond } from '@phosphor-icons/react'

import type { Facility } from '@/api/types'
import { date } from '@/lib/format'
import { dur, ease } from '@/lib/motion'
import { cn } from '@/lib/utils'
import { sourceName, type FoundContradiction } from './runSelectors'

/**
 * An operational finding, not an alert card: the directory said one thing, the
 * call said another, and live information won. Amber rule on the left, three
 * aligned columns, the quote as evidence underneath.
 */
export function ContradictionBanner({
  found,
  facilities,
  onSelect,
  className,
}: {
  found: FoundContradiction[]
  facilities: Map<string, Facility>
  onSelect?: (facilityId: string) => void
  className?: string
}) {
  if (found.length === 0) return null
  const [lead, ...rest] = found
  const { evaluation, contradiction } = lead
  const facility = facilities.get(evaluation.facility_id)
  const claim = facility?.directory_claims.find((c) => c.code === contradiction.code)
  const heading = found.length === 1 ? 'Contradiction detected' : `${found.length} contradictions detected`

  return (
    <m.section
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: dur.ui, ease: ease.out }}
      aria-label={heading}
      className={cn('border-l-[3px] border-not-confirmed bg-not-confirmed/[0.06] py-4 pl-4 pr-4 sm:pl-5', className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="label-caps inline-flex items-center gap-2 text-not-confirmed">
          <WarningDiamond size={15} weight="bold" aria-hidden="true" />
          {heading}
        </h2>
        <p className="text-[13px] text-ink-muted">
          {onSelect ? (
            <button type="button" onClick={() => onSelect(evaluation.facility_id)} className="font-medium text-ink hover:underline hover:underline-offset-4">
              {evaluation.facility_name}
            </button>
          ) : (
            <span className="font-medium text-ink">{evaluation.facility_name}</span>
          )}{' '}
          <span className="font-mono">{evaluation.facility_id}</span>
        </p>
      </div>

      <dl className="mt-3 grid gap-x-8 gap-y-3 text-[14px] sm:grid-cols-[1fr_1fr_1.4fr]">
        <div>
          <dt className="text-[13px] text-ink-muted">Directory</dt>
          <dd className="mt-0.5 font-medium">{contradiction.directory_says}</dd>
          {claim ? (
            <dd className="mt-0.5 text-[12px] text-ink-muted">
              {claim.source} · updated {date(claim.last_updated)}
            </dd>
          ) : null}
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">{sourceName(evaluation)}</dt>
          <dd className="mt-0.5 font-medium">{contradiction.call_says}</dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">Resolution</dt>
          <dd className="mt-0.5">{contradiction.resolution}</dd>
        </div>
      </dl>

      {contradiction.quote ? (
        <blockquote className="mt-3 max-w-[72ch] border-l border-ink/20 pl-3 text-[14px] text-ink-muted">
          “{contradiction.quote}”
        </blockquote>
      ) : null}

      {rest.length > 0 ? (
        <ul className="mt-3 grid gap-1 border-t border-not-confirmed/20 pt-3 text-[13px]">
          {rest.map((item) => (
            <li key={`${item.evaluation.facility_id}-${item.contradiction.code}`} className="text-ink-muted">
              <span className="font-medium text-ink">{item.evaluation.facility_name}</span>: directory said “
              {item.contradiction.directory_says}”, {sourceName(item.evaluation).toLowerCase()} said “{item.contradiction.call_says}”.
            </li>
          ))}
        </ul>
      ) : null}
    </m.section>
  )
}
