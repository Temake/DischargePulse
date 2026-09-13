/** Shown while a lazy route chunk loads. Deliberately quiet: no spinner flash
 *  for a chunk that usually arrives in one frame. */
export function RouteFallback() {
  return <div className="min-h-dvh bg-bg" aria-busy="true" aria-live="polite" />
}
