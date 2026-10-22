import { useRef, useState } from 'react'
import type { DragEvent } from 'react'
import { Link } from 'react-router-dom'
import { DEMO, DEMO_SAMPLE, getClinician, importCommit, importPreview, NeedsBackend } from '../api'
import { effectivePathway } from '../pathways'
import type { ImportPreview, ImportResult, MatchConfidence, SkippedRow } from '../types'
import { PaperclipIcon } from './icons'
import { PasscodeGate } from './PasscodeGate'
import { PathwayChip } from './PathwayChip'
import { primaryButton, secondaryButton } from './ui'

const MATCH: Record<MatchConfidence, string> = {
  exact: 'Exact', alias: 'Alias', fuzzy: 'Fuzzy', none: 'No match', manual: 'Set by you',
}

function skippedCsv(rows: SkippedRow[]): string {
  const q = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`
  return ['row,nhs_number,name,reason', ...rows.map((r) => [r.row, r.nhs_number, r.name, r.reason].map(q).join(','))].join('\n')
}

/**
 * Spreadsheet import: 1 choose a file, 2 check the column mapping (the clinician can change any column, or ignore
 * it; missing required fields block the import), 3 import and see what was added, updated or skipped.
 */
export function ImportPanel({ onImported, onClose }: { onImported: (r: ImportResult) => void; onClose: () => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [mapping, setMapping] = useState<Record<string, string | null>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [over, setOver] = useState(false)

  async function choose(f: File | undefined) {
    if (!f) return
    setFile(f); setPreview(null); setResult(null); setError(null); setBusy(true)
    try {
      const p = await importPreview(f)
      setPreview(p)
      setMapping(Object.fromEntries(p.columns.map((c) => [c.header, c.field])))
    } catch (e) {
      setError(e instanceof NeedsBackend || e instanceof Error ? e.message : "Couldn't read the spreadsheet")
    } finally {
      setBusy(false)
    }
  }

  async function remap(header: string, field: string | null) {
    const next = { ...mapping, [header]: field }
    setMapping(next)
    if (!file || DEMO) return
    setBusy(true)
    try {
      setPreview(await importPreview(file, next))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't check the mapping")
    } finally {
      setBusy(false)
    }
  }

  async function commit() {
    if (!file) return
    setBusy(true); setError(null)
    try {
      const r = await importCommit(file, mapping, getClinician())
      setResult(r)
      onImported(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't import")
    } finally {
      setBusy(false)
    }
  }

  function reset() {
    setFile(null); setPreview(null); setResult(null); setError(null)
    if (input.current) input.current.value = ''
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    choose(e.dataTransfer.files[0])
  }

  const blocked = !preview || preview.problems.length > 0 || preview.valid === 0 || busy
  const downloadSkipped = () => {
    const url = URL.createObjectURL(new Blob([skippedCsv(result?.skipped ?? [])], { type: 'text/csv' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: 'skipped_rows.csv' })
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="fade-up mb-5 min-w-0 rounded-lg border border-line bg-surface p-4 sm:p-5" aria-label="Import spreadsheet">
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 className="text-sm font-semibold">Import spreadsheet</h2>
        <a href="/import_template.csv" download className="text-sm text-primary underline-offset-2 hover:underline dark:text-text">
          Download template
        </a>
        {DEMO && (
          <a href={`/samples/${DEMO_SAMPLE}`} download className="text-sm text-primary underline-offset-2 hover:underline dark:text-text">
            Download the sample
          </a>
        )}
        <button type="button" onClick={onClose} className="press ml-auto h-11 px-2 text-sm text-muted hover:text-text">Close</button>
      </div>

      {/* step 1: choose a file (live site: after the passcode) */}
      {!result && (
        <PasscodeGate primary={false}>
        <label onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={onDrop}
          className={`flex min-h-16 cursor-pointer items-center gap-3 rounded-md border border-dashed px-4 py-3 text-sm ${
            over ? 'border-primary' : 'border-line'}`}>
          <span className="shrink-0 text-muted"><PaperclipIcon /></span>
          <span className={file ? 'truncate' : 'text-muted'}>
            {file ? file.name : 'Choose a .csv or .xlsx file, or drop it here'}
          </span>
          {busy && <span className="reading-bar ml-auto" aria-label="Reading" />}
          <input ref={input} type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="sr-only" onChange={(e) => choose(e.target.files?.[0])} />
        </label>
        </PasscodeGate>
      )}
      {DEMO && !result && <p className="mt-2 text-xs text-muted">Demo site: only {DEMO_SAMPLE} works; other files need the backend.</p>}
      {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}

      {/* step 2: the mapping */}
      {preview && !result && (
        <div className="mt-4">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[30rem] text-sm">
              <thead className="text-left text-xs text-muted">
                <tr><th className="py-1.5 font-medium">Column in the file</th><th className="py-1.5 font-medium">Field</th>
                  <th className="py-1.5 font-medium">Match</th></tr>
              </thead>
              <tbody className="divide-y divide-line">
                {preview.columns.map((c) => (
                  <tr key={c.header}>
                    <td className="py-1.5 pr-3 font-medium">{c.header || '(no header)'}</td>
                    <td className="py-1.5 pr-3">
                      <select value={mapping[c.header] ?? ''} disabled={DEMO || busy} aria-label={`Field for ${c.header}`}
                        onChange={(e) => remap(c.header, e.target.value || null)}
                        className="h-11 w-full max-w-60 rounded-md border border-line bg-surface px-2 text-sm disabled:opacity-80">
                        <option value="">Ignore</option>
                        {preview.fields.map((f) => <option key={f.field} value={f.field}>{f.label}{f.required ? ' *' : ''}</option>)}
                      </select>
                    </td>
                    <td className="py-1.5 text-muted">{MATCH[mapping[c.header] === c.field ? c.confidence : 'manual']}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {DEMO && <p className="mt-2 text-xs text-muted">Changing the mapping needs the backend.</p>}

          {preview.problems.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm font-medium text-danger">{preview.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          )}

          <h3 className="mt-5 mb-1 text-xs font-medium text-muted">First {preview.rows.length} of {preview.total_rows} rows</h3>
          <div className="max-h-72 overflow-auto rounded-md border border-line">
            <table className="w-full text-xs whitespace-nowrap">
              <thead className="sticky top-0 bg-sunken text-left text-muted">
                <tr>{preview.columns.map((c) => <th key={c.header} className="px-2 py-1.5 font-medium">{c.header}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-line">
                {preview.rows.map((r, i) => (
                  <tr key={i}>{r.map((v, j) => <td key={j} className={`px-2 py-1 ${mapping[preview.columns[j].header] ? '' : 'text-muted'}`}>{v}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>

          {preview.skipped.length > 0 && preview.problems.length === 0 && (
            <p className="mt-3 text-sm text-muted">{preview.skipped.length} rows will be skipped: {preview.skipped.slice(0, 3).map((s) => `row ${s.row}, ${s.reason}`).join('; ')}
              {preview.skipped.length > 3 ? '…' : ''}</p>
          )}

          {/* step 3: import */}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button type="button" className={primaryButton} disabled={blocked} onClick={commit}>
              {busy ? 'Checking…' : `Import ${preview.valid} patient${preview.valid === 1 ? '' : 's'}`}
            </button>
            <button type="button" className={secondaryButton} onClick={reset}>Choose another file</button>
          </div>
        </div>
      )}

      {/* summary */}
      {result && (
        <div className="fade-up">
          <p className="text-base font-semibold tabular-nums">
            {result.added} added · {result.updated} updated · {result.skipped.length} skipped
          </p>
          <p className="mt-0.5 text-xs text-muted">{result.file} · {result.rows} rows</p>
          <ul className="mt-3 divide-y divide-line">
            {result.referrals.slice(0, 5).map((r) => (
              <li key={r.id} className="flex min-h-11 items-center gap-3 py-1 text-sm">
                <Link to={`/patient/${r.id}`} className="min-w-0 flex-1 truncate font-semibold hover:underline">{r.name}</Link>
                <PathwayChip pathway={effectivePathway(r)} priority={r.priority} />
              </li>
            ))}
          </ul>
          {result.referrals.length > 5 && <p className="mt-1 text-xs text-muted">and {result.referrals.length - 5} more in the queue below</p>}
          <div className="mt-4 flex flex-wrap gap-3">
            {result.skipped.length > 0 && (
              <button type="button" className={secondaryButton} onClick={downloadSkipped}>Download skipped rows</button>
            )}
            <button type="button" className={secondaryButton} onClick={reset}>Import another</button>
          </div>
        </div>
      )}
    </section>
  )
}
