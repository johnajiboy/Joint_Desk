# Joint Desk: synthetic data (stage 1)

Synthetic data for the knee osteoarthritis referral decision support system. Built to NHS standards,
no real patients. See `docs/assumptions.md` for every standard, distribution and source.

## Run it

```bash
cd knee-dss
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python data/generate_patients.py     # 1,500 patients
python data/generate_letters.py      # 150 letters + answer key
python data/check_data.py            # checks everything, writes data_summary.md
```

Same seed, same data every time. Change size with `--n`, randomness with `--seed`.

## What you get (`data/output/`)

| File | What it is | Used for (report section) |
|---|---|---|
| `patients_clean.csv` | 1,500 patients with true values and the true pathway | Ground truth, knowledge extraction (4), backlog (5, 7) |
| `patients_raw.csv` | Same patients with 685 realistic errors and 18 duplicates | Cleaning and discretisation (3) |
| `data_quality_log.csv` | Every error added: row, field, true value, raw value | Checking your cleaning worked (3) |
| `letters/L0001.txt` ... | 150 GP referral letters in NHS e-RS style | LLM input (4) |
| `letters.jsonl` | The same letters in one file | Batch LLM runs |
| `answer_key.jsonl` / `.csv` | For each letter: facts it states, exact evidence words, difficulty tags, gold pathway | LLM evaluation (7) |
| `data_summary.md` | Distributions and counts | Report tables |

## Files

| File | Purpose |
|---|---|
| `kneedss/standards.py` | NHS number (999 test range, modulus 11), Data Dictionary codes, ICD-10, SNOMED CT, OPCS-4, Oxford Knee Score bands, radiology wording |
| `kneedss/rules.py` | NICE-based pathway rules and priority score (shared with the decision system later) |
| `data/generate_patients.py` | Patient generator |
| `data/generate_letters.py` | Letter and answer key generator |
| `data/check_data.py` | Consistency checks and summary |
| `docs/assumptions.md` | Standards, distributions, sources |
| `docs/data_dictionary.md` | Every column explained |
