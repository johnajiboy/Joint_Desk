import { useMemo, useRef } from 'react'
import type { RefObject } from 'react'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { GlossaryKey } from '../glossary'
import { Term } from './Term'
import { phase, useLoop } from './useLoop'

export type Row = { week: number } & Record<string, number>

export type Series = {
  key: string
  label: string              // legend and tooltip
  end: string                // end label prefix: "Joint Desk · 829"
  color: string              // a validated series colour (text never uses it)
  term?: GlossaryKey
}

const REDRAW_MS = 10000
const DOT_MS = 7000

type LabelPos = { x?: string | number; y?: string | number; index?: number }

/** Direct label just above the end of its line, right-aligned inside the chart (fits on a phone). */
function EndLabel({ x, y, index, last, text }: LabelPos & { last: number; text: string }) {
  if (index !== last || x === undefined || y === undefined) return <g />
  return <text className="end-label" x={Number(x)} y={Number(y)} dy={-9} textAnchor="end" fontSize={12} fill="var(--text)">{text}</text>
}

function ChartTooltip({ active, payload, label, series }: {
  active?: boolean; payload?: { dataKey?: unknown; value?: number }[]; label?: number; series: Series[]
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-text">Week {label}</div>
      {series.map((s) => (
        <div key={s.key} className="flex items-center gap-2 text-muted">
          <span className="inline-block size-2 rounded-full" style={{ background: s.color }} />
          <span className="flex-1">{s.label}</span>
          <span className="font-medium text-text tabular-nums">{payload.find((p) => p.dataKey === s.key)?.value}</span>
        </div>
      ))}
    </div>
  )
}

/**
 * A line chart that loops calmly: every 10 s the lines erase and redraw (stroke-dashoffset), a glowing dot travels
 * each line on a 7 s loop, end labels pulse softly, and the optional shaded gap fades in after the lines draw.
 * End labels and the gap label always show final values.
 */
export function LoopLineChart({ data, series, card, gap, ariaLabel }: {
  data: Row[]
  series: Series[]
  card: RefObject<HTMLElement | null>
  gap?: { low: string; high: string; label: string }
  ariaLabel: string
}) {
  const box = useRef<HTMLDivElement>(null)
  const dots = useRef<(HTMLSpanElement | null)[]>([])
  const last = data.length - 1
  const step = Math.max(1, Math.round(last / 5))
  const ticks = useMemo(() => data.filter((_, i) => i % step === 0 || i === last).map((r) => r.week), [data, step, last])

  useLoop(card, (ms) => {
    const root = box.current
    if (!root) return
    const still = ms === Infinity
    const t = ms % REDRAW_MS
    const draw = still ? 1 : phase(t, 0, 1400)
    const erase = still ? 0 : phase(t, REDRAW_MS - 600, 600)
    const rootBox = root.getBoundingClientRect()
    const svgBox = root.querySelector('svg')?.getBoundingClientRect()
    const off = svgBox ? { x: svgBox.left - rootBox.left, y: svgBox.top - rootBox.top } : { x: 0, y: 0 }
    root.querySelectorAll<SVGPathElement>('path.recharts-line-curve').forEach((path, i) => {
      const len = path.getTotalLength()
      path.style.strokeDasharray = `${len} ${len}`
      path.style.strokeDashoffset = `${len * (1 - draw) - len * erase}`
      const dot = dots.current[i]
      if (!dot) return
      if (still) { dot.style.opacity = '0'; return }
      const p = (ms % DOT_MS) / DOT_MS
      const pt = path.getPointAtLength(len * phase(p * DOT_MS, 0, DOT_MS))
      const edges = Math.min(1, 5 * Math.sin(Math.PI * p))                 // fades at the ends: no jump on restart
      const between = phase(t, 1500, 400) * (1 - phase(t, REDRAW_MS - 1100, 400))
      dot.style.transform = `translate(${off.x + pt.x}px, ${off.y + pt.y}px)`
      dot.style.opacity = `${edges * between}`
    })
    root.querySelectorAll<SVGPathElement>('.recharts-area-area').forEach((area) => {
      area.style.opacity = still ? '1' : `${phase(t, 1400, 700) * (1 - phase(t, REDRAW_MS - 700, 400))}`
    })
    root.querySelectorAll<SVGTextElement>('text.end-label').forEach((label) => {
      label.style.opacity = still ? '1' : `${0.85 + 0.15 * Math.cos((2 * Math.PI * ms) / 3000)}`
    })
  })

  const lastRow = data[last]
  return (
    <div>
      <ul className="mb-2 flex flex-wrap justify-end gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 rounded-full" style={{ background: s.color }} />
            {s.term ? <Term k={s.term}>{s.label}</Term> : s.label}
          </li>
        ))}
        {gap && (
          <li className="flex items-center gap-1.5">
            <span className="inline-block size-2.5 rounded-sm" style={{ background: 'var(--gap-fill)' }} />
            Gap
          </li>
        )}
      </ul>
      <div ref={box} className="relative h-64 w-full" role="img" aria-label={ariaLabel}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 24, right: 12, bottom: 4, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--line)" strokeOpacity={0.6} />
            <XAxis dataKey="week" ticks={ticks} tickLine={false} axisLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} width={48} allowDecimals={false} />
            <Tooltip cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }}
              content={(p) => <ChartTooltip {...(p as object)} series={series} />} />
            {gap && (
              <Area dataKey={(r: Row) => [r[gap.low], r[gap.high]]} stroke="none" fill="var(--gap-fill)"
                isAnimationActive={false} activeDot={false} legendType="none" tooltipType="none" />
            )}
            {series.map((s) => (
              <Line key={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={2}
                dot={false} activeDot={{ r: 4, stroke: 'var(--surface)', strokeWidth: 2 }} isAnimationActive={false}
                label={(props: LabelPos) => (
                  <EndLabel {...props} last={last} text={`${s.end} · ${Math.round(lastRow[s.key]).toLocaleString()}`} />
                )} />
            ))}
            {gap && (
              <ReferenceDot x={lastRow.week} y={(lastRow[gap.low] + lastRow[gap.high]) / 2} r={0} ifOverflow="visible"
                label={{ value: gap.label, position: 'left', fill: 'var(--text)', fontSize: 12, fontWeight: 600, offset: 8,
                  className: 'gap-label' }} />
            )}
          </ComposedChart>
        </ResponsiveContainer>
        {series.map((s, i) => (
          <span key={s.key} ref={(el) => { dots.current[i] = el }} aria-hidden="true"
            className="pointer-events-none absolute -top-[4px] -left-[4px] size-2 rounded-full opacity-0"
            style={{ background: s.color, boxShadow: `0 0 0 4px color-mix(in srgb, ${s.color} 22%, transparent), 0 0 10px ${s.color}` }} />
        ))}
      </div>
    </div>
  )
}
