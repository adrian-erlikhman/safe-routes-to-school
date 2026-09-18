# Holdout validation

## The Los Angeles holdout has not been run. No claim about this model's predictive skill is currently supported by anything in this repository.

That is the finding, and it is not a good one. `pipeline/eval/holdout.py` is
written, tested and ready, but it has never been pointed at Los Angeles data,
because `.cache/crime.json` is not in the repository (it is 85,634 records and
gitignored) and `data.lacity.org` was unreachable from the environment this
work was done in — the egress policy there returns 403 for it. The numbers
below are from a synthetic fixture with a known answer. **They describe the
evaluation, not the city.** Nobody should quote them, and no reader should come
away thinking the risk surface has been shown to predict anything.

Producing the real table takes two commands and about ten minutes:

```bash
python pipeline/fetch_crime.py        # ~85k records from data.lacity.org
python pipeline/eval/holdout.py       # rewrites this file
```

Run those and this file is replaced wholesale with measured results, including
the plain-language verdict at the top — which may well be a null. The script
decides that from the numbers, not from hope: it requires the model to beat
*both* unsmoothed count baselines by more than twice the standard error of the
AUC difference, in every time window, on the primary outcome. There is no
configuration of it that reports success without that.

## Why this is the honest state rather than a stub

The thing being tested is exactly the thing that is easy to fake. `validate.py`
proves A\* returns Dijkstra's cost and that the "safer" route has lower
exposure — but exposure is defined by the risk surface, so the second of those
is true by construction, and a surface of random numbers passes it. Filling
this file with plausible-looking numbers would be the same failure one level
up. So: the machinery is here, the controls prove the machinery works, and the
result is missing. It is meant to be conspicuous.

## What has been checked: the evaluation itself

The evaluation is run against two fixtures from `pipeline/eval/fixture.py`,
both 40,000 synthetic incidents over 2020–2024, laid on the real Los Angeles
street network. One has structure to find and one does not. Both are checked in
CI on every push.

### Positive control — structure exists, the holdout must find it

220 fixed hotspots persist from the training years into the test year.

| Window | Model | Top 1% | Top 5% | Top 10% | PAI@1% | PAI@5% | AUC |
|---|---|---|---|---|---|---|---|
| am | model | 17.6% | 49.7% | 64.0% | 17.62 | 9.95 | **0.795** |
| am | train_count | 14.5% | 27.5% | 31.9% | 14.48 | 5.49 | 0.619 |
| am | count_2023 | 11.1% | 15.5% | 19.9% | 11.14 | 3.11 | 0.552 |
| am | uniform | 0.8% | 5.7% | 10.4% | 0.78 | 1.14 | 0.500 |
| pm | model | 16.5% | 55.3% | 68.6% | 16.48 | 11.06 | **0.804** |
| pm | train_count | 20.6% | 38.8% | 41.9% | 20.54 | 7.75 | 0.677 |
| pm | count_2023 | 12.5% | 19.7% | 23.1% | 12.50 | 3.94 | 0.570 |
| pm | uniform | 0.6% | 4.7% | 10.2% | 0.64 | 0.93 | 0.500 |
| night | model | 16.3% | 52.3% | 66.2% | 16.29 | 10.45 | **0.786** |
| night | train_count | 21.3% | 43.4% | 47.5% | 21.29 | 8.68 | 0.705 |
| night | count_2023 | 13.8% | 23.9% | 29.2% | 13.77 | 4.78 | 0.607 |
| night | uniform | 1.0% | 5.4% | 10.8% | 1.03 | 1.07 | 0.500 |

Verdict returned: *beats both dumb baselines in all 3 windows, by 0.081 to
0.176 AUC*. The kernel finds the hotspots and the unsmoothed counts do not,
which is the whole argument for smoothing.

Two sanity checks fall out of this table. `uniform` scores AUC 0.500 to three
decimal places in every window, as it must. Its hit rate at each level lands
within noise of the level itself — 0.8% at the 1% cut — which confirms that
"top 1%" really is 1% of the network by length and the metric is not quietly
flattering itself.

### Negative control — nothing to find, the holdout must say so

Incidents fall at random every year, so 2020–2023 carries no information about
2024.

| Window | Model | AUC | Best dumb baseline | AUC |
|---|---|---|---|---|
| am | model | 0.524 | train_count | 0.502 |
| pm | model | 0.495 | train_count | 0.510 |
| night | model | 0.490 | train_count | 0.527 |

Verdict returned: *Null result: the model does not beat the dumb baselines.*

This control caught a real bug during development. An earlier version compared
AUCs against a flat 0.02 margin and reported the `am` window here as a win, off
a 0.022 gap that is pure noise at this sample size. A test that cannot fail is
not a test, and that one could not fail reliably. The threshold now has to clear
both a practical floor and twice the Hanley–McNeil standard error of the
difference, and CI asserts that this fixture still produces the word "Null".

## What the real run will and will not settle

It will answer whether the surface ranks Los Angeles blocks by where juvenile
victimisation actually happened in 2024, and whether the weighting and
smoothing beat simply counting. Worth saying in advance: **beating the count
baselines is a low bar that the model may still fail**, and if it does, the
right conclusion is that the risk surface is a restatement of the incident
record rather than a model of it. That would not make the app useless — routing
around recorded robberies is still routing around recorded robberies — but it
would mean the severity weights, the juvenile multiplier and the half-life are
decoration, and the README should say so.

It will not settle whether the model predicts *crime*, as opposed to *recorded
crime*. Both the fit and the test come from the same reporting process, with
the same variation in who calls the police. No holdout drawn from one source
can see past that, and this one does not claim to.

---
Hand-written status, because there is no measured result to generate it from.
`pipeline/eval/holdout.py` overwrites this file entirely on its first real run.
