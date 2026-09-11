import { Panel } from '../layout/Panel'
import { Placeholder } from '../layout/Placeholder'

/**
 * Facilities x hard requirements, one verification state per cell.
 * Source: FacilityEvaluation.findings on the run snapshot.
 */
export function BedIntelligenceMatrix() {
  return (
    <Panel title="Bed Intelligence Matrix">
      <Placeholder>Facilities x hard requirements with confirmed / not confirmed / unavailable / unknown.</Placeholder>
    </Panel>
  )
}
