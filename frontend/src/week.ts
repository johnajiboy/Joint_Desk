import { effectivePathway } from './pathways'
import type { Referral, SlotList, WeekConfig, WeekPlan } from './types'

/**
 * Stand-in weekly list until the PuLP optimiser (stage 5): for each slot type, everyone over the long-wait
 * limit first, then highest priority, then longest wait.
 */
export function greedyWeek(queue: Referral[], cfg: WeekConfig): WeekPlan {
  const long = (r: Referral) => (r.weeks_waiting ?? 0) > cfg.long_wait_weeks
  const byNeed = (a: Referral, b: Referral) =>
    Number(long(b)) - Number(long(a)) || b.priority - a.priority || (b.weeks_waiting ?? 0) - (a.weeks_waiting ?? 0)

  const kinds = ['surgery', 'physio', 'weight_physio'] as const
  const lists: SlotList[] = kinds.map((kind) => {
    const capacity = cfg.capacity[kind]
    const candidates = queue.filter((r) => effectivePathway(r) === kind).sort(byNeed)
    const chosen = candidates.slice(0, capacity)
    return { kind, capacity, in: chosen, next: candidates.slice(capacity, capacity + 5), waiting: candidates.length - chosen.length }
  })

  const total = queue.filter((r) => long(r) && (kinds as readonly string[]).includes(effectivePathway(r))).length
  const included = lists.reduce((n, l) => n + l.in.filter(long).length, 0)
  return { week_of: cfg.week_of, method: 'greedy', lists, long_wait: { weeks: cfg.long_wait_weeks, included, total } }
}
