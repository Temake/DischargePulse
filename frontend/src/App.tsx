import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'

import { Landing } from '@/routes/Landing'
import { RouteFallback } from '@/routes/RouteFallback'

// The console loads on demand so the landing ships without it.
const lazyNamed = <K extends string>(load: () => Promise<Record<K, React.ComponentType>>, name: K) =>
  lazy(() => load().then((module) => ({ default: module[name] })))

const AppShell = lazyNamed(() => import('@/app/shell/AppShell'), 'AppShell')
const Runs = lazyNamed(() => import('@/routes/Runs'), 'Runs')
const RunNew = lazyNamed(() => import('@/routes/RunNew'), 'RunNew')
const Run = lazyNamed(() => import('@/routes/Run'), 'Run')
const CallDetail = lazyNamed(() => import('@/routes/CallDetail'), 'CallDetail')
const Cases = lazyNamed(() => import('@/routes/Cases'), 'Cases')
const CaseDetail = lazyNamed(() => import('@/routes/Cases'), 'CaseDetail')
const Facilities = lazyNamed(() => import('@/routes/Facilities'), 'Facilities')
const System = lazyNamed(() => import('@/routes/System'), 'System')
const Console = lazyNamed(() => import('@/routes/Console'), 'Console')
const NotFound = lazyNamed(() => import('@/routes/NotFound'), 'NotFound')

export default function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<AppShell />}>
          <Route path="/console" element={<Console />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/new" element={<RunNew />} />
          <Route path="/runs/:runId" element={<Run />} />
          <Route path="/runs/:runId/calls/:facilityId" element={<CallDetail />} />
          <Route path="/cases" element={<Cases />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
          <Route path="/facilities" element={<Facilities />} />
          <Route path="/facilities/:facilityId" element={<Facilities />} />
          <Route path="/system" element={<System />} />
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  )
}
