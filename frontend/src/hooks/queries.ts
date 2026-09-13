import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import {
  getBudget,
  getHealth,
  getPatient,
  getRun,
  listFacilities,
  listPatients,
  listRuns,
} from '@/api/client'
import type { Facility } from '@/api/types'

/** Query keys in one place so stream handlers invalidate the right entries. */
export const keys = {
  health: ['health'] as const,
  budget: ['budget'] as const,
  patients: ['patients'] as const,
  patient: (id: string) => ['patients', id] as const,
  facilities: ['facilities'] as const,
  runs: ['runs'] as const,
  run: (id: string) => ['runs', id] as const,
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: getHealth, retry: false, refetchInterval: 30_000 })
}

export function useBudget() {
  return useQuery({ queryKey: keys.budget, queryFn: getBudget, retry: false, staleTime: 10_000 })
}

export function usePatients() {
  return useQuery({ queryKey: keys.patients, queryFn: listPatients, staleTime: Infinity, retry: 1 })
}

export function usePatient(caseId: string | undefined) {
  return useQuery({
    queryKey: keys.patient(caseId ?? ''),
    queryFn: () => getPatient(caseId!),
    enabled: Boolean(caseId),
    staleTime: Infinity,
    retry: 1,
  })
}

export function useFacilities() {
  return useQuery({ queryKey: keys.facilities, queryFn: listFacilities, staleTime: Infinity, retry: 1 })
}

/** Facility lookup by id. Empty until the directory loads. */
export function useFacilityIndex(): Map<string, Facility> {
  const { data } = useFacilities()
  return useMemo(() => new Map((data ?? []).map((view) => [view.facility.facility_id, view.facility])), [data])
}

export function useRuns() {
  return useQuery({ queryKey: keys.runs, queryFn: listRuns, retry: 1, refetchInterval: 15_000 })
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: keys.run(runId ?? ''),
    queryFn: () => getRun(runId!),
    enabled: Boolean(runId),
    retry: (count, error) => (error as { status?: number }).status !== 404 && count < 2,
  })
}
