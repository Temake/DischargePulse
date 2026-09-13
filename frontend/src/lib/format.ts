/** Display formatting. Anything that changes on screen renders tabular. */

/** Elapsed seconds as a clock, 01:58. */
export function clock(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '--:--'
  const total = Math.max(0, Math.round(value))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

export function score(value: number | null | undefined): string {
  if (value == null) return '--'
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function miles(value: number): string {
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)} mi`
}

/** Wall-clock time of an ISO timestamp, 09:41:22, in the viewer's zone. */
export function time(iso: string | null | undefined): string {
  if (!iso) return '--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '--'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '--'
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

/** A calendar date such as a directory's last update. Date-only values are read as UTC so they never shift a day. */
export function date(iso: string | null | undefined): string {
  if (!iso) return '--'
  const value = new Date(iso)
  if (Number.isNaN(value.getTime())) return '--'
  return value.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: /^\d{4}-\d{2}-\d{2}$/.test(iso) ? 'UTC' : undefined,
  })
}

/** Seconds between two ISO timestamps, or from `start` to now when `end` is null. */
export function secondsBetween(start: string | null | undefined, end?: string | null): number | null {
  if (!start) return null
  const from = new Date(start).getTime()
  const to = end ? new Date(end).getTime() : Date.now()
  if (Number.isNaN(from) || Number.isNaN(to)) return null
  return Math.max(0, (to - from) / 1000)
}

/** Truncate an id for display without losing its recognisable head. */
export function shortId(value: string | null | undefined, keep = 16): string {
  if (!value) return '--'
  return value.length <= keep ? value : `${value.slice(0, keep)}…`
}

/** Clinical shorthand, 71F. The backend sends sex as a word. */
export function ageSex(patient: { age: number; sex: string }): string {
  return `${patient.age}${patient.sex.charAt(0).toUpperCase()}`
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`
}
