import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { AnimatePresence, m, useReducedMotion } from 'framer-motion'
import { ArrowRight } from '@phosphor-icons/react'

import { ButtonLink } from '@/components/ui/Button'
import { EXAMPLE_RUN_ID } from '@/landing/data/snapshot'
import { facility, story } from '@/landing/data/story'
import { Container, Headline } from '@/landing/layout'
import { ageSex, miles, plural, score } from '@/lib/format'
import { constraintShort } from '@/lib/labels'
import { dur, ease } from '@/lib/motion'
import { cn } from '@/lib/utils'

interface Station {
  phase: string
  body: ReactNode
  tone?: 'finding' | 'verdict' | 'gate'
}

const firstName = (id: string) => facility(id)?.name ?? id

/** The run's beats, each drawn from the snapshot. */
function stations(): Station[] {
  const list: Station[] = []
  const { firstPlan, patient, firstAct, contradiction, claim, withContradiction, lead, proposal } = story

  if (firstPlan) {
    list.push({
      phase: 'Plan',
      body: (
        <>
          <p>
            <span className="font-mono">{patient.family_zip}</span> · {miles(firstPlan.radius_miles)}
          </p>
          <p className="text-ink-muted">{plural(firstPlan.queue.length, 'facility', 'facilities')} in the queue</p>
          {story.payerExclusions[0] ? (
            <p className="text-ink-muted">
              <span className="font-mono text-ink">{story.payerExclusions[0][0]}</span> out of network
            </p>
          ) : null}
        </>
      ),
    })
  }
  const dispatched = firstAct?.payload.facility_ids
  if (Array.isArray(dispatched)) {
    list.push({
      phase: 'Act',
      body: (dispatched as string[]).map((id) => <p key={id}>{firstName(id)}</p>),
    })
  }
  if (contradiction && withContradiction) {
    list.push({
      phase: 'Observe',
      tone: 'finding',
      body: (
        <>
          <p>{contradiction.label}</p>
          <dl className="mt-0.5 grid grid-cols-[auto_1fr] gap-x-3 text-ink-muted">
            <dt>Directory</dt>
            <dd className="text-ink">{claim?.claimed_available ? 'available' : 'not listed'}</dd>
            <dt>Attendant</dt>
            <dd className="font-medium text-unavailable">unavailable</dd>
          </dl>
        </>
      ),
    })
    list.push({
      phase: 'Reason',
      tone: 'verdict',
      body: (
        <>
          <p className="label-caps text-not-confirmed">Contradiction</p>
          <p>
            {withContradiction.facility_name} disqualified
          </p>
        </>
      ),
    })
  }
  if (lead?.facility) {
    list.push({
      phase: 'Re-plan',
      body: (
        <p>
          Sister campus named by the attendant, <span className="font-mono">{lead.facility.facility_id}</span>
          <span className="text-ink-muted"> at {miles(lead.facility.distance_miles)}</span>
        </p>
      ),
    })
  }
  if (proposal) {
    list.push({
      phase: 'Human gate',
      tone: 'gate',
      body: (
        <>
          <p className="font-medium">{proposal.facility_name}</p>
          <p className="text-ink-muted">
            Every hard requirement confirmed · score <span className="font-mono text-ink">{score(proposal.match_score)}</span>
          </p>
          <p className="mt-1 text-accent">Waiting for a case manager</p>
        </>
      ),
    })
  }
  return list
}

const STATIONS = stations()

/** Clinical needs beyond payer and bed, e.g. "Wound VAC, IV". */
const CLINICAL = story.patient.requirements
  .filter((r) => r.kind === 'hard' && r.code !== 'payer_network' && r.code !== 'staffed_bed')
  .map((r) => constraintShort[r.code])
  .join(', ')

/**
 * An operator's work surface, not a screenshot: one frame, one vertical rule,
 * the example run's beats in order. Each beat enters once, in the order the
 * run produced it; the final verified facility is the last to arrive.
 */
function WorkSurface() {
  const reduce = useReducedMotion()
  const [revealed, setRevealed] = useState(0)
  const count = reduce ? STATIONS.length : revealed

  useEffect(() => {
    if (reduce || revealed >= STATIONS.length) return
    const id = window.setTimeout(() => setRevealed((c) => c + 1), revealed === 0 ? 450 : 850)
    return () => window.clearTimeout(id)
  }, [revealed, reduce])

  return (
    <div className="border border-hairline bg-surface">
      <div className="flex items-baseline justify-between gap-3 border-b border-hairline px-5 py-3 text-[13px]">
        <p>
          Case <span className="font-mono">{story.patient.case_id}</span>
          <span className="text-ink-muted">
            {' '}
            · {ageSex(story.patient)} · {CLINICAL}
          </span>
        </p>
        <span className="font-mono text-[11px] font-medium tracking-[0.06em] text-ink-muted">SCRIPTED</span>
      </div>

      <ol className="relative px-5 py-4" aria-label="Example run, step by step">
        {/* The rule sits in the gutter between label and data: 1.25rem padding + 5.2rem label + half the 1.5rem gap. */}
        <span className="absolute bottom-6 left-[7.2rem] top-6 w-px bg-hairline" aria-hidden="true" />
        <AnimatePresence initial={false}>
          {STATIONS.slice(0, count).map((station, index) => {
            const current = index === count - 1
            return (
              <m.li
                key={station.phase}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: dur.ui, ease: ease.out }}
                className="relative grid grid-cols-[5.2rem_1fr] gap-x-6 py-2.5 text-[14px] leading-snug"
              >
                <span
                  className={cn(
                    'label-caps pt-px',
                    station.tone === 'gate' ? 'text-accent' : current ? 'text-ink' : 'text-ink-muted',
                  )}
                >
                  {station.phase}
                </span>
                <span
                  className={cn(
                    'absolute left-[5.95rem] top-[1.05rem] size-[7px] -translate-x-1/2 rounded-full ring-4 ring-surface',
                    station.tone === 'gate' ? 'bg-accent' : station.tone === 'verdict' ? 'bg-not-confirmed' : 'bg-ink/70',
                  )}
                  aria-hidden="true"
                />
                <div className={cn('min-w-0', station.tone === 'verdict' && 'border-l-2 border-not-confirmed pl-3 -ml-3.5')}>
                  {station.body}
                </div>
              </m.li>
            )
          })}
        </AnimatePresence>
        {count < STATIONS.length ? <li className="h-4" aria-hidden="true" /> : null}
      </ol>

      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-hairline px-5 py-3 text-[12px] text-ink-muted">
        <span>{story.label}. No call placed.</span>
        <Link
          to={`/runs/${EXAMPLE_RUN_ID}`}
          className="inline-flex min-h-11 items-center gap-1 font-medium text-ink hover:underline hover:underline-offset-4 pointer-fine:min-h-0"
        >
          Open in the console <ArrowRight size={12} aria-hidden="true" />
        </Link>
      </div>
    </div>
  )
}

export function Hero() {
  return (
    <section className="pb-20 pt-28 sm:pt-32 lg:pb-28 lg:pt-36">
      <Container className="grid items-start gap-12 lg:grid-cols-[minmax(0,1fr)_25rem] lg:gap-16 xl:grid-cols-[minmax(0,1fr)_27rem]">
        <div className="max-w-[44rem] lg:pt-6">
          <Headline as="h1" className="text-[2.5rem] leading-[1.03] sm:text-[3.5rem] lg:text-[4rem]">
            The agent makes
            <br className="hidden sm:block" /> the placement calls.
            <span className="mt-2 block text-ink-muted sm:mt-3">You make the decision.</span>
          </Headline>
          <p className="mt-7 max-w-[36rem] text-[18px] leading-relaxed text-ink-muted sm:text-[19px]">
            DischargePulse checks post-acute facilities by phone, verifies the requirements that matter, catches
            contradictions in stale directory data, and stops before a referral is sent.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <ButtonLink to="/console">Open the console</ButtonLink>
            <ButtonLink to={`/runs/${EXAMPLE_RUN_ID}`} variant="secondary">
              Watch an example run
            </ButtonLink>
          </div>
        </div>

        <WorkSurface />
      </Container>
    </section>
  )
}
