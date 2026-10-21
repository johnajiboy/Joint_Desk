import { PATHWAYS } from '../pathways'
import type { PathwayKey } from '../types'

export function PathwayChip({ pathway, priority, large = false, full = false, className = '' }: {
  pathway: PathwayKey
  priority?: number
  large?: boolean
  full?: boolean
  className?: string
}) {
  const p = PATHWAYS[pathway]
  return (
    <span className={`chip chip-${pathway} ${large ? 'chip-lg' : ''} shrink-0 ${className}`} title={p.label}
      aria-label={priority === undefined ? p.label : `${p.label}, priority ${priority}`}>
      {/* one text, so the chip never breaks into "Surgery" and "· 79" */}
      {priority === undefined ? (full ? p.label : p.short) : `${full ? p.label : p.short} · ${priority}`}
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
