import { ReasoningTrace } from '@/agent/ReasoningTrace'
import { snapshot, snapshotEvents, snapshotFacilities } from '@/landing/data/snapshot'
import { story } from '@/landing/data/story'
import { Container, Headline } from '@/landing/layout'
import { date } from '@/lib/format'

const STATEMENTS = [
  {
    title: 'Synthetic data',
    body: 'Every patient and facility record is synthetic. No real patient or nursing facility is involved.',
  },
  {
    title: 'Stand-in answering line',
    body: 'Live calls reach an answering line configured with a scripted admissions scenario, never a real facility.',
  },
  {
    title: 'Labeled provenance',
    body: 'REPLAY means a recorded call. SCRIPTED means no call was placed. Simulated answers on a live call are labeled as simulated.',
  },
  {
    title: 'No send path',
    body: 'Approval records a decision. Nothing in the product can send a referral or book transport.',
  },
]

/** A real event trace next to plain statements of what is and is not real. */
export function Provenance() {
  return (
    <section id="safety" aria-labelledby="safety-heading" className="scroll-mt-20 border-t border-hairline py-24 lg:py-32">
      <Container className="grid gap-14 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-20">
        <div className="order-2 lg:order-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-ink/20 pb-3">
            <p className="text-[15px] font-medium">Event trace</p>
            <p className="text-[13px] text-ink-muted">
              Example run · case <span className="font-mono">{story.patient.case_id}</span> · {snapshotEvents.length} events
            </p>
          </div>
          <ReasoningTrace
            events={snapshotEvents}
            facilities={snapshotFacilities}
            scrollClassName="max-h-[34rem] pr-3"
            follow={false}
          />
          <p className="mt-3 border-t border-hairline pt-3 text-[12px] leading-relaxed text-ink-muted">
            Every line is an unedited <span className="font-mono">AgentEvent.message</span>. {story.disclaimer} Generated{' '}
            {date(snapshot.generated_at)}.
          </p>
        </div>

        <div className="order-1 lg:order-2">
          <Headline id="safety-heading" className="text-[2.25rem] leading-[1.08] sm:text-[2.75rem]">
            Audit-ready prototype using synthetic healthcare data.
          </Headline>
          <dl className="mt-10 border-t border-ink/20">
            {STATEMENTS.map((item) => (
              <div key={item.title} className="border-b border-hairline py-5">
                <dt className="label-caps text-ink">{item.title}</dt>
                <dd className="mt-1.5 text-[16px] leading-relaxed text-ink-muted">{item.body}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Container>
    </section>
  )
}
