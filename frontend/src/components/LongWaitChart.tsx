import { useMemo, useRef } from 'react'
import type { RefObject } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { OptimiseResults, Policy } from '../types'
import { Term } from './Term'
import { phase, useLoop } from './useLoop'

/** Optimiser = series 1, Priority only = series 2 (validated palette; text stays in text colours). */
const SERIES: { policy: Policy; key: string; color: string; term: 'optimiser' | 'priority_only' }[] = [
  { policy: 'Optimiser', key: 'opt', color: 'var(--series-1)', term: 'optimiser' },
  { policy: 'Priority only', key: 'pri', color: 'var(--series-2)', term: 'priority_only' },
]

type Row = { week: number; opt: number; pri: number }
type LabelPos = { x?: string | number; y?: string | number; index?: number }

function EndLabel({ x, y, index, last, text }: LabelPos & { last: number; text: string }) {
  if (index !== last || x === undefined || y === undefined) return <g />
  return <text className="end-label" x={Number(x) + 8} y={Number(y)} dy={4} fontSize={12} fill="var(--text)">{text}</text>
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

const REDRAW_MS = 10000
const DOT_MS = 6000

/**
 * Every 10 s both lines erase and redraw (stroke-dashoffset). Between redraws a glowing dot in each series colour
 * travels along its line on a 6 s loop, and the end labels pulse softly. The labels always show the final value.
 */
function useChartLoop(card: RefObject<HTMLElement | null>, box: RefObject<HTMLDivElement | null>,
  dots: RefObject<(HTMLSpanElement | null)[]>) {
  useLoop(card, (ms) => {
    const root = box.current
    if (!root) return
    const paths = root.querySelectorAll<SVGPathElement>('path.recharts-line-curve')
    const labels = root.querySelectorAll<SVGTextElement>('text.end-label')
    const still = ms === Infinity
    const t = ms % REDRAW_MS
    const draw = still ? 1 : phase(t, 0, 1400)
    const erase = still ? 0 : phase(t, REDRAW_MS - 600, 600)
    const svg = root.querySelector('svg')
    const off = svg ? { x: svg.getBoundingClientRect().left - root.getBoundingClientRect().left,
      y: svg.getBoundingClientRect().top - root.getBoundingClientRect().top } : { x: 0, y: 0 }
    paths.forEach((path, i) => {
      const len = path.getTotalLength()
      path.style.strokeDasharray = `${len} ${len}`
      path.style.strokeDashoffset = `${len * (1 - draw) - len * erase}`        // draws in, then erases from the start
      const dot = dots.current?.[i]
      if (!dot) return
      if (still) { dot.style.opacity = '0'; return }
      const p = (ms % DOT_MS) / DOT_MS
      const travel = phase(p * DOT_MS, 0, DOT_MS)                             // slow at both ends of the line
      const edges = Math.min(1, 5 * Math.sin(Math.PI * p))                     // fades at the ends: no jump on restart
      const between = phase(t, 1500, 400) * (1 - phase(t, REDRAW_MS - 1100, 400))
      const pt = path.getPointAtLength(len * travel)
      dot.style.transform = `translate(${off.x + pt.x}px, ${off.y + pt.y}px)`
      dot.style.opacity = `${edges * between}`
    })
    labels.forEach((label) => {
      label.style.opacity = still ? '1' : `${0.85 + 0.15 * Math.cos((2 * Math.PI * ms) / 3000)}`   // 0.7 to 1
    })
  })
}

export function LongWaitChart({ o, card }: { o: OptimiseResults; card: RefObject<HTMLElement | null> }) {
  const box = useRef<HTMLDivElement>(null)
  const dots = useRef<(HTMLSpanElement | null)[]>([])
  useChartLoop(card, box, dots)
  const data = useMemo<Row[]>(() => o.series.Optimiser.map((r, i) => ({
    week: r.week, opt: r.over_52, pri: o.series['Priority only'][i].over_52,
  })), [o])
  const last = data.length - 1
  const step = Math.max(1, Math.round(last / 5))
  const ticks = data.filter((_, i) => i % step === 0 || i === last).map((r) => r.week)

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
      <div ref={box} className="relative h-64 w-full" role="img"
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
                isAnimationActive={false}
                label={(props: LabelPos) => (
                  <EndLabel {...props} last={last} text={`${s.policy} · ${data[last][s.key as 'opt' | 'pri']}`} />
                )} />
            ))}
          </LineChart>
        </ResponsiveContainer>
        {SERIES.map((s, i) => (
          <span key={s.key} ref={(el) => { dots.current[i] = el }} aria-hidden="true"
            className="pointer-events-none absolute -top-[4px] -left-[4px] size-2 rounded-full opacity-0"
            style={{ background: s.color, boxShadow: `0 0 0 4px color-mix(in srgb, ${s.color} 22%, transparent), 0 0 10px ${s.color}` }} />
        ))}
      </div>
    </div>
  )
}
