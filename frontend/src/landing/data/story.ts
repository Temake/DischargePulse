/**
 * The landing page's narrative, derived from the example run rather than typed
 * in. If the snapshot is regenerated from a different run, the copy follows
 * the data, and a missing beat simply disappears instead of being invented.
 */
import type { Contradiction, Facility, FacilityEvaluation } from '@/api/types'
import { snapshot, snapshotEvents, snapshotRun } from './snapshot'

const facilityById = new Map(snapshot.facilities.map((f) => [f.facility_id, f]))

export function facility(id: string): Facility | undefined {
  return facilityById.get(id)
}

const [firstPlan, secondPlan] = snapshotRun.plans

const withContradiction = snapshotRun.evaluations.find((e) =>
  e.contradictions.some((c) => c.code === 'wound_vac'),
) ?? snapshotRun.evaluations.find((e) => e.contradictions.length > 0)

const contradiction: Contradiction | undefined =
  withContradiction?.contradictions.find((c) => c.code === 'wound_vac') ?? withContradiction?.contradictions[0]

const contradictedFacility = withContradiction ? facility(withContradiction.facility_id) : undefined

const payerExclusions = Object.entries(firstPlan?.excluded ?? {}).filter(([, reason]) =>
  /payer/i.test(reason),
)

const match: FacilityEvaluation | undefined = snapshotRun.proposal?.evaluation

/** The facility a call named as a lead, and who named it. */
const lead = (() => {
  for (const evaluation of snapshotRun.evaluations) {
    const id = evaluation.sister_facility_leads[0]
    if (id) return { namedBy: evaluation, facility: facility(id) }
  }
  return null
})()

/** Event index (1-based count) at which each beat of the story has happened. */
function countThrough(predicate: (index: number) => boolean): number {
  const index = snapshotEvents.findIndex((_, i) => predicate(i))
  return index === -1 ? snapshotEvents.length : index + 1
}

export const beats = {
  planned: countThrough((i) => snapshotEvents[i].phase === 'plan'),
  firstBatchReasoned: countThrough(
    (i) => snapshotEvents[i].phase === 'replan' || (snapshotEvents[i].phase === 'plan' && snapshotEvents[i].cycle > 1),
  ) - 1,
  replanned: countThrough((i) => snapshotEvents[i].phase === 'plan' && snapshotEvents[i].cycle > 1),
  verified: countThrough((i) => snapshotEvents[i].phase === 'awaiting_approval'),
}

export const story = {
  patient: snapshot.patient,
  label: snapshot.label,
  disclaimer: snapshot.disclaimer,
  firstPlan,
  secondPlan,
  radius: firstPlan?.radius_miles ?? snapshot.patient.search_radius_miles,
  payerExclusions,
  withContradiction,
  contradiction,
  contradictedFacility,
  claim: contradictedFacility?.directory_claims.find((c) => c.code === contradiction?.code),
  lead,
  match,
  matchFacility: match ? facility(match.facility_id) : undefined,
  proposal: snapshotRun.proposal,
  firstAct: snapshotEvents.find((e) => e.phase === 'act'),
}
