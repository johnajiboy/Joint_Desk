import { useEffect, useState } from 'react'
import { getResults } from '../api'
import { Card, ErrorNote, Loading, Meter, PageHeader } from '../components/AppShell'
import { BacklogChart } from '../components/BacklogChart'
import type { CI, OptimiseResults, Pair, Policy, Results as ResultsData, TreeResults } from '../types'

const pct = (v: number) => `${(v * 100).toFixed(1)}%`

const FIELD_LABELS: Record<string, string> = {
  name: 'Name', age: 'Age', sex: 'Sex', side: 'Knee', oks: 'OKS', oks_before: 'Earlier OKS', kl: 'X-ray grade',
  xray_finding: 'X-ray wording', physio_weeks: 'Physio weeks', injections: 'Injections', bmi: 'BMI',
  night_pain: 'Night pain', lives_alone_or_carer: 'Lives alone / carer', walking_aid: 'Walking aid',
  diabetes: 'Diabetes', smoking: 'Smoking', weeks_waiting: 'Weeks (letter)',
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md bg-sunken p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 text-xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  )
}

/** A learned split shown as the rule's comparison: "OKS <= 26.5" reads as 26 for whole-number scores. */
function Cut({ value, same }: { value: number | null; same: boolean }) {
  if (value === null) return <span className="text-muted">not used</span>
  return <span className={`tabular-nums ${same ? '' : 'font-medium text-danger'}`}>≤ {value}{same ? ' · same' : ''}</span>
}

function TreeCard({ t }: { t: TreeResults }) {
  const [cont, disc] = t.runs
  const [showTree, setShowTree] = useState(false)
  return (
    <Card title="Rules vs decision tree" className="fade-up"
      meta={<span className="ml-auto text-xs text-muted tabular-nums">{t.train} train · {t.test} test · labels from rules.py</span>}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
        <Stat label="Agreement · raw values" value={pct(cont.agreement)} sub={`depth ${cont.depth} · ${cont.leaves} leaves`} />
        <Stat label="Agreement · bands" value={pct(disc.agreement)} sub={`depth ${disc.depth} · ${disc.leaves} leaves`} />
        <Stat label="Disagreements" value={`${cont.disagreements} · ${disc.disagreements}`} sub="raw · bands" />
        <Stat label="Truth check" value={`${t.truth_check.matching}/${t.truth_check.patients}`} sub="true pathway = rules" />
      </div>

      <div className="mt-4 space-y-4">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[22rem] text-sm">
            <thead className="text-left text-xs text-muted">
              <tr><th className="py-1 font-medium">Rule</th><th className="py-1 font-medium">Tree · raw</th>
                <th className="py-1 font-medium">Tree · bands</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {t.thresholds.map((x) => (
                <tr key={x.rule}>
                  <td className="py-1.5">{x.short}</td>
                  <td className="py-1.5"><Cut value={x.tree} same={x.same} /></td>
                  <td className="py-1.5"><Cut value={x.banded} same={x.banded_same} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {t.band_misses.map((m) => (
            <p key={m.short} className="mt-2 text-xs text-muted">
              Bands can't draw the rule {m.short}; the nearest band edge is {m.band_edge}.
            </p>
          ))}
        </div>

        <div>
          <h3 className="mb-1 text-xs font-medium text-muted">Where the tree and the rules disagree</h3>
          {t.disagreements.length === 0 ? <p className="text-sm text-muted">None</p> : (
            <ul className="divide-y divide-line text-sm">
              {t.disagreements.map((d) => (
                <li key={`${d.model}-${d.patient_id}`} className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-1 py-1.5">
                  <span className="w-20 font-medium tabular-nums">{d.patient_id}</span>
                  <span className="text-muted tabular-nums">OKS {d.oks} · KL {d.kl_grade}</span>
                  <span className="ml-auto text-xs"><span className="text-muted">rules</span> {d.rules.replace('Keep on ', '')}
                    <span className="text-muted"> · tree</span> {d.tree} <span className="text-muted">({d.model === 'continuous' ? 'raw' : 'bands'})</span></span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <button onClick={() => setShowTree(!showTree)} aria-expanded={showTree}
        className="press mt-3 h-11 rounded-md px-2 text-sm text-primary dark:text-text">
        {showTree ? 'Hide learned rules' : 'Learned rules'}
      </button>
      {showTree && (
        <pre className="fade-up mt-1 max-h-96 overflow-auto rounded-md bg-sunken p-3 font-mono text-xs leading-5">{t.tree_text}</pre>
      )}
    </Card>
  )
}

const POLICIES: Policy[] = ['FCFS', 'Priority only', 'Optimiser']

/** Mean ± half-width of the 95% CI, as in eval/results/optimise. */
const pm = (m: number, lo: number, hi: number) => {
  const d = Math.abs(m) >= 100 ? 0 : 1
  return `${m.toFixed(d)} ± ${((hi - lo) / 2).toFixed(d)}`
}

function OptimiseCard({ o }: { o: OptimiseResults }) {
  const cap = o.capacity.surgery
  const at = (c: number, p: Policy) => o.summary.find((r) => r.surgery_capacity === c && r.policy === p)
  const caps = [...new Set(o.summary.map((r) => r.surgery_capacity))]
  const ci = (scenario: string, metric: string) => o.robustness.find((r) => r.scenario === scenario && r.metric === metric)
  const cell = (c?: CI) => (c ? pm(c.mean, c.ci_low, c.ci_high) : '—')
  const pair = (comparison: string, metric: string) => o.pairs.find((r) => r.comparison === comparison && r.metric === metric)
  const metricKeys = Object.keys(o.metrics)
  const lw = o.thresholds.long_wait_weeks
  const triageKeys = ['surgery_list_start', 'surgery_list_end', 'mean_wait_surgery', 'over_18_end', 'over_52_end']
  const triageLabel = (k: string) => (k === 'surgery_list_start' ? 'Surgery list, start' : o.metrics[k])
  const vs = (other: string) => `Optimiser - ${other}`
  const PairCell = ({ p }: { p?: Pair }) => p ? (
    <><span className="tabular-nums">{pm(p.mean_diff, p.ci_low, p.ci_high)}</span>
      <span className="block text-xs text-muted">{p.verdict}</span></>
  ) : <>—</>

  return (
    <Card title={`Weekly slots · ${o.weeks}-week simulation`} className="fade-up lg:col-span-2"
      meta={<span className="ml-auto text-xs text-muted tabular-nums">{o.arrival_rate} new referrals a week · surgery {o.capacity.surgery},
        physio {o.capacity.physio}, weight support {o.capacity.weight_support}</span>}>
      <BacklogChart o={o} />
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div className="overflow-x-auto">
          <h3 className="mb-1 text-xs font-medium text-muted">Surgery capacity {cap} · seed {o.seeds[0]}</h3>
          <table className="w-full min-w-[24rem] text-sm tabular-nums">
            <thead className="text-left text-xs text-muted">
              <tr><th className="py-1 font-medium">Policy</th><th className="py-1 text-right font-medium">Over-{lw}s skipped</th>
                <th className="py-1 text-right font-medium">Over {lw}, end</th><th className="py-1 text-right font-medium">Surgery wait</th>
                <th className="py-1 text-right font-medium">OKS operated</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {POLICIES.map((p) => {
                const r = at(cap, p)
                if (!r) return null
                return (
                  <tr key={p}>
                    <td className="py-1.5">{p}</td>
                    <td className={`py-1.5 text-right ${r.over_52_skipped_patients ? 'font-medium text-danger' : ''}`}>{r.over_52_skipped_patients}</td>
                    <td className={`py-1.5 text-right ${r.over_52_end ? 'text-danger' : ''}`}>{r.over_52_end}</td>
                    <td className="py-1.5 text-right">{r.mean_wait_surgery.toFixed(1)} wk</td>
                    <td className="py-1.5 text-right">{r.mean_oks_operated.toFixed(1)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">Lower OKS = worse knees treated. Skipped = over {lw} weeks, passed over for someone who isn't.</p>
        </div>
        <div className="overflow-x-auto">
          <h3 className="mb-1 text-xs font-medium text-muted">Over {lw} weeks after {o.weeks} weeks, by surgery slots a week</h3>
          <table className="w-full min-w-[20rem] text-sm tabular-nums">
            <thead className="text-left text-xs text-muted">
              <tr><th className="py-1 font-medium">Slots</th>{POLICIES.map((p) => <th key={p} className="py-1 text-right font-medium">{p}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-line">
              {caps.map((c) => (
                <tr key={c}>
                  <td className="py-1.5">{c}</td>
                  {POLICIES.map((p) => {
                    const v = at(c, p)?.over_52_end
                    return <td key={p} className={`py-1.5 text-right ${v ? 'text-danger' : ''}`}>{v ?? '—'}</td>
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="overflow-x-auto">
          <h3 className="mb-1 text-xs font-medium text-muted">Across {o.seeds.length} arrival seeds · mean ± 95% CI</h3>
          <table className="w-full min-w-[28rem] text-sm tabular-nums">
            <thead className="text-left text-xs text-muted">
              <tr><th className="py-1 font-medium">Measure</th>{POLICIES.map((p) => <th key={p} className="py-1 text-right font-medium">{p}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-line">
              {metricKeys.map((k) => (
                <tr key={k}>
                  <td className="py-1.5">{o.metrics[k]}</td>
                  {POLICIES.map((p) => <td key={p} className="py-1.5 text-right">{cell(ci(p, k))}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="overflow-x-auto">
          <h3 className="mb-1 text-xs font-medium text-muted">Do the differences hold? Optimiser minus each policy, paired by seed</h3>
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="text-left text-xs text-muted">
              <tr><th className="py-1 font-medium">Measure</th><th className="py-1 font-medium">vs FCFS</th>
                <th className="py-1 font-medium">vs Priority only</th></tr>
            </thead>
            <tbody className="divide-y divide-line align-top">
              {metricKeys.map((k) => (
                <tr key={k}>
                  <td className="py-1.5 pr-2">{o.metrics[k]}</td>
                  <td className="py-1.5 pr-2"><PairCell p={pair(vs('FCFS'), k)} /></td>
                  <td className="py-1.5"><PairCell p={pair(vs('Priority only'), k)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="overflow-x-auto lg:col-span-2">
          <h3 className="mb-1 text-xs font-medium text-muted">
            Triage on vs off · optimiser, {o.seeds.length} seeds · off = {o.triage_off_rule}
          </h3>
          <table className="w-full min-w-[30rem] text-sm">
            <thead className="text-left text-xs text-muted">
              <tr><th className="py-1 font-medium">Measure</th><th className="py-1 text-right font-medium">Triage on</th>
                <th className="py-1 text-right font-medium">Triage off</th><th className="py-1 pl-4 font-medium">Off minus on</th></tr>
            </thead>
            <tbody className="divide-y divide-line align-top">
              {triageKeys.map((k) => {
                const p = pair(`${o.triage_off_scenario} - Optimiser`, k)
                return (
                  <tr key={k}>
                    <td className="py-1.5">{triageLabel(k)}</td>
                    <td className="py-1.5 text-right tabular-nums">{cell(ci('Optimiser', k))}</td>
                    <td className="py-1.5 text-right tabular-nums">{cell(ci(o.triage_off_scenario, k))}</td>
                    <td className="py-1.5 pl-4">{p ? <PairCell p={p} /> : <span className="text-muted">same start list each seed</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  )
}

export default function Results() {
  const [r, setR] = useState<ResultsData | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => { getResults().then(setR).catch(() => setError(true)) }, [])

  if (error) return <ErrorNote text="Couldn't load results" />
  if (!r) return <Loading />
  const { dev, test } = r.extraction
  const c = r.cleaning

  return (
    <>
      <PageHeader title="Results" meta={<span className="chip chip-plain">{dev.model}</span>} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="LLM accuracy per field" meta={<span className="ml-auto flex gap-3 text-xs text-muted">
          <span>Dev {dev.letters}</span><span>Test {test.letters}</span></span>} className="fade-up">
          <ul className="space-y-1.5">
            {Object.keys(dev.field_accuracy).map((f, i) => (
              <li key={f} className="grid grid-cols-[minmax(0,8rem)_1fr_1fr] items-center gap-3 text-sm">
                <span className="truncate text-muted">{FIELD_LABELS[f] ?? f}</span>
                {[dev, test].map((s) => (
                  <span key={s === dev ? 'd' : 't'} className="flex items-center gap-2">
                    <span className="flex-1"><Meter value={s.field_accuracy[f]} max={1} delay={i * 30} /></span>
                    <span className="w-12 text-right text-xs tabular-nums">{pct(s.field_accuracy[f])}</span>
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Quotes and pathway" meta={<span className="ml-auto text-xs text-muted">dev · held-out test</span>}
          className="fade-up">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Quote hit rate" value={pct(test.quote_hit_rate)} sub={`dev ${pct(dev.quote_hit_rate)}`} />
            <Stat label="Pathway agreement" value={pct(test.pathway_agreement)} sub={`dev ${pct(dev.pathway_agreement)}`} />
            <Stat label="Letters fully right" value={pct(test.letters_all_fields_right)} sub={`dev ${pct(dev.letters_all_fields_right)}`} />
            <Stat label="Facts dropped" value={`${test.facts_dropped}`} sub={`dev ${dev.facts_dropped}`} />
            <Stat label="Priority difference" value={test.priority_mae.toFixed(1)} sub={`dev ${dev.priority_mae.toFixed(1)}`} />
            <Stat label="Test run cost" value={test.cost_usd === null ? '—' : `$${test.cost_usd.toFixed(2)}`}
              sub={`${test.letters} letters`} />
          </div>
          <p className="mt-3 text-xs text-muted">Test letters: new patients, shorthand, typos, scanned text. Prompt tuned on dev only.</p>
        </Card>

        <Card title="Cleaning" meta={<span className="ml-auto text-xs text-muted tabular-nums">
          {c.raw_rows.toLocaleString()} rows → {c.patients.toLocaleString()} patients</span>} className="fade-up">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Duplicates removed" value={`${c.duplicates_removed}`} />
            <Stat label="Fixed" value={`${c.fixed}`} sub={`of ${c.logged}`} />
            <Stat label="Set missing" value={`${c.set_missing}`} sub="can't recover" />
            <Stat label="Left wrong" value={`${c.wrong}`} />
          </div>
          <table className="mt-4 w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr><th className="py-1 font-medium">Problem</th><th className="py-1 text-right font-medium">Fixed</th>
                <th className="py-1 text-right font-medium">Missing</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {c.by_issue.map((b) => (
                <tr key={`${b.field}-${b.issue}`}>
                  <td className="py-1.5"><span className="font-medium">{b.field.replace(/_/g, ' ')}</span>
                    <span className="text-muted"> · {b.issue.replace(/ \(.*\)/, '')}</span></td>
                  <td className="py-1.5 text-right tabular-nums">{b.fixed || '—'}</td>
                  <td className="py-1.5 text-right tabular-nums">{b['set missing'] || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {r.optimise && <OptimiseCard o={r.optimise} />}
        {r.decision_tree ? <TreeCard t={r.decision_tree} /> : (
          <Card title="Rules vs decision tree" className="fade-up">
            <div className="flex min-h-40 items-center justify-center rounded-md border border-dashed border-line text-sm text-muted">
              Not built yet
            </div>
          </Card>
        )}
      </div>
    </>
  )
}
