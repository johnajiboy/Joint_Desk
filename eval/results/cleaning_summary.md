# Cleaning summary

Raw rows: 1,518. Patients after cleaning: 1,500. Changes made: 496.

| Check | Result |
|---|---|
| Duplicate referrals removed | 18 of 18 logged (same patients) |
| Logged cell problems | 667 |
| Fixed (clean value = true value) | 398 (59.7%) |
| Set missing (true value can't be recovered) | 269 (40.3%) |
| Left wrong | 0 |
| Changes the log doesn't explain | 0 |
| Pathway from cleaned data = pathway from full record | 88.2% |

## Logged problems by issue

| field          | issue                                 |   logged |   fixed |   set missing |   wrong |
|:---------------|:--------------------------------------|---------:|--------:|--------------:|--------:|
| age            | impossible value                      |       15 |      15 |             0 |       0 |
| bmi            | decimal point lost (e.g. 31.4 -> 314) |       22 |      22 |             0 |       0 |
| bmi            | missing                               |       45 |       0 |            45 |       0 |
| kl_grade       | missing                               |       30 |       0 |            30 |       0 |
| laterality     | inconsistent label                    |      120 |     120 |             0 |       0 |
| oks            | missing                               |       90 |       0 |            90 |       0 |
| oks            | out of range (OKS is 0-48)            |       15 |       0 |            15 |       0 |
| physio_weeks   | free text in numeric field            |       45 |       0 |            45 |       0 |
| referral_date  | mixed date format                     |       75 |      75 |             0 |       0 |
| sex            | inconsistent label                    |      150 |     150 |             0 |       0 |
| smoking_status | inconsistent label                    |       60 |      16 |            44 |       0 |

## Every cell against the truth

Missing = the truth has a value the cleaned table doesn't (it was lost in the raw file).

| field          |   cells |   match truth |   missing |   wrong | wrong patients   |
|:---------------|--------:|--------------:|----------:|--------:|:-----------------|
| nhs_number     |    1500 |          1500 |         0 |       0 |                  |
| title          |    1500 |          1500 |         0 |       0 |                  |
| first_name     |    1500 |          1500 |         0 |       0 |                  |
| surname        |    1500 |          1500 |         0 |       0 |                  |
| sex_code       |    1500 |          1500 |         0 |       0 |                  |
| sex            |    1500 |          1500 |         0 |       0 |                  |
| date_of_birth  |    1500 |          1500 |         0 |       0 |                  |
| age            |    1500 |          1500 |         0 |       0 |                  |
| laterality     |    1500 |          1500 |         0 |       0 |                  |
| referral_date  |    1500 |          1500 |         0 |       0 |                  |
| weeks_waiting  |    1500 |          1500 |         0 |       0 |                  |
| kl_grade       |    1500 |          1470 |        30 |       0 |                  |
| oks            |    1500 |          1395 |       105 |       0 |                  |
| oks_before     |    1500 |          1500 |         0 |       0 |                  |
| physio_weeks   |    1500 |          1455 |        45 |       0 |                  |
| injections     |    1500 |          1500 |         0 |       0 |                  |
| bmi            |    1500 |          1455 |        45 |       0 |                  |
| smoking_status |    1500 |          1456 |        44 |       0 |                  |
| diabetes       |    1500 |          1500 |         0 |       0 |                  |
| night_pain     |    1500 |          1500 |         0 |       0 |                  |
| lives_alone    |    1500 |          1500 |         0 |       0 |                  |
| carer          |    1500 |          1500 |         0 |       0 |                  |

## Missing after cleaning

|                |   patients |
|:---------------|-----------:|
| oks            |        105 |
| kl_grade       |         30 |
| bmi            |         45 |
| physio_weeks   |         45 |
| smoking_status |         44 |

## Pathway: full record vs cleaned data

Patients with a missing score, X-ray grade or physiotherapy history go to "Ask the GP".

| full record                     |   Ask the GP for more information |   Keep on non-surgical care |   Physio first |   Surgery list |   Weight support and physio first |
|:--------------------------------|----------------------------------:|----------------------------:|---------------:|---------------:|----------------------------------:|
| Keep on non-surgical care       |                                43 |                         284 |              0 |              0 |                                 0 |
| Physio first                    |                                28 |                           0 |            188 |              0 |                                 0 |
| Surgery list                    |                                97 |                           0 |              0 |            783 |                                 0 |
| Weight support and physio first |                                 8 |                           0 |              1 |              0 |                                68 |

## Bands

| OKS band           |   patients |
|:-------------------|-----------:|
| severe             |        649 |
| moderate to severe |        620 |
| mild to moderate   |        120 |
| missing            |        105 |
| satisfactory       |          6 |

| BMI category   |   patients |
|:---------------|-----------:|
| Obese I        |        488 |
| Overweight     |        439 |
| Obese II       |        264 |
| Healthy        |        151 |
| Obese III      |        113 |
| missing        |         45 |

| Wait band     |   patients |
|:--------------|-----------:|
| 0-18 weeks    |        749 |
| 19-52 weeks   |        643 |
| Over 52 weeks |        108 |
