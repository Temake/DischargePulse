import type { ReactNode } from 'react'

import { useCrumbs } from '@/app/shell/crumbs'
import { PageHeader } from '@/app/shell/PageHeader'
import { SkeletonRows } from '@/components/ui/States'
import { useBudget, useHealth, useRuns } from '@/hooks/queries'
import { telephonyDescription, telephonyName } from '@/lib/labels'
import { isActive } from '@/agent/runSelectors'
import { cn } from '@/lib/utils'

function Row({ label, value, note, tone }: { label: string; value: ReactNode; note?: ReactNode; tone?: 'ok' | 'warn' | 'bad' }) {
  return (
    <div className="grid gap-x-8 gap-y-0.5 border-b border-hairline py-3.5 sm:grid-cols-[12rem_minmax(0,16rem)_minmax(0,1fr)]">
      <dt className="text-[14px] text-ink-muted">{label}</dt>
      <dd className="flex items-center gap-2 text-[15px] font-medium">
        {tone ? (
          <span
            className={cn('size-2 rounded-full', tone === 'ok' ? 'bg-confirmed' : tone === 'warn' ? 'bg-not-confirmed' : 'bg-unavailable')}
            aria-hidden="true"
          />
        ) : null}
        {value}
      </dd>
      {note ? <dd className="text-[13px] text-ink-muted">{note}</dd> : null}
    </div>
  )
}

export function System() {
  useCrumbs([{ label: 'System' }])
  const health = useHealth()
  const budget = useBudget()
  const runs = useRuns()
  const b = budget.data ?? health.data?.budget
  const active = (runs.data ?? []).filter((r) => isActive(r.status)).length

  return (
    <>
      <PageHeader title="System" description="What the backend reports right now. Nothing on this page is estimated." />
      {health.isLoading ? (
        <SkeletonRows rows={6} className="max-w-2xl" />
      ) : (
        <dl className="max-w-5xl border-t border-ink/15">
          <Row
            label="API"
            value={health.isError ? 'Unreachable' : 'Operational'}
            tone={health.isError ? 'bad' : 'ok'}
            note={health.isError ? 'Start the FastAPI backend on port 8000.' : `GET /api/health returned "${health.data?.status}".`}
          />
          {health.data ? (
            <>
              <Row
                label="Telephony"
                value={telephonyName(health.data.telephony_mode)}
                note={telephonyDescription[health.data.telephony_mode]}
              />
              <Row
                label="Live calls"
                value={health.data.live_available ? 'Available' : 'Unavailable'}
                tone={health.data.live_available ? 'ok' : 'warn'}
                note={health.data.live_available ? 'A CALL-E key is configured.' : 'No CALL-E key configured. Runs can replay or use the scripted attendant.'}
              />
              {b ? (
                <Row
                  label="Call budget"
                  value={
                    <span className="font-mono tabular-nums">
                      {b.spent} / {b.ceiling}
                    </span>
                  }
                  tone={b.remaining <= 2 ? 'bad' : b.remaining <= 5 ? 'warn' : undefined}
                  note={`${b.remaining} live calls remain. Checked before every dial.`}
                />
              ) : null}
              <Row
                label="Recorded calls"
                value={<span className="font-mono tabular-nums">{health.data.cassettes}</span>}
                note="Cassettes available to replay mode."
              />
              <Row
                label="Synthetic data"
                value={health.data.synthetic_data_only ? 'Yes' : 'No'}
                note="All patient and facility records are synthetic."
              />
            </>
          ) : null}
          <Row
            label="Runs in memory"
            value={<span className="font-mono tabular-nums">{runs.data?.length ?? '--'}</span>}
            note={`${active} active. A backend restart clears every run.`}
          />
        </dl>
      )}
    </>
  )
}
