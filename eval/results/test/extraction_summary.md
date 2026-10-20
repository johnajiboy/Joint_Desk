# Extraction evaluation: test set

Model: `claude-sonnet-5-5`. Letters scored: 100. Run time 92s.

| Measure | Value |
|---|---|
| Mean field accuracy | 100.0% |
| Letters with every field right | 100.0% |
| Quote hit rate | 100.0% (1623/1623) |
| Facts dropped by quote check | 0 |
| Pathway agreement | 100.0% (100/100) |
| Priority score, mean absolute difference | 0.0 |
| NHS number matched to waiting list | 100.0% |

## API usage

Recorded for 100 of 100 letters (100 read by the API in this run, the rest from the cache).

| Tokens | Total | Per letter |
|---|---:|---:|
| Input | 77,679 | 777 |
| Output (incl. thinking) | 97,347 | 973 |
| Cache read | 271,942 | 2,719 |
| Cache write | 17,358 | 174 |
| API calls | 100 | 1.00 |
| **Cost (USD)** | **$1.23** | $0.0123 |

## Per-field accuracy

| field                |   accuracy |   correct |   wrong |   missed |   extra |
|:---------------------|-----------:|----------:|--------:|---------:|--------:|
| name                 |     100.0% |       100 |       0 |        0 |       0 |
| age                  |     100.0% |       100 |       0 |        0 |       0 |
| sex                  |     100.0% |       100 |       0 |        0 |       0 |
| side                 |     100.0% |       100 |       0 |        0 |       0 |
| oks                  |     100.0% |       100 |       0 |        0 |       0 |
| oks_before           |     100.0% |       100 |       0 |        0 |       0 |
| kl                   |     100.0% |       100 |       0 |        0 |       0 |
| xray_finding         |     100.0% |       100 |       0 |        0 |       0 |
| physio_weeks         |     100.0% |       100 |       0 |        0 |       0 |
| injections           |     100.0% |       100 |       0 |        0 |       0 |
| bmi                  |     100.0% |       100 |       0 |        0 |       0 |
| night_pain           |     100.0% |       100 |       0 |        0 |       0 |
| lives_alone_or_carer |     100.0% |       100 |       0 |        0 |       0 |
| walking_aid          |     100.0% |       100 |       0 |        0 |       0 |
| diabetes             |     100.0% |       100 |       0 |        0 |       0 |
| smoking              |     100.0% |       100 |       0 |        0 |       0 |
| weeks_waiting        |     100.0% |       100 |       0 |        0 |       0 |

## Pathway: gold vs from extraction

| gold                            |   Ask the GP for more information |   Keep on non-surgical care |   Physio first |   Surgery list |   Weight support and physio first |
|:--------------------------------|----------------------------------:|----------------------------:|---------------:|---------------:|----------------------------------:|
| Ask the GP for more information |                                31 |                           0 |              0 |              0 |                                 0 |
| Keep on non-surgical care       |                                 0 |                          15 |              0 |              0 |                                 0 |
| Physio first                    |                                 0 |                           0 |             13 |              0 |                                 0 |
| Surgery list                    |                                 0 |                           0 |              0 |             32 |                                 0 |
| Weight support and physio first |                                 0 |                           0 |              0 |              0 |                                 9 |

## By difficulty tag

| tag             |   letters |   pathway agreement |   all fields right |
|:----------------|----------:|--------------------:|-------------------:|
| abbreviation    |        10 |              100.0% |             100.0% |
| bmi_conflict    |        29 |              100.0% |             100.0% |
| bmi_old_value   |        14 |              100.0% |             100.0% |
| bmi_two_values  |        52 |              100.0% |             100.0% |
| kl_from_wording |        68 |              100.0% |             100.0% |
| negation        |        52 |              100.0% |             100.0% |
| oks_missing     |        14 |              100.0% |             100.0% |
| physio_missing  |         7 |              100.0% |             100.0% |
| physio_vague    |         7 |              100.0% |             100.0% |
| reordered       |        60 |              100.0% |             100.0% |
| scanned         |        32 |              100.0% |             100.0% |
| shorthand       |       100 |              100.0% |             100.0% |
| typos           |        98 |              100.0% |             100.0% |
| xray_missing    |         6 |              100.0% |             100.0% |

## By letter style

| style      |   letters |   pathway agreement |   all fields right |
|:-----------|----------:|--------------------:|-------------------:|
| brief      |        32 |              100.0% |             100.0% |
| narrative  |        38 |              100.0% |             100.0% |
| structured |        30 |              100.0% |             100.0% |
