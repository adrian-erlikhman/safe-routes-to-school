"""How much does each hand-chosen constant actually move the recommendation?

Every number in `config.py` was picked by judgement and never tested. Some of
them barely matter; some of them decide which street a child is sent down. This
finds out which is which, by perturbing each one over a range a reasonable
person might have chosen instead and measuring two things:

  surface     Spearman rank correlation of the whole risk surface against
              baseline. Answers "did the model change its mind about the city".
  routes      over ~200 fixed school-bound trips, the share of the safest
              route's length that is no longer on the safest route. Answers
              "did the model change its mind about this walk", which is the
              only question the app actually asks it.

The second matters more. A constant can shift every score by a lot and change
no route at all, because routing depends on the *ordering* of nearby blocks
rather than their absolute values -- and that is the failure mode a correlation
alone would hide.

  python pipeline/eval/sensitivity.py            # full sweep
  python pipeline/eval/sensitivity.py --fast     # fewer pairs, for CI
"""
import argparse, heapq, json, math, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
import geo
import build_graph as B
from eval import common as K

# The top of the app's lambda ladder: the "safest" option a user can pick, and
# so the one whose stability actually matters.
SAFEST_LAMBDA = 7.0
N_PAIRS = 200
TRIP_MIN_M, TRIP_MAX_M = 700.0, 2500.0    # a plausible walk to school
ROUTING_BUCKET = "night"                   # the window the safest option is for


# ------------------------------------------------------------------- routing
def astar(csr, ed, risk, nodes_xy, src, dst, lam, exponent):
    """Cheapest path under length * (1 + lam * risk**exponent), as the app does."""
    head, to, eix = csr
    x, y = nodes_xy
    n = len(x)
    dist = np.full(n, np.inf)
    prev_e = np.full(n, -1, dtype=np.int64)
    prev_n = np.full(n, -1, dtype=np.int64)
    done = np.zeros(n, dtype=bool)
    h = lambda i: math.hypot(x[i] - x[dst], y[i] - y[dst])
    dist[src] = 0.0
    pq = [(h(src), src)]
    while pq:
        _, u = heapq.heappop(pq)
        if done[u]:
            continue
        done[u] = True
        if u == dst:
            break
        du = dist[u]
        for k in range(head[u], head[u + 1]):
            v = to[k]
            if done[v]:
                continue
            ei = eix[k]
            nd = du + ed[ei] * (1.0 + lam * risk[ei] ** exponent)
            if nd < dist[v]:
                dist[v] = nd
                prev_e[v] = ei
                prev_n[v] = u
                heapq.heappush(pq, (nd + h(v), v))
    if not np.isfinite(dist[dst]):
        return None
    edges, cur = [], dst
    while cur != src:
        edges.append(int(prev_e[cur]))
        cur = int(prev_n[cur])
    return np.array(edges, dtype=np.int64)


def route_set(g, risk, pairs, exponent, lam=SAFEST_LAMBDA):
    csr = g.csr()
    x, y = geo.to_xy(g.nodes[:, 0], g.nodes[:, 1])
    xy = (np.asarray(x), np.asarray(y))
    out = []
    for src, dst in pairs:
        out.append(astar(csr, g.ed, risk, xy, src, dst, lam, exponent))
    return out


def route_change(g, base, other):
    """Share of the baseline safest route's length that is no longer used."""
    changed, total, n = 0.0, 0.0, 0
    for a, b in zip(base, other):
        if a is None or b is None or not len(a):
            continue
        la = g.ed[a].sum()
        keep = g.ed[np.intersect1d(a, b, assume_unique=False)].sum()
        changed += la - keep
        total += la
        n += 1
    return (changed / total) if total else float("nan"), n


def pick_pairs(g, n, seed=5):
    """School-bound trips: a random origin to the node nearest a real school."""
    rng = np.random.default_rng(seed)
    schools = json.load(open(os.path.join(C.OUT, "schools.json")))
    sx, sy = geo.to_xy(np.array([s["lat"] for s in schools]),
                       np.array([s["lon"] for s in schools]))
    nx, ny = geo.to_xy(g.nodes[:, 0], g.nodes[:, 1])
    nx, ny = np.asarray(nx), np.asarray(ny)
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack([nx, ny]))
    _, school_node = tree.query(np.column_stack([np.asarray(sx), np.asarray(sy)]))

    pairs = []
    guard = 0
    while len(pairs) < n and guard < n * 200:
        guard += 1
        dst = int(school_node[rng.integers(len(school_node))])
        src = int(rng.integers(g.nN))
        d = math.hypot(nx[src] - nx[dst], ny[src] - ny[dst])
        if TRIP_MIN_M <= d <= TRIP_MAX_M and src != dst:
            pairs.append((src, dst))
    return pairs


# ------------------------------------------------------------------ surfaces
class Model:
    """Rebuilds the risk surface from whatever inputs the cache actually has."""

    def __init__(self, g, incidents, fast=False, lights_path=None):
        self.g = g
        self.inc = incidents
        self.grid = B.Grid()
        self.samples = g.samples(step=B.SAMPLE_STEP * (2.0 if fast else 1.0))
        self.lights_path = lights_path or os.path.join(C.RAW,
                                                       "streetlights.json")
        self.lights = self._light_credit()
        self.penalty = self._road_penalty()

    def _light_credit(self):
        path = self.lights_path
        if not os.path.exists(path):
            return None
        pts = np.asarray(json.load(open(path)), dtype=np.float64)
        if not len(pts):
            return None
        lx, ly = geo.to_xy(pts[:, 0], pts[:, 1])
        return np.asarray(lx), np.asarray(ly)

    def _road_penalty(self):
        """Per-edge road-type penalty, which needs the OSM cache.

        `graph.bin` does not store road type, so this reconstructs it by
        re-running the build's own edge splitting. That only lines up if the
        cache is the one the shipped graph was built from, so the edge count is
        checked and the sweep is skipped rather than guessed at if it differs.
        """
        if not os.path.exists(os.path.join(C.RAW, "osm_ways.json")):
            return None
        nodes, edges = B.build_edges()
        edges, _keep = B.largest_component(edges)
        if len(edges) != self.g.nE:
            print(f"  road types: cache has {len(edges):,} edges, graph.bin "
                  f"has {self.g.nE:,} -- not the same build, skipping",
                  flush=True)
            return None
        return np.array([B.ROADTYPE_PENALTY.get(e[3], 0.0) for e in edges])

    def credit(self, radius, max_credit):
        from scipy.ndimage import uniform_filter
        if self.lights is None:
            return np.zeros(self.g.nE)
        lx, ly = self.lights
        sx, sy, off = self.samples
        lg = self.grid.rasterise(lx, ly, np.ones(len(lx)))
        win = max(3, int(round(2 * radius / B.CELL)))
        near = uniform_filter(lg, size=win, mode="constant") * (win * win)
        cnt = B.per_edge_mean(self.grid.sample(near, sx, sy), off)
        return max_credit * np.minimum(1.0, cnt / 4.0)

    def surface(self, bandwidth=None, compression=1.6, severity_scale=1.0,
                juvenile_weight=None, halflife=None, light_radius=None,
                light_max=None, use_severity=True, penalty_scale=1.0):
        w = K.weights(self.inc, severity_scale=severity_scale,
                      juvenile_weight=juvenile_weight, halflife=halflife,
                      use_severity=use_severity)
        raw = K.kernel_surface(self.grid, self.samples, self.inc, w,
                               bandwidth=bandwidth)
        pct = K.pooled_percentile(raw, compression=compression)
        cr = self.credit(light_radius or C.LIGHT_RADIUS_M,
                         C.LIGHT_MAX_CREDIT if light_max is None else light_max)
        dark = B.dark_fractions(np.bincount(self.inc["hour"], minlength=24)
                                .astype(float))
        pen = (0.0 if self.penalty is None else self.penalty * penalty_scale)
        return {b: np.clip(pct[b] * (1.0 - cr * dark[b]) + pen, 0.0, 1.0)
                for b in B.BUCKET_ORDER}


# --------------------------------------------------------------------- sweep
def sweep_spec(model):
    """Every constant, its plausible range, and what it needs to be measured."""
    lights = model.lights is not None
    return [
        dict(name="KERNEL_BANDWIDTH_M", base=C.KERNEL_BANDWIDTH_M,
             values=[60, 90, 120, 180, 250], kw="bandwidth", need=True,
             why="how far one incident's influence reaches"),
        dict(name="ppct ** compression", base=1.6,
             values=[1.0, 1.3, 1.6, 2.0, 2.5], kw="compression", need=True,
             why="how hard the bottom of the distribution is flattened"),
        dict(name="RECENCY_HALFLIFE_YEARS", base=C.RECENCY_HALFLIFE_YEARS,
             values=[1.0, 2.5, 5.0, 100.0], kw="halflife", need=True,
             why="how fast a 2020 incident stops counting"),
        dict(name="JUVENILE_WEIGHT", base=C.JUVENILE_WEIGHT,
             values=[1.0, 2.0, 3.0, 5.0], kw="juvenile_weight", need=True,
             why="how much more a crime against a child counts"),
        dict(name="SEVERITY spread", base=1.0,
             values=[0.0, 0.5, 1.0, 2.0], kw="severity_scale", need=True,
             why="0 makes every offence count the same, 2 doubles the spread"),
        dict(name="LIGHT_MAX_CREDIT", base=C.LIGHT_MAX_CREDIT,
             values=[0.0, 0.2, 0.35, 0.5], kw="light_max", need=lights,
             why="the most a well-lit block can earn back"),
        dict(name="LIGHT_RADIUS_M", base=C.LIGHT_RADIUS_M,
             values=[30.0, 60.0, 120.0], kw="light_radius", need=lights,
             why="how near a lamp has to be to count"),
        dict(name="ROADTYPE_PENALTY scale", base=1.0,
             values=[0.0, 0.5, 2.0], kw="penalty_scale",
             need=model.penalty is not None, needs=".cache/osm_ways.json",
             why="0 drops the arterial penalty entirely, 2 doubles every "
                 "road-type adjustment"),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--incidents", default=None)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--lights", default=None,
                    help="path to a streetlights.json (default .cache/)")
    ap.add_argument("--pairs", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    t0 = time.time()
    g = K.Graph()
    n_pairs = a.pairs or (25 if a.fast else N_PAIRS)
    pairs = pick_pairs(g, n_pairs)
    print(f"{len(pairs)} school-bound trips, "
          f"{TRIP_MIN_M:.0f}-{TRIP_MAX_M:.0f} m", flush=True)

    results = []

    # ---- the routing exponent needs no incident data: it is applied to the
    # shipped surface at route time, so it can always be measured.
    shipped = {b: g.er[:, k].astype(float) / 255.0
               for k, b in enumerate(g.meta["buckets"])}
    base_r = route_set(g, shipped[ROUTING_BUCKET], pairs, 1.5)
    print("\nrisk ** exponent (routing only, on the shipped surface)", flush=True)
    for e in [1.0, 1.25, 1.5, 1.75, 2.0]:
        if e == 1.5:
            continue
        other = route_set(g, shipped[ROUTING_BUCKET], pairs, e)
        ch, n = route_change(g, base_r, other)
        results.append(dict(param="risk ** routing exponent", base=1.5,
                            value=e, surface=1.0, routes=ch, n=n,
                            why="how firmly the router avoids a bad block"))
        print(f"  {e:>5}  routes {100*ch:5.1f}% changed", flush=True)

    # ---- everything else needs incidents
    try:
        inc = K.load_incidents(a.incidents)
    except SystemExit as e:
        print(f"\n{e}\nskipping every parameter that needs incident data.")
        inc = None

    if inc is not None:
        model = Model(g, inc, fast=a.fast, lights_path=a.lights)
        print(f"\n{len(inc):,} incidents; streetlights "
              f"{'available' if model.lights is not None else 'MISSING'}",
              flush=True)
        base_s = model.surface()
        base_routes = route_set(g, base_s[ROUTING_BUCKET], pairs, 1.5)

        # A noise floor for the route metric. The network has a 15 m median
        # block and carries a separate footway alongside most streets, so many
        # "safest" routes are near-ties that flip between equivalent pavements
        # under any nudge at all. Perturbing the bandwidth by 1% -- a change no
        # one would argue about -- measures how much of the route churn below
        # is that twitchiness rather than the parameter. Anything near this
        # line has not been shown to matter.
        ctrl = model.surface(bandwidth=C.KERNEL_BANDWIDTH_M * 1.01)
        ctrl_routes = route_set(g, ctrl[ROUTING_BUCKET], pairs, 1.5)
        ch, n = route_change(g, base_routes, ctrl_routes)
        rho = float(np.mean([K.spearman(base_s[b], ctrl[b])
                             for b in B.BUCKET_ORDER]))
        results.append(dict(param="CONTROL: 1% bandwidth", base=120.0,
                            value=round(C.KERNEL_BANDWIDTH_M * 1.01, 1),
                            surface=rho, routes=ch, n=n,
                            why="noise floor -- a change nobody would argue "
                                "about, for comparison"))
        print(f"\nCONTROL 1% bandwidth change: routes {100*ch:5.1f}% changed, "
              f"surface rho {rho:.4f}\n  (anything near this line is route "
              f"churn, not the parameter)", flush=True)

        for spec in sweep_spec(model):
            if not spec["need"]:
                print(f"\n{spec['name']}: skipped, needs "
                      f"{spec.get('needs', '.cache/streetlights.json')}",
                      flush=True)
                continue
            print(f"\n{spec['name']}  (config: {spec['base']})  "
                  f"-- {spec['why']}", flush=True)
            for v in spec["values"]:
                if v == spec["base"]:
                    continue
                s = model.surface(**{spec["kw"]: v})
                rho = float(np.mean([K.spearman(base_s[b], s[b])
                                     for b in B.BUCKET_ORDER]))
                rts = route_set(g, s[ROUTING_BUCKET], pairs, 1.5)
                ch, n = route_change(g, base_routes, rts)
                results.append(dict(param=spec["name"], base=spec["base"],
                                    value=v, surface=rho, routes=ch, n=n,
                                    why=spec["why"]))
                print(f"  {v:>8}  surface rho {rho:.4f}   "
                      f"routes {100*ch:5.1f}% changed", flush=True)

    # ------------------------------------------------------------- ranking
    by_param = {}
    for r in results:
        by_param.setdefault(r["param"], []).append(r)
    ranked = sorted(by_param.items(),
                    key=lambda kv: -max(x["routes"] for x in kv[1]
                                        if np.isfinite(x["routes"])),
                    )
    print("\n" + "=" * 72)
    print("RANKED BY HOW MUCH THEY MOVE THE ACTUAL RECOMMENDATION")
    print("=" * 72)
    print(f"  {'parameter':<28} {'worst-case route change':>24} "
          f"{'min rank corr':>14}")
    lines = ["| Parameter | Range swept | Worst-case route change | "
             "Min rank correlation |", "|---|---|---|---|"]
    for name, rows in ranked:
        worst = max(x["routes"] for x in rows if np.isfinite(x["routes"]))
        rho = min(x["surface"] for x in rows)
        vals = sorted({x["value"] for x in rows} | {rows[0]["base"]})
        mark = "  <-- noise floor" if name.startswith("CONTROL") else ""
        print(f"  {name:<28} {100*worst:>23.1f}% {rho:>14.4f}{mark}")
        lines.append(f"| {'**' if mark else '`'}{name}{'**' if mark else '`'} "
                     f"| {vals[0]} to {vals[-1]} (config {rows[0]['base']}) | "
                     f"{'' if mark else '**'}{100*worst:.1f}%"
                     f"{'' if mark else '**'} | {rho:.4f} |"
                     + (" <- noise floor" if mark else ""))

    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "sensitivity_results.md")
    with open(out, "w") as f:
        f.write("# Parameter sensitivity\n\n")
        if a.note:
            f.write(f"> **{a.note}**\n\n")
        f.write(f"Each constant perturbed over a range a reasonable person "
                f"might have chosen instead, measured against a baseline at "
                f"the configured values. *Worst-case route change* is the "
                f"share of the safest route's length that moves, over "
                f"{len(pairs)} school-bound trips of "
                f"{TRIP_MIN_M:.0f}-{TRIP_MAX_M:.0f} m in the `{ROUTING_BUCKET}` "
                f"window, at the top of the app's lambda ladder "
                f"(lambda={SAFEST_LAMBDA}). Rank correlation is Spearman "
                f"against the baseline surface, averaged over the three "
                f"windows.\n\n")
        f.write("\n".join(lines) + "\n\n")
        f.write("## Every point measured\n\n")
        f.write("| Parameter | Value | Rank corr | Route change |\n|---|---|---|---|\n")
        for name, rows in ranked:
            for r in rows:
                f.write(f"| `{name}` | {r['value']} | {r['surface']:.4f} | "
                        f"{100*r['routes']:.1f}% |\n")
        f.write(f"\n---\nGenerated by `pipeline/eval/sensitivity.py`.\n")
    with open(out.replace(".md", ".json"), "w") as f:
        json.dump(results, f, indent=1, default=float)
    print(f"\nwrote {out}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
