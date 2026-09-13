import { story } from '@/landing/data/story'
import { Container, Headline } from '@/landing/layout'

const ask = new Map(story.patient.requirements.map((r) => [r.code, r.ask_as]))

const HARD = [
  { code: 'payer_network', name: 'Payer', fallback: 'whether the facility is in network for the patient’s plan' },
  { code: 'staffed_bed', name: 'Staffed bed', fallback: 'whether a staffed bed is open for this patient' },
  { code: 'wound_vac', name: 'Wound VAC', fallback: 'whether certified staff can manage a wound VAC' },
  { code: 'iv_infusion', name: 'IV infusion', fallback: 'whether they can administer the IV course' },
  { code: 'contact_isolation', name: 'Isolation', fallback: 'whether a contact isolation room is available' },
  { code: 'bariatric_capacity', name: 'Bariatric', fallback: 'whether they have bariatric equipment and staffing' },
] as const

const FACTS = [
  {
    title: 'Typed results',
    body: 'Each call returns yes, no or unknown per requirement, with the quote behind it. Unknown is never rounded up to yes.',
  },
  {
    title: 'Call provenance',
    body: 'Every call is stamped LIVE, REPLAY or SCRIPTED, and simulated answers are labeled separately. Nothing hides where a finding came from.',
  },
  {
    title: 'Budget guard',
    body: 'A hard ceiling is checked before every dial. A run that could overspend is refused before it starts.',
  },
  {
    title: 'Evidence vs ownership',
    body: 'A sister facility named on a call is evidence. A shared owner in the directory is only a lead, and is labeled as one.',
  },
  {
    title: 'Adaptive calls',
    body: 'The next call depends on the last answer: follow a named lead, widen the radius, or stop at a verified match.',
  },
]

/** One large editorial feature and five supporting facts separated by hairlines. No bento. */
export function Capabilities() {
  return (
    <section aria-labelledby="capabilities-heading" className="border-t border-hairline bg-surface-2/40 py-24 lg:py-32">
      <Container className="grid gap-16 lg:grid-cols-[minmax(0,7fr)_minmax(0,4fr)] lg:gap-20">
        <div>
          <Headline id="capabilities-heading" className="max-w-[36rem] text-[2.25rem] leading-[1.08] sm:text-[3rem]">
            The agent checks what the directory cannot.
          </Headline>
          <p className="mt-5 max-w-[34rem] text-[17px] leading-relaxed text-ink-muted">
            Hard constraints disqualify. Preferences like distance, CMS rating and partner status only rank. The two are never
            blended into one score that could hide a missing requirement.
          </p>

          <div className="mt-12 border-t border-ink/20">
            <p className="label-caps pt-4 text-ink-muted">Hard constraints</p>
            <ul className="mt-2">
              {HARD.map((item) => (
                <li key={item.code} className="grid gap-x-8 gap-y-1 border-b border-hairline py-4 sm:grid-cols-[11rem_1fr]">
                  <span className="text-[1.375rem] font-medium tracking-[-0.01em]">{item.name}</span>
                  <span className="text-[15px] leading-relaxed text-ink-muted">
                    Asks {ask.get(item.code) || item.fallback}.
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <ul className="self-end border-t border-ink/20">
          {FACTS.map((fact) => (
            <li key={fact.title} className="border-b border-hairline py-5">
              <p className="text-[16px] font-medium">{fact.title}</p>
              <p className="mt-1 text-[15px] leading-relaxed text-ink-muted">{fact.body}</p>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  )
}
