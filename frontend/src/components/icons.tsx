import type React from 'react'

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="1" y="1" width="30" height="30" rx="9" stroke="var(--logo-frame, currentColor)" strokeWidth="1.5" />
      <path d="M12 5v8.5c-2.2.6-2.4 4 .3 4h7.4c2.7 0 2.5-3.4.3-4V5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M10 20h12" stroke="var(--logo-joint, currentColor)" strokeWidth="1.8" />
      <path d="M10.5 23h11M13 23v5M19 23v5" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

export function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4" />
    </svg>
  )
}

export function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
    </svg>
  )
}

/* Landing orbit chips */

export function LetterIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4.5 3.5h15a1 1 0 0 1 1 1V15l-5.5 5.5H4.5a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1z" fill="#f6c445" />
      <path d="M20.5 15H16a1 1 0 0 0-1 1v4.5z" fill="#c9971f" />
      <path d="M7 8h10M7 11.5h10M7 15h5" stroke="#7a5a0e" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

export function SparkleIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10 2.5l1.9 5.6 5.6 1.9-5.6 1.9L10 17.5l-1.9-5.6L2.5 10l5.6-1.9z" fill="#a78bfa" />
      <path d="M18 14l.95 2.55L21.5 17.5l-2.55.95L18 21l-.95-2.55-2.55-.95 2.55-.95z" fill="#22d3ee" />
    </svg>
  )
}

export function ChecklistIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3.5" y="2.5" width="17" height="19" rx="2.5" stroke="#34d399" strokeWidth="1.6" />
      <rect x="6.5" y="6" width="3.5" height="3.5" rx=".8" fill="#34d399" />
      <rect x="6.5" y="10.75" width="3.5" height="3.5" rx=".8" fill="#f6c445" />
      <rect x="6.5" y="15.5" width="3.5" height="3.5" rx=".8" fill="#f472b6" />
      <path d="M12.5 7.75H17.5M12.5 12.5H17.5M12.5 17.25H16" stroke="#34d399" strokeWidth="1.4" />
      <path d="M7.3 7.8l.8.8 1.3-1.5" stroke="#0a3d2a" strokeWidth="1" />
    </svg>
  )
}

export function StethoscopeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 3v5.5a4.5 4.5 0 0 0 9 0V3" stroke="#f472b6" strokeWidth="1.8" />
      <path d="M10.5 13v2.5a4.5 4.5 0 0 0 9 0V13" stroke="#f472b6" strokeWidth="1.8" />
      <circle cx="6" cy="3" r="1.1" fill="#f472b6" />
      <circle cx="15" cy="3" r="1.1" fill="#f472b6" />
      <circle cx="19.5" cy="11" r="2.6" fill="#60a5fa" />
      <circle cx="19.5" cy="11" r="1" fill="#dbeafe" />
    </svg>
  )
}

export function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="4.5" width="18" height="16.5" rx="2.5" fill="#f3f4f8" />
      <path d="M5.5 4.5h13A2.5 2.5 0 0 1 21 7v2H3V7a2.5 2.5 0 0 1 2.5-2.5z" fill="#ef4444" />
      <rect x="7" y="2.5" width="1.8" height="4" rx=".9" fill="#7f1d1d" />
      <rect x="15.2" y="2.5" width="1.8" height="4" rx=".9" fill="#7f1d1d" />
      <rect x="5.5" y="11" width="3.4" height="3" rx=".7" fill="#7c8cf8" />
      <rect x="10.3" y="11" width="3.4" height="3" rx=".7" fill="#34d399" />
      <rect x="15.1" y="11" width="3.4" height="3" rx=".7" fill="#f6c445" />
      <rect x="5.5" y="15.5" width="3.4" height="3" rx=".7" fill="#f472b6" />
      <rect x="10.3" y="15.5" width="3.4" height="3" rx=".7" fill="#4fc3f7" />
    </svg>
  )
}

/* App icons (stroke, currentColor) */

function Stroke({ children, size = 20 }: { children: React.ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}

export function InboxIcon() {
  return (
    <Stroke>
      <path d="M4 13.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4.5" />
      <path d="M4 13.5 6.2 6.3A2 2 0 0 1 8.1 5h7.8a2 2 0 0 1 1.9 1.3L20 13.5h-4.5l-1 2h-5l-1-2z" />
    </Stroke>
  )
}

export function WeekIcon() {
  return (
    <Stroke>
      <rect x="3.5" y="5" width="17" height="15" rx="2" />
      <path d="M3.5 9.5h17M8 3v4M16 3v4M7.5 13h3M13.5 13h3M7.5 16.5h3" />
    </Stroke>
  )
}

export function ResultsIcon() {
  return (
    <Stroke>
      <path d="M4 20h16M7 16v-4M12 16V6M17 16v-7" />
    </Stroke>
  )
}

export function PaperclipIcon() {
  return (
    <Stroke>
      <path d="m20 11.5-7.6 7.6a5 5 0 0 1-7.1-7.1l8.1-8.1a3.4 3.4 0 0 1 4.8 4.8l-8.1 8.1a1.7 1.7 0 0 1-2.4-2.4L15 7" />
    </Stroke>
  )
}

export function CheckIcon({ size = 16 }: { size?: number }) {
  return (
    <Stroke size={size}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </Stroke>
  )
}

export function BackIcon() {
  return (
    <Stroke size={18}>
      <path d="M15 5l-7 7 7 7" />
    </Stroke>
  )
}

/** A small spreadsheet grid, in its own green (for "Import spreadsheet"). */
export function SheetIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--sheet-icon)" strokeWidth="1.8"
      strokeLinejoin="round" aria-hidden="true">
      <rect x="3.5" y="3.5" width="17" height="17" rx="2.5" />
      <path d="M3.5 9h17M3.5 14.5h17M9.5 9v11.5M15 9v11.5" />
    </svg>
  )
}
