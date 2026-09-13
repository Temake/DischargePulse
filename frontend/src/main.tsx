import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { domMax, LazyMotion, MotionConfig } from 'framer-motion'
import { Toaster } from 'sonner'

import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './index.css'
import App from './App.tsx'
import { applyInitialTheme } from './lib/theme'

applyInitialTheme()

// Stream events invalidate queries, so refetching on window focus would only
// duplicate work the socket already did.
const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 30_000 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* domMax: the loop track's sliding bar uses layoutId. `m` components
            only, so the full motion bundle never loads. */}
        <LazyMotion features={domMax} strict>
          <MotionConfig reducedMotion="user">
            <App />
            <Toaster
              position="bottom-right"
              toastOptions={{
                unstyled: true,
                classNames: {
                  toast:
                    'flex w-[356px] max-w-[calc(100vw-2rem)] gap-3 rounded-field border border-hairline bg-surface px-4 py-3 text-ink shadow-overlay',
                  title: 'text-[14px] font-medium',
                  description: 'mt-0.5 text-[13px] text-ink-muted',
                },
              }}
            />
          </MotionConfig>
        </LazyMotion>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
