/**
 * Turning a run into what each panel needs.
 *
 * Two sources feed the same components: a live run (REST record plus the
 * WebSocket event stream) and the example playback (a finished record whose
 * events are revealed on a timer). Both are reduced to a `RunView` here.
 *
 * The backend sends no mid-call progress: between an `act` event and its
 * `observe` events, all the UI knows is which calls are in flight and when the
 * batch started. These selectors carry exactly that much and no more.
 */
import type {
  AgentEvent,
  AgentPhase,
  AnswersSource,
  CallMode,
  Contradiction,
  FacilityEvaluation,
  PlacementPlan,
  PlacementProposal,
  RunRecord,
  RunStatus,
  TelephonyLabel,
} from '@/api/types'

export interface RunView {
  runId: string
  caseId: string
  telephony: TelephonyLabel
  liveFacilityIds: string[]
  status: RunStatus
  startedAt: string
  finishedAt: string | null
  events: AgentEvent[]
  plans: PlacementPlan[]
  evaluations: FacilityEvaluation[]
  proposal: PlacementProposal | null
  callsPlaced: number
  liveCalls: number
  cyclesUsed: number
  error: string | null
}

export function viewFromRecord(record: RunRecord, events?: AgentEvent[]): RunView {
  const run = record.run
  return {
    runId: record.run_id,
    caseId: record.case_id,
    telephony: record.telephony,
    liveFacilityIds: record.live_facility_ids,
    status: run.status,
    startedAt: record.started_at,
    finishedAt: record.finished_at,
    events: events && events.length >= run.events.length ? events : run.events,
    plans: run.plans,
    evaluations: run.evaluations,
    proposal: run.proposal,
    callsPlaced: run.calls_placed,
    liveCalls: run.live_calls,
    cyclesUsed: run.cycles_used,
    error: run.error,
  }
}

/**
 * The view of a finished run as it stood after `shown` events. Every field is
 * derived from events that have been revealed, so playback never shows a
 * finding before the event that produced it.
 */
export function viewAtEvents(record: RunRecord, shown: AgentEvent[]): RunView {
  const run = record.run
  const planCount = shown.filter((e) => e.phase === 'plan').length
  const reasoned = new Set(shown.filter((e) => e.phase === 'reason').map((e) => e.facility_id))
  const gate = shown.some((e) => e.phase === 'awaiting_approval' || e.phase === 'complete')
  const done = shown.length >= run.events.length
  return {
    ...viewFromRecord(record, shown),
    events: shown,
    status: done ? run.status : 'running',
    finishedAt: done ? record.finished_at : null,
    plans: run.plans.slice(0, planCount),
    evaluations: run.evaluations.filter((e) => reasoned.has(e.facility_id)),
    proposal: gate ? run.proposal : null,
    callsPlaced: shown.filter((e) => e.phase === 'observe').length,
    cyclesUsed: shown.reduce((max, e) => Math.max(max, e.cycle), 0),
  }
}

// ---------------------------------------------------------------------------
// Loop position
// ---------------------------------------------------------------------------

export function currentPhase(view: Pick<RunView, 'events'>): AgentPhase | null {
  return view.events[view.events.length - 1]?.phase ?? null
}

export function isActive(status: RunStatus): boolean {
  return status === 'running' || status === 'awaiting_approval'
}

// ---------------------------------------------------------------------------
// Call lanes
// ---------------------------------------------------------------------------

export type LaneState = 'in_flight' | 'observed' | 'failed'

export interface CallLane {
  facilityId: string
  cycle: number
  state: LaneState
  /** When the batch this call belongs to was dispatched. */
  dispatchedAt: string
  /** Whether this leg was dialed live, known before any result arrives. */
  expectedMode: CallMode
  mode: CallMode | null
  answersSource: AnswersSource | null
  callId: string | null
  durationSeconds: number | null
  transcriptTurns: number
  message: string | null
  evaluation: FacilityEvaluation | null
}

function num(value: unknown): number | null {
  return typeof value === 'number' ? value : null
}

function str(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function expectedModeFor(telephony: TelephonyLabel, facilityId: string, liveIds: string[]): CallMode {
  if (telephony === 'live' || telephony === 'simulated') return 'live'
  if (telephony === 'hybrid') return liveIds.includes(facilityId) ? 'live' : 'replay'
  if (telephony === 'scripted') return 'scripted'
  return 'replay'
}

/** Lanes for the calls the run has reached so far, in dispatch order. */
export function lanesFrom(view: RunView): CallLane[] {
  const lanes = new Map<string, CallLane>()
  const evaluations = new Map(view.evaluations.map((e) => [e.facility_id, e]))

  for (const event of view.events) {
    if (event.phase === 'act') {
      const ids = event.payload.facility_ids
      if (!Array.isArray(ids)) continue
      for (const id of ids as string[]) {
        if (lanes.has(id)) continue
        lanes.set(id, {
          facilityId: id,
          cycle: event.cycle,
          state: 'in_flight',
          dispatchedAt: event.at,
          expectedMode: expectedModeFor(view.telephony, id, view.liveFacilityIds),
          mode: null,
          answersSource: null,
          callId: null,
          durationSeconds: null,
          transcriptTurns: 0,
          message: null,
          evaluation: null,
        })
      }
    }

    if (event.phase === 'observe' && event.facility_id) {
      const lane = lanes.get(event.facility_id)
      if (!lane) continue
      const mode = str(event.payload.mode) as CallMode | null
      lane.message = event.message
      if (!mode) {
        // The agent emits an observe with no payload when the call itself raised.
        lane.state = 'failed'
        continue
      }
      lane.state = 'observed'
      lane.mode = mode
      lane.answersSource = (str(event.payload.answers_source) as AnswersSource | null) ?? 'call'
      lane.callId = str(event.payload.call_id)
      lane.durationSeconds = num(event.payload.duration_seconds)
      lane.transcriptTurns = num(event.payload.transcript_turns) ?? 0
    }
  }

  for (const lane of lanes.values()) {
    lane.evaluation = evaluations.get(lane.facilityId) ?? null
  }
  return [...lanes.values()]
}

// ---------------------------------------------------------------------------
// Contradictions
// ---------------------------------------------------------------------------

export interface FoundContradiction {
  evaluation: FacilityEvaluation
  contradiction: Contradiction
}

export function contradictionsOf(evaluations: FacilityEvaluation[]): FoundContradiction[] {
  return evaluations.flatMap((evaluation) =>
    evaluation.contradictions.map((contradiction) => ({ evaluation, contradiction })),
  )
}

/** Who a finding came from, in the words the backend uses. */
export function sourceName(evaluation: Pick<FacilityEvaluation, 'observation'>): string {
  const observation = evaluation.observation
  if (!observation) return 'Call'
  if (observation.mode === 'scripted') return 'Scripted attendant'
  if (observation.answers_source === 'simulated') return 'Simulated attendant'
  return observation.mode === 'replay' ? 'Recorded call' : 'Live call'
}
