import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getQueue } from '../api'
import { ErrorNote, Loading, PageHeader } from '../components/AppShell'
import { stagger } from '../components/ui'
import { PathwayChip, Weeks } from '../components/PathwayChip'
import { UploadBar } from '../components/UploadBar'
import { effectivePathway, TABS } from '../pathways'
import type { Referral } from '../types'

function DecisionNote({ r }: { r: Referral }) {
  if (!r.decision) return null
  return <span className="text-xs text-muted">{r.decision.kind === 'overridden' ? 'Overridden' : 'Confirmed'}</span>
}

export default function Queue() {
  const [queue, setQueue] = useState<Referral[] | null>(null)
  const [error, setError] = useState(false)
  const [params, setParams] = useSearchParams()
  const tab = TABS.find((t) => t.key === params.get('tab')) ?? TABS[0]
  const navigate = useNavigate()

  const load = () => getQueue().then(setQueue).catch(() => setError(true))
  useEffect(() => { load() }, [])

  const counts = useMemo(
    () => Object.fromEntries(TABS.map((t) => [t.key, queue?.filter((r) => t.match(effectivePathway(r))).length ?? 0])),
    [queue],
  )
  const rows = useMemo(() => queue?.filter((r) => tab.match(effectivePathway(r))) ?? [], [queue, tab])

  return (
    <>
      <PageHeader title="Referrals" meta={queue && <span className="chip chip-plain">{queue.length}</span>} />
      <UploadBar onRead={load} />

      <div role="tablist" aria-label="Pathway" className="no-scrollbar -mx-4 mb-3 flex gap-1 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={t.key === tab.key}
            onClick={() => setParams(t.key === 'all' ? {} : { tab: t.key }, { replace: true })}
            className={`press flex h-11 shrink-0 items-center gap-2 rounded-md px-3 text-sm ${
              t.key === tab.key ? 'border border-line bg-surface font-medium' : 'border border-transparent text-muted hover:text-text'}`}>
            {t.label}
            <span className="tabular-nums text-muted">{counts[t.key]}</span>
          </button>
        ))}
      </div>

      {error && <ErrorNote text="Couldn't load referrals" />}
      {!error && !queue && <Loading />}
      {queue && rows.length === 0 && <ErrorNote text="No referrals" />}

      {rows.length > 0 && (
        <>
          {/* tablet and desktop: table */}
          <div className="hidden overflow-hidden rounded-lg border border-line bg-surface sm:block">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Pathway</th>
                  <th className="px-4 py-3 text-right font-medium">Priority</th>
                  <th className="px-4 py-3 text-right font-medium">Waiting</th>
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
                      <div className="text-xs text-muted">{r.letter_id}</div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <PathwayChip pathway={effectivePathway(r)} />
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
                      <PathwayChip pathway={effectivePathway(r)} />
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
        </>
      )}
    </>
  )
}
