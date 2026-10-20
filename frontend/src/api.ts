/**
 * All data access. Without VITE_API_URL the app runs in demo mode: it reads the JSON exported by
 * scripts/export_demo.py from /demo/ and keeps the clinician's decisions in localStorage. With VITE_API_URL set,
 * the same functions call the FastAPI backend (stage 6). Nothing here ever holds an API key.
 */
import type { Decision, PathwayKey, Patient, Referral, Results, UploadResult, WeekPlan } from './types'

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

async function saveDecision(id: string, d: Decision): Promise<Decision> {
  if (DEMO) {
    writeDecision(id, d)
    return d
  }
  return request<Decision>('', `/patients/${id}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(d),
  })
}

export function confirmPathway(id: string, rulesPathway: PathwayKey, pathway: PathwayKey) {
  return saveDecision(id, { kind: 'confirmed', pathway, was: rulesPathway, at: new Date().toISOString() })
}

export function overridePathway(id: string, rulesPathway: PathwayKey, pathway: PathwayKey) {
  const kind = pathway === rulesPathway ? 'confirmed' : 'overridden'
  return saveDecision(id, { kind, pathway, was: rulesPathway, at: new Date().toISOString() })
}

// ------------------------------------------------------------------ reads

let queueRequest: Promise<Referral[]> | null = null

export async function getQueue(): Promise<Referral[]> {
  queueRequest ??= request<Referral[]>('queue.json', '/queue')
  const queue = await queueRequest
  return DEMO ? queue.map((r) => ({ ...r, decision: decisionFor(r.id) })) : queue
}

export async function getPatient(id: string): Promise<Patient> {
  if (!/^[A-Za-z0-9_-]+$/.test(id)) throw new Error('Unknown patient')
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
 * Read one letter. Demo mode has no LLM, so it recognises the demo letters by file name (L0001.txt, T0042.pdf)
 * or, for text files, by their content, and shows the saved result.
 */
export async function uploadLetter(file: File): Promise<UploadResult> {
  if (!DEMO) {
    const body = new FormData()
    body.append('file', file)
    try {
      const referral = await request<Referral>('', '/letters', { method: 'POST', body })
      return { file: file.name, ok: true, referral }
    } catch {
      return { file: file.name, ok: false, message: "Couldn't read file" }
    }
  }
  const started = Date.now()
  const queue = await getQueue()
  const stem = file.name.replace(/\.[^.]+$/, '').trim().toUpperCase()
  let match = queue.find((r) => r.letter_id === stem)
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
