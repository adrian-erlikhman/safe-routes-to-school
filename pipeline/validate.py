"""Sanity-check the built graph and verify the routing maths.

Three things worth proving before trusting any number the UI prints:

  1. the graph is connected and the risk surface is sanely distributed
  2. the A* used in the browser returns *exactly* the same cost as plain
     Dijkstra -- i.e. straight-line distance really is an admissible heuristic
     under the risk-weighted cost, so routes are optimal and not just plausible
  3. routing for safety actually reduces exposure, and by how much

Run after build_graph.py:  python pipeline/validate.py
"""
import heapq, json, math, os, random, sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

MAGIC = 0x53525453
FORMAT_VERSION = 2
# Six uint32: magic, version, nNodes, nEdges, nGeom, nNames.
HEADER_BYTES = 24


def load():
    """Read graph.bin using the same section order the writer emits."""
    path = os.path.join(C.OUT, "graph.bin")
    raw = np.fromfile(path, dtype=np.uint8)
    head = raw[:HEADER_BYTES].view(np.uint32)
    if int(head[0]) != MAGIC:
        raise SystemExit("bad magic -- not a graph.bin")
    if int(head[1]) != FORMAT_VERSION:
        raise SystemExit(f"graph format v{int(head[1])}, expected "
                         f"v{FORMAT_VERSION}")
    nN, nE, nG = int(head[2]), int(head[3]), int(head[4])

    # Every section offset is derived from the header, so a wrong header size
    # silently shifts every array by a few bytes rather than failing loudly.
    # Check the total instead: it only adds up when all six fields are right.
    want = (HEADER_BYTES + nN * 8 + nE * 4 + nE * 4 + (nE + 1) * 4
            + nG * 8 + nE * 2 + nE * 2 + nE * 3)
    if want != raw.size:
        raise SystemExit(f"graph.bin is {raw.size:,} bytes, header implies "
                         f"{want:,} -- section layout has drifted")

    o = HEADER_BYTES
    nodes = raw[o:o + nN * 8].view(np.int32).reshape(nN, 2) / 1e6
    o += nN * 8
    eu = raw[o:o + nE * 4].view(np.int32); o += nE * 4
    ev = raw[o:o + nE * 4].view(np.int32); o += nE * 4
    o += (nE + 1) * 4          # geom offsets -- not needed for validation
    o += nG * 8                # geom points
    ed = raw[o:o + nE * 2].view(np.uint16); o += nE * 2
    o += nE * 2                # street-name ids -- not needed for validation
    er = raw[o:o + nE * 3].view(np.uint8).reshape(nE, 3)
    if o + nE * 3 != raw.size:
        raise SystemExit("risk section does not end at EOF -- layout drift")

    meta = json.load(open(os.path.join(C.OUT, "graph_meta.json")))
    return dict(nodes=nodes, eu=eu, ev=ev, ed=ed, er=er, meta=meta,
                nN=nN, nE=nE)


def adjacency(g):
    adj = defaultdict(list)
    eu, ev = g["eu"], g["ev"]
    for i in range(g["nE"]):
        adj[int(eu[i])].append((int(ev[i]), i))
        adj[int(ev[i])].append((int(eu[i]), i))
    return adj


def metres(a, b):
    return math.hypot((a[1] - b[1]) * 92500.0, (a[0] - b[0]) * 111320.0)


def cost(g, ei, lam, b):
    r = g["er"][ei, b] / 255.0
    return float(g["ed"][ei]) * (1.0 + lam * r * math.sqrt(r))


def dijkstra(g, adj, src, dst, lam, b):
    dist = {src: 0.0}
    pq = [(0.0, src)]
    done = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u)
        if u == dst:
            return d, len(done)
        for v, ei in adj[u]:
            if v in done:
                continue
            nd = d + cost(g, ei, lam, b)
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return math.inf, len(done)


def astar(g, adj, src, dst, lam, b):
    nodes = g["nodes"]
    dist = {src: 0.0}
    pq = [(metres(nodes[src], nodes[dst]), src)]
    done = set()
    while pq:
        _, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u)
        if u == dst:
            return dist[u], len(done)
        for v, ei in adj[u]:
            if v in done:
                continue
            nd = dist[u] + cost(g, ei, lam, b)
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                heapq.heappush(pq, (nd + metres(nodes[v], nodes[dst]), v))
    return math.inf, len(done)


def path_stats(g, adj, src, dst, lam, b):
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, src)]
    done = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u)
        if u == dst:
            break
        for v, ei in adj[u]:
            if v in done:
                continue
            nd = d + cost(g, ei, lam, b)
            if nd < dist.get(v, math.inf):
                dist[v] = nd
                prev[v] = (u, ei)
                heapq.heappush(pq, (nd, v))
    if dst not in dist:
        return None
    length = exposure = 0.0
    cur = dst
    while cur != src:
        u, ei = prev[cur]
        length += float(g["ed"][ei])
        exposure += float(g["ed"][ei]) * (g["er"][ei, b] / 255.0)
        cur = u
    return length, exposure


def pick_pair(g, adj, rng, target_m=1400):
    """A random source and a node roughly `target_m` away, both connected."""
    nodes = g["nodes"]
    for _ in range(400):
        src = rng.randrange(g["nN"])
        if len(adj[src]) < 2:
            continue
        # sample candidates and take the one closest to the target distance
        cands = [rng.randrange(g["nN"]) for _ in range(600)]
        dst = min(cands, key=lambda k: abs(metres(nodes[src], nodes[k]) - target_m))
        if len(adj[dst]) >= 2 and dst != src:
            return src, dst
    return None, None


def main():
    g = load()
    nodes, er, ed = g["nodes"], g["er"], g["ed"]
    print(f"nodes {g['nN']:,}   edges {g['nE']:,}")
    print(f"meta  {json.dumps({k: v for k, v in g['meta'].items() if k != 'bbox'})}")

    adj = adjacency(g)
    deg = np.zeros(g["nN"], dtype=np.int32)
    np.add.at(deg, g["eu"], 1)
    np.add.at(deg, g["ev"], 1)
    print(f"degree: mean {deg.mean():.2f}  min {deg.min()}  "
          f"isolated {(deg == 0).sum()}")
    print(f"network length: {ed.astype(np.int64).sum()/1000:,.0f} km")
    print(f"block length: median {np.median(ed):.0f} m  max {ed.max()} m")

    for b, name in enumerate(g["meta"]["buckets"]):
        r = er[:, b] / 255.0
        print(f"  {name:5} risk  mean {r.mean():.3f}  p50 {np.percentile(r,50):.3f}"
              f"  p90 {np.percentile(r,90):.3f}  p99 {np.percentile(r,99):.3f}")

    # Buckets must actually differ, or the time selector is decoration.
    a, n = er[:, 0] / 255.0, er[:, 2] / 255.0
    print(f"  am vs night: corr {np.corrcoef(a, n)[0,1]:.3f}, "
          f"{int((np.abs(a-n) > 0.15).sum()):,} blocks differ by >0.15")

    # ------------------------------------------------ A* vs Dijkstra equality
    print("\nA* optimality vs Dijkstra (identical cost required):")
    rng = random.Random(7)
    ok = True
    for t in range(6):
        src, dst = pick_pair(g, adj, rng)
        if src is None:
            continue
        lam = [0.0, 2.0, 5.0][t % 3]
        b = t % 3
        dj, dn = dijkstra(g, adj, src, dst, lam, b)
        ast, an = astar(g, adj, src, dst, lam, b)
        if math.isinf(dj) and math.isinf(ast):
            print(f"  {t}: both unreachable (consistent)")
            continue
        match = abs(dj - ast) < 1e-6
        ok &= match
        print(f"  {t}: lam={lam:<4} bucket={g['meta']['buckets'][b]:5} "
              f"cost={dj:11,.1f}  settled dijkstra={dn:6,} astar={an:6,}  "
              f"({100*an/max(dn,1):.0f}% of the work)  "
              f"{'MATCH' if match else 'MISMATCH'}")
    print("  ->", "PASS" if ok else "FAIL")

    # ------------------------------------------- does safety routing do work?
    print("\nsafest vs shortest, after dark (lambda=5):")
    rng = random.Random(11)
    wins = trials = 0
    for _ in range(6):
        src, dst = pick_pair(g, adj, rng)
        if src is None:
            continue
        base = path_stats(g, adj, src, dst, 0.0, 2)
        safe = path_stats(g, adj, src, dst, 5.0, 2)
        if not base or not safe or base[0] == 0 or base[1] == 0:
            continue
        trials += 1
        cut = (1 - safe[1] / base[1]) * 100
        extra = (safe[0] / base[0] - 1) * 100
        if cut > 0.5:
            wins += 1
        print(f"  {base[0]:6.0f} m -> {safe[0]:6.0f} m (+{extra:4.1f}%)   "
              f"exposure {base[1]:8.0f} -> {safe[1]:8.0f}  ({cut:+5.1f}%)")
    print(f"  -> exposure reduced on {wins}/{trials} trips")


if __name__ == "__main__":
    main()
