import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getResults } from '../api'
import { annotate } from '../components/annotate'
import { Card, ErrorNote, Loading, PageHeader } from '../components/AppShell'
import { LongWaitChart } from '../components/LongWaitChart'
import { Term } from '../components/Term'
import type { CI, OptimiseResults, Pair, Policy, Results as ResultsData, TreeResults } from '../types'

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

function Tile({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="fade-up rounded-lg border border-line bg-surface p-4">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
      <div className="mt-0.5 text-xs text-muted">{sub}</div>
    </div>
  )
}

function Swatch({ color }: { color: string }) {
  return <span className="inline-block size-2.5 shrink-0 rounded-sm" style={{ background: color }} />
}

// ---------------------------------------------------------------- triage

function TriageBars({ o }: { o: OptimiseResults }) {
  const mean = (scenario: string, metric: string) => o.robustness.find((r) => r.scenario === scenario && r.metric === metric)?.mean
  const keys = ['surgery_list_end', 'over_18_end', 'mean_wait_surgery']
  const fmt = (k: string, v: number) => (k.startsWith('mean_wait') ? `${v.toFixed(1)} wk` : Math.round(v).toLocaleString())
  const scenarios = [
    { name: 'Optimiser', label: 'Triage on', color: 'var(--series-1)' },
    { name: o.triage_off_scenario, label: 'Off', color: 'var(--series-2)' },
  ]
  return (
    <>
      <ul className="mb-3 flex justify-end gap-4 text-xs text-muted" aria-label="Legend">
        {scenarios.map((s) => <li key={s.label} className="flex items-center gap-1.5"><Swatch color={s.color} />{s.label}</li>)}
      </ul>
      <div className="space-y-4">
        {keys.map((k, i) => {
          const values = scenarios.map((s) => mean(s.name, k) ?? 0)
          const max = Math.max(...values, 1)
          const [head, ...rest] = o.metrics[k].split(',')
          return (
            <div key={k}>
              <div className="mb-1.5 text-sm">
                {k === 'over_18_end' ? <Term k="waits">{head}</Term> : head}{rest.length ? `,${rest.join(',')}` : ''}
              </div>
              {scenarios.map((s, j) => (
                <div key={s.label} className="mb-1 flex items-center gap-2">
                  <div className="h-3 flex-1">
                    <div className="bar-grow h-full rounded-r-[4px]"
                      style={{ width: `${(values[j] / max) * 100}%`, background: s.color, animationDelay: `${(i * 2 + j) * 90}ms` }} />
                  </div>
                  <span className="w-16 text-right text-sm tabular-nums">{fmt(k, values[j])}</span>
                </div>
              ))}
            </div>
          )
        })}
      </div>
      <p className="mt-4 text-xs text-muted">
        Off = {annotate(o.triage_off_rule)}. Mean of {o.seeds.length} simulations.
      </p>
    </>
  )
}

// ---------------------------------------------------------------- cleaning

function CleaningBar({ c }: { c: ResultsData['cleaning'] }) {
  const parts = [
    { label: 'Fixed', n: c.fixed, color: 'var(--series-1)' },
    { label: 'Set missing', n: c.set_missing, color: 'var(--series-2)' },
    { label: 'Duplicates removed', n: c.duplicates_removed, color: 'var(--series-3)' },
  ]
  const total = parts.reduce((s, p) => s + p.n, 0) + c.wrong
  return (
    <>
      <div className="bar-grow flex h-5 gap-[2px] overflow-hidden rounded-[4px]" role="img"
        aria-label={parts.map((p) => `${p.label} ${p.n}`).join(', ')}>
        {parts.map((p) => <span key={p.label} style={{ width: `${(p.n / total) * 100}%`, background: p.color }} />)}
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

function Gauge({ value, label, sub, color, delay = 0 }: { value: number; label: ReactNode; sub: string; color: string; delay?: number }) {
  const r = 46
  const full = 2 * Math.PI * r
  return (
    <figure className="flex flex-col items-center text-center">
      <svg viewBox="0 0 120 120" className="size-32" role="img" aria-label={`${pct(value)} agreement`}>
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--line)" strokeWidth="10" />
        <circle cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={full} strokeDashoffset={full * (1 - value)} transform="rotate(-90 60 60)"
          className="ring-draw" style={{ ['--ring-full' as string]: `${full}`, animationDelay: `${delay}ms` }} />
        <text x="60" y="66" textAnchor="middle" fontSize="20" fontWeight="600" fill="var(--text)">{pct(value)}</text>
      </svg>
      <figcaption className="mt-2 text-sm font-medium">{label}</figcaption>
      <div className="text-xs text-muted">{sub}</div>
    </figure>
  )
}

function TreeGauges({ t }: { t: TreeResults }) {
  const [raw, banded] = t.runs
  const sub = (n: number) => (n === 0 ? 'no disagreements' : `${n} disagreement${n === 1 ? '' : 's'}`)
  return (
    <>
      <div className="flex flex-wrap justify-around gap-4">
        <Gauge value={raw.agreement} label="Raw values" sub={sub(raw.disagreements)} color="var(--series-1)" />
        <Gauge value={banded.agreement} label={<Term k="nhs_bands">NHS bands</Term>} sub={sub(banded.disagreements)}
          color="var(--series-3)" delay={200} />
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
          <Table caption="Where the tree and the rules disagree" head={['Patient', 'OKS', 'KL', 'Rules', 'Tree', 'Model']}
            rows={t.disagreements.length ? t.disagreements.map((d) => [d.patient_id, d.oks, d.kl_grade, d.rules, d.tree, d.model])
              : [['None', '', '', '', '', '']]} />
        </>}
        <Table caption="Cleaning, logged problems by issue" head={['Problem', 'Logged', 'Fixed', 'Set missing', 'Wrong']}
          rows={r.cleaning.by_issue.map((b) => [`${b.field} · ${b.issue}`, b.logged, b.fixed, b['set missing'], b.wrong])} />
      </div>
    </details>
  )
}

// ---------------------------------------------------------------- page

export default function Results() {
  const [r, setR] = useState<ResultsData | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => { getResults().then(setR).catch(() => setError(true)) }, [])

  if (error) return <ErrorNote text="Couldn't load results" />
  if (!r) return <Loading />
  const test = r.extraction.test
  const o = r.optimise
  const c = r.cleaning
  const costPer100 = test.cost_usd === null ? null : (test.cost_usd / test.letters) * 100
  const total = c.fixed + c.set_missing + c.duplicates_removed + c.wrong

  // the note under the chart only says what the data shows
  const fcfsSame = !!o && o.series.FCFS.every((row, i) => row.over_52 === o.series.Optimiser[i].over_52)
  const oksAt = (p: Policy) => o?.summary.find((s) => s.policy === p && s.surgery_capacity === o.capacity.surgery)?.mean_oks_operated
  const fcfsOks = oksAt('FCFS')
  const optOks = oksAt('Optimiser')

  return (
    <>
      <PageHeader title="Results" meta={<span className="chip chip-plain">Held-out test set · {test.letters} letters</span>} />

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile label="Letters read right" value={pct(test.letters_all_fields_right)} sub="every fact correct" />
        <Tile label="Quotes found" value={pct(test.quote_hit_rate)} sub="each fact's words are in the letter" />
        <Tile label="Pathway matches" value={pct(test.pathway_agreement)} sub="rules on the facts read vs answer key" />
        <Tile label="Cost to read" value={costPer100 === null ? '—' : `$${costPer100.toFixed(2)}`} sub="per 100 letters" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {o && (
          <Card className="fade-up lg:col-span-2" title={<>Nobody left past {o.thresholds.long_wait_weeks} weeks</>}
            meta={<span className="ml-auto text-xs text-muted">waiting over <Term k="waits">{o.thresholds.long_wait_weeks} weeks</Term> · {o.weeks} weeks</span>}>
            <LongWaitChart o={o} />
            {fcfsSame && fcfsOks !== undefined && optOks !== undefined && fcfsOks > optOks && (
              <p className="mt-2 text-xs text-muted">
                <Term k="fcfs">First come, first served</Term> follows the optimiser line exactly, but operates on milder
                knees (mean <Term k="oks">OKS</Term> {fcfsOks.toFixed(1)} vs {optOks.toFixed(1)}).
              </p>
            )}
          </Card>
        )}
        {o && (
          <Card className="fade-up" title={<><Term k="triage">Triage</Term> halves the backlog</>}>
            <TriageBars o={o} />
          </Card>
        )}
        <Card className="fade-up lg:col-span-2" title="Data cleaned"
          meta={<span className="ml-auto text-xs text-muted tabular-nums">
            {total.toLocaleString()} problems found in {c.raw_rows.toLocaleString()} raw rows · {c.wrong} left wrong</span>}>
          <CleaningBar c={c} />
        </Card>
        {r.decision_tree && (
          <Card className="fade-up" title="Learned tree agrees with the rules">
            <TreeGauges t={r.decision_tree} />
          </Card>
        )}
      </div>

      <FullTables r={r} />
    </>
  )
}
