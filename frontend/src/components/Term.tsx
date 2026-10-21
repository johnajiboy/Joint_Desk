import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { GLOSSARY } from '../glossary'
import type { GlossaryKey } from '../glossary'

/**
 * A term with a small "?" that shows its one-line meaning. Opens on mouse hover, keyboard focus or tap; closes on
 * leaving, Escape, or a tap elsewhere. The tooltip is linked to the "?" with aria-describedby.
 */
export function Term({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  const g = GLOSSARY[k]
  const [open, setOpen] = useState(false)
  const [shift, setShift] = useState(0)
  const id = useId()
  const root = useRef<HTMLSpanElement>(null)
  const tip = useRef<HTMLSpanElement>(null)

  // keep the tooltip on screen (phones): nudge it sideways if it would cross either edge
  useLayoutEffect(() => {
    if (!open || !tip.current) return
    const r = tip.current.getBoundingClientRect()
    const edge = 8
    const dx = r.left < edge ? edge - r.left : r.right > window.innerWidth - edge ? window.innerWidth - edge - r.right : 0
    if (dx) setShift((s) => s + dx)
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onDown = (e: PointerEvent) => !root.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open])

  function show(next: boolean) {
    if (!next) setShift(0)
    setOpen(next)
  }

  return (
    <span ref={root} className="term"
      onPointerEnter={(e) => e.pointerType === 'mouse' && show(true)}
      onPointerLeave={(e) => e.pointerType === 'mouse' && show(false)}>
      {children ?? g.term}
      <button type="button" className="term-q" aria-label={`What is ${g.term}?`} aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onFocus={(e) => e.currentTarget.matches(':focus-visible') && show(true)}
        onBlur={() => show(false)}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()                       // never trigger the row or card it sits in
          show(!open)
        }}>
        ?
      </button>
      {open && (
        <span ref={tip} id={id} role="tooltip" className="term-tip" style={{ translate: `calc(-50% + ${shift}px) 0` }}>
          {g.text}
        </span>
      )}
    </span>
  )
}
