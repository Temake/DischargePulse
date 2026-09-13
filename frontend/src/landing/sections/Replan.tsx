import { useEffect, useMemo, useRef, useState } from 'react'
import { useInView, useReducedMotion } from 'framer-motion'

import { RadiusMap } from '@/agent/RadiusMap'
import { viewAtEvents } from '@/agent/runSelectors'
import { snapshot, snapshotEvents, snapshotRecord } from '@/landing/data/snapshot'
import { beats, story } from '@/landing/data/story'
import { Container, Headline } from '@/landing/layout'
import { miles } from '@/lib/format'
import { cn } from '@/lib/utils'

const STAGES = [
  {
    title: `Search ${miles(story.radius)} from ${story.patient.family_zip}`,
    body: 'The plan starts at the family zip. Out-of-network and out-of-radius facilities are set aside before any call.',
    at: beats.planned,
  },
  {
    title: 'First batch reasoned over',
    body: 'Both facilities in the radius fail a hard requirement. One of them named a sister campus.',
    at: beats.firstBatchReasoned,
  },
  {
    title: story.lead?.facility ? `${story.lead.facility.facility_id} queued from a named lead` : 'Lead queued',
    body: `A facility named during a conversation outranks the radius rule that excluded it.`,
    at: beats.replanned,
  },
  {
    title: 'Verified, sweep stopped',
    body: 'Every hard requirement confirmed. The remaining facilities are never called.',
    at: beats.verified,
  },
]

/**
 * Re-planning as a technical diagram. Each stage is the example run's real
 * state after a given event, drawn by the same RadiusMap the console uses.
 */
export function Replan() {
  const [stage, setStage] = useState(0)
  const [touched, setTouched] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { amount: 0.5 })
  const reduce = useReducedMotion()

  useEffect(() => {
    if (!inView || touched || reduce || stage >= STAGES.length - 1) return
    const id = window.setTimeout(() => setStage((s) => s + 1), 2600)
    return () => window.clearTimeout(id)
  }, [inView, touched, reduce, stage])

  const view = useMemo(() => viewAtEvents(snapshotRecord, snapshotEvents.slice(0, STAGES[stage].at)), [stage])

  return (
    <section aria-labelledby="replan-heading" className="border-t border-hairline py-24 lg:py-32">
      <Container className="grid gap-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-20">
        <div>
          <Headline id="replan-heading" className="text-[2.25rem] leading-[1.08] sm:text-[2.75rem]">
            When the plan stops working, the agent changes it.
          </Headline>
          <p className="mt-5 max-w-[32rem] text-[17px] leading-relaxed text-ink-muted">
            In this run the radius never widened: a sister campus named by the attendant was a better lead than the{' '}
            {miles(story.radius)} rule.
            Had the queue emptied, the agent would have widened toward the {miles(story.patient.max_radius_miles)} cap.
          </p>

          <div role="tablist" aria-label="Re-planning stages" className="mt-10 border-t border-hairline">
            {STAGES.map((item, index) => (
              <button
                key={item.title}
                role="tab"
                type="button"
                aria-selected={stage === index}
                aria-controls="replan-diagram"
                onClick={() => {
                  setTouched(true)
                  setStage(index)
                }}
                className={cn(
                  'relative grid w-full grid-cols-[2rem_1fr] border-b border-hairline py-3.5 text-left transition-colors',
                  stage === index ? 'text-ink' : 'text-ink-muted hover:text-ink',
                )}
              >
                {stage === index ? <span className="absolute inset-y-0 left-0 w-[2px] bg-accent" aria-hidden="true" /> : null}
                <span className="pl-3 font-mono text-[13px] tabular-nums">{index + 1}</span>
                <span>
                  <span className="block text-[16px] font-medium">{item.title}</span>
                  {stage === index ? <span className="mt-1 block text-[14px] leading-relaxed text-ink-muted">{item.body}</span> : null}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div ref={ref} id="replan-diagram" role="tabpanel" aria-label={STAGES[stage].title} className="lg:pt-2">
          <div className="border border-hairline bg-surface p-5 sm:p-7">
            <div className="mb-4 flex items-baseline justify-between gap-4 text-[13px] text-ink-muted">
              <span>Miles from the family zip</span>
              <span className="font-mono">{snapshot.patient.case_id}</span>
            </div>
            <RadiusMap patient={snapshot.patient} facilities={snapshot.facilities} plans={view.plans} evaluations={view.evaluations} />
            <p className="mt-4 text-[12px] text-ink-muted">
              Distance only. The directory holds no coordinates, so the diagram does not pretend to know direction.
            </p>
          </div>
        </div>
      </Container>
    </section>
  )
}
