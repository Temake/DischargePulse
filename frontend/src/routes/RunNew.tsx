import { useId, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { startRun, type ApiError } from '@/api/client'
import type { RunRecord, StartRunRequest, TelephonyMode } from '@/api/types'
import { useCrumbs } from '@/app/shell/crumbs'
import { PageHeader } from '@/app/shell/PageHeader'
import { Button, ButtonLink } from '@/components/ui/Button'
import { Input } from '@/components/ui/Field'
import { ErrorNote, SkeletonRows } from '@/components/ui/States'
import { keys, useBudget, useFacilities, useHealth, usePatients } from '@/hooks/queries'
import { EXAMPLE_RUN_ID } from '@/landing/data/snapshot'
import { constraintShort, telephonyDescription, telephonyName } from '@/lib/labels'
import { ageSex, miles } from '@/lib/format'
import { cn } from '@/lib/utils'

type UiMode = TelephonyMode | 'hybrid'

const MODES: { value: UiMode; spends: boolean; needsLive: boolean }[] = [
  { value: 'replay', spends: false, needsLive: false },
  { value: 'scripted', spends: false, needsLive: false },
  { value: 'hybrid', spends: true, needsLive: true },
  { value: 'simulated', spends: true, needsLive: true },
  { value: 'live', spends: true, needsLive: true },
  { value: 'auto', spends: false, needsLive: false },
]

const hybridDescription =
  'Dials the facilities you pick live and replays the rest from recordings. Spends credit for each live leg.'

function Block({ index, title, children }: { index: number; title: string; children: ReactNode }) {
  return (
    <section className="grid gap-4 border-t border-ink/15 pt-4 md:grid-cols-[11rem_minmax(0,1fr)] md:gap-8">
      <h2 className="text-[15px] font-semibold">
        <span className="mr-2 font-mono text-[12px] text-ink-muted">{String(index).padStart(2, '0')}</span>
        {title}
      </h2>
      <div className="min-w-0">{children}</div>
    </section>
  )
}

function RadioRow({
  name,
  value,
  checked,
  disabled,
  onChange,
  title,
  meta,
  children,
}: {
  name: string
  value: string
  checked: boolean
  disabled?: boolean
  onChange: () => void
  title: ReactNode
  meta?: ReactNode
  children?: ReactNode
}) {
  return (
    <label
      className={cn(
        'relative grid cursor-pointer grid-cols-[1.25rem_minmax(0,1fr)] gap-x-3 border-b border-hairline py-3 pl-3 pr-2 last:border-b-0',
        checked && 'bg-surface',
        disabled && 'cursor-not-allowed opacity-55',
      )}
    >
      {checked ? <span className="absolute inset-y-0 left-0 w-[2px] bg-accent" aria-hidden="true" /> : null}
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={onChange}
        className="mt-1 size-4 accent-[var(--color-accent)]"
      />
      <span className="min-w-0">
        <span className="flex flex-wrap items-baseline justify-between gap-x-4">
          <span className="text-[15px] font-medium">{title}</span>
          {meta ? <span className="text-[13px] text-ink-muted">{meta}</span> : null}
        </span>
        {children ? <span className="mt-0.5 block text-[13px] leading-relaxed text-ink-muted">{children}</span> : null}
      </span>
    </label>
  )
}

export function RunNew() {
  useCrumbs([{ label: 'Runs', to: '/runs' }, { label: 'Start a run' }])
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const patients = usePatients()
  const facilities = useFacilities()
  const health = useHealth()
  const budget = useBudget()
  const ids = { cycles: useId(), calls: useId(), latency: useId() }

  const [pickedCase, setCaseId] = useState<string>(params.get('case') ?? '')
  const [pickedMode, setMode] = useState<UiMode | null>(null)
  const [liveIds, setLiveIds] = useState<string[]>([])
  const [maxCycles, setMaxCycles] = useState('4')
  const [maxCalls, setMaxCalls] = useState('')
  const [latency, setLatency] = useState('0')

  // Defaults come from the backend, not from the page.
  const caseId = pickedCase || patients.data?.[0]?.case_id || ''
  const mode: UiMode | null = pickedMode ?? health.data?.telephony_mode ?? null

  const liveAvailable = health.data?.live_available ?? false
  const remaining = budget.data?.remaining ?? health.data?.budget.remaining ?? 0
  const selectedMode = MODES.find((m) => m.value === mode)
  const patient = patients.data?.find((p) => p.case_id === caseId)
  const dialable = (facilities.data ?? []).filter((f) => f.dialable)
  const needsCallCeiling = mode === 'live' || mode === 'simulated'
  const usesReplay = mode === 'replay' || mode === 'hybrid' || mode === 'auto'

  const problems = useMemo(() => {
    const list: string[] = []
    if (!caseId) list.push('Choose a case.')
    if (!mode) list.push('Choose a telephony mode.')
    if (selectedMode?.needsLive && !liveAvailable) list.push('Live telephony is not configured on the backend.')
    if (mode === 'hybrid' && liveIds.length === 0) list.push('Pick at least one facility to dial live.')
    if (mode === 'hybrid' && liveIds.length > remaining) list.push(`Only ${remaining} live calls remain in the budget.`)
    const cycles = Number(maxCycles)
    if (!Number.isInteger(cycles) || cycles < 1 || cycles > 10) list.push('Cycles must be a whole number from 1 to 10.')
    if (maxCalls !== '') {
      const calls = Number(maxCalls)
      if (!Number.isInteger(calls) || calls < 1 || calls > 50) list.push('Call ceiling must be a whole number from 1 to 50.')
      else if (needsCallCeiling && calls > remaining) list.push(`This run could place ${calls} calls but only ${remaining} remain.`)
    } else if (needsCallCeiling) {
      list.push('Live and simulated runs need a call ceiling.')
    }
    const lat = Number(latency)
    if (usesReplay && (Number.isNaN(lat) || lat < 0 || lat > 30)) list.push('Replay pacing must be between 0 and 30 seconds.')
    return list
  }, [caseId, mode, selectedMode, liveAvailable, liveIds, remaining, maxCycles, maxCalls, needsCallCeiling, latency, usesReplay])

  const start = useMutation<RunRecord, ApiError, StartRunRequest>({
    mutationFn: startRun,
    onSuccess: (record) => {
      queryClient.setQueryData(keys.run(record.run_id), record)
      void queryClient.invalidateQueries({ queryKey: keys.runs, exact: true })
      navigate(`/runs/${record.run_id}`)
    },
  })

  const submit = () => {
    if (problems.length > 0 || !mode) return
    start.mutate({
      case_id: caseId,
      mode: mode === 'hybrid' ? 'replay' : mode,
      live_facility_ids: mode === 'hybrid' ? liveIds : [],
      max_cycles: Number(maxCycles),
      max_calls: maxCalls === '' ? null : Number(maxCalls),
      replay_latency_seconds: usesReplay ? Number(latency) : 0,
    })
  }

  if (patients.isError || health.isError) {
    return (
      <>
        <PageHeader title="Start a run" />
        <ErrorNote title="The backend is not reachable">
          Start it with <code className="font-mono">uvicorn app.main:app --reload</code> in <code className="font-mono">backend/</code>, then reload.
          You can still watch the <a className="underline underline-offset-4" href={`/runs/${EXAMPLE_RUN_ID}`}>example run</a>.
        </ErrorNote>
      </>
    )
  }

  const spends = selectedMode?.spends ?? false

  return (
    <>
      <PageHeader
        title="Start a run"
        description="Configure one placement run. The agent plans, calls and reasons on its own, then stops at your approval."
      />

      <div className="grid gap-10 pb-16 lg:grid-cols-[minmax(0,1fr)_20rem] xl:gap-14">
        <form
          className="grid content-start gap-8"
          onSubmit={(event) => {
            event.preventDefault()
            submit()
          }}
          id="start-run"
        >
          <Block index={1} title="Case">
            {patients.isLoading ? (
              <SkeletonRows rows={3} />
            ) : (
              <fieldset>
                <legend className="sr-only">Case</legend>
                <div className="border-y border-hairline">
                  {patients.data?.map((p) => (
                    <RadioRow
                      key={p.case_id}
                      name="case"
                      value={p.case_id}
                      checked={caseId === p.case_id}
                      onChange={() => setCaseId(p.case_id)}
                      title={
                        <>
                          <span className="font-mono">{p.case_id}</span>
                          <span className="ml-2 font-normal text-ink-muted">
                            {ageSex(p)} · {p.payer_plan}
                          </span>
                        </>
                      }
                      meta={`${miles(p.search_radius_miles)} → ${miles(p.max_radius_miles)}`}
                    >
                      {p.requirements
                        .filter((r) => r.kind === 'hard')
                        .map((r) => constraintShort[r.code])
                        .join(' · ')}
                    </RadioRow>
                  ))}
                </div>
              </fieldset>
            )}
          </Block>

          <Block index={2} title="Telephony">
            <fieldset>
              <legend className="sr-only">Telephony mode</legend>
              <div className="border-y border-hairline">
                {MODES.map((option) => {
                  const disabled = option.needsLive && !liveAvailable
                  return (
                    <RadioRow
                      key={option.value}
                      name="mode"
                      value={option.value}
                      checked={mode === option.value}
                      disabled={disabled}
                      onChange={() => setMode(option.value)}
                      title={telephonyName(option.value)}
                      meta={
                        disabled
                          ? 'Unavailable: no CALL-E key'
                          : option.value === health.data?.telephony_mode
                            ? 'Backend default'
                            : option.spends
                              ? 'Spends credit'
                              : undefined
                      }
                    >
                      {option.value === 'hybrid' ? hybridDescription : telephonyDescription[option.value as TelephonyMode]}
                    </RadioRow>
                  )
                })}
              </div>
            </fieldset>

            {mode === 'hybrid' ? (
              <fieldset className="mt-5">
                <legend className="text-sm font-medium">Dial live</legend>
                {dialable.length === 0 ? (
                  <p className="mt-1 text-[13px] text-ink-muted">
                    No facility has a demo receiver number. Set DEMO_PHONE_PRIMARY or DEMO_PHONE_SECONDARY on the backend.
                  </p>
                ) : (
                  <ul className="mt-2 grid gap-1">
                    {dialable.map(({ facility }) => (
                      <li key={facility.facility_id}>
                        <label className="flex min-h-11 items-center gap-3 text-[14px] pointer-fine:min-h-9">
                          <input
                            type="checkbox"
                            className="size-4 accent-[var(--color-accent)]"
                            checked={liveIds.includes(facility.facility_id)}
                            onChange={(event) =>
                              setLiveIds((prev) =>
                                event.target.checked
                                  ? [...prev, facility.facility_id]
                                  : prev.filter((id) => id !== facility.facility_id),
                              )
                            }
                          />
                          <span className="font-mono text-[13px]">{facility.facility_id}</span>
                          {facility.name}
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </fieldset>
            ) : null}
          </Block>

          <Block index={3} title="Limits">
            <div className="grid gap-5 sm:grid-cols-3">
              <div className="grid content-start gap-1.5">
                <label htmlFor={ids.cycles} className="text-sm font-medium">
                  Max cycles
                </label>
                <Input id={ids.cycles} type="number" min={1} max={10} inputMode="numeric" value={maxCycles} onChange={(e) => setMaxCycles(e.target.value)} className="font-mono" />
                <p className="text-[13px] text-ink-muted">Plan-to-replan loops. 1 to 10.</p>
              </div>
              <div className="grid content-start gap-1.5">
                <label htmlFor={ids.calls} className="text-sm font-medium">
                  Call ceiling{needsCallCeiling ? '' : ' (optional)'}
                </label>
                <Input
                  id={ids.calls}
                  type="number"
                  min={1}
                  max={50}
                  inputMode="numeric"
                  value={maxCalls}
                  onChange={(e) => setMaxCalls(e.target.value)}
                  className="font-mono"
                  required={needsCallCeiling}
                />
                <p className="text-[13px] text-ink-muted">Facilities this run may check. Required when calls are placed.</p>
              </div>
              <div className={cn('grid content-start gap-1.5', !usesReplay && 'opacity-50')}>
                <label htmlFor={ids.latency} className="text-sm font-medium">
                  Replay pacing (s)
                </label>
                <Input
                  id={ids.latency}
                  type="number"
                  min={0}
                  max={30}
                  step={0.5}
                  value={latency}
                  onChange={(e) => setLatency(e.target.value)}
                  disabled={!usesReplay}
                  className="font-mono"
                />
                <p className="text-[13px] text-ink-muted">Delay per replayed call, for watching the loop. 0 to 30.</p>
              </div>
            </div>
          </Block>
        </form>

        {/* Review: persistent summary */}
        <aside className="lg:sticky lg:top-20 lg:self-start" aria-labelledby="review-heading">
          <div className="border-t border-ink/15 pt-4">
            <h2 id="review-heading" className="text-[15px] font-semibold">
              <span className="mr-2 font-mono text-[12px] text-ink-muted">04</span>Review
            </h2>
            <dl className="mt-3 divide-y divide-hairline border-y border-hairline text-[14px]">
              <div className="flex justify-between gap-4 py-2.5">
                <dt className="text-ink-muted">Case</dt>
                <dd className="text-right">
                  {patient ? (
                    <>
                      <span className="font-mono">{patient.case_id}</span>
                      <span className="block text-[13px] text-ink-muted">{patient.display_name}</span>
                    </>
                  ) : (
                    '--'
                  )}
                </dd>
              </div>
              <div className="flex justify-between gap-4 py-2.5">
                <dt className="text-ink-muted">Telephony</dt>
                <dd>{mode ? telephonyName(mode) : '--'}</dd>
              </div>
              <div className="flex justify-between gap-4 py-2.5">
                <dt className="text-ink-muted">Places real calls</dt>
                <dd>{spends ? `Yes${mode === 'hybrid' ? `, ${liveIds.length}` : ''}` : 'No'}</dd>
              </div>
              <div className="flex justify-between gap-4 py-2.5">
                <dt className="text-ink-muted">Limits</dt>
                <dd className="text-right font-mono text-[13px] tabular-nums">
                  {maxCycles} cycles · {maxCalls || 'no'} call cap
                </dd>
              </div>
              <div className="flex justify-between gap-4 py-2.5">
                <dt className="text-ink-muted">Budget left</dt>
                <dd className="font-mono tabular-nums">
                  {budget.data ? `${budget.data.remaining} / ${budget.data.ceiling}` : '--'}
                </dd>
              </div>
            </dl>

            {problems.length > 0 && (start.isIdle || start.isError) ? (
              <ul className="mt-3 grid gap-1 text-[13px] text-ink-muted" aria-live="polite">
                {problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            ) : null}

            {start.error ? (
              <p role="alert" className="mt-3 border-l-2 border-unavailable pl-3 text-[13px]">
                {start.error.message}
              </p>
            ) : null}

            <Button type="submit" form="start-run" className="mt-4 w-full" disabled={problems.length > 0 || start.isPending}>
              {start.isPending ? 'Starting…' : spends ? 'Start run and place calls' : 'Start run'}
            </Button>
            <p className="mt-3 text-[13px] leading-relaxed text-ink-muted">
              The agent never sends a referral. It stops with a proposal for you to approve or decline.
            </p>
            <ButtonLink to={`/runs/${EXAMPLE_RUN_ID}`} variant="ghost" size="sm" className="-ml-3 mt-2">
              Watch the example run instead
            </ButtonLink>
          </div>
        </aside>
      </div>
    </>
  )
}
