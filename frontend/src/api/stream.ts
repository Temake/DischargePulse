/**
 * Live event stream for one placement run: /ws/runs/{run_id}
 *
 * Protocol, from backend/app/api/websocket.py:
 *   - `hello` once on connect
 *   - every `event` the client missed is replayed, then live events follow
 *   - a full `run` snapshot on each state change
 *   - the server closes (1000) once the run is terminal; a run awaiting
 *     approval stays open so the case manager's decision arrives live
 *   - an unknown run id is refused before the socket opens
 *
 * Because every connect replays the full history, a reconnect is safe: the
 * consumer resets its event list on `hello` and rebuilds from the backlog.
 */

import type { StreamFrame } from './types'

export type StreamStatus = 'connecting' | 'open' | 'reconnecting' | 'closed' | 'unavailable'

export interface StreamHandlers {
  onFrame: (frame: StreamFrame) => void
  onStatus: (status: StreamStatus) => void
}

const MAX_ATTEMPTS = 6

function streamUrl(runId: string): string {
  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
  if (apiBaseUrl) {
    const api = new URL(apiBaseUrl)
    api.protocol = api.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${api.protocol}//${api.host}/ws/runs/${encodeURIComponent(runId)}`
  }
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/ws/runs/${encodeURIComponent(runId)}`
}

/** Opens the stream and returns a function that closes it. */
export function openRunStream(runId: string, { onFrame, onStatus }: StreamHandlers): () => void {
  let socket: WebSocket | null = null
  let attempts = 0
  let stopped = false
  let timer: number | undefined

  const connect = () => {
    onStatus(attempts === 0 ? 'connecting' : 'reconnecting')
    socket = new WebSocket(streamUrl(runId))
    let greeted = false

    socket.onmessage = (message) => {
      let frame: StreamFrame
      try {
        frame = JSON.parse(message.data as string) as StreamFrame
      } catch {
        return
      }
      if (frame.type === 'hello') {
        greeted = true
        attempts = 0
        onStatus('open')
      }
      onFrame(frame)
    }

    socket.onclose = (event) => {
      socket = null
      if (stopped) return
      // A normal close after hello means the run is terminal and fully delivered.
      if (greeted && event.code === 1000) {
        onStatus('closed')
        return
      }
      attempts += 1
      if (attempts > MAX_ATTEMPTS) {
        onStatus('unavailable')
        return
      }
      onStatus('reconnecting')
      timer = window.setTimeout(connect, Math.min(8000, 500 * 2 ** (attempts - 1)))
    }
  }

  connect()

  return () => {
    stopped = true
    window.clearTimeout(timer)
    socket?.close()
  }
}
