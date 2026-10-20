# Extraction evaluation: dev set

Model: `claude-sonnet-5-5`. Letters scored: 150. Run time 0s.

| Measure | Value |
|---|---|
| Mean field accuracy | 100.0% |
| Letters with every field right | 99.3% |
| Quote hit rate | 100.0% (2410/2411) |
| Facts dropped by quote check | 1 |
| Pathway agreement | 100.0% (150/150) |
| Priority score, mean absolute difference | 0.0 |
| NHS number matched to waiting list | 100.0% |

## Per-field accuracy

| field                |   accuracy |   correct |   wrong |   missed |   extra |
|:---------------------|-----------:|----------:|--------:|---------:|--------:|
| name                 |     100.0% |       150 |       0 |        0 |       0 |
| age                  |     100.0% |       150 |       0 |        0 |       0 |
| sex                  |     100.0% |       150 |       0 |        0 |       0 |
| side                 |     100.0% |       150 |       0 |        0 |       0 |
| oks                  |     100.0% |       150 |       0 |        0 |       0 |
| oks_before           |     100.0% |       150 |       0 |        0 |       0 |
| kl                   |      99.3% |       149 |       1 |        0 |       0 |
| xray_finding         |     100.0% |       150 |       0 |        0 |       0 |
| physio_weeks         |     100.0% |       150 |       0 |        0 |       0 |
| injections           |     100.0% |       150 |       0 |        0 |       0 |
| bmi                  |     100.0% |       150 |       0 |        0 |       0 |
| night_pain           |     100.0% |       150 |       0 |        0 |       0 |
| lives_alone_or_carer |     100.0% |       150 |       0 |        0 |       0 |
| walking_aid          |     100.0% |       150 |       0 |        0 |       0 |
| diabetes             |     100.0% |       150 |       0 |        0 |       0 |
| smoking              |     100.0% |       150 |       0 |        0 |       0 |
| weeks_waiting        |     100.0% |       150 |       0 |        0 |       0 |

## Pathway: gold vs from extraction

| gold                            |   Ask the GP for more information |   Keep on non-surgical care |   Physio first |   Surgery list |   Weight support and physio first |
|:--------------------------------|----------------------------------:|----------------------------:|---------------:|---------------:|----------------------------------:|
| Ask the GP for more information |                                52 |                           0 |              0 |              0 |                                 0 |
| Keep on non-surgical care       |                                 0 |                          24 |              0 |              0 |                                 0 |
| Physio first                    |                                 0 |                           0 |             19 |              0 |                                 0 |
| Surgery list                    |                                 0 |                           0 |              0 |             42 |                                 0 |
| Weight support and physio first |                                 0 |                           0 |              0 |              0 |                                13 |

## By difficulty tag

| tag             |   letters |   pathway agreement |   all fields right |
|:----------------|----------:|--------------------:|-------------------:|
| abbreviation    |        13 |              100.0% |             100.0% |
| bmi_conflict    |        17 |              100.0% |             100.0% |
| bmi_two_values  |        31 |              100.0% |             100.0% |
| kl_from_wording |       103 |              100.0% |              99.0% |
| negation        |        66 |              100.0% |              98.5% |
| oks_missing     |        26 |              100.0% |             100.0% |
| physio_missing  |         4 |              100.0% |             100.0% |
| physio_vague    |        12 |              100.0% |             100.0% |
| xray_missing    |        14 |              100.0% |             100.0% |

## By letter style

| style      |   letters |   pathway agreement |   all fields right |
|:-----------|----------:|--------------------:|-------------------:|
| brief      |        41 |              100.0% |             100.0% |
| narrative  |        62 |              100.0% |             100.0% |
| structured |        47 |              100.0% |              97.9% |
