import { Fragment } from 'react'
import { AnimatePresence, m } from 'framer-motion'

import type { ConstraintCode, ConstraintFinding, Facility, FacilityEvaluation } from '@/api/types'
import { Tooltip } from '@/components/ui/Tooltip'
import { constraintShort, dispositionLabel, dispositionTone, HARD_ORDER, verificationLabel } from '@/lib/labels'
import { score } from '@/lib/format'
import { arrive } from '@/lib/motion'
import { cn } from '@/lib/utils'
import { sourceName } from './runSelectors'
import { StateMark, stateShort } from './StateChip'

/** Hard-constraint columns actually present in this run, in canonical order. */
function columnsFor(evaluations: FacilityEvaluation[]): ConstraintCode[] {
  const present = new Set(evaluations.flatMap((e) => e.findings.filter((f) => f.kind === 'hard').map((f) => f.code)))
  return HARD_ORDER.filter((code) => present.has(code))
}

function Evidence({
  finding,
  evaluation,
  facility,
}: {
  finding: ConstraintFinding
  evaluation: FacilityEvaluation
  facility?: Facility
}) {
  const claim = facility?.directory_claims.find((c) => c.code === finding.code)
  const contradiction = evaluation.contradictions.find((c) => c.code === finding.code)
  return (
    <div className="grid gap-2">
      <p className="font-medium">
        {finding.label}: {verificationLabel[finding.state]}
      </p>
      <p className="text-ink-muted">{finding.rationale}</p>
      {finding.quote ? <p className="border-l-2 border-hairline pl-2.5">“{finding.quote}”</p> : null}
      <p className="text-[12px] text-ink-muted">
        Source: {sourceName(evaluation)}
        {claim ? ` · Directory: ${claim.claimed_available ? 'available' : 'not available'}` : ''}
      </p>
      {contradiction ? <p className="text-[12px] font-medium text-not-confirmed">Contradicts the directory</p> : null}
    </div>
  )
}

/**
 * Hard constraints by facility. A table, because the question it answers is a
 * comparison. Cells carry a glyph and a short word; the evidence behind each
 * cell opens on hover or focus. Below `md` each facility becomes its own block
 * so nothing requires sideways scrolling to read.
 */
export function BedIntelligenceMatrix({
  evaluations,
  facilities,
  selectedId,
  onSelect,
  className,
}: {
  evaluations: FacilityEvaluation[]
  facilities: Map<string, Facility>
  selectedId?: string | null
  onSelect?: (facilityId: string) => void
  className?: string
}) {
  if (evaluations.length === 0) {
    return (
      <p className={cn('py-6 text-sm text-ink-muted', className)}>
        Findings appear here once the first batch of calls has been reasoned over.
      </p>
    )
  }

  const columns = columnsFor(evaluations)
  const cellFor = (evaluation: FacilityEvaluation, code: ConstraintCode) =>
    evaluation.findings.find((f) => f.code === code && f.kind === 'hard')

  return (
    // Sized by its own column, not the viewport: the workbench's center column is narrow at desktop widths.
    <div className={cn('@container', className)}>
      {/* Wide container: the table. */}
      <div className="scrollbar-thin hidden overflow-x-auto @[40rem]:block">
        <table className="w-full border-collapse text-[13px]">
          <caption className="sr-only">
            Hard constraints by facility. Focus a cell to read the evidence behind it.
          </caption>
          <thead>
            <tr className="border-b border-ink/15 text-left text-ink-muted">
              <th scope="col" className="label-caps py-2 pr-4 font-semibold">Facility</th>
              {columns.map((code) => (
                <th key={code} scope="col" className="label-caps px-3 py-2 font-semibold">
                  {constraintShort[code]}
                </th>
              ))}
              <th scope="col" className="label-caps px-3 py-2 text-right font-semibold">Score</th>
              <th scope="col" className="label-caps py-2 pl-3 font-semibold">Disposition</th>
            </tr>
          </thead>
          <tbody>
            <AnimatePresence initial={false}>
              {evaluations.map((evaluation) => {
                const facility = facilities.get(evaluation.facility_id)
                const selected = selectedId === evaluation.facility_id
                return (
                  <m.tr
                    key={evaluation.facility_id}
                    {...arrive}
                    className={cn('border-b border-hairline align-top', selected && 'bg-surface-2/70')}
                  >
                    <th scope="row" className="py-2.5 pr-4 text-left font-normal">
                      {onSelect ? (
                        <button
                          type="button"
                          onClick={() => onSelect(evaluation.facility_id)}
                          aria-pressed={selected}
                          className="text-left font-medium hover:underline hover:decoration-hairline hover:underline-offset-4"
                        >
                          {facility?.name ?? evaluation.facility_name}
                        </button>
                      ) : (
                        <span className="font-medium">{facility?.name ?? evaluation.facility_name}</span>
                      )}
                      <span className="block font-mono text-[12px] text-ink-muted">{evaluation.facility_id}</span>
                    </th>
                    {columns.map((code) => {
                      const finding = cellFor(evaluation, code)
                      const contradicted = evaluation.contradictions.some((c) => c.code === code)
                      return (
                        <td key={code} className="px-3 py-2.5">
                          {finding ? (
                            <Tooltip
                              content={<Evidence finding={finding} evaluation={evaluation} facility={facility} />}
                              label={`${constraintShort[code]}: ${verificationLabel[finding.state]}${contradicted ? ', contradicts directory' : ''}. Show evidence.`}
                              triggerClassName="-mx-1 px-1 py-0.5 hover:bg-surface-2"
                            >
                              <StateMark state={finding.state} label={stateShort[finding.state]} size={14} />
                              {contradicted ? (
                                <span className="ml-1 align-super text-[10px] font-semibold text-not-confirmed" aria-hidden="true">
                                  ≠
                                </span>
                              ) : null}
                            </Tooltip>
                          ) : (
                            <span className="text-ink-muted">n/a</span>
                          )}
                        </td>
                      )
                    })}
                    <td className="px-3 py-2.5 text-right font-mono tabular-nums">{score(evaluation.match_score)}</td>
                    <td className={cn('py-2.5 pl-3 font-medium', dispositionTone[evaluation.disposition])}>
                      {dispositionLabel[evaluation.disposition]}
                    </td>
                  </m.tr>
                )
              })}
            </AnimatePresence>
          </tbody>
        </table>
        <p className="mt-2 text-[12px] text-ink-muted">
          <span className="font-semibold text-not-confirmed">≠</span> the call contradicted the directory. Hover or focus a cell for evidence.
        </p>
      </div>

      {/* Narrow container: one block per facility, evidence inline. */}
      <div className="grid grid-cols-1 gap-x-8 border-t border-hairline @[26rem]:grid-cols-2 @[40rem]:hidden [&>section]:border-b [&>section]:border-hairline">
        {evaluations.map((evaluation) => {
          const facility = facilities.get(evaluation.facility_id)
          return (
            <section key={evaluation.facility_id} className="py-3.5" aria-label={evaluation.facility_name}>
              <div className="flex items-baseline justify-between gap-3">
                <p className="font-medium">{facility?.name ?? evaluation.facility_name}</p>
                <span className="font-mono text-[13px] tabular-nums">{score(evaluation.match_score)}</span>
              </div>
              <p className={cn('text-[13px] font-medium', dispositionTone[evaluation.disposition])}>
                {dispositionLabel[evaluation.disposition]}
              </p>
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
                {columns.map((code) => {
                  const finding = cellFor(evaluation, code)
                  const contradicted = evaluation.contradictions.find((c) => c.code === code)
                  return (
                    <Fragment key={code}>
                      <dt className="text-ink-muted">{constraintShort[code]}</dt>
                      <dd>
                        {finding ? <StateMark state={finding.state} size={14} /> : 'n/a'}
                        {contradicted ? (
                          <span className="block text-[12px] text-not-confirmed">
                            Contradicts directory ({contradicted.directory_says})
                          </span>
                        ) : null}
                        {finding?.quote ? (
                          <span className="mt-0.5 block text-[12px] text-ink-muted">“{finding.quote}”</span>
                        ) : null}
                      </dd>
                    </Fragment>
                  )
                })}
              </dl>
            </section>
          )
        })}
      </div>
    </div>
  )
}
