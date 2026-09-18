# Parameter sensitivity

Every constant in `config.py` was chosen by judgement. This measures which of
them a reasonable disagreement would actually change, and which are decoration.

Two numbers per parameter:

- **surface** — Spearman rank correlation of the whole risk surface against
  baseline. Did the model change its mind about the city?
- **routes** — over 200 fixed school-bound trips (700–2500 m, `night` window,
  at the top of the app's λ ladder), the share of the safest route's length
  that is no longer on the safest route. Did it change its mind about *this
  walk*?

The second is the one that matters. Routing depends on the ordering of nearby
blocks, not on absolute scores, so a parameter can move every number in the
city and change no route — and a correlation on its own would hide that.

### The noise floor

The network has a 15 m median block and carries a separate unnamed footway
alongside most streets, so many "safest" routes are near-ties that flip between
equivalent pavements under any nudge. Perturbing the bandwidth by 1% — a change
nobody would argue about — moves **1.4%** of route length. That is the floor.
A parameter near it has not been shown to matter.

---

## Measured on Los Angeles

One parameter is applied at route time to the shipped surface rather than
during the fit, so it can be measured against `data/graph.bin` directly, on the
real street network, with no incident cache. These are real numbers.

`cost(block) = length × (1 + λ · risk^exponent)`

| Exponent | Route change vs config | |
|---|---|---|
| 1.0 (linear) | **13.0%** | mushy: dodges everything a little |
| 1.25 | 6.0% | |
| **1.5** | — | configured |
| 1.75 | 5.7% | |
| 2.0 | **11.1%** | avoids bad blocks harder, tolerates mild ones |

Nine times the noise floor at the ends of the range. The exponent is doing real
work, and the README's claim that a linear penalty "produces mushy routes that
dodge everything a little and nothing much" is at least measurably a different
route — 13% of the safest walk changes. Whether the 1.5 route is *better* is
not something this measures, and not something anything in this repository
currently measures.

## Measured on a synthetic fixture — not Los Angeles

Every other parameter acts during the fit, so sweeping it needs the incident
cache. `.cache/crime.json` is gitignored and `data.lacity.org` was unreachable
from the environment this work was done in, so the sweep below ran on
`pipeline/eval/fixture.py` — 40,000 synthetic incidents on the real street
network. See `holdout_results.md` for why that is stated this loudly.

**The street network and the routing are real; the incidents are not.** The
ranking is a property of this fixture, and the real one will differ. Treat it
as evidence that the sweep works and that the method is worth running, not as a
result about the model.

| Parameter | Range swept | Worst-case route change | Min rank correlation |
|---|---|---|---|
| `KERNEL_BANDWIDTH_M` | 60 to 250 (config 120) | **56.2%** | 0.8362 |
| `JUVENILE_WEIGHT` | 1.0 to 5.0 (config 3.0) | **29.6%** | 0.9746 |
| `ppct ** compression` | 1.0 to 2.5 (config 1.6) | **24.5%** | 0.9987 |
| `RECENCY_HALFLIFE_YEARS` | 1.0 to 100 (config 2.5) | **24.1%** | 0.9798 |
| `LIGHT_RADIUS_M` | 30 to 120 (config 60) | **19.2%** | 0.9969 |
| `LIGHT_MAX_CREDIT` | 0.0 to 0.5 (config 0.35) | **19.0%** | 0.9960 |
| `SEVERITY spread` | 0.0 to 2.0 (config 1.0) | **17.7%** | 0.9892 |
| `risk ** routing exponent` | 1.0 to 2.0 (config 1.5) | **13.0%** | 1.0000 |
| **CONTROL: 1% bandwidth** | 120 to 121.2 | 1.4% | 1.0000 |

`ROADTYPE_PENALTY` is swept only when `.cache/osm_ways.json` is present, since
road type is not stored in `graph.bin` and has to be recovered by re-running
the build's edge splitting. That cache was not available here, so the script
skipped it by name — and that skip path is the only part of this sweep that
ran. The reconstruction guards itself by checking the rebuilt edge count
against the shipped graph and refusing rather than guessing when they differ,
but it has not been exercised against a real cache.

### What stands out, on this fixture

**Bandwidth dominates, by a factor of two over anything else.** At 60 m the
surface only correlates 0.84 with the configured one and more than half the
safest route changes. This is the least defensible constant in `config.py`: the
README justifies 120 m as matching how coarsely LAPD records locations, which
is a reason to prefer *some* smoothing, not a derivation of that figure. On
this evidence it deserves to be fitted rather than argued — the holdout script
can do exactly that, by sweeping bandwidth and picking the value with the best
out-of-sample AUC.

**The rank correlations are nearly useless on their own.** `ppct ** compression`
correlates 0.9987 with baseline and still moves a quarter of the safest route.
A monotone transform cannot change the ranking of the surface at all, so its
correlation is ~1 by construction — but it changes the *spacing* between
scores, which is what the router integrates over length. Anyone tuning this
model by watching a correlation would conclude the exponent was inert. It is
not.

**Every parameter clears the noise floor by at least 12×.** There is no
decoration in this list. That is not the comfortable result: it means the
recommendation is sensitive to seven separate numbers that were chosen by
judgement, and only one of them has ever been checked against held-out data.

## Reproducing

```bash
python pipeline/eval/sensitivity.py                 # needs .cache/crime.json
python pipeline/eval/sensitivity.py --fast          # 25 trips, what CI runs
```

With no incident cache it still runs and reports the routing exponent alone,
skipping the rest by name.

---
Generated by `pipeline/eval/sensitivity.py`; the split between the two sections
above is editorial and will disappear once the real cache is available.
