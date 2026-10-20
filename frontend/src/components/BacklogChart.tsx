import { useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { OptimiseResults, Policy } from '../types'

/** Two series, colours from validated categorical slots 1-2 (CSS --series-1/2, light and dark). */
const SERIES: { policy: Policy; key: string; label: string; color: string; dash?: string }[] = [
  { policy: 'Optimiser', key: 'opt', label: 'Optimiser', color: 'var(--series-1)' },
  { policy: 'FCFS', key: 'fcfs', label: 'First come, first served', color: 'var(--series-2)', dash: '6 4' },
]

type Row = { week: number } & Record<string, number>

const reduceMotion = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      {SERIES.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <svg width="18" height="4" aria-hidden="true"><line x1="1" y1="2" x2="17" y2="2" stroke={s.color} strokeWidth="2"
            strokeDasharray={s.dash} strokeLinecap="round" /></svg>
          {s.label}
        </li>
      ))}
    </ul>
  )
}

function ChartTooltip({ active, payload, label, metric }: {
  active?: boolean; payload?: { dataKey?: string | number; value?: number }[]; label?: number; metric: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-text">Week {label}</div>
      {SERIES.map((s) => {
        const v = payload.find((p) => p.dataKey === `${s.key}_${metric}`)?.value
        return (
          <div key={s.key} className="flex items-center gap-2 text-muted">
            <span className="inline-block size-2 rounded-full" style={{ background: s.color }} />
            <span className="flex-1">{s.policy}</span>
            <span className="font-medium text-text tabular-nums">{v}</span>
          </div>
        )
      })}
    </div>
  )
}

type LabelPos = { x?: string | number; y?: string | number; index?: number }

/** Direct label at the end of a line (text in a text token, not the series colour). */
function EndLabel({ x, y, index, last, text }: LabelPos & { last: number; text: string }) {
  if (index !== last || x === undefined || y === undefined) return <g />
  return <text x={Number(x) + 6} y={Number(y)} dy={4} fontSize={11} fill="var(--muted)">{text}</text>
}

function Chart({ data, metric, title }: { data: Row[]; metric: '18' | '52'; title: string }) {
  const animate = !reduceMotion()
  const last = data.length - 1
  return (
    <figure className="min-w-0">
      <figcaption className="mb-2 text-sm font-medium">{title}</figcaption>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 72, bottom: 4, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--line)" />
            <XAxis dataKey="week" tickLine={false} axisLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }}
              ticks={[1, 6, 11, 16, 21, 26]} />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} width={44}
              allowDecimals={false} />
            <Tooltip cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }}
              content={(p) => <ChartTooltip {...(p as object)} metric={metric} />} />
            {SERIES.map((s) => (
              <Line key={s.key} type="monotone" dataKey={`${s.key}_${metric}`} name={s.label} stroke={s.color}
                strokeWidth={2} strokeDasharray={s.dash} dot={false} activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }}
                isAnimationActive={animate} animationDuration={900}
                label={(props: LabelPos) => (
                  <EndLabel {...props} last={last} text={s.policy === 'FCFS' ? 'FCFS' : 'Optimiser'} />
                )} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

export function BacklogChart({ o }: { o: OptimiseResults }) {
  const [table, setTable] = useState(false)
  const data = useMemo<Row[]>(() => o.series.Optimiser.map((r, i) => ({
    week: r.week,
    opt_18: r.over_18, opt_52: r.over_52,
    fcfs_18: o.series.FCFS[i].over_18, fcfs_52: o.series.FCFS[i].over_52,
  })), [o])

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <Legend />
        <button onClick={() => setTable(!table)} aria-expanded={table}
          className="press ml-auto h-11 rounded-md px-2 text-sm text-primary dark:text-text">
          {table ? 'Chart' : 'Table'}
        </button>
      </div>
      {table ? (
        <div className="max-h-72 overflow-auto">
          <table className="w-full text-sm tabular-nums">
            <thead className="sticky top-0 bg-surface text-left text-xs text-muted">
              <tr><th className="py-1 font-medium">Week</th><th className="py-1 text-right font-medium">Over 18 · optimiser</th>
                <th className="py-1 text-right font-medium">Over 18 · FCFS</th><th className="py-1 text-right font-medium">Over 52 · optimiser</th>
                <th className="py-1 text-right font-medium">Over 52 · FCFS</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.map((r) => (
                <tr key={r.week}><td className="py-1">{r.week}</td><td className="py-1 text-right">{r.opt_18}</td>
                  <td className="py-1 text-right">{r.fcfs_18}</td><td className="py-1 text-right">{r.opt_52}</td>
                  <td className="py-1 text-right">{r.fcfs_52}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <Chart data={data} metric="18" title="Waiting over 18 weeks" />
          <Chart data={data} metric="52" title="Waiting over 52 weeks" />
        </div>
      )}
    </div>
  )
}
