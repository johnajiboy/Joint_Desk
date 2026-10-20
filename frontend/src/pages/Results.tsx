import { useEffect, useState } from 'react'
import { getResults } from '../api'
import { Card, ErrorNote, Loading, Meter, PageHeader } from '../components/AppShell'
import type { Results as ResultsData } from '../types'

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

        <Card title="Rules vs decision tree" className="fade-up">
          <div className="flex min-h-40 items-center justify-center rounded-md border border-dashed border-line text-sm text-muted">
            Stage 4 · not built yet
          </div>
        </Card>
      </div>
    </>
  )
}
