"""Shared machinery for the holdout and sensitivity evaluations.

Two design choices worth stating up front.

**The graph is read from `data/graph.bin`, not rebuilt.** The shipped binary
carries every block's endpoints, simplified shape points and length, which is
all a risk surface needs: re-densifying those polylines at the same 25 m step
`build_graph.py` uses reproduces its sample points to within the 10 m
Douglas-Peucker tolerance. That means an evaluation needs only
`.cache/crime.json` -- one fetch script -- rather than the whole 100 MB cache.

**The model code is imported, not reimplemented.** `build_graph` supplies the
raster, the bucket definitions and the per-edge reduction, so a surface fitted
here is fitted by the same code that ships, and a bug in one is a bug in both.
An evaluation that quietly reimplements the thing it is evaluating is worth
very little.
"""
import json, math, os, sys

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
import geo
import build_graph as B

MAGIC = 0x53525453
FORMAT_VERSION = 2
HEADER_BYTES = 24          # six uint32: magic, version, nNodes, nEdges, nGeom, nNames

# LAPD publishes coordinates rounded to the hundred block to protect victims,
# so a test incident can sit up to roughly half a block from where it happened.
# 100 m snaps it to the right block face without reaching across an arterial.
SNAP_RADIUS_M = 100.0


# --------------------------------------------------------------------- graph
class Graph:
    """Everything `graph.bin` holds, plus re-derived sample points."""

    def __init__(self, path=None):
        path = path or os.path.join(C.OUT, "graph.bin")
        raw = np.fromfile(path, dtype=np.uint8)
        head = raw[:HEADER_BYTES].view(np.uint32)
        if int(head[0]) != MAGIC:
            raise SystemExit(f"{path}: bad magic -- not a graph.bin")
        if int(head[1]) != FORMAT_VERSION:
            raise SystemExit(f"{path}: format v{int(head[1])}, expected "
                             f"v{FORMAT_VERSION}")
        nN, nE, nG = int(head[2]), int(head[3]), int(head[4])

        o = HEADER_BYTES
        self.nodes = raw[o:o + nN * 8].view(np.int32).reshape(nN, 2) / 1e6
        o += nN * 8
        self.eu = raw[o:o + nE * 4].view(np.int32).copy(); o += nE * 4
        self.ev = raw[o:o + nE * 4].view(np.int32).copy(); o += nE * 4
        self.gOff = raw[o:o + (nE + 1) * 4].view(np.uint32).copy()
        o += (nE + 1) * 4
        self.gPts = raw[o:o + nG * 8].view(np.int32).reshape(nG, 2) / 1e6
        o += nG * 8
        self.ed = raw[o:o + nE * 2].view(np.uint16).astype(np.float64)
        o += nE * 2
        self.ename = raw[o:o + nE * 2].view(np.uint16).copy(); o += nE * 2
        self.er = raw[o:o + nE * 3].view(np.uint8).reshape(nE, 3)
        if o + nE * 3 != raw.size:
            raise SystemExit(f"{path}: section layout has drifted")

        self.nN, self.nE = nN, nE
        self.meta = json.load(open(os.path.join(C.OUT, "graph_meta.json")))
        self._samples = None
        self._csr = None
        self._tree = None

    # ---------------------------------------------------------- sample points
    def samples(self, step=B.SAMPLE_STEP):
        """Points every ~`step` m along every block, flat, with edge offsets.

        Mirrors `build_graph.edge_geometry`: one flat array so the whole city
        can be looked up against a raster in a single vectorised call.
        """
        if self._samples is not None:
            return self._samples
        ax, ay = geo.to_xy(self.nodes[self.eu, 0], self.nodes[self.eu, 1])
        bx, by = geo.to_xy(self.nodes[self.ev, 0], self.nodes[self.ev, 1])
        gx, gy = geo.to_xy(self.gPts[:, 0], self.gPts[:, 1])
        gOff = self.gOff.astype(np.int64)

        xs, ys = [], []
        offsets = np.zeros(self.nE + 1, dtype=np.int64)
        for i in range(self.nE):
            a, b = gOff[i], gOff[i + 1]
            if b > a:
                px = np.concatenate(([ax[i]], gx[a:b], [bx[i]]))
                py = np.concatenate(([ay[i]], gy[a:b], [by[i]]))
            else:
                px = np.array([ax[i], bx[i]])
                py = np.array([ay[i], by[i]])
            sx, sy, _ = geo.densify(px, py, step=step)
            xs.append(np.asarray(sx))
            ys.append(np.asarray(sy))
            offsets[i + 1] = offsets[i] + len(sx)
        self._samples = (np.concatenate(xs), np.concatenate(ys), offsets)
        return self._samples

    def sample_edge_index(self):
        """Edge index of every sample point, for snapping incidents to blocks."""
        _, _, off = self.samples()
        return np.repeat(np.arange(self.nE), np.diff(off))

    def snap(self, x, y, radius=SNAP_RADIUS_M):
        """Nearest block to each point. Returns (edge_index, hit_mask)."""
        sx, sy, _ = self.samples()
        if self._tree is None:
            self._tree = cKDTree(np.column_stack([sx, sy]))
        d, idx = self._tree.query(np.column_stack([x, y]), k=1,
                                  distance_upper_bound=radius)
        hit = np.isfinite(d)
        ei = np.zeros(len(x), dtype=np.int64)
        owner = self.sample_edge_index()
        ei[hit] = owner[idx[hit]]
        return ei, hit

    # ------------------------------------------------------------- adjacency
    def csr(self):
        """Compressed adjacency, the same shape the browser builds."""
        if self._csr is not None:
            return self._csr
        src = np.concatenate([self.eu, self.ev])
        dst = np.concatenate([self.ev, self.eu])
        eid = np.concatenate([np.arange(self.nE, dtype=np.int32)] * 2)
        order = np.argsort(src, kind="stable")
        head = np.zeros(self.nN + 1, dtype=np.int64)
        np.cumsum(np.bincount(src, minlength=self.nN), out=head[1:])
        self._csr = (head, dst[order].astype(np.int32), eid[order])
        return self._csr


# ----------------------------------------------------------------- incidents
FIELDS = [("x", "f8"), ("y", "f8"), ("hour", "i4"), ("year", "i4"),
          ("day", "f8"), ("sev", "f8"), ("juv", "?")]


def load_incidents(path=None):
    """Every cached incident with the fields a refit needs, unweighted.

    Weighting is deliberately *not* baked in here: the holdout refits from a
    date slice and the sensitivity sweep varies the weights, so both need the
    raw severity class and victim age rather than a finished number.
    """
    path = path or os.path.join(C.RAW, "crime.json")
    if not os.path.exists(path):
        raise SystemExit(
            f"no incident cache at {path}\n"
            f"  run:  python pipeline/fetch_crime.py\n"
            f"  (or:  python pipeline/eval/fixture.py  for a synthetic stand-in)")
    with open(path) as f:
        rows = json.load(f)

    lat, lon, hour, year, day, sev, juv = [], [], [], [], [], [], []
    for r in rows:
        try:
            la, lo = float(r["lat"]), float(r["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if la == 0.0:
            continue
        d = (r.get("date_occ") or "")[:10]
        try:
            y, mo, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
        except ValueError:
            continue
        t = (r.get("time_occ") or "1200").zfill(4)
        try:
            h = int(t[:2]) % 24
        except ValueError:
            h = 12
        try:
            age = int(r.get("vict_age") or -1)
        except ValueError:
            age = -1
        lat.append(la)
        lon.append(lo)
        hour.append(h)
        year.append(y)
        # Fractional year, so recency decay is smooth inside a year rather than
        # stepping on 1 January.
        day.append(y + ((mo - 1) * 30.44 + dd) / 365.25)
        sev.append(C.SEVERITY.get(r.get("crm_cd_desc", ""), C.DEFAULT_SEVERITY))
        juv.append(C.JUVENILE_AGE[0] <= age <= C.JUVENILE_AGE[1])

    n = len(lat)
    out = np.zeros(n, dtype=FIELDS)
    x, y = geo.to_xy(np.array(lat), np.array(lon))
    out["x"], out["y"] = np.asarray(x), np.asarray(y)
    out["hour"] = hour
    out["year"] = year
    out["day"] = day
    out["sev"] = sev
    out["juv"] = juv
    return out


def weights(inc, severity_scale=1.0, juvenile_weight=None, halflife=None,
            reference_year=None, use_severity=True, use_recency=True):
    """Model weight per incident, with every constant overridable.

    `severity_scale` stretches the severity spread about its mean rather than
    scaling it outright: multiplying every weight by a constant cannot change a
    rank-normalised surface at all, so a sweep that did that would report a
    spurious zero.
    """
    juvenile_weight = C.JUVENILE_WEIGHT if juvenile_weight is None else juvenile_weight
    halflife = C.RECENCY_HALFLIFE_YEARS if halflife is None else halflife
    reference_year = C.REFERENCE_YEAR if reference_year is None else reference_year

    w = np.ones(len(inc))
    if use_severity:
        s = inc["sev"]
        w = w * (s.mean() + (s - s.mean()) * severity_scale)
    w = np.where(inc["juv"], w * juvenile_weight, w)
    if use_recency and halflife > 0:
        w = w * 0.5 ** ((reference_year - inc["day"]) / halflife)
    return np.maximum(w, 1e-9)


# ------------------------------------------------------------- risk surfaces
def bucket_mask(inc, bucket):
    fn = B.BUCKETS[bucket]
    return np.fromiter((fn(int(h)) for h in inc["hour"]), bool, len(inc))


def kernel_surface(grid, samples, inc, w, bandwidth=None, buckets=None,
                   per_hour=True):
    """Per-block kernel density per bucket -- `build_graph`'s step 3, exactly.

    Returns {bucket: array over edges}.
    """
    bandwidth = C.KERNEL_BANDWIDTH_M if bandwidth is None else bandwidth
    buckets = buckets or B.BUCKET_ORDER
    sx, sy, off = samples
    sigma = bandwidth / B.CELL
    out = {}
    for b in buckets:
        m = bucket_mask(inc, b)
        dens = gaussian_filter(grid.rasterise(inc["x"][m], inc["y"][m], w[m]),
                               sigma=sigma, mode="constant")
        vals = grid.sample(dens, sx, sy)
        s = B.per_edge_mean(vals, off)
        out[b] = s / B.BUCKET_HOURS[b] if per_hour else s
    return out


def pooled_percentile(raw, buckets=None, compression=1.6):
    """Rank against the pooled distribution, then compress the bottom.

    Pooled rather than per bucket, for the reason `build_graph` gives: ranking
    each bucket on its own forces all three to the same marginal distribution
    and erases the fact that some hours are genuinely worse.
    """
    buckets = buckets or B.BUCKET_ORDER
    pooled = np.concatenate([raw[b] for b in buckets])
    order = pooled.argsort()
    ppct = np.empty(len(pooled))
    ppct[order] = np.linspace(0.0, 1.0, len(pooled))
    ppct = ppct ** compression
    n = len(raw[buckets[0]])
    return {b: ppct[k * n:(k + 1) * n] for k, b in enumerate(buckets)}


# ------------------------------------------------------------------- metrics
def roc_auc(score, label):
    """Mann-Whitney U, which is the AUC exactly, with ties at half credit."""
    label = np.asarray(label, dtype=bool)
    npos, nneg = int(label.sum()), int((~label).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    order = np.argsort(score, kind="mergesort")
    s = np.asarray(score, dtype=float)[order]
    ranks = np.empty(len(s), dtype=float)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2.0 + 1.0
        i = j + 1
    rpos = ranks[label[order]].sum()
    return (rpos - npos * (npos + 1) / 2.0) / (npos * nneg)


def auc_se(auc, npos, nneg):
    """Hanley-McNeil standard error of an AUC.

    Needed because a bare margin threshold cannot tell a real separation from
    sampling noise, and with a few hundred positive blocks per window the noise
    is worth two or three points of AUC. Assuming the exponential form for the
    score distributions is the standard conservative choice.
    """
    if not npos or not nneg or not np.isfinite(auc):
        return float("nan")
    q1 = auc / (2.0 - auc)
    q2 = 2.0 * auc * auc / (1.0 + auc)
    var = (auc * (1 - auc) + (npos - 1) * (q1 - auc ** 2)
           + (nneg - 1) * (q2 - auc ** 2)) / (npos * nneg)
    return math.sqrt(max(var, 0.0))


def top_share(score, weight, frac, rng=None):
    """Mask of the highest-scoring blocks holding `frac` of network length.

    Length, not block count: a "top 5%" made of 5% of the *blocks* can be 12%
    of the pavement when the worst blocks are long arterials, which would
    flatter every hit rate reported against it.

    Ties are broken at random rather than by block index. The count baselines
    tie tens of thousands of blocks at zero, and index order correlates with
    OSM way order, so a deterministic tie-break would hand them a real but
    entirely spurious edge over a continuous surface that never ties.
    """
    score = np.asarray(score, dtype=float)
    shuffle = (rng or np.random.default_rng(0)).permutation(len(score))
    order = shuffle[np.argsort(-score[shuffle], kind="mergesort")]
    cum = np.cumsum(weight[order])
    cut = np.searchsorted(cum, frac * weight.sum()) + 1
    mask = np.zeros(len(score), dtype=bool)
    mask[order[:cut]] = True
    return mask


def hit_rate_and_pai(score, weight, hits, fracs=(0.01, 0.05, 0.10), rng=None):
    """Hit rate and PAI at each coverage level.

    PAI is the standard crime-forecasting Predictive Accuracy Index: the share
    of incidents caught divided by the share of the study area flagged. On a
    street network "area" is network length, so PAI 10 at the 1% level means
    the flagged 1% of pavement caught 10% of what happened.
    """
    total = float(hits.sum())
    out = []
    for f in fracs:
        m = top_share(score, weight, f, rng=rng)
        share_len = float(weight[m].sum() / weight.sum())
        caught = float(hits[m].sum())
        rate = caught / total if total else float("nan")
        out.append(dict(frac=f, hit_rate=rate,
                        pai=(rate / share_len) if share_len else float("nan"),
                        caught=caught, blocks=int(m.sum()),
                        length_share=share_len))
    return out


def spearman(a, b):
    """Rank correlation, ties averaged."""
    def rank(v):
        order = np.argsort(v, kind="mergesort")
        r = np.empty(len(v), dtype=float)
        sv = np.asarray(v, dtype=float)[order]
        i = 0
        while i < len(sv):
            j = i
            while j + 1 < len(sv) and sv[j + 1] == sv[i]:
                j += 1
            r[order[i:j + 1]] = (i + j) / 2.0
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    ra -= ra.mean(); rb -= rb.mean()
    denom = math.sqrt(float((ra * ra).sum()) * float((rb * rb).sum()))
    return float((ra * rb).sum() / denom) if denom else float("nan")
