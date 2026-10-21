import type { PathwayKey, Referral } from './types'

/** `short` is the label on every pill and list in the app; `label` is the full name (tooltips, the Why panel). */
export const PATHWAYS: Record<PathwayKey, { label: string; short: string }> = {
  surgery: { label: 'Surgery list', short: 'Surgery' },
  physio: { label: 'Physio first', short: 'Physio first' },
  weight_physio: { label: 'Weight support and physio first', short: 'Weight + physio' },
  non_surgical: { label: 'Keep on non-surgical care', short: 'Non-surgical' },
  review: { label: 'Ask the GP for more information', short: 'Needs info' },
}

export const PATHWAY_KEYS = Object.keys(PATHWAYS) as PathwayKey[]

/** The pathway that counts: the clinician's override if there is one, else the rules'. */
export function effectivePathway(r: Pick<Referral, 'pathway' | 'decision'>): PathwayKey {
  return r.decision?.pathway ?? r.pathway
}

export const TABS: { key: string; label: string; match: (p: PathwayKey) => boolean }[] = [
  { key: 'all', label: 'All', match: () => true },
  { key: 'surgery', label: 'Surgery', match: (p) => p === 'surgery' },
  { key: 'physio', label: 'Physio', match: (p) => p === 'physio' || p === 'weight_physio' },
  { key: 'info', label: 'Needs info', match: (p) => p === 'review' },
]
