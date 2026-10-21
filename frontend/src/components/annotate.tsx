import { Fragment } from 'react'
import type { ReactNode } from 'react'
import { AUTO_TERMS } from '../glossary'
import { Term } from './Term'

/** Running text with a "?" after each known abbreviation (OKS, KL, BMI). */
export function annotate(text: string): ReactNode {
  const words = Object.keys(AUTO_TERMS)
  const parts = text.split(new RegExp(`\\b(${words.join('|')})\\b`))
  return parts.map((part, i) =>
    AUTO_TERMS[part] ? <Term key={i} k={AUTO_TERMS[part]}>{part}</Term> : <Fragment key={i}>{part}</Fragment>)
}
