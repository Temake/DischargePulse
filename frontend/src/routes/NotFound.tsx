import { ButtonLink } from '@/components/ui/Button'

export function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center px-6">
      <p className="font-mono text-[13px] text-ink-muted">404</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-[-0.02em]">No page here</h1>
      <p className="mt-2 text-ink-muted">
        The link may be old. If it pointed at a run, runs live in memory and a backend restart clears them.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <ButtonLink to="/runs">Open runs</ButtonLink>
        <ButtonLink to="/" variant="secondary">
          Product overview
        </ButtonLink>
      </div>
    </main>
  )
}
