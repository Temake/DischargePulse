/**
 * TypeScript mirror of the backend API contract.
 *
 * Declarations only. Field names are snake_case because they match the JSON
 * the FastAPI backend sends. Source of truth:
 *   backend/app/models/schemas.py
 *   backend/app/services/run_manager.py
 *   backend/app/api/routes.py
 *   backend/app/api/websocket.py
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type ConstraintKind = 'hard' | 'soft'

export type ConstraintCode =
  | 'payer_network'
  | 'staffed_bed'
  | 'wound_vac'
  | 'iv_infusion'
  | 'contact_isolation'
  | 'bariatric_capacity'
  | 'distance'
  | 'cms_rating'
  | 'preferred_partner'

export type VerificationState =
  | 'confirmed'
  | 'not_confirmed'
  | 'explicitly_unavailable'
  | 'unknown'

export type Disposition =
  | 'match_verified'
  | 'disqualified'
  | 'needs_follow_up'
  | 'unreached'

export type CallMode = 'live' | 'replay'

export type CallOutcome = 'completed' | 'failed' | 'canceled' | 'no_answer'

export type TranscriptSpeaker = 'bot' | 'user' | 'unknown'

export type AgentPhase =
  | 'plan'
  | 'act'
  | 'observe'
  | 'reason'
  | 'replan'
  | 'awaiting_approval'
  | 'complete'

export type ReplanTrigger =
  | 'no_beds_in_radius'
  | 'sister_facility_lead'
  | 'payer_mismatch'
  | 'contradiction_disqualified'
  | 'early_stop_match_found'
  | 'budget_exhausted'

export type RunStatus =
  | 'running'
  | 'awaiting_approval'
  | 'no_match_found'
  | 'approved'
  | 'declined'
  | 'failed'

export type ApprovalStatus = 'pending' | 'approved' | 'declined'

export type TelephonyMode = 'live' | 'replay' | 'auto'

/** Label of the actuator a run used. "scripted" appears only in tests. */
export type TelephonyLabel = 'live' | 'replay' | 'hybrid' | 'scripted' | string

// ---------------------------------------------------------------------------
// Reference data
// ---------------------------------------------------------------------------

export interface Requirement {
  code: ConstraintCode
  kind: ConstraintKind
  label: string
  detail: string
  ask_as: string
}

export interface PatientCase {
  case_id: string
  display_name: string
  age: number
  sex: string
  payer: string
  payer_plan: string
  weight_lbs: number
  hospital_day: number
  discharge_summary: string
  family_zip: string
  search_radius_miles: number
  max_radius_miles: number
  requirements: Requirement[]
  synthetic: boolean
}

export interface DirectoryClaim {
  code: ConstraintCode
  claimed_available: boolean
  source: string
  last_updated: string
}

export interface Facility {
  facility_id: string
  name: string
  facility_type: string
  phone: string
  admissions_extension: string | null
  address: string
  zip_code: string
  distance_miles: number
  cms_star_rating: number
  preferred_partner: boolean
  accepted_payers: string[]
  directory_claims: DirectoryClaim[]
  sister_facility_ids: string[]
  roleplay_brief: string | null
  synthetic: boolean
}

export interface FacilityView {
  facility: Facility
  dialable: boolean
}

// ---------------------------------------------------------------------------
// Calls and reasoning
// ---------------------------------------------------------------------------

export interface TranscriptTurn {
  offset_seconds: number | null
  speaker: TranscriptSpeaker
  text: string
}

export interface CallObservation {
  facility_id: string
  phone: string
  mode: CallMode
  roleplay_requested: boolean
  call_id: string | null
  provider_call_id: string | null
  started_at: string | null
  completed_at: string | null
  duration_seconds: number | null
  outcome: CallOutcome
  structured_result: Record<string, unknown> | null
  summary: string | null
  task_completed: boolean | null
  confidence_score: number | null
  confidence_label: string | null
  evidence: string[]
  transcript_turns: TranscriptTurn[]
  failure_code: string | null
  failure_message: string | null
  recorded_at: string
}

export interface ConstraintFinding {
  code: ConstraintCode
  kind: ConstraintKind
  label: string
  state: VerificationState
  quote: string | null
  rationale: string
}

export interface Contradiction {
  code: ConstraintCode
  label: string
  directory_says: string
  call_says: string
  quote: string | null
  resolution: string
}

export interface FacilityEvaluation {
  facility_id: string
  facility_name: string
  disposition: Disposition
  match_score: number
  findings: ConstraintFinding[]
  contradictions: Contradiction[]
  disqualifying_codes: ConstraintCode[]
  /** Sister facilities named on the call - live evidence. */
  sister_facility_leads: string[]
  /** Sister facilities from directory ownership data only - not call evidence. */
  ownership_leads: string[]
  coordinator_name: string | null
  callback_number: string | null
  fax_number: string | null
  observation: CallObservation | null
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

export interface AgentEvent {
  cycle: number
  phase: AgentPhase
  message: string
  facility_id: string | null
  trigger: ReplanTrigger | null
  payload: Record<string, unknown>
  at: string
}

export interface PlacementPlan {
  cycle: number
  radius_miles: number
  queue: string[]
  rationale: string
  excluded: Record<string, string>
}

export interface PlacementProposal {
  case_id: string
  facility_id: string
  facility_name: string
  match_score: number
  evaluation: FacilityEvaluation
  packet_path: string | null
  status: ApprovalStatus
  proposed_at: string
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
}

export interface PlacementRun {
  case_id: string
  status: RunStatus
  cycles_used: number
  calls_placed: number
  plans: PlacementPlan[]
  evaluations: FacilityEvaluation[]
  events: AgentEvent[]
  proposal: PlacementProposal | null
  error: string | null
}

export interface RunRecord {
  run_id: string
  case_id: string
  telephony: TelephonyLabel
  live_facility_ids: string[]
  started_at: string
  finished_at: string | null
  run: PlacementRun
}

export interface RunSummary {
  run_id: string
  case_id: string
  status: RunStatus
  telephony: TelephonyLabel
  calls_placed: number
  cycles_used: number
  started_at: string
  finished_at: string | null
  proposed_facility: string | null
}

// ---------------------------------------------------------------------------
// Requests and system views
// ---------------------------------------------------------------------------

export interface StartRunRequest {
  case_id: string
  mode?: TelephonyMode | null
  live_facility_ids?: string[]
  max_cycles?: number
  max_calls?: number | null
  replay_latency_seconds?: number
}

export interface DecisionRequest {
  decided_by: string
  note?: string | null
}

export interface BudgetView {
  spent: number
  ceiling: number
  remaining: number
}

export interface HealthView {
  status: string
  telephony_mode: TelephonyMode
  live_available: boolean
  budget: BudgetView
  cassettes: number
  synthetic_data_only: boolean
}

// ---------------------------------------------------------------------------
// WebSocket frames  (/ws/runs/{run_id})
// ---------------------------------------------------------------------------

export interface HelloFrame {
  type: 'hello'
  run_id: string
  case_id: string
  status: RunStatus
  telephony: TelephonyLabel
}

export interface EventFrame {
  type: 'event'
  event: AgentEvent
}

export interface RunFrame {
  type: 'run'
  run: RunRecord
}

export type StreamFrame = HelloFrame | EventFrame | RunFrame
