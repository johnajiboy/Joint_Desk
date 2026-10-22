/**
 * All data access. With VITE_API_URL set, every function calls the FastAPI backend (backend/main.py), which
 * stores decisions in its database. Without it the app runs in demo mode: it reads the JSON exported by
 * scripts/export_demo.py from /demo/ and keeps decisions in this browser's localStorage. No API key ever
 * reaches the frontend.
 */
import { plan as planWeek } from './planner'
import type { Change, ListPatient } from './planner'
import type { Booking, BookResult, Decision, ImportPreview, ImportResult, PathwayKey, Patient, Referral, Results, SlotKind,
  UploadResult, WeekPlan } from './types'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '')
export const DEMO = !API_URL

async function request<T>(demoPath: string, apiPath: string, init?: RequestInit): Promise<T> {
  const url = DEMO ? `/demo/${demoPath}` : `${API_URL}${apiPath}`
  const res = await fetch(url, init)
  if (!res.ok) throw new Error(`${res.status} ${url}`)
  return res.json() as Promise<T>
}

// ------------------------------------------------------------------ decisions (demo: this browser only)

const DECISIONS_KEY = 'jd-decisions'

function readDecisions(): Record<string, Decision> {
  try {
    return JSON.parse(localStorage.getItem(DECISIONS_KEY) ?? '{}') as Record<string, Decision>
  } catch {
    return {}
  }
}

function writeDecision(id: string, d: Decision) {
  try {
    localStorage.setItem(DECISIONS_KEY, JSON.stringify({ ...readDecisions(), [id]: d }))
  } catch {
    // storage blocked: the decision lasts until the page reloads
  }
  memory[id] = d
}

const memory: Record<string, Decision> = {}

function decisionFor(id: string): Decision | undefined {
  return memory[id] ?? readDecisions()[id]
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>('', path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

/** POST that turns the API's error detail into the message ("No slot left · all booked"). */
async function postChecked<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const out = await res.json().catch(() => null)
  if (!res.ok) throw new Error(typeof out?.detail === 'string' ? out.detail : "Couldn't save")
  return out as T
}

// ------------------------------------------------------------------ bookings (demo: this browser only)

const BOOKINGS_KEY = 'jd-bookings'
const bookingMemory: Record<string, Booking | null> = {}

function readBookings(): Record<string, Booking> {
  let stored: Record<string, Booking> = {}
  try {
    stored = JSON.parse(localStorage.getItem(BOOKINGS_KEY) ?? '{}') as Record<string, Booking>
  } catch {
    // storage blocked: only this page session's bookings
  }
  const out = { ...stored }
  for (const [id, b] of Object.entries(bookingMemory)) {
    if (b) out[id] = b
    else delete out[id]
  }
  return out
}

function writeBooking(id: string, b: Booking | null) {
  bookingMemory[id] = b
  try {
    localStorage.setItem(BOOKINGS_KEY, JSON.stringify(readBookings()))
  } catch {
    // storage blocked: the booking lasts until the page reloads
  }
}

/** Who is deciding. No accounts yet: the name the clinician types, remembered in this browser. */
const NAME_KEY = 'jd-clinician'

export function getClinician(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setClinician(name: string) {
  try {
    localStorage.setItem(NAME_KEY, name)
  } catch {
    // storage blocked: the name is asked again next time
  }
}

/** Confirm the pathway that counts now. Backend: stored with who and when. Demo: this browser only. */
export async function confirmPathway(id: string, rulesPathway: PathwayKey, pathway: PathwayKey, by: string, reason?: string) {
  if (!DEMO) return post<Decision>(`/patients/${id}/confirm`, { by: by || 'clinician', reason: reason || null })
  const d: Decision = { kind: 'confirmed', pathway, was: rulesPathway, by, reason, at: new Date().toISOString() }
  writeDecision(id, d)
  return d
}

/** Change the pathway. Backend: stored with who, when, old and new pathway and the reason. */
export async function overridePathway(id: string, rulesPathway: PathwayKey, pathway: PathwayKey, by: string, reason?: string) {
  if (!DEMO) return post<Decision>(`/patients/${id}/override`, { pathway, by: by || 'clinician', reason: reason || null })
  const kind = pathway === rulesPathway ? 'confirmed' : 'overridden'
  const d: Decision = { kind, pathway, was: rulesPathway, by, reason, at: new Date().toISOString() }
  writeDecision(id, d)
  return d
}

// ------------------------------------------------------------------ reads

let demoQueue: Promise<Referral[]> | null = null

export async function getQueue(): Promise<Referral[]> {
  if (!DEMO) return request<Referral[]>('', '/queue')          // always fresh: uploads and decisions change it
  demoQueue ??= request<Referral[]>('queue.json', '')
  const queue = await demoQueue
  // patients from a demo spreadsheet import replace their old row or join the queue (this page session only)
  const imported = Object.values(demoImported.referrals)
  const merged = [...queue.filter((r) => !demoImported.referrals[r.id]), ...imported]
  return merged.map((r) => ({ ...r, decision: decisionFor(r.id) }))
}

export async function getPatient(id: string): Promise<Patient> {
  if (!/^[A-Za-z0-9_-]+$/.test(id)) throw new Error('Unknown patient')
  const local = () => ({ decision: decisionFor(id), booking: readBookings()[id] ?? null })
  if (DEMO && demoImported.patients[id]) return { ...demoImported.patients[id], ...local() }
  const p = await request<Patient>(`patients/${id}.json`, `/patients/${id}`)
  return DEMO ? { ...p, ...local() } : p
}

export function getResults(): Promise<Results> {
  return request<Results>('results.json', '/results')
}

interface WaitingList {
  week_of: string
  capacity: Record<SlotKind, number>
  long_wait: number
  columns: string[]
  rows: [string, string, PathwayKey, number, number, boolean][]
}

let demoList: Promise<WaitingList> | null = null

/** The demo week, re-planned in this browser: the waiting list with this browser's overrides, bookings and import. */
async function demoPlan(extraBooking?: { id: string } & Booking): Promise<WeekPlan> {
  demoList ??= request<WaitingList>('waiting_list.json', '')
  const list = await demoList
  const patients = new Map<string, ListPatient>(list.rows.map(([id, name, pathway, priority, weeks_waiting, has_page]) =>
    [id, { id, name, pathway, priority, weeks_waiting, has_page }]))
  for (const r of Object.values(demoImported.referrals)) {
    if (r.weeks_waiting !== null) patients.set(r.id, { id: r.id, name: r.name, pathway: r.pathway, priority: r.priority,
      weeks_waiting: r.weeks_waiting, has_page: true })
  }
  const changes: Record<string, Change> = {}
  for (const [id, d] of Object.entries({ ...readDecisions(), ...memory })) {
    const p = patients.get(id)
    if (!p) continue
    p.pathway = d.pathway                                     // the pathway that counts: the clinician's
    if (d.kind === 'overridden') changes[id] = { overridden: true, booked: false, was: d.was, by: d.by, at: d.at, reason: d.reason }
  }
  const bookings = { ...readBookings(), ...(extraBooking ? { [extraBooking.id]: extraBooking } : {}) }
  for (const [id, b] of Object.entries(bookings)) {
    if (!patients.has(id)) continue
    const c = changes[id] ?? { overridden: false, booked: false, was: null, at: b.at }
    changes[id] = { ...c, booked: true, by: b.by, at: c.at > b.at ? c.at : b.at, booking_reason: b.reason }
  }
  return planWeek([...patients.values()], changes, list.capacity, list.long_wait, list.week_of)
}

/** This week's slots. Backend: the optimiser on the database. Demo: re-planned in the browser (same rules). */
export function buildWeek(): Promise<WeekPlan> {
  return DEMO ? demoPlan() : postChecked<WeekPlan>('/week/build', {})
}

/**
 * Book a patient into this week: always in, counts against capacity. If that pushes anyone over 52 weeks out of a
 * slot, nothing is saved and the answer names them; call again with confirm to book anyway.
 */
export async function bookThisWeek(id: string, by: string, reason: string, confirm = false): Promise<BookResult> {
  if (!DEMO) return postChecked<BookResult>(`/patients/${id}/book`, { by: by || 'clinician', reason, confirm })
  const booking: Booking = { by: by || null, at: new Date().toISOString(), reason }
  const week = await demoPlan({ id, ...booking })             // throws NoSlotLeft when every slot is booked
  const pushed_out = week.pushed_out.map(({ id, name, weeks_waiting }) => ({ id, name, weeks_waiting }))
  if (pushed_out.length && !confirm) return { booked: false, needs_confirm: true, pushed_out, booking: null }
  writeBooking(id, booking)
  return { booked: true, needs_confirm: false, pushed_out, booking }
}

export async function unbookThisWeek(id: string, by: string): Promise<void> {
  if (!DEMO) {
    await postChecked(`/patients/${id}/unbook`, { by: by || 'clinician' })
    return
  }
  writeBooking(id, null)
}

// ------------------------------------------------------------------ passcode (live site: uploads and imports)

/** Uploads and imports can spend API credit, so on the live site they need a passcode: asked once, kept for this
 * browser session (sessionStorage), sent as X-Upload-Passcode. A wrong or changed one locks them again. */
const PASSCODE_KEY = 'jd-passcode'
let passcodeMemory = ''
export const LOCK_EVENT = 'jd-uploads-lock'

function storedPasscode(): string {
  try {
    return sessionStorage.getItem(PASSCODE_KEY) ?? passcodeMemory
  } catch {
    return passcodeMemory
  }
}

function keepPasscode(code: string) {
  passcodeMemory = code
  try {
    if (code) sessionStorage.setItem(PASSCODE_KEY, code)
    else sessionStorage.removeItem(PASSCODE_KEY)
  } catch {
    // storage blocked: kept in memory until the page reloads
  }
  window.dispatchEvent(new Event(LOCK_EVENT))
}

const passcodeHeader = (): Record<string, string> => (storedPasscode() ? { 'X-Upload-Passcode': storedPasscode() } : {})

export interface Health {
  ok: boolean
  demo_mode: boolean
  database: 'postgres' | 'sqlite'
  passcode: boolean
  llm_reads_today: number
  llm_daily_cap: number
}

let health: Promise<Health> | null = null

export function getHealth(): Promise<Health> {
  health ??= request<Health>('', '/health')
  return health
}

/** True when uploads need a passcode that this session doesn't have yet. */
export async function uploadsLocked(): Promise<boolean> {
  if (DEMO) return false
  const h = await getHealth().catch(() => null)
  return !!h?.passcode && !storedPasscode()
}

export async function unlockUploads(code: string): Promise<boolean> {
  const res = await fetch(`${API_URL}/passcode`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ passcode: code }) })
  if (res.ok) keepPasscode(code)
  return res.ok
}

// ------------------------------------------------------------------ upload

export const MAX_FILES = 5
export const MAX_FILE_MB = 2

async function textKey(text: string): Promise<string> {
  const data = new TextEncoder().encode(text.replace(/\s+/g, ' ').trim())
  const hash = await crypto.subtle.digest('SHA-256', data)
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * Read one letter. Demo mode has no LLM, so it recognises the demo letters by base name (L0001.txt, L0001.pdf,
 * T0042.docx all mean that letter) or, for text files, by their content, and shows the saved result.
 */
export async function uploadLetter(file: File): Promise<UploadResult> {
  if (file.size > MAX_FILE_MB * 1024 * 1024) return { file: file.name, ok: false, message: `File too large (max ${MAX_FILE_MB} MB)` }
  if (!DEMO) {
    const body = new FormData()
    body.append('files', file)
    try {
      const res = await fetch(`${API_URL}/letters`, { method: 'POST', body, headers: passcodeHeader() })
      if (res.status === 401) {
        keepPasscode('')
        return { file: file.name, ok: false, message: 'Passcode needed' }
      }
      if (!res.ok) throw new Error(String(res.status))
      const [result] = (await res.json()) as UploadResult[]
      return result
    } catch {
      return { file: file.name, ok: false, message: "Couldn't read file" }
    }
  }
  const started = Date.now()
  const queue = await getQueue()
  // the letter ID at the start of the name: L0001.txt, L0001.pdf, T0042.docx, "L0001 (1).pdf"
  const id = /^([LT]\d{4})(?!\d)/.exec(file.name.trim().toUpperCase())?.[1]
  let match = id ? queue.find((r) => r.letter_id === id) : undefined
  if (!match && (file.type.startsWith('text/') || /\.txt$/i.test(file.name))) {
    const key = await textKey(await file.text())
    match = queue.find((r) => r.text_key === key)
  }
  await wait(Math.max(0, 900 + Math.random() * 700 - (Date.now() - started)))  // let "Reading…" show
  return match
    ? { file: file.name, ok: true, referral: match }
    : { file: file.name, ok: false, message: "Couldn't read file · demo mode" }
}

export function uploadLetters(files: File[]): Promise<UploadResult[]> {
  return Promise.all(files.map(uploadLetter))
}

// ------------------------------------------------------------------ spreadsheet import

/** The demo site has no backend: only the sample spreadsheet works, with results precomputed by the backend code. */
export const DEMO_SAMPLE = 'import_sample.csv'

export class NeedsBackend extends Error {}

const demoImported: { referrals: Record<string, Referral>; patients: Record<string, Patient> } = { referrals: {}, patients: {} }
let demoSample: Promise<{ preview: ImportPreview; commit: ImportResult; patients: Record<string, Patient> }> | null = null

function sampleOnly(file: File) {
  if (file.name !== DEMO_SAMPLE) throw new NeedsBackend('Needs the backend · run locally')
  demoSample ??= request('import_sample.json', '')
  return demoSample
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: 'POST', body: form, headers: passcodeHeader() })
  if (res.status === 401) {
    keepPasscode('')
    throw new Error('Passcode needed')
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : "Couldn't read the spreadsheet")
  return body as T
}

/** Detected column mapping (or a given one), the first 10 rows, problems, and how many rows would import. */
export async function importPreview(file: File, mapping?: Record<string, string | null>): Promise<ImportPreview> {
  if (DEMO) return (await sampleOnly(file)).preview
  const form = new FormData()
  form.append('file', file)
  if (mapping) form.append('mapping', JSON.stringify(mapping))
  return postForm<ImportPreview>('/import/preview', form)
}

/** Import with the confirmed mapping. The backend records who imported what and when. */
export async function importCommit(file: File, mapping: Record<string, string | null>, by: string): Promise<ImportResult> {
  if (DEMO) {
    const sample = await sampleOnly(file)
    for (const r of sample.commit.referrals) demoImported.referrals[r.id] = r
    Object.assign(demoImported.patients, sample.patients)
    return sample.commit
  }
  const form = new FormData()
  form.append('file', file)
  form.append('mapping', JSON.stringify(mapping))
  form.append('by', by || 'clinician')
  return postForm<ImportResult>('/import/commit', form)
}
