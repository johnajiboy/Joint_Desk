# Joint Desk

MSc Intelligent Decision Support Systems project. Supports an NHS MSK triage clinician deciding what
happens to each knee osteoarthritis referral: surgery list, physio first, weight support and physio
first, keep on non-surgical care, or ask the GP for more information.

All data is synthetic (see `docs/assumptions.md`). Never add real patient data.

## Rules for working in this repo

- Never add `Co-Authored-By`, "Generated with Claude Code" or any AI attribution to commits, PRs or files.
- Commit only when asked. Small commits with plain messages.
- Build one stage at a time and run its tests before moving on.
- The LLM only reads letters. It never decides the pathway: `kneedss/rules.py` does, and a clinician confirms.
- Keep `kneedss/rules.py` the single source of the pathway rules; the generators and the app both use it.

## Stack

- Python 3.12: pandas, numpy, scikit-learn, PuLP, pydantic, anthropic SDK, pypdf, python-docx, pytest
- Backend: FastAPI + SQLite (SQLModel)
- Frontend: React + TypeScript (Vite), Tailwind, Recharts
- Env: `ANTHROPIC_API_KEY` in `.env` (never commit it). `DEMO_MODE=1` uses saved LLM results.

## Layout

```
kneedss/          shared Python: standards.py, rules.py, extract.py, optimise.py, schemas.py
data/             generators + output (already built: 1,500 patients, 150 letters, answer key)
backend/          FastAPI app (api routes, db, services)
frontend/         React app
eval/             evaluation scripts that write tables/figures for the report
tests/            pytest
docs/             assumptions, data dictionary
```

## Core flow

1. Clinician uploads a letter (PDF, DOCX or TXT, one or many) on the Queue screen.
2. Backend extracts the text (pypdf / python-docx).
3. LLM returns facts as JSON validated by a pydantic model, each with an exact quote from the letter.
4. Quote check: drop any fact whose quote is not in the letter text.
5. `rules.decide()` gives the pathway; `rules.priority_score()` the priority.
6. Match on NHS number: update the existing waiting-list patient, otherwise create one.
7. Clinician confirms or overrides; overrides are recorded.
8. "Build this week's list": PuLP fills surgery and physio slots by priority; nobody over 52 weeks is skipped.

## Stages

1. Done: data generators (`data/`).
2. Extraction: `kneedss/extract.py` + `eval/eval_extraction.py` scored against `data/output/answer_key.jsonl`
   (per-field accuracy, quote hit rate, pathway agreement). Cache LLM results to `data/cache/`.
3. Cleaning: `kneedss/clean.py` turns `patients_raw.csv` into a clean table; check it against
   `data_quality_log.csv`. Discretise OKS bands, BMI categories, wait bands.
4. Knowledge: decision tree trained on the clean data, compared with the expert rules.
5. Optimiser: `kneedss/optimise.py` weekly allocation; compare with first come, first served.
6. Backend API: upload, queue, patient, confirm, build week, results.
7. Frontend: the four screens below.
8. PDF letters: export each generated letter as an NHS-style PDF for upload demos.

## UI rules (keep it quiet and short)

- Numbers, chips and short labels, not sentences. "Surgery · 81", not a paragraph.
- One primary button per screen. Colour only for status (pathway chips, over-limit values).
- One line of reasoning per decision; more behind a "Why" toggle.
- Evidence is shown in place: highlight the quoted words in the letter.
- Empty/error states in a few words: "No score in letter", "Ask GP", "Couldn't read file".
- One typeface (IBM Plex Sans). Navy primary (#1b2f5e light / #3b63c4 dark). Light and dark mode via CSS
  variables with a toggle in the header; remember the choice. No gradients, no shadows on cards, no emoji.
- Upload is a search-style bar: paperclip icon, file field ("Choose referral letters or drop them here"),
  Browse and "Upload and read" buttons; drag and drop onto it. Each file then shows as a chip:
  "Reading…" with a moving bar, then its pathway chip pops in.
- Motion: short fade-up on load (staggered rows), highlights sweeping into the letter, chart lines drawing,
  meters growing, hover and press feedback. 150-900 ms, transform and opacity only, and turned off under
  prefers-reduced-motion.
- Must work at 1440px and on a tablet.

## Landing page (route `/`, the only exception to the "no gradients, no shadows" rule)

Full-screen, animated, dark by default with the same light/dark toggle. Clicking "Start here" goes to the Queue.

- Colours (dark): background radial gradient #141a3d centre to #0a0e27 edge; text #e8ecff; muted #9aa3c7;
  lines #2a3166; blue #7c8cf8; sky #4fc3f7. Light mode: #f4f6ff / #e4e9ff, text #0f1640, blue #4f5fe0, sky #0288d1.
- Fonts: Outfit 800 for the title, IBM Plex Sans for text, IBM Plex Mono for the clock.
- Header: glass bar (blur, 1px line border, 16px radius). Left: logo + "Joint Desk". Right: live clock
  (`hh:mm:ss AM/PM`, ticks every second, small blinking sky dot) and the mode toggle.
- Background: about 14 twinkling 2px stars.
- Centre stage (500x500): a filled disc r225 that draws in, a dashed ring r170, a soft sky glow behind the knee.
- Knee: line-drawn SVG (femur, patella, tendons, tibia, fibula), strokes draw in one after another (about 1.8 s).
  The joint space is a sky line that fades in and pulses.
- Orbit: 5 round chips (56px) circle the knee once every 80 s; each chip counter-rotates so it stays upright.
  Pop in one by one from 1.9 s. Coloured icons and hover glow colour:
  | Chip | Icon | Hover colour |
  |---|---|---|
  | Letter | yellow sticky note with lines | #f6c445 |
  | LLM reads | purple sparkle + small cyan sparkle | #a78bfa |
  | Rules | green checklist with green/yellow/pink boxes | #34d399 |
  | Clinician | stethoscope (pink tubes, blue chest piece) | #f472b6 |
  | Week plan | calendar, red header, coloured date squares | #ef4444 |
- Hover: a chip scales to 1.14 with a 2px ring and a glow in its colour, label brightens. Hovering the stage
  pauses the orbit and brightens the disc and the glow.
- Mouse parallax on the whole page: stars move -14px, orbit 22px, knee 10px at the edges (rAF throttled),
  back to 0 on mouse leave.
- Title "Joint **Desk**" 76px, "Desk" in a blue-to-sky gradient; tagline "Knee referrals, read and prioritised."
- "Start here" button shaped like a mouse: 34x54 capsule outline with a scrolling wheel, breathing glow,
  spaced uppercase text under it. Hover: border turns sky, lifts 2px, letter spacing widens. Keyboard focus ring.
- Order: header, knee draw, rings, chips, title (2.6 s), tagline, button (3.1 s).
- prefers-reduced-motion: no orbit, parallax, twinkle or draw; show everything at once.
- Responsive: page is `min-height: 100svh`. Stage is `min(500px, 88vw)` square; knee, glow and chips are sized
  in % of the stage so everything scales together. Title `clamp(46px, 12vw, 76px)`, tagline `clamp(15px, 4vw, 18px)`.
  Chips 56px (desktop), 48px (≤900px), 40px with 10.5px labels (≤600px). At ≤600px the header is 52px tall,
  16px side gutter, and shows logo, clock and an icon-only toggle. Short phones (≤700px tall): stage max 360px.
  Touch (`hover: none`): no parallax, chip glow shows on tap (`:active`) instead of hover.

## Responsive (all screens)

- Test at 375px (phone), 768px (tablet), 1440px (desktop). No horizontal page scroll; 16px side gutter on phones.
- Desktop: side nav + sheet. Tablet (≤1024px): nav collapses to icons. Phone (≤640px): nav becomes a bottom
  tab bar (Referrals, This week, Results); header keeps title, mode toggle and the one primary button.
- Upload bar: on phones the field takes the full width and Browse / "Upload and read" go on a row below it.
- Queue table: on phones each row becomes a card (name, pathway chip, priority, weeks); tabs scroll sideways.
- Patient: two columns on desktop; on tablet and phone the facts/pathway panel comes first, the letter under it
  behind a "Letter" toggle, charts stacked full width.
- This week: capacity tiles 4 across, 2x2 on tablet and phone; the three lists stack on phones.
- Results: 2x2 card grid on desktop, one column on phones. Charts use a responsive container.
- Tap targets at least 44px. Use Tailwind breakpoints (`sm`, `md`, `lg`), not fixed widths.

## Screens

| Screen | Shows | Primary action |
|---|---|---|
| Landing | Animated title, knee, orbit chips, clock (spec above) | Start here |
| Queue | Referrals: name, pathway chip, priority, weeks waiting. Tabs: All, Surgery, Physio, Needs info. Drop zone for letters | Upload letters |
| Patient | Letter with highlighted facts (left); facts, pathway, priority, charts: OKS trend, priority breakdown, weeks vs 18/52 (right) | Confirm |
| This week | Slots filled (surgery, physio, weight support), who's in, who's next | Build this week's list |
| Results | Cleaning summary, LLM accuracy per field, rules vs decision tree, backlog before/after | none |

## Commands

```bash
python data/generate_patients.py && python data/generate_letters.py && python data/check_data.py
pytest
uvicorn backend.main:app --reload
cd frontend && npm run dev
```
