import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { buildWeek, getClinician, getLatestWeek } from '../api'
import { Card, ErrorNote, Loading, PageHeader } from '../components/AppShell'
import { PathwayChip, Weeks } from '../components/PathwayChip'
import { Term } from '../components/Term'
import { primaryButton, stagger } from '../components/ui'
import type { ReactNode } from 'react'
import type { UnmetPatient, WeekChange, WeekPatient, WeekPlan } from '../types'

const LABELS = { surgery: 'Surgery', physio: 'Physio', weight_support: 'Weight support' }

const builtAt = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

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

const SLOT_TEXT = { surgery: 'surgery', physio: 'physio', weight_support: 'weight support' }

function outcome(c: WeekChange): string {
  if (c.outcome === 'in' && c.slot) return `In a ${SLOT_TEXT[c.slot]} slot`
  if (c.outcome === 'next') return `Next in line · #${c.rank}`
  return 'No slot needed (non-surgical / needs info)'
}

function PersonLink({ p, className, children }: { p: { id: string; has_page: boolean }; className: string; children: ReactNode }) {
  return p.has_page
    ? <Link to={`/patient/${p.id}`} className={`press hover:bg-sunken ${className}`}>{children}</Link>
    : <div className={className} title={`${p.id} · no letter yet`}>{children}</div>
}

function Changes({ changes }: { changes: WeekChange[] }) {
  return (
    <Card title="Your changes this week" className="fade-up mb-5 min-w-0"
      meta={<span className="ml-auto text-xs text-muted tabular-nums">{changes.length}</span>}>
      {changes.length === 0 ? <p className="py-2 text-sm text-muted">No overrides or bookings</p> : (
        <ul className="-mx-2">
          {changes.map((c, i) => (
            <li key={c.id} className="fade-up" style={stagger(i)}>
              <PersonLink p={c} className="flex min-h-12 flex-wrap items-center gap-x-3 gap-y-1 rounded-md px-2 py-1.5 text-sm">
                <span className="min-w-0 flex-1 basis-40">
                  <span className="block truncate font-semibold">{c.name}</span>
                  <span className="block truncate text-xs text-muted">
                    {[c.overridden && 'Overridden', c.booked && 'Booked', c.by].filter(Boolean).join(' · ')}
                  </span>
                </span>
                <PathwayChip pathway={c.pathway} />
                <span className={`w-full text-sm sm:w-56 sm:text-right ${c.outcome === 'in' ? 'font-medium' : 'text-muted'}`}>{outcome(c)}</span>
              </PersonLink>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function PushedOut({ people }: { people: UnmetPatient[] }) {
  return (
    <div className="fade-up mb-5 rounded-lg border border-line bg-surface p-4 text-sm" role="alert">
      <div className="font-medium text-danger">Bookings push out {people.length} over 52 weeks</div>
      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
        {people.map((p) => (
          <li key={p.id}>
            <PersonLink p={p} className="-mx-1 inline-flex min-h-11 items-center rounded-md px-1">
              <span className="font-semibold">{p.name}</span><span className="ml-1 text-muted tabular-nums">· {p.weeks_waiting} wk</span>
            </PersonLink>
          </li>
        ))}
      </ul>
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
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // the latest saved plan, so a refresh (or a server restart) keeps it
  useEffect(() => {
    getLatestWeek().then(setPlan).catch(() => setPlan(null)).finally(() => setLoaded(true))
  }, [])

  async function build() {
    setBusy(true)
    setError(null)
    try {
      setPlan(await buildWeek(getClinician()))
    } catch (e) {
      // the API's own words for overbooking and solver failures; anything else (network, 5xx) in short
      setError(e instanceof Error && /^(No slot|Couldn't build)/.test(e.message) ? e.message : "Couldn't build the list")
    } finally {
      setBusy(false)
    }
  }

  const lw = plan?.long_wait

  return (
    <>
      <PageHeader title="This week"
        meta={plan && <>
          <span className="chip chip-plain">Week of {weekOf(plan.week_of)}</span>
          {plan.method === 'demo' && <span className="chip chip-plain">Demo plan</span>}
          {plan.built_at && (
            <span className="text-xs text-muted">Built {builtAt(plan.built_at)}{plan.built_by ? ` · ${plan.built_by}` : ''}</span>
          )}
        </>}
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

      {plan && plan.pushed_out?.length > 0 && <PushedOut people={plan.pushed_out} />}

      {plan?.status === 'infeasible' && (
        <div className="fade-up mb-5 rounded-lg border border-line bg-surface p-4 text-sm">
          <div className="font-medium text-danger">Over-52s don't all fit · {lw?.unmet} without a slot</div>
          <p className="mt-1 text-muted">
            {[...plan.shortfall, plan.locked > 0 && `${plan.locked} booked`].filter(Boolean).join(' · ')}.
            {' '}Every slot left after bookings goes to them; nobody over 52 weeks is skipped.
          </p>
        </div>
      )}

      {error && <ErrorNote text={error} />}
      {plan && <Changes changes={plan.changes ?? []} />}
      {!loaded && <Loading />}
      {loaded && !plan && !error && <ErrorNote text="Not built yet · click Build this week's list" />}

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
                    <span className="min-w-0 flex-1 truncate font-semibold">{p.name}
                      {p.pushed_out && <span className="ml-2 text-xs font-normal text-danger">pushed out by a booking</span>}</span>
                    <span className="w-20 text-right"><Weeks weeks={p.weeks_waiting} limit={plan.long_wait.weeks} /></span>
                    <span className="w-16 text-right font-medium tabular-nums">{p.priority}</span>
                  </>
                )
                return (
                  <li key={p.id}>
                    <PersonLink p={p} className="flex min-h-11 items-center gap-2 rounded-md px-2 text-sm">{row}</PersonLink>
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
            {plan.method === 'demo'
              ? <>Demo plan · rebuilt in this browser with your overrides and bookings, same rules as the <Term k="optimiser">optimiser</Term></>
              : <><Term k="optimiser">Optimiser</Term> (PuLP, HiGHS)</>}
            {' '}· {plan.patients.toLocaleString()} on the waiting list · bookings first, then over {lw?.weeks} weeks,
            then <Term k="priority">priority</Term>, ties to the longest wait
          </p>
        </>
      )}
    </>
  )
}
