"""Download the walkable street network from OpenStreetMap via Overpass.

Requested as ways-plus-nodes (not `out geom`) because we need the shared OSM
node ids: two ways that reference the same node are genuinely connected, which
is what makes the routing graph's topology correct at intersections.
Tiled + cached per tile so one Overpass timeout doesn't restart the download.
"""
import json, os, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

TILES = 4  # TILES x TILES grid over the bbox

WALKABLE = ("residential|footway|path|pedestrian|living_street|service|steps|"
            "tertiary|tertiary_link|secondary|secondary_link|primary|primary_link|"
            "unclassified|track|cycleway|road")

QUERY = """[out:json][timeout:300];
way["highway"~"^({hw})$"]["foot"!~"^(no|private)$"]["access"!~"^(private|no)$"]
  ({s},{w},{n},{e});
out body;
>;
out skel qt;
"""


# The main Overpass instance rate-limits hard and times out on the densest
# tiles; rotating mirrors turns a failed run into a merely slow one.
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
# overpass.osm.jp was dropped from this list: it serves a certificate that is
# not valid for its own hostname, so every request to it fails TLS verification
# rather than merely being slow. A mirror that cannot be reached is worse than
# one that is missing, because the rotation spends a retry on it.
# `python pipeline/check_apis.py` probes whatever is in this list.


def fetch_tile(s, w, n, e, idx):
    cache = os.path.join(C.RAW, f"osm_tile_{idx}.json")
    if os.path.exists(cache) and os.path.getsize(cache) > 500:
        print(f"  tile {idx}: cached", flush=True)
        with open(cache) as f:
            return json.load(f)
    q = QUERY.format(hw=WALKABLE, s=s, w=w, n=n, e=e)
    data = urllib.parse.urlencode({"data": q}).encode()
    for attempt in range(8):
        endpoint = MIRRORS[attempt % len(MIRRORS)]
        try:
            req = urllib.request.Request(
                endpoint, data=data,
                headers={"User-Agent": "safe-routes-to-school/1.0 (student project)"})
            with urllib.request.urlopen(req, timeout=400) as r:
                out = json.load(r)
            if not out.get("elements"):
                raise ValueError("empty response")
            with open(cache, "w") as f:
                json.dump(out, f)
            print(f"  tile {idx}: {len(out['elements']):,} elements "
                  f"[{endpoint.split('/')[2]}]", flush=True)
            return out
        except Exception as ex:
            wait = min(60, 10 * (attempt + 1))
            print(f"  tile {idx} attempt {attempt+1} on {endpoint.split('/')[2]} "
                  f"failed ({ex}); waiting {wait}s", flush=True)
            if attempt == 7:
                raise
            time.sleep(wait)


def main():
    os.makedirs(C.RAW, exist_ok=True)
    b = C.BBOX
    dlat = (b["north"] - b["south"]) / TILES
    dlon = (b["east"] - b["west"]) / TILES
    ways, nodes = {}, {}
    idx = 0
    for i in range(TILES):
        for j in range(TILES):
            idx += 1
            s = b["south"] + i * dlat
            n = s + dlat
            w = b["west"] + j * dlon
            e = w + dlon
            res = fetch_tile(round(s, 5), round(w, 5), round(n, 5), round(e, 5), idx)
            for el in res.get("elements", []):
                if el["type"] == "way":
                    ways[el["id"]] = el
                elif el["type"] == "node":
                    nodes[el["id"]] = (el["lat"], el["lon"])
            time.sleep(2)  # be polite to the public Overpass instance
    print(f"\ntotal: {len(ways):,} ways, {len(nodes):,} nodes", flush=True)
    with open(os.path.join(C.RAW, "osm_ways.json"), "w") as f:
        json.dump({"ways": list(ways.values()),
                   "nodes": {str(k): v for k, v in nodes.items()}}, f)
    print("wrote data/raw/osm_ways.json")


if __name__ == "__main__":
    main()
