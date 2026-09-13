import type { CallObservation } from '@/api/types'
import { clock, shortId, time } from '@/lib/format'
import { callModeLabel, speakerLabel } from '@/lib/labels'
import { cn } from '@/lib/utils'

/**
 * A call transcript presented as evidence, not a chat.
 *
 * Turns arrive with the observation after the call ends; the backend has no
 * audio stream and no recording URL, so there is no player here and nothing
 * that implies one. The header says exactly what kind of call produced it.
 */
export function TranscriptPlayback({
  observation,
  limit,
  className,
}: {
  observation: CallObservation | null
  limit?: number
  className?: string
}) {
  if (!observation) {
    return <p className={cn('text-sm text-ink-muted', className)}>No call record for this facility.</p>
  }

  const turns = limit ? observation.transcript_turns.slice(0, limit) : observation.transcript_turns
  const hidden = observation.transcript_turns.length - turns.length

  const heading =
    observation.mode === 'replay'
      ? 'Transcript of recorded call'
      : observation.mode === 'live'
        ? 'Transcript of live call'
        : 'No transcript'

  return (
    <div className={className}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-[14px] font-medium">{heading}</p>
        <p className="text-[12px] text-ink-muted">
          <span className="font-mono">{callModeLabel[observation.mode]}</span>
          {observation.call_id ? (
            <>
              {' · '}
              <span className="font-mono">{shortId(observation.call_id, 22)}</span>
            </>
          ) : null}
          {observation.started_at ? (
            <>
              {' · '}
              <span className="font-mono tabular-nums">{time(observation.started_at)}</span>
            </>
          ) : null}
        </p>
      </div>

      {observation.answers_source === 'simulated' && observation.simulation_note ? (
        <p className="mt-2 border-l-2 border-not-confirmed/60 pl-3 text-[13px] text-ink-muted">{observation.simulation_note}</p>
      ) : null}

      {observation.mode === 'scripted' ? (
        <p className="mt-2 text-[13px] text-ink-muted">
          No call was placed for this facility, so there is nothing to transcribe. The findings came from the test scenario.
        </p>
      ) : turns.length === 0 ? (
        <p className="mt-2 text-[13px] text-ink-muted">The call returned no transcript turns.</p>
      ) : (
        <ol className="mt-3 divide-y divide-hairline border-y border-hairline" aria-label={heading}>
          {turns.map((turn, index) => (
            <li key={index} className="grid grid-cols-[3.25rem_1fr] gap-x-3 py-2.5 text-[14px]">
              <span className="font-mono text-[12px] tabular-nums leading-6 text-ink-muted">
                {turn.offset_seconds != null ? clock(turn.offset_seconds) : '--:--'}
              </span>
              <div className="min-w-0">
                <p
                  className={cn(
                    'label-caps leading-6',
                    turn.speaker === 'bot' ? 'text-accent' : 'text-ink-muted',
                  )}
                >
                  {speakerLabel[turn.speaker]}
                </p>
                <p className="leading-relaxed">{turn.text}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
      {hidden > 0 ? <p className="mt-2 text-[13px] text-ink-muted">{hidden} more turns in the full call record.</p> : null}
    </div>
  )
}
