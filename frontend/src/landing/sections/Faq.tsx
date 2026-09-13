import { Plus } from '@phosphor-icons/react'

import { Container, Headline } from '@/landing/layout'

const QUESTIONS = [
  {
    q: 'Does DischargePulse send referrals or book transport?',
    a: 'No. The agent stops at a proposal. A case manager approves or declines, and that decision is recorded. Referral packet dispatch is not built into this prototype.',
  },
  {
    q: 'Are the calls real?',
    a: 'It depends on the run, and every call says which. LIVE is a real CALL-E call to a stand-in answering line. REPLAY serves a recorded call. SCRIPTED places no call and uses scenario answers. The example run on this page is scripted.',
  },
  {
    q: 'What counts as a contradiction?',
    a: 'A hard requirement the directory lists as available that the facility says it cannot meet, or the reverse. Live information overrides the directory, and the facility is disqualified if the requirement fails.',
  },
  {
    q: 'What happens when no facility qualifies?',
    a: 'The agent follows leads named on calls, widens the radius up to the case cap, and stops when cycles or the call ceiling run out. It then escalates to the case manager with every call it made.',
  },
  {
    q: 'How is call credit protected?',
    a: 'A ceiling is checked before every dial. Runs that place calls must set their own limit, only one such run may be active at a time, and a run that could exceed the remaining budget is refused before it starts.',
  },
  {
    q: 'Is this HIPAA compliant?',
    a: 'No compliance claim is made. This is a prototype that runs only on synthetic patient and facility data.',
  },
  {
    q: 'Where do runs live?',
    a: 'In the backend process’s memory. Restarting the backend clears every run.',
  },
]

/** Two columns: a short framing on the left, questions separated by hairlines on the right. */
export function Faq() {
  return (
    <section id="faq" aria-labelledby="faq-heading" className="scroll-mt-20 border-t border-hairline bg-surface-2/40 py-24 lg:py-32">
      <Container className="grid gap-12 lg:grid-cols-[minmax(0,4fr)_minmax(0,7fr)] lg:gap-20">
        <div>
          <Headline id="faq-heading" className="text-[2.25rem] leading-[1.08]">
            Questions a case manager would ask
          </Headline>
          <p className="mt-4 max-w-[24rem] text-[16px] leading-relaxed text-ink-muted">
            Short answers, including the ones about what this prototype does not do.
          </p>
        </div>

        <div className="border-t border-ink/20">
          {QUESTIONS.map((item) => (
            <details key={item.q} className="group border-b border-hairline">
              <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-6 py-4 text-[17px] font-medium [&::-webkit-details-marker]:hidden">
                {item.q}
                <Plus size={16} className="shrink-0 text-ink-muted transition-transform duration-200 group-open:rotate-45" aria-hidden="true" />
              </summary>
              <p className="max-w-[40rem] pb-5 text-[16px] leading-relaxed text-ink-muted">{item.a}</p>
            </details>
          ))}
        </div>
      </Container>
    </section>
  )
}
