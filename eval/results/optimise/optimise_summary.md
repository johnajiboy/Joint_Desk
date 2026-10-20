# Weekly slots: 26-week simulation

Start: the cleaned waiting list, 1040 patients needing a slot (surgery 783, physio 189, weight support and physio 68); 75 already over 52 weeks. New referrals: 26.3 a week (Poisson; the rate implied by the generator's referral dates), 638 in 26 weeks, same for every policy. Slots a week: surgery 12, physio 20, weight support 8. Counts are of patients who need one of these slots.

**Skipped** = an over-52 patient left without a slot while a slot they could use went to someone not over 52. **Weeks over-52s didn't fit** = weeks the optimiser reported infeasible (it then gave every slot it could to over-52s; the rest were listed, not skipped).

## Surgery capacity 12

|                            |   FCFS |   Priority only |   Optimiser |
|:---------------------------|-------:|----------------:|------------:|
| Over 18 weeks, end         |  555   |           583   |       559   |
| Over 52 weeks, end         |    0   |           118   |         0   |
| Over 52, weekly mean       |    5.7 |            76.5 |         5.7 |
| Over-52 patients skipped   |    0   |           181   |         0   |
| Weeks over-52s didn't fit  |    0   |             0   |         6   |
| Mean wait, surgery         |   52   |            35   |        48.9 |
| Mean wait, physio          |   20   |            20   |        20   |
| Mean wait, weight + physio |   21.6 |            21.6 |        21.5 |
| Mean OKS operated on       |   17.1 |            12.2 |        15.1 |
| Treated                    |  675   |           675   |       675   |

![Backlog](backlog.png)

In the over-52 panel FCFS and the optimiser are the same line: both clear the over-52s by week 7 and keep the count at zero (FCFS by always taking the longest wait, the optimiser by its hard rule).

![Wait by pathway](wait_by_pathway.png)

## Sensitivity: surgery capacity 8, 12, 16 a week

|   Surgery slots | Policy        |   Over 52, end |   Over 52, weekly mean |   Over 18, end |   Over-52s skipped |   Weeks infeasible |   Mean wait, surgery |   Mean OKS operated on |
|----------------:|:--------------|---------------:|-----------------------:|---------------:|-------------------:|-------------------:|---------------------:|-----------------------:|
|               8 | FCFS          |             17 |                   12.8 |            659 |                  0 |                  0 |                 59.3 |                   17.3 |
|               8 | Priority only |            149 |                   87.7 |            668 |                198 |                  0 |                 37.6 |                   11.2 |
|               8 | Optimiser     |             20 |                   14.5 |            659 |                  0 |                 22 |                 58.9 |                   16.5 |
|              12 | FCFS          |              0 |                    5.7 |            555 |                  0 |                  0 |                 52   |                   17.1 |
|              12 | Priority only |            118 |                   76.5 |            583 |                181 |                  0 |                 35   |                   12.2 |
|              12 | Optimiser     |              0 |                    5.7 |            559 |                  0 |                  6 |                 48.9 |                   15.1 |
|              16 | FCFS          |              0 |                    3.5 |            451 |                  0 |                  0 |                 46.9 |                   16.9 |
|              16 | Priority only |             95 |                   66.3 |            493 |                163 |                  0 |                 33.7 |                   12.9 |
|              16 | Optimiser     |              0 |                    3.5 |            474 |                  0 |                  4 |                 41.9 |                   14.5 |

![Sensitivity](sensitivity.png)
