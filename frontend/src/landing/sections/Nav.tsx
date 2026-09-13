import { useState } from 'react'
import { Link } from 'react-router'
import { List } from '@phosphor-icons/react'

import { ButtonLink, IconButton } from '@/components/ui/Button'
import { Sheet } from '@/components/ui/Sheet'

const LINKS = [
  { href: '#how-it-works', label: 'How it works' },
  { href: '#contradiction', label: 'The contradiction' },
  { href: '#safety', label: 'Safety' },
  { href: '#faq', label: 'FAQ' },
]

/** One quiet floating bar. No shrink-on-scroll, no glass spectacle. */
export function Nav() {
  const [open, setOpen] = useState(false)

  return (
    <header className="fixed inset-x-0 top-0 z-nav px-3 pt-3 sm:px-5">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-14 max-w-[1280px] items-center gap-6 rounded-panel border border-hairline bg-bg/92 pl-4 pr-2 backdrop-blur-sm sm:pl-5"
      >
        <Link to="/" className="inline-flex min-h-11 items-center text-[15px] font-semibold tracking-[-0.01em]">
          DischargePulse
        </Link>
        <ul className="ml-auto hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="inline-flex h-10 items-center rounded-field px-3 text-[14px] text-ink-muted transition-colors hover:text-ink"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <ButtonLink to="/console" size="sm" className="ml-auto hidden md:ml-2 md:inline-flex">
          Open console
        </ButtonLink>
        <IconButton className="ml-auto md:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
          <List size={20} />
        </IconButton>
      </nav>

      <Sheet open={open} onClose={() => setOpen(false)} title="DischargePulse" width="max-w-[20rem]">
        <ul className="grid">
          {LINKS.map((link) => (
            <li key={link.href} className="border-b border-hairline">
              <a href={link.href} onClick={() => setOpen(false)} className="flex min-h-12 items-center text-[16px]">
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <ButtonLink to="/console" className="mt-6 w-full">
          Open console
        </ButtonLink>
      </Sheet>
    </header>
  )
}
