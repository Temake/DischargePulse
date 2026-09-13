import { useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, m, useMotionValueEvent, useReducedMotion, useScroll } from 'framer-motion'

import { ProvenanceBadge } from '@/agent/ProvenanceBadge'
import { snapshotRun } from '@/landing/data/snapshot'
import { facility, story } from '@/landing/data/story'
import { Container, Headline } from '@/landing/layout'
import { miles, score } from '@/lib/format'
import { dispositionLabel, dispositionTone } from '@/lib/labels'
import { dur, ease } from '@/lib/motion'
import { cn } from '@/lib/utils'

interface Step {
  key: string
  title: string
  summary: string
  artifact: ReactNode
}

function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn('font-mono', className)}>{children}</span>
}

function ArtifactHead({ phase, detail }: { phase: string; detail?: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-hairline pb-3">
      <p className="label-caps text-accent">{phase}</p>
      {detail ? <p className="text-[12px] text-ink-muted">{detail}</p> : null}
    </div>
  )
}

const snf1 = story.withContradiction
const result = snf1?.observation?.structured_result ?? {}

const STEPS: Step[] = [
  {
    key: 'plan',
    title: 'Plan',
    summary: 'Filter the directory by payer and radius, then rank what is left by distance, CMS rating and partner status.',
    artifact: story.firstPlan ? (
      <>
        <ArtifactHead phase="Plan" detail={`cycle ${story.firstPlan.cycle}`} />
        <p className="mt-4 text-[22px] font-medium leading-snug tracking-[-0.01em]">
          {story.firstPlan.queue.length} facilities within {miles(story.firstPlan.radius_miles)} of{' '}
          <Mono>{story.patient.family_zip}</Mono>
        </p>
        <ol className="mt-4 grid gap-1.5 text-[15px]">
          {story.firstPlan.queue.map((id, i) => (
            <li key={id} className="flex gap-3">
              <Mono className="text-ink-muted">{i + 1}</Mono>
              <Mono>{id}</Mono>
              <span className="text-ink-muted">{facility(id)?.name}</span>
            </li>
          ))}
        </ol>
        {story.payerExclusions.map(([id, reason]) => (
          <div key={id} className="mt-5 border-t border-hairline pt-3 text-[15px]">
            <Mono>{id}</Mono> <span className="text-unavailable">out of network</span>
            <p className="text-[13px] text-ink-muted">{reason}</p>
          </div>
        ))}
      </>
    ) : null,
  },
  {
    key: 'act',
    title: 'Act',
    summary: 'Place the calls concurrently, up to 6 at a time and never past the 20-call ceiling.',
    artifact: (
      <>
        <ArtifactHead phase="Act" detail="concurrent" />
        <ul className="mt-3 divide-y divide-hairline">
          {((story.firstAct?.payload.facility_ids as string[] | undefined) ?? []).map((id) => (
            <li key={id} className="flex items-center justify-between gap-4 py-3 text-[15px]">
              <span>
                {facility(id)?.name}
                <Mono className="block text-[12px] text-ink-muted">{id}</Mono>
              </span>
              <ProvenanceBadge mode="scripted" />
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[13px] text-ink-muted">{story.firstAct?.message}</p>
      </>
    ),
  },
  {
    key: 'observe',
    title: 'Observe',
    summary: 'Every call returns a typed result, not a paragraph to interpret: yes, no, or unknown per requirement.',
    artifact: (
      <>
        <ArtifactHead phase="Observe" detail={<Mono>{snf1?.facility_id}</Mono>} />
        <dl className="mt-3 grid grid-cols-[1fr_auto] gap-y-2 font-mono text-[15px]">
          {['wound_vac', 'staffed_bed', 'payer_network', 'iv_infusion'].map((key) => {
            const value = String(result[key] ?? 'unknown')
            return (
              <div key={key} className="contents">
                <dt className="text-ink-muted">{key}</dt>
                <dd
                  className={cn(
                    'text-right font-medium uppercase',
                    value === 'no' ? 'text-unavailable' : value === 'yes' ? 'text-confirmed' : 'text-unknown',
                  )}
                >
                  {value}
                </dd>
              </div>
            )
          })}
        </dl>
        {typeof result.wound_vac_detail === 'string' && result.wound_vac_detail ? (
          <p className="mt-4 border-t border-hairline pt-3 text-[14px]">“{result.wound_vac_detail}”</p>
        ) : null}
      </>
    ),
  },
  {
    key: 'reason',
    title: 'Reason',
    summary: 'Check hard constraints separately from preferences, and compare what was said with what the directory claims.',
    artifact: story.contradiction && snf1 ? (
      <>
        <ArtifactHead phase="Reason" detail={<Mono>{snf1.facility_id}</Mono>} />
        <p className="label-caps mt-4 text-not-confirmed">Contradiction</p>
        <p className="mt-2 text-[22px] font-medium tracking-[-0.01em]">
          Directory <span className="text-not-confirmed">≠</span> attendant
        </p>
        <p className="mt-1 text-[15px] text-ink-muted">
          {story.contradiction.directory_says} · {story.contradiction.call_says}
        </p>
        <p className={cn('mt-4 border-t border-hairline pt-3 text-[15px] font-medium', dispositionTone[snf1.disposition])}>
          {snf1.facility_name}: {dispositionLabel[snf1.disposition].toLowerCase()}
        </p>
      </>
    ) : null,
  },
  {
    key: 'replan',
    title: 'Re-plan',
    summary: 'When reality changes the plan, change the plan: follow a named lead, or widen the radius toward its cap.',
    artifact: story.lead?.facility ? (
      <>
        <ArtifactHead phase="Re-plan" detail="sister facility lead" />
        <p className="mt-4 text-[15px] text-ink-muted">
          Named during the <Mono className="text-ink">{story.lead.namedBy.facility_id}</Mono> conversation
        </p>
        <p className="mt-1 text-[22px] font-medium tracking-[-0.01em]">{story.lead.facility.name}</p>
        <p className="mt-1 text-[15px] text-ink-muted">
          <Mono>{story.lead.facility.facility_id}</Mono> · {miles(story.lead.facility.distance_miles)}, outside the{' '}
          {miles(story.radius)} radius
        </p>
        <p className="mt-4 border-t border-hairline pt-3 text-[14px]">{story.secondPlan?.rationale}</p>
      </>
    ) : null,
  },
  {
    key: 'gate',
    title: 'Human gate',
    summary: 'Stop at the first verified match and ask. The agent has no way to send a referral.',
    artifact: story.proposal ? (
      <>
        <ArtifactHead phase="Human gate" detail="awaiting approval" />
        <p className="mt-4 text-[22px] font-medium tracking-[-0.01em]">{story.proposal.facility_name}</p>
        <p className="mt-1 text-[15px] text-ink-muted">
          Score <Mono className="text-ink">{score(story.proposal.match_score)}</Mono> · {snapshotRun.calls_placed} facilities
          checked · {snapshotRun.cycles_used} cycles
        </p>
        <p className="mt-4 border-t border-hairline pt-3 text-[15px]">
          Proposal ready. A case manager approves or declines; nothing is sent either way.
        </p>
      </>
    ) : null,
  },
]

function StepText({
  step,
  index,
  active,
  itemRef,
}: {
  step: Step
  index: number
  active: boolean
  itemRef: (node: HTMLLIElement | null) => void
}) {
  return (
    <li ref={itemRef} className="relative pb-14 pl-8 lg:min-h-[52vh] lg:pb-0">
      <span
        className={cn(
          'absolute left-0 top-2 size-[9px] -translate-x-1/2 rounded-full ring-4 ring-bg transition-colors duration-300',
          active ? 'bg-accent' : 'bg-hairline',
        )}
        aria-hidden="true"
      />
      <p className={cn('font-mono text-[13px] tabular-nums transition-colors duration-300', active ? 'text-accent' : 'text-ink-muted')}>
        {String(index + 1).padStart(2, '0')}
      </p>
      <h3 className={cn('mt-1 text-[1.75rem] font-semibold tracking-[-0.02em] transition-colors duration-300', !active && 'lg:text-ink-muted')}>
        {step.title}
      </h3>
      <p className="mt-2 max-w-[28rem] text-[17px] leading-relaxed text-ink-muted">{step.summary}</p>
      {/* Phones and tablets: the artifact sits under its step. */}
      <div className="mt-6 border border-hairline bg-surface p-5 lg:hidden">{step.artifact}</div>
    </li>
  )
}

/**
 * The signature interaction: a vertical operational timeline. The active phase
 * follows the reader's scroll; the evidence beside it is real output from the
 * example run at that phase. No rings, no radar, no beams.
 */
export function Loop() {
  const [active, setActive] = useState(0)
  const reduce = useReducedMotion()
  const steps = STEPS.filter((s) => s.artifact)
  const items = useRef<(HTMLLIElement | null)[]>([])
  const { scrollY } = useScroll()

  // The active phase is the last step whose top has crossed the middle of the
  // viewport. Position-based, so a fast scroll or a jump link never skips one.
  useMotionValueEvent(scrollY, 'change', () => {
    const middle = window.innerHeight / 2
    let next = 0
    items.current.forEach((node, index) => {
      if (node && node.getBoundingClientRect().top < middle) next = index
    })
    setActive(next)
  })

  return (
    <section id="how-it-works" aria-labelledby="loop-heading" className="scroll-mt-20 border-t border-hairline bg-surface-2/40 py-24 lg:py-32">
      <Container>
        <div className="max-w-[40rem]">
          <Headline id="loop-heading" className="text-[2.25rem] leading-[1.08] sm:text-[3rem]">
            One loop, repeated until there is evidence.
          </Headline>
          <p className="mt-5 text-[18px] leading-relaxed text-ink-muted">
            Plan, act, observe, reason, re-plan. The loop can cycle as many times as the budget allows. It always exits to a
            person.
          </p>
        </div>

        <div className="mt-16 grid gap-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-20">
          <ol className="relative ml-1 border-l border-hairline">
            {steps.map((step, index) => (
              <StepText
                key={step.key}
                step={step}
                index={index}
                active={active === index}
                itemRef={(node) => {
                  items.current[index] = node
                }}
              />
            ))}
          </ol>

          <div className="hidden lg:block">
            <div className="sticky top-[22vh] border border-hairline bg-surface p-7">
              <AnimatePresence mode="wait" initial={false}>
                <m.div
                  key={steps[active]?.key}
                  initial={reduce ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduce ? undefined : { opacity: 0, y: -4 }}
                  transition={{ duration: dur.ui, ease: ease.out }}
                  aria-live="polite"
                >
                  {steps[active]?.artifact}
                </m.div>
              </AnimatePresence>
              <p className="mt-6 border-t border-hairline pt-3 text-[12px] text-ink-muted">
                Example run, case {story.patient.case_id}. {story.label}.
              </p>
            </div>
          </div>
        </div>
      </Container>
    </section>
  )
}
