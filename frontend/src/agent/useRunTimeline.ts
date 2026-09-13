import { useCallback, useEffect, useMemo, useState } from 'react'
import { useReducedMotion } from 'framer-motion'

import type { AgentEvent } from '@/api/types'

/** Calls take longer than decisions. Pacing only; every event shown is real. */
const WEIGHT: Partial<Record<AgentEvent['phase'], number>> = { act: 2.2, awaiting_approval: 1.2 }

/**
 * Reveals a finished run's events on a timer so a viewer can watch the loop
 * unfold. The live console feeds the same components from the WebSocket; this
 * exists only for the example run.
 *
 * Reduced motion shows the finished state. Playback runs once when `active`
 * turns true, never on a loop.
 */
export function useRunTimeline(events: AgentEvent[], { active, stepMs = 1000 }: { active: boolean; stepMs?: number }) {
  const reduce = useReducedMotion()
  const [revealed, setRevealed] = useState(0)
  const [stopped, setStopped] = useState(false)

  const count = reduce ? events.length : revealed
  const playing = active && !reduce && !stopped && revealed < events.length

  useEffect(() => {
    if (!playing) return
    const delay = revealed === 0 ? 300 : stepMs * (WEIGHT[events[revealed - 1]?.phase] ?? 1)
    const id = window.setTimeout(() => setRevealed((value) => value + 1), delay)
    return () => window.clearTimeout(id)
  }, [playing, revealed, events, stepMs])

  const restart = useCallback(() => {
    setStopped(false)
    setRevealed(0)
  }, [])

  const skipToEnd = useCallback(() => {
    setStopped(true)
    setRevealed(events.length)
  }, [events.length])

  const shown = useMemo(() => events.slice(0, count), [events, count])

  return { shown, count, playing, finished: count >= events.length, restart, skipToEnd }
}
