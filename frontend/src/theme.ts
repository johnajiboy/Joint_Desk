import { useCallback, useLayoutEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const KEY = 'jd-theme'

function saved(): Theme | null {
  try {
    const t = localStorage.getItem(KEY)
    return t === 'light' || t === 'dark' ? t : null
  } catch {
    return null
  }
}

function systemTheme(): Theme {
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Saved choice wins; otherwise `fallback` (or the system setting). */
export function useTheme(fallback?: Theme) {
  const [theme, setTheme] = useState<Theme>(() => saved() ?? fallback ?? systemTheme())

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem(KEY, next)
      } catch {
        // Storage blocked: the choice lasts for this page only.
      }
      return next
    })
  }, [])

  return { theme, toggle }
}
