"""Probe every upstream this pipeline depends on, and say which ones answer.

Five public services stand between a clone of this repository and a working
build, and they fail in different ways: a Socrata dataset gets retired, an
ArcGIS layer is renumbered, an Overpass mirror goes down for a week, a GTLab
raw URL moves. When `fetch_*.py` then dies eight minutes in, the error rarely
names the real problem.

This asks each one a cheap question -- one row, one layer description, one
status line -- and reports what came back, so a failed build can be diagnosed
in ten seconds instead of by reading four fetch scripts.

  python pipeline/check_apis.py
  python pipeline/check_apis.py --json      # for CI
"""
import argparse, json, os, socket, ssl, sys, time
import urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

# Overpass status endpoints answer slowly when an instance is busy, and a
# timeout here would read as "down" when the real fetch (which allows 300 s)
# would have succeeded. 45 s is long enough to tell busy from broken.
TIMEOUT = 45

# Overpass mirrors are listed in fetch_osm.py; keep them in step by importing
# rather than copying, so a mirror added there is probed here automatically.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fetch_osm import MIRRORS as OSM_MIRRORS
except Exception:
    OSM_MIRRORS = [C.OVERPASS]
try:
    from fetch_transit import FEEDS as GTFS_FEEDS
except Exception:
    GTFS_FEEDS = {}
try:
    # Probe the CDE directory through the opener fetch_schools actually uses,
    # so this check tests the fetch rather than just the host.
    from fetch_schools import opener as cde_opener
except Exception:
    cde_opener = None


def probe(name, url, check=None, method="GET", head_bytes=4096, opener=None,
          timeout=None):
    """Fetch a little of `url` and run `check` over it. Never raises.

    `opener` lets a probe go through the same machinery its fetch script uses,
    so a green check here means that script would work rather than merely that
    the host is up.
    """
    t0 = time.time()
    rec = dict(name=name, url=url.split("?")[0], ok=False, detail="", ms=0)
    try:
        req = urllib.request.Request(url, method=method,
                                     headers={"User-Agent": "safe-routes-check"})
        open_fn = opener.open if opener is not None else urllib.request.urlopen
        with open_fn(req, timeout=timeout or TIMEOUT) as r:
            body = r.read(head_bytes) if method == "GET" else b""
            rec["status"] = r.status
            rec["ok"] = 200 <= r.status < 300
            if rec["ok"] and check:
                ok, detail = check(body, r.headers.get("content-type", ""))
                rec["ok"], rec["detail"] = ok, detail
            elif rec["ok"]:
                # A HEAD has no body, so report what the server declares.
                size = r.headers.get("content-length")
                rec["detail"] = (f"{int(size)/1e6:.1f} MB" if size
                                 else f"{len(body):,} bytes")
    except urllib.error.HTTPError as e:
        rec["status"] = e.code
        rec["detail"] = f"HTTP {e.code} {e.reason}"
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        rec["detail"] = f"{type(reason).__name__}: {reason}"
        if isinstance(reason, ssl.SSLError):
            rec["detail"] += "  (TLS -- check the CA bundle if behind a proxy)"
    except (socket.timeout, TimeoutError):
        rec["detail"] = f"timed out after {timeout or TIMEOUT}s"
    except Exception as e:                     # noqa: BLE001 -- a probe must not throw
        rec["detail"] = f"{type(e).__name__}: {e}"
    rec["ms"] = int((time.time() - t0) * 1000)
    return rec


# ------------------------------------------------------------------- checkers
def json_rows(body, ctype=""):
    try:
        rows = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return False, "response was not JSON (dataset retired or renamed?)"
    if not isinstance(rows, list) or not rows:
        return False, "JSON held no rows"
    want = {"date_occ", "time_occ", "crm_cd_desc", "lat", "lon"}
    missing = want - set(rows[0])
    return (not missing,
            "schema ok" if not missing else f"missing fields: {sorted(missing)}")


def arcgis_layer(body, ctype=""):
    try:
        meta = json.loads(body.decode("utf-8", "replace"))
    except Exception:
        # A retired or renamed layer answers 200 with an HTML error page, which
        # is a different problem from the 502s this service also throws, and the
        # two need different responses -- one is waited out, one is a code fix.
        snip = " ".join(body.decode("utf-8", "replace").split())[:110]
        return False, (f"not JSON (content-type {ctype or 'unset'}): {snip}"
                       if snip else f"empty body, content-type {ctype or 'unset'}")
    if "error" in meta:
        return False, str(meta["error"].get("message", meta["error"]))
    return True, f"layer {meta.get('id', '?')}: {meta.get('name', 'unnamed')}"


def overpass_status(body, ctype=""):
    text = body.decode("utf-8", "replace")
    for line in text.splitlines():
        if "slots available" in line or "Connected as" in line:
            return True, line.strip()
    return bool(text.strip()), text.splitlines()[0][:70] if text.strip() else "empty"


def tab_header(body, ctype=""):
    line = body.decode("utf-8", "replace").splitlines()[:1]
    if not line:
        return False, "empty response"
    cols = line[0].split("\t")
    return len(cols) > 5, f"{len(cols)} tab-separated columns"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--warn-only", action="store_true",
                    help="always exit 0; these are third-party services and "
                         "one being down is not a broken pull request")
    ap.add_argument("--github-summary", action="store_true",
                    help="write a table to $GITHUB_STEP_SUMMARY and raise a "
                         "workflow annotation for anything not answering")
    a = ap.parse_args()

    # Keyword args throughout: `probe` takes head_bytes before opener, so a
    # positional list silently binds an opener to head_bytes. That shipped once
    # and crashed the CDE probe.
    checks = []

    crime_url = C.SOCRATA_CRIME + "?" + urllib.parse.urlencode(
        {"$select": "dr_no,date_occ,time_occ,crm_cd_desc,premis_desc,"
                    "vict_age,lat,lon", "$limit": 1})
    checks.append(dict(name="LAPD crime (Socrata)", url=crime_url,
                       check=json_rows))

    lights_url = ("https://maps.lacity.org/lahub/rest/services/"
                  "Bureau_of_Street_Lighting/MapServer/0?f=json")
    checks.append(dict(name="Streetlights (ArcGIS)", url=lights_url,
                       check=arcgis_layer))

    checks.append(dict(name="CDE school directory", url=C.CDE_SCHOOLS,
                       check=tab_header, timeout=180,
                       opener=cde_opener() if cde_opener else None))

    for i, m in enumerate(OSM_MIRRORS):
        checks.append(dict(name=f"Overpass mirror {i+1}",
                           url=m.replace("/interpreter", "/status"),
                           check=overpass_status))

    for kind, url in GTFS_FEEDS.items():
        checks.append(dict(name=f"LA Metro GTFS ({kind})", url=url,
                           method="HEAD"))

    results = [probe(**c) for c in checks]

    if a.json:
        print(json.dumps(results, indent=1))
    else:
        width = max(len(r["name"]) for r in results)
        print(f"{'upstream':<{width}}  {'':4} {'ms':>6}  detail")
        print("-" * (width + 40))
        for r in results:
            print(f"{r['name']:<{width}}  {'ok' if r['ok'] else 'FAIL':4} "
                  f"{r['ms']:>6}  {r['detail']}")

    # Overpass is the one service with mirrors, so one answering is enough.
    overpass = [r for r in results if r["name"].startswith("Overpass")]
    others = [r for r in results if not r["name"].startswith("Overpass")]
    bad = [r["name"] for r in others if not r["ok"]]
    if overpass and not any(r["ok"] for r in overpass):
        bad.append("every Overpass mirror")
    if not a.json:
        if bad:
            print(f"\n{len(bad)} upstream(s) not answering: {', '.join(bad)}")
            print("A build will fail at the matching fetch_* step. If these are "
                  "403s from a corporate or sandbox proxy, the services are "
                  "probably fine and the egress policy is not.")
        else:
            print("\nall upstreams answering -- a full build should fetch cleanly")

    if a.github_summary:
        summary(results, bad)
    return 0 if a.warn_only else (1 if bad else 0)


def summary(results, bad):
    """A table in the run summary, and one annotation per upstream that is down.

    An informational job that goes red teaches people to ignore red, so this
    reports through annotations instead: visible on the run, not a failed check.
    """
    lines = ["## Upstream data sources", "",
             "| Upstream | | Time | Detail |", "|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['name']} | {'ok' if r['ok'] else '**down**'} | "
                     f"{r['ms']:,} ms | {r['detail'] or ''} |")
    if bad:
        lines += ["", f"**{len(bad)} not answering.** These are third-party "
                      f"services outside this repository's control; a build "
                      f"would fail at the matching `fetch_*` step until they "
                      f"recover."]
    else:
        lines += ["", "All answering. A full build should fetch cleanly."]
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a") as f:
            f.write("\n".join(lines) + "\n")
    for r in results:
        if not r["ok"]:
            print(f"::warning title=Upstream down::{r['name']}: {r['detail']}")


if __name__ == "__main__":
    sys.exit(main())
