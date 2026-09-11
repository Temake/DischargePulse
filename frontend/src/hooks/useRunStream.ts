/**
 * React hook over openRunStream (../api/stream).
 *
 * Scaffold only. Intended to expose the frames received for a run so panels can
 * render the cognitive loop, evaluations and approval state.
 */

import type { StreamFrame } from '../api/types'

export interface RunStreamState {
  frames: StreamFrame[]
}

export function useRunStream(_runId: string | null): RunStreamState {
  // TODO: subscribe with openRunStream and collect frames.
  return { frames: [] }
}
