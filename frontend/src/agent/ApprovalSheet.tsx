import { useId, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { approveRun, declineRun, type ApiError } from '@/api/client'
import type { Facility, PlacementProposal, RunRecord } from '@/api/types'
import { Button } from '@/components/ui/Button'
import { Field, Input, Textarea } from '@/components/ui/Field'
import { Sheet } from '@/components/ui/Sheet'
import { keys } from '@/hooks/queries'
import { dateTime, miles, score } from '@/lib/format'
import { callModeLabel, HARD_ORDER } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { sourceName } from './runSelectors'
import { StateMark } from './StateChip'

const NAME_KEY = 'dp-decided-by'

function rememberedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? ''
  } catch {
    return ''
  }
}

function Section({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn('border-t border-hairline pt-4', className)}>
      <h3 className="text-[13px] font-medium text-ink-muted">{title}</h3>
      <div className="mt-2.5">{children}</div>
    </section>
  )
}

export type ApprovalMode = { kind: 'live'; runId: string } | { kind: 'demo' }

/**
 * The human gate as a decision surface: proposal, evidence, decision, note.
 *
 * In the console the actions post to /approve or /decline, which records who
 * decided and why. Nothing is sent: referral packet dispatch does not exist in
 * this prototype, and the copy says so next to the buttons. On the landing page
 * the same sheet opens with the actions disabled.
 */
export function ApprovalSheet({
  open,
  onClose,
  proposal,
  facility,
  mode,
}: {
  open: boolean
  onClose: () => void
  proposal: PlacementProposal
  facility?: Facility
  mode: ApprovalMode
}) {
  const queryClient = useQueryClient()
  const nameId = useId()
  const noteId = useId()
  const [name, setName] = useState(rememberedName)
  const [note, setNote] = useState('')
  const [nameError, setNameError] = useState<string | null>(null)

  const evaluation = proposal.evaluation
  const observation = evaluation.observation
  const hard = evaluation.findings
    .filter((f) => f.kind === 'hard')
    .sort((a, b) => HARD_ORDER.indexOf(a.code) - HARD_ORDER.indexOf(b.code))
  const soft = evaluation.findings.filter((f) => f.kind === 'soft')
  const pending = proposal.status === 'pending'
  const demo = mode.kind === 'demo'

  const decide = useMutation<RunRecord, ApiError, 'approve' | 'decline'>({
    mutationFn: (verb) => {
      if (mode.kind !== 'live') throw new Error('Demo mode')
      const body = { decided_by: name.trim(), note: note.trim() || null }
      return verb === 'approve' ? approveRun(mode.runId, body) : declineRun(mode.runId, body)
    },
    onSuccess: (record, verb) => {
      if (mode.kind === 'live') queryClient.setQueryData(keys.run(mode.runId), record)
      void queryClient.invalidateQueries({ queryKey: keys.runs, exact: true })
      try {
        localStorage.setItem(NAME_KEY, name.trim())
      } catch {
        // Convenience only.
      }
      toast(verb === 'approve' ? 'Approval recorded' : 'Decline recorded', {
        description: 'The decision is on the run record. No referral was sent.',
      })
    },
  })

  const submit = (verb: 'approve' | 'decline') => {
    if (!name.trim()) {
      setNameError('Enter your name. The decision is recorded against it.')
      document.getElementById(nameId)?.focus()
      return
    }
    setNameError(null)
    decide.mutate(verb)
  }

  const footer = pending ? (
    <div>
      {decide.error ? (
        <p role="alert" className="mb-3 text-[13px] text-unavailable">
          {decide.error.message}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Button onClick={() => submit('approve')} disabled={demo || decide.isPending}>
          {decide.isPending && decide.variables === 'approve' ? 'Recording…' : 'Approve placement'}
        </Button>
        <Button variant="quiet-danger" onClick={() => submit('decline')} disabled={demo || decide.isPending}>
          {decide.isPending && decide.variables === 'decline' ? 'Recording…' : 'Decline'}
        </Button>
      </div>
      <p className="mt-3 text-[13px] text-ink-muted">
        {demo
          ? 'Example run. Decisions are disabled here; the console records them against a real run.'
          : 'This records your decision. Referral packet dispatch is not built into this prototype.'}
      </p>
    </div>
  ) : null

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={proposal.facility_name}
      description={
        <>
          Proposed for case <span className="font-mono">{proposal.case_id}</span> · {pending ? 'awaiting your decision' : `${proposal.status}`}
        </>
      }
      footer={footer}
    >
      <div className="grid gap-5">
        {/* Proposal */}
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[14px] sm:grid-cols-4">
          <div>
            <dt className="text-[13px] text-ink-muted">Match score</dt>
            <dd className="mt-0.5 font-mono text-2xl tabular-nums tracking-tight">
              {score(proposal.match_score)}
              <span className="text-[13px] text-ink-muted"> /100</span>
            </dd>
          </div>
          <div>
            <dt className="text-[13px] text-ink-muted">Facility</dt>
            <dd className="mt-1.5 font-mono">{proposal.facility_id}</dd>
          </div>
          {facility ? (
            <>
              <div>
                <dt className="text-[13px] text-ink-muted">Distance</dt>
                <dd className="mt-1.5 font-mono tabular-nums">{miles(facility.distance_miles)}</dd>
              </div>
              <div>
                <dt className="text-[13px] text-ink-muted">CMS rating</dt>
                <dd className="mt-1.5 font-mono tabular-nums">{facility.cms_star_rating} / 5</dd>
              </div>
            </>
          ) : null}
        </dl>

        {!pending ? (
          <div className="border-l-2 border-ink/30 pl-4">
            <p className="text-[15px] font-medium">
              {proposal.status === 'approved' ? 'Approved' : 'Declined'} by {proposal.decided_by}
            </p>
            <p className="text-[13px] text-ink-muted">
              {dateTime(proposal.decided_at)}
              {proposal.decision_note ? ` · “${proposal.decision_note}”` : ''}
            </p>
            <p className="mt-1 text-[13px] text-ink-muted">Decision recorded. No referral packet was sent.</p>
          </div>
        ) : null}

        <Section title="Hard requirements">
          <ul className="divide-y divide-hairline">
            {hard.map((finding) => (
              <li key={finding.code} className="grid gap-1 py-2.5 sm:grid-cols-[10rem_1fr] sm:gap-4">
                <p className="text-[14px]">{finding.label}</p>
                <div className="text-[14px]">
                  <StateMark state={finding.state} />
                  <p className="mt-0.5 text-[13px] text-ink-muted">{finding.rationale}</p>
                  {finding.quote ? <p className="mt-1 text-[13px]">“{finding.quote}”</p> : null}
                </div>
              </li>
            ))}
          </ul>
        </Section>

        {soft.length > 0 ? (
          <Section title="Preferences">
            <ul className="grid gap-1.5 text-[14px]">
              {soft.map((finding) => (
                <li key={finding.code} className="flex items-baseline justify-between gap-4">
                  <span>{finding.label}</span>
                  <StateMark state={finding.state} size={14} />
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        <Section title="Admissions contact">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-[14px] sm:grid-cols-3">
            <div>
              <dt className="text-[13px] text-ink-muted">Coordinator</dt>
              <dd>{evaluation.coordinator_name || 'Not given'}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-ink-muted">Callback</dt>
              <dd className="font-mono tabular-nums">{evaluation.callback_number || 'Not given'}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-ink-muted">Referral fax</dt>
              <dd className="font-mono tabular-nums">{evaluation.fax_number || 'Not given'}</dd>
            </div>
          </dl>
        </Section>

        <Section title="Provenance">
          <p className="text-[14px]">
            {sourceName(evaluation)}
            {observation ? (
              <span className="text-ink-muted">
                {' · '}
                <span className="font-mono">{callModeLabel[observation.mode]}</span>
                {observation.call_id ? <span className="font-mono"> · {observation.call_id}</span> : null}
              </span>
            ) : null}
          </p>
          {observation?.simulation_note ? <p className="mt-1 text-[13px] text-ink-muted">{observation.simulation_note}</p> : null}
        </Section>

        {pending ? (
          <Section title="Decision">
            <div className="grid gap-4">
              <Field label="Your name" htmlFor={nameId} error={nameError} hint="Recorded as the decision owner.">
                <Input
                  id={nameId}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={120}
                  autoComplete="name"
                  disabled={demo}
                  aria-invalid={Boolean(nameError)}
                  aria-describedby={nameError ? `${nameId}-error` : `${nameId}-hint`}
                />
              </Field>
              <Field label="Note (optional)" htmlFor={noteId}>
                <Textarea
                  id={noteId}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  maxLength={1000}
                  disabled={demo}
                />
              </Field>
            </div>
          </Section>
        ) : null}
      </div>
    </Sheet>
  )
}
