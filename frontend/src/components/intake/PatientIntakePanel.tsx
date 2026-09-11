import { Panel } from '../layout/Panel'
import { Placeholder } from '../layout/Placeholder'

/**
 * Synthetic patient selector with hard constraints and soft preferences.
 * Source: GET /api/patients, GET /api/patients/{case_id}.
 */
export function PatientIntakePanel() {
  return (
    <Panel title="Patient & Requirements">
      <Placeholder>Patient selector, hard constraints, soft preferences, start-run controls.</Placeholder>
    </Panel>
  )
}
