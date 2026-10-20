import { useState } from 'react'
import { Link } from 'react-router-dom'
import { buildWeek } from '../api'
import { Card, ErrorNote, PageHeader } from '../components/AppShell'
import { primaryButton, stagger } from '../components/ui'
import { PathwayChip, Weeks } from '../components/PathwayChip'
import type { Referral, SlotList, WeekPlan } from '../types'

const NAMES: Record<SlotList['kind'], string> = { surgery: 'Surgery', physio: 'Physio', weight_physio: 'Weight support' }

const weekOf = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

function Tile({ label, value, of, over = false }: { label: string; value: number | null; of: number; over?: boolean }) {
  return (
    <div className="fade-up rounded-lg border border-line bg-surface p-4">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">
        <span className={over ? 'text-danger' : ''}>{value ?? '—'}</span>
        <span className="text-base font-normal text-muted"> / {of}</span>
      </div>
    </div>
  )
}

function Row({ r, i, muted = false }: { r: Referral; i: number; muted?: boolean }) {
  return (
    <li className="fade-up" style={stagger(i)}>
      <Link to={`/patient/${r.id}`}
        className={`press flex min-h-11 items-center gap-3 rounded-md px-2 text-sm hover:bg-sunken ${muted ? 'text-muted' : ''}`}>
        <span className="w-5 shrink-0 text-right text-xs text-muted tabular-nums">{i + 1}</span>
        <span className="min-w-0 flex-1 truncate">{r.name}</span>
        <span className="w-8 text-right font-medium tabular-nums">{r.priority}</span>
        <span className="w-14 text-right"><Weeks weeks={r.weeks_waiting} /></span>
      </Link>
    </li>
  )
}

export default function Week() {
  const [plan, setPlan] = useState<WeekPlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)

  async function build() {
    setBusy(true)
    setError(false)
    try {
      setPlan(await buildWeek())
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  const capacity = { surgery: 12, physio: 20, weight_physio: 8 }
  const lists = plan?.lists
  const lw = plan?.long_wait

  return (
    <>
      <PageHeader title="This week"
        meta={plan && <span className="chip chip-plain">Week of {weekOf(plan.week_of)}</span>}
        action={<button className={primaryButton} onClick={build} disabled={busy}>
          {busy ? 'Building…' : plan ? 'Rebuild list' : "Build this week's list"}
        </button>} />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {(['surgery', 'physio', 'weight_physio'] as const).map((k) => {
          const l = lists?.find((x) => x.kind === k)
          return <Tile key={k} label={`${NAMES[k]} slots`} value={l ? l.in.length : null} of={l?.capacity ?? capacity[k]} />
        })}
        <Tile label="Over 52 weeks in" value={lw ? lw.included : null} of={lw?.total ?? 0}
          over={!!lw && lw.included < lw.total} />
      </div>

      {error && <ErrorNote text="Couldn't build the list" />}
      {!plan && !error && <ErrorNote text="Not built yet" />}

      {lists && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {lists.map((l) => (
              <Card key={l.kind} title={NAMES[l.kind]}
                meta={<span className="ml-auto flex items-center gap-2 text-xs text-muted">
                  <PathwayChip pathway={l.kind} /> {l.in.length} in · {l.waiting} waiting
                </span>}>
                {l.in.length === 0 ? <p className="py-4 text-sm text-muted">Nobody on this pathway</p> : (
                  <ol>{l.in.map((r, i) => <Row key={r.id} r={r} i={i} />)}</ol>
                )}
                {l.next.length > 0 && (
                  <>
                    <h3 className="mt-3 mb-1 px-2 text-xs font-medium text-muted">Next</h3>
                    <ol>{l.next.map((r, i) => <Row key={r.id} r={r} i={l.in.length + i} muted />)}</ol>
                  </>
                )}
              </Card>
            ))}
          </div>
          <p className="mt-4 text-xs text-muted">
            Greedy fill · over {lw?.weeks} weeks first, then priority · optimiser in stage 5
          </p>
        </>
      )}
    </>
  )
}
