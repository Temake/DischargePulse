/**
 * REST client for the DischargePulse backend.
 *
 * Paths are relative in development (Vite proxies them to :8000). Set
 * VITE_API_BASE_URL when the static frontend and API are deployed separately.
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

export class ApiError extends Error {
  // Declared, not a constructor parameter property: erasableSyntaxOnly is on.
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/** FastAPI sends `{detail: string}` for handled errors and a list for validation errors. */
function detailOf(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null
  const detail = (body as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          const loc = 'loc' in item && Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
          return loc ? `${loc}: ${String(item.msg)}` : String(item.msg)
        }
        return String(item)
      })
      .join('; ')
  }
  return null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'The backend is not reachable.')
  }

  if (!response.ok) {
    let message = `${init?.method ?? 'GET'} ${path} failed with ${response.status}`
    try {
      message = detailOf(await response.json()) ?? message
    } catch {
      // Non-JSON error body (the dev proxy returns plain text when the backend is down).
      if (response.status >= 500) message = 'The backend is not reachable.'
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

// --- system ----------------------------------------------------------------

/** GET /api/health */
export function getHealth(): Promise<HealthView> {
  return request<HealthView>('/api/health')
}

/** GET /api/budget */
export function getBudget(): Promise<BudgetView> {
  return request<BudgetView>('/api/budget')
}

// --- reference data --------------------------------------------------------

/** GET /api/patients */
export function listPatients(): Promise<PatientCase[]> {
  return request<PatientCase[]>('/api/patients')
}

/** GET /api/patients/{case_id} */
export function getPatient(caseId: string): Promise<PatientCase> {
  return request<PatientCase>(`/api/patients/${encodeURIComponent(caseId)}`)
}

/** GET /api/facilities */
export function listFacilities(): Promise<FacilityView[]> {
  return request<FacilityView[]>('/api/facilities')
}

// --- runs ------------------------------------------------------------------

/** POST /api/runs - returns 202 with the run id; follow it on the WebSocket. */
export function startRun(body: StartRunRequest): Promise<RunRecord> {
  return post<RunRecord>('/api/runs', body)
}

/** GET /api/runs */
export function listRuns(): Promise<RunSummary[]> {
  return request<RunSummary[]>('/api/runs')
}

/** GET /api/runs/{run_id} */
export function getRun(runId: string): Promise<RunRecord> {
  return request<RunRecord>(`/api/runs/${encodeURIComponent(runId)}`)
}

/** POST /api/runs/{run_id}/approve - the human-in-the-loop gate. */
export function approveRun(runId: string, decision: DecisionRequest): Promise<RunRecord> {
  return post<RunRecord>(`/api/runs/${encodeURIComponent(runId)}/approve`, decision)
}

/** POST /api/runs/{run_id}/decline */
export function declineRun(runId: string, decision: DecisionRequest): Promise<RunRecord> {
  return post<RunRecord>(`/api/runs/${encodeURIComponent(runId)}/decline`, decision)
}
