/** One-line meanings for the terms the app uses, shown by <Term>. The only place these are written. */
export const GLOSSARY = {
  oks: { term: 'OKS', text: 'Oxford Knee Score, 0–48 questionnaire on pain and function. Lower is worse.' },
  kl: { term: 'KL', text: 'Kellgren–Lawrence X-ray grade, 0–4. Higher is worse; 4 is bone on bone.' },
  bmi: { term: 'BMI', text: 'Body mass index. 35 or more adds weight support.' },
  fcfs: { term: 'FCFS', text: 'First come, first served. Longest wait goes first.' },
  priority_only: { term: 'Priority only', text: 'Worst knee goes first, however long others have waited.' },
  optimiser: { term: 'Optimiser', text: 'Worst knees first, but everyone over 52 weeks gets a slot first.' },
  waits: { term: '18 / 52 weeks', text: 'NHS waiting standards. 18 is the target; 52 is the maximum.' },
  triage: { term: 'Triage', text: 'The rules send patients to physio, weight support or more info instead of straight to surgery.' },
  priority: { term: 'Priority', text: '0–100 score from knee score, X-ray, recent decline, time waiting, night pain and living alone.' },
  nhs_bands: { term: 'NHS bands', text: 'OKS groups 0–19, 20–29, 30–39, 40–48.' },
} as const

export type GlossaryKey = keyof typeof GLOSSARY

/** Abbreviations that get a "?" automatically wherever annotate() is used on running text. */
export const AUTO_TERMS: Record<string, GlossaryKey> = { OKS: 'oks', KL: 'kl', BMI: 'bmi' }
