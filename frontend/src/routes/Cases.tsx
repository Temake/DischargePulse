import { Link, useParams } from 'react-router'

import { RunStatusText } from '@/agent/RunWorkbench'
import { useCrumbs } from '@/app/shell/crumbs'
import { PageHeader, PageSection } from '@/app/shell/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { Empty, ErrorNote, SkeletonRows } from '@/components/ui/States'
import { usePatient, usePatients, useRuns } from '@/hooks/queries'
import { ageSex, dateTime, miles } from '@/lib/format'
import { constraintShort, telephonyName } from '@/lib/labels'

export function Cases() {
  useCrumbs([{ label: 'Cases' }])
  const patients = usePatients()

  return (
    <>
      <PageHeader title="Cases" description="Patients ready for discharge who need post-acute placement. All synthetic." />
      {patients.isLoading ? (
        <SkeletonRows rows={4} />
      ) : patients.isError ? (
        <ErrorNote title="Could not load cases">{(patients.error as Error).message}</ErrorNote>
      ) : (
        <ul className="divide-y divide-hairline border-y border-ink/15">
          {patients.data?.map((p) => {
            const hard = p.requirements.filter((r) => r.kind === 'hard' && r.code !== 'payer_network' && r.code !== 'staffed_bed')
            return (
              <li key={p.case_id}>
                <Link
                  to={`/cases/${p.case_id}`}
                  className="grid gap-x-8 gap-y-1 py-4 transition-colors hover:bg-surface-2/50 sm:grid-cols-[6rem_minmax(0,1fr)_auto] sm:px-2"
                >
                  <span className="font-mono text-[15px] font-medium">{p.case_id}</span>
                  <span className="min-w-0">
                    <span className="block text-[15px]">
                      {ageSex(p)} · {p.payer_plan}
                    </span>
                    <span className="block text-[14px] text-ink-muted">
                      {hard.map((r) => r.detail.split(',')[0]).join(' · ') || hard.map((r) => constraintShort[r.code]).join(' · ')}
                    </span>
                  </span>
                  <span className="font-mono text-[14px] tabular-nums text-ink-muted sm:text-right">
                    {miles(p.search_radius_miles)} → {miles(p.max_radius_miles)}
                    <span className="block font-sans text-[13px]">from {p.family_zip}</span>
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}

export function CaseDetail() {
  const { caseId = '' } = useParams()
  const patient = usePatient(caseId)
  const runs = useRuns()
  useCrumbs([{ label: 'Cases', to: '/cases' }, { label: caseId }])

  if (patient.isLoading) return <SkeletonRows rows={6} />
  if (patient.isError || !patient.data) {
    return (
      <Empty title={`No case ${caseId}`} action={<ButtonLink to="/cases" variant="secondary">All cases</ButtonLink>}>
        The backend has no synthetic patient with this id.
      </Empty>
    )
  }

  const p = patient.data
  const caseRuns = (runs.data ?? []).filter((r) => r.case_id === caseId)

  return (
    <div className="pb-16">
      <PageHeader
        title={p.display_name}
        description={
          <>
            Case <span className="font-mono text-ink">{p.case_id}</span> · {ageSex(p)} · {p.payer} · hospital day{' '}
            {p.hospital_day}
          </>
        }
        actions={<ButtonLink to={`/runs/new?case=${p.case_id}`}>Start a run for this case</ButtonLink>}
      />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="grid content-start gap-9">
          <PageSection title="Discharge summary">
            <p className="max-w-[68ch] text-[15px] leading-relaxed">{p.discharge_summary}</p>
          </PageSection>

          <PageSection title="Requirements" meta="Hard requirements disqualify; preferences only rank">
            <div className="scrollbar-thin overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-[14px]">
                <thead>
                  <tr className="border-b border-hairline text-left text-ink-muted">
                    <th scope="col" className="label-caps py-2 pr-4 font-semibold">Requirement</th>
                    <th scope="col" className="label-caps py-2 pr-4 font-semibold">Kind</th>
                    <th scope="col" className="label-caps py-2 font-semibold">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {p.requirements.map((r) => (
                    <tr key={r.code} className="border-b border-hairline align-top">
                      <th scope="row" className="py-2.5 pr-4 text-left font-medium">{r.label}</th>
                      <td className="py-2.5 pr-4 text-ink-muted">{r.kind === 'hard' ? 'Hard' : 'Preference'}</td>
                      <td className="py-2.5">
                        {r.detail}
                        {r.ask_as ? <span className="mt-0.5 block text-[13px] text-ink-muted">Asked as: {r.ask_as}</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </PageSection>
        </div>

        <div className="grid content-start gap-9">
          <PageSection title="Search">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[14px]">
              <div>
                <dt className="text-[13px] text-ink-muted">Family zip</dt>
                <dd className="font-mono">{p.family_zip}</dd>
              </div>
              <div>
                <dt className="text-[13px] text-ink-muted">Radius</dt>
                <dd className="font-mono tabular-nums">
                  {miles(p.search_radius_miles)} → {miles(p.max_radius_miles)}
                </dd>
              </div>
              <div>
                <dt className="text-[13px] text-ink-muted">Payer plan</dt>
                <dd>{p.payer_plan}</dd>
              </div>
              <div>
                <dt className="text-[13px] text-ink-muted">Weight</dt>
                <dd className="font-mono tabular-nums">{p.weight_lbs} lb</dd>
              </div>
            </dl>
          </PageSection>

          <PageSection title="Runs for this case">
            {caseRuns.length === 0 ? (
              <p className="text-sm text-ink-muted">No runs for this case since the backend started.</p>
            ) : (
              <ul className="divide-y divide-hairline text-[14px]">
                {caseRuns.map((run) => (
                  <li key={run.run_id}>
                    <Link to={`/runs/${run.run_id}`} className="flex flex-wrap items-baseline justify-between gap-x-4 py-2.5 hover:bg-surface-2/50">
                      <RunStatusText status={run.status} />
                      <span className="text-ink-muted">
                        {telephonyName(run.telephony)} · <span className="font-mono text-[13px]">{dateTime(run.started_at)}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PageSection>
        </div>
      </div>
    </div>
  )
}
