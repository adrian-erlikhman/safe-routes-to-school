"""Generate a synthetic incident file, so the evaluation can be tested itself.

An evaluation nobody has evaluated is just more untested code. This writes a
`crime.json`-shaped file with a known answer, in two modes:

  hotspot  incidents concentrate on a fixed set of places that persist from
           the training years into the test year. Real structure exists, so a
           working holdout script *must* find it. Positive control.
  null     incidents fall uniformly at random every year, so nothing in
           2020-2023 predicts 2024 beyond where the streets happen to be.
           A working holdout script must *fail* to find signal. Negative
           control -- this is the run that proves the report can say no.

The file is written as `crime.synthetic.json` and every report built from it
carries a SYNTHETIC banner. It is a test fixture. It is not Los Angeles, and
no number derived from it describes anything that happened to anyone.

  python pipeline/eval/fixture.py --mode hotspot
"""
import argparse, json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from eval import common as K

BANNER = "SYNTHETIC FIXTURE -- not real incident data, for testing the eval only"

N_HOTSPOTS = 220          # roughly one per square kilometre of the study area
HOTSPOT_SIGMA_M = 90.0    # tight enough that a 120 m kernel can resolve it
HOTSPOT_SHARE = 0.65      # the rest is uniform background noise
JUVENILE_SHARE = 0.22     # close to the real file's juvenile-victim fraction

CRIMES = list(C.SEVERITY.keys())
PREMISES = ["STREET", "SIDEWALK", "ALLEY", "PARKING LOT", "BUS STOP"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("hotspot", "null"), default="hotspot")
    ap.add_argument("--n", type=int, default=40000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None)
    ap.add_argument("--lights", type=int, default=0,
                    help="also write a synthetic streetlight file with N lamps, "
                         "so the lighting parameters can be swept too")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    g = K.Graph()
    lat, lon = g.nodes[:, 0], g.nodes[:, 1]

    # Both modes put incidents on the street network, because an incident in
    # the middle of a block of buildings would simply fail to snap and would
    # make the two modes differ for the wrong reason.
    if a.mode == "hotspot":
        spots = rng.choice(len(lat), N_HOTSPOTS, replace=False)
        # metres -> degrees, locally: good enough for a fixture.
        dlat = HOTSPOT_SIGMA_M / 111320.0
        dlon = HOTSPOT_SIGMA_M / 92500.0
        pick = rng.random(a.n) < HOTSPOT_SHARE
        home = spots[rng.integers(0, N_HOTSPOTS, a.n)]
        base = rng.integers(0, len(lat), a.n)
        src = np.where(pick, home, base)
        la = lat[src] + rng.normal(0, dlat, a.n) * pick
        lo = lon[src] + rng.normal(0, dlon, a.n) * pick
    else:
        src = rng.integers(0, len(lat), a.n)
        la, lo = lat[src], lon[src]

    year = rng.integers(2020, 2025, a.n)
    month = rng.integers(1, 13, a.n)
    day = rng.integers(1, 29, a.n)
    hour = rng.integers(0, 24, a.n)
    minute = rng.integers(0, 60, a.n)
    crime = rng.integers(0, len(CRIMES), a.n)
    prem = rng.integers(0, len(PREMISES), a.n)
    juv = rng.random(a.n) < JUVENILE_SHARE
    age = np.where(juv, rng.integers(5, 19, a.n), rng.integers(19, 80, a.n))

    rows = [dict(dr_no=str(200000000 + i),
                 date_occ=f"{year[i]}-{month[i]:02d}-{day[i]:02d}T00:00:00.000",
                 time_occ=f"{hour[i]:02d}{minute[i]:02d}",
                 crm_cd_desc=CRIMES[crime[i]],
                 premis_desc=PREMISES[prem[i]],
                 vict_age=str(int(age[i])),
                 lat=f"{la[i]:.6f}", lon=f"{lo[i]:.6f}",
                 area_name="SYNTHETIC")
            for i in range(a.n)]

    os.makedirs(C.RAW, exist_ok=True)
    out = a.out or os.path.join(C.RAW, "crime.synthetic.json")
    with open(out, "w") as f:
        json.dump(rows, f)
    print(f"{BANNER}\nmode={a.mode} n={a.n:,} seed={a.seed} -> {out}")

    if a.lights:
        # Lamps on the network, denser where the streets are, which is roughly
        # how a real city lights itself.
        src = rng.integers(0, len(lat), a.lights)
        pts = [[round(float(lat[k]), 6), round(float(lon[k]), 6)] for k in src]
        lp = os.path.join(C.RAW, "streetlights.synthetic.json")
        with open(lp, "w") as f:
            json.dump(pts, f, separators=(",", ":"))
        print(f"{a.lights:,} synthetic lamps -> {lp}")


if __name__ == "__main__":
    main()
