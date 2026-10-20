import { Link } from 'react-router-dom'
import { ThemeToggle } from '../components/ThemeToggle'
import { Logo } from '../components/icons'
import { useTheme } from '../theme'

export default function Queue() {
  const { theme, toggle } = useTheme()

  return (
    <div className="min-h-svh bg-bg text-text">
      <header className="flex h-14 items-center justify-between border-b border-line px-4 sm:px-6">
        <Link to="/" className="flex min-h-11 items-center gap-2 font-semibold text-primary dark:text-text">
          <Logo size={26} />
          <span>Joint Desk</span>
        </Link>
        <ThemeToggle
          theme={theme}
          onToggle={toggle}
          className="inline-flex h-11 min-w-11 items-center justify-center gap-2 rounded-md border border-line px-3 text-sm transition-transform duration-150 hover:border-primary active:scale-95 [&_.toggle-label]:hidden sm:[&_.toggle-label]:inline"
        />
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <h1 className="fade-up text-xl font-semibold">Referrals</h1>
        <div
          className="fade-up mt-6 rounded-lg border border-line bg-surface px-6 py-12 text-center text-sm text-muted"
          style={{ animationDelay: '80ms' }}
        >
          No referrals yet
        </div>
      </main>
    </div>
  )
}
