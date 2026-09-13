import { useState } from 'react'

import { ApprovalSheet } from '@/agent/ApprovalSheet'
import { StateMark } from '@/agent/StateChip'
import { Button } from '@/components/ui/Button'
import { story } from '@/landing/data/story'
import { Container, Headline } from '@/landing/layout'
import { score } from '@/lib/format'
import { constraintShort, HARD_ORDER } from '@/lib/labels'

/**
 * The strongest statement on the page, and the proposal it refers to. The
 * button opens the same ApprovalSheet the console uses, with its actions
 * disabled, because nothing on a marketing page should record a decision.
 */
export function Gate() {
  const [open, setOpen] = useState(false)
  const { proposal, match, matchFacility } = story
  if (!proposal || !match) return null

  const hard = match.findings
    .filter((f) => f.kind === 'hard')
    .sort((a, b) => HARD_ORDER.indexOf(a.code) - HARD_ORDER.indexOf(b.code))

  return (
    <section aria-labelledby="gate-heading" className="border-t border-hairline py-24 lg:py-36">
      <Container>
        <Headline id="gate-heading" className="max-w-[58rem] text-[2.5rem] leading-[1.04] sm:text-[3.5rem] lg:text-[4rem]">
          The agent found the bed.
          <span className="block text-ink-muted">It does not get to send the referral.</span>
        </Headline>

        <div className="mt-16 grid gap-10 lg:grid-cols-[minmax(0,4fr)_minmax(0,6fr)] lg:gap-20">
          <p className="max-w-[26rem] text-[17px] leading-relaxed text-ink-muted">
            The run ends with a proposal and a person. Approving records who decided and why. Referral packets and fax dispatch
            are not built into this prototype, so there is no path for the agent to send one.
          </p>

          <div className="border-t-2 border-ink">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 pt-4">
              <p className="text-[1.375rem] font-semibold uppercase tracking-[0.02em]">{proposal.facility_name}</p>
              <p className="font-mono text-[13px] text-ink-muted">{proposal.facility_id}</p>
            </div>

            <dl className="mt-4 divide-y divide-hairline border-y border-hairline text-[16px]">
              <div className="grid grid-cols-[10rem_1fr] py-3">
                <dt className="text-ink-muted">Score</dt>
                <dd className="font-mono tabular-nums">{score(proposal.match_score)}</dd>
              </div>
              {hard.map((finding) => (
                <div key={finding.code} className="grid grid-cols-[10rem_1fr] py-3">
                  <dt className="text-ink-muted">{constraintShort[finding.code]}</dt>
                  <dd>
                    <StateMark state={finding.state} />
                  </dd>
                </div>
              ))}
              <div className="grid grid-cols-[10rem_1fr] py-3">
                <dt className="text-ink-muted">Coordinator</dt>
                <dd>{match.coordinator_name || 'Not given'}</dd>
              </div>
              <div className="grid grid-cols-[10rem_1fr] py-3">
                <dt className="text-ink-muted">Direct fax</dt>
                <dd className="font-mono tabular-nums">{match.fax_number || 'Not given'}</dd>
              </div>
            </dl>

            <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3">
              <Button onClick={() => setOpen(true)}>Review placement</Button>
              <p className="text-[13px] text-ink-muted">Example run. Answers scripted, decision disabled.</p>
            </div>
          </div>
        </div>
      </Container>

      <ApprovalSheet open={open} onClose={() => setOpen(false)} proposal={proposal} facility={matchFacility} mode={{ kind: 'demo' }} />
    </section>
  )
}
