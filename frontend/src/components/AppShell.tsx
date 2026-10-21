import type { ReactNode } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { DEMO } from '../api'
import { useTheme } from '../theme'
import { InboxIcon, Logo, ResultsIcon, WeekIcon } from './icons'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/queue', label: 'Referrals', icon: <InboxIcon /> },
  { to: '/week', label: 'This week', icon: <WeekIcon /> },
  { to: '/results', label: 'Results', icon: <ResultsIcon /> },
]

/** Header nav on every screen; on phones the nav moves to a bottom tab bar. */
export function AppShell() {
  const { theme, toggle } = useTheme()

  return (
    <div className="min-h-svh bg-bg text-text">
      <header className="sticky top-0 z-20 border-b border-line bg-surface">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-4 sm:gap-4 sm:px-6">
          <Link to="/" className="press flex min-h-11 shrink-0 items-center gap-2 font-semibold text-primary dark:text-text"
            aria-label="Joint Desk home">
            <Logo size={26} />
            <span>Joint Desk</span>
          </Link>
          <nav className="ml-2 hidden items-center gap-1 sm:flex" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} title={n.label}
                className={({ isActive }) =>
                  `press flex h-11 min-w-11 items-center justify-center gap-2 rounded-md px-3 text-sm ${
                    isActive ? 'bg-sunken font-medium text-text' : 'text-muted hover:text-text'}`}>
                {n.icon}
                <span className="hidden lg:inline">{n.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <span className="chip chip-plain hidden md:inline-flex">{DEMO ? 'Demo data' : 'Live'}</span>
            <ThemeToggle theme={theme} onToggle={toggle}
              className="press inline-flex h-11 min-w-11 items-center justify-center gap-2 rounded-md border border-line px-3 text-sm hover:border-primary [&_.toggle-label]:hidden lg:[&_.toggle-label]:inline" />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 pt-5 pb-24 sm:px-6 sm:pt-6 sm:pb-10">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-3 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] sm:hidden"
        aria-label="Main">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to}
            className={({ isActive }) =>
              `press flex h-14 flex-col items-center justify-center gap-0.5 text-[11px] ${isActive ? 'font-medium text-text' : 'text-muted'}`}>
            {n.icon}
            {n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

export function PageHeader({ title, meta, action }: { title: string; meta?: ReactNode; action?: ReactNode }) {
  return (
    <div className="fade-up mb-5 flex flex-wrap items-center gap-x-3 gap-y-3">
      <h1 className="text-xl font-semibold sm:text-2xl">{title}</h1>
      {meta}
      {action && <div className="ml-auto">{action}</div>}
    </div>
  )
}

export function Card({ title, meta, children, className = '' }: { title?: ReactNode; meta?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-lg border border-line bg-surface p-4 sm:p-5 ${className}`}>
      {title && (
        <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1">
          <h2 className="text-sm font-semibold">{title}</h2>
          {meta}
        </div>
      )}
      {children}
    </section>
  )
}

export function Meter({ value, max, over = false, delay = 0 }: { value: number; max: number; over?: boolean; delay?: number }) {
  const share = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0
  return (
    <div className="meter" role="meter" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
      <span className={over ? 'over' : ''} style={{ transform: `scaleX(${share})`, animationDelay: `${delay}ms` }} />
    </div>
  )
}

export function Loading() {
  return <div className="py-16 text-center text-sm text-muted">Loading…</div>
}

export function ErrorNote({ text }: { text: string }) {
  return <div className="py-16 text-center text-sm text-muted">{text}</div>
}
