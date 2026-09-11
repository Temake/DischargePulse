import { Panel } from '../layout/Panel'
import { Placeholder } from '../layout/Placeholder'

/**
 * Timestamped transcript and extracted result for the selected call.
 * Source: CallObservation.transcript_turns and structured_result.
 */
export function CallTranscriptPanel() {
  return (
    <Panel title="Call Transcript">
      <Placeholder>Timestamped transcript, extracted answers, confidence and evidence.</Placeholder>
    </Panel>
  )
}
