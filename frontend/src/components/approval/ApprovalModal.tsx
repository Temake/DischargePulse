import { Panel } from '../layout/Panel'
import { Placeholder } from '../layout/Placeholder'

/**
 * Human-in-the-loop gate. The agent proposes; a case manager decides.
 * Source: PlacementProposal; POST /api/runs/{run_id}/approve | /decline.
 */
export function ApprovalModal() {
  return (
    <Panel title="Approve Placement">
      <Placeholder>Proposed facility, match score, approve / decline with decider name.</Placeholder>
    </Panel>
  )
}
