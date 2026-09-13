import { useMemo } from 'react'
import { useParams } from 'react-router'

import type { ApiError } from '@/api/client'
import { RunWorkbench } from '@/agent/RunWorkbench'
import { useRunTimeline } from '@/agent/useRunTimeline'
import { viewAtEvents, viewFromRecord } from '@/agent/runSelectors'
import { useCrumbs } from '@/app/shell/crumbs'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Empty, ErrorNote, SkeletonRows } from '@/components/ui/States'
import { useFacilityIndex, usePatient, useRun } from '@/hooks/queries'
import { useRunStream } from '@/hooks/useRunStream'
import {
  EXAMPLE_RUN_ID,
  snapshot,
  snapshotEvents,
  snapshotFacilities,
  snapshotRecord,
} from '@/landing/data/snapshot'
import type { StreamStatus } from '@/api/stream'

export function Run() {
  const { runId = '' } = useParams()
  return runId === EXAMPLE_RUN_ID ? <ExampleRun /> : <LiveRun runId={runId} />
}

const streamText: Record<StreamStatus, string> = {
  connecting: 'Connecting to run stream',
  open: 'Receiving live events',
  reconnecting: 'Reconnecting to run stream',
  closed: 'Run finished, stream closed',
  unavailable: 'Live updates unavailable',
}

function LiveRun({ runId }: { runId: string }) {
  useCrumbs([{ label: 'Runs', to: '/runs' }, { label: runId }])
  const run = useRun(runId)
  const stream = useRunStream(run.isError ? null : runId)
  const patient = usePatient(run.data?.case_id)
  const facilities = useFacilityIndex()

  const view = useMemo(
    () => (run.data ? viewFromRecord(run.data, stream.hello ? stream.events : undefined) : null),
    [run.data, stream.hello, stream.events],
  )

  if (run.isError) {
    const status = (run.error as ApiError).status
    return status === 404 ? (
      <Empty
        title="This run is not on the backend"
        action={<ButtonLink to="/runs/new">Start a run</ButtonLink>}
      >
        Runs live in memory, so a backend restart clears them. The id may also be mistyped.
      </Empty>
    ) : (
      <ErrorNote title="Could not load the run">{(run.error as Error).message}</ErrorNote>
    )
  }

  if (!view) {
    return (
      <div className="grid gap-6 py-4">
        <SkeletonRows rows={2} className="max-w-md" />
        <SkeletonRows rows={6} />
      </div>
    )
  }

  const quietStream = stream.status === 'closed' || stream.status === 'open'

  return (
    <RunWorkbench
      view={view}
      patient={patient.data}
      facilities={facilities}
      approvalMode={{ kind: 'live', runId }}
      callHref={(facilityId) => `/runs/${runId}/calls/${facilityId}`}
      controls={
        <p className={quietStream ? 'text-[13px] text-ink-muted' : 'text-[13px] text-not-confirmed'} role="status">
          {streamText[stream.status]}
        </p>
      }
    />
  )
}

function ExampleRun() {
  useCrumbs([{ label: 'Runs', to: '/runs' }, { label: 'Example run' }])
  const timeline = useRunTimeline(snapshotEvents, { active: true, stepMs: 1100 })
  const view = useMemo(() => viewAtEvents(snapshotRecord, timeline.shown), [timeline.shown])

  return (
    <RunWorkbench
      view={view}
      patient={snapshot.patient}
      facilities={snapshotFacilities}
      approvalMode={{ kind: 'demo' }}
      callHref={(facilityId) => `/runs/${EXAMPLE_RUN_ID}/calls/${facilityId}`}
      timers={false}
      notice={
        <div className="mb-5 flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-hairline pb-3 text-[13px]">
          <span className="font-mono text-[11px] font-medium tracking-[0.06em] text-ink">SCRIPTED</span>
          <span className="font-medium">Example run. {snapshot.label}.</span>
          <span className="text-ink-muted">{snapshot.disclaimer}</span>
        </div>
      }
      controls={
        <>
          <p className="text-[13px] text-ink-muted" role="status">
            Event <span className="font-mono tabular-nums text-ink">{timeline.count}</span> of{' '}
            <span className="font-mono tabular-nums">{snapshotEvents.length}</span>
          </p>
          {timeline.finished ? (
            <Button variant="secondary" onClick={timeline.restart}>
              Play again
            </Button>
          ) : (
            <Button variant="secondary" onClick={timeline.skipToEnd}>
              Skip to end
            </Button>
          )}
        </>
      }
    />
  )
}
