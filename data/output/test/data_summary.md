# Data summary

Patients: 1,500. Raw rows: 1,518 (18 duplicates). Data-quality issues logged: 685.

## Patients (clean)

|                |   mean |   std |   min |   50% |   max |
|:---------------|-------:|------:|------:|------:|------:|
| age            |   68.7 |   9.4 |    45 |  69   |    92 |
| bmi            |   31.6 |   5.6 |    19 |  31.3 |    55 |
| oks            |   20.1 |   7.1 |     2 |  20   |    45 |
| oks_before     |   22.7 |   7.9 |     0 |  22   |    48 |
| kl_grade       |    3   |   0.8 |     1 |   3   |     4 |
| physio_weeks   |    7   |   5.3 |     0 |   7   |    20 |
| weeks_waiting  |   23.4 |  17.5 |     2 |  19   |   104 |
| priority_score |   52.4 |  11.9 |    18 |  52   |    89 |

- Female: 57.5%
- Type 2 diabetes: 12.9%; hypertension: 34.1%; CKD: 7.1%
- Waiting over 18 weeks: 50.1%; over 52 weeks: 7.2%
- IMD deciles 1-3 (most deprived): 44.0%

Mean Oxford Knee Score by X-ray grade: KL1: 26.3, KL2: 23.6, KL3: 20.6, KL4: 16.4

## Pathways (full record)

| true_pathway_label              |   patients |
|:--------------------------------|-----------:|
| Surgery list                    |        880 |
| Keep on non-surgical care       |        327 |
| Physio first                    |        216 |
| Weight support and physio first |         77 |

## Data-quality issues in the raw file

|                                                  |   rows |
|:-------------------------------------------------|-------:|
| ('(row)', 'duplicate referral')                  |     18 |
| ('age', 'impossible value')                      |     15 |
| ('bmi', 'decimal point lost (e.g. 31.4 -> 314)') |     22 |
| ('bmi', 'missing')                               |     45 |
| ('kl_grade', 'missing')                          |     30 |
| ('laterality', 'inconsistent label')             |    120 |
| ('oks', 'missing')                               |     90 |
| ('oks', 'out of range (OKS is 0-48)')            |     15 |
| ('physio_weeks', 'free text in numeric field')   |     45 |
| ('referral_date', 'mixed date format')           |     75 |
| ('sex', 'inconsistent label')                    |    150 |
| ('smoking_status', 'inconsistent label')         |     60 |

## Letters

Letters: 100 (80 initial, 20 expedite). Styles: narrative 38, brief 32, structured 30.

Gold pathway from what the letter states:

| gold_pathway_label              |   letters |
|:--------------------------------|----------:|
| Surgery list                    |        32 |
| Ask the GP for more information |        31 |
| Keep on non-surgical care       |        15 |
| Physio first                    |        13 |
| Weight support and physio first |         9 |

Letters whose pathway differs from the full record (because facts are missing from the letter): 32

Difficulty tags:

|                 |   letters |
|:----------------|----------:|
| shorthand       |       100 |
| typos           |        98 |
| kl_from_wording |        68 |
| reordered       |        60 |
| bmi_two_values  |        52 |
| negation        |        52 |
| scanned         |        32 |
| bmi_conflict    |        29 |
| bmi_old_value   |        14 |
| oks_missing     |        14 |
| abbreviation    |        10 |
| physio_missing  |         7 |
| physio_vague    |         7 |
| xray_missing    |         6 |

Facts stated per field (out of 100):

|                      |   letters |
|:---------------------|----------:|
| name                 |       100 |
| age                  |       100 |
| sex                  |       100 |
| side                 |       100 |
| oks                  |        86 |
| oks_before           |        60 |
| kl                   |        94 |
| xray_finding         |        94 |
| physio_weeks         |        86 |
| injections           |        77 |
| bmi                  |       100 |
| night_pain           |        77 |
| lives_alone_or_carer |        77 |
| walking_aid          |        76 |
| diabetes             |       100 |
| smoking              |       100 |
| weeks_waiting        |        20 |
