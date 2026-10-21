import type { Referral } from './types'

/**
 * Does a referral match the search? Name, letter ID and file name by substring (case-insensitive); the NHS number
 * with or without spaces. `files` are names of files uploaded in this session for that patient.
 */
export function matches(r: Referral, query: string, files: string[] = []): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const text = [r.name, r.letter_id, r.filename, ...files].filter(Boolean).map((v) => String(v).toLowerCase())
  if (text.some((v) => v.includes(q))) return true
  const digits = q.replace(/[\s-]/g, '')
  return /^\d+$/.test(digits) && (r.nhs_number ?? '').replace(/\D/g, '').includes(digits)
}
