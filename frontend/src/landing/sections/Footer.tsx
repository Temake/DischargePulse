import { Link } from 'react-router'

import { Container } from '@/landing/layout'

const REPO = 'https://github.com/Temake/DischargePulse/blob/main'

const LINKS = [
  { label: 'Product', to: '/' },
  { label: 'Architecture', href: `${REPO}/ARCHITECTURE.md` },
  { label: 'Runbook', href: `${REPO}/docs/DEMO_RUNBOOK.md` },
  { label: 'API', href: 'http://localhost:8000/docs', note: 'local backend' },
]

export function Footer() {
  return (
    <footer className="border-t border-hairline py-12">
      <Container className="grid gap-8 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
        <div>
          <p className="text-[15px] font-semibold">DischargePulse</p>
          <p className="mt-2 text-[14px] text-ink-muted">Synthetic healthcare data only.</p>
          <p className="text-[14px] text-ink-muted">Built for the CALL-E hackathon.</p>
        </div>
        <nav aria-label="Footer">
          <ul className="grid grid-cols-2 gap-x-10 gap-y-1 text-[14px] sm:grid-cols-4">
            {LINKS.map((link) => (
              <li key={link.label}>
                {link.to ? (
                  <Link to={link.to} className="inline-flex min-h-11 items-center text-ink-muted hover:text-ink">
                    {link.label}
                  </Link>
                ) : (
                  <a
                    href={link.href}
                    className="inline-flex min-h-11 items-center text-ink-muted hover:text-ink"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {link.label}
                    {link.note ? <span className="sr-only"> ({link.note})</span> : null}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </nav>
      </Container>
    </footer>
  )
}
