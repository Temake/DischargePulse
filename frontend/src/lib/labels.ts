/**
 * Enum to human words. Every state the backend can send has exactly one
 * phrasing here, so the same word appears on the landing page and in the app.
 */
import type {
  AgentPhase,
  CallMode,
  ConstraintCode,
  Disposition,
  ReplanTrigger,
  RunStatus,
  TelephonyLabel,
  TelephonyMode,
  TranscriptSpeaker,
  VerificationState,
} from '@/api/types'

export const phaseLabel: Record<AgentPhase, string> = {
  plan: 'Plan',
  act: 'Act',
  observe: 'Observe',
  reason: 'Reason',
  replan: 'Re-plan',
  awaiting_approval: 'Human gate',
  complete: 'Complete',
}

/** The five loop phases. The gate sits outside the loop on purpose. */
export const LOOP_PHASES: AgentPhase[] = ['plan', 'act', 'observe', 'reason', 'replan']

export const verificationLabel: Record<VerificationState, string> = {
  confirmed: 'Confirmed',
  not_confirmed: 'Not confirmed',
  explicitly_unavailable: 'Unavailable',
  unknown: 'Unknown',
}

/** Token class per state. Color never travels alone; a glyph always rides with it. */
export const verificationTone: Record<VerificationState, string> = {
  confirmed: 'text-confirmed',
  not_confirmed: 'text-not-confirmed',
  explicitly_unavailable: 'text-unavailable',
  unknown: 'text-unknown',
}

export const dispositionLabel: Record<Disposition, string> = {
  match_verified: 'Verified match',
  disqualified: 'Disqualified',
  needs_follow_up: 'Needs follow-up',
  unreached: 'Not reached',
}

export const dispositionTone: Record<Disposition, string> = {
  match_verified: 'text-confirmed',
  disqualified: 'text-unavailable',
  needs_follow_up: 'text-not-confirmed',
  unreached: 'text-unknown',
}

export const triggerLabel: Record<ReplanTrigger, string> = {
  no_beds_in_radius: 'Nothing left in radius',
  sister_facility_lead: 'Sister facility lead',
  payer_mismatch: 'Payer mismatch',
  contradiction_disqualified: 'Facility disqualified',
  early_stop_match_found: 'Match found, sweep stopped',
  budget_exhausted: 'Call ceiling reached',
}

export const runStatusLabel: Record<RunStatus, string> = {
  running: 'Running',
  awaiting_approval: 'Awaiting approval',
  no_match_found: 'No match found',
  approved: 'Approved',
  declined: 'Declined',
  failed: 'Failed',
}

/** Provenance stamp for one call. */
export const callModeLabel: Record<CallMode, string> = {
  live: 'LIVE',
  replay: 'REPLAY',
  scripted: 'SCRIPTED',
}

export const telephonyLabel: Record<string, string> = {
  live: 'Live',
  replay: 'Replay',
  hybrid: 'Hybrid',
  simulated: 'Simulated attendant',
  scripted: 'Scripted',
  auto: 'Auto',
}

export function telephonyName(label: TelephonyLabel | TelephonyMode): string {
  return telephonyLabel[label] ?? label
}

export const telephonyDescription: Record<TelephonyMode, string> = {
  replay:
    'Serves recorded calls from cassettes. Facilities with no recording come back not reached. No credit spent.',
  scripted:
    'No calls placed. Attendant answers come from the test scenario and are labeled scripted. No credit spent.',
  simulated:
    'Real CALL-E calls to the stand-in line. If the line gives no usable answers, attendant answers are simulated and labeled. Spends credit.',
  live: 'Real CALL-E calls. Spends credit against the call budget.',
  auto: 'Live when CALL-E credentials are configured, otherwise replay.',
}

/** Short column names for hard constraints. */
export const constraintShort: Record<ConstraintCode, string> = {
  payer_network: 'Payer',
  staffed_bed: 'Bed',
  wound_vac: 'Wound VAC',
  iv_infusion: 'IV',
  contact_isolation: 'Isolation',
  bariatric_capacity: 'Bariatric',
  distance: 'Distance',
  cms_rating: 'CMS rating',
  preferred_partner: 'Preferred partner',
}

/** Canonical column order for the bed intelligence matrix. */
export const HARD_ORDER: ConstraintCode[] = [
  'payer_network',
  'staffed_bed',
  'wound_vac',
  'iv_infusion',
  'contact_isolation',
  'bariatric_capacity',
]

export const speakerLabel: Record<TranscriptSpeaker, string> = {
  bot: 'Agent',
  user: 'Admissions',
  unknown: 'Unattributed',
}
