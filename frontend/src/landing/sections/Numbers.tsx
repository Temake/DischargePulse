import { Container } from '@/landing/layout'

const FIGURES = [
  { value: '3 to 5 hrs', label: 'phone work per placement, done by hand today' },
  { value: '6', label: 'concurrent calls per batch' },
  { value: '20', label: 'call ceiling, checked before every dial' },
  { value: '0', label: 'referrals sent without approval' },
]

/** A restrained strip. Static numbers, hairlines, no counters. */
export function Numbers() {
  return (
    <section aria-label="Operating limits" className="border-t border-hairline py-16 lg:py-20">
      <Container>
        <dl className="grid grid-cols-2 gap-y-10 lg:grid-cols-4">
          {FIGURES.map((figure, index) => (
            <div key={figure.label} className={index % 2 === 1 ? 'border-l border-hairline pl-5 lg:pl-8' : index > 0 ? 'lg:border-l lg:border-hairline lg:pl-8' : ''}>
              <dt className="sr-only">{figure.label}</dt>
              <dd>
                <span className="block text-[2.5rem] font-semibold leading-none tracking-[-0.03em] sm:text-[3rem]">{figure.value}</span>
                <span className="mt-2 block max-w-[14rem] text-[15px] text-ink-muted" aria-hidden="true">
                  {figure.label}
                </span>
              </dd>
            </div>
          ))}
        </dl>
      </Container>
    </section>
  )
}
