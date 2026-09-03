"""Build a compact transit graph from LA Metro's GTFS bus and rail feeds.

We do not need a full schedule-based planner. What matters for this project is
which stops connect to which, how long the ride takes, and roughly how long you
wait, because the point of the bus is that the minutes you spend riding are
minutes you are not exposed to the street.

So per route and direction we keep one representative stop pattern (the trip
that visits the most stops) with its cumulative ride times, plus a headway
estimated from how many trips run that pattern.
"""
import csv, io, json, os, sys, urllib.request, zipfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

FEEDS = {
    "bus":  "https://gitlab.com/LACMTA/gtfs_bus/-/raw/master/gtfs_bus.zip",
    "rail": "https://gitlab.com/LACMTA/gtfs_rail/-/raw/master/gtfs_rail.zip",
}
SERVICE_HOURS = 18.0        # span a weekday pattern realistically operates
MIN_WAIT, MAX_WAIT = 4.0, 25.0


def download(kind, url):
    path = os.path.join(C.RAW, f"gtfs_{kind}.zip")
    if os.path.exists(path) and os.path.getsize(path) > 200_000:
        print(f"  {kind}: cached", flush=True)
        return path
    print(f"  {kind}: downloading", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "safe-routes-to-school/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
        f.write(r.read())
    print(f"  {kind}: {os.path.getsize(path)/1e6:.1f} MB", flush=True)
    return path


def rows(zf, name):
    with zf.open(name) as fh:
        for r in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig")):
            yield r


def hhmmss(s):
    try:
        h, m, sec = (s or "").split(":")
        return int(h) * 3600 + int(m) * 60 + int(sec)
    except Exception:
        return None


def parse(kind, path, stops, patterns, names):
    with zipfile.ZipFile(path) as zf:
        inside = set(zf.namelist())

        # ---- stops we care about
        local = {}
        for r in rows(zf, "stops.txt"):
            try:
                la, lo = float(r["stop_lat"]), float(r["stop_lon"])
            except (TypeError, ValueError, KeyError):
                continue
            if not C.in_bbox(la, lo):
                continue
            local[r["stop_id"]] = (la, lo, (r.get("stop_name") or "").strip())

        # ---- route labels
        route_label = {}
        for r in rows(zf, "routes.txt"):
            short = (r.get("route_short_name") or "").strip()
            long_ = (r.get("route_long_name") or "").strip()
            route_label[r["route_id"]] = short or long_ or r["route_id"]

        # ---- trip -> (route, direction)
        trip_key, key_trips = {}, defaultdict(list)
        for r in rows(zf, "trips.txt"):
            k = (r["route_id"], r.get("direction_id", "0"))
            trip_key[r["trip_id"]] = k
            key_trips[k].append(r["trip_id"])

        # ---- pass 1: how many stops does each trip make
        count = defaultdict(int)
        if "stop_times.txt" not in inside:
            return
        for r in rows(zf, "stop_times.txt"):
            count[r["trip_id"]] += 1

        # representative trip per route+direction
        best = {}
        for k, tids in key_trips.items():
            pick = max(tids, key=lambda t: count.get(t, 0))
            if count.get(pick, 0) >= 2:
                best[k] = pick
        wanted = {t: k for k, t in best.items()}

        # ---- pass 2: collect the chosen trips only
        seq = defaultdict(list)
        for r in rows(zf, "stop_times.txt"):
            k = wanted.get(r["trip_id"])
            if k is None:
                continue
            try:
                order = int(r["stop_sequence"])
            except (TypeError, ValueError):
                continue
            seq[k].append((order, r["stop_id"], hhmmss(r.get("departure_time")
                                                      or r.get("arrival_time"))))

        for k, items in seq.items():
            items.sort()
            ids, times = [], []
            t0 = None
            for _, sid, t in items:
                if sid not in local:
                    # A pattern can leave the study area and come back. Break it
                    # rather than implying a ride between two unconnected stops.
                    continue
                if sid not in stops:
                    la, lo, nm = local[sid]
                    if nm not in names:
                        names[nm] = len(names)
                    stops[sid] = [round(la, 6), round(lo, 6), names[nm]]
                if t is not None and t0 is None:
                    t0 = t
                ids.append(sid)
                times.append(0 if t is None or t0 is None else max(0, t - t0))
            if len(ids) < 2:
                continue
            trips_per_day = len(key_trips[k])
            tph = max(trips_per_day / SERVICE_HOURS, 0.01)
            wait = min(MAX_WAIT, max(MIN_WAIT, 30.0 / tph))
            patterns.append({
                "r": route_label.get(k[0], k[0]),
                "k": kind,
                "w": round(wait, 1),
                "s": ids,
                "t": times,
            })


def main():
    os.makedirs(C.RAW, exist_ok=True)
    stops, patterns, names = {}, [], {}
    for kind, url in FEEDS.items():
        p = download(kind, url)
        print(f"  parsing {kind}", flush=True)
        parse(kind, p, stops, patterns, names)
        print(f"    stops so far {len(stops):,}, patterns {len(patterns):,}", flush=True)

    # Reindex stop ids to array positions so the client holds flat arrays.
    order = list(stops.keys())
    pos = {sid: i for i, sid in enumerate(order)}
    out = {
        "names": [n for n, _ in sorted(names.items(), key=lambda kv: kv[1])],
        "stops": [stops[s] for s in order],
        "patterns": [
            {"r": p["r"], "k": p["k"], "w": p["w"],
             "s": [pos[s] for s in p["s"]], "t": p["t"]}
            for p in patterns
        ],
    }
    os.makedirs(C.OUT, exist_ok=True)
    path = os.path.join(C.OUT, "transit.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n{len(out['stops']):,} stops, {len(out['patterns']):,} patterns "
          f"-> {path} ({os.path.getsize(path)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
