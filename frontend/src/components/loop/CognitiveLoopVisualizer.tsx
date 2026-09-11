import { Panel } from '../layout/Panel'
import { Placeholder } from '../layout/Placeholder'

/**
 * Plan -> Act -> Observe -> Reason -> Re-Plan timeline, one entry per AgentEvent.
 * Source: `event` frames from /ws/runs/{run_id}.
 */
export function CognitiveLoopVisualizer() {
  return (
    <Panel title="Agent Cognitive Loop">
      <Placeholder>Plan / Act / Observe / Reason / Re-Plan timeline, grouped by cycle.</Placeholder>
    </Panel>
  )
}
