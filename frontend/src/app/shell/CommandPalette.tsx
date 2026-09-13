import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, m } from 'framer-motion'
import { useNavigate } from 'react-router'

import { useDialogFocus } from '@/components/ui/Sheet'
import { useFacilities, usePatients, useRuns } from '@/hooks/queries'
import { EXAMPLE_RUN_ID } from '@/landing/data/snapshot'
import { ageSex } from '@/lib/format'
import { runStatusLabel } from '@/lib/labels'
import { dur, ease } from '@/lib/motion'
import { setTheme, useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

interface Command {
  id: string
  group: string
  label: string
  detail?: string
  run: () => void
}

/**
 * Keyboard-first navigation. Ctrl/Cmd+K opens it; arrows move, Enter runs,
 * Escape closes. Built as an ARIA combobox over a listbox.
 */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const { theme } = useTheme()
  const runs = useRuns()
  const patients = usePatients()
  const facilities = useFacilities()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const panel = useRef<HTMLDivElement>(null)
  const listId = useId()
  const close = () => {
    setQuery('')
    setActive(0)
    onOpenChange(false)
  }
  useDialogFocus(open, panel, close)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setQuery('')
        setActive(0)
        onOpenChange(!open)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  const commands = useMemo<Command[]>(() => {
    const go = (to: string) => () => navigate(to)
    const list: Command[] = [
      { id: 'nav-runs', group: 'Go to', label: 'Runs', run: go('/runs') },
      { id: 'nav-new', group: 'Go to', label: 'Start a run', run: go('/runs/new') },
      { id: 'nav-cases', group: 'Go to', label: 'Cases', run: go('/cases') },
      { id: 'nav-facilities', group: 'Go to', label: 'Facilities', run: go('/facilities') },
      { id: 'nav-system', group: 'Go to', label: 'System', run: go('/system') },
      { id: 'nav-example', group: 'Go to', label: 'Example run', detail: 'Scripted, case 10482', run: go(`/runs/${EXAMPLE_RUN_ID}`) },
      { id: 'nav-home', group: 'Go to', label: 'Product overview', run: go('/') },
      {
        id: 'theme',
        group: 'Actions',
        label: theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme',
        run: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
      },
    ]
    for (const run of runs.data ?? []) {
      list.push({
        id: `run-${run.run_id}`,
        group: 'Runs',
        label: run.run_id,
        detail: `Case ${run.case_id} · ${runStatusLabel[run.status]}`,
        run: go(`/runs/${run.run_id}`),
      })
    }
    for (const patient of patients.data ?? []) {
      list.push({
        id: `case-${patient.case_id}`,
        group: 'Cases',
        label: `Case ${patient.case_id}`,
        detail: `${ageSex(patient)} · ${patient.payer_plan}`,
        run: go(`/cases/${patient.case_id}`),
      })
    }
    for (const view of facilities.data ?? []) {
      list.push({
        id: `facility-${view.facility.facility_id}`,
        group: 'Facilities',
        label: view.facility.name,
        detail: view.facility.facility_id,
        run: go(`/facilities/${view.facility.facility_id}`),
      })
    }
    return list
  }, [navigate, theme, runs.data, patients.data, facilities.data])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return commands.filter((c) => c.group === 'Go to' || c.group === 'Actions')
    return commands.filter((c) => `${c.label} ${c.detail ?? ''} ${c.group}`.toLowerCase().includes(q))
  }, [commands, query])

  const execute = (command: Command | undefined) => {
    if (!command) return
    close()
    command.run()
  }

  const activeId = filtered[active] ? `${listId}-${filtered[active].id}` : undefined

  return createPortal(
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-overlay flex items-start justify-center px-4 pt-[12vh]">
          <m.div
            className="absolute inset-0 bg-[#0c0f11]/35"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: dur.micro }}
            onClick={close}
            aria-hidden="true"
          />
          <m.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: dur.ui, ease: ease.out }}
            className="relative w-full max-w-lg overflow-hidden rounded-panel border border-hairline bg-surface shadow-overlay"
          >
            <input
              data-autofocus
              role="combobox"
              aria-expanded="true"
              aria-controls={listId}
              aria-activedescendant={activeId}
              aria-autocomplete="list"
              aria-label="Search pages, runs, cases and facilities"
              placeholder="Search pages, runs, cases, facilities"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setActive(0)
              }}
              onKeyDown={(event) => {
                if (event.key === 'ArrowDown') {
                  event.preventDefault()
                  setActive((i) => Math.min(filtered.length - 1, i + 1))
                } else if (event.key === 'ArrowUp') {
                  event.preventDefault()
                  setActive((i) => Math.max(0, i - 1))
                } else if (event.key === 'Enter') {
                  event.preventDefault()
                  execute(filtered[active])
                }
              }}
              className="h-12 w-full border-b border-hairline bg-transparent px-4 text-[15px] outline-none placeholder:text-ink-muted"
            />
            <ul id={listId} role="listbox" aria-label="Results" className="scrollbar-thin max-h-[50vh] overflow-y-auto py-1.5">
              {filtered.length === 0 ? (
                <li className="px-4 py-3 text-sm text-ink-muted">No matches.</li>
              ) : (
                filtered.map((command, index) => {
                  const showGroup = index === 0 || filtered[index - 1].group !== command.group
                  return (
                    <li key={command.id} role="presentation">
                      {showGroup ? <p className="px-4 pb-1 pt-2.5 text-[12px] text-ink-muted">{command.group}</p> : null}
                      <div
                        id={`${listId}-${command.id}`}
                        role="option"
                        aria-selected={index === active}
                        onMouseMove={() => setActive(index)}
                        onClick={() => execute(command)}
                        className={cn(
                          'mx-1.5 flex min-h-10 cursor-pointer items-center justify-between gap-4 rounded-field px-2.5 text-[14px]',
                          index === active && 'bg-surface-2',
                        )}
                      >
                        <span className={cn('truncate', command.group === 'Runs' && 'font-mono text-[13px]')}>{command.label}</span>
                        {command.detail ? <span className="shrink-0 truncate text-[12px] text-ink-muted">{command.detail}</span> : null}
                      </div>
                    </li>
                  )
                })
              )}
            </ul>
          </m.div>
        </div>
      ) : null}
    </AnimatePresence>,
    document.body,
  )
}
