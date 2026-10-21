import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { OptimiseResults, Policy } from '../types'
import { Term } from './Term'

/** Optimiser = series 1, Priority only = series 2 (validated palette; text stays in text colours). */
const SERIES: { policy: Policy; key: string; color: string; term: 'optimiser' | 'priority_only' }[] = [
  { policy: 'Optimiser', key: 'opt', color: 'var(--series-1)', term: 'optimiser' },
  { policy: 'Priority only', key: 'pri', color: 'var(--series-2)', term: 'priority_only' },
]

const reduceMotion = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

type Row = { week: number; opt: number; pri: number }
type LabelPos = { x?: string | number; y?: string | number; index?: number }

function EndLabel({ x, y, index, last, text }: LabelPos & { last: number; text: string }) {
  if (index !== last || x === undefined || y === undefined) return <g />
  return <text x={Number(x) + 8} y={Number(y)} dy={4} fontSize={12} fill="var(--text)">{text}</text>
}

function ChartTooltip({ active, payload, label }: {
  active?: boolean; payload?: { dataKey?: string | number; value?: number }[]; label?: number
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-text">Week {label}</div>
      {SERIES.map((s) => (
        <div key={s.key} className="flex items-center gap-2 text-muted">
          <span className="inline-block size-2 rounded-full" style={{ background: s.color }} />
          <span className="flex-1">{s.policy}</span>
          <span className="font-medium text-text tabular-nums">{payload.find((p) => p.dataKey === s.key)?.value}</span>
        </div>
      ))}
    </div>
  )
}

export function LongWaitChart({ o }: { o: OptimiseResults }) {
  const data = useMemo<Row[]>(() => o.series.Optimiser.map((r, i) => ({
    week: r.week, opt: r.over_52, pri: o.series['Priority only'][i].over_52,
  })), [o])
  const last = data.length - 1
  const step = Math.max(1, Math.round(last / 5))
  const ticks = data.filter((_, i) => i % step === 0 || i === last).map((r) => r.week)
  const animate = !reduceMotion()

  return (
    <div>
      <ul className="mb-2 flex flex-wrap justify-end gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
        {SERIES.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 rounded-full" style={{ background: s.color }} />
            <Term k={s.term}>{s.policy}</Term>
          </li>
        ))}
      </ul>
      <div className="h-64 w-full" role="img"
        aria-label={`Patients waiting over ${o.thresholds.long_wait_weeks} weeks, by week: ` +
          SERIES.map((s) => `${s.policy} ends at ${data[last][s.key as 'opt' | 'pri']}`).join(', ')}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 112, bottom: 4, left: -12 }}>
            <CartesianGrid vertical={false} stroke="var(--line)" strokeOpacity={0.6} />
            <XAxis dataKey="week" ticks={ticks} tickLine={false} axisLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} width={44} allowDecimals={false} />
            <Tooltip cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }} content={(p) => <ChartTooltip {...(p as object)} />} />
            {SERIES.map((s) => (
              <Line key={s.key} type="monotone" dataKey={s.key} name={s.policy} stroke={s.color} strokeWidth={2}
                dot={false} activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }}
                isAnimationActive={animate} animationDuration={1200}
                label={(props: LabelPos) => (
                  <EndLabel {...props} last={last} text={`${s.policy} · ${data[last][s.key as 'opt' | 'pri']}`} />
                )} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
