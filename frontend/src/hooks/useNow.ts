import { useEffect, useState } from 'react'

/**
 * Wall-clock time, ticking once a second while `active`.
 * Drives the elapsed timer on in-flight calls: the only thing on a call row
 * allowed to change between backend events.
 */
export function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [active])

  return now
}
