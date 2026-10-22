import { useRef, useState } from 'react'
import type { DragEvent, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { MAX_FILES, uploadLetter } from '../api'
import type { UploadResult } from '../types'
import { primaryButton, secondaryButton } from './ui'
import { PaperclipIcon } from './icons'
import { PathwayChip } from './PathwayChip'
import { effectivePathway } from '../pathways'

type Item = { key: string; name: string; result?: UploadResult }

/** The same file (name and size) is one chip, however often it is uploaded. */
const fileKey = (f: File) => `${f.name}|${f.size}`

const ACCEPT = '.pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export function UploadBar({ onRead }: { onRead?: (result: UploadResult) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [items, setItems] = useState<Item[]>([])
  const [over, setOver] = useState(false)
  const [tooMany, setTooMany] = useState(false)

  function pick(list: FileList | null) {
    if (!list?.length) return
    setTooMany(list.length > MAX_FILES)
    setFiles([...list].slice(0, MAX_FILES))
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    pick(e.dataTransfer.files)
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!files.length) return
    const unique = new Map(files.map((f) => [fileKey(f), f]))
    const batch = [...unique].map(([key, file]) => ({ key, name: file.name, file }))
    // a re-uploaded file replaces its old chip (back to "Reading…") rather than adding a second one
    setItems((prev) => [...batch.map(({ key, name }) => ({ key, name })), ...prev.filter((it) => !unique.has(it.key))].slice(0, 12))
    setFiles([])
    setTooMany(false)
    if (input.current) input.current.value = ''
    for (const b of batch) {
      uploadLetter(b.file).then((result) => {
        setItems((prev) => prev.map((it) => (it.key === b.key ? { ...it, result } : it)))
        onRead?.(result)
      })
    }
  }

  const label = files.length === 0 ? 'Choose referral letters or drop them here'
    : files.length === 1 ? files[0].name : `${files.length} letters chosen`

  return (
    <div className="fade-up mb-5 w-full max-w-[720px]">
      <form onSubmit={submit}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={`flex flex-wrap items-center gap-2 rounded-lg border bg-surface p-2 sm:flex-nowrap ${
          over ? 'border-primary' : 'border-line'}`}>
        <label className="flex min-h-11 min-w-0 basis-full cursor-pointer items-center gap-3 rounded-md px-2 sm:flex-1 sm:basis-auto">
          <span className="shrink-0 text-muted"><PaperclipIcon /></span>
          <span className={`truncate text-sm ${files.length ? 'text-text' : 'text-muted'}`}>{label}</span>
          <input ref={input} type="file" multiple accept={ACCEPT} className="sr-only"
            onChange={(e) => pick(e.target.files)} />
        </label>
        <button type="button" className={`${secondaryButton} flex-1 sm:flex-none`} onClick={() => input.current?.click()}>
          Browse
        </button>
        <button type="submit" className={`${primaryButton} flex-1 sm:flex-none`} disabled={!files.length}>
          Upload and read
        </button>
      </form>

      {tooMany && <p className="mt-2 text-sm text-muted">At most {MAX_FILES} files at once · first {MAX_FILES} chosen</p>}

      {items.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-live="polite">
          {items.map((it) => (
            <li key={it.key} className="fade-up flex h-9 max-w-full items-center gap-2 rounded-full border border-line bg-surface pr-1.5 pl-3 text-sm">
              <span className="max-w-40 truncate text-muted">{it.name}</span>
              {!it.result && (
                <>
                  <span className="text-muted">Reading…</span>
                  <span className="reading-bar" aria-hidden="true" />
                </>
              )}
              {it.result?.ok && (
                <Link to={`/patient/${it.result.referral.id}`} className="pop-in">
                  <PathwayChip pathway={effectivePathway(it.result.referral)} priority={it.result.referral.priority} />
                </Link>
              )}
              {it.result && !it.result.ok && <span className="pop-in chip chip-plain">{it.result.message}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
