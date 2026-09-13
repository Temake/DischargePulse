import { lazy, Suspense, useEffect } from 'react'

import { Hero } from '@/landing/sections/Hero'
import { Nav } from '@/landing/sections/Nav'

// Everything below the fold arrives in a second chunk.
const BelowFold = lazy(() => import('@/landing/BelowFold'))

/**
 * The landing page: a product narrative for hospital operations leaders, told
 * with the example run's real data. Editorial and spacious, where the console
 * is dense; the agent components are shared between the two.
 */
export function Landing() {
  useEffect(() => {
    document.title = 'DischargePulse · The agent makes the calls. You make the decision.'
  }, [])

  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-toast focus:rounded-field focus:bg-accent focus:px-4 focus:py-2.5 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to content
      </a>
      <Nav />
      <main id="main" className="bg-bg">
        <Hero />
        <Suspense fallback={<div className="min-h-dvh" />}>
          <BelowFold />
        </Suspense>
      </main>
    </>
  )
}
