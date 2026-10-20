# Decision tree vs expert rules

Truth check: `true_pathway` in patients_clean.csv equals `rules.decide()` (pathway and rule) for **1500 of 1500** patients.

The label is the pathway the rules give on the cleaned table, so agreement shows how much of the expert rules the tree recovers from data. Missing OKS, X-ray grade or physio goes to review before the tree, as in rule 1. Split: 1050 train / 450 test, stratified, seed 2026; max_depth 2-8 and min_samples_leaf 1-20 tuned by 5-fold CV on the training split.

| | Raw values | Discretised (OKS bands, BMI categories, wait bands) |
|---|---|---|
| Best max_depth / min_samples_leaf | 5 / 1 | 5 / 1 |
| CV accuracy (train, complete records) | 99.9% | 97.6% |
| Depth / leaves | 5 / 10 | 5 / 11 |
| Agreement with rules, test split | **100.0%** (450) | **98.2%** (450) |
| Agreement, complete records only | 100.0% (397) | 98.0% (397) |
| Disagreements | 0 | 8 |

## Continuous features

### Per pathway (rules as reference)

| pathway                         |   precision |   recall |    f1 |   patients |
|:--------------------------------|------------:|---------:|------:|-----------:|
| Surgery list                    |       1.000 |    1.000 | 1.000 |        235 |
| Physio first                    |       1.000 |    1.000 | 1.000 |         57 |
| Weight support and physio first |       1.000 |    1.000 | 1.000 |         20 |
| Keep on non-surgical care       |       1.000 |    1.000 | 1.000 |         85 |
| Ask the GP for more information |       1.000 |    1.000 | 1.000 |         53 |

### Confusion matrix

| rules                           |   Surgery list |   Physio first |   Weight support and physio first |   Keep on non-surgical care |   Ask the GP for more information |
|:--------------------------------|---------------:|---------------:|----------------------------------:|----------------------------:|----------------------------------:|
| Surgery list                    |            235 |              0 |                                 0 |                           0 |                                 0 |
| Physio first                    |              0 |             57 |                                 0 |                           0 |                                 0 |
| Weight support and physio first |              0 |              0 |                                20 |                           0 |                                 0 |
| Keep on non-surgical care       |              0 |              0 |                                 0 |                          85 |                                 0 |
| Ask the GP for more information |              0 |              0 |                                 0 |                           0 |                                53 |

### Rule thresholds vs learned splits

A split at `<= t` is the same cut as the rule when t lies between the rule value and the next possible value (whole numbers; BMI to 0.1).

| rule                                       | short                   | feature      | rule_cut   |   tree_nearest | tree_splits   | same_cut   |
|:-------------------------------------------|:------------------------|:-------------|:-----------|---------------:|:--------------|:-----------|
| OKS 26 or less (with KL 3+) -> surgery     | OKS ≤ 26 → surgery      | oks          | <= 26      |          26.5  | 19.5, 26.5    | True       |
| OKS above 19 (severe 0-19) -> physio first | OKS > 19 → physio first | oks          | <= 19      |          19.5  | 19.5, 26.5    | True       |
| KL grade 3 or more                         | KL ≥ 3                  | kl_grade     | <= 2       |           2.5  | 2.5           | True       |
| BMI 35 or more -> weight support           | BMI ≥ 35                | bmi          | <= 34.9    |          34.95 | 34.35, 34.95  | True       |
| Physio under 6 weeks                       | Physio < 6 weeks        | physio_weeks | <= 5       |           5.5  | 5.5           | True       |
| OKS drop of 5 or more                      | OKS drop ≥ 5            | oks_drop     | <= 4       |           4    | 4             | True       |

Extra splits that are not rule cuts: bmi <= 34.35. The tree splits halfway between the nearest patients either side; where nobody sits near the rule's value, any cut in that gap fits the data equally well, so these agree with the rules on every patient but are not the rules' numbers.

### Feature importance

|                      |   importance |
|:---------------------|-------------:|
| kl_grade             |        0.338 |
| physio_weeks         |        0.269 |
| oks                  |        0.222 |
| bmi                  |        0.130 |
| oks_drop             |        0.041 |
| weeks_waiting        |        0.000 |
| night_pain           |        0.000 |
| lives_alone_or_carer |        0.000 |
| age                  |        0.000 |
| female               |        0.000 |

### Learned tree (`tree_rules.txt`)

```
|--- kl_grade <= 2.50
|   |--- physio_weeks <= 5.50
|   |   |--- oks <= 19.50
|   |   |   |--- class: non_surgical
|   |   |--- oks >  19.50
|   |   |   |--- bmi <= 34.35
|   |   |   |   |--- class: physio
|   |   |   |--- bmi >  34.35
|   |   |   |   |--- class: weight_physio
|   |--- physio_weeks >  5.50
|   |   |--- class: non_surgical
|--- kl_grade >  2.50
|   |--- oks <= 19.50
|   |   |--- class: surgery
|   |--- oks >  19.50
|   |   |--- physio_weeks <= 5.50
|   |   |   |--- bmi <= 34.95
|   |   |   |   |--- class: physio
|   |   |   |--- bmi >  34.95
|   |   |   |   |--- class: weight_physio
|   |   |--- physio_weeks >  5.50
|   |   |   |--- oks <= 26.50
|   |   |   |   |--- class: surgery
|   |   |   |--- oks >  26.50
|   |   |   |   |--- oks_drop <= 4.00
|   |   |   |   |   |--- class: non_surgical
|   |   |   |   |--- oks_drop >  4.00
|   |   |   |   |   |--- class: surgery
```

## Discretised features

### Per pathway (rules as reference)

| pathway                         |   precision |   recall |    f1 |   patients |
|:--------------------------------|------------:|---------:|------:|-----------:|
| Surgery list                    |       0.967 |    1.000 | 0.983 |        235 |
| Physio first                    |       1.000 |    1.000 | 1.000 |         57 |
| Weight support and physio first |       1.000 |    1.000 | 1.000 |         20 |
| Keep on non-surgical care       |       1.000 |    0.906 | 0.951 |         85 |
| Ask the GP for more information |       1.000 |    1.000 | 1.000 |         53 |

### Confusion matrix

| rules                           |   Surgery list |   Physio first |   Weight support and physio first |   Keep on non-surgical care |   Ask the GP for more information |
|:--------------------------------|---------------:|---------------:|----------------------------------:|----------------------------:|----------------------------------:|
| Surgery list                    |            235 |              0 |                                 0 |                           0 |                                 0 |
| Physio first                    |              0 |             57 |                                 0 |                           0 |                                 0 |
| Weight support and physio first |              0 |              0 |                                20 |                           0 |                                 0 |
| Keep on non-surgical care       |              8 |              0 |                                 0 |                          77 |                                 0 |
| Ask the GP for more information |              0 |              0 |                                 0 |                           0 |                                53 |

### Rule thresholds vs learned splits

A split at `<= t` is the same cut as the rule when t lies between the rule value and the next possible value (whole numbers; BMI to 0.1). Band splits are shown as the raw value at the band edge.

| rule                                       | short                   | feature      | rule_cut   |   tree_nearest | tree_splits   | same_cut   |
|:-------------------------------------------|:------------------------|:-------------|:-----------|---------------:|:--------------|:-----------|
| OKS 26 or less (with KL 3+) -> surgery     | OKS ≤ 26 → surgery      | oks          | <= 26      |           29   | 19, 29        | False      |
| OKS above 19 (severe 0-19) -> physio first | OKS > 19 → physio first | oks          | <= 19      |           19   | 19, 29        | True       |
| KL grade 3 or more                         | KL ≥ 3                  | kl_grade     | <= 2       |            2.5 | 2.5           | True       |
| BMI 35 or more -> weight support           | BMI ≥ 35                | bmi          | <= 34.9    |           34.9 | 34.9          | True       |
| Physio under 6 weeks                       | Physio < 6 weeks        | physio_weeks | <= 5       |            5.5 | 5.5           | True       |
| OKS drop of 5 or more                      | OKS drop ≥ 5            | oks_drop     | <= 4       |            4   | 2.5, 4        | True       |

Extra splits that are not rule cuts: oks <= 29.0, oks_drop <= 2.5. A band split can only fall on a band edge, so the OKS band edge at 29 stands in for the rules' 26: patients with OKS 27-29 and KL 3+ are where the 8 disagreements come from. Any other extra split either leads to the same pathway on both sides or sits in a gap between patients.

### Feature importance

|                      |   importance |
|:---------------------|-------------:|
| kl_grade             |        0.362 |
| physio_weeks         |        0.288 |
| oks_band             |        0.190 |
| bmi_category         |        0.140 |
| oks_drop             |        0.021 |
| wait_band            |        0.000 |
| night_pain           |        0.000 |
| lives_alone_or_carer |        0.000 |
| age                  |        0.000 |
| female               |        0.000 |

### Learned tree (`tree_rules_discretised.txt`)

```
|--- kl_grade <= 2.50
|   |--- physio_weeks <= 5.50
|   |   |--- oks_band <= 0.50
|   |   |   |--- class: non_surgical
|   |   |--- oks_band >  0.50
|   |   |   |--- bmi_category <= 4.50
|   |   |   |   |--- class: physio
|   |   |   |--- bmi_category >  4.50
|   |   |   |   |--- class: weight_physio
|   |--- physio_weeks >  5.50
|   |   |--- class: non_surgical
|--- kl_grade >  2.50
|   |--- oks_band <= 0.50
|   |   |--- class: surgery
|   |--- oks_band >  0.50
|   |   |--- physio_weeks <= 5.50
|   |   |   |--- bmi_category <= 4.50
|   |   |   |   |--- class: physio
|   |   |   |--- bmi_category >  4.50
|   |   |   |   |--- class: weight_physio
|   |   |--- physio_weeks >  5.50
|   |   |   |--- oks_band <= 1.50
|   |   |   |   |--- oks_drop <= 2.50
|   |   |   |   |   |--- class: surgery
|   |   |   |   |--- oks_drop >  2.50
|   |   |   |   |   |--- class: surgery
|   |   |   |--- oks_band >  1.50
|   |   |   |   |--- oks_drop <= 4.00
|   |   |   |   |   |--- class: non_surgical
|   |   |   |   |--- oks_drop >  4.00
|   |   |   |   |   |--- class: surgery
```

## Disagreements on the test split

| patient_id   |   oks |   kl_grade |   bmi |   physio_weeks |   weeks_waiting |   oks_drop | rules                     |   rule | tree         | model       |
|:-------------|------:|-----------:|------:|---------------:|----------------:|-----------:|:--------------------------|-------:|:-------------|:------------|
| KP01346      |    28 |          4 |  33.8 |             10 |              13 |          1 | Keep on non-surgical care |      6 | Surgery list | discretised |
| KP00344      |    27 |          4 |  36.6 |             17 |              14 |          1 | Keep on non-surgical care |      6 | Surgery list | discretised |
| KP01229      |    28 |          3 |  35.8 |              9 |               8 |          4 | Keep on non-surgical care |      6 | Surgery list | discretised |
| KP01329      |    28 |          3 |  32.1 |              6 |               3 |          3 | Keep on non-surgical care |      6 | Surgery list | discretised |
| KP00283      |    28 |          4 |  31.4 |             11 |               3 |         -1 | Keep on non-surgical care |      6 | Surgery list | discretised |
| KP00200      |    27 |          3 |  32.7 |             18 |              11 |          0 | Keep on non-surgical care |      6 | Surgery list | discretised |
| KP00166      |    27 |          3 |  32.4 |             11 |              24 |         -4 | Keep on non-surgical care |      6 | Surgery list | discretised |
| KP01307      |    29 |          3 |  27.1 |             10 |              30 |          1 | Keep on non-surgical care |      6 | Surgery list | discretised |
