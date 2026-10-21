import { PATHWAYS } from '../pathways'
import type { PathwayKey } from '../types'

/**
 * The one pathway pill used everywhere: "Surgery", "Weight + physio", "Physio first", "Non-surgical", "Needs info",
 * or with a priority "Surgery · 79". `weight` adds the "+ weight" tag after a surgery pill.
 */
export function PathwayChip({ pathway, priority, weight = false, className = '' }: {
  pathway: PathwayKey
  priority?: number
  weight?: boolean
  className?: string
}) {
  const p = PATHWAYS[pathway]
  const text = priority === undefined ? p.short : `${p.short} · ${priority}`
  const pill = (
    <span className={`pill pill-${pathway} ${weight ? '' : className}`} title={p.label}
      aria-label={priority === undefined ? p.label : `${p.label}, priority ${priority}`}>
      {text}
    </span>
  )
  if (!(weight && pathway === 'surgery')) return pill
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 ${className}`}>
      {pill}
      <span className="pill pill-weight" title="Weight support offered alongside surgery">+ weight</span>
    </span>
  )
}

/** Weeks waiting; over the long-wait limit shows in the status colour. */
export function Weeks({ weeks, limit = 52 }: { weeks: number | null; limit?: number }) {
  if (weeks === null) return <span className="text-muted">—</span>
  return (
    <span className={`tabular-nums ${weeks > limit ? 'font-medium text-danger' : ''}`}>
      {weeks}
      <span className="text-muted"> wk</span>
    </span>
  )
}
