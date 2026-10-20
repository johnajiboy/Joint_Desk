# Extraction: dev vs held-out test

Model: `claude-sonnet-5-5`. The prompt was tuned on the dev set only; the test set uses new patients and harder letters (shorthand, typos, reordering, scanned text).

| Measure                              | Dev (150, tuned on)   | Test (100, held out, hard)   |
|:-------------------------------------|:----------------------|:-----------------------------|
| Letters                              | 150                   | 100                          |
| Mean field accuracy                  | 100.0%                | 100.0%                       |
| Letters with every field right       | 99.3%                 | 100.0%                       |
| Quote hit rate                       | 100.0%                | 100.0%                       |
| Facts dropped by quote check         | 1                     | 0                            |
| Pathway agreement                    | 100.0%                | 100.0%                       |
| Priority score, mean abs. difference | 0.0                   | 0.0                          |
| NHS number matched                   | 100.0%                | 100.0%                       |
| API cost                             | not recorded          | $1.23 (100 letters)          |

## Per-field accuracy

|                      |    Dev |   Test |   Change |
|:---------------------|-------:|-------:|---------:|
| name                 | 100.0% | 100.0% |     0.0% |
| age                  | 100.0% | 100.0% |     0.0% |
| sex                  | 100.0% | 100.0% |     0.0% |
| side                 | 100.0% | 100.0% |     0.0% |
| oks                  | 100.0% | 100.0% |     0.0% |
| oks_before           | 100.0% | 100.0% |     0.0% |
| kl                   |  99.3% | 100.0% |     0.7% |
| xray_finding         | 100.0% | 100.0% |     0.0% |
| physio_weeks         | 100.0% | 100.0% |     0.0% |
| injections           | 100.0% | 100.0% |     0.0% |
| bmi                  | 100.0% | 100.0% |     0.0% |
| night_pain           | 100.0% | 100.0% |     0.0% |
| lives_alone_or_carer | 100.0% | 100.0% |     0.0% |
| walking_aid          | 100.0% | 100.0% |     0.0% |
| diabetes             | 100.0% | 100.0% |     0.0% |
| smoking              | 100.0% | 100.0% |     0.0% |
| weeks_waiting        | 100.0% | 100.0% |     0.0% |
