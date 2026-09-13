import { ButtonLink } from '@/components/ui/Button'
import { EXAMPLE_RUN_ID } from '@/landing/data/snapshot'
import { Container, Headline } from '@/landing/layout'

/** An editorial close. The faintest accent tint, no banner. */
export function FinalCta() {
  return (
    <section aria-labelledby="cta-heading" className="border-t border-hairline bg-accent-tint/35 py-24 dark:bg-accent-tint/20 lg:py-32">
      <Container className="grid items-end gap-10 lg:grid-cols-[minmax(0,7fr)_minmax(0,4fr)]">
        <Headline id="cta-heading" className="text-[2.5rem] leading-[1.04] sm:text-[3.5rem]">
          Let the agent make the calls.
          <span className="block text-ink-muted">Keep the decision human.</span>
        </Headline>
        <div className="flex flex-wrap gap-3 lg:justify-end">
          <ButtonLink to={`/runs/${EXAMPLE_RUN_ID}`}>Watch the agent work</ButtonLink>
          <ButtonLink to="/console" variant="secondary">
            Open the console
          </ButtonLink>
        </div>
      </Container>
    </section>
  )
}
