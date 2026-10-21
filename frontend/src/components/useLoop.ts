import { useEffect, useRef } from 'react'
import type { RefObject } from 'react'

/**
 * A pausable animation clock for the Results charts. Calls `frame(ms)` every animation frame with the time the
 * loop has been running. Time stops while the pointer is over `card` and while the tab is hidden, so loops
 * resume where they left off. Under prefers-reduced-motion it calls `frame(Infinity)` once: draw the final state.
 * Frames should only set transform, opacity or stroke-dashoffset.
 */
export function useLoop(card: RefObject<HTMLElement | null>, frame: (ms: number) => void) {
  const latest = useRef(frame)
  useEffect(() => {
    latest.current = frame
  })

  useEffect(() => {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      latest.current(Infinity)
      return
    }
    const el = card.current
    let hovered = false
    let elapsed = 0
    let last = performance.now()
    let raf = 0
    const enter = (e: PointerEvent) => { if (e.pointerType === 'mouse') hovered = true }
    const leave = () => { hovered = false }
    el?.addEventListener('pointerenter', enter)
    el?.addEventListener('pointerleave', leave)

    const tick = (now: number) => {
      const dt = Math.min(now - last, 100)          // a long gap (tab switch) never jumps the loop
      last = now
      if (!hovered && document.visibilityState === 'visible') elapsed += dt
      latest.current(elapsed)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    const onVisible = () => { last = performance.now() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      cancelAnimationFrame(raf)
      el?.removeEventListener('pointerenter', enter)
      el?.removeEventListener('pointerleave', leave)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [card])
}

/** Smooth start and finish. */
export const easeInOut = (x: number) => {
  const t = Math.min(1, Math.max(0, x))
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2
}

/** 0 before `start`, eased 0 to 1 over `dur` ms, 1 after. */
export const phase = (ms: number, start: number, dur: number) => easeInOut((ms - start) / dur)

/** Count up once (tiles): returns a ref to the element whose text is updated, from 0 to `to` over `dur` ms. */
export function useCountUp(to: number, format: (n: number) => string, dur = 1000) {
  const ref = useRef<HTMLSpanElement>(null)
  const fmt = useRef(format)
  useEffect(() => {
    fmt.current = format
  })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
      el.textContent = fmt.current(to)
      return
    }
    const start = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / dur)
      el.textContent = fmt.current(to * (1 - (1 - p) ** 3))
      if (p < 1) raf = requestAnimationFrame(tick)
      else el.textContent = fmt.current(to)                // always end exactly on the final value
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [to, dur])
  return ref
}
