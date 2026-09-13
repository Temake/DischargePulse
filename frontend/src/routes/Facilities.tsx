import { useMemo } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { useQueries } from '@tanstack/react-query'
import { CheckCircle, XCircle } from '@phosphor-icons/react'

import { getRun } from '@/api/client'
import type { Facility, FacilityEvaluation, FacilityView } from '@/api/types'
import { sourceName } from '@/agent/runSelectors'
import { StateMark } from '@/agent/StateChip'
import { useCrumbs } from '@/app/shell/crumbs'
import { PageHeader } from '@/app/shell/PageHeader'
import { Sheet } from '@/components/ui/Sheet'
import { ErrorNote, SkeletonRows } from '@/components/ui/States'
import { keys, useFacilities, useRuns } from '@/hooks/queries'
import { EXAMPLE_RUN_ID, snapshotRecord } from '@/landing/data/snapshot'
import { date, miles, score } from '@/lib/format'
import { constraintShort, dispositionLabel, dispositionTone, HARD_ORDER } from '@/lib/labels'
import { cn } from '@/lib/utils'

interface Finding {
  runId: string
  label: string
  startedAt: string
  evaluation: FacilityEvaluation
}

/** Phone findings per facility, from backend runs plus the labelled example run. */
function usePhoneFindings(): Map<string, Finding[]> {
  const runs = useRuns()
  const recent = (runs.data ?? []).slice(0, 12)
  const records = useQueries({
    queries: recent.map((run) => ({ queryKey: keys.run(run.run_id), queryFn: () => getRun(run.run_id), staleTime: 15_000 })),
  })

  return useMemo(() => {
    const map = new Map<string, Finding[]>()
    const add = (runId: string, label: string, startedAt: string, evaluations: FacilityEvaluation[]) => {
      for (const evaluation of evaluations) {
        const list = map.get(evaluation.facility_id) ?? []
        list.push({ runId, label, startedAt, evaluation })
        map.set(evaluation.facility_id, list)
      }
    }
    for (const query of records) {
      const record = query.data
      if (record) add(record.run_id, record.run_id, record.started_at, record.run.evaluations)
    }
    add(EXAMPLE_RUN_ID, 'Example run (scripted)', snapshotRecord.started_at, snapshotRecord.run.evaluations)
    return map
  }, [records])
}

function ClaimsSummary({ facility }: { facility: Facility }) {
  const hard = facility.directory_claims.filter((c) => HARD_ORDER.includes(c.code))
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1">
      {hard
        .sort((a, b) => HARD_ORDER.indexOf(a.code) - HARD_ORDER.indexOf(b.code))
        .map((claim) => (
          <li key={claim.code} className="inline-flex items-center gap-1">
            {claim.claimed_available ? (
              <CheckCircle size={13} weight="fill" className="text-ink-muted" aria-hidden="true" />
            ) : (
              <XCircle size={13} weight="bold" className="text-ink-muted" aria-hidden="true" />
            )}
            {constraintShort[claim.code]}
            <span className="sr-only">{claim.claimed_available ? 'claimed available' : 'claimed not available'}</span>
          </li>
        ))}
    </ul>
  )
}

export function Facilities() {
  const { facilityId } = useParams()
  const navigate = useNavigate()
  const facilities = useFacilities()
  const findings = usePhoneFindings()
  const open = facilities.data?.find((v) => v.facility.facility_id === facilityId)

  useCrumbs(
    open
      ? [{ label: 'Facilities', to: '/facilities' }, { label: open.facility.name }]
      : [{ label: 'Facilities' }],
  )

  return (
    <>
      <PageHeader
        title="Facilities"
        description="The regional directory, next to what calls actually found. A directory claim is a starting point, not evidence."
      />

      {facilities.isLoading ? (
        <SkeletonRows rows={6} />
      ) : facilities.isError ? (
        <ErrorNote title="Could not load the directory">{(facilities.error as Error).message}</ErrorNote>
      ) : (
        <div className="scrollbar-thin overflow-x-auto pb-16">
          <table className="w-full min-w-[920px] border-collapse text-[14px]">
            <caption className="sr-only">Facility directory with the latest phone finding for each facility</caption>
            <thead>
              <tr className="border-b border-ink/15 text-left text-ink-muted">
                <th scope="col" className="label-caps py-2 pr-4 font-semibold">Facility</th>
                <th scope="col" className="label-caps py-2 pr-4 text-right font-semibold">Distance</th>
                <th scope="col" className="label-caps py-2 pr-4 text-right font-semibold">CMS</th>
                <th scope="col" className="label-caps py-2 pr-4 font-semibold">Directory claims</th>
                <th scope="col" className="label-caps py-2 pr-4 font-semibold">Latest phone finding</th>
                <th scope="col" className="label-caps py-2 font-semibold">Demo line</th>
              </tr>
            </thead>
            <tbody>
              {facilities.data?.map((view) => (
                <FacilityRow
                  key={view.facility.facility_id}
                  view={view}
                  finding={findings.get(view.facility.facility_id)?.[0]}
                  selected={view.facility.facility_id === facilityId}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open ? (
        <Sheet
          open
          onClose={() => navigate('/facilities')}
          title={open.facility.name}
          description={
            <>
              <span className="font-mono">{open.facility.facility_id}</span> · {open.facility.facility_type} ·{' '}
              {miles(open.facility.distance_miles)}
            </>
          }
          width="max-w-[640px]"
        >
          <FacilityDetail view={open} findings={findings.get(open.facility.facility_id) ?? []} />
        </Sheet>
      ) : null}
    </>
  )
}

function FacilityRow({ view, finding, selected }: { view: FacilityView; finding?: Finding; selected: boolean }) {
  const { facility } = view
  const contradictions = finding?.evaluation.contradictions.length ?? 0
  return (
    <tr className={cn('border-b border-hairline align-top transition-colors hover:bg-surface-2/50', selected && 'bg-surface-2/70')}>
      <th scope="row" className="py-3 pr-4 text-left font-normal">
        <Link to={`/facilities/${facility.facility_id}`} className="font-medium hover:underline hover:underline-offset-4">
          {facility.name}
        </Link>
        <span className="block font-mono text-[12px] text-ink-muted">
          {facility.facility_id}
          {facility.preferred_partner ? <span className="font-sans"> · preferred partner</span> : null}
        </span>
      </th>
      <td className="py-3 pr-4 text-right font-mono tabular-nums">{miles(facility.distance_miles)}</td>
      <td className="py-3 pr-4 text-right font-mono tabular-nums">{facility.cms_star_rating}/5</td>
      <td className="py-3 pr-4 text-[13px] text-ink-muted">
        <ClaimsSummary facility={facility} />
        <span className="mt-0.5 block text-[12px]">Accepts {facility.accepted_payers.join(', ')}</span>
      </td>
      <td className="py-3 pr-4 text-[13px]">
        {finding ? (
          <>
            <span className={cn('font-medium', dispositionTone[finding.evaluation.disposition])}>
              {dispositionLabel[finding.evaluation.disposition]}
            </span>
            {contradictions > 0 ? (
              <span className="ml-2 font-medium text-not-confirmed">
                ≠ {contradictions === 1 ? 'contradicts directory' : `${contradictions} contradictions`}
              </span>
            ) : null}
            <span className="block text-[12px] text-ink-muted">
              {sourceName(finding.evaluation)} · {finding.label}
            </span>
          </>
        ) : (
          <span className="text-ink-muted">Not called</span>
        )}
      </td>
      <td className="py-3 text-[13px] text-ink-muted">{view.dialable ? 'Dialable' : 'No demo line'}</td>
    </tr>
  )
}

function FacilityDetail({ view, findings }: { view: FacilityView; findings: Finding[] }) {
  const { facility } = view
  const claims = [...facility.directory_claims].sort((a, b) => HARD_ORDER.indexOf(a.code) - HARD_ORDER.indexOf(b.code))

  return (
    <div className="grid gap-7">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[14px]">
        <div className="col-span-2">
          <dt className="text-[13px] text-ink-muted">Address</dt>
          <dd>{facility.address}</dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">Phone</dt>
          <dd className="font-mono">
            {facility.phone}
            {facility.admissions_extension ? ` x${facility.admissions_extension}` : ''}
          </dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">Demo line</dt>
          <dd>{view.dialable ? 'Dialable' : 'None attached'}</dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">Accepted payers</dt>
          <dd>{facility.accepted_payers.join(', ')}</dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">Sister facilities (directory)</dt>
          <dd className="font-mono">{facility.sister_facility_ids.join(', ') || 'None'}</dd>
        </div>
      </dl>

      <section>
        <h3 className="border-t border-ink/15 pt-4 text-[15px] font-semibold">Directory claim vs phone finding</h3>
        {findings.length === 0 ? (
          <p className="mt-2 text-sm text-ink-muted">No call has checked this facility yet, so the directory is all there is.</p>
        ) : null}
        {(findings.length ? findings : [null]).map((finding, index) => (
          <div key={finding ? finding.runId : index} className="mt-4">
            {finding ? (
              <p className="text-[13px] text-ink-muted">
                <Link to={`/runs/${finding.runId}/calls/${facility.facility_id}`} className="font-medium text-ink underline decoration-hairline underline-offset-4 hover:decoration-ink">
                  {finding.label}
                </Link>{' '}
                · {sourceName(finding.evaluation)} · score <span className="font-mono">{score(finding.evaluation.match_score)}</span>
              </p>
            ) : null}
            <table className="mt-2 w-full border-collapse text-[14px]">
              <thead>
                <tr className="border-b border-hairline text-left text-ink-muted">
                  <th scope="col" className="label-caps py-2 pr-3 font-semibold">Requirement</th>
                  <th scope="col" className="label-caps py-2 pr-3 font-semibold">Directory</th>
                  <th scope="col" className="label-caps py-2 font-semibold">Phone</th>
                </tr>
              </thead>
              <tbody>
                {claims.map((claim) => {
                  const result = finding?.evaluation.findings.find((f) => f.code === claim.code)
                  const contradicted = finding?.evaluation.contradictions.some((c) => c.code === claim.code)
                  return (
                    <tr key={claim.code} className="border-b border-hairline align-top">
                      <th scope="row" className="py-2.5 pr-3 text-left font-normal">{constraintShort[claim.code]}</th>
                      <td className="py-2.5 pr-3">
                        {claim.claimed_available ? 'Available' : 'Not available'}
                        <span className="block text-[12px] text-ink-muted">{date(claim.last_updated)}</span>
                      </td>
                      <td className="py-2.5">
                        {result ? <StateMark state={result.state} /> : <span className="text-ink-muted">Not asked</span>}
                        {contradicted ? <span className="block text-[12px] font-medium text-not-confirmed">≠ contradicts directory</span> : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ))}
        {claims[0] ? <p className="mt-3 text-[12px] text-ink-muted">Directory source: {claims[0].source}.</p> : null}
      </section>
    </div>
  )
}
