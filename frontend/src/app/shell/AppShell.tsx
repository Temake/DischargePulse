import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'
import { m } from 'framer-motion'
import { List, Moon, Sun } from '@phosphor-icons/react'

import { IconButton } from '@/components/ui/Button'
import { Sheet } from '@/components/ui/Sheet'
import { useBudget, useHealth } from '@/hooks/queries'
import { telephonyName } from '@/lib/labels'
import { dur, ease } from '@/lib/motion'
import { useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { CommandPalette } from './CommandPalette'
import { CrumbProvider, useCrumbState } from './crumbs'

const NAV = [
  { to: '/runs', label: 'Runs', end: true },
  { to: '/runs/new', label: 'Start a run', end: true },
  { to: '/cases', label: 'Cases' },
  { to: '/facilities', label: 'Facilities' },
  { to: '/system', label: 'System' },
]

function Wordmark() {
  return (
    <Link to="/" className="inline-flex min-h-11 items-center text-[15px] font-semibold tracking-[-0.01em]">
      DischargePulse
    </Link>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation()
  return (
    <ul className="grid gap-0.5">
      {NAV.map((item) => {
        // /runs/:id belongs to Runs, but /runs/new is its own item.
        const runsChild = item.to === '/runs' && pathname.startsWith('/runs/') && pathname !== '/runs/new'
        return (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'relative flex min-h-11 items-center rounded-field px-3 text-[14px] transition-colors pointer-fine:min-h-9',
                  isActive || runsChild ? 'bg-surface-2 font-medium text-ink' : 'text-ink-muted hover:bg-surface-2/60 hover:text-ink',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive || runsChild ? (
                    <span className="absolute inset-y-2 left-0 w-[2px] rounded-full bg-accent" aria-hidden="true" />
                  ) : null}
                  {item.label}
                </>
              )}
            </NavLink>
          </li>
        )
      })}
    </ul>
  )
}

function Breadcrumbs() {
  const crumbs = useCrumbState()
  if (crumbs.length === 0) return null
  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1.5 text-[14px]">
        {crumbs.map((crumb, index) => {
          const last = index === crumbs.length - 1
          return (
            <li key={`${crumb.label}-${index}`} className={cn('flex min-w-0 items-center gap-1.5', !last && 'hidden sm:flex')}>
              {index > 0 ? (
                <span className="hidden text-ink-muted/60 sm:inline" aria-hidden="true">
                  /
                </span>
              ) : null}
              {crumb.to && !last ? (
                <Link to={crumb.to} className="truncate text-ink-muted hover:text-ink">
                  {crumb.label}
                </Link>
              ) : (
                <span className="truncate font-medium" aria-current={last ? 'page' : undefined}>
                  {crumb.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

function SystemReadout() {
  const health = useHealth()
  const budget = useBudget()
  const b = budget.data ?? health.data?.budget

  return (
    <Link
      to="/system"
      className="hidden items-center gap-5 rounded-field px-2 py-1 text-[13px] text-ink-muted hover:bg-surface-2 md:flex"
      aria-label="System status"
    >
      <span>
        Telephony{' '}
        <span className="text-ink">{health.data ? telephonyName(health.data.telephony_mode) : health.isError ? 'Offline' : '…'}</span>
      </span>
      {b ? (
        <span className="flex items-center gap-2">
          Budget
          <span className="font-mono tabular-nums text-ink">
            {b.spent}/{b.ceiling}
          </span>
          <span className="relative h-1 w-10 overflow-hidden rounded-full bg-hairline" aria-hidden="true">
            <span
              className={cn('absolute inset-y-0 left-0', b.remaining <= 2 ? 'bg-unavailable' : 'bg-ink/60')}
              style={{ width: `${Math.min(100, (b.spent / Math.max(1, b.ceiling)) * 100)}%` }}
            />
          </span>
        </span>
      ) : null}
    </Link>
  )
}

/**
 * The console frame: a quiet text rail, a top bar, and the page. Dense and
 * functional; it deliberately does not share the landing page's composition.
 */
export function AppShell() {
  const { theme, toggle } = useTheme()
  const [menuOpen, setMenuOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  return (
    <CrumbProvider>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-toast focus:rounded-field focus:bg-accent focus:px-4 focus:py-2.5 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to content
      </a>
      <div className="min-h-dvh bg-bg lg:grid lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label="Console" className="sticky top-0 hidden h-dvh flex-col border-r border-hairline px-3 py-3 lg:flex">
          <div className="px-2">
            <Wordmark />
          </div>
          <div className="mt-6">
            <NavItems />
          </div>
          <div className="mt-auto px-3 pb-2 text-[12px] leading-relaxed text-ink-muted">
            <p>Synthetic healthcare data only.</p>
            <p>Runs live in memory and clear when the backend restarts.</p>
          </div>
        </nav>

        <div className="min-w-0">
          <header className="sticky top-0 z-nav flex h-14 items-center gap-3 border-b border-hairline bg-bg/95 px-4 backdrop-blur-sm sm:px-6 lg:px-8">
            <IconButton className="-ml-2 lg:hidden" aria-label="Open navigation" onClick={() => setMenuOpen(true)}>
              <List size={20} />
            </IconButton>
            <Breadcrumbs />
            <div className="ml-auto flex items-center gap-1">
              <SystemReadout />
              <button
                type="button"
                onClick={() => setPaletteOpen(true)}
                className="inline-flex h-11 items-center gap-3 rounded-field px-2.5 text-[13px] text-ink-muted hover:bg-surface-2 hover:text-ink pointer-fine:h-9"
                aria-keyshortcuts="Control+K Meta+K"
              >
                <span className="hidden sm:inline">Search</span>
                <kbd className="rounded-edge border border-hairline px-1.5 font-mono text-[11px]">Ctrl K</kbd>
              </button>
              <IconButton onClick={toggle} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
                {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              </IconButton>
            </div>
          </header>

          <m.main
            id="main"
            // Facility detail is a sheet over the directory, so it must not remount the page.
            key={location.pathname.startsWith('/facilities') ? '/facilities' : location.pathname}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: dur.ui, ease: ease.out }}
            className="mx-auto w-full max-w-[1480px] px-4 pt-6 sm:px-6 lg:px-8"
          >
            <Outlet />
          </m.main>
        </div>
      </div>

      <Sheet open={menuOpen} onClose={() => setMenuOpen(false)} title={<Wordmark />} side="left" width="max-w-[18rem]">
        <nav aria-label="Console">
          <NavItems onNavigate={() => setMenuOpen(false)} />
        </nav>
        <p className="mt-8 px-3 text-[12px] leading-relaxed text-ink-muted">Synthetic healthcare data only.</p>
      </Sheet>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </CrumbProvider>
  )
}
