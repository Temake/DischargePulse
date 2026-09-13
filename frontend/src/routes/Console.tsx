import { Navigate } from 'react-router'

import { isActive } from '@/agent/runSelectors'
import { SkeletonRows } from '@/components/ui/States'
import { useRuns } from '@/hooks/queries'

/** /console opens whatever needs attention: the newest active run, or a new one. */
export function Console() {
  const runs = useRuns()
  if (runs.isLoading) return <SkeletonRows rows={4} />
  const active = runs.data?.find((run) => isActive(run.status))
  return <Navigate to={active ? `/runs/${active.run_id}` : '/runs/new'} replace />
}
