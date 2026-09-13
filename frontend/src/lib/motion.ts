/**
 * Motion tokens. Every animation in the product uses these, so timing reads as
 * one system rather than per-component taste.
 *
 * Motion exists to explain a change of state: a phase advancing, a call row
 * arriving, a contradiction landing, the radius widening, a sheet opening.
 * Transform and opacity only. No infinite loops except the LIVE dot while a
 * live call is genuinely in flight.
 */

export const ease = { out: [0.16, 1, 0.3, 1], inOut: [0.65, 0, 0.35, 1] } as const

export const spring = {
  snappy: { type: 'spring', stiffness: 420, damping: 34 },
  soft: { type: 'spring', stiffness: 140, damping: 22 },
} as const

export const dur = { micro: 0.18, ui: 0.28, reveal: 0.6 } as const

/** A row or block arriving because data arrived. */
export const arrive = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: dur.ui, ease: ease.out },
} as const

/** Shared viewport config so reveals fire at the same point everywhere. */
export const viewportOnce = { once: true, margin: '-12% 0px' } as const
