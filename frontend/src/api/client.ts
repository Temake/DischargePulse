/**
 * REST client for the DischargePulse backend.
 *
 * Scaffold only: signatures match the backend routes, bodies are not written.
 * Paths are relative - Vite proxies /api to the backend in development.
 */

import type {
  BudgetView,
  DecisionRequest,
  FacilityView,
  HealthView,
  PatientCase,
  RunRecord,
  RunSummary,
  StartRunRequest,
} from './types'

const notImplemented = (name: string): never => {
  throw new Error(`api.${name} is not implemented yet`)
}

// --- system ----------------------------------------------------------------

/** GET /api/health */
export function getHealth(): Promise<HealthView> {
  return notImplemented('getHealth')
}

/** GET /api/budget */
export function getBudget(): Promise<BudgetView> {
  return notImplemented('getBudget')
}

// --- reference data --------------------------------------------------------

/** GET /api/patients */
export function listPatients(): Promise<PatientCase[]> {
  return notImplemented('listPatients')
}

/** GET /api/patients/{case_id} */
export function getPatient(_caseId: string): Promise<PatientCase> {
  return notImplemented('getPatient')
}

/** GET /api/facilities */
export function listFacilities(): Promise<FacilityView[]> {
  return notImplemented('listFacilities')
}

// --- runs ------------------------------------------------------------------

/** POST /api/runs - returns 202 with the run id; follow it on the WebSocket. */
export function startRun(_request: StartRunRequest): Promise<RunRecord> {
  return notImplemented('startRun')
}

/** GET /api/runs */
export function listRuns(): Promise<RunSummary[]> {
  return notImplemented('listRuns')
}

/** GET /api/runs/{run_id} */
export function getRun(_runId: string): Promise<RunRecord> {
  return notImplemented('getRun')
}

/** POST /api/runs/{run_id}/approve - the human-in-the-loop gate. */
export function approveRun(_runId: string, _decision: DecisionRequest): Promise<RunRecord> {
  return notImplemented('approveRun')
}

/** POST /api/runs/{run_id}/decline */
export function declineRun(_runId: string, _decision: DecisionRequest): Promise<RunRecord> {
  return notImplemented('declineRun')
}
