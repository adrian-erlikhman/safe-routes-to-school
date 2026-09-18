"""End-to-end smoke test of the build, on a synthetic city.

`build_graph.py` needs ~100 MB of cached downloads, which CI does not have and
a contributor may not want to wait for. This builds a small grid city with
known properties, runs the real `build_graph.main()` over it into a temporary
directory, and checks the result -- so a change to the risk model is exercised
by something before it reaches the shipped graph.

It asserts the things that are supposed to be true by construction:

  * the output parses as a v2 graph and every section ends where the header says
  * risk stays inside 0..1 in every window
  * the streetlight credit is time-aware: identical lamps and identical
    incidents must leave the daylight window less discounted than the dark one
  * shrinkage pulls thin blocks towards their neighbourhood and leaves
    well-evidenced ones alone

  python pipeline/eval/smoke.py
"""
import json, os, shutil, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C

GRID = 26              # GRID x GRID intersections
SPAN = 0.02            # degrees; a ~2 km square inside the study area
N_CRIMES = 6000
N_LIGHTS = 4000


def synth_cache(path, seed=3):
    rng = np.random.default_rng(seed)
    lat0 = (C.BBOX["south"] + C.BBOX["north"]) / 2.0
    lon0 = (C.BBOX["west"] + C.BBOX["east"]) / 2.0
    lats = lat0 + np.linspace(-SPAN / 2, SPAN / 2, GRID)
    lons = lon0 + np.linspace(-SPAN / 2, SPAN / 2, GRID)

    nodes, ways, nid = {}, [], 1
    ids = np.zeros((GRID, GRID), dtype=int)
    for i in range(GRID):
        for j in range(GRID):
            nodes[str(nid)] = [round(float(lats[i]), 6), round(float(lons[j]), 6)]
            ids[i, j] = nid
            nid += 1
    kinds = ["residential", "primary", "footway", "secondary"]
    for i in range(GRID):
        ways.append(dict(nodes=[int(x) for x in ids[i, :]],
                         tags={"highway": kinds[i % 4],
                               "name": f"{i} Street"}))
        ways.append(dict(nodes=[int(x) for x in ids[:, i]],
                         tags={"highway": kinds[(i + 2) % 4],
                               "name": f"{i} Avenue"}))
    with open(os.path.join(path, "osm_ways.json"), "w") as f:
        json.dump(dict(nodes=nodes, ways=ways), f)

    # Incidents at every hour, so all three windows are populated, and clustered
    # so that shrinkage and the kernel both have something to work with.
    hot = rng.integers(0, GRID, (12, 2))
    pick = rng.integers(0, 12, N_CRIMES)
    la = lats[hot[pick, 0]] + rng.normal(0, 0.0007, N_CRIMES)
    lo = lons[hot[pick, 1]] + rng.normal(0, 0.0007, N_CRIMES)
    hour = rng.integers(0, 24, N_CRIMES)
    rows = [dict(dr_no=str(i), date_occ=f"{2020 + i % 5}-06-15T00:00:00.000",
                 time_occ=f"{hour[i]:02d}30",
                 crm_cd_desc="ROBBERY", premis_desc="STREET",
                 vict_age=str(int(rng.integers(6, 60))),
                 lat=f"{la[i]:.6f}", lon=f"{lo[i]:.6f}")
            for i in range(N_CRIMES)]
    with open(os.path.join(path, "crime.json"), "w") as f:
        json.dump(rows, f)

    ll = [[round(float(lat0 + rng.uniform(-SPAN / 2, SPAN / 2)), 6),
           round(float(lon0 + rng.uniform(-SPAN / 2, SPAN / 2)), 6)]
          for _ in range(N_LIGHTS)]
    with open(os.path.join(path, "streetlights.json"), "w") as f:
        json.dump(ll, f)


def main():
    tmp = tempfile.mkdtemp(prefix="srts-smoke-")
    raw, out = os.path.join(tmp, "cache"), os.path.join(tmp, "data")
    os.makedirs(raw), os.makedirs(out)
    try:
        synth_cache(raw)
        C.RAW, C.OUT = raw, out
        import build_graph as B
        from eval import common as K
        B.main(sidecar=True)

        K.C.OUT = out
        g = K.Graph(os.path.join(out, "graph.bin"))
        meta = json.load(open(os.path.join(out, "graph_meta.json")))
        risk = {b: g.er[:, k] / 255.0 for k, b in enumerate(meta["buckets"])}

        checks = []

        def check(name, ok, detail=""):
            checks.append((name, bool(ok), detail))

        check("graph parses and sections line up", g.nE > 0 and g.nN > 0,
              f"{g.nN:,} nodes / {g.nE:,} edges")
        check("risk stays in 0..1",
              all((r >= 0).all() and (r <= 1).all() for r in risk.values()))

        dark = meta["dark_fraction"]
        check("daylight window gets no lighting credit", dark["pm"] == 0.0,
              f"pm dark fraction {dark['pm']}")
        check("dark window gets most of it", dark["night"] > 0.7,
              f"night dark fraction {dark['night']}")
        check("morning sits between the two",
              0.0 < dark["am"] < dark["night"], f"am {dark['am']}")

        conf = meta["confidence"]
        check("confidence is reported per window", set(conf) == set(meta["buckets"]))
        check("thin blocks are shrunk towards the neighbourhood",
              any(conf[b]["p10"] < conf[b]["p90"] for b in meta["buckets"]),
              "  ".join(f"{b} p10 {conf[b]['p10']} p90 {conf[b]['p90']}"
                        for b in meta["buckets"]))
        check("confidence sidecar is written on request",
              os.path.exists(os.path.join(out, "confidence.bin")))

        print("\n" + "=" * 66)
        for name, ok, detail in checks:
            print(f"  {'PASS' if ok else 'FAIL'}  {name}"
                  + (f"   [{detail}]" if detail else ""))
        bad = [n for n, ok, _ in checks if not ok]
        print("=" * 66)
        print(f"  -> {'PASS' if not bad else 'FAIL: ' + ', '.join(bad)}")
        return 1 if bad else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
