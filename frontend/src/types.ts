export type PathwayKey = 'surgery' | 'physio' | 'weight_physio' | 'non_surgical' | 'review'

/** The clinician's call on a referral. Overrides keep the pathway the rules gave. */
export interface Decision {
  kind: 'confirmed' | 'overridden'
  pathway: PathwayKey
  was: PathwayKey              // what the rules said
  old_pathway?: PathwayKey     // the pathway before this decision (backend)
  reason?: string | null
  by?: string
  at: string
}

export interface Referral {
  id: string
  letter_id: string | null
  set: 'dev' | 'test' | 'upload' | null
  name: string
  nhs_number?: string | null
  filename?: string | null          // the file the letter came from (backend: the latest upload)
  pathway: PathwayKey
  rule: number
  priority: number
  weeks_waiting: number | null
  weight_support: boolean
  text_key: string | null
  decision?: Decision | null
}

export type FactValue = string | number | boolean | null

export interface Span {
  field: string
  start: number
  end: number
}

export interface Patient extends Omit<Referral, 'text_key' | 'nhs_number'> {
  nhs_number: string | null
  on_waiting_list: boolean
  facts: Record<string, FactValue>
  quotes: Record<string, string>
  spans: Span[]
  dropped: { field: string; value: FactValue; quote: string | null; reason: string }[]
  label: string
  reasons: string[]
  priority_parts: Record<string, number>
  priority_max: Record<string, number>
  /** Booked into this week by a clinician ("Book this week"): always gets a slot. */
  booking?: Booking | null
  letter_text: string
}

export interface Booking {
  by?: string | null
  at: string
  reason?: string | null
}

/** Booking answer: when it would push anyone over 52 weeks out of a slot, nothing is stored until confirmed. */
export interface BookResult {
  booked: boolean
  needs_confirm: boolean
  pushed_out: { id: string; name: string; weeks_waiting: number }[]
  booking: Booking | null
}

export interface WeekPatient {
  id: string
  name: string
  pathway: PathwayKey
  priority: number
  weeks_waiting: number
  long_wait: boolean
  reason: string
  has_page: boolean
}

export type SlotKind = 'surgery' | 'physio' | 'weight_support'

export interface SlotList {
  kind: SlotKind
  label: string
  capacity: number
  in: WeekPatient[]
  next: WeekPatient[]
  waiting: number
}

export interface UnmetPatient {
  id: string; name: string; pathway: PathwayKey; priority: number; weeks_waiting: number; has_page: boolean
  pushed_out?: boolean          // had a slot until a booking took it
}

/** A patient a clinician overrode or booked, and what that did this week. */
export interface WeekChange {
  id: string
  name: string
  pathway: PathwayKey           // the pathway now
  priority: number
  weeks_waiting: number
  has_page: boolean
  overridden: boolean
  booked: boolean
  was: PathwayKey | null        // what the rules said (overrides)
  by?: string | null
  at: string
  reason?: string | null
  booking_reason?: string | null
  outcome: 'in' | 'next' | 'none'
  slot: SlotKind | null
  rank: number | null           // place in the queue for that slot type (1 = next)
}

/** The week plan: the optimiser (backend POST /week/build) or the demo site's browser plan (planner.ts). */
export interface WeekPlan {
  week_of: string
  method: 'optimiser' | 'demo'
  status: 'optimal' | 'infeasible'
  shortfall: string[]
  patients: number
  lists: SlotList[]
  long_wait: { weeks: number; total: number; included: number; unmet: number }
  /** Every over-52 patient left without a slot this week, longest wait first. */
  unmet: UnmetPatient[]
  locked: number
  /** Over-52s who lost their slot to a booking. */
  pushed_out: UnmetPatient[]
  changes: WeekChange[]
}

export type UploadResult =
  | { file: string; ok: true; referral: Referral }
  | { file: string; ok: false; message: string }

export interface ExtractionResult {
  letters: number
  mean_field_accuracy: number
  letters_all_fields_right: number
  quote_hit_rate: number
  facts_dropped: number
  pathway_agreement: number
  priority_mae: number
  field_accuracy: Record<string, number>
  cost_usd: number | null
}

export interface Results {
  extraction: { dev: ExtractionResult; test: ExtractionResult }
  cleaning: {
    raw_rows: number
    patients: number
    duplicates_removed: number
    logged: number
    fixed: number
    set_missing: number
    wrong: number
    by_issue: { field: string; issue: string; logged: number; fixed: number; 'set missing': number; wrong: number }[]
  }
  decision_tree: TreeResults | null
  optimise: OptimiseResults | null
  backlog: Backlog
}

/** The current (cleaned) waiting list. */
export interface Backlog {
  patients: number
  waiting_for_slot: number
  surgery: number
  over_standard: number
  over_long_wait: number
  standard_weeks: number
  long_wait_weeks: number
  by_pathway: Partial<Record<PathwayKey, number>>
}

export type Policy = 'FCFS' | 'Priority only' | 'Optimiser'

export interface CI { scenario: string; metric: string; mean: number; ci_low: number; ci_high: number }

export interface Pair {
  comparison: string; metric: string; mean_diff: number; ci_low: number; ci_high: number
  lower_seeds: number; higher_seeds: number; seeds: number; verdict: string
}

export interface OptimiseResults {
  weeks: number
  arrival_rate: number
  capacity: { surgery: number; physio: number; weight_support: number }
  thresholds: { standard_weeks: number; long_wait_weeks: number }
  seeds: number[]
  metrics: Record<string, string>
  triage_off_scenario: string
  triage_off_rule: string
  robustness: CI[]
  pairs: Pair[]
  surgery_list: { seed: number; seeds: number; weeks: number[]; on: number[]; off: number[]; mean_on: number[]; mean_off: number[] } | null
  series: Record<Policy, { week: number; over_18: number; over_52: number; waiting: number }[]>
  summary: { policy: Policy; surgery_capacity: number; over_18_end: number; over_52_end: number; over_52_mean: number;
    over_52_skipped_patients: number; weeks_infeasible: number; mean_wait_surgery: number; mean_oks_operated: number }[]
}

export interface TreeRun {
  name: 'continuous' | 'discretised'
  agreement: number
  agreement_complete: number
  cv_accuracy: number
  depth: number
  leaves: number
  best_params: { max_depth: number; min_samples_leaf: number }
  test_patients: number
  disagreements: number
}

export interface TreeResults {
  truth_check: { patients: number; matching: number }
  train: number
  test: number
  runs: TreeRun[]
  thresholds: { rule: string; short: string; rule_cut: string; tree: number | null; same: boolean; banded: number | null; banded_same: boolean }[]
  band_misses: { short: string; rule_cut: string; band_edge: number }[]
  disagreements: { patient_id: string; oks: number; kl_grade: number; bmi: number | null; physio_weeks: number;
    oks_drop: number; rules: string; tree: string; features: string }[]
  importances: Record<string, number>
  tree_text: string
}

// ---------------------------------------------------------------- spreadsheet import

export type MatchConfidence = 'exact' | 'alias' | 'fuzzy' | 'none' | 'manual'

export interface ImportColumn { header: string; field: string | null; confidence: MatchConfidence }
export interface ImportField { field: string; label: string; required: boolean }
export interface SkippedRow { row: number; nhs_number: string; name: string; reason: string }

export interface ImportPreview {
  file: string
  columns: ImportColumn[]
  rows: string[][]
  total_rows: number
  problems: string[]
  valid: number
  skipped: SkippedRow[]
  fields: ImportField[]
}

export interface ImportResult {
  file: string
  rows: number
  added: number
  updated: number
  skipped: SkippedRow[]
  referrals: Referral[]
}
