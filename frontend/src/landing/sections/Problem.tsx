import { story } from '@/landing/data/story'
import { Container } from '@/landing/layout'
import { date } from '@/lib/format'

/**
 * Typography and whitespace only. The three lines are the product thesis in
 * the order a case manager lives it.
 */
export function Problem() {
  const name = story.contradictedFacility?.name.split(' ')[0] ?? 'A facility'
  return (
    <section aria-labelledby="problem-heading" className="border-t border-hairline py-24 lg:py-32">
      <Container className="grid gap-14 lg:grid-cols-12 lg:gap-8">
        <div className="lg:col-span-7 lg:col-start-2">
          <h2 id="problem-heading" className="sr-only">
            The problem
          </h2>
          <p className="text-balance text-[1.75rem] font-medium leading-[1.2] tracking-[-0.02em] sm:text-[2.25rem]">
            A directory said {name} could take a wound VAC patient.
          </p>
          <p className="mt-6 text-balance text-[1.75rem] font-medium leading-[1.2] tracking-[-0.02em] text-ink-muted sm:text-[2.25rem]">
            The night nurse was not signed off.
          </p>
          <p className="mt-12 max-w-[34rem] text-[18px] leading-relaxed">
            The mistake is small in a directory. It is not small at discharge.
            {story.claim ? (
              <span className="text-ink-muted">
                {' '}
                That record was last updated {date(story.claim.last_updated)}. Case managers find out the rest by
                phone: beds, insurance, clinical capability, admissions hours, phone menus and receptionists.
              </span>
            ) : null}
          </p>
        </div>

        <aside className="border-t border-ink/15 pt-4 lg:col-span-3 lg:col-start-10 lg:mt-3 lg:self-start">
          <p className="text-[2.75rem] font-semibold leading-none tracking-[-0.03em]">3 to 5 hours</p>
          <p className="mt-2 text-[15px] text-ink-muted">typical phone work per placement</p>
        </aside>
      </Container>
    </section>
  )
}
