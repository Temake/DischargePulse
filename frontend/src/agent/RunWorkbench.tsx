import { useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowRight } from '@phosphor-icons/react'

import type { Facility, PatientCase, RunStatus } from '@/api/types'
import { Button } from '@/components/ui/Button'
import { ErrorNote } from '@/components/ui/States'
import { ageSex, dateTime, miles, plural, time } from '@/lib/format'
import {
  dispositionLabel,
  dispositionTone,
  phaseLabel,
  runStatusLabel,
  telephonyName,
} from '@/lib/labels'
import { cn } from '@/lib/utils'
import { ApprovalSheet, type ApprovalMode } from './ApprovalSheet'
import { BedIntelligenceMatrix } from './BedIntelligenceMatrix'
import { CallLanes } from './CallLanes'
import { ContradictionBanner } from './ContradictionBanner'
import { LoopTrack } from './LoopTrack'
import { RadiusMap } from './RadiusMap'
import { ReasoningTrace } from './ReasoningTrace'
import { contradictionsOf, currentPhase, lanesFrom, type RunView } from './runSelectors'
import { TranscriptPlayback } from './TranscriptPlayback'

export function PanelHeading({ children, meta, className }: { children: ReactNode; meta?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-baseline justify-between gap-3 pb-2', className)}>
      <h2 className="text-[13px] font-semibold">{children}</h2>
      {meta ? <p className="text-[12px] text-ink-muted">{meta}</p> : null}
    </div>
  )
}

const statusTone: Record<RunStatus, string> = {
  running: 'bg-accent',
  awaiting_approval: 'bg-accent',
  no_match_found: 'bg-not-confirmed',
  approved: 'bg-confirmed',
  declined: 'bg-ink-muted',
  failed: 'bg-unavailable',
}

export function RunStatusText({ status, className }: { status: RunStatus; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <span className={cn('size-2 shrink-0 rounded-full', statusTone[status])} aria-hidden="true" />
      {runStatusLabel[status]}
    </span>
  )
}

/** Screen-reader narration of the loop: one polite announcement per real event. */
function RunAnnouncer({ view }: { view: RunView }) {
  const last = view.events[view.events.length - 1]
  return (
    <p className="sr-only" aria-live="polite" aria-atomic="true">
      {last ? `${phaseLabel[last.phase]}. ${last.message}` : ''}
    </p>
  )
}

/**
 * The live run page, as a workbench.
 *
 *   patient + plan      calls + bed intelligence      reasoning + selected call
 *
 * Dense rows, hairlines and aligned columns. The same component renders a live
 * run and the example playback; only the `view` source differs.
 */
export function RunWorkbench({
  view,
  patient,
  facilities,
  approvalMode,
  callHref,
  timers = true,
  notice,
  controls,
}: {
  view: RunView
  patient: PatientCase | undefined
  facilities: Map<string, Facility>
  approvalMode: ApprovalMode
  callHref?: (facilityId: string) => string
  timers?: boolean
  /** A line above the header, e.g. the example run's provenance. */
  notice?: ReactNode
  /** Right side of the header, e.g. playback controls or stream state. */
  controls?: ReactNode
}) {
  const lanes = useMemo(() => lanesFrom(view), [view])
  const found = useMemo(() => contradictionsOf(view.evaluations), [view.evaluations])
  const phase = currentPhase(view)
  const [approvalOpen, setApprovalOpen] = useState(false)

  // Follow the work until the viewer picks a facility themselves.
  const [picked, setPicked] = useState<string | null>(null)
  const selected = picked ?? view.proposal?.facility_id ?? lanes[lanes.length - 1]?.facilityId ?? null

  const select = (facilityId: string) => {
    setPicked(facilityId)
    if (window.matchMedia('(max-width: 1279px)').matches) {
      document.getElementById('selected-call')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const facilityList = useMemo(() => [...facilities.values()], [facilities])
  const selectedEvaluation = view.evaluations.find((e) => e.facility_id === selected) ?? null
  const selectedLane = lanes.find((l) => l.facilityId === selected) ?? null
  const inFlight = lanes.filter((l) => l.state === 'in_flight').length
  const plan = view.plans[view.plans.length - 1]
  const proposal = view.proposal
  const hard = patient?.requirements.filter((r) => r.kind === 'hard') ?? []
  const soft = patient?.requirements.filter((r) => r.kind === 'soft') ?? []

  return (
    <div className="pb-16">
      <RunAnnouncer view={view} />
      {notice}

      {/* Case and run header */}
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4 pb-5">
        <div className="min-w-0">
          <p className="text-[13px] text-ink-muted">
            Case <span className="font-mono text-ink">{view.caseId}</span>
            <span aria-hidden="true"> · </span>
            Run <span className="font-mono">{view.runId}</span>
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-[-0.02em] sm:text-[28px]">
            {patient ? patient.display_name : `Case ${view.caseId}`}
          </h1>
          <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-ink-muted">
            <div className="flex gap-1.5">
              <dt>Status</dt>
              <dd className="text-ink">
                <RunStatusText status={view.status} />
              </dd>
            </div>
            <div className="flex gap-1.5">
              <dt>Telephony</dt>
              <dd className="text-ink">{telephonyName(view.telephony)}</dd>
            </div>
            <div className="flex gap-1.5">
              <dt>Started</dt>
              <dd className="font-mono tabular-nums text-ink">{time(view.startedAt)}</dd>
            </div>
            <div className="flex gap-1.5">
              <dt>Checked</dt>
              <dd className="text-ink">
                {plural(view.callsPlaced, 'facility', 'facilities')}
                {view.liveCalls > 0 ? ` · ${view.liveCalls} live` : ''}
              </dd>
            </div>
            <div className="flex gap-1.5">
              <dt>Cycles</dt>
              <dd className="font-mono tabular-nums text-ink">{view.cyclesUsed}</dd>
            </div>
          </dl>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {controls}
          {proposal ? (
            <Button onClick={() => setApprovalOpen(true)} variant={proposal.status === 'pending' ? 'primary' : 'secondary'}>
              {proposal.status === 'pending' ? 'Review placement' : 'View decision'}
            </Button>
          ) : null}
        </div>
      </header>

      <LoopTrack phase={phase} status={view.status} cycle={view.cyclesUsed || undefined} className="mb-5" />

      {view.error ? (
        <ErrorNote title="The run failed" className="mb-5">
          {view.error}
        </ErrorNote>
      ) : null}

      {view.status === 'no_match_found' ? (
        <div className="mb-5 border-l-2 border-ink/40 py-1 pl-4">
          <p className="text-[15px] font-medium">No verified match</p>
          <p className="mt-0.5 text-sm text-ink-muted">
            The agent stopped and escalated to you with the full call record below. Nothing was proposed and nothing was sent.
          </p>
        </div>
      ) : null}

      {proposal && proposal.status !== 'pending' ? (
        <div className="mb-5 border-l-2 border-ink/40 py-1 pl-4">
          <p className="text-[15px] font-medium">
            {proposal.status === 'approved' ? 'Placement approved' : 'Placement declined'} by {proposal.decided_by}
          </p>
          <p className="mt-0.5 text-sm text-ink-muted">
            {proposal.facility_name} · {dateTime(proposal.decided_at)}. Decision recorded; no referral packet was sent.
          </p>
        </div>
      ) : null}

      <ContradictionBanner found={found} facilities={facilities} onSelect={select} className="mb-6" />

      <div className="grid gap-x-8 gap-y-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:grid-cols-[17rem_minmax(0,1fr)_22rem]">
        {/* Left: patient, requirements, plan, radius */}
        {/* Each column is minmax(0,1fr) inside: an auto track would grow to the matrix table's min width and overflow. */}
        <aside className="order-3 grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-7 lg:order-2 xl:order-1" aria-label="Patient and plan">
          <section>
            <PanelHeading className="border-b border-hairline">Patient</PanelHeading>
            {patient ? (
              <div className="pt-2.5 text-[14px]">
                <p>
                  {ageSex(patient)} · hospital day {patient.hospital_day}
                </p>
                <p className="text-ink-muted">{patient.payer_plan}</p>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-muted">{patient.discharge_summary}</p>
              </div>
            ) : (
              <p className="pt-2.5 text-sm text-ink-muted">Loading case…</p>
            )}
          </section>

          {patient ? (
            <section>
              <PanelHeading className="border-b border-hairline" meta={`${hard.length} hard · ${soft.length} soft`}>
                Requirements
              </PanelHeading>
              <ul className="divide-y divide-hairline text-[13px]">
                {hard.map((r) => (
                  <li key={r.code} className="py-2">
                    <p className="font-medium">{r.label}</p>
                    <p className="text-ink-muted">{r.detail}</p>
                  </li>
                ))}
                {soft.map((r) => (
                  <li key={r.code} className="py-2 text-ink-muted">
                    <p>
                      {r.label} <span className="text-[12px]">(preference)</span>
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section>
            <PanelHeading className="border-b border-hairline" meta={plan ? `Cycle ${plan.cycle}` : undefined}>
              Current plan
            </PanelHeading>
            {plan ? (
              <div className="pt-2.5 text-[13px]">
                <p className="leading-snug">{plan.rationale}</p>
                <p className="mt-2 text-ink-muted">
                  Radius <span className="font-mono tabular-nums text-ink">{miles(plan.radius_miles)}</span>
                  {patient ? (
                    <>
                      {' '}
                      of <span className="font-mono text-ink">{patient.family_zip}</span>
                    </>
                  ) : null}
                </p>
                <ol className="mt-2 grid gap-1">
                  {plan.queue.map((id, index) => (
                    <li key={id} className="flex min-w-0 gap-2">
                      <span className="font-mono tabular-nums text-ink-muted">{index + 1}</span>
                      <span className="shrink-0 whitespace-nowrap font-mono">{id}</span>
                      <span className="truncate text-ink-muted">{facilities.get(id)?.name}</span>
                    </li>
                  ))}
                </ol>
                {Object.keys(plan.excluded).length > 0 ? (
                  <details className="mt-2 text-ink-muted">
                    <summary className="cursor-pointer py-1 hover:text-ink">
                      {plural(Object.keys(plan.excluded).length, 'facility', 'facilities')} excluded
                    </summary>
                    <ul className="mt-1 grid gap-1">
                      {Object.entries(plan.excluded).map(([id, reason]) => (
                        <li key={id}>
                          <span className="font-mono text-ink">{id}</span> {reason}
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}
              </div>
            ) : (
              <p className="pt-2.5 text-sm text-ink-muted">Waiting for the first plan.</p>
            )}
          </section>

          {patient && facilityList.length > 0 ? (
            <section>
              <PanelHeading className="border-b border-hairline" meta={`cap ${miles(patient.max_radius_miles)}`}>
                Radius
              </PanelHeading>
              <RadiusMap
                patient={patient}
                facilities={facilityList}
                plans={view.plans}
                evaluations={view.evaluations}
                compact
                className="pt-2"
              />
            </section>
          ) : null}
        </aside>

        {/* Center: calls and bed intelligence */}
        <div className="order-1 grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-9 lg:col-span-2 xl:col-span-1 xl:order-2">
          <section aria-label="Calls">
            <PanelHeading
              meta={
                lanes.length > 0
                  ? `${plural(lanes.length, 'dispatched', 'dispatched')}${inFlight ? ` · ${inFlight} in flight` : ''}`
                  : undefined
              }
            >
              Calls
            </PanelHeading>
            <CallLanes
              lanes={lanes}
              facilities={facilities}
              selectedId={selected}
              onSelect={select}
              callHref={callHref}
              timers={timers}
            />
          </section>

          <section aria-label="Bed intelligence">
            <PanelHeading meta="Hard constraints only">Bed intelligence</PanelHeading>
            <BedIntelligenceMatrix
              evaluations={view.evaluations}
              facilities={facilities}
              selectedId={selected}
              onSelect={select}
            />
          </section>
        </div>

        {/* Right: reasoning and selected call */}
        <aside className="order-2 grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-9 lg:order-3 xl:sticky xl:top-20 xl:self-start" aria-label="Reasoning">
          <section>
            <PanelHeading className="border-b border-hairline" meta={`${view.events.length} events`}>
              Reasoning
            </PanelHeading>
            <ReasoningTrace
              events={view.events}
              facilities={facilities}
              onSelectFacility={select}
              scrollClassName="max-h-[26rem] xl:max-h-[calc(100dvh-24rem)] min-h-40 pr-2"
            />
          </section>

          <section id="selected-call" className="scroll-mt-20">
            <PanelHeading className="border-b border-hairline">Selected call</PanelHeading>
            {selected ? (
              <div className="pt-2.5">
                <p className="text-[15px] font-medium">{facilities.get(selected)?.name ?? selected}</p>
                {selectedEvaluation ? (
                  <>
                    <p className={cn('text-[13px] font-medium', dispositionTone[selectedEvaluation.disposition])}>
                      {dispositionLabel[selectedEvaluation.disposition]}
                    </p>
                    {selectedEvaluation.observation?.summary &&
                    selectedEvaluation.observation.summary !== selectedEvaluation.observation.simulation_note ? (
                      <p className="mt-2 text-[13px] leading-relaxed text-ink-muted">{selectedEvaluation.observation.summary}</p>
                    ) : null}
                    <TranscriptPlayback observation={selectedEvaluation.observation} limit={6} className="mt-3" />
                    {callHref ? (
                      <Link
                        to={callHref(selected)}
                        className="mt-3 inline-flex min-h-11 items-center gap-1 text-[14px] font-medium underline decoration-hairline underline-offset-4 hover:decoration-ink pointer-fine:min-h-0"
                      >
                        Full call record <ArrowRight size={13} aria-hidden="true" />
                      </Link>
                    ) : null}
                  </>
                ) : selectedLane?.state === 'in_flight' ? (
                  <p className="mt-1 text-[13px] text-ink-muted">
                    In flight. The transcript and findings arrive when the batch completes.
                  </p>
                ) : (
                  <p className="mt-1 text-[13px] text-ink-muted">No evaluation for this facility yet.</p>
                )}
              </div>
            ) : (
              <p className="pt-2.5 text-sm text-ink-muted">Select a call to read its evidence.</p>
            )}
          </section>
        </aside>
      </div>

      {proposal ? (
        <ApprovalSheet
          open={approvalOpen}
          onClose={() => setApprovalOpen(false)}
          proposal={proposal}
          facility={facilities.get(proposal.facility_id)}
          mode={approvalMode}
        />
      ) : null}
    </div>
  )
}
