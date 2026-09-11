import { Panel } from '../layout/Panel'
import { Placeholder } from '../layout/Placeholder'

/**
 * Live call intelligence that overrides stale directory data.
 * Source: FacilityEvaluation.contradictions.
 */
export function ContradictionBanner() {
  return (
    <Panel title="Contradictions">
      <Placeholder>Directory says X, live call says Y - with the quote from the call.</Placeholder>
    </Panel>
  )
}
