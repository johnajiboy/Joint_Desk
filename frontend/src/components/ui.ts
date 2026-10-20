/** Shared class names and helpers for the app screens. */

export const primaryButton =
  'press inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-on-primary disabled:opacity-40'
export const secondaryButton =
  'press inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-surface px-4 text-sm hover:border-primary disabled:opacity-40'

/** Staggered fade-up for list rows (capped so long lists don't wait). */
export function stagger(i: number) {
  return { animationDelay: `${Math.min(i, 15) * 30}ms` }
}
