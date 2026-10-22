/**
 * The demo site's week plan, rebuilt in the browser so this browser's overrides and bookings show straight away.
 * Same rules as kneedss/optimise.py: booked patients first (they count against capacity), then everyone over 52
 * weeks, then priority, ties to the longest wait. Weight support slots only take weight support patients, so
 * filling them first and then the physio slots from everyone left picks the same patients as the solver.
 */
import type { PathwayKey, SlotKind, WeekChange, WeekPatient, WeekPlan } from './types'

export interface ListPatient {
  id: string
  name: string
  pathway: PathwayKey
  priority: number
  weeks_waiting: number
  has_page: boolean
}

export interface Change {
  overridden: boolean
  booked: boolean
  was: PathwayKey | null
  by?: string | null
  at: string
  reason?: string | null
  booking_reason?: string | null
}

export const SLOTS: { kind: SlotKind; label: string }[] = [
  { kind: 'surgery', label: 'Surgery' }, { kind: 'physio', label: 'Physio' }, { kind: 'weight_support', label: 'Weight support' },
]
// slot types each pathway may use, preferred first
export const ALLOWED: Partial<Record<PathwayKey, SlotKind[]>> = {
  surgery: ['surgery'], physio: ['physio'], weight_physio: ['weight_support', 'physio'],
}
const NEXT_SHOWN = 5

export class NoSlotLeft extends Error {}

const canUse = (p: ListPatient, slot: SlotKind) => ALLOWED[p.pathway]?.includes(slot) ?? false

interface Assigned { p: ListPatient; slot: SlotKind }

function allocate(cand: ListPatient[], capacity: Record<SlotKind, number>, locked: Set<string>, longWait: number): Assigned[] {
  const order = (a: ListPatient, b: ListPatient) =>
    Number(locked.has(b.id)) - Number(locked.has(a.id))
    || Number(b.weeks_waiting > longWait) - Number(a.weeks_waiting > longWait)
    || b.priority - a.priority || b.weeks_waiting - a.weeks_waiting || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
  const sorted = [...cand].sort(order)
  const out: Assigned[] = []
  const take = (pool: ListPatient[], slot: SlotKind) => {
    const chosen = pool.slice(0, capacity[slot])
    out.push(...chosen.map((p) => ({ p, slot })))
    return new Set(chosen.map((p) => p.id))
  }
  take(sorted.filter((p) => p.pathway === 'surgery'), 'surgery')
  const ws = take(sorted.filter((p) => p.pathway === 'weight_physio'), 'weight_support')
  take(sorted.filter((p) => (p.pathway === 'physio' || p.pathway === 'weight_physio') && !ws.has(p.id)), 'physio')
  const placed = new Set(out.map((a) => a.p.id))
  if ([...locked].some((id) => !placed.has(id))) throw new NoSlotLeft('No slot left · all booked')
  return out
}

function shortfall(cand: ListPatient[], capacity: Record<SlotKind, number>, longWait: number): string[] {
  const n = (pw: PathwayKey) => cand.filter((p) => p.pathway === pw && p.weeks_waiting > longWait).length
  const [s, p, w] = [n('surgery'), n('physio'), n('weight_physio')]
  const spare = Math.max(0, capacity.physio - p)
  const out: string[] = []
  if (s > capacity.surgery) out.push(`${s} over ${longWait} weeks need surgery; ${capacity.surgery} slots`)
  if (p > capacity.physio) out.push(`${p} over ${longWait} weeks need physio; ${capacity.physio} slots`)
  if (w > capacity.weight_support + spare)
    out.push(`${w} over ${longWait} weeks need weight support; ${capacity.weight_support} slots + ${spare} spare physio`)
  return out
}

export function plan(patients: ListPatient[], changes: Record<string, Change>, capacity: Record<SlotKind, number>,
  longWait: number, weekOf: string): WeekPlan {
  const cand = patients.filter((p) => ALLOWED[p.pathway])
  const ids = new Set(cand.map((p) => p.id))
  const locked = new Set(Object.entries(changes).filter(([id, c]) => c.booked && ids.has(id)).map(([id]) => id))
  const assigned = allocate(cand, capacity, locked, longWait)
  const isLong = (p: ListPatient) => p.weeks_waiting > longWait
  const placed = new Map(assigned.map((a) => [a.p.id, a.slot]))
  const waiting = cand.filter((p) => !placed.has(p.id))
  const unmetIds = new Set(waiting.filter(isLong).map((p) => p.id))

  // over-52s who had a slot in the same week without bookings were pushed out by a booking
  let pushedIds = new Set<string>()
  if (locked.size && unmetIds.size) {
    const free = new Set(allocate(cand, capacity, new Set(), longWait).map((a) => a.p.id))
    pushedIds = new Set([...unmetIds].filter((id) => free.has(id)))
  }

  const cut: Partial<Record<SlotKind, number>> = {}
  for (const a of assigned) if (!isLong(a.p)) cut[a.slot] = Math.min(cut[a.slot] ?? Infinity, a.p.priority)

  const person = (p: ListPatient, reason: string): WeekPatient => ({
    id: p.id, name: p.name, pathway: p.pathway, priority: p.priority, weeks_waiting: p.weeks_waiting,
    long_wait: isLong(p), reason, has_page: p.has_page })
  const reasonIn = (p: ListPatient, slot: SlotKind) =>
    locked.has(p.id) ? 'Booked this week by a clinician'
      : isLong(p) ? `Over ${longWait} weeks (${p.weeks_waiting}) · must have a slot`
        : `Priority ${p.priority} · ${p.weeks_waiting} weeks${p.pathway === 'weight_physio' && slot === 'physio' ? ' · physio slot, weight support full' : ''}`
  const byNeed = (a: ListPatient, b: ListPatient) =>
    Number(isLong(b)) - Number(isLong(a)) || b.priority - a.priority || b.weeks_waiting - a.weeks_waiting || (a.id < b.id ? -1 : 1)
  const queueFor = (slot: SlotKind) => waiting.filter((p) => canUse(p, slot)).sort(byNeed)

  const lists = SLOTS.map(({ kind, label }) => {
    const chosen = assigned.filter((a) => a.slot === kind).map((a) => a.p).sort(byNeed)
    return {
      kind, label, capacity: capacity[kind],
      in: chosen.map((p) => person(p, reasonIn(p, kind))),
      next: queueFor(kind).slice(0, NEXT_SHOWN).map((p) => person(p,
        isLong(p) ? `Over ${longWait} weeks · no slot left`
          : cut[kind] !== undefined ? `Priority ${p.priority} · below the cut-off (${cut[kind]})` : `Priority ${p.priority} · slots full`)),
      waiting: cand.filter((p) => canUse(p, kind)).length - chosen.length,
    }
  })

  const unmet = waiting.filter(isLong)
    .sort((a, b) => b.weeks_waiting - a.weeks_waiting || b.priority - a.priority || (a.id < b.id ? -1 : 1))
    .map((p) => ({ id: p.id, name: p.name, pathway: p.pathway, priority: p.priority, weeks_waiting: p.weeks_waiting,
      has_page: p.has_page, pushed_out: pushedIds.has(p.id) }))

  const byId = new Map(patients.map((p) => [p.id, p]))
  const changed: WeekChange[] = Object.entries(changes).flatMap(([id, c]) => {
    const p = byId.get(id)
    if (!p) return []
    const slot = placed.get(id)
    let outcome: Pick<WeekChange, 'outcome' | 'slot' | 'rank'> = { outcome: 'none', slot: null, rank: null }
    if (slot) outcome = { outcome: 'in', slot, rank: null }
    else if (ALLOWED[p.pathway]) {
      const first = ALLOWED[p.pathway]![0]
      outcome = { outcome: 'next', slot: first, rank: queueFor(first).findIndex((q) => q.id === id) + 1 }
    }
    return [{ id, name: p.name, pathway: p.pathway, priority: p.priority, weeks_waiting: p.weeks_waiting,
      has_page: p.has_page, ...c, ...outcome }]
  }).sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0))

  return {
    week_of: weekOf, method: 'demo', status: unmet.length ? 'infeasible' : 'optimal',
    shortfall: unmet.length ? shortfall(cand, capacity, longWait) : [], patients: cand.length, lists,
    long_wait: { weeks: longWait, total: cand.filter(isLong).length, included: assigned.filter((a) => isLong(a.p)).length, unmet: unmet.length },
    unmet, locked: locked.size, pushed_out: unmet.filter((u) => u.pushed_out), changes: changed,
  }
}
