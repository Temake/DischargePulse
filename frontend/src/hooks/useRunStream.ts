import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { openRunStream, type StreamStatus } from '@/api/stream'
import type { AgentEvent, HelloFrame } from '@/api/types'
import { keys } from './queries'

export interface RunStreamState {
  status: StreamStatus
  hello: HelloFrame | null
  /** Every event since the run began, rebuilt from the backlog on each connect. */
  events: AgentEvent[]
}

/** Phases after which the run record has new plans, evaluations or a proposal to fetch. */
const REFETCH_PHASES = new Set(['plan', 'observe', 'reason', 'replan', 'awaiting_approval', 'complete'])

/**
 * Follows one run over the WebSocket.
 *
 * Events drive the loop, trace and call lanes directly. The `run` frame is only
 * sent on state changes, so evaluations appended mid-run are fetched from REST
 * after the events that produce them. Nothing here invents progress between
 * events: the backend sends none.
 */
export function useRunStream(runId: string | null): RunStreamState {
  const queryClient = useQueryClient()
  // State is tagged with its run so switching runs never shows the previous run's events.
  const [state, setState] = useState<RunStreamState & { runId: string | null }>({ ...INITIAL, runId })
  const refetchTimer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!runId) return

    const scheduleRefetch = () => {
      window.clearTimeout(refetchTimer.current)
      refetchTimer.current = window.setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: keys.run(runId), exact: true })
      }, 200)
    }

    const forRun = (prev: RunStreamState & { runId: string | null }) =>
      prev.runId === runId ? prev : { ...INITIAL, runId }

    const close = openRunStream(runId, {
      onStatus: (status) => setState((prev) => ({ ...forRun(prev), status })),
      onFrame: (frame) => {
        if (frame.type === 'hello') {
          // The backlog follows; start clean so a reconnect never duplicates events.
          setState((prev) => ({ ...forRun(prev), hello: frame, events: [] }))
          return
        }
        if (frame.type === 'event') {
          setState((prev) => {
            const base = forRun(prev)
            return { ...base, events: [...base.events, frame.event] }
          })
          if (REFETCH_PHASES.has(frame.event.phase)) scheduleRefetch()
          return
        }
        queryClient.setQueryData(keys.run(runId), frame.run)
        void queryClient.invalidateQueries({ queryKey: keys.runs, exact: true })
        void queryClient.invalidateQueries({ queryKey: keys.budget })
        void queryClient.invalidateQueries({ queryKey: keys.health })
      },
    })

    return () => {
      window.clearTimeout(refetchTimer.current)
      close()
    }
  }, [runId, queryClient])

  if (state.runId !== runId) return INITIAL
  return state
}

const INITIAL: RunStreamState = { status: 'connecting', hello: null, events: [] }
