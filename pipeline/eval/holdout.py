"""Does the risk surface predict crime it has never seen?

`validate.py` proves the router finds the cheapest path under the model's own
cost. That is a statement about the search, not about the model: exposure is
defined by the risk surface, so "the safer route has lower exposure" is true by
construction and a surface of random numbers would satisfy it exactly as well.

This asks the question that is not circular. Fit the kernel on 2020-2023 only,
then score how well the resulting surface ranks blocks by where 2024 incidents
actually happened -- data the fit never touched -- against three baselines dumb
enough that beating them has to mean something:

  uniform      every block equally risky. The floor. AUC 0.5 by construction.
  train count  incidents per block over the training years, unweighted and
               unsmoothed. Tests whether severity, juvenile and recency
               weighting plus the Gaussian kernel earn their complexity.
  2023 count   last training year only, unsmoothed. Tests whether five years
               of history beat simply asking what happened most recently.

Reported per time bucket, because a surface that is only predictive at night
is a different product from one that works on the walk home.

  python pipeline/eval/holdout.py                    # writes holdout_results.md
  python pipeline/eval/holdout.py --fast             # coarser, for CI
"""
import argparse, datetime as dt, json, math, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
import build_graph as B
from eval import common as K

TRAIN_START = "2020-01-01"
TRAIN_END   = "2023-12-31"
TEST_YEAR   = 2024

# Recency decay must be anchored to the end of training, not to config's 2025.
# Anchoring at 2025 would let the fit lean on how close each incident is to the
# test year, which is a fact about the future the model is not allowed to know.
TRAIN_REFERENCE_YEAR = 2024.0

FRACS = (0.01, 0.05, 0.10)


def date_to_year(s):
    d = dt.date.fromisoformat(s)
    return d.year + ((d.month - 1) * 30.44 + d.day) / 365.25


def build_models(g, inc_train, samples, grid, fast=False):
    """The model surface plus the three baselines, per bucket."""
    models = {}

    w = K.weights(inc_train, reference_year=TRAIN_REFERENCE_YEAR)
    raw = K.kernel_surface(grid, samples, inc_train, w)
    models["model"] = K.pooled_percentile(raw)

    models["uniform"] = {b: np.zeros(g.nE) for b in B.BUCKET_ORDER}

    # Unsmoothed counts: snap each training incident to its nearest block and
    # count. No severity, no juvenile weight, no recency, no kernel.
    ei, hit = g.snap(inc_train["x"], inc_train["y"])
    for name, sel in (("train_count", np.ones(len(inc_train), bool)),
                      ("count_2023", inc_train["year"] == 2023)):
        out = {}
        for b in B.BUCKET_ORDER:
            m = hit & sel & K.bucket_mask(inc_train, b)
            c = np.bincount(ei[m], minlength=g.nE).astype(float)
            out[b] = c / B.BUCKET_HOURS[b]
        models[name] = out

    # The shipped surface, for reference only. It was fitted on 2020-2024, so
    # it has seen the test year: it is an in-sample ceiling, not a competitor.
    models["shipped (in-sample)"] = {
        b: g.er[:, k].astype(float) / 255.0
        for k, b in enumerate(g.meta["buckets"])}
    return models


def evaluate(g, models, inc_test, rng):
    """Every model against every bucket, for both outcomes."""
    ei, hit = g.snap(inc_test["x"], inc_test["y"])
    length = g.ed
    rows, coverage = [], dict(snapped=int(hit.sum()), total=int(len(inc_test)))

    for outcome, sel in (("juvenile", inc_test["juv"]),
                         ("all", np.ones(len(inc_test), bool))):
        for b in B.BUCKET_ORDER:
            m = hit & sel & K.bucket_mask(inc_test, b)
            counts = np.bincount(ei[m], minlength=g.nE).astype(float)
            label = counts > 0
            n_inc, n_blocks = int(m.sum()), int(label.sum())
            for name, surf in models.items():
                s = surf[b]
                auc = K.roc_auc(s, label) if n_blocks else float("nan")
                hp = K.hit_rate_and_pai(s, length, counts, FRACS, rng=rng)
                rows.append(dict(outcome=outcome, bucket=b, model=name,
                                 incidents=n_inc, blocks=n_blocks,
                                 negatives=g.nE - n_blocks, auc=auc, hits=hp))
    return rows, coverage


# ------------------------------------------------------------------ reporting
def fmt_table(rows, outcome, order):
    out = ["| Window | Model | Top 1% | Top 5% | Top 10% | PAI@1% | PAI@5% | AUC |",
           "|---|---|---|---|---|---|---|---|"]
    for b in B.BUCKET_ORDER:
        for name in order:
            r = next((r for r in rows if r["outcome"] == outcome
                      and r["bucket"] == b and r["model"] == name), None)
            if r is None:
                continue
            h = {x["frac"]: x for x in r["hits"]}
            out.append(
                f"| {b} | {name} | {h[0.01]['hit_rate']*100:.1f}% | "
                f"{h[0.05]['hit_rate']*100:.1f}% | {h[0.10]['hit_rate']*100:.1f}% | "
                f"{h[0.01]['pai']:.2f} | {h[0.05]['pai']:.2f} | {r['auc']:.3f} |")
    return "\n".join(out)


# A separation has to clear two bars, because either alone is easy to fool.
# MIN_MARGIN is practical: a hundredth of AUC changes nobody's walk. The
# standard-error test is statistical: with a few hundred positive blocks per
# window, two points of AUC is comfortably inside the noise, and a bare
# threshold would score coin flips as wins. Verified against the null fixture
# in `fixture.py`, where an earlier bare-threshold version claimed one.
MIN_MARGIN = 0.02
SE_MULTIPLE = 2.0


def verdict(rows):
    """Plain language, decided by the numbers rather than by hope.

    The model has to beat *both* dumb baselines on AUC in every bucket for the
    primary outcome. Beating uniform alone is not a finding: uniform is 0.5.
    """
    prim = [r for r in rows if r["outcome"] == "juvenile"]
    beats, ties, total = [], [], 0
    for b in B.BUCKET_ORDER:
        row = lambda n: next((r for r in prim
                              if r["bucket"] == b and r["model"] == n), None)
        rm = row("model")
        if rm is None or not np.isfinite(rm["auc"]):
            continue
        total += 1
        best = max((row(n) for n in ("train_count", "count_2023")),
                   key=lambda r: (r["auc"] if r and np.isfinite(r["auc"])
                                  else -1.0))
        margin = rm["auc"] - best["auc"]
        npos, nneg = rm["blocks"], rm["negatives"]
        # Treat the two AUCs as independent. They share labels so they are in
        # fact correlated, which makes this overstate the noise -- erring
        # towards calling a real win a tie rather than the other way round.
        se = math.hypot(K.auc_se(rm["auc"], npos, nneg),
                        K.auc_se(best["auc"], npos, nneg))
        need = max(MIN_MARGIN, SE_MULTIPLE * se) if np.isfinite(se) \
            else MIN_MARGIN
        rec = (b, rm["auc"], best["model"], best["auc"], margin, need)
        (beats if margin > need else ties).append(rec)
    return beats, ties, total


def write_report(path, rows, coverage, meta, note):
    beats, ties, total = verdict(rows)
    won = len(beats)
    lines = ["# Holdout validation", ""]

    if note:
        lines += [f"> **{note}**", ""]

    if total == 0:
        head = ("**No verdict.** The test year holds no juvenile-victim "
                "incidents that snap to a block, so nothing was measured.")
    elif won == total:
        head = (f"**The model beats both dumb baselines in all {total} time "
                f"windows** on the primary outcome, by "
                f"{min(x[4] for x in beats):.3f} to "
                f"{max(x[4] for x in beats):.3f} AUC.")
    elif won == 0:
        head = (f"**Null result: the model does not beat the dumb baselines.** "
                f"In all {total} time windows, an unsmoothed count of past "
                f"incidents ranks blocks at least as well as the weighted "
                f"kernel does. The severity weights, the juvenile multiplier, "
                f"the recency half-life and the 120 m kernel are not earning "
                f"their complexity on this test. Treat the risk surface as a "
                f"restatement of where incidents were recorded, not as a "
                f"model that adds anything to them.")
    else:
        head = (f"**Mixed: the model beats both dumb baselines in {won} of "
                f"{total} time windows** and is within noise of them in the "
                f"rest. Read the per-window table before quoting a headline.")
    lines += [head, ""]
    lines += [
        f"Fitted on incidents from {TRAIN_START} to {TRAIN_END}; scored "
        f"against {TEST_YEAR}. The fit never sees {TEST_YEAR}, and its recency "
        f"decay is anchored at {TRAIN_REFERENCE_YEAR:.0f} rather than "
        f"config's {C.REFERENCE_YEAR:.0f} so it cannot lean on how close an "
        f"incident sits to the test year.", ""]
    lines += ["```",
              f"train incidents   {meta['n_train']:,}",
              f"test incidents    {meta['n_test']:,}  "
              f"({meta['n_test_juv']:,} juvenile-victim)",
              f"snapped to block  {coverage['snapped']:,} of "
              f"{coverage['total']:,} "
              f"({100*coverage['snapped']/max(coverage['total'],1):.1f}% "
              f"within {K.SNAP_RADIUS_M:.0f} m)",
              f"blocks            {meta['n_edges']:,}",
              f"kernel bandwidth  {C.KERNEL_BANDWIDTH_M:.0f} m",
              "```", ""]

    order = ["model", "train_count", "count_2023", "uniform",
             "shipped (in-sample)"]
    lines += ["## Primary outcome: juvenile-victim street offences, "
              f"{TEST_YEAR}", "",
              "Hit rate is the share of test incidents falling on the "
              "highest-scoring blocks, where *top 1%* means the worst 1% of "
              "the network **by length**, not by block count. PAI is that hit "
              "rate over the length share -- PAI 10 at the 1% level means the "
              "flagged 1% of pavement caught 10% of what happened. AUC is the "
              "chance a block that saw an incident outranks one that did not.",
              "", fmt_table(rows, "juvenile", order), ""]
    lines += [f"## Secondary outcome: all filtered incidents, {TEST_YEAR}", "",
              fmt_table(rows, "all", order), ""]
    lines += ["## How to read the reference row", "",
              "`shipped (in-sample)` is the surface in `data/graph.bin`. It "
              "was fitted on 2020-2024, so it has already seen the test year "
              "and is not a competitor -- it is the ceiling a leak-free fit is "
              "being asked to approach. It also carries the streetlight credit "
              "and road-type penalty, which the refit does not, because those "
              "need caches this evaluation deliberately does not require.", ""]
    if ties:
        lines += ["## Where it does not separate", ""]
        for b, m, bname, bauc, margin, need in ties:
            lines.append(f"- **{b}**: model AUC {m:.3f} against {bauc:.3f} for "
                         f"`{bname}`, the better dumb baseline. Margin "
                         f"{margin:+.3f}, and this window needs {need:.3f} to "
                         f"clear both the practical floor and twice the "
                         f"standard error.")
        lines.append("")
    lines += ["---", f"Generated by `pipeline/eval/holdout.py` on "
              f"{dt.date.today().isoformat()}.", ""]
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--incidents", default=None,
                    help="path to a crime.json (default .cache/crime.json)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--fast", action="store_true",
                    help="coarser sampling; for CI, not for quoting")
    ap.add_argument("--note", default="",
                    help="banner printed at the top of the report")
    a = ap.parse_args()

    t0 = time.time()
    g = K.Graph()
    inc = K.load_incidents(a.incidents)
    print(f"{len(inc):,} incidents, {g.nE:,} blocks", flush=True)

    lo, hi = date_to_year(TRAIN_START), date_to_year(TRAIN_END)
    train = inc[(inc["day"] >= lo) & (inc["day"] <= hi)]
    test = inc[inc["year"] == TEST_YEAR]
    print(f"train {len(train):,}  test {len(test):,} "
          f"({int(test['juv'].sum()):,} juvenile)", flush=True)
    if not len(train) or not len(test):
        raise SystemExit("train or test split is empty -- check the date range")

    step = B.SAMPLE_STEP * (2.0 if a.fast else 1.0)
    samples = g.samples(step=step)
    grid = B.Grid()
    print(f"  {len(samples[0]):,} sample points @ {step:.0f} m", flush=True)

    models = build_models(g, train, samples, grid, fast=a.fast)
    rng = np.random.default_rng(20240101)
    rows, coverage = evaluate(g, models, test, rng)

    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "holdout_results.md")
    meta = dict(n_train=len(train), n_test=len(test),
                n_test_juv=int(test["juv"].sum()), n_edges=g.nE)
    head = write_report(out, rows, coverage, meta, a.note)

    print()
    print(fmt_table(rows, "juvenile",
                    ["model", "train_count", "count_2023", "uniform"]))
    print()
    print(head.replace("**", ""))
    print(f"\nwrote {out}  ({time.time()-t0:.0f}s)")
    with open(out.replace(".md", ".json"), "w") as f:
        json.dump(dict(rows=rows, coverage=coverage, meta=meta), f, indent=1,
                  default=float)


if __name__ == "__main__":
    main()
