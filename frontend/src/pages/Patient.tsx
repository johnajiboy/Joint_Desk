import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { bookThisWeek, confirmPathway, getClinician, getPatient, overridePathway, setClinician, unbookThisWeek } from '../api'
import { Card, ErrorNote, Loading, Meter } from '../components/AppShell'
import { primaryButton, secondaryButton } from '../components/ui'
import { BackIcon, CheckIcon } from '../components/icons'
import { annotate } from '../components/annotate'
import { PathwayChip } from '../components/PathwayChip'
import { Term } from '../components/Term'
import type { GlossaryKey } from '../glossary'
import { effectivePathway, PATHWAY_KEYS, PATHWAYS } from '../pathways'
import { ALLOWED } from '../planner'
import type { BookResult, FactValue, PathwayKey, Patient as PatientData, Span } from '../types'

const yesNo = (v: FactValue) => (v === true ? 'Yes' : v === false ? 'No' : null)

/** Facts in the order a triage clinician reads them. `field` links a row to its quote in the letter. */
const FACT_ROWS: { field: string; label: string; term?: GlossaryKey; show: (f: Record<string, FactValue>) => string | null; empty: string }[] = [
  { field: 'oks', label: 'Oxford Knee Score', term: 'oks', empty: 'No score in letter',
    show: (f) => (f.oks === null ? null : f.oks_before === null ? `${f.oks}` : `${f.oks} (was ${f.oks_before})`) },
  { field: 'kl', label: 'X-ray grade', term: 'kl', empty: 'No X-ray grade', show: (f) => (f.kl === null ? null : `KL ${f.kl}`) },
  { field: 'physio_weeks', label: 'Physio', empty: 'Not clear', show: (f) => (f.physio_weeks === null ? null : `${f.physio_weeks} weeks`) },
  { field: 'bmi', label: 'BMI', term: 'bmi', empty: 'Not in letter', show: (f) => (f.bmi === null ? null : `${f.bmi}`) },
  { field: 'injections', label: 'Injections', empty: 'Not in letter', show: (f) => (f.injections === null ? null : `${f.injections}`) },
  { field: 'night_pain', label: 'Night pain', empty: 'Not in letter', show: (f) => yesNo(f.night_pain) },
  { field: 'lives_alone_or_carer', label: 'Lives alone or carer', empty: 'Not in letter', show: (f) => yesNo(f.lives_alone_or_carer) },
  { field: 'walking_aid', label: 'Walking aid', empty: 'Not in letter', show: (f) => yesNo(f.walking_aid) },
  { field: 'diabetes', label: 'Diabetes', empty: 'Not in letter', show: (f) => yesNo(f.diabetes) },
  { field: 'smoking', label: 'Smoking', empty: 'Not in letter', show: (f) => (f.smoking as string | null) },
  { field: 'side', label: 'Knee', empty: 'Not in letter', show: (f) => (f.side as string | null) },
]

const PARTS: { key: string; label: string }[] = [
  { key: 'pain_function', label: 'Pain and function' },
  { key: 'xray', label: 'X-ray damage' },
  { key: 'decline', label: 'Recent decline' },
  { key: 'waiting', label: 'Time waiting' },
  { key: 'social', label: 'Night pain, social' },
]

const reduceMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches

// ---------------------------------------------------------------- letter with highlights

type Segment = { text: string; fields: string[]; order: number }

function segments(text: string, spans: Span[]): Segment[] {
  const cuts = [...new Set([0, text.length, ...spans.flatMap((s) => [s.start, s.end])])].sort((a, b) => a - b)
  const out: Segment[] = []
  for (let i = 0; i < cuts.length - 1; i++) {
    const [a, b] = [cuts[i], cuts[i + 1]]
    const covering = spans.filter((s) => s.start <= a && b <= s.end)
    out.push({ text: text.slice(a, b), fields: covering.map((s) => s.field), order: covering.length ? spans.indexOf(covering[0]) : -1 })
  }
  return out
}

function Letter({ p, active, onPick }: { p: PatientData; active: string | null; onPick: (f: string) => void }) {
  const segs = useMemo(() => segments(p.letter_text, p.spans), [p])
  return (
    <div className="rounded-lg border border-line bg-surface">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm">
        <span><span className="font-medium">Letter {p.letter_id}</span><span className="text-muted"> · {p.spans.length} quotes</span></span>
      </div>
      <div className="max-h-[75vh] overflow-auto px-4 py-4 text-[13.5px] leading-6 whitespace-pre-wrap break-words">
        {segs.map((s, i) =>
          s.fields.length ? (
            <mark key={i} data-fields={s.fields.join(' ')} onClick={() => onPick(s.fields[0])}
              title={s.fields.join(', ')}
              className={`hl ${active && s.fields.includes(active) ? 'hl-active' : ''}`}
              style={{ animationDelay: `${150 + Math.min(s.order, 20) * 35}ms` }}>
              {s.text}
            </mark>
          ) : (
            <span key={i}>{s.text}</span>
          ),
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- page

export default function Patient() {
  const { id = '' } = useParams()
  const [loaded, setLoaded] = useState<PatientData | null>(null)
  const p = loaded?.id === id ? loaded : null
  const setP = setLoaded
  const [error, setError] = useState(false)
  const [active, setActive] = useState<string | null>(null)
  const [why, setWhy] = useState(false)
  const [letterOpen, setLetterOpen] = useState(false)
  const [overriding, setOverriding] = useState(false)
  const [choice, setChoice] = useState<PathwayKey | null>(null)
  const [name, setName] = useState(getClinician)
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [booking, setBooking] = useState(false)
  const [bookReason, setBookReason] = useState('')
  const [pushed, setPushed] = useState<BookResult['pushed_out'] | null>(null)
  const [bookError, setBookError] = useState<string | null>(null)

  useEffect(() => {
    getPatient(id).then(setLoaded).catch(() => setError(true))
  }, [id])

  if (error) return <ErrorNote text="Patient not found" />
  if (!p) return <Loading />

  const current = effectivePathway(p)
  const f = p.facts

  function pick(field: string) {
    setActive(field)
    setLetterOpen(true)
    requestAnimationFrame(() =>
      document.querySelector(`mark[data-fields~="${field}"]`)?.scrollIntoView({
        block: 'center', behavior: reduceMotion() ? 'auto' : 'smooth' }))
  }

  async function decide(run: () => Promise<PatientData['decision']>) {
    setSaving(true)
    setClinician(name.trim())
    try {
      setP({ ...p!, decision: await run() })
      setOverriding(false)
      setReason('')
    } finally {
      setSaving(false)
    }
  }
  const confirm = () => decide(() => confirmPathway(p!.id, p!.pathway, current, name.trim()))

  async function book(confirmed = false) {
    setSaving(true)
    setBookError(null)
    setClinician(name.trim())
    try {
      const r = await bookThisWeek(p!.id, name.trim(), bookReason.trim(), confirmed)
      if (r.needs_confirm) {
        setPushed(r.pushed_out)
        return
      }
      setP({ ...p!, booking: r.booking })
      setBooking(false); setBookReason(''); setPushed(null)
    } catch (e) {
      setBookError(e instanceof Error ? e.message : "Couldn't book")
    } finally {
      setSaving(false)
    }
  }

  async function unbook() {
    setSaving(true)
    setBookError(null)
    try {
      await unbookThisWeek(p!.id, name.trim())
      setP({ ...p!, booking: null })
    } catch (e) {
      setBookError(e instanceof Error ? e.message : "Couldn't unbook")
    } finally {
      setSaving(false)
    }
  }
  const canBook = !!ALLOWED[current] && p.weeks_waiting !== null
  const saveOverride = () => choice && decide(() => overridePathway(p!.id, p!.pathway, choice, name.trim(), reason.trim()))

  const weeks = p.weeks_waiting ?? 0
  const scale = Math.max(78, weeks)

  return (
    <>
      <div className="fade-up mb-4 flex items-center gap-2">
        <Link to="/queue" className="press -ml-2 flex h-11 items-center gap-1 rounded-md px-2 text-sm text-muted hover:text-text">
          <BackIcon /> Referrals
        </Link>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:items-start">
        {/* facts and decision: first on tablet and phone, right on desktop */}
        <div className="space-y-4 lg:order-2">
          <Card>
            <div className="fade-up">
              <h1 className="text-xl font-semibold">{p.name}</h1>
              <p className="mt-0.5 text-sm text-muted">
                {[p.nhs_number, f.age !== null && `${f.age} yrs`, f.sex, f.side && `${f.side} knee`].filter(Boolean).join(' · ')}
              </p>
            </div>

            <div className="fade-up mt-4 flex flex-wrap items-center gap-2" style={{ animationDelay: '60ms' }}>
              <PathwayChip pathway={current} priority={p.priority} weight={p.weight_support} />
              {p.decision?.kind === 'confirmed' && (
                <span className="flex items-center gap-1 text-sm text-muted"><CheckIcon /> Confirmed{p.decision.by ? ` · ${p.decision.by}` : ''}</span>
              )}
              {p.decision?.kind === 'overridden' && (
                <span className="text-sm text-muted">
                  Overridden{p.decision.by ? ` by ${p.decision.by}` : ''} · rules said {PATHWAYS[p.decision.was].short}
                </span>
              )}
            </div>

            <div className="fade-up mt-3 flex items-start gap-3 text-sm" style={{ animationDelay: '120ms' }}>
              <p className="min-w-0 flex-1">{annotate(p.reasons.join(' · '))}</p>
              <button onClick={() => setWhy(!why)} aria-expanded={why}
                className="press -my-2 h-11 shrink-0 rounded-md px-2 text-sm text-primary dark:text-text">
                {why ? 'Hide' : 'Why'}
              </button>
            </div>
            {why && (
              <div className="fade-up mt-2 rounded-md bg-sunken p-3 text-sm">
                <div className="font-medium">Rule {p.rule} · {PATHWAYS[p.pathway].label}</div>
                <ul className="mt-1 list-disc pl-5 text-muted">
                  {p.reasons.map((r) => <li key={r}>{annotate(r)}</li>)}
                  {p.weight_support && <li>BMI 35 or more: weight support offered</li>}
                </ul>
                <p className="mt-2 text-xs text-muted">Rules decide, the LLM only reads, you confirm.</p>
              </div>
            )}

            {p.decision?.reason && <p className="mt-1 text-sm text-muted">“{p.decision.reason}”</p>}

            <label className="mt-4 flex items-center gap-2 text-sm">
              <span className="text-muted">Your name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="e.g. Dr A. Shah"
                className="h-11 min-w-0 flex-1 rounded-md border border-line bg-surface px-3 text-sm focus:border-primary focus:outline-none" />
            </label>
            <div className="mt-2 flex flex-wrap gap-2">
              <button className={primaryButton} onClick={confirm}
                disabled={saving || (p.decision?.kind === 'confirmed' && p.decision.pathway === current)}>
                {p.decision?.kind === 'confirmed' && p.decision.pathway === current ? <><CheckIcon /> Confirmed</> : 'Confirm'}
              </button>
              <button className={secondaryButton} onClick={() => { setOverriding(!overriding); setChoice(null) }}
                aria-expanded={overriding}>
                Override
              </button>
              {p.booking ? (
                <button className={secondaryButton} onClick={unbook} disabled={saving}>Unbook</button>
              ) : canBook && (
                <button className={secondaryButton} aria-expanded={booking}
                  onClick={() => { setBooking(!booking); setPushed(null); setBookError(null) }}>
                  Book this week
                </button>
              )}
            </div>
            {p.booking && (
              <p className="fade-up mt-2 text-sm text-muted">
                <span className="font-medium text-text">Booked this week</span>
                {p.booking.by ? ` · ${p.booking.by}` : ''}{p.booking.reason ? ` · “${p.booking.reason}”` : ''}
              </p>
            )}
            {bookError && <p className="mt-2 text-sm font-medium text-danger">{bookError}</p>}
            {booking && !p.booking && (
              <fieldset className="fade-up mt-3 rounded-md border border-line p-3">
                <legend className="px-1 text-xs text-muted">Book into this week · always gets a slot</legend>
                <input value={bookReason} onChange={(e) => { setBookReason(e.target.value); setPushed(null) }} maxLength={500}
                  placeholder="Reason (needed)" aria-label="Reason for booking"
                  className="h-11 w-full rounded-md border border-line bg-surface px-3 text-sm focus:border-primary focus:outline-none" />
                {pushed && (
                  <div className="fade-up mt-3 text-sm" role="alert">
                    <p className="font-medium text-danger">Pushes out {pushed.length} over 52 weeks</p>
                    <ul className="mt-1 text-muted">
                      {pushed.map((q) => <li key={q.id}>{q.name} · {q.weeks_waiting} wk</li>)}
                    </ul>
                  </div>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className={secondaryButton} disabled={!bookReason.trim() || saving} onClick={() => book(!!pushed)}>
                    {pushed ? 'Book anyway' : 'Save booking'}
                  </button>
                  <button className="press h-11 px-3 text-sm text-muted" onClick={() => { setBooking(false); setPushed(null) }}>Cancel</button>
                </div>
              </fieldset>
            )}
            {overriding && (
              <fieldset className="fade-up mt-3 rounded-md border border-line p-3">
                <legend className="px-1 text-xs text-muted">Change pathway to</legend>
                <div className="flex flex-wrap gap-2">
                  {PATHWAY_KEYS.filter((k) => k !== current).map((k) => (
                    <label key={k} className={`press flex min-h-11 cursor-pointer items-center gap-2 rounded-md border px-3 text-sm ${
                      choice === k ? 'border-primary' : 'border-line'}`}>
                      <input type="radio" name="override" className="sr-only" checked={choice === k} onChange={() => setChoice(k)} />
                      <PathwayChip pathway={k} />
                    </label>
                  ))}
                </div>
                <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} placeholder="Reason"
                  className="mt-3 h-11 w-full rounded-md border border-line bg-surface px-3 text-sm focus:border-primary focus:outline-none" />
                <div className="mt-3 flex gap-2">
                  <button className={secondaryButton} disabled={!choice || saving} onClick={saveOverride}>Save override</button>
                  <button className="press h-11 px-3 text-sm text-muted" onClick={() => setOverriding(false)}>Cancel</button>
                </div>
              </fieldset>
            )}
          </Card>

          <Card title="Facts" meta={<span className="text-xs text-muted">tap to see the words in the letter</span>}>
            <dl className="divide-y divide-line">
              {FACT_ROWS.map((row, i) => {
                const value = row.show(f)
                const quoted = value !== null && row.field in p.quotes
                return (
                  <div key={row.field} className="fade-up flex min-h-11 items-center gap-3 py-1.5 text-sm"
                    style={{ animationDelay: `${i * 25}ms` }}>
                    <dt className="w-36 shrink-0 text-muted">{row.term ? <Term k={row.term}>{row.label}</Term> : row.label}</dt>
                    <dd className={`min-w-0 flex-1 ${value === null ? 'text-muted' : 'font-medium'}`}>
                      {value === null ? row.empty : quoted ? (
                        <button onClick={() => pick(row.field)} title="Show in the letter"
                          className="press -my-2 min-h-11 text-left underline decoration-line decoration-dotted underline-offset-4 hover:decoration-muted">
                          <span className={active === row.field ? 'hl hl-active' : ''}>{value}</span>
                        </button>
                      ) : value}
                    </dd>
                  </div>
                )
              })}
              {f.xray_finding !== null && (
                <div className="py-2 text-sm">
                  <button onClick={() => pick('xray_finding')} className="w-full text-left">
                    <span className="block text-muted">X-ray report</span>
                    <span className="mt-0.5 block">{String(f.xray_finding)}</span>
                  </button>
                </div>
              )}
              {p.dropped.map((d) => (
                <div key={d.field} className="flex min-h-11 items-center gap-3 py-1.5 text-sm text-muted">
                  <span className="w-36 shrink-0">{d.field.replace(/_/g, ' ')}</span>
                  <span>Dropped · quote not in letter</span>
                </div>
              ))}
            </dl>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            <Card title={<Term k="priority">Priority</Term>} meta={<span className="ml-auto font-semibold tabular-nums">{p.priority}</span>}>
              <ul className="space-y-2.5">
                {PARTS.map((part, i) => (
                  <li key={part.key} className="text-sm">
                    <div className="mb-1 flex justify-between">
                      <span className="text-muted">{part.label}</span>
                      <span className="tabular-nums">{p.priority_parts[part.key]}<span className="text-muted">/{p.priority_max[part.key]}</span></span>
                    </div>
                    <Meter value={p.priority_parts[part.key]} max={p.priority_max[part.key]} delay={i * 80} />
                  </li>
                ))}
              </ul>
            </Card>

            <Card title={<Term k="waits">Waiting</Term>} meta={<span className={`ml-auto font-semibold tabular-nums ${weeks > 52 ? 'text-danger' : ''}`}>
              {p.weeks_waiting === null ? '—' : `${weeks} wk`}</span>}>
              <div className="relative pt-5 pb-6">
                <Meter value={weeks} max={scale} over={weeks > 52} />
                {[18, 52].map((m) => (
                  <div key={m} className="absolute top-3 bottom-4 border-l border-dashed border-muted" style={{ left: `${(m / scale) * 100}%` }}>
                    <span className="absolute top-full mt-1 -translate-x-1/2 text-xs text-muted">{m}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted">
                {p.weeks_waiting === null ? 'Not on the waiting list'
                  : weeks > 52 ? 'Over 52 weeks' : weeks > 18 ? 'Past the 18-week standard' : 'Within 18 weeks'}
              </p>
            </Card>
          </div>
        </div>

        {/* letter: left on desktop, behind a toggle on tablet and phone */}
        <div className="lg:order-1">
          <button onClick={() => setLetterOpen(!letterOpen)} aria-expanded={letterOpen}
            className={`${secondaryButton} mb-3 w-full lg:hidden`}>
            {letterOpen ? 'Hide letter' : 'Letter'}
          </button>
          <div className={`${letterOpen ? 'block' : 'hidden'} lg:block lg:sticky lg:top-20`}>
            {p.letter_text ? <Letter p={p} active={active} onPick={setActive} /> : (
              <div className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-muted">
                No letter · from the waiting list record
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
