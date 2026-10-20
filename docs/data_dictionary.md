# Data dictionary

## patients_clean.csv (one row per patient)

| Column | Type | Meaning | Standard |
|---|---|---|---|
| patient_id | text | Project ID, KP00001 to KP01500 | Project |
| nhs_number | text | Synthetic NHS number, 999 test range, formatted 3-3-4 | NHS number, modulus 11 |
| title, first_name, surname | text | Synthetic name | |
| sex_code, sex | text | 1 Male, 2 Female | Person Stated Gender Code |
| date_of_birth | date (ISO) | | |
| age | integer | Age on 20/10/2026 | |
| postcode_outward | text | Outward code only (e.g. TS5) | Privacy: no full postcode |
| imd_decile | 1-10 | Index of Multiple Deprivation decile, 1 = most deprived | English IMD |
| practice_code, practice_name | text | Fictional GP practice (Y99 prefix) | ODS-style code, fictional |
| gp_name | text | Fictional referring GP | |
| source_of_referral | code | 03 = GP | Source of Referral for Outpatients |
| priority_type, priority | code, text | 1 Routine, 2 Urgent | Priority Type |
| treatment_function_code | code | 110 Trauma and Orthopaedics | Treatment Function Code |
| rtt_status | code | 10 = first activity | RTT Period Status |
| referral_date | date (ISO) | Start of the RTT clock | |
| weeks_waiting | integer | Weeks since referral on 20/10/2026 | RTT |
| icd10 | code | M17.0 bilateral, M17.1 unilateral primary knee OA | ICD-10 |
| snomed_problem | code | 239873007 Osteoarthritis of knee | SNOMED CT |
| laterality | text | Right, Left, Bilateral | |
| kl_grade | 0-4 | Kellgren-Lawrence X-ray grade | |
| oks | 0-48 | Oxford Knee Score now (lower is worse) | Oxford Knee Score |
| oks_before | 0-48 | Earlier Oxford Knee Score | |
| oks_months_between | integer | Months between the two scores | |
| physio_weeks | integer | Weeks of physiotherapy completed | |
| injections | integer | Steroid injections | |
| analgesia | text | Current pain relief | dm+d-style dose wording |
| bmi | number | Body mass index, kg/m2 | |
| diabetes, hypertension, ckd | true/false | Comorbidities | |
| hba1c | integer | mmol/mol, diabetics only | |
| smoking_status | text | Never smoked, Ex-smoker, Current smoker | |
| night_pain, walking_aid | true/false | | |
| walk_minutes | integer | Walking tolerance | |
| lives_alone, carer, employed | true/false | Social context | |
| true_pathway, true_pathway_label | code, text | Pathway from the rules using all true facts | `kneedss/rules.py` |
| true_rule | 1-6 | Which rule fired | |
| weight_support | true/false | Weight support offered alongside | |
| priority_score | 0-100 | Surgical priority | `kneedss/rules.py` |

## patients_raw.csv

The same columns minus the five truth columns (`true_pathway` to `priority_score`), with errors added and
duplicate rows. Every change is in `data_quality_log.csv`.

## answer_key.jsonl (one object per letter)

| Key | Meaning |
|---|---|
| letter_id, patient_id | Links the letter to its patient |
| letter_type | initial or expedite |
| style | structured, narrative or brief |
| letter_date | Date of the letter |
| difficulty_tags | oks_missing, kl_from_wording, xray_missing, physio_vague, physio_missing, abbreviation, negation, bmi_two_values, bmi_conflict |
| gold | The facts as the letter states them (null if not stated): name, age, sex, side, oks, oks_before, kl, xray_finding, physio_weeks, injections, bmi, night_pain, lives_alone_or_carer, walking_aid, diabetes, smoking, weeks_waiting |
| evidence | For each stated fact, the exact words in the letter it comes from |
| gold_pathway, gold_pathway_label, gold_rule | Pathway the rules give from the letter's facts |
| gold_weight_support, gold_priority_score | |
| record_pathway | Pathway from the full GP record, to show the effect of facts missing from letters |
