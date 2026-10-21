import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getQueue } from '../api'
import { ErrorNote, Loading, PageHeader } from '../components/AppShell'
import { stagger } from '../components/ui'
import { PathwayChip, Weeks } from '../components/PathwayChip'
import { Term } from '../components/Term'
import { UploadBar } from '../components/UploadBar'
import { effectivePathway, TABS } from '../pathways'
import { matches } from '../search'
import type { Referral, UploadResult } from '../types'

const PAGE = 25

function DecisionNote({ r }: { r: Referral }) {
  if (!r.decision) return null
  return <span className="text-xs text-muted">{r.decision.kind === 'overridden' ? 'Overridden' : 'Confirmed'}</span>
}

export default function Queue() {
  const [queue, setQueue] = useState<Referral[] | null>(null)
  const [error, setError] = useState(false)
  const [params, setParams] = useSearchParams()
  const tab = TABS.find((t) => t.key === params.get('tab')) ?? TABS[0]
  const query = params.get('q') ?? ''
  const [shown, setShown] = useState(PAGE)
  const [uploaded, setUploaded] = useState<Record<string, string[]>>({})   // patient id -> files uploaded this session
  const search = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const load = () => getQueue().then(setQueue).catch(() => setError(true))
  useEffect(() => { load() }, [])

  function setParam(key: 'q' | 'tab', value: string) {
    const next = new URLSearchParams(params)
    if (!value || (key === 'tab' && value === 'all')) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
    setShown(PAGE)
  }

  function onRead(result: UploadResult) {
    if (result.ok) {
      const id = result.referral.id
      setUploaded((u) => ({ ...u, [id]: [...new Set([...(u[id] ?? []), result.file])] }))
    }
    load()
  }

  const found = useMemo(() => queue?.filter((r) => matches(r, query, uploaded[r.id])) ?? [], [queue, query, uploaded])
  const counts = useMemo(
    () => Object.fromEntries(TABS.map((t) => [t.key, found.filter((r) => t.match(effectivePathway(r))).length])),
    [found],
  )
  const allRows = useMemo(() => found.filter((r) => tab.match(effectivePathway(r))), [found, tab])
  const rows = allRows.slice(0, shown)

  return (
    <>
      <PageHeader title="Referrals" meta={queue && <span className="chip chip-plain">{queue.length}</span>} />
      <UploadBar onRead={onRead} />

      <div className="mb-3 w-full max-w-[720px]">
        <label className="flex h-11 items-center gap-2 rounded-lg border border-line bg-surface px-3 focus-within:border-primary">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
            strokeLinecap="round" className="shrink-0 text-muted" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" />
          </svg>
          <span className="sr-only">Search referrals</span>
          <input ref={search} type="search" value={query} onChange={(e) => setParam('q', e.target.value)}
            onKeyDown={(e) => e.key === 'Escape' && setParam('q', '')}
            placeholder="Search name, NHS number, letter or file" autoComplete="off" spellCheck={false}
            className="h-full min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted" />
          {query && (
            <button type="button" onClick={() => { setParam('q', ''); search.current?.focus() }}
              className="press -mr-2 h-11 shrink-0 px-2 text-sm text-muted hover:text-text">Clear</button>
          )}
        </label>
      </div>

      <div role="tablist" aria-label="Pathway" className="no-scrollbar -mx-4 mb-3 flex gap-1 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={t.key === tab.key}
            onClick={() => setParam('tab', t.key)}
            className={`press flex h-11 shrink-0 items-center gap-2 rounded-md px-3 text-sm ${
              t.key === tab.key ? 'border border-line bg-surface font-medium' : 'border border-transparent text-muted hover:text-text'}`}>
            {t.label}
            <span className="tabular-nums text-muted">{counts[t.key]}</span>
          </button>
        ))}
      </div>

      {error && <ErrorNote text="Couldn't load referrals" />}
      {!error && !queue && <Loading />}
      {queue && rows.length === 0 && (
        <div className="py-16 text-center text-sm text-muted">
          {query ? <>No match · <button type="button" onClick={() => { setParam('q', ''); search.current?.focus() }}
            className="text-primary underline underline-offset-2 dark:text-text">Clear</button></> : 'No referrals'}
        </div>
      )}

      {rows.length > 0 && (
        <>
          {/* tablet and desktop: table */}
          <div className="hidden overflow-hidden rounded-lg border border-line bg-surface sm:block">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Pathway</th>
                  <th className="px-4 py-3 text-right font-medium"><Term k="priority">Priority</Term></th>
                  <th className="px-4 py-3 text-right font-medium"><Term k="waits">Waiting</Term></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.id} tabIndex={0} style={stagger(i)}
                    onClick={() => navigate(`/patient/${r.id}`)}
                    onKeyDown={(e) => e.key === 'Enter' && navigate(`/patient/${r.id}`)}
                    className="fade-up cursor-pointer border-b border-line last:border-0 hover:bg-sunken focus-visible:bg-sunken focus-visible:outline-none">
                    <td className="px-4 py-2.5">
                      <div className="font-medium">{r.name}</div>
                      <div className="text-xs text-muted">{r.letter_id ?? '—'}</div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <PathwayChip pathway={effectivePathway(r)} weight={r.weight_support} />
                        <DecisionNote r={r} />
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-right font-medium tabular-nums">{r.priority}</td>
                    <td className="px-4 py-2.5 text-right"><Weeks weeks={r.weeks_waiting} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* phones: cards */}
          <ul className="space-y-2 sm:hidden">
            {rows.map((r, i) => (
              <li key={r.id} className="fade-up" style={stagger(i)}>
                <Link to={`/patient/${r.id}`}
                  className="press flex min-h-16 items-center gap-3 rounded-lg border border-line bg-surface p-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{r.name}</div>
                    <div className="mt-1 flex items-center gap-2">
                      <PathwayChip pathway={effectivePathway(r)} weight={r.weight_support} />
                      <DecisionNote r={r} />
                    </div>
                  </div>
                  <div className="text-right text-sm">
                    <div className="font-medium tabular-nums">{r.priority}</div>
                    <Weeks weeks={r.weeks_waiting} />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {allRows.length > rows.length && (
            <div className="mt-3 flex items-center justify-center gap-3 text-sm text-muted">
              <span className="tabular-nums">{rows.length} of {allRows.length}</span>
              <button type="button" onClick={() => setShown((n) => n + PAGE)}
                className="press h-11 rounded-md border border-line bg-surface px-4 text-text hover:border-primary">Show more</button>
            </div>
          )}
        </>
      )}
    </>
  )
}
