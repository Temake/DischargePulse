import { useId, useState } from 'react'

import { sourceName } from '@/agent/runSelectors'
import { story } from '@/landing/data/story'
import { Container, Headline } from '@/landing/layout'
import { date } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * The centerpiece, laid out like an investigation: the record, the call, the
 * verdict. It reads completely with no interaction. The slider is a subtle
 * second reading: drag it toward the directory and the call's evidence is set
 * aside, showing what a directory-only search would have concluded.
 */
export function Contradiction() {
  const sliderId = useId()
  const [evidence, setEvidence] = useState(100)
  const { contradiction, claim, withContradiction, contradictedFacility, patient } = story
  if (!contradiction || !withContradiction) return null

  const listedTotal = contradictedFacility?.directory_claims.length ?? 0
  const listedAvailable = contradictedFacility?.directory_claims.filter((c) => c.claimed_available).length ?? 0
  const withCall = evidence >= 50
  const callWeight = Math.max(0.28, evidence / 100)

  return (
    <section id="contradiction" aria-labelledby="contradiction-heading" className="scroll-mt-20 border-t border-hairline py-24 lg:py-32">
      <Container>
        <p className="text-[14px] text-ink-muted">
          Example scenario · {patient.display_name}
        </p>
        <Headline id="contradiction-heading" className="mt-3 max-w-[48rem] text-[2.25rem] leading-[1.08] sm:text-[3rem]">
          The directory says one thing. The call says another.
        </Headline>

        <div className="mt-14 grid gap-y-10 border-t border-ink/20 lg:grid-cols-[minmax(0,5fr)_auto_minmax(0,7fr)]">
          {/* The directory */}
          <div className="pt-6 lg:pr-12">
            <p className="label-caps text-ink-muted">The directory</p>
            <p className="mt-6 text-[15px] text-ink-muted">{contradiction.label}</p>
            <p
              className={cn(
                'mt-1 text-[2.5rem] font-semibold leading-none tracking-[-0.03em] transition-[color,text-decoration-color] duration-300',
                withCall && 'text-ink-muted line-through decoration-not-confirmed decoration-2',
              )}
            >
              Available
            </p>
            <dl className="mt-8 grid grid-cols-[7rem_1fr] gap-y-2 text-[15px]">
              <dt className="text-ink-muted">Source</dt>
              <dd>{claim?.source ?? 'Directory'}</dd>
              <dt className="text-ink-muted">Last updated</dt>
              <dd className="font-mono tabular-nums">{date(claim?.last_updated)}</dd>
              <dt className="text-ink-muted">Facility</dt>
              <dd>
                {contradictedFacility?.name} <span className="font-mono text-[13px] text-ink-muted">{withContradiction.facility_id}</span>
              </dd>
            </dl>
          </div>

          {/* The relation between them */}
          <div className="hidden w-px bg-hairline lg:block" aria-hidden="true">
            <span
              className={cn(
                'relative top-[5.6rem] -ml-[0.9rem] block w-8 bg-bg text-center text-[1.75rem] font-semibold leading-none text-not-confirmed transition-opacity duration-300',
                withCall ? 'opacity-100' : 'opacity-0',
              )}
            >
              ≠
            </span>
          </div>

          {/* The call */}
          <div className="border-t border-hairline pt-6 transition-opacity duration-300 lg:border-t-0 lg:pl-12" style={{ opacity: callWeight }}>
            <p className="label-caps text-ink-muted">The call</p>
            <p className="mt-6 text-[15px] text-ink-muted">{contradiction.label}</p>
            <p className="mt-1 text-[2.5rem] font-semibold leading-none tracking-[-0.03em] text-unavailable">Unavailable</p>
            <dl className="mt-8 grid grid-cols-[7rem_1fr] gap-y-2 text-[15px]">
              <dt className="text-ink-muted">Source</dt>
              <dd>{sourceName(withContradiction)} · no call placed in this example</dd>
              {contradiction.quote ? (
                <>
                  <dt className="text-ink-muted">Said</dt>
                  <dd className="max-w-[34rem]">“{contradiction.quote}”</dd>
                </>
              ) : null}
            </dl>
          </div>
        </div>

        {/* Verdict */}
        <div className="mt-12 grid gap-6 border-t border-ink/20 pt-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-12">
          <p className="label-caps text-ink-muted">Verdict</p>
          <div aria-live="polite">
            {withCall ? (
              <>
                <p className="text-[1.75rem] font-semibold tracking-[-0.02em]">
                  <span className="font-mono">{withContradiction.facility_id}</span> disqualified.
                </p>
                <p className="mt-2 max-w-[38rem] text-[17px] leading-relaxed text-ink-muted">{contradiction.resolution}</p>
              </>
            ) : (
              <>
                <p className="text-[1.75rem] font-semibold tracking-[-0.02em] text-ink-muted">
                  <span className="font-mono">{withContradiction.facility_id}</span> looks like a match.
                </p>
                <p className="mt-2 max-w-[38rem] text-[17px] leading-relaxed text-ink-muted">
                  The directory lists {listedAvailable} of {listedTotal} hard requirements as available
                  {contradictedFacility?.preferred_partner ? ', and the facility is a preferred partner' : ''}. The patient would have
                  arrived at a facility that cannot manage the wound VAC.
                </p>
              </>
            )}
          </div>
        </div>

        <div className="mt-10 grid gap-2 lg:ml-[calc(5/12*100%)] lg:max-w-[28rem]">
          <label htmlFor={sliderId} className="flex justify-between text-[13px] text-ink-muted">
            <span>Directory only</span>
            <span>With the call</span>
          </label>
          <input
            id={sliderId}
            type="range"
            min={0}
            max={100}
            step={1}
            value={evidence}
            onChange={(event) => setEvidence(Number(event.target.value))}
            aria-valuetext={withCall ? 'Directory and call evidence' : 'Directory evidence only'}
            className="h-11 w-full cursor-ew-resize accent-[var(--color-accent)]"
          />
        </div>
      </Container>
    </section>
  )
}
