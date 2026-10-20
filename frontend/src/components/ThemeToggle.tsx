import type { Theme } from '../theme'
import { MoonIcon, SunIcon } from './icons'

type Props = {
  theme: Theme
  onToggle: () => void
  className?: string
}

export function ThemeToggle({ theme, onToggle, className = '' }: Props) {
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      onClick={onToggle}
      className={className}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
      <span className="toggle-label">{next === 'light' ? 'Light' : 'Dark'}</span>
    </button>
  )
}
