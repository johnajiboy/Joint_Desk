# Assumptions behind the synthetic data

Real patient data can't be used (UK GDPR special category data; Caldicott Principles), so the data is
generated. Every value below is either sourced or stated as an assumption. **Before submitting, check each
"Verify" item against the latest published figure and update `data/generate_patients.py` if needed.**

## NHS standards used

| Item | Standard | Use in the data |
|---|---|---|
| NHS number | 10 digits, modulus 11 check digit; numbers starting 999 are the NHS test range | Every patient has a valid 999 test number |
| Gender | NHS Data Dictionary, Person Stated Gender Code (1 Male, 2 Female) | `sex_code`, `sex` |
| Priority | NHS Data Dictionary, Priority Type (1 Routine, 2 Urgent, 3 Two week wait) | `priority_type` |
| Referral source | NHS Data Dictionary, Source of Referral for Outpatients (03 = GP) | `source_of_referral` |
| Specialty | Treatment Function Code 110, Trauma and Orthopaedics | `treatment_function_code` |
| RTT status | Referral to Treatment Period Status (10 = first activity) | `rtt_status` |
| Diagnosis | ICD-10 M17.0 (bilateral primary gonarthrosis), M17.1 (other primary gonarthrosis) | `icd10` |
| Problem list | SNOMED CT 239873007 Osteoarthritis of knee; comorbidity codes in `kneedss/standards.py` | Letter problem lists |
| Surgery | OPCS-4 W40.1 Primary total prosthetic replacement of knee joint using cement | For the slot model later |
| Pain and function | Oxford Knee Score, 12 items, 0 (worst) to 48 (best); bands 0-19 severe, 20-29 moderate to severe, 30-39 mild to moderate, 40-48 satisfactory | `oks`, `oks_before` |
| X-ray | Kellgren-Lawrence grade 0-4, written in letters as the radiologist's wording | `kl_grade` |
| Waiting time | 18-week referral-to-treatment standard; 52 weeks as the long-wait marker | `weeks_waiting` |
| Letter layout | NHS e-Referral Service referral: auto-filled record block, then GP free text | Letters |
| Pathway rules | NICE NG226, Osteoarthritis in over 16s (2022), simplified | `kneedss/rules.py` |

## Distributions

| Field | Value used | Source or reasoning |
|---|---|---|
| Sex | 57% female | NJR 12th Annual Report: 43% of primary knee replacements were in men |
| Age | Normal, mean 69, SD 9.5, 45-92 | NJR: median age about 70; listing-clinic study: knee mean 69.8 (SD 9.7). Verify against latest NJR |
| Indication | All knee osteoarthritis | NJR: osteoarthritis the sole indication in 96% of primary knee replacements |
| BMI | Log-normal, median 31 | Assumption from typical NJR primary knee BMI around 31. Verify in NJR Part Two data |
| Oxford Knee Score | Mean 31 - 3.6 x KL grade, SD 6.5 (overall mean about 20) | Listing-clinic mean 16.8 to 18.7 (hip and knee combined). Referrals include milder cases, so slightly higher |
| X-ray grade | KL1 4%, KL2 21%, KL3 43%, KL4 32% | Assumption: orthopaedic referrals skew to moderate or severe change |
| Score decline | About 1.5 + 0.6 x (KL - 2) points per 6 months, SD 3 | Assumption: worse joints decline faster |
| Physiotherapy | None 22%, 2-5 weeks 15%, 6-12 weeks 50%, 13-20 weeks 13% | Assumption: most patients are offered exercise therapy first (NICE NG226) |
| Diabetes | 6% rising 1.2 points per BMI unit over 25 | Assumption: diabetes is more common with higher BMI |
| Hypertension, CKD | Rise with age | Assumption |
| Smoking | Never 48%, ex 40%, current 12% | Assumption, in line with an older population |
| Living alone | About 18-30%, higher with age and in women | Assumption |
| Weeks waiting | Log-normal, median 18, up to 104; about 7% over 52 | Assumption shaped like Trauma and Orthopaedics RTT waits. Verify against latest NHS England RTT statistics |
| Deprivation | Postcode-based IMD decile; about 44% in deciles 1-3 | Middlesbrough has a high share of the most deprived areas in England |

## Letters

| Feature | Share | Why |
|---|---|---|
| Oxford Knee Score stated | 80% | Many GPs don't record it |
| X-ray as KL grade / radiologist wording only / requested / not mentioned | 25% / 65% / 5% / 5% | Reports usually describe findings in words |
| Physiotherapy in weeks / vague / not mentioned | 86% / 8% / 6% | |
| Coded BMI out of date, newer BMI in the text | 12% | Tests choosing the most recent value |
| Expedite letters (state weeks waiting) | About 30% | GPs write again when patients deteriorate |

### X-ray wording for KL 2

Two of the three KL 2 wordings used "early" ("Early osteoarthritic change...", "...early medial joint space
narrowing..."), which fits KL 1 as well. The extraction model read "early" as KL 1, and the answer key could
not fairly call that wrong. Both are now worded with "mild" and "definite osteophytes", the KL 2 criteria, and
no KL 2 wording says "early". They were replaced in place so the random draws are unchanged.

The 150 dev letters on disk were generated before this fix and have not been regenerated, so their results stay
comparable. 20 of them use one of the old KL 2 wordings (L0005, L0017, L0019, L0028, L0049, L0051, L0054,
L0064, L0080, L0083, L0098, L0099, L0107, L0123, L0127, L0131, L0145, L0146, L0147, L0150). Running
`python data/generate_letters.py` again would change only that line in those 20 letters
(`tests/test_generate_letters.py` checks this). The test set uses the new wording.

## Held-out test set

The extraction prompt was tuned on the 150 dev letters, so dev scores are optimistic. The test set is for a
fair score and must never be used to change the prompt.

| Item | Dev set | Test set |
|---|---|---|
| Folder | `data/output/` | `data/output/test/` |
| Letters | 150, IDs L0001-L0150, seed 11 | 100, IDs T0001-T0100, seed 2027 |
| Patients | stratified sample of the 1,500 | different patients: dev patients excluded |
| Letter mode | normal | hard |

Hard mode keeps every fact and rule the same and makes the text harder to read. Each change draws from its own
random generator, and every evidence quote is re-read from the final text so it stays an exact substring.

| Feature | Rate | Detail |
|---|---|---|
| GP shorthand | each phrase 60% | "OA", "R) knee", "L) knee", "bilat knees", "physio", "c/o", "w/", "&", "mins", "XR", "Mx", "inj" |
| Typos | 2-5 per letter | two letters swapped inside a word of 6+ letters; never digits |
| Facts out of order | 60% | letter sections and history sentences shuffled |
| BMI conflicts | more often | coded BMI out of date 35% (vs 15%), newer BMI in the text 30% (vs 12%), or an older dated BMI in the text 35% of the rest |
| Scanned-style text | 35% | hard line breaks mid-sentence, doubled spaces, collapsed columns, a "Page 1 of 2" break |

Shorthand and typos go only in the GP's free text, not the computer-made record block, and never in the
radiologist's X-ray wording.

Gold rule: a fact is in the answer key only if the letter states it. Where two values conflict, the newest
dated value is gold. Weeks waiting for the pathway decision comes from the waiting list (the RTT clock), not
the letter.

## Cleaning (`kneedss/clean.py`)

| Problem in the raw file | What cleaning does | Why |
|---|---|---|
| Duplicate referral (same NHS number) | Keep one row, preferring the surname not in capitals | The capitals copy is the re-keyed one |
| Sex as "M", "female", "2"... | Take it from the sex code (1 Male, 2 Female) | The code is the coded field and was never corrupted |
| Laterality as "Rt", "B/L"... | Map to Right, Left, Bilateral | Fixed list of synonyms |
| Referral date as dd/mm/yyyy | Convert to ISO; recalculate weeks waiting from it | The RTT clock starts at referral |
| Impossible age (0, 129, 199) | Recalculate from date of birth on 20/10/2026 | Date of birth is the primary record |
| BMI with a lost decimal point (314) | Divide by 10 when that gives a BMI of 12-80 | 314 can't be a BMI; 31.4 is typical |
| OKS outside 0-48 | Set missing | The true score can't be known |
| Physio as "some", "yes", "?", "6-8" | Set missing | In the data these carry no information (true values include 0) |
| Smoking "unknown" or blank | Set missing; capitals standardised | |
| OKS, BMI or X-ray grade missing | Left missing, never imputed | The rules send these referrals to "Ask the GP", as a clinician would |

Missing values are not imputed because a guessed Oxford score or X-ray grade would change a patient's pathway.
`eval/eval_cleaning.py` checks every logged problem and every cell against the truth
(`eval/results/cleaning_summary.md`): no value is left wrong.

Age in the truth table is always worked out from the date of birth on the extract date (20/10/2026). An
earlier version stored the drawn age instead, which was one year out for one patient (KP00788, born 21/10/1955:
now 70, was 71). The drawn age still sets the date of birth and the age-related risks, so fixing this changed
only that one cell in `patients_clean.csv` and `patients_raw.csv`; letters, answer keys and caches are the same.

## Sources

- NHS number validation and test range: [cardinal_pythonlib nhs module](https://cardinalpythonlib.readthedocs.io/en/latest/_modules/cardinal_pythonlib/nhs.html)
- National Joint Registry 12th Annual Report (2015): [HQIP](https://www.hqip.org.uk/wp-content/uploads/2018/02/national-joint-registry-12th-annual-report-2015.pdf)
- Oxford scores at listing clinic and pre-operative assessment: [PMC5838660](https://pmc.ncbi.nlm.nih.gov/articles/PMC5838660)
- NICE NG226, Osteoarthritis in over 16s: diagnosis and management (2022)
- NHS Data Dictionary (codes listed above)
