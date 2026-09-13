import { Link, useNavigate } from 'react-router'

import type { RunSummary } from '@/api/types'
import { RunStatusText } from '@/agent/RunWorkbench'
import { isActive } from '@/agent/runSelectors'
import { useCrumbs } from '@/app/shell/crumbs'
import { PageHeader } from '@/app/shell/PageHeader'
import { ButtonLink } from '@/components/ui/Button'
import { Empty, ErrorNote, SkeletonRows } from '@/components/ui/States'
import { useRuns } from '@/hooks/queries'
import { useNow } from '@/hooks/useNow'
import { EXAMPLE_RUN_ID, snapshotRecord } from '@/landing/data/snapshot'
import { clock, dateTime, secondsBetween } from '@/lib/format'
import { telephonyName } from '@/lib/labels'
import { cn } from '@/lib/utils'

function outcome(run: RunSummary): string {
  if (run.proposed_facility) {
    const verb = run.status === 'approved' ? 'Approved' : run.status === 'declined' ? 'Declined' : 'Proposed'
    return `${verb}: ${run.proposed_facility}`
  }
  if (run.status === 'no_match_found') return 'No verified match'
  if (run.status === 'failed') return 'Run failed'
  return 'In progress'
}

export function Runs() {
  useCrumbs([{ label: 'Runs' }])
  const runs = useRuns()
  const navigate = useNavigate()
  const anyActive = (runs.data ?? []).some((r) => isActive(r.status) && !r.finished_at)
  const now = useNow(anyActive)

  return (
    <>
      <PageHeader
        title="Runs"
        description="Every placement run since the backend started. Runs live in memory and clear on restart."
        actions={<ButtonLink to="/runs/new">Start a run</ButtonLink>}
      />

      {runs.isLoading ? (
        <SkeletonRows rows={5} />
      ) : runs.isError ? (
        <ErrorNote title="Could not load runs">{(runs.error as Error).message}</ErrorNote>
      ) : runs.data && runs.data.length > 0 ? (
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full min-w-[860px] border-collapse text-[14px]">
            <caption className="sr-only">Placement runs, newest first</caption>
            <thead>
              <tr className="border-b border-ink/15 text-left text-ink-muted">
                {['Status', 'Case', 'Mode', 'Calls', 'Cycles', 'Started', 'Duration', 'Outcome'].map((h) => (
                  <th
                    key={h}
                    scope="col"
                    className={cn('label-caps py-2 pr-4 font-semibold', (h === 'Calls' || h === 'Cycles' || h === 'Duration') && 'text-right')}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.data.map((run) => {
                const active = isActive(run.status)
                const duration = secondsBetween(run.started_at, run.finished_at ?? new Date(now).toISOString())
                return (
                  <tr
                    key={run.run_id}
                    onClick={(event) => {
                      if ((event.target as HTMLElement).closest('a')) return
                      navigate(`/runs/${run.run_id}`)
                    }}
                    className={cn(
                      'cursor-pointer border-b border-hairline transition-colors hover:bg-surface-2/60',
                      active && 'bg-accent-tint/40',
                    )}
                  >
                    <td className="relative py-3 pr-4">
                      {active ? <span className="absolute inset-y-0 left-0 w-[2px] bg-accent" aria-hidden="true" /> : null}
                      <Link to={`/runs/${run.run_id}`} className="pl-2.5 hover:underline hover:underline-offset-4">
                        <RunStatusText status={run.status} />
                        <span className="sr-only">, open run {run.run_id}</span>
                      </Link>
                    </td>
                    <td className="py-3 pr-4">
                      <span className="font-mono">{run.case_id}</span>
                      <span className="block font-mono text-[12px] text-ink-muted">{run.run_id}</span>
                    </td>
                    <td className="py-3 pr-4">
                      {telephonyName(run.telephony)}
                      {run.live_calls > 0 ? <span className="block text-[12px] text-ink-muted">{run.live_calls} live</span> : null}
                    </td>
                    <td className="py-3 pr-4 text-right font-mono tabular-nums">{run.calls_placed}</td>
                    <td className="py-3 pr-4 text-right font-mono tabular-nums">{run.cycles_used}</td>
                    <td className="py-3 pr-4 font-mono text-[13px] tabular-nums">{dateTime(run.started_at)}</td>
                    <td className="py-3 pr-4 text-right font-mono tabular-nums">
                      {run.status === 'awaiting_approval' && !run.finished_at ? (
                        <span className="font-sans text-[13px] text-ink-muted">Waiting</span>
                      ) : (
                        clock(duration)
                      )}
                    </td>
                    <td className="py-3 pr-4">{outcome(run)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title="No runs since the backend started"
          action={
            <div className="flex flex-wrap gap-3">
              <ButtonLink to="/runs/new">Start a run</ButtonLink>
              <ButtonLink to={`/runs/${EXAMPLE_RUN_ID}`} variant="secondary">
                Watch the example run
              </ButtonLink>
            </div>
          }
        >
          Runs live in memory, so a backend restart clears this list.
        </Empty>
      )}

      <p className="mt-8 border-t border-hairline pt-4 text-[13px] text-ink-muted">
        Example run, not stored on the backend:{' '}
        <Link to={`/runs/${EXAMPLE_RUN_ID}`} className="text-ink underline decoration-hairline underline-offset-4 hover:decoration-ink">
          case {snapshotRecord.case_id}, scripted
        </Link>
        . Simulated call answers, real agent logic.
      </p>
    </>
  )
}
