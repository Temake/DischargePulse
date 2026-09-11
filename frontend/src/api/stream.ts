/**
 * Live event stream for one placement run: /ws/runs/{run_id}
 *
 * Scaffold only. Frame shapes are in ./types (StreamFrame). Protocol, from
 * backend/app/api/websocket.py:
 *   - `hello` once on connect
 *   - every `event` the client missed is replayed, then live events follow
 *   - a full `run` snapshot on each state change
 *   - the server closes (1000) once the run is terminal; a run awaiting
 *     approval stays open so the case manager's decision arrives live
 *   - close code 4404 means the run id is unknown
 */

import type { StreamFrame } from './types'

export type FrameHandler = (frame: StreamFrame) => void

/** Opens the stream and returns a function that closes it. */
export function openRunStream(_runId: string, _onFrame: FrameHandler): () => void {
  throw new Error('openRunStream is not implemented yet')
}
