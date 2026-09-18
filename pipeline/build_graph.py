"""Turn raw OSM ways into a routable graph and score every block for risk.

Pipeline:
  1. split OSM ways into edges at true intersections (shared node ids)
  2. keep the largest connected component
  3. score each edge with a time-of-day-aware kernel density of violent crime
  4. apply street-lighting credit and road-type adjustment
  5. emit a compact JSON the browser can route on directly

The kernel density is evaluated by rasterising incidents onto a 20 m grid and
convolving with a Gaussian, rather than by running a radius query per sample
point. The two are mathematically equivalent for a fixed bandwidth, but the
convolution turns ~4 million spatial queries into three FFT-scale filters --
minutes instead of hours, which matters when you want to re-tune the weights.
"""
import gzip, json, os, shutil, sys
from collections import defaultdict

import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter, map_coordinates

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import geo
import solar

CELL = 20.0          # metres per grid cell
SAMPLE_STEP = 25.0   # sample every block this often

# Time buckets. Crime risk is not a property of a place alone -- it is a
# property of a place *at an hour*. Route quality depends on which you use.
BUCKETS = {
    "am":    lambda h: 5 <= h < 10,        # walk to school
    "pm":    lambda h: 10 <= h < 17,       # walk home
    "night": lambda h: h >= 17 or h < 5,   # after practice, after dark
}
BUCKET_ORDER = ["am", "pm", "night"]

# Buckets cover unequal spans, so raw counts are not comparable: "after dark"
# is 12 hours and would look worst simply for being longest. Dividing by span
# gives an incidents-per-hour rate -- which reveals that the afternoon walk
# home is actually the most dangerous hour of a student's day.
BUCKET_HOURS = {"am": 5.0, "pm": 7.0, "night": 12.0}

GEOM_TOLERANCE_M = 10.0   # Douglas-Peucker tolerance for shipped shape points

# How far from a named street a sidewalk can sit and still be called by its
# name, and how far off parallel it may run. A sidewalk is typically 8 to 15 m
# from the centreline; 25 m catches wide arterials without jumping a block.
SIDEWALK_SNAP_M = 25.0
SIDEWALK_PARALLEL_DEG = 35.0

# Walking an eight-lane arterial is worse than a residential street even at
# identical crime counts: more conflict points, worse sightlines, more noise.
ROADTYPE_PENALTY = {
    "primary": 0.16, "primary_link": 0.16, "trunk": 0.20, "trunk_link": 0.20,
    "secondary": 0.10, "secondary_link": 0.10, "tertiary": 0.05,
    "residential": 0.0, "living_street": -0.03, "footway": -0.05,
    "pedestrian": -0.06, "path": -0.02, "steps": 0.0, "service": 0.02,
    "alley": 0.10, "track": 0.06, "cycleway": -0.03, "unclassified": 0.02,
}

# The five display bands the app colours blocks with. Kept here so a build can
# report how many blocks a change actually moves, rather than reporting a mean
# shift that nobody can see on the map.
BANDS = [0.20, 0.40, 0.60, 0.80]

# --------------------------------------------------- sparse-block shrinkage
# A block with two incidents in its kernel and a block with forty currently get
# the same confident percentile. They should not: the first is mostly noise.
# Both are shrunk towards the mean of their neighbourhood, with the pull set by
# how much evidence the block actually has.
#
# The neighbourhood is a ~10 minute walk. Smaller and "local mean" is just the
# block again, which shrinks nothing; larger and it becomes the city average,
# which would flatten genuine differences between adjacent neighbourhoods.
LOCAL_MEAN_RADIUS_M = 800.0

# Prior strength is estimated from the data by moments rather than chosen, so
# this pair is only a sanity clamp on that estimate. Below ~0.5 effective
# incidents the shrinkage does nothing; above ~50 it would overwhelm even
# well-evidenced blocks.
SHRINK_K_BOUNDS = (0.5, 50.0)


def bucket_hours_list(bucket):
    """The clock hours a bucket covers, derived from its own predicate."""
    return [h for h in range(24) if BUCKETS[bucket](h)]


def dark_fractions(hour_hist):
    """Share of each bucket's incidents that happen after dark, school year.

    Weighted by when incidents actually occur rather than by clock hours: the
    credit scales a risk score, and risk sits where the incidents are. The
    5 a.m. hour is dark for most of the school year but carries few incidents,
    so weighting by the clock alone would overstate what lighting can do to the
    morning walk.
    """
    lat = (C.BBOX["south"] + C.BBOX["north"]) / 2.0
    lon = (C.BBOX["west"] + C.BBOX["east"]) / 2.0
    return {b: solar.dark_fraction(bucket_hours_list(b), lat, lon, hour_hist)
            for b in BUCKET_ORDER}


def shrink_to_local_mean(score, n_eff, local):
    """Empirical-Bayes shrinkage of a block's rate towards its neighbourhood.

    Each block's kernel score is a noisy estimate of a real local rate. How
    noisy depends on how many incidents are behind it: a weighted sum of n
    draws has a relative standard error of about 1/sqrt(n), whatever the
    weights are in. So the whole estimate is done on the *relative* scale,
    which keeps it dimensionless and independent of how the severity weights
    happen to be scaled:

        observed spread   mean(((s - m) / m)^2)      -- real differences + noise
        sampling noise    mean(1 / n_eff)            -- noise alone
        prior variance    the first minus the second -- real differences alone
        k                 1 / prior variance         -- effective incidents
                                                        needed to outweigh the
                                                        neighbourhood

    and the posterior weight on the block's own evidence is n / (n + k). Both
    quantities are estimated from the data by moments rather than chosen, which
    is the point: this is meant to remove a hand-set constant, not add one.

    Returns (shrunk score, confidence in 0..1, fitted k).
    """
    # Blocks in genuinely empty parts of the map have a local mean near zero,
    # where a relative residual is meaningless and numerically explosive. Fit
    # the moments on the blocks that carry the distribution and apply the
    # result everywhere.
    floor = max(np.percentile(local, 10), 1e-12)
    fit = (local > floor) & (n_eff > 0)
    m = np.maximum(local, floor)
    if fit.sum() >= 100:
        rel = (score[fit] - m[fit]) / m[fit]
        total_var = float(np.mean(rel * rel))
        noise_var = float(np.mean(1.0 / np.maximum(n_eff[fit], 1e-6)))
        prior_var = max(total_var - noise_var, 1e-6)
        k = float(np.clip(1.0 / prior_var, *SHRINK_K_BOUNDS))
    else:
        # Too little to fit on: shrink as little as the clamp allows rather
        # than inventing a prior.
        k = SHRINK_K_BOUNDS[0]
    conf = n_eff / (n_eff + k)
    return conf * score + (1.0 - conf) * m, conf, k


# --------------------------------------------------------------------- grids
class Grid:
    """Fixed raster over the study area, in local metres."""

    def __init__(self):
        b = C.BBOX
        x0, y0 = geo.to_xy(b["south"], b["west"])
        x1, y1 = geo.to_xy(b["north"], b["east"])
        pad = 4 * C.KERNEL_BANDWIDTH_M          # room for the kernel tails
        self.x0, self.y0 = float(x0) - pad, float(y0) - pad
        self.nx = int(np.ceil((float(x1) - self.x0 + pad) / CELL))
        self.ny = int(np.ceil((float(y1) - self.y0 + pad) / CELL))

    def rasterise(self, x, y, w):
        cx = ((x - self.x0) / CELL).astype(np.int32)
        cy = ((y - self.y0) / CELL).astype(np.int32)
        ok = (cx >= 0) & (cx < self.nx) & (cy >= 0) & (cy < self.ny)
        g = np.zeros((self.nx, self.ny), dtype=np.float32)
        np.add.at(g, (cx[ok], cy[ok]), w[ok].astype(np.float32))
        return g

    def sample(self, grid, x, y):
        cx = (x - self.x0) / CELL
        cy = (y - self.y0) / CELL
        return map_coordinates(grid, np.vstack([cx, cy]), order=1,
                               mode="nearest")


# -------------------------------------------------------------------- crimes
def load_crimes():
    with open(os.path.join(C.RAW, "crime.json")) as f:
        rows = json.load(f)
    lat, lon, w, hour = [], [], [], []
    for r in rows:
        try:
            la, lo = float(r["lat"]), float(r["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if la == 0.0:
            continue
        sev = C.SEVERITY.get(r.get("crm_cd_desc", ""), C.DEFAULT_SEVERITY)
        try:
            age = int(r.get("vict_age") or -1)
        except ValueError:
            age = -1
        if C.JUVENILE_AGE[0] <= age <= C.JUVENILE_AGE[1]:
            sev *= C.JUVENILE_WEIGHT
        year = float((r.get("date_occ") or "2022")[:4])
        sev *= 0.5 ** ((C.REFERENCE_YEAR - year) / C.RECENCY_HALFLIFE_YEARS)
        t = (r.get("time_occ") or "1200").zfill(4)
        try:
            h = int(t[:2]) % 24
        except ValueError:
            h = 12
        lat.append(la)
        lon.append(lo)
        w.append(sev)
        hour.append(h)
    x, y = geo.to_xy(np.array(lat), np.array(lon))
    return (np.asarray(x), np.asarray(y),
            np.array(w, dtype=np.float64), np.array(hour, dtype=np.int32))


def load_lights():
    path = os.path.join(C.RAW, "streetlights.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        pts = json.load(f)
    if not pts:
        return None
    arr = np.asarray(pts, dtype=np.float64)
    x, y = geo.to_xy(arr[:, 0], arr[:, 1])
    return np.asarray(x), np.asarray(y)


# --------------------------------------------------------------------- graph
def build_edges():
    with open(os.path.join(C.RAW, "osm_ways.json")) as f:
        raw = json.load(f)
    nodes = {int(k): v for k, v in raw["nodes"].items()}
    ways = raw["ways"]

    # A node is an intersection if more than one way references it.
    ref_count = defaultdict(int)
    for w in ways:
        for nid in w.get("nodes", []):
            ref_count[nid] += 1

    edges = []
    for w in ways:
        nds = [n for n in w.get("nodes", []) if n in nodes]
        if len(nds) < 2:
            continue
        tags = w.get("tags") or {}
        hw = tags.get("highway", "residential")
        if tags.get("service") == "alley":
            hw = "alley"
        # Street names let the app say "avoids Venice Boulevard" instead of
        # drawing a line and leaving the reader to work out what it means.
        name = (tags.get("name") or "").strip()
        cut = [0]
        for i in range(1, len(nds) - 1):
            if ref_count[nds[i]] > 1:
                cut.append(i)
        cut.append(len(nds) - 1)
        for a, b in zip(cut, cut[1:]):
            if b <= a:
                continue
            chain = nds[a:b + 1]
            if chain[0] == chain[-1]:
                continue
            edges.append((chain[0], chain[-1], chain, hw, name))
    return nodes, edges


def largest_component(edges):
    adj = defaultdict(list)
    for u, v, *_ in edges:
        adj[u].append(v)
        adj[v].append(u)
    seen, best = set(), []
    for start in adj:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nb in adj[cur]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        if len(comp) > len(best):
            best = comp
    keep = set(best)
    return [e for e in edges if e[0] in keep and e[1] in keep], keep


# ---------------------------------------------------------------- geometry
def edge_geometry(nodes, edges):
    """One pass over edges: true length, sample points, and drawable polyline.

    Sample points for every edge are concatenated into one flat array so the
    grid lookup can be done for the whole city in a single vectorised call.
    """
    n = len(edges)
    lengths = np.zeros(n)
    offsets = np.zeros(n + 1, dtype=np.int64)
    sx_parts, sy_parts, geoms = [], [], []

    for i, (u, v, chain, hw, _name) in enumerate(edges):
        pts = np.array([nodes[k] for k in chain], dtype=np.float64)
        xs, ys = geo.to_xy(pts[:, 0], pts[:, 1])
        sx, sy, total = geo.densify(np.asarray(xs), np.asarray(ys),
                                    step=SAMPLE_STEP)
        lengths[i] = max(float(total), 1.0)
        sx_parts.append(sx)
        sy_parts.append(sy)
        offsets[i + 1] = offsets[i] + len(sx)
        geoms.append(pts)
        if i and i % 50000 == 0:
            print(f"    geometry {i:,}/{n:,}", flush=True)

    return (lengths, np.concatenate(sx_parts), np.concatenate(sy_parts),
            offsets, geoms)


def per_edge_mean(values, offsets):
    """Mean of `values` within each edge's slice, via reduceat."""
    counts = np.diff(offsets)
    sums = np.add.reduceat(values, offsets[:-1])
    return sums / np.maximum(counts, 1)


def simplify(pts, tol):
    """Douglas-Peucker on a lat/lon polyline, tolerance in metres.

    Shape points are the single largest cost in the file we ship to browsers,
    and OSM carries far more of them than a 15 px-wide street line can show.
    """
    if len(pts) <= 2:
        return pts
    xs, ys = geo.to_xy(pts[:, 0], pts[:, 1])
    xy = np.column_stack([np.asarray(xs), np.asarray(ys)])
    keep = np.zeros(len(pts), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p, q = xy[a], xy[b]
        seg = q - p
        L = np.hypot(*seg)
        mid = xy[a + 1:b]
        if L < 1e-9:
            dist = np.hypot(mid[:, 0] - p[0], mid[:, 1] - p[1])
        else:
            # perpendicular distance from each interior point to segment p->q
            dist = np.abs(seg[0] * (p[1] - mid[:, 1])
                          - seg[1] * (p[0] - mid[:, 0])) / L
        k = int(dist.argmax())
        if dist[k] > tol:
            keep[a + 1 + k] = True
            stack.append((a, a + 1 + k))
            stack.append((a + 1 + k, b))
    return pts[keep]


# ------------------------------------------------------------------- main
def main(sidecar=False):
    print("loading OSM...", flush=True)
    nodes, edges = build_edges()
    print(f"  {len(edges):,} raw edges", flush=True)
    edges, keep = largest_component(edges)
    print(f"  {len(edges):,} edges in largest connected component "
          f"({len(keep):,} intersections)", flush=True)

    print("computing geometry + sample points...", flush=True)
    lengths, sx, sy, offsets, geoms = edge_geometry(nodes, edges)
    print(f"  {len(sx):,} sample points along "
          f"{lengths.sum()/1000:,.0f} km of street", flush=True)

    print("loading crime...", flush=True)
    cx, cy, cw, chour = load_crimes()
    print(f"  {len(cx):,} weighted incidents", flush=True)

    grid = Grid()
    print(f"  raster {grid.nx} x {grid.ny} cells @ {CELL:.0f} m", flush=True)
    sigma_cells = C.KERNEL_BANDWIDTH_M / CELL

    raw_scores, unshrunk, confidence = {}, {}, {}
    local_sigma = LOCAL_MEAN_RADIUS_M / CELL
    for b in BUCKET_ORDER:
        m = np.fromiter((BUCKETS[b](int(h)) for h in chour), bool, len(chour))
        dens = gaussian_filter(grid.rasterise(cx[m], cy[m], cw[m]),
                               sigma=sigma_cells, mode="constant")
        vals = grid.sample(dens, sx, sy)
        # Per-hour rate, so a 12-hour bucket is not penalised for its length.
        score = per_edge_mean(vals, offsets) / BUCKET_HOURS[b]
        unshrunk[b] = score

        # How much evidence is actually behind that number. The same kernel run
        # over unweighted counts gives a density; scipy normalises the kernel to
        # sum to one over cells, so multiplying by its effective cell area turns
        # that back into "incidents within about one bandwidth of here".
        ones = gaussian_filter(grid.rasterise(cx[m], cy[m], np.ones(int(m.sum()))),
                               sigma=sigma_cells, mode="constant")
        n_eff = (per_edge_mean(grid.sample(ones, sx, sy), offsets)
                 * (2.0 * np.pi * sigma_cells * sigma_cells))

        # The neighbourhood this block is shrunk towards.
        local = (per_edge_mean(grid.sample(
            gaussian_filter(dens, sigma=local_sigma, mode="constant"), sx, sy),
            offsets) / BUCKET_HOURS[b])

        raw_scores[b], confidence[b], k = shrink_to_local_mean(score, n_eff, local)
        # Mean absolute change against the mean score. Per-block relative
        # change would divide by the near-zero scores of empty blocks and
        # report a meaningless number in the millions of percent.
        moved = (float(np.mean(np.abs(raw_scores[b] - score)))
                 / max(float(np.mean(score)), 1e-12))
        print(f"  bucket {b:5}: {int(m.sum()):,} incidents over "
              f"{BUCKET_HOURS[b]:.0f}h = {m.sum()/BUCKET_HOURS[b]:,.0f}/hour"
              f"  | n_eff median {np.median(n_eff):.1f}"
              f"  shrink k={k:.1f} conf median {np.median(confidence[b]):.2f}"
              f"  moved {100*moved:.1f}%", flush=True)

    # ---------------------------------------------------------- lighting
    lights = load_lights()
    light_credit = np.zeros(len(edges))
    if lights is not None:
        lx, ly = lights
        lg = grid.rasterise(lx, ly, np.ones(len(lx)))
        win = max(3, int(round(2 * C.LIGHT_RADIUS_M / CELL)))
        # uniform_filter gives the mean per cell in the window; multiplying by
        # the window's cell count recovers "lamps within ~60 m of here".
        near = uniform_filter(lg, size=win, mode="constant") * (win * win)
        cnt = per_edge_mean(grid.sample(near, sx, sy), offsets)
        light_credit = C.LIGHT_MAX_CREDIT * np.minimum(1.0, cnt / 4.0)
        print(f"  streetlights: {len(lx):,} lamps, mean {cnt.mean():.1f} "
              f"within {C.LIGHT_RADIUS_M:.0f} m of a block", flush=True)
    else:
        print("  streetlights: unavailable, skipping credit", flush=True)

    # A streetlight cannot make 11 a.m. safer. The credit used to be applied
    # identically to all three windows, which quietly handed every lit block a
    # 35% discount at noon -- a protective effect the lamp was not providing.
    # Scale it by how much of each window is actually dark, from NOAA sunrise
    # and sunset over the Los Angeles school year, weighted by the hours
    # incidents really fall in. See pipeline/solar.py for the assumptions.
    dark = dark_fractions(np.bincount(chour, minlength=24).astype(float))
    print("  dark fraction: " + "  ".join(
        f"{b}={dark[b]:.2f}" for b in BUCKET_ORDER), flush=True)

    # ------------------------------------------- normalise to a 0..1 risk
    # Rank-normalise: absolute kernel values are unitless, but "this block is
    # worse than 90% of blocks in LA" is a statement a parent can act on.
    # Rank against the *pooled* distribution of all three buckets, not each
    # bucket separately. Normalising per bucket would force all three to the
    # same marginal distribution, silently erasing the fact that some hours of
    # the day are genuinely more dangerous than others -- which is the whole
    # point of having buckets. Pooling keeps them comparable: 0.7 means the
    # same absolute danger whether it is 8 a.m. or 9 p.m.
    pooled = np.concatenate([raw_scores[b] for b in BUCKET_ORDER])
    order = pooled.argsort()
    ppct = np.empty(len(pooled))
    ppct[order] = np.linspace(0.0, 1.0, len(pooled))
    # Compress the bottom: most streets are genuinely fine, and a
    # mildly-below-median block should not read as meaningfully risky.
    ppct = ppct ** 1.6

    n_e = len(edges)
    risk, risk_timeblind = {}, {}
    pen = np.array([ROADTYPE_PENALTY.get(e[3], 0.0) for e in edges])
    for k, b in enumerate(BUCKET_ORDER):
        pct = ppct[k * n_e:(k + 1) * n_e]
        risk[b] = np.clip(pct * (1.0 - light_credit * dark[b]) + pen, 0.0, 1.0)
        # The same surface under the old time-blind rule, so the build can say
        # what this one fix moved rather than leaving it to be taken on trust.
        risk_timeblind[b] = np.clip(pct * (1.0 - light_credit) + pen, 0.0, 1.0)

    print("\n  lighting fix, blocks changing display band:", flush=True)
    total_moved = 0
    for b in BUCKET_ORDER:
        was = np.digitize(risk_timeblind[b], BANDS)
        now = np.digitize(risk[b], BANDS)
        moved = int((was != now).sum())
        total_moved += moved
        up = int((now > was).sum())
        print(f"    {b:5} {moved:7,} of {n_e:,} blocks "
              f"({100*moved/n_e:4.1f}%), {up:,} into a worse band "
              f"(credit x{dark[b]:.2f})", flush=True)
    print(f"    total {total_moved:,} block-windows changed band", flush=True)

    # ------------------------------------------------------------- emit
    sorted_keep = sorted(keep)
    idx_of = {nid: k for k, nid in enumerate(sorted_keep)}

    # A packed binary blob rather than JSON. 431k edges of JSON costs ~40 MB
    # and a multi-second JSON.parse on the main thread; the same data as typed
    # arrays is a third of the size and becomes usable the instant it lands,
    # because the browser can view the buffer without parsing anything.
    node_ll = np.empty((len(sorted_keep), 2), dtype=np.int32)
    for k, nid in enumerate(sorted_keep):
        la, lo = nodes[nid]
        node_ll[k] = (round(la * 1e6), round(lo * 1e6))

    eu = np.array([idx_of[e[0]] for e in edges], dtype=np.int32)
    ev = np.array([idx_of[e[1]] for e in edges], dtype=np.int32)
    ed = np.clip(np.round(lengths), 1, 65535).astype(np.uint16)
    er = np.empty((len(edges), 3), dtype=np.uint8)
    for k, b in enumerate(BUCKET_ORDER):
        er[:, k] = np.round(risk[b] * 255).astype(np.uint8)

    # Street names, deduplicated into a table so each edge carries a 2-byte id
    # instead of a repeated string. NO_NAME marks footpaths and service roads,
    # which OSM mostly leaves unnamed.
    NO_NAME = 0xFFFF
    name_ids, name_list = {}, []
    ename = np.full(len(edges), NO_NAME, dtype=np.uint16)
    for i, e in enumerate(edges):
        nm = e[4]
        if not nm:
            continue
        k = name_ids.get(nm)
        if k is None:
            k = len(name_list)
            if k >= NO_NAME:        # 65,534 names is far beyond any city
                continue
            name_ids[nm] = k
            name_list.append(nm)
        ename[i] = k
    print(f"  street names: {len(name_list):,} unique, "
          f"{int((ename != NO_NAME).sum()):,} of {len(edges):,} blocks named "
          f"directly", flush=True)

    # OSM maps most Los Angeles sidewalks as separate unnamed footways, so a
    # walking route spends much of its length on ways with no name and the
    # directions read "unnamed path" for whole kilometres. Give each unnamed
    # block the name of the nearest named block running roughly parallel to it,
    # which is what a person means when they say they walked down Venice.
    ends = np.array([[nodes[e[0]][0], nodes[e[0]][1],
                      nodes[e[1]][0], nodes[e[1]][1]] for e in edges])
    ax, ay = geo.to_xy(ends[:, 0], ends[:, 1])
    bx, by = geo.to_xy(ends[:, 2], ends[:, 3])
    mid = np.column_stack([(ax + bx) / 2, (ay + by) / 2])
    bearing = np.degrees(np.arctan2(by - ay, bx - ax)) % 180.0

    have = ename != NO_NAME
    lack = ~have
    if have.any() and lack.any():
        from scipy.spatial import cKDTree
        tree = cKDTree(mid[have])
        have_idx = np.flatnonzero(have)
        cand = tree.query_ball_point(mid[lack], SIDEWALK_SNAP_M)
        inherited = 0
        for slot, hits in zip(np.flatnonzero(lack), cand):
            if not hits:
                continue
            hs = have_idx[np.asarray(hits)]
            db = np.abs(bearing[hs] - bearing[slot])
            db = np.minimum(db, 180.0 - db)          # parallel either way round
            ok = db <= SIDEWALK_PARALLEL_DEG
            if not ok.any():
                continue
            hs = hs[ok]
            d = np.hypot(mid[hs, 0] - mid[slot, 0], mid[hs, 1] - mid[slot, 1])
            ename[slot] = ename[hs[int(d.argmin())]]
            inherited += 1
        print(f"  sidewalks matched to a street: {inherited:,} "
              f"(now {int((ename != NO_NAME).sum()):,} named)", flush=True)

    print("simplifying geometry...", flush=True)
    geom_off = np.zeros(len(edges) + 1, dtype=np.uint32)
    geom_parts = []
    kept = dropped = 0
    for i, g in enumerate(geoms):
        if len(g) > 2:
            s = simplify(g, GEOM_TOLERANCE_M)[1:-1]   # endpoints come from u/v
            dropped += len(g) - 2 - len(s)
            kept += len(s)
        else:
            s = np.empty((0, 2))
        if len(s):
            geom_parts.append(np.round(np.asarray(s) * 1e6).astype(np.int32))
        geom_off[i + 1] = geom_off[i] + len(s)
    geom_pts = (np.concatenate(geom_parts) if geom_parts
                else np.empty((0, 2), dtype=np.int32))
    print(f"  kept {kept:,} shape points, dropped {dropped:,} "
          f"at {GEOM_TOLERANCE_M:.0f} m tolerance", flush=True)

    os.makedirs(C.OUT, exist_ok=True)
    path = os.path.join(C.OUT, "graph.bin")
    # Sections are ordered by descending alignment requirement -- every 4-byte
    # array first, then the uint16, then the uint8 -- so each one lands on a
    # natural boundary with zero padding and the reader can derive every offset
    # from the header alone.
    with open(path, "wb") as f:
        header = np.array([0x53525453,            # "SRTS"
                           2,                      # format version
                           len(sorted_keep),
                           len(edges),
                           len(geom_pts),
                           len(name_list)], dtype=np.uint32)
        f.write(header.tobytes())      # 24 bytes, still 4-byte aligned
        f.write(node_ll.tobytes())     # int32  nNodes * 2
        f.write(eu.tobytes())          # int32  nEdges
        f.write(ev.tobytes())          # int32  nEdges
        f.write(geom_off.tobytes())    # uint32 nEdges + 1
        f.write(geom_pts.tobytes())    # int32  nGeom * 2
        f.write(ed.tobytes())          # uint16 nEdges
        f.write(ename.tobytes())       # uint16 nEdges
        f.write(er.tobytes())          # uint8  nEdges * 3

    # Confidence does not fit the shipped format. graph.bin v2 is a fixed set of
    # sections with every offset derived from the header, and the browser
    # rejects any version it does not know, so adding a per-block byte is a
    # format change that needs the reader changed with it -- not something to
    # slip in. The proposal is written up in docs/FORMAT_V3.md; until it is
    # taken, the numbers are summarised here and the full array is available
    # behind --confidence-sidecar for anyone who wants to look at it.
    conf_stats = {b: dict(
        median=round(float(np.median(confidence[b])), 3),
        p10=round(float(np.percentile(confidence[b], 10)), 3),
        p90=round(float(np.percentile(confidence[b], 90)), 3),
        below_half=int((confidence[b] < 0.5).sum()),
    ) for b in BUCKET_ORDER}
    for b in BUCKET_ORDER:
        c = conf_stats[b]
        print(f"   {b:5} confidence: median {c['median']:.2f}  "
              f"p10 {c['p10']:.2f}  {c['below_half']:,} blocks under 0.5 "
              f"(mostly their neighbourhood's score, not their own)")

    if sidecar:
        cpath = os.path.join(C.OUT, "confidence.bin")
        arr = np.empty((n_e, 3), dtype=np.uint8)
        for k, b in enumerate(BUCKET_ORDER):
            arr[:, k] = np.round(confidence[b] * 255).astype(np.uint8)
        arr.tofile(cpath)
        print(f"  wrote {cpath} ({arr.nbytes/1e6:.1f} MB) -- "
              f"proposed v3 section, not read by the site")

    meta = {
        "buckets": BUCKET_ORDER,
        "bucket_hours": [BUCKET_HOURS[b] for b in BUCKET_ORDER],
        "nodes": len(sorted_keep),
        "edges": len(edges),
        "geom": int(len(geom_pts)),
        "crimes": int(len(cx)),
        "lights": 0 if lights is None else int(len(lights[0])),
        "bandwidth_m": C.KERNEL_BANDWIDTH_M,
        "km": round(float(lengths.sum() / 1000), 1),
        "names": len(name_list),
        "dark_fraction": {b: round(dark[b], 3) for b in BUCKET_ORDER},
        "confidence": conf_stats,
        "bbox": C.BBOX,
    }
    with open(os.path.join(C.OUT, "graph_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)

    with open(os.path.join(C.OUT, "street_names.json"), "w",
              encoding="utf-8") as f:
        json.dump(name_list, f, ensure_ascii=False, separators=(",", ":"))

    # Ship a pre-gzipped copy too: the browser inflates it with
    # DecompressionStream, so the transfer is ~5 MB instead of ~10 MB whether
    # or not the host chooses to compress .bin itself.
    with open(path, "rb") as fin, gzip.open(path + ".gz", "wb",
                                            compresslevel=9) as fout:
        shutil.copyfileobj(fin, fout)

    mb = os.path.getsize(path) / 1e6
    gz = os.path.getsize(path + ".gz") / 1e6
    print(f"\nwrote {len(sorted_keep):,} nodes / {len(edges):,} edges "
          f"-> {path} ({mb:.1f} MB, {gz:.1f} MB gzipped)")
    for b in BUCKET_ORDER:
        r = risk[b]
        print(f"   {b:5} risk: mean {r.mean():.3f}  p90 {np.percentile(r,90):.3f}"
              f"  p99 {np.percentile(r,99):.3f}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confidence-sidecar", action="store_true",
                    help="also write data/confidence.bin (proposed v3 section, "
                         "see docs/FORMAT_V3.md); the site does not read it")
    main(sidecar=ap.parse_args().confidence_sidecar)
