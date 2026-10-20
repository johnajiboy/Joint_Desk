import { useEffect, useState } from 'react'
import { getResults } from '../api'
import { Card, ErrorNote, Loading, Meter, PageHeader } from '../components/AppShell'
import type { Results as ResultsData, TreeResults } from '../types'

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

const RULE_SHORT: Record<string, string> = {
  'OKS 26 or less (with KL 3+) -> surgery': 'OKS ≤ 26 → surgery',
  'OKS above 19 (severe 0-19) -> physio first': 'OKS > 19 → physio first',
  'KL grade 3 or more': 'KL ≥ 3',
  'BMI 35 or more -> weight support': 'BMI ≥ 35',
  'Physio under 6 weeks': 'Physio < 6 weeks',
  'OKS drop of 5 or more': 'OKS drop ≥ 5',
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
                  <td className="py-1.5">{RULE_SHORT[x.rule] ?? x.rule}</td>
                  <td className="py-1.5"><Cut value={x.tree} same={x.same} /></td>
                  <td className="py-1.5"><Cut value={x.banded} same={x.banded_same} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">OKS bands end at 19 and 29, so the banded tree can't draw the rules' line at 26.</p>
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
