import { Link, useParams } from 'react-router'
import { ArrowLeft } from '@phosphor-icons/react'

import type { Facility, FacilityEvaluation, RunRecord } from '@/api/types'
import { ContradictionBanner } from '@/agent/ContradictionBanner'
import { ProvenanceBadge } from '@/agent/ProvenanceBadge'
import { sourceName } from '@/agent/runSelectors'
import { StateMark } from '@/agent/StateChip'
import { TranscriptPlayback } from '@/agent/TranscriptPlayback'
import { useCrumbs } from '@/app/shell/crumbs'
import { PageSection } from '@/app/shell/PageHeader'
import { Empty, ErrorNote, SkeletonRows } from '@/components/ui/States'
import { useFacilityIndex, useRun } from '@/hooks/queries'
import { EXAMPLE_RUN_ID, snapshotFacilities, snapshotRecord } from '@/landing/data/snapshot'
import { clock, date, dateTime, miles, score } from '@/lib/format'
import { dispositionLabel, dispositionTone, HARD_ORDER, verificationLabel } from '@/lib/labels'
import { cn } from '@/lib/utils'

export function CallDetail() {
  const { runId = '', facilityId = '' } = useParams()
  const example = runId === EXAMPLE_RUN_ID
  const run = useRun(example ? undefined : runId)
  const apiFacilities = useFacilityIndex()
  const record: RunRecord | undefined = example ? snapshotRecord : run.data
  const facilities = example ? snapshotFacilities : apiFacilities
  const facility = facilities.get(facilityId)

  useCrumbs([
    { label: 'Runs', to: '/runs' },
    { label: example ? 'Example run' : runId, to: `/runs/${runId}` },
    { label: facility?.name ?? facilityId },
  ])

  if (!example && run.isLoading) return <SkeletonRows rows={6} />
  if (!example && run.isError) return <ErrorNote title="Could not load the run">{(run.error as Error).message}</ErrorNote>

  const evaluation = record?.run.evaluations.find((e) => e.facility_id === facilityId)

  return (
    <div className="pb-16">
      <Link
        to={`/runs/${runId}`}
        className="-ml-1 inline-flex min-h-11 items-center gap-1.5 text-[14px] text-ink-muted hover:text-ink pointer-fine:min-h-8"
      >
        <ArrowLeft size={14} aria-hidden="true" /> Back to run
      </Link>
      {evaluation ? (
        <CallRecord evaluation={evaluation} facility={facility} example={example} />
      ) : (
        <Empty title="No call record for this facility in this run">
          The agent may not have reached this facility yet, or it was excluded before any call.
        </Empty>
      )}
    </div>
  )
}

function CallRecord({ evaluation, facility, example }: { evaluation: FacilityEvaluation; facility?: Facility; example: boolean }) {
  const observation = evaluation.observation
  const findings = [...evaluation.findings].sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'hard' ? -1 : 1
    return HARD_ORDER.indexOf(a.code) - HARD_ORDER.indexOf(b.code)
  })
  const claims = new Map(facility?.directory_claims.map((c) => [c.code, c]) ?? [])
  const found = evaluation.contradictions.map((contradiction) => ({ evaluation, contradiction }))

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 pb-6 pt-2">
        <div className="min-w-0">
          <p className="text-[13px] text-ink-muted">
            <span className="font-mono">{evaluation.facility_id}</span>
            {facility ? ` · ${miles(facility.distance_miles)} · ${facility.facility_type}` : null}
            {example ? ' · example run' : null}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-[-0.02em] sm:text-[28px]">{evaluation.facility_name}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[14px]">
            <span className={cn('font-medium', dispositionTone[evaluation.disposition])}>
              {dispositionLabel[evaluation.disposition]}
            </span>
            <span className="text-ink-muted">
              Score <span className="font-mono tabular-nums text-ink">{score(evaluation.match_score)}</span>
            </span>
            {observation ? <ProvenanceBadge mode={observation.mode} answersSource={observation.answers_source} /> : null}
          </p>
        </div>
      </header>

      {found.length > 0 ? <ContradictionBanner found={found} facilities={new Map(facility ? [[facility.facility_id, facility]] : [])} className="mb-8" /> : null}

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <div className="grid content-start gap-9">
          <PageSection title="Findings" meta="Directory claim against what this call established">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full min-w-[520px] border-collapse text-[14px]">
                <thead>
                  <tr className="border-b border-hairline text-left text-ink-muted">
                    <th scope="col" className="label-caps py-2 pr-4 font-semibold">Requirement</th>
                    <th scope="col" className="label-caps py-2 pr-4 font-semibold">Directory</th>
                    <th scope="col" className="label-caps py-2 font-semibold">{sourceName(evaluation)}</th>
                  </tr>
                </thead>
                <tbody>
                  {findings.map((finding) => {
                    const claim = claims.get(finding.code)
                    const contradicted = evaluation.contradictions.some((c) => c.code === finding.code)
                    return (
                      <tr key={finding.code} className="border-b border-hairline align-top">
                        <th scope="row" className="py-3 pr-4 text-left font-normal">
                          {finding.label}
                          <span className="block text-[12px] text-ink-muted">{finding.kind === 'hard' ? 'Hard requirement' : 'Preference'}</span>
                        </th>
                        <td className="py-3 pr-4 text-ink-muted">
                          {claim ? (
                            <>
                              <span className="text-ink">{claim.claimed_available ? 'Available' : 'Not available'}</span>
                              <span className="block text-[12px]">Updated {date(claim.last_updated)}</span>
                            </>
                          ) : (
                            'No claim'
                          )}
                        </td>
                        <td className="py-3">
                          <StateMark state={finding.state} />
                          {contradicted ? <span className="ml-2 text-[12px] font-medium text-not-confirmed">≠ directory</span> : null}
                          <span className="mt-0.5 block text-[13px] text-ink-muted">{finding.rationale}</span>
                          {finding.quote ? <span className="mt-1 block text-[13px]">“{finding.quote}”</span> : null}
                          <span className="sr-only">{verificationLabel[finding.state]}</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </PageSection>

          <PageSection title="Admissions contact">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[14px] sm:grid-cols-3">
              <div>
                <dt className="text-[13px] text-ink-muted">Coordinator</dt>
                <dd>{evaluation.coordinator_name || 'Not given'}</dd>
              </div>
              <div>
                <dt className="text-[13px] text-ink-muted">Callback</dt>
                <dd className="font-mono">{evaluation.callback_number || 'Not given'}</dd>
              </div>
              <div>
                <dt className="text-[13px] text-ink-muted">Referral fax</dt>
                <dd className="font-mono">{evaluation.fax_number || 'Not given'}</dd>
              </div>
            </dl>
          </PageSection>

          {evaluation.sister_facility_leads.length > 0 || evaluation.ownership_leads.length > 0 ? (
            <PageSection title="Leads">
              <dl className="grid gap-3 text-[14px]">
                {evaluation.sister_facility_leads.length > 0 ? (
                  <div>
                    <dt className="text-[13px] text-ink-muted">Named by {sourceName(evaluation).toLowerCase()}</dt>
                    <dd className="font-mono">{evaluation.sister_facility_leads.join(', ')}</dd>
                  </div>
                ) : null}
                {evaluation.ownership_leads.length > 0 ? (
                  <div>
                    <dt className="text-[13px] text-ink-muted">Same owner, from the directory only (not call evidence)</dt>
                    <dd className="font-mono">{evaluation.ownership_leads.join(', ')}</dd>
                  </div>
                ) : null}
              </dl>
            </PageSection>
          ) : null}
        </div>

        <div className="grid content-start gap-9">
          <PageSection title="Call">
            {observation ? (
              <>
                <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[14px]">
                  <div>
                    <dt className="text-[13px] text-ink-muted">Outcome</dt>
                    <dd className="capitalize">{observation.outcome.replace('_', ' ')}</dd>
                  </div>
                  <div>
                    <dt className="text-[13px] text-ink-muted">Duration</dt>
                    <dd className="font-mono tabular-nums">{observation.duration_seconds != null ? clock(observation.duration_seconds) : 'None'}</dd>
                  </div>
                  <div>
                    <dt className="text-[13px] text-ink-muted">CALL-E call id</dt>
                    <dd className="break-all font-mono text-[13px]">{observation.call_id ?? 'None'}</dd>
                  </div>
                  <div>
                    <dt className="text-[13px] text-ink-muted">Confidence</dt>
                    <dd>
                      {observation.confidence_score != null ? (
                        <span className="font-mono tabular-nums">{observation.confidence_score.toFixed(2)}</span>
                      ) : (
                        'None'
                      )}
                      {observation.confidence_label ? <span className="text-ink-muted"> {observation.confidence_label}</span> : null}
                    </dd>
                  </div>
                  {observation.started_at ? (
                    <div className="col-span-2">
                      <dt className="text-[13px] text-ink-muted">Placed</dt>
                      <dd className="font-mono text-[13px] tabular-nums">{dateTime(observation.started_at)}</dd>
                    </div>
                  ) : null}
                </dl>
                {observation.summary ? <p className="mt-4 text-[14px] leading-relaxed">{observation.summary}</p> : null}
                {observation.failure_message ? (
                  <p className="mt-3 text-[13px] text-unavailable">{observation.failure_message}</p>
                ) : null}
                {observation.evidence.length > 0 ? (
                  <ul className="mt-3 grid list-disc gap-1 pl-5 text-[13px] text-ink-muted">
                    {observation.evidence.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                ) : null}
                {observation.answers_source === 'simulated' && observation.call_structured_result ? (
                  <details className="mt-4 text-[13px]">
                    <summary className="cursor-pointer py-1 font-medium">What the call itself extracted</summary>
                    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-mono text-[12px]">
                      {Object.entries(observation.call_structured_result).map(([key, value]) => (
                        <div key={key} className="contents">
                          <dt className="text-ink-muted">{key}</dt>
                          <dd>{String(value) || '""'}</dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-ink-muted">No observation was recorded.</p>
            )}
          </PageSection>

          <PageSection title="Transcript">
            <TranscriptPlayback observation={observation} />
          </PageSection>
        </div>
      </div>
    </>
  )
}
