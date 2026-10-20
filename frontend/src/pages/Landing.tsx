import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ThemeToggle } from '../components/ThemeToggle'
import {
  CalendarIcon,
  ChecklistIcon,
  LetterIcon,
  Logo,
  SparkleIcon,
  StethoscopeIcon,
} from '../components/icons'
import { useTheme } from '../theme'
import './Landing.css'

const CHIPS: { label: string; color: string; icon: ReactNode }[] = [
  { label: 'Letter', color: '#f6c445', icon: <LetterIcon /> },
  { label: 'LLM reads', color: '#a78bfa', icon: <SparkleIcon /> },
  { label: 'Rules', color: '#34d399', icon: <ChecklistIcon /> },
  { label: 'Clinician', color: '#f472b6', icon: <StethoscopeIcon /> },
  { label: 'Week plan', color: '#ef4444', icon: <CalendarIcon /> },
]

// Orbit radius as a share of the stage: the dashed ring (r170 of 500).
const ORBIT = 34

// Fixed positions so the sky is the same on every load: [left %, top %, delay s].
const STARS: [number, number, number][] = [
  [8, 14, 0.2], [21, 72, 1.6], [33, 9, 2.9], [46, 88, 0.9], [57, 22, 3.4], [69, 64, 1.1], [82, 11, 2.2],
  [92, 46, 0.5], [14, 41, 3.0], [27, 93, 1.9], [75, 84, 2.6], [88, 77, 0.1], [4, 63, 1.4], [62, 4, 3.8],
]

function formatClock(d: Date) {
  const h = d.getHours() % 12 || 12
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(d.getMinutes())}:${pad(d.getSeconds())} ${d.getHours() < 12 ? 'AM' : 'PM'}`
}

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="clock">
      <span className="clock-dot" aria-hidden="true" />
      <time dateTime={now.toISOString()}>{formatClock(now)}</time>
    </span>
  )
}

/** Mouse parallax: writes --px / --py (-1..1) on the page, at most once per frame. */
function useParallax() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const fine = matchMedia('(hover: hover) and (pointer: fine)').matches
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!fine || reduce) return

    let raf = 0
    let x = 0
    let y = 0
    const apply = () => {
      raf = 0
      el.style.setProperty('--px', x.toFixed(3))
      el.style.setProperty('--py', y.toFixed(3))
    }
    const queue = () => {
      if (!raf) raf = requestAnimationFrame(apply)
    }
    const onMove = (e: PointerEvent) => {
      x = (e.clientX / window.innerWidth) * 2 - 1
      y = (e.clientY / window.innerHeight) * 2 - 1
      queue()
    }
    const onLeave = () => {
      x = 0
      y = 0
      queue()
    }
    el.addEventListener('pointermove', onMove)
    el.addEventListener('pointerleave', onLeave)
    return () => {
      el.removeEventListener('pointermove', onMove)
      el.removeEventListener('pointerleave', onLeave)
      cancelAnimationFrame(raf)
    }
  }, [])
  return ref
}

function Knee() {
  return (
    <svg className="knee" viewBox="0 0 200 300" fill="none" aria-hidden="true">
      {/* femur */}
      <path
        className="bone"
        style={{ '--d': '0.2s', '--t': '0.45s' } as CSSProperties}
        pathLength={1}
        d="M80 0C80 40 78 70 74 95C68 112 52 118 52 134C52 146 62 150 74 148C84 147 92 142 100 142C108 142 116 147 126 148C138 150 148 146 148 134C148 118 132 112 126 95C122 70 120 40 120 0"
      />
      {/* quadriceps tendon */}
      <path
        className="bone tendon"
        style={{ '--d': '0.55s', '--t': '0.25s' } as CSSProperties}
        pathLength={1}
        d="M92 94C93 70 94 50 95 28M108 94C107 70 106 50 105 28"
      />
      {/* patella */}
      <ellipse
        className="bone"
        style={{ '--d': '0.75s', '--t': '0.3s' } as CSSProperties}
        pathLength={1}
        cx="100"
        cy="112"
        rx="15"
        ry="19"
      />
      {/* patellar tendon */}
      <path
        className="bone tendon"
        style={{ '--d': '1s', '--t': '0.25s' } as CSSProperties}
        pathLength={1}
        d="M94 130C95 150 96 168 96 186M106 130C105 150 104 168 104 186"
      />
      {/* tibia */}
      <path
        className="bone"
        style={{ '--d': '1.2s', '--t': '0.4s' } as CSSProperties}
        pathLength={1}
        d="M80 300C80 250 78 210 72 190C62 180 54 172 54 162C54 158 60 156 72 156C84 156 92 158 100 158C108 158 116 156 128 156C140 156 146 158 146 162C146 172 138 180 128 190C122 210 120 250 120 300"
      />
      {/* fibula */}
      <path
        className="bone"
        style={{ '--d': '1.55s', '--t': '0.45s' } as CSSProperties}
        pathLength={1}
        d="M140 300C140 260 141 225 141 202C136 197 136 185 144 181C152 177 160 183 158 191C156 197 150 199 149 205C148 230 148 265 148 300"
      />
      {/* joint space */}
      <path className="joint" d="M58 152C75 154 90 153 100 151C110 153 125 154 142 152" />
    </svg>
  )
}

export default function Landing() {
  const { theme, toggle } = useTheme('dark')
  const pageRef = useParallax()

  return (
    // Empty touch handler lets :active fire on iOS so chips glow on tap.
    <div className="landing" ref={pageRef} onTouchStart={() => {}}>
      <div className="px-stars" aria-hidden="true">
        {STARS.map(([left, top, delay], i) => (
          <span
            key={i}
            className="star"
            style={{ left: `${left}%`, top: `${top}%`, animationDelay: `${delay}s` }}
          />
        ))}
      </div>

      <header className="lp-header">
        <div className="lp-brand">
          <Logo />
          <span className="lp-wordmark">Joint Desk</span>
        </div>
        <div className="lp-header-right">
          <Clock />
          <ThemeToggle theme={theme} onToggle={toggle} className="lp-toggle" />
        </div>
      </header>

      <main className="lp-main">
        <div className="stage">
          <svg className="rings" viewBox="0 0 500 500" aria-hidden="true">
            <circle className="disc-fill" cx="250" cy="250" r="225" />
            <circle className="disc-hi" cx="250" cy="250" r="225" />
            <circle className="disc-edge" cx="250" cy="250" r="225" pathLength={1} transform="rotate(-90 250 250)" />
            <circle className="ring" cx="250" cy="250" r="170" />
          </svg>

          <div className="px-knee">
            <div className="glow" aria-hidden="true" />
            <Knee />
          </div>

          <div className="px-orbit">
            <div className="orbit">
              {CHIPS.map((chip, i) => {
                const a = ((-90 + i * 72) * Math.PI) / 180
                return (
                  <div
                    key={chip.label}
                    className="chip-slot"
                    style={{
                      left: `${50 + ORBIT * Math.cos(a)}%`,
                      top: `${50 + ORBIT * Math.sin(a)}%`,
                    }}
                  >
                    <div className="chip-counter">
                      <div
                        className="chip-pop"
                        style={{ '--c': chip.color, animationDelay: `${1.9 + i * 0.15}s` } as CSSProperties}
                      >
                        <div className="chip">{chip.icon}</div>
                        <span className="chip-label">{chip.label}</span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        <h1 className="lp-title">
          Joint <span>Desk</span>
        </h1>
        <p className="lp-tagline">Knee referrals, read and prioritised.</p>

        <div className="lp-cta">
          <Link to="/queue" className="start">
            <span className="mouse" aria-hidden="true">
              <span className="wheel" />
            </span>
            <span className="start-text">Start here</span>
          </Link>
        </div>
      </main>
    </div>
  )
}
