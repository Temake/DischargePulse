import { AppShell } from './components/layout/AppShell'
import { PatientIntakePanel } from './components/intake/PatientIntakePanel'
import { CognitiveLoopVisualizer } from './components/loop/CognitiveLoopVisualizer'
import { ContradictionBanner } from './components/contradictions/ContradictionBanner'
import { BedIntelligenceMatrix } from './components/matrix/BedIntelligenceMatrix'
import { CallTranscriptPanel } from './components/calls/CallTranscriptPanel'

// Layout only. ApprovalModal (components/approval) is mounted once a run
// reaches awaiting_approval - not wired yet.
export default function App() {
  return (
    <AppShell>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[320px_1fr_380px]">
        <aside className="space-y-6">
          <PatientIntakePanel />
        </aside>

        <section className="space-y-6">
          <CognitiveLoopVisualizer />
          <ContradictionBanner />
          <BedIntelligenceMatrix />
        </section>

        <aside className="space-y-6">
          <CallTranscriptPanel />
        </aside>
      </div>
    </AppShell>
  )
}
