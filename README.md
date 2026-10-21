# Joint Desk

Decision support for an NHS MSK triage clinician deciding what happens to each knee osteoarthritis referral:
surgery list, physio first, weight support and physio first, keep on non-surgical care, or ask the GP for more
information. An LLM only reads the letters; the rules in `kneedss/rules.py` decide; a clinician confirms.

**All data is synthetic** (NHS test-range numbers, fictional practices). See `docs/assumptions.md`.

Live demo (demo data, no backend): https://frontend-wine-ten-82.vercel.app

## Run it locally

Needs Python 3.12, Node 20+, and the CBC solver for the weekly optimiser (`brew install cbc` on macOS).

### One-time setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r backend/requirements.txt
cd frontend && npm install && cd ..
```

Optional: put `ANTHROPIC_API_KEY=...` in `.env` (never commit it). Keep `DEMO_MODE=1` there too: the app then only
uses saved LLM results and never spends API credit. Without a key everything still runs from the saved results.

### Two terminals

```bash
# Terminal 1: the API on http://localhost:8000 (fills backend/joint_desk.db on first start)
source .venv/bin/activate
uvicorn backend.main:app --reload
```

```bash
# Terminal 2: the app on http://localhost:5173, talking to that API
cd frontend
VITE_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:5173 and click **Start here**. The header shows **Live** when the app is using the API.
Without `VITE_API_URL` the app runs on the static demo data (header: **Demo data**), as the Vercel site does.

To try uploads, export the letters as files and drop some onto the Referrals screen:

```bash
python scripts/export_pdfs.py      # 250 PDFs + 10 DOCX, read back and checked; zips in data/output/
```

Files named after a letter (`L0001.pdf`, `T0042.docx`, `L0001.txt`) are matched to it; their facts are reused
only when every quote behind them is found in the file. Other files need the LLM (`DEMO_MODE=0` and a key).

### Tests

```bash
pytest                              # all Python tests, including every API endpoint
cd frontend && npm run build        # type check and production build
```

## Rebuild the data and results

```bash
python data/generate_patients.py && python data/generate_letters.py && python data/check_data.py
python -m kneedss.clean && python eval/eval_cleaning.py         # stage 3: cleaning
python eval/eval_extraction.py                                   # stage 2: extraction (dev set, cached results only)
python eval/eval_tree.py                                         # stage 4: decision tree vs rules
python eval/eval_optimise.py                                     # stage 5: optimiser, 26-week simulation
python scripts/export_demo.py                                    # demo JSON for the frontend
python scripts/export_pdfs.py                                    # stage 8: PDF and DOCX letters
```

The held-out test set and a real LLM run (spends API credit):

```bash
python data/generate_letters.py --n 100 --seed 2027 --out data/output/test --prefix T --hard \
  --exclude data/output/answer_key.jsonl && python data/check_data.py --out data/output/test
DEMO_MODE=0 python eval/eval_extraction.py --data data/output/test --results eval/results/test
python eval/compare_sets.py
```

## Deploy

- Frontend: Vercel, root directory `frontend`, deploys on every push to `main`. Set `VITE_API_URL` in the Vercel
  project to use the backend.
- Backend: Render free web service from `render.yaml` (`DEMO_MODE=1`). `ANTHROPIC_API_KEY` is set only in the
  Render dashboard, never in the repo.

## Layout

| Path | What it is |
|---|---|
| `kneedss/` | Shared Python: standards, rules, LLM call (`llm.py`), extraction and quote check, cleaning, decision tree, optimiser, results |
| `backend/` | FastAPI + SQLite: letters, queue, patients, decisions, week plan, results |
| `frontend/` | React + TypeScript (Vite, Tailwind, Recharts): landing, Referrals, Patient, This week, Results |
| `data/` | Generators and output (patients, letters, answer keys) |
| `eval/` | Evaluation scripts; tables and figures in `eval/results/` |
| `scripts/` | Demo JSON export, PDF/DOCX export |
| `tests/` | pytest |
| `docs/` | Assumptions and data dictionary |

## Data (`data/output/`)

| File | What it is | Used for (report section) |
|---|---|---|
| `patients_clean.csv` | 1,500 patients with true values and the true pathway | Ground truth, knowledge extraction (4), backlog (5, 7) |
| `patients_raw.csv` | Same patients with 685 realistic errors and 18 duplicates | Cleaning and discretisation (3) |
| `data_quality_log.csv` | Every error added: row, field, true value, raw value | Checking your cleaning worked (3) |
| `waiting_list.csv`, `cleaning_actions.csv` | The cleaned waiting list and every change cleaning made | The app, the optimiser (5) |
| `letters/L0001.txt` ... | 150 GP referral letters in NHS e-RS style (dev set) | LLM input (4) |
| `test/` | 100 harder held-out letters (T0001...) with their answer key | Fair LLM evaluation (7) |
| `letters.jsonl` | The same letters in one file | Batch LLM runs |
| `answer_key.jsonl` / `.csv` | For each letter: facts it states, exact evidence words, difficulty tags, gold pathway | LLM evaluation (7) |
| `data_summary.md` | Distributions and counts | Report tables |
| `letters_pdf.zip`, `letters_test_pdf.zip`, `letters_docx_sample.zip` | PDF and DOCX letters (built by `scripts/export_pdfs.py`, not committed) | Upload demos (8) |
