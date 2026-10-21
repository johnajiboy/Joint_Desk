import { useState } from 'react'
import { Link } from 'react-router-dom'
import { buildWeek } from '../api'
import { Card, ErrorNote, PageHeader } from '../components/AppShell'
import { PathwayChip, Weeks } from '../components/PathwayChip'
import { Term } from '../components/Term'
import { primaryButton, stagger } from '../components/ui'
import type { ReactNode } from 'react'
import type { WeekPatient, WeekPlan } from '../types'

const LABELS = { surgery: 'Surgery', physio: 'Physio', weight_support: 'Weight support' }

const weekOf = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })

function Tile({ label, value, of, over = false }: { label: ReactNode; value: number | null; of: number | null; over?: boolean }) {
  return (
    <div className="fade-up rounded-lg border border-line bg-surface p-4">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">
        <span className={over ? 'text-danger' : ''}>{value ?? '—'}</span>
        {of !== null && <span className="text-base font-normal text-muted"> / {of}</span>}
      </div>
    </div>
  )
}

function Row({ p, i, muted = false }: { p: WeekPatient; i: number; muted?: boolean }) {
  const body = (
    <>
      <span className="w-5 shrink-0 pt-0.5 text-right text-xs text-muted tabular-nums">{i + 1}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-semibold">{p.name}</span>
        <span className={`block truncate text-xs ${p.long_wait && muted ? 'text-danger' : 'text-muted'}`}>{p.reason}</span>
      </span>
      {p.pathway === 'weight_physio' && <PathwayChip pathway={p.pathway} className="hidden xl:inline-flex" />}
      <span className="w-8 pt-0.5 text-right font-medium tabular-nums">{p.priority}</span>
      <span className="w-14 pt-0.5 text-right"><Weeks weeks={p.weeks_waiting} /></span>
    </>
  )
  const cls = `flex min-h-12 items-start gap-3 rounded-md px-2 py-1.5 text-sm ${muted ? 'text-muted' : ''}`
  return (
    <li className="fade-up" style={stagger(i)}>
      {p.has_page
        ? <Link to={`/patient/${p.id}`} className={`press hover:bg-sunken ${cls}`}>{body}</Link>
        : <div className={cls} title={p.id}>{body}</div>}
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

  const lw = plan?.long_wait

  return (
    <>
      <PageHeader title="This week"
        meta={plan && <span className="chip chip-plain">Week of {weekOf(plan.week_of)}</span>}
        action={<button className={primaryButton} onClick={build} disabled={busy}>
          {busy ? 'Building…' : plan ? 'Rebuild list' : "Build this week's list"}
        </button>} />

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {(['surgery', 'physio', 'weight_support'] as const).map((k) => {
          const l = plan?.lists.find((x) => x.kind === k)
          return <Tile key={k} label={`${LABELS[k]} slots`} value={l ? l.in.length : null} of={l?.capacity ?? null} />
        })}
        <Tile label={<>{lw ? 'Over ' : 'Long waits in'}{lw && <Term k="waits">{lw.weeks} weeks</Term>}{lw ? ' in' : ''}</>}
          value={lw ? lw.included : null} of={lw?.total ?? null}
          over={!!lw && lw.included < lw.total} />
      </div>

      {plan?.status === 'infeasible' && (
        <div className="fade-up mb-5 rounded-lg border border-line bg-surface p-4 text-sm">
          <div className="font-medium text-danger">Over-52s don't all fit · {lw?.unmet} without a slot</div>
          <p className="mt-1 text-muted">{plan.shortfall.join(' · ')}. Every slot they can use goes to them; nobody over 52 weeks is skipped.</p>
        </div>
      )}

      {error && <ErrorNote text="Couldn't build the list" />}
      {!plan && !error && <ErrorNote text="Not built yet" />}

      {plan && plan.unmet?.length > 0 && (
        <details className="fade-up mb-5 rounded-lg border border-line bg-surface">
          <summary className="flex min-h-11 cursor-pointer items-center gap-2 px-4 py-2 text-sm font-medium">
            <span className="text-danger tabular-nums">{plan.unmet.length}</span>
            over {plan.long_wait.weeks} weeks still waiting
            <span className="ml-auto text-xs font-normal text-muted">longest wait first</span>
          </summary>
          <div className="border-t border-line px-2 pb-2">
            <div className="flex px-2 pt-2 pb-1 text-xs text-muted">
              <span className="flex-1">Name</span>
              <span className="w-20 text-right">Waiting</span>
              <span className="w-16 text-right"><Term k="priority">Priority</Term></span>
            </div>
            <ol className="max-h-96 overflow-auto">
              {plan.unmet.map((p) => {
                const row = (
                  <>
                    <span className="min-w-0 flex-1 truncate font-semibold">{p.name}</span>
                    <span className="w-20 text-right"><Weeks weeks={p.weeks_waiting} limit={plan.long_wait.weeks} /></span>
                    <span className="w-16 text-right font-medium tabular-nums">{p.priority}</span>
                  </>
                )
                const cls = 'flex min-h-11 items-center gap-2 rounded-md px-2 text-sm'
                return (
                  <li key={p.id}>
                    {p.has_page
                      ? <Link to={`/patient/${p.id}`} className={`press hover:bg-sunken ${cls}`}>{row}</Link>
                      : <div className={cls} title={`${p.id} · no letter yet`}>{row}</div>}
                  </li>
                )
              })}
            </ol>
          </div>
        </details>
      )}

      {plan && (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {plan.lists.map((l) => (
              <Card key={l.kind} title={l.label} className="min-w-0"
                meta={<span className="ml-auto text-xs text-muted tabular-nums">{l.in.length}/{l.capacity} · {l.waiting} still waiting</span>}>
                {l.in.length === 0 ? <p className="py-4 text-sm text-muted">Nobody needs this slot</p> : (
                  <ol>{l.in.map((p, i) => <Row key={p.id} p={p} i={i} />)}</ol>
                )}
                {l.next.length > 0 && (
                  <>
                    <h3 className="mt-3 mb-1 px-2 text-xs font-medium text-muted">Next</h3>
                    <ol>{l.next.map((p, i) => <Row key={p.id} p={p} i={l.in.length + i} muted />)}</ol>
                  </>
                )}
              </Card>
            ))}
          </div>
          <p className="mt-4 text-xs text-muted">
            <Term k="optimiser">Optimiser</Term> (PuLP, CBC) · {plan.patients.toLocaleString()} on the waiting list · over {lw?.weeks} weeks
            first, then <Term k="priority">priority</Term>, ties to the longest wait
          </p>
        </>
      )}
    </>
  )
}
