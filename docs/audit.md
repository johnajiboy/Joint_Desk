# Joint Desk audit

Run 26/10/2026 11:44 on commit `5d60ee1` with `python scripts/audit.py`: a throwaway database, DEMO_MODE=1, no API calls, no behaviour changed. ✓ = check passed.

| # | Claim | Result | Evidence |
|---|---|---|---|
| 1 | Reading | **PASS** | 3/3 files (PDF, DOCX, TXT) read; OKS, KL, physio, BMI each with a quote found in the file |
| 2 | Quote check | **PASS** | invented OKS quote dropped and logged with reason 'quote not in letter'; 5 real facts kept |
| 3 | Rules decide | **PASS** | schema has no pathway/priority; LLM called once; 3 examples (surgery rule 4, physio rule 3, needs info rule 1) identical on rerun |
| 4 | Clinician decides | **PASS** | confirm + override stored with who, when, old/new and reason; the override moved KP01437 out of the Physio queue filter and out of this week's slots, all lists still full |
| 5 | Optimiser | **PASS** | 28 passed in 6.58s; HiGHS; same plan twice; plan stored and served after refresh; all slots within capacity; 0 over-52s passed over; infeasible week reported with 41 over-52s listed; solver errors reported as such |

Full test suite (`pytest`): **263 passed in 18.84s**

## 1. Reading: PDF, DOCX and TXT through POST /letters (DEMO_MODE=1)

Code: `backend/main.py:198` `@app.post("/letters", dependencies=[Passcode])`
; `kneedss/extract.py:75` `def read_letter(name: str, data: bytes) -> str:`
; `backend/services.py:183` `def read_letter(session: Session, filename: str, data: bytes) -> dict:`
; `backend/services.py:206` `if stored and stored.quotes and all(X.quote_in_letter(q, text) for q in stored.quotes.values()):`

- ✓ all three files read (one request, DEMO_MODE=1, no API call)
- ✓ L0010.pdf: every one of 16 quotes is in the text read from the file
- ✓ T0003.docx: every one of 16 quotes is in the text read from the file
- ✓ L0011.txt: every one of 14 quotes is in the text read from the file

| File | Patient | Fact | Value | Exact quote | Quote in file |
|---|---|---|---|---|---|
| L0010.pdf | Malcolm Ellis | OKS | 20 | Oxford Knee Score 20 | yes |
| L0010.pdf | Malcolm Ellis | KL grade | 4 | Large osteophytes, marked joint space narrowing with bone-on-bone contact, severe sclerosis and varus deformity. | yes |
| L0010.pdf | Malcolm Ellis | Physio weeks | 0 | He has not yet had physiotherapy | yes |
| L0010.pdf | Malcolm Ellis | BMI | 30.1 | BMI 30.1 kg/m2 | yes |
| T0003.docx | Fatima Fletcher | OKS | 15 | Oxford knee score recorded at 15 | yes |
| T0003.docx | Fatima Fletcher | KL grade | None | — | n/a |
| T0003.docx | Fatima Fletcher | Physio weeks | 4 | completed 4 weeks of physiotherapy | yes |
| T0003.docx | Fatima Fletcher | BMI | 33.7 | BMI 33.7 kg/m2 | yes |
| L0011.txt | Stephen Mensah | OKS | 32 | Oxford Knee Score today is 32 | yes |
| L0011.txt | Stephen Mensah | KL grade | None | — | n/a |
| L0011.txt | Stephen Mensah | Physio weeks | 4 | physio x4/52 | yes |
| L0011.txt | Stephen Mensah | BMI | 36.1 | BMI today 36.1 | yes |

## 2. Quote check drops an invented quote

Code: `kneedss/extract.py:158` `def check_quotes(raw: dict, text: str) -> tuple[dict, dict, list]:`; `kneedss/extract.py:169` `reason = "quote not in letter"`

- ✓ invented OKS 12 dropped: facts['oks'] is None, no quote kept
- ✓ recorded as dropped: `[{'field': 'oks', 'value': 12, 'quote': 'Her Oxford Knee Score today is 12', 'reason': 'quote not in letter'}]`
- ✓ real facts kept with their quotes: kl=3, physio_weeks=5, bmi=25.4, oks_before=24, night_pain=False
- ✓ control: the real answer for L0001 drops nothing

## 3. The rules decide, not the LLM

Code: `kneedss/schemas.py:46` `class LetterFacts(BaseModel):`; `kneedss/extract.py:237` `d = decide(f)`; `backend/services.py:175` `dec = X.decide_letter(facts, p.weeks_waiting if p.on_waiting_list else None)`; `kneedss/importer.py:201` `d = decide(f)`

- ✓ LLM schema fields (20): nhs_number, name, letter_date, date_of_birth, age, sex, side, oks, oks_before, kl, xray_finding, physio_weeks, injections, bmi, night_pain, lives_alone_or_carer, walking_aid, diabetes, smoking, weeks_waiting; no pathway, priority or rule
- ✓ the LLM is called in one place only: `kneedss/extract.py:131` `raw = llm.complete_json(SYSTEM, PROMPT.format(text=text), LetterFacts.model_json_schema(), usage=usage)`; its answer is validated as LetterFacts (facts only)
- ✓ every place a stored pathway is set takes it from rules output (`d`/`dec` = decide() / decide_letter() / importer.classify()), the seeded demo letters (computed by decide_letter), or a clinician Decision:
  - `backend/db.py:183` `pathway=d["pathway"], rule=d["rule"], priority=priority_score(f), weight_support=d["weight_support"],`
  - `backend/services.py:109` `return d.new_pathway if d else p.pathway`
  - `backend/services.py:176` `p.pathway, p.rule, p.priority, p.weight_support = dec["pathway"], dec["rule"], dec["priority"], dec["weight_support"]`
  - `backend/services.py:269` `pathway=dec["pathway"], rule=dec["rule"], priority=dec["priority"])`
  - `backend/services.py:272` `p.pathway, p.rule, p.priority, p.weight_support = dec["pathway"], dec["rule"], dec["priority"], dec["weight_support"]`
- ✓ L0004: decide() twice gives the same result (surgery, rule 4)
- ✓ L0001: decide() twice gives the same result (physio, rule 3)
- ✓ L0007: decide() twice gives the same result (review, rule 1)

| Letter | Facts read | Pathway | Rule | Why |
|---|---|---|---|---|
| L0004 | OKS 21, KL 4, physio 10 wk, BMI 37.1 | Surgery list | 4 | OKS 21; KL grade 4; Physio 10 weeks |
| L0001 | OKS 22, KL 3, physio 5 wk, BMI 25.4 | Physio first | 3 | Physio 5 weeks (under 6); OKS 22 above severe range |
| L0007 | OKS 8, KL 4, physio None wk, BMI 31.5 | Ask the GP for more information | 1 | Physiotherapy history unclear |

## 4. The clinician decides (through the API)

Code: `backend/main.py:165` `@app.post("/patients/{pid}/override")`; `backend/services.py:119` `def record_decision(session: Session, p: Patient, new_pathway: str | None, by: str, reason: str | None, kind: str) -> Decision:`; `backend/services.py:108` `def effective_pathway(p: Patient, d: Decision | None) -> str:`

| id | patient | kind | by | at (UTC) | rules said | old | new | reason |
|---|---|---|---|---|---|---|---|---|
| 1 | KP00678 | confirmed | Dr Audit | 2026-10-26T11:43:47+00:00 | surgery | surgery | surgery | Agree with rules |
| 2 | KP01437 | overridden | Dr Audit | 2026-10-26T11:43:47+00:00 | physio | physio | non_surgical | Patient declines physio for now |

- ✓ two Decision rows: one confirm, one override
- ✓ override stored with who (Dr Audit), when, old → new (physio → non_surgical) and reason
- ✓ queue: KP01437 moved from the Physio filter to Non-surgical
- ✓ week plan: KP01437 has no slot after the override, and every list is still full
  - surgery: out —, in — (12 → 12 slots)
  - physio: out ['KP01437'], in ['KP01063'] (20 → 20 slots)
  - weight_support: out —, in — (8 → 8 slots)
  - weight-support patients can use physio slots, so freeing one slot can move more than one name
## 5. The optimiser

Code: `kneedss/optimise.py:107` `def optimise(df: pd.DataFrame, capacity: dict[str, int] | None = None, long_wait: int = LONG_WAIT,`; `kneedss/optimise.py:138` `prob += (pulp.lpSum(vs) == 1) if (pid in locked or (hard and long[pid])) else (pulp.lpSum(vs) <= 1)`; `kneedss/optimise.py:159` `status = "infeasible"`; `kneedss/optimise.py:224` `def skipped_long_waiters(df: pd.DataFrame, assigned: pd.DataFrame, long_wait: int = LONG_WAIT) -> list[str]:`; solver `kneedss/optimise.py:52` `def solver() -> pulp.LpSolver:`; stored plans `backend/services.py:323` `def save_week(session: Session, plan: dict, by: str) -> dict:`

- ✓ `pytest tests/test_optimise.py`: 28 passed in 6.58s
- ✓ solver: HiGHS (highspy), zero optimality gap
- ✓ built twice: the two plans are identical (every list, every patient, every reason)
- ✓ each build is stored (who, when) and GET /week/latest serves the last one, so a refresh keeps it
- ✓ Surgery: 12 of 12 slots
- ✓ Physio: 20 of 20 slots
- ✓ Weight support: 8 of 8 slots
- ✓ the API's plan and a direct optimise() on the same data give the same patients
- ✓ HiGHS and CBC give the same patients in every slot on this waiting list
- ✓ no patient over 52 weeks was passed over for someone under 52 weeks (skipped_long_waiters = [])
- ✓ more over-52s than slots (53 need surgery, 12 surgery slots): status 'infeasible', shortfall ['53 over 52 weeks need surgery; 12 slots']
- ✓ every surgery slot this week went to someone over 52 weeks
- ✓ the next in line are over-52s marked 'Over 52 weeks · no slot left' (KP00248, KP01478, KP00709, KP00666, KP00528)
- the optimiser lists all 41 over-52s without a slot by ID (Plan.long_wait['unmet']): KP00026, KP00099, KP00100, KP00161, KP00215, KP00248, KP00276, KP00288, KP00390, KP00452, KP00454, KP00466, …
- ✓ the API returns all 41 by name, longest wait first (This week: '41 over 52 weeks still waiting')
- ✓ a solver failure gives 500 "Couldn't build the list · solver error" (not 'No slot left'); the reason is logged

