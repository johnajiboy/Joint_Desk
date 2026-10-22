import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { LOCK_EVENT, unlockUploads, uploadsLocked } from '../api'
import { LockIcon } from './icons'
import { primaryButton, secondaryButton } from './ui'

/**
 * Live site: uploads and imports need the passcode. Until this session has it, show a passcode field in place of
 * the children; once unlocked (here or in another gate) the children come back. Demo site: always open.
 */
export function PasscodeGate({ children, primary = true }: { children: ReactNode; primary?: boolean }) {
  const [locked, setLocked] = useState<boolean | null>(null)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [wrong, setWrong] = useState(false)

  useEffect(() => {
    const check = () => { uploadsLocked().then(setLocked) }
    check()
    window.addEventListener(LOCK_EVENT, check)
    return () => window.removeEventListener(LOCK_EVENT, check)
  }, [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!code) return
    setBusy(true)
    setWrong(false)
    try {
      const ok = await unlockUploads(code)
      setWrong(!ok)
      if (ok) setCode('')
    } catch {
      setWrong(true)
    } finally {
      setBusy(false)
    }
  }

  if (locked === null) return null
  if (!locked) return <>{children}</>
  return (
    <div className="fade-up mb-5 w-full max-w-[720px]">
      <form onSubmit={submit} className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-surface p-2 sm:flex-nowrap">
        <label className="flex min-h-11 min-w-0 basis-full items-center gap-3 rounded-md px-2 sm:flex-1 sm:basis-auto">
          <span className="shrink-0 text-muted"><LockIcon /></span>
          <span className="sr-only">Passcode for uploads</span>
          <input type="password" value={code} onChange={(e) => { setCode(e.target.value); setWrong(false) }}
            autoComplete="off" maxLength={200} placeholder="Passcode for uploads"
            className="h-11 min-w-0 flex-1 bg-transparent text-sm placeholder:text-muted focus:outline-none" />
        </label>
        <button type="submit" className={`${primary ? primaryButton : secondaryButton} flex-1 sm:flex-none`} disabled={!code || busy}>
          {busy ? 'Checking…' : 'Unlock'}
        </button>
      </form>
      {wrong && <p className="mt-2 text-sm font-medium text-danger">Wrong passcode</p>}
    </div>
  )
}
