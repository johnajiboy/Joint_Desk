/**
 * All data access. With VITE_API_URL set, every function calls the FastAPI backend (backend/main.py), which
 * stores decisions in its database. Without it the app runs in demo mode: it reads the JSON exported by
 * scripts/export_demo.py from /demo/ and keeps decisions in this browser's localStorage. No API key ever
 * reaches the frontend.
 */
import type { Decision, ImportPreview, ImportResult, PathwayKey, Patient, Referral, Results, UploadResult, WeekPlan } from './types'

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
  if (DEMO && demoImported.patients[id]) return { ...demoImported.patients[id], decision: decisionFor(id) }
  const p = await request<Patient>(`patients/${id}.json`, `/patients/${id}`)
  return DEMO ? { ...p, decision: decisionFor(id) } : p
}

export function getResults(): Promise<Results> {
  return request<Results>('results.json', '/results')
}

/** This week's slots from the optimiser. Demo: the plan exported from the cleaned waiting list. */
export function buildWeek(): Promise<WeekPlan> {
  return request<WeekPlan>('week.json', '/week/build', DEMO ? undefined : { method: 'POST' })
}

// ------------------------------------------------------------------ upload

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
  if (!DEMO) {
    const body = new FormData()
    body.append('files', file)
    try {
      const [result] = await request<UploadResult[]>('', '/letters', { method: 'POST', body })
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
  const res = await fetch(`${API_URL}${path}`, { method: 'POST', body: form })
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
