import { useEffect, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import { buildWeek, getResults } from '../api'
import { annotate } from '../components/annotate'
import { Card, ErrorNote, Loading, PageHeader } from '../components/AppShell'
import { LoopLineChart } from '../components/LoopLineChart'
import type { Row } from '../components/LoopLineChart'
import { PathwayChip } from '../components/PathwayChip'
import { Link } from 'react-router-dom'
import { Term } from '../components/Term'
import { phase, useCountUp, useLoop } from '../components/useLoop'
import { PATHWAYS } from '../pathways'
import type { Backlog, CI, OptimiseResults, Pair, PathwayKey, Policy, Results as ResultsData, TreeResults, WeekPlan } from '../types'

// Every number on this page comes from results.json (exported from eval/results). Nothing is typed in.

const pct = (v: number) => {
  const p = Math.round(v * 1000) / 10
  return `${Number.isInteger(p) ? p : p.toFixed(1)}%`
}
const POLICIES: Policy[] = ['FCFS', 'Priority only', 'Optimiser']
const pm = (m: number, lo: number, hi: number) => {
  const d = Math.abs(m) >= 100 ? 0 : 1
  return `${m.toFixed(d)} ± ${((hi - lo) / 2).toFixed(d)}`
}

/** Counts up once on load, then stays on the final value (which is also its accessible name). */
function Tile({ label, value, format, sub }: { label: string; value: number | null; format: (n: number) => string; sub: string }) {
  const num = useCountUp(value ?? 0, format)
  return (
    <div className="fade-up rounded-lg border border-line bg-surface p-4">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums" aria-label={value === null ? 'not recorded' : format(value)}>
        {value === null ? '—' : <span ref={num} aria-hidden="true">{format(value)}</span>}
      </div>
      <div className="mt-0.5 text-xs text-muted">{sub}</div>
    </div>
  )
}

function Swatch({ color }: { color: string }) {
  return <span className="inline-block size-2.5 shrink-0 rounded-sm" style={{ background: color }} />
}

// ---------------------------------------------------------------- cleaning

/** Segments fill one after another, looping every 10 s. The counts beside them never move. */
function CleaningBar({ c, card }: { c: ResultsData['cleaning']; card: RefObject<HTMLElement | null> }) {
  const segs = useRef<(HTMLSpanElement | null)[]>([])
  useLoop(card, (ms) => {
    const t = ms % 10000
    segs.current.forEach((seg, i) => {
      if (seg) seg.style.transform = `scaleX(${ms === Infinity ? 1 : phase(t, i * 700, 900) * (1 - phase(t, 9500, 400))})`
    })
  })
  const parts = [
    { label: 'Fixed', n: c.fixed, color: 'var(--series-1)' },
    { label: 'Set missing', n: c.set_missing, color: 'var(--series-2)' },
    { label: 'Duplicates removed', n: c.duplicates_removed, color: 'var(--series-3)' },
  ]
  const total = parts.reduce((s, p) => s + p.n, 0) + c.wrong
  return (
    <>
      <div className="flex h-5 gap-[2px] overflow-hidden rounded-[4px]" role="img"
        aria-label={parts.map((p) => `${p.label} ${p.n}`).join(', ')}>
        {parts.map((p, i) => (
          <span key={p.label} ref={(el) => { segs.current[i] = el }} className="origin-left"
            style={{ width: `${(p.n / total) * 100}%`, background: p.color }} />
        ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
        {parts.map((p) => (
          <li key={p.label} className="flex items-center gap-2">
            <Swatch color={p.color} />
            <span className="text-muted">{p.label}</span>
            <span className="font-medium tabular-nums">{p.n}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">Set missing = the true value can't be recovered, so it is not guessed.</p>
    </>
  )
}

// ---------------------------------------------------------------- tree

/**
 * Ring loop, every 6 s: fills to the value (1.4 s), holds, empties quickly (0.4 s). The number inside follows the
 * fill; the caption under the ring always shows the final value.
 */
function Gauge({ value, label, sub, color, delay = 0, card }: {
  value: number; label: ReactNode; sub: string; color: string; delay?: number; card: RefObject<HTMLElement | null>
}) {
  const r = 46
  const full = 2 * Math.PI * r
  const ring = useRef<SVGCircleElement>(null)
  const num = useRef<SVGTextElement>(null)
  useLoop(card, (ms) => {
    const t = (ms + 6000 - delay) % 6000
    const fill = ms === Infinity ? 1 : ms < delay ? 0 : phase(t, 0, 1400) * (1 - phase(t, 5600, 400))
    if (ring.current) ring.current.style.strokeDashoffset = `${full * (1 - value * fill)}`
    if (num.current) num.current.textContent = pct(value * fill)
  })
  return (
    <figure className="flex flex-col items-center text-center">
      <svg viewBox="0 0 120 120" className="size-32" role="img" aria-label={`${pct(value)} agreement`}>
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--line)" strokeWidth="10" />
        <circle ref={ring} cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={full} strokeDashoffset={full * (1 - value)} transform="rotate(-90 60 60)" />
        <text ref={num} x="60" y="66" textAnchor="middle" fontSize="20" fontWeight="600" fill="var(--text)"
          aria-hidden="true">{pct(value)}</text>
      </svg>
      <figcaption className="mt-2 text-sm font-medium">{label} · {pct(value)}</figcaption>
      <div className="text-xs text-muted">{sub}</div>
    </figure>
  )
}

function TreeGauges({ t, card }: { t: TreeResults; card: RefObject<HTMLElement | null> }) {
  const [raw, banded] = t.runs
  const sub = (n: number) => (n === 0 ? 'no disagreements' : `${n} disagreement${n === 1 ? '' : 's'}`)
  return (
    <>
      <div className="flex flex-wrap justify-around gap-4">
        <Gauge card={card} value={raw.agreement} label="Raw values" sub={sub(raw.disagreements)} color="var(--series-1)" />
        <Gauge card={card} value={banded.agreement} label={<Term k="nhs_bands">NHS bands</Term>} sub={sub(banded.disagreements)}
          color="var(--series-3)" delay={250} />
      </div>
      <p className="mt-3 text-xs text-muted">
        Agreement with the expert rules on {raw.test_patients} held-out patients.
        {t.band_misses.map((m) => <span key={m.short}> Bands can't draw {annotate(m.short)}; nearest edge {m.band_edge}.</span>)}
      </p>
    </>
  )
}

// ---------------------------------------------------------------- full tables (closed by default)

function Table({ caption, head, rows }: { caption: string; head: ReactNode[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[28rem] text-sm tabular-nums">
        <caption className="mb-1 text-left text-xs font-medium text-muted">{caption}</caption>
        <thead className="text-left text-xs text-muted">
          <tr>{head.map((h, i) => <th key={i} className={`py-1 font-medium ${i ? 'text-right' : ''}`}>{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row, i) => (
            <tr key={i}>{row.map((c, j) => <td key={j} className={`py-1.5 align-top ${j ? 'text-right' : ''}`}>{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FullTables({ r }: { r: ResultsData }) {
  const { dev, test } = r.extraction
  const o = r.optimise
  const t = r.decision_tree
  const ci = (sc: string, m: string) => o?.robustness.find((x: CI) => x.scenario === sc && x.metric === m)
  const cell = (c?: CI) => (c ? pm(c.mean, c.ci_low, c.ci_high) : '—')
  const pair = (cmp: string, m: string) => o?.pairs.find((x: Pair) => x.comparison === cmp && x.metric === m)
  const pairCell = (p?: Pair) => (p ? <>{pm(p.mean_diff, p.ci_low, p.ci_high)}<span className="block text-xs text-muted">{p.verdict}</span></> : '—')
  return (
    <details className="mt-6">
      <summary className="w-fit cursor-pointer text-sm text-primary underline-offset-2 hover:underline dark:text-text">Full tables</summary>
      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <Table caption="LLM accuracy per field" head={['Field', `Dev (${dev.letters})`, `Test (${test.letters})`]}
          rows={Object.keys(dev.field_accuracy).map((f) => [f, pct(dev.field_accuracy[f]), pct(test.field_accuracy[f])])} />
        <Table caption="Extraction, dev vs held-out test" head={['Measure', 'Dev', 'Test']}
          rows={[['Letters with every field right', pct(dev.letters_all_fields_right), pct(test.letters_all_fields_right)],
            ['Quote hit rate', pct(dev.quote_hit_rate), pct(test.quote_hit_rate)],
            ['Facts dropped by quote check', dev.facts_dropped, test.facts_dropped],
            ['Pathway agreement', pct(dev.pathway_agreement), pct(test.pathway_agreement)],
            ['Priority, mean abs. difference', dev.priority_mae.toFixed(1), test.priority_mae.toFixed(1)]]} />
        {o && (() => {
          const { standard_weeks: std, long_wait_weeks: lw } = o.thresholds
          return <>
            <Table caption={`Waiting over ${std} and ${lw} weeks, by week (surgery capacity ${o.capacity.surgery})`}
              head={['Week', ...POLICIES.flatMap((p) => [`>${std} · ${p}`, `>${lw} · ${p}`])]}
              rows={o.series.Optimiser.map((row, i) => [row.week, ...POLICIES.flatMap((p) => [o.series[p][i].over_18, o.series[p][i].over_52])])} />
            <Table caption={`Over ${lw} weeks after ${o.weeks} weeks, by surgery slots a week`} head={['Slots', ...POLICIES]}
              rows={[...new Set(o.summary.map((s) => s.surgery_capacity))].map((c) => [c, ...POLICIES.map((p) =>
                o.summary.find((s) => s.surgery_capacity === c && s.policy === p)?.over_52_end ?? '—')])} />
            <Table caption={`Across ${o.seeds.length} arrival seeds, mean ± 95% CI`} head={['Measure', ...POLICIES]}
              rows={Object.keys(o.metrics).map((k) => [o.metrics[k], ...POLICIES.map((p) => cell(ci(p, k)))])} />
            <Table caption="Optimiser minus each policy, paired by seed" head={['Measure', 'vs FCFS', 'vs Priority only']}
              rows={Object.keys(o.metrics).map((k) => [o.metrics[k], pairCell(pair('Optimiser - FCFS', k)), pairCell(pair('Optimiser - Priority only', k))])} />
            <Table caption={`Triage on vs off (optimiser, ${o.seeds.length} seeds)`} head={['Measure', 'On', 'Off', 'Off minus on']}
              rows={Object.keys(o.metrics).map((k) => [o.metrics[k], cell(ci('Optimiser', k)), cell(ci(o.triage_off_scenario, k)),
                pairCell(pair(`${o.triage_off_scenario} - Optimiser`, k))])} />
          </>
        })()}
        {t && <>
          <Table caption="Rule cut points vs learned splits" head={['Rule', 'Tree · raw', 'Tree · bands']}
            rows={t.thresholds.map((x) => [x.short, x.tree === null ? 'not used' : `≤ ${x.tree}${x.same ? ' · same' : ''}`,
              x.banded === null ? 'not used' : `≤ ${x.banded}${x.banded_same ? ' · same' : ''}`])} />
          <Table caption="Where the tree and the rules disagree" head={['Patient', 'OKS', 'KL', 'Rules', 'Tree', 'Features']}
            rows={t.disagreements.length ? t.disagreements.map((d) => [d.patient_id, d.oks, d.kl_grade, d.rules, d.tree, d.features])
              : [['None', '', '', '', '', '']]} />
        </>}
        <Table caption="Cleaning, logged problems by issue" head={['Problem', 'Logged', 'Fixed', 'Set missing', 'Wrong']}
          rows={r.cleaning.by_issue.map((b) => [`${b.field} · ${b.issue}`, b.logged, b.fixed, b['set missing'], b.wrong])} />
      </div>
    </details>
  )
}

// ---------------------------------------------------------------- backlog view

function StillTile({ label, value, sub, tone }: { label: ReactNode; value: string; sub: ReactNode; tone?: 'good' | 'danger' }) {
  return (
    <div className="fade-up rounded-lg border border-line bg-surface p-4">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
      <div className={`mt-0.5 text-xs ${tone === 'good' ? 'font-medium text-good' : tone === 'danger' ? 'font-medium text-danger' : 'text-muted'}`}>{sub}</div>
    </div>
  )
}

/** Meters that regrow every 10 s (staggered); the numbers beside them never move. */
function useRegrow(card: RefObject<HTMLElement | null>, step = 150) {
  const bars = useRef<(HTMLElement | null)[]>([])
  useLoop(card, (ms) => {
    const t = ms % 10000
    bars.current.forEach((bar, i) => {
      if (bar) bar.style.transform = `scaleX(${ms === Infinity ? 1 : phase(t, i * step, 1100) * (1 - phase(t, 9500, 400))})`
    })
  })
  return (i: number) => (el: HTMLElement | null) => { bars.current[i] = el }
}

function SurgeryListCard({ o, card }: { o: OptimiseResults; card: RefObject<HTMLElement | null> }) {
  const sl = o.surgery_list!
  const data: Row[] = sl.weeks.map((week, i) => ({ week, on: sl.on[i], off: sl.off[i] }))
  const avoided = Math.round(sl.off.at(-1)! - sl.on.at(-1)!)
  const round = (n: number) => Math.round(n).toLocaleString()
  return (
    <Card ref={card} className="fade-up lg:col-span-2" title="Surgery list: with Joint Desk vs without"
      meta={<span className="ml-auto text-xs text-muted">patients on the surgery list · {o.weeks} weeks</span>}>
      <LoopLineChart card={card} data={data}
        series={[
          { key: 'on', label: 'Joint Desk', end: 'Joint Desk', color: 'var(--series-1)', term: 'optimiser' },
          { key: 'off', label: 'Without triage', end: 'Without triage', color: 'var(--series-2)', term: 'triage' },
        ]}
        gap={{ low: 'on', high: 'off', label: `Backlog avoided · ${avoided.toLocaleString()} patients` }}
        ariaLabel={`Surgery list over ${o.weeks} weeks: Joint Desk ends at ${round(sl.on.at(-1)!)}, without triage ${round(sl.off.at(-1)!)}; ${avoided} patients avoided`} />
      <p className="mt-2 text-xs text-muted">
        Without <Term k="triage">triage</Term>, every referral with X-ray damage goes straight on the surgery list. One
        simulated run; the average over {sl.seeds} runs is {round(sl.mean_on.at(-1)!)} vs {round(sl.mean_off.at(-1)!)}.
      </p>
    </Card>
  )
}

function ThisWeekCard({ plan, card }: { plan: WeekPlan | null; card: RefObject<HTMLElement | null> }) {
  const grow = useRegrow(card)
  return (
    <Card ref={card} className="fade-up" title="This week">
      {!plan ? <p className="py-6 text-sm text-muted">Loading…</p> : (() => {
        const booked = plan.lists.flatMap((l) => l.in)
        const longest = booked.length ? Math.max(...booked.map((p) => p.weeks_waiting)) : null
        const surgeryShort = plan.shortfall.some((x) => x.includes('surgery'))
        return (
          <>
            <ul className="space-y-3">
              {plan.lists.map((l, i) => (
                <li key={l.kind} className="text-sm">
                  <div className="mb-1 flex justify-between">
                    <span>{l.label}</span>
                    <span className="tabular-nums"><span className="font-medium">{l.in.length}</span><span className="text-muted">/{l.capacity}</span></span>
                  </div>
                  <div className="meter">
                    <span ref={grow(i)} style={{ transform: 'scaleX(1)', width: `${(l.in.length / Math.max(l.capacity, 1)) * 100}%`, animation: 'none' }} />
                  </div>
                </li>
              ))}
            </ul>
            {longest !== null && (
              <p className="mt-4 text-sm">Longest waiter booked: <span className="font-semibold tabular-nums">{longest} weeks</span></p>
            )}
            {plan.long_wait.unmet > 0 && (
              <p className="mt-3 rounded-md px-3 py-2 text-sm" style={{ background: 'var(--review-bg)', color: 'var(--review-fg)' }}>
                {plan.long_wait.unmet} patients over {plan.long_wait.weeks} weeks still need a slot.
                {surgeryShort ? ' Not enough surgery capacity this week.' : ' Not enough capacity this week.'}
              </p>
            )}
            <Link to="/week" className="mt-4 inline-flex min-h-11 items-center text-sm text-primary underline-offset-2 hover:underline dark:text-text">
              Open this week →
            </Link>
          </>
        )
      })()}
    </Card>
  )
}

function LongWaitCard({ o, card }: { o: OptimiseResults; card: RefObject<HTMLElement | null> }) {
  const lw = o.thresholds.long_wait_weeks
  const data: Row[] = o.series.Optimiser.map((r, i) => ({ week: r.week, opt: r.over_52, pri: o.series['Priority only'][i].over_52 }))
  return (
    <Card ref={card} className="fade-up lg:col-span-2" title={<>Nobody left past {lw} weeks</>}
      meta={<span className="ml-auto text-xs text-muted">waiting over <Term k="waits">{lw} weeks</Term> · {o.weeks} weeks</span>}>
      <LoopLineChart card={card} data={data}
        series={[
          { key: 'opt', label: 'Joint Desk', end: 'Joint Desk', color: 'var(--series-1)', term: 'optimiser' },
          { key: 'pri', label: 'Worst knee first', end: 'Worst knee first', color: 'var(--series-2)', term: 'priority_only' },
        ]}
        ariaLabel={`Patients waiting over ${lw} weeks: Joint Desk ends at ${data.at(-1)!.opt}, worst knee first at ${data.at(-1)!.pri}`} />
    </Card>
  )
}

const ORDER: PathwayKey[] = ['surgery', 'weight_physio', 'physio', 'non_surgical', 'review']
const FG: Record<PathwayKey, string> = {
  surgery: 'var(--surgery-fg)', weight_physio: 'var(--weight-fg)', physio: 'var(--physio-fg)',
  non_surgical: 'var(--nonsurg-fg)', review: 'var(--review-fg)',
}

function WhereCard({ b, card }: { b: Backlog; card: RefObject<HTMLElement | null> }) {
  const grow = useRegrow(card, 450)
  const parts = ORDER.map((k) => ({ k, n: b.by_pathway[k] ?? 0 })).filter((p) => p.n > 0)
  return (
    <Card ref={card} className="fade-up" title="Where referrals went"
      meta={<span className="ml-auto text-xs text-muted tabular-nums">{b.patients.toLocaleString()} patients</span>}>
      <div className="flex h-5 gap-[2px] overflow-hidden rounded-[4px]" role="img"
        aria-label={parts.map((p) => `${PATHWAYS[p.k].short} ${p.n}`).join(', ')}>
        {parts.map((p, i) => (
          <span key={p.k} ref={grow(i)} className="origin-left" style={{ width: `${(p.n / b.patients) * 100}%`, background: FG[p.k] }} />
        ))}
      </div>
      <ul className="mt-3 divide-y divide-line">
        {parts.map((p) => (
          <li key={p.k} className="flex min-h-10 items-center gap-3 py-1 text-sm">
            <PathwayChip pathway={p.k} />
            <span className="ml-auto font-medium tabular-nums">{p.n.toLocaleString()}</span>
            <span className="w-14 text-right text-muted tabular-nums">{pct(p.n / b.patients)}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

// ---------------------------------------------------------------- page

export default function Results() {
  const listCard = useRef<HTMLElement>(null)
  const weekCard = useRef<HTMLElement>(null)
  const longCard = useRef<HTMLElement>(null)
  const whereCard = useRef<HTMLElement>(null)
  const cleanCard = useRef<HTMLElement>(null)
  const treeCard = useRef<HTMLElement>(null)
  const [r, setR] = useState<ResultsData | null>(null)
  const [plan, setPlan] = useState<WeekPlan | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    getResults().then(setR).catch(() => setError(true))
    buildWeek().then(setPlan).catch(() => setPlan(null))
  }, [])

  if (error) return <ErrorNote text="Couldn't load results" />
  if (!r) return <Loading />
  const { backlog: b, optimise: o, cleaning: c } = r
  const test = r.extraction.test
  const costPer100 = test.cost_usd === null ? null : (test.cost_usd / test.letters) * 100
  const total = c.fixed + c.set_missing + c.duplicates_removed + c.wrong
  const sl = o?.surgery_list
  const moved = sl ? Math.round(sl.off[0] - sl.on[0]) : null
  const clearWeek = o?.series.Optimiser.find((row) => row.over_52 === 0)?.week

  return (
    <>
      <PageHeader title="Backlog" meta={<span className="chip chip-plain">Waiting list · {b.patients.toLocaleString()} patients</span>} />

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StillTile label="On the surgery list" value={b.surgery.toLocaleString()} tone="good"
          sub={moved === null ? '' : `${moved.toLocaleString()} fewer than without triage`} />
        <StillTile label={<>Waiting over <Term k="waits">{b.standard_weeks} weeks</Term></>} value={b.over_standard.toLocaleString()}
          sub={`of ${b.waiting_for_slot.toLocaleString()} waiting for a slot`} />
        <StillTile label={<>Waiting over <Term k="waits">{b.long_wait_weeks} weeks</Term></>} value={b.over_long_wait.toLocaleString()}
          tone="danger" sub={clearWeek === undefined ? 'not cleared within the simulation' : `→ 0 within ${clearWeek} weeks on this plan`} />
        <StillTile label="Moved off the surgery list" value={moved === null ? '—' : moved.toLocaleString()}
          sub="to physio, weight support or other care" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {sl && o && <SurgeryListCard o={o} card={listCard} />}
        <ThisWeekCard plan={plan} card={weekCard} />
        {o && <LongWaitCard o={o} card={longCard} />}
        <WhereCard b={b} card={whereCard} />
      </div>

      <details className="mt-8 border-t border-line pt-4">
        <summary className="w-fit cursor-pointer text-sm font-medium text-primary underline-offset-2 hover:underline dark:text-text">
          Evaluation · how accurate it is
        </summary>
        <div className="mt-4">
          <p className="mb-3 text-xs text-muted">Held-out test set · {test.letters} letters</p>
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Tile label="Letters read right" value={test.letters_all_fields_right} format={pct} sub="every fact correct" />
            <Tile label="Quotes found" value={test.quote_hit_rate} format={pct} sub="each fact's words are in the letter" />
            <Tile label="Pathway matches" value={test.pathway_agreement} format={pct} sub="rules on the facts read vs answer key" />
            <Tile label="Cost to read" value={costPer100} format={(n) => `$${n.toFixed(2)}`} sub="per 100 letters" />
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card ref={cleanCard} className="fade-up lg:col-span-2" title="Data cleaned"
              meta={<span className="ml-auto text-xs text-muted tabular-nums">
                {total.toLocaleString()} problems found in {c.raw_rows.toLocaleString()} raw rows · {c.wrong} left wrong</span>}>
              <CleaningBar c={c} card={cleanCard} />
            </Card>
            {r.decision_tree && (
              <Card ref={treeCard} className="fade-up" title="Learned tree agrees with the rules">
                <TreeGauges t={r.decision_tree} card={treeCard} />
              </Card>
            )}
          </div>
          <FullTables r={r} />
        </div>
      </details>
    </>
  )
}
