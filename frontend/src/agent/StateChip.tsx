import { CheckCircle, Question, WarningCircle, XCircle } from '@phosphor-icons/react'

import type { VerificationState } from '@/api/types'
import { verificationLabel, verificationTone } from '@/lib/labels'
import { cn } from '@/lib/utils'

export const STATE_GLYPH = {
  confirmed: CheckCircle,
  not_confirmed: WarningCircle,
  explicitly_unavailable: XCircle,
  unknown: Question,
} as const

/**
 * A verification state as glyph plus word, with no container. Color is the
 * third signal, never the only one, so the mark survives monochrome print or a
 * viewer who cannot separate red from green.
 */
export function StateMark({
  state,
  label,
  size = 15,
  className,
}: {
  state: VerificationState
  /** Replaces the state's own wording, e.g. "No". The state still reaches screen readers. */
  label?: string
  size?: number
  className?: string
}) {
  const Glyph = STATE_GLYPH[state]
  return (
    <span className={cn('inline-flex items-center gap-1.5', verificationTone[state], className)}>
      <Glyph size={size} weight={state === 'confirmed' ? 'fill' : 'bold'} aria-hidden="true" className="shrink-0" />
      <span className={label ? undefined : 'text-ink'}>{label ?? verificationLabel[state]}</span>
      {label ? <span className="sr-only"> ({verificationLabel[state]})</span> : null}
    </span>
  )
}

/** Terse wording for dense table cells. */
export const stateShort: Record<VerificationState, string> = {
  confirmed: 'Yes',
  not_confirmed: 'Unclear',
  explicitly_unavailable: 'No',
  unknown: 'Unknown',
}
