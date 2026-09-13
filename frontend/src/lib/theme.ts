import { useCallback, useSyncExternalStore } from 'react'

/**
 * Light / dark theme, class-driven so the toggle wins over the OS setting.
 * The choice is a per-viewer convenience kept in localStorage; when storage is
 * unavailable the page simply follows the OS.
 */
export type Theme = 'light' | 'dark'

const KEY = 'dp-theme'
const listeners = new Set<() => void>()

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

function current(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

export function applyInitialTheme() {
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  const theme = stored() ?? (prefersDark ? 'dark' : 'light')
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

export function setTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    // Storage blocked: the change still applies for this page view.
  }
  listeners.forEach((listener) => listener())
}

export function useTheme() {
  const theme = useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    current,
    () => 'light' as Theme,
  )
  const toggle = useCallback(() => setTheme(current() === 'dark' ? 'light' : 'dark'), [])
  return { theme, toggle }
}
