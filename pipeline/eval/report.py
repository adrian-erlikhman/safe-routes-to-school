"""Render the evaluation results as one self-contained HTML page.

Markdown is the right format for the results files themselves -- they are read
in diffs and in pull requests. It is the wrong format for showing somebody
whether a model works, because the thing that matters is a comparison against
baselines and a noise floor, and comparison is what a page can draw and a table
cannot.

Everything is inline: no CDN, no fonts, no scripts. The page is served from
GitHub Pages alongside the app, and the app's whole design is that it keeps
working with no network.

  python pipeline/eval/report.py --out docs/validation.html
"""
import argparse, datetime as dt, html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CSS = """
:root{
  --bg:#f7f7f5; --panel:#fff; --ink:#1a1a18; --muted:#6b6b66; --line:#e2e2dd;
  --good:#3c7a4e; --warn:#c8912b; --bad:#a52714; --accent:#2d5f8a;
  --floor:#9a9a94; --shadow:0 1px 2px rgba(0,0,0,.05),0 8px 24px rgba(0,0,0,.05);
}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
  --bg:#16161a; --panel:#1e1e23; --ink:#eceCE8; --muted:#9a9a94; --line:#32323a;
  --good:#6fae80; --warn:#e0b45c; --bad:#e0685a; --accent:#7fb0dd;
  --floor:#6b6b66; --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.25);
}}
:root[data-theme=dark]{
  --bg:#16161a; --panel:#1e1e23; --ink:#ececE8; --muted:#9a9a94; --line:#32323a;
  --good:#6fae80; --warn:#e0b45c; --bad:#e0685a; --accent:#7fb0dd;
  --floor:#6b6b66; --shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.25);
}
*{box-sizing:border-box}
html,body{max-width:100%;overflow-x:clip}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
  "Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:900px;margin:0 auto;padding:48px 16px 96px}
header{margin-bottom:40px}
h1{font-size:clamp(28px,5vw,40px);line-height:1.15;margin:0 0 8px;
  letter-spacing:-.02em}
.sub{color:var(--muted);margin:0;font-size:17px}
h2{font-size:22px;margin:48px 0 4px;letter-spacing:-.01em}
h2+.lede{color:var(--muted);margin:0 0 20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:24px;box-shadow:var(--shadow);margin:20px 0}
.verdict{border-left:4px solid var(--bad)}
.verdict.pass{border-left-color:var(--good)}
.verdict h3{margin:0 0 10px;font-size:19px;line-height:1.35}
.verdict p{margin:0;color:var(--muted)}
.banner{background:var(--warn);color:#1a1a18;border-radius:10px;padding:12px 16px;
  font-weight:600;font-size:14px;margin:0 0 24px;letter-spacing:.01em}
table{width:100%;border-collapse:collapse;font-size:14px;margin:4px 0}
th{text-align:left;font-weight:600;color:var(--muted);font-size:12px;
  text-transform:uppercase;letter-spacing:.06em;padding:8px 10px;
  border-bottom:1px solid var(--line)}
th.num,td.num{white-space:nowrap}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -4px;
  padding:0 4px}
td{padding:9px 10px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:0}
td.num{text-align:right;font-variant-numeric:tabular-nums}
tr.model td{font-weight:650}
tr.model td:first-child::before{content:"";display:inline-block;width:6px;
  height:6px;border-radius:50%;background:var(--accent);margin-right:8px;
  vertical-align:middle}
.tag{display:inline-block;font-size:11px;padding:2px 7px;border-radius:99px;
  border:1px solid var(--line);color:var(--muted);vertical-align:middle;
  margin-left:8px;text-transform:uppercase;letter-spacing:.05em}
.bars{margin:8px 0 0}
.bar-row{display:grid;grid-template-columns:minmax(0,1fr) 56px;gap:12px;
  align-items:center;padding:7px 0}
.bar-label{font-size:14px;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.bar-label code{font-size:13px;background:none;padding:0}
.track{height:9px;background:var(--line);border-radius:99px;overflow:hidden;
  margin-top:5px}
.fill{height:100%;border-radius:99px;background:var(--accent)}
.fill.floor{background:var(--floor)}
.bar-val{text-align:right;font-variant-numeric:tabular-nums;font-size:14px;
  font-weight:650}
.note{color:var(--muted);font-size:14px}
code{background:var(--line);padding:1px 5px;border-radius:4px;font-size:13px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
pre{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:14px 16px;overflow-x:auto;font-size:13px;
  font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
pre code{background:none;padding:0}
footer{margin-top:64px;padding-top:24px;border-top:1px solid var(--line);
  color:var(--muted);font-size:13px}
a{color:var(--accent)}
@media (max-width:560px){
  .wrap{padding:28px 16px 64px}
  th,td{padding:7px 6px;font-size:13px}
  .hide-sm{display:none}
}
"""


def esc(x):
    return html.escape(str(x))


def bars(rows, floor=None):
    """Horizontal bars, scaled to the largest value, floor marked if given."""
    top = max([abs(v) for _, v in rows] + [1e-9])
    out = ['<div class="bars">']
    for label, v in rows:
        is_floor = floor is not None and label.lower().startswith("control")
        pct = 100 * abs(v) / top
        out.append(
            f'<div class="bar-row"><div class="bar-label">{label}'
            f'<div class="track"><i class="fill{" floor" if is_floor else ""}" '
            f'style="width:{pct:.1f}%;display:block"></i></div></div>'
            f'<div class="bar-val">{100*v:.0f}%</div></div>')
    out.append("</div>")
    return "\n".join(out)


def holdout_section(data, label, synthetic=True):
    if not data:
        return ""
    rows = [r for r in data["rows"] if r["outcome"] == "juvenile"]
    order = ["model", "train_count", "count_2023", "uniform"]
    pretty = {"model": "kernel model", "train_count": "count, no kernel",
              "count_2023": "2023 count only", "uniform": "uniform"}
    out = [f'<h2>{esc(label)}</h2>']
    if synthetic:
        out.append(
            '<p class="banner">These are not Los Angeles numbers. Synthetic '
            'incidents with 220 planted hotspots, on the real street network, '
            'so a working holdout has to find them. This table shows the '
            'evaluation works. It says nothing about the real model.</p>')
    out.append('<div class="card"><div class="scroll"><table>'
               '<thead><tr>'
               '<th>Window</th><th>Model</th><th class="num">Top 1%</th>'
               '<th class="num hide-sm">Top 5%</th>'
               '<th class="num hide-sm">PAI@1%</th>'
               '<th class="num">AUC</th></tr></thead><tbody>')
    for b in ("am", "pm", "night"):
        for name in order:
            r = next((r for r in rows if r["bucket"] == b
                      and r["model"] == name), None)
            if not r:
                continue
            h = {x["frac"]: x for x in r["hits"]}
            cls = ' class="model"' if name == "model" else ""
            out.append(
                f'<tr{cls}><td>{esc(b)}</td><td>{esc(pretty[name])}</td>'
                f'<td class="num">{100*h[0.01]["hit_rate"]:.1f}%</td>'
                f'<td class="num hide-sm">{100*h[0.05]["hit_rate"]:.1f}%</td>'
                f'<td class="num hide-sm">{h[0.01]["pai"]:.1f}</td>'
                f'<td class="num">{r["auc"]:.3f}</td></tr>')
    out.append("</tbody></table></div></div>")
    return "\n".join(out)


def build(args):
    hold = json.load(open(args.holdout)) if args.holdout \
        and os.path.exists(args.holdout) else None
    sens = json.load(open(args.sensitivity)) if args.sensitivity \
        and os.path.exists(args.sensitivity) else None

    parts = []
    parts.append('<header><h1>Does the risk model predict anything?</h1>'
                 '<p class="sub">Out-of-sample validation for '
                 '<a href="../">Safe Routes to School</a>. '
                 'The router is provably correct; that is a different question '
                 'from whether the thing it routes over is.</p></header>')

    if args.status == "unvalidated":
        parts.append(
            '<div class="card verdict"><h3>Not yet validated against Los '
            'Angeles.</h3><p>The holdout is written, tested and ready, and has '
            'never been run on real incidents: the cache is not in the '
            'repository and the source API was unreachable from where this was '
            'built. No claim about this model&rsquo;s predictive skill is '
            'currently supported. Everything below tests the <em>evaluation</em>, '
            'on synthetic fixtures with known answers.</p></div>')
        parts.append('<pre><code>python pipeline/fetch_crime.py\n'
                     'python pipeline/eval/holdout.py</code></pre>')

    parts.append('<h2>What is actually proven</h2>'
                 '<p class="lede">Three claims, three very different levels of '
                 'evidence.</p><div class="card"><table><tbody>'
                 '<tr><td>A* returns exactly Dijkstra&rsquo;s cost</td>'
                 '<td class="num" style="color:var(--good);font-weight:650">'
                 'proven</td></tr>'
                 '<tr><td>The &ldquo;safer&rdquo; route has lower exposure</td>'
                 '<td class="num" style="color:var(--warn);font-weight:650">'
                 'circular</td></tr>'
                 '<tr><td>The risk surface predicts where crime happens</td>'
                 '<td class="num" style="color:var(--bad);font-weight:650">'
                 'untested</td></tr>'
                 '</tbody></table>'
                 '<p class="note" style="margin:14px 0 0">'
                 'The middle row is true by construction &mdash; exposure is '
                 'defined by the surface &mdash; so a surface of random numbers '
                 'would satisfy it too.</p></div>')

    if hold:
        parts.append(holdout_section(hold, args.holdout_label,
                                     synthetic=args.status == "unvalidated"))

    if sens:
        by = {}
        for r in sens:
            by.setdefault(r["param"], []).append(r)
        ranked = sorted(by.items(),
                        key=lambda kv: -max(x["routes"] for x in kv[1]))
        rows = [(f'<code>{esc(n)}</code>' if not n.startswith("CONTROL")
                 else f'<span style="color:var(--muted)">{esc(n)}</span>',
                 max(x["routes"] for x in v)) for n, v in ranked]
        floor = next((max(x["routes"] for x in v) for n, v in ranked
                      if n.startswith("CONTROL")), None)
        parts.append('<h2>Which constants move the recommendation</h2>'
                     '<p class="lede">Share of the safest route&rsquo;s length '
                     'that changes when each constant is perturbed over a range '
                     'a reasonable person might have chosen instead.</p>')
        parts.append('<div class="card">' + bars(rows, floor=floor)
                     + ('<p class="note" style="margin:16px 0 0">The grey bar '
                        'is the noise floor: perturbing the bandwidth by 1%, a '
                        'change nobody would argue about. Anything near it has '
                        'not been shown to matter.</p>' if floor is not None
                        else "") + '</div>')

    parts.append(
        '<h2>What it cannot tell you</h2>'
        '<div class="card"><p style="margin:0">Both the fit and the test come '
        'from the same reporting process, with the same variation in who calls '
        'the police and who does not. A holdout drawn from one source cannot '
        'see past that. Even a passing result would mean the model predicts '
        '<em>recorded</em> crime &mdash; which is not the same claim, and is '
        'not the one a parent reads it as.</p></div>')

    parts.append(f'<footer>Generated by <code>pipeline/eval/report.py</code> on '
                 f'{dt.date.today().isoformat()}. Source: '
                 f'<code>pipeline/eval/holdout_results.md</code> and '
                 f'<code>sensitivity_results.md</code>.</footer>')

    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,'
            f'initial-scale=1">'
            f'<title>Model Validation</title>'
            f'<meta name="description" content="Out-of-sample validation of the '
            f'Safe Routes to School risk model.">'
            f'<style>{CSS}</style></head><body><div class="wrap">'
            + "\n".join(parts) + '</div></body></html>')
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", default=None, help="holdout_results.json")
    ap.add_argument("--sensitivity", default=None,
                    help="sensitivity_results.json")
    ap.add_argument("--holdout-label",
                    default="Holdout, on a synthetic fixture")
    ap.add_argument("--status", choices=("unvalidated", "validated"),
                    default="unvalidated")
    ap.add_argument("--out", default="docs/validation.html")
    a = ap.parse_args()
    page = build(a)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        f.write(page)
    print(f"wrote {a.out}  ({len(page)/1000:.0f} kB)")


if __name__ == "__main__":
    main()
