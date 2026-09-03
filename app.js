/* Safe Routes to School / Los Angeles
 *
 * Everything runs in the browser. The pipeline ships a packed binary graph
 * where each block already carries a risk score per time-of-day window, and
 * A* here minimises  length * (1 + lambda * risk^1.5)  instead of length.
 */
'use strict';

const MAGIC = 0x53525453;        // "SRTS"
const NO_NAME = 0xFFFF;
const WALK_MPS = 1.32;           // about 3 mph, an unhurried kid
const MAX_DRAW = 22000;          // viewport budget for the risk layer
const NOMINATIM = 'https://nominatim.openstreetmap.org/search';
const PHOTON = 'https://photon.komoot.io/api/';

/* Named options rather than a slider. A slider invites fiddling and never says
 * what its ends mean, while a route you can point at is a choice you can make.
 *
 * A fixed pair of lambdas often returns the same path twice, because past some
 * threshold the search has already routed around everything it can. So walk a
 * ladder, throw away duplicates, and offer only the options that differ. */
const LADDER = [0, 0.5, 1, 1.75, 2.75, 4.25, 7];

const N_COMPASS = 16;

/* Zoomed out, drawing every above-average block is an unreadable smear, so the
 * threshold rises with distance and detail fills in as you approach one walk. */
const FLOOR_BY_ZOOM = { 13: 0.60, 14: 0.50, 15: 0.42, 16: 0.36 };
const floorFor = z => FLOOR_BY_ZOOM[Math.min(16, Math.max(13, z))];

const S = {
  meta: null, schools: null, names: null,
  nLat: null, nLon: null,
  eu: null, ev: null, ed: null, er: null, ename: null,
  gOff: null, gPts: null,
  head: null, to: null, eidx: null,
  nNodes: 0, nEdges: 0,
  bucket: 1, pick: 2, mode: 'foot',
  origin: null, school: null,
  routes: null, report: null,
  showRisk: true, showSchools: false,
  lang: 'en', embed: false, preset: null,
};

/* ------------------------------------------------------------ language */
/* English lives in the HTML and in the table below; other languages ship as
 * es.js-style files that register on window.LANGS. Static text is swapped by
 * data-t key, and everything built at run time goes through t(). */
const EN = {
  'win.0': 'morning', 'win.1': 'afternoon', 'win.2': 'evening',
  'clock.0': '5am to 10am', 'clock.1': '10am to 5pm', 'clock.2': '5pm to 5am',
  'compass': 'N,NNE,NE,ENE,E,ESE,SE,SSE,S,SSW,SW,WSW,W,WNW,NW,NNW',

  'toast.nostreet': 'No walkable street near that point.',
  'toast.same': 'That start point is already at the school.',
  'toast.noroute': 'No walking route connects those points.',
  'toast.nobus': 'No single bus or rail ride links those points. Showing the walk.',
  'toast.rcnostreet': 'That school is not near a walkable street.',
  'toast.rcnone': 'Could not reach that school from any direction.',
  'toast.copyfail': 'Copy failed. The address bar holds the link.',
  'toast.print': 'Pick a route first.',
  'ac.none': 'Nothing found for that',
  'ac.busy': 'Searching…',
  'ac.offline': 'Offline: addresses cannot be looked up. Type two cross streets, or tap the map.',
  'ac.xstreet': 'cross streets',
  'geo.wait': 'Finding your location…',
  'geo.here': 'My location',
  'toast.nogeo': 'This browser does not share location.',
  'toast.geoout': 'You are outside the map area, which covers central Los Angeles.',
  'toast.geofail': 'Could not get your location. Check the browser permission.',

  'mode.none': 'Nothing within a 900 m walk of both ends shares one route, so these are '
    + 'walking options. Transfers are out of scope: each change adds another wait to stand through.',
  'mode.found': 'Riding covers distance without putting you on the street. Waiting does '
    + 'not, so a minute at a stop is charged like {w} m of walking there.',

  'opt.short': 'Shortest', 'opt.shortH': 'what a map app gives you',
  'opt.mid': 'Balanced', 'opt.midH': 'most calm per extra step',
  'opt.safe': 'Safest', 'opt.safeH': 'lowest exposure available',
  'opt.walk': 'Walk the whole way', 'opt.walkH': 'no bus, for comparison',
  'opt.route': 'Route {r}',
  'opt.then': ' then ',
  'opt.rideH': '{n} min riding, {d} on foot',
  'opt.change': ', one change',

  'card.less': '{cut}% less exposure',
  'card.min': '{n} min',
  'card.sub': '{d} walk / {e}',

  'why.same': 'The shortest way here is also the calmest one the model can find, so '
    + 'there is nothing to trade off.',
  'why.skips': 'Skips <b>{len}</b> of <span class="st">{st}</span>, which scores <b>{n}</b> at this hour.',
  'why.along': 'Goes along <span class="st">{st}</span> instead, at <b>{n}</b>.',
  'why.samelen': 'It comes out the same length.',
  'why.costm': 'Costs you <b>{m} m</b>, under a minute of walking.',
  'why.cost1': 'Costs you <b>1 minute</b>.',
  'why.costn': 'Costs you <b>{n} minutes</b>.',
  'why.drops': 'Total exposure drops <b>{cut}%</b>.',
  'unnamed': 'an unnamed path',
  'unnamed.turn': 'unnamed path',

  'why.t.ride': 'ride <b>{r}</b> for <b>{n} min</b>',
  'why.t.ridex': 'ride <b>{r}</b> for <b>{n} min</b> with one change at <span class="st">{stop}</span>',
  'why.t.main': 'Walk <b>{d1}</b> to <span class="st">{stop}</span>, wait about <b>{w} min</b> '
    + 'in total, then {ride}, then walk <b>{d2}</b> at the other end.',
  'why.t.only': 'Only <b>{d}</b> of this trip happens on the street.',
  'why.t.drops': 'Against walking the whole way, exposure drops <b>{cut}%</b>.',
  'why.t.flat': 'That is about the same exposure as walking it, so take whichever suits you.',

  'hours.now': '\u00B7 now',
  'hours.note': 'This same trip carries the most exposure in the {win} ({clock}). Changing '
    + 'the window above re-runs the search, which often returns a different route entirely.',

  'turn.board': 'Board {r} at {stop}',
  'turn.wait': 'wait {n} min',
  'turn.ride': 'Ride {n} stops',
  'turn.off': 'Get off at {stop}',
  'turn.xfer': 'Walk to {stop} to change',
  'stop.a': 'a stop',
  'mk.board': 'Board', 'mk.off': 'Get off', 'mk.change': 'Change here',
  'pin.start': 'Start',
  'dest.custom': 'Chosen destination',

  'rc.title': '{n} approaches / <b>{win}</b>',
  'rc.ratio': 'Approaching {school} from the <b>{worst}</b> means walking through '
    + '<b>{ratio} times</b> the exposure of the calmest approach, from the <b>{best}</b>.',
  'rc.same': 'Approaching {school} from the <b>{worst}</b> means walking through about the '
    + 'same exposure as the calmest approach, from the <b>{best}</b>.',
  'rc.tail': 'That is where a crossing guard, a lighting request or a walking group would do the most good.',

  'when.now': 'It is {clock}, so {win} is selected. Change it to plan a different walk.',
  'when.restored': 'Restored from a shared link.',
  'preset': 'This page is set up for <b>{school}</b>. Type where you start. '
    + '<a href="{href}">Not your school?</a>',
  'share.done': 'Link copied',
  'emb.done': 'Code copied',

  'net.saved': '<b>Saved on this device.</b> Works without a connection.',
  'net.off': '<b>Offline.</b> Routes still work; the map shows streets without labels.',

  'boot.build': 'Building the routing graph',
  'boot.sub': '{n} incidents / {km} km of street',
  'boot.fail': 'The data files did not load.',

  'pc.k': 'Walking card / Safe Routes to School',
  'pc.to': 'to {school}',
  'pc.from': 'From {from}',
  'pc.when': 'For the {win} ({clock}), {mode}.',
  'pc.mode.foot': 'on foot', 'pc.mode.bus': 'by bus or rail',
  'pc.opt': 'Option', 'pc.time': 'Time', 'pc.walk': 'On foot', 'pc.exp': 'Exposure',
  'pc.turns': 'Street by street', 'pc.hours': 'Same route, different hour',
  'pc.open': 'Open this trip on a phone',
  'pc.foot': 'Scores run 0 to 100 against every block in Los Angeles at that hour; lower is '
    + 'calmer. This is a second opinion about a walk, not a guarantee. Data: LAPD 2020 to '
    + '2024, LA Metro, OpenStreetMap.',
  'pc.printed': 'Printed {date}',
};

const LANGS = Object.assign({ en: { name: 'English', s: {}, d: EN } }, window.LANGS || {});

function t(key, vars) {
  const pack = LANGS[S.lang] || LANGS.en;
  let str = (pack.d && pack.d[key]) != null ? pack.d[key] : EN[key];
  if (str == null) return key;
  if (vars) for (const k in vars) str = str.split(`{${k}}`).join(vars[k]);
  return str;
}
const winName = b => t('win.' + b);
const winClock = b => t('clock.' + b);
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const compassName = k => t('compass').split(',')[k];

function applyLang() {
  const pack = LANGS[S.lang] || LANGS.en;
  document.documentElement.lang = S.lang;
  for (const el of document.querySelectorAll('[data-t]')) {
    if (el.dataset.en == null) el.dataset.en = el.innerHTML;
    const k = el.dataset.t;
    el.innerHTML = (S.lang !== 'en' && pack.s[k]) ? pack.s[k] : el.dataset.en;
  }
  for (const el of document.querySelectorAll('[data-tp]')) {
    if (el.dataset.enp == null) el.dataset.enp = el.placeholder;
    const k = el.dataset.tp;
    el.placeholder = (S.lang !== 'en' && pack.s[k]) ? pack.s[k] : el.dataset.enp;
  }
  for (const el of document.querySelectorAll('[data-dyn]')) {
    el.innerHTML = t(el.dataset.dyn, el.dataset.dynVars ? JSON.parse(el.dataset.dynVars) : null);
  }
  [...$('lang').children].forEach(c => c.classList.toggle('on', c.dataset.l === S.lang));
  $('lg-when').textContent = winName(S.bucket);
  renderPreset();
  renderEmbed();
  renderNet();
  if (S.routes) { renderCards(); select(S.pick, false); }
  if (S.report) renderReport();
}

/* Text set at run time that must survive a language switch is tagged with the
 * key it came from, so applyLang can rebuild it. */
function setDyn(el, key, vars) {
  el.dataset.dyn = key;
  if (vars) el.dataset.dynVars = JSON.stringify(vars); else delete el.dataset.dynVars;
  el.innerHTML = t(key, vars);
}

function setLang(l, persist = true) {
  if (!LANGS[l]) l = 'en';
  S.lang = l;
  if (persist) { try { localStorage.setItem('srs-lang', l); } catch (e) { /* private mode */ } }
  applyLang();
  writeUrl();
}

/* ------------------------------------------------------------------- map */
const map = L.map('map', { zoomControl: false, preferCanvas: true })
  .setView([34.035, -118.33], 13);
L.control.zoom({ position: 'bottomleft' }).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap &copy; CARTO / crime records: LAPD via data.lacity.org',
  maxZoom: 19, subdomains: 'abcd',
}).addTo(map);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png', {
  maxZoom: 19, subdomains: 'abcd', pane: 'shadowPane',
}).addTo(map);

const riskLayer = L.layerGroup().addTo(map);
const routeLayer = L.layerGroup().addTo(map);
const spokeLayer = L.layerGroup().addTo(map);
const pinLayer = L.layerGroup().addTo(map);
const schoolLayer = L.layerGroup();

/* ------------------------------------------------------------ utilities */
const $ = id => document.getElementById(id);
const fmtM = m => m < 950 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(2)} km`;
const fmtMin = m => t('card.min', { n: Math.max(1, Math.round(m / WALK_MPS / 60)) });
const risk = (ei, b) => S.er[ei * 3 + b] / 255;
const streetName = ei => (S.ename[ei] === NO_NAME ? null : S.names[S.ename[ei]]);

function toast(msg) {
  const t = $('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 3600);
}

/* Five flat steps rather than a smooth ramp, so the legend and the map agree
 * and a colour always maps back to a readable band. */
const BANDS = [
  { upto: 0.20, hex: '#3c7a4e' },
  { upto: 0.40, hex: '#7d9b3f' },
  { upto: 0.60, hex: '#c8912b' },
  { upto: 0.80, hex: '#c8622b' },
  { upto: 1.01, hex: '#a52714' },
];
const bandColor = v => (BANDS.find(b => v <= b.upto) || BANDS[4]).hex;

const metres = (aLat, aLon, bLat, bLon) =>
  Math.hypot((aLon - bLon) * 92500, (aLat - bLat) * 111320);

/* --------------------------------------------------------- binary heap */
class Heap {
  constructor(cap) { this.k = new Float64Array(cap); this.v = new Int32Array(cap); this.n = 0; }
  get size() { return this.n; }
  push(key, val) {
    if (this.n === this.k.length) this._grow();
    let i = this.n++;
    this.k[i] = key; this.v[i] = val;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (this.k[p] <= this.k[i]) break;
      this._swap(i, p); i = p;
    }
  }
  pop() {
    const top = this.v[0];
    const n = --this.n;
    this.k[0] = this.k[n]; this.v[0] = this.v[n];
    let i = 0;
    for (;;) {
      const l = 2 * i + 1, r = l + 1;
      let m = i;
      if (l < n && this.k[l] < this.k[m]) m = l;
      if (r < n && this.k[r] < this.k[m]) m = r;
      if (m === i) break;
      this._swap(i, m); i = m;
    }
    return top;
  }
  _swap(a, b) {
    const tk = this.k[a]; this.k[a] = this.k[b]; this.k[b] = tk;
    const tv = this.v[a]; this.v[a] = this.v[b]; this.v[b] = tv;
  }
  _grow() {
    const k = new Float64Array(this.k.length * 2), v = new Int32Array(this.v.length * 2);
    k.set(this.k); v.set(this.v); this.k = k; this.v = v;
  }
}

/* ------------------------------------------------------- binary decode */
/* Section order mirrors the writer: header, nodes(i32), eu(i32), ev(i32),
 * geomOff(u32), geomPts(i32), d(u16), name(u16), risk(u8). Ordering by
 * descending alignment means each view lands on a natural boundary. */
function decode(buf) {
  const h = new Uint32Array(buf, 0, 6);
  if (h[0] !== MAGIC) throw new Error('not a graph file');
  if (h[1] !== 2) throw new Error(`graph format v${h[1]} is not supported`);
  const nN = h[2], nE = h[3], nG = h[4];
  let o = 24;

  const nll = new Int32Array(buf, o, nN * 2); o += nN * 8;
  S.eu = new Int32Array(buf, o, nE); o += nE * 4;
  S.ev = new Int32Array(buf, o, nE); o += nE * 4;
  S.gOff = new Uint32Array(buf, o, nE + 1); o += (nE + 1) * 4;
  S.gPts = new Int32Array(buf, o, nG * 2); o += nG * 8;
  S.ed = new Uint16Array(buf, o, nE); o += nE * 2;
  S.ename = new Uint16Array(buf, o, nE); o += nE * 2;
  S.er = new Uint8Array(buf, o, nE * 3);

  // Floats once, up front: A* touches these millions of times.
  S.nLat = new Float64Array(nN);
  S.nLon = new Float64Array(nN);
  for (let i = 0; i < nN; i++) {
    S.nLat[i] = nll[i * 2] / 1e6;
    S.nLon[i] = nll[i * 2 + 1] / 1e6;
  }
  S.nNodes = nN; S.nEdges = nE;
}

function buildAdjacency() {
  const nN = S.nNodes, nE = S.nEdges;
  const head = new Int32Array(nN + 1);
  for (let i = 0; i < nE; i++) { head[S.eu[i] + 1]++; head[S.ev[i] + 1]++; }
  for (let i = 0; i < nN; i++) head[i + 1] += head[i];
  const cur = head.slice(0, nN);
  const to = new Int32Array(nE * 2), eidx = new Int32Array(nE * 2);
  for (let i = 0; i < nE; i++) {
    const u = S.eu[i], v = S.ev[i];
    to[cur[u]] = v; eidx[cur[u]++] = i;
    to[cur[v]] = u; eidx[cur[v]++] = i;
  }
  S.head = head; S.to = to; S.eidx = eidx;
}

function buildIndex() {
  const CELL = 0.004;   // about 440 m
  const idx = new Map();
  for (let i = 0; i < S.nNodes; i++) {
    const k = ((Math.floor(S.nLat[i] / CELL) & 0xffff) << 16)
            | (Math.floor(S.nLon[i] / CELL) & 0xffff);
    let a = idx.get(k); if (!a) idx.set(k, a = []);
    a.push(i);
  }
  S.cellIdx = idx; S.CELL = CELL;

  // Edges by cell too, keyed on both endpoints, so a map tile can ask for the
  // blocks that touch it without scanning all 431,599.
  const eidx = new Map();
  const put = (k, i) => { let a = eidx.get(k); if (!a) eidx.set(k, a = []); a.push(i); };
  for (let i = 0; i < S.nEdges; i++) {
    const ku = cellKey(S.nLat[S.eu[i]], S.nLon[S.eu[i]]);
    const kv = cellKey(S.nLat[S.ev[i]], S.nLon[S.ev[i]]);
    put(ku, i); if (kv !== ku) put(kv, i);
  }
  S.edgeCells = eidx;
}
const cellKey = (lat, lon) =>
  ((Math.floor(lat / 0.004) & 0xffff) << 16) | (Math.floor(lon / 0.004) & 0xffff);

/* -------------------------------------------------------- street layer */
/* The graph already holds every walkable block in the study area, so the map
 * can draw its own basemap from it. It sits underneath the CARTO tiles: when
 * they load they cover it, and when they cannot, offline or on a school
 * network that blocks the tile host, the streets are still there under the
 * route. No labels, which is what the tiles are for. */
const StreetTiles = L.GridLayer.extend({
  createTile(coords) {
    const tile = document.createElement('canvas');
    const size = this.getTileSize();
    tile.width = size.x; tile.height = size.y;
    if (!S.edgeCells) return tile;
    const z = coords.z;
    const origin = coords.scaleBy(size);
    const nw = this._map.unproject(origin, z);
    const se = this._map.unproject(origin.add(size), z);
    const pad = 2 * S.CELL;                       // catch blocks that only cross the tile
    const s0 = se.lat - pad, n0 = nw.lat + pad, w0 = nw.lng - pad, e0 = se.lng + pad;

    const ctx = tile.getContext('2d');
    ctx.strokeStyle = z >= 16 ? '#cfc9b6' : '#d6d0bf';
    ctx.lineWidth = z >= 17 ? 3.2 : z >= 16 ? 2.3 : z >= 15 ? 1.5 : z >= 14 ? 1 : 0.7;
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    const seen = new Set();
    const proj = (lat, lon) => this._map.project([lat, lon], z).subtract(origin);
    for (let la = Math.floor(s0 / S.CELL); la <= Math.floor(n0 / S.CELL); la++) {
      for (let lo = Math.floor(w0 / S.CELL); lo <= Math.floor(e0 / S.CELL); lo++) {
        const cell = S.edgeCells.get(((la & 0xffff) << 16) | (lo & 0xffff));
        if (!cell) continue;
        for (const i of cell) {
          if (seen.has(i)) continue;
          seen.add(i);
          const u = S.eu[i];
          let p = proj(S.nLat[u], S.nLon[u]);
          ctx.moveTo(p.x, p.y);
          for (const q of edgeShape(i, u)) { p = proj(q[0], q[1]); ctx.lineTo(p.x, p.y); }
          p = proj(S.nLat[S.ev[i]], S.nLon[S.ev[i]]);
          ctx.lineTo(p.x, p.y);
        }
      }
    }
    ctx.stroke();
    return tile;
  },
});

function nearestNode(lat, lon) {
  const ci = Math.floor(lat / S.CELL), cj = Math.floor(lon / S.CELL);
  let best = -1, bd = Infinity, foundAt = -1;
  for (let ring = 0; ring <= 8; ring++) {
    if (foundAt >= 0 && ring > foundAt + 1) break;
    for (let di = -ring; di <= ring; di++) {
      for (let dj = -ring; dj <= ring; dj++) {
        if (ring > 0 && Math.abs(di) !== ring && Math.abs(dj) !== ring) continue;
        const a = S.cellIdx.get((((ci + di) & 0xffff) << 16) | ((cj + dj) & 0xffff));
        if (!a) continue;
        for (const n of a) {
          const dy = (S.nLat[n] - lat) * 111320, dx = (S.nLon[n] - lon) * 92500;
          const d = dx * dx + dy * dy;
          if (d < bd) { bd = d; best = n; }
        }
      }
    }
    if (best >= 0 && foundAt < 0) foundAt = ring;
  }
  return best;
}

/* ------------------------------------------------------------------- A* */
function route(src, dst, lambda, bucket) {
  const n = S.nNodes;
  const g = new Float64Array(n).fill(Infinity);
  const prevN = new Int32Array(n).fill(-1);
  const prevE = new Int32Array(n).fill(-1);
  const done = new Uint8Array(n);
  const dLat = S.nLat[dst], dLon = S.nLon[dst];
  const er = S.er, ed = S.ed;

  const h = new Heap(1 << 16);
  g[src] = 0;
  h.push(metres(S.nLat[src], S.nLon[src], dLat, dLon), src);

  while (h.size) {
    const u = h.pop();
    if (done[u]) continue;
    done[u] = 1;
    if (u === dst) break;
    const gu = g[u];
    for (let p = S.head[u]; p < S.head[u + 1]; p++) {
      const v = S.to[p];
      if (done[v]) continue;
      const ei = S.eidx[p];
      const r = er[ei * 3 + bucket] / 255;
      const ng = gu + ed[ei] * (1 + lambda * r * Math.sqrt(r));
      if (ng < g[v]) {
        g[v] = ng; prevN[v] = u; prevE[v] = ei;
        h.push(ng + metres(S.nLat[v], S.nLon[v], dLat, dLon), v);
      }
    }
  }
  if (!isFinite(g[dst])) return null;

  const nodes = [], edges = [];
  for (let v = dst; v !== -1; v = prevN[v]) {
    nodes.push(v);
    if (prevE[v] >= 0) edges.push(prevE[v]);
    if (v === src) break;
  }
  nodes.reverse(); edges.reverse();

  let dist = 0, exposure = 0;
  for (const ei of edges) { dist += ed[ei]; exposure += ed[ei] * risk(ei, bucket); }
  return { nodes, edges, dist, exposure, score: dist ? exposure / dist * 100 : 0 };
}

/* Mean risk of an existing path measured in a different window, for the
 * "same route, different hour" comparison. */
function scoreAt(r, bucket) {
  let e = 0, d = 0;
  for (const ei of r.edges) { d += S.ed[ei]; e += S.ed[ei] * risk(ei, bucket); }
  return d ? e / d * 100 : 0;
}

function edgeShape(ei, from) {
  const a = S.gOff[ei], b = S.gOff[ei + 1];
  const out = [];
  for (let k = a; k < b; k++) out.push([S.gPts[k * 2] / 1e6, S.gPts[k * 2 + 1] / 1e6]);
  return (S.eu[ei] === from) ? out : out.reverse();
}

function routeLatLngs(r) {
  const pts = [];
  for (let i = 0; i < r.edges.length; i++) {
    const a = r.nodes[i];
    pts.push([S.nLat[a], S.nLon[a]]);
    for (const p of edgeShape(r.edges[i], a)) pts.push(p);
  }
  const last = r.nodes[r.nodes.length - 1];
  pts.push([S.nLat[last], S.nLon[last]]);
  return pts;
}

/* ----------------------------------------------------------- narrative */
/* Group a set of edges by street name and total how much walking and how much
 * exposure each street contributes, so the app can name what it avoided. */
function byStreet(edgeIds, bucket) {
  const acc = new Map();
  for (const ei of edgeIds) {
    const nm = streetName(ei) || ' unnamed';
    let a = acc.get(nm);
    if (!a) acc.set(nm, a = { name: nm, len: 0, worst: 0, weighted: 0 });
    const r = risk(ei, bucket);
    a.len += S.ed[ei];
    a.worst = Math.max(a.worst, r);
    a.weighted += S.ed[ei] * r;
  }
  return [...acc.values()].sort((x, y) => y.weighted - x.weighted);
}

const streetLabel = s =>
  s.name === ' unnamed' ? t('unnamed') : s.name;

function explain(sel, base, bucket) {
  if (sel.edges.length === base.edges.length
      && sel.edges.every((e, i) => e === base.edges[i])) {
    return { same: true, html: t('why.same') };
  }
  const selSet = new Set(sel.edges), baseSet = new Set(base.edges);
  const avoided = byStreet(base.edges.filter(e => !selSet.has(e)), bucket);
  const taken = byStreet(sel.edges.filter(e => !baseSet.has(e)), bucket);

  const cut = base.exposure > 0
    ? Math.round((1 - sel.exposure / base.exposure) * 100) : 0;
  const extra = sel.dist - base.dist;
  const mins = Math.round(extra / WALK_MPS / 60);

  const parts = [];
  if (avoided.length) {
    const a = avoided[0];
    parts.push(t('why.skips', { len: fmtM(a.len), st: streetLabel(a),
                                n: Math.round(a.worst * 100) }));
  }
  if (taken.length) {
    // Prefer naming a street that differs from the one avoided: sidewalks on
    // both sides of a boulevard share its name, and "skips Venice, goes along
    // Venice instead" is true but reads as nonsense.
    const avoidedName = avoided.length ? avoided[0].name : null;
    const tk = taken.find(x => x.name !== ' unnamed' && x.name !== avoidedName)
            || taken.find(x => x.name !== ' unnamed') || taken[0];
    parts.push(t('why.along', { st: streetLabel(tk), n: Math.round(tk.worst * 100) }));
  }
  const cost = extra < 15
    ? t('why.samelen')
    : (mins < 1
        ? t('why.costm', { m: Math.round(extra) })
        : (mins === 1 ? t('why.cost1') : t('why.costn', { n: mins })));
  parts.push(`${cost} ${t('why.drops', { cut })}`);

  return { same: false, flat: cut <= 2, html: parts.join(' ') };
}

/* Directions, as a person would give them.
 *
 * Walking on separately-mapped sidewalks means the raw path zigzags across
 * junctions, producing runs of two-metre hops that are crossings rather than
 * turns. Merge same-name neighbours, then repeatedly fold anything shorter
 * than a block into whichever neighbour is longer, until the list stops
 * changing. Nothing is thrown away, so the distances still sum to the route. */
const MIN_LEG_M = 35;

function mergeSameName(segs) {
  const out = [];
  for (const s of segs) {
    const last = out[out.length - 1];
    if (last && last.label === s.label) {
      last.len += s.len;
      last.worst = Math.max(last.worst, s.worst);
    } else out.push({ ...s });
  }
  return out;
}

function turnList(r, bucket) {
  let segs = mergeSameName(r.edges.map(ei => ({
    label: streetName(ei) || t('unnamed.turn'),
    len: S.ed[ei],
    worst: risk(ei, bucket),
  })));

  for (let pass = 0; pass < 12; pass++) {
    if (segs.length < 2) break;
    let k = -1;
    for (let i = 0; i < segs.length; i++) {
      if (segs[i].len < MIN_LEG_M && (k < 0 || segs[i].len < segs[k].len)) k = i;
    }
    if (k < 0) break;
    const prev = segs[k - 1], next = segs[k + 1];
    const host = !prev ? next : !next ? prev : (prev.len >= next.len ? prev : next);
    host.len += segs[k].len;
    host.worst = Math.max(host.worst, segs[k].worst);
    segs.splice(k, 1);
    segs = mergeSameName(segs);
  }
  return segs;
}

/* ------------------------------------------------------- risk heatmap */
let drawPending = null;
function drawRisk() {
  clearTimeout(drawPending);
  if (!S.showRisk || !S.nNodes) { riskLayer.clearLayers(); $('hint').classList.remove('show'); return; }
  const out = map.getZoom() < 13;
  $('hint').classList.toggle('show', out);
  if (out) { riskLayer.clearLayers(); $('lg-count').textContent = '0'; return; }

  drawPending = setTimeout(() => {
    riskLayer.clearLayers();
    const b = map.getBounds().pad(0.1);
    const s = b.getSouth(), n = b.getNorth(), w = b.getWest(), e = b.getEast();
    const picked = [];
    for (let i = 0; i < S.nEdges; i++) {
      const u = S.eu[i], v = S.ev[i];
      const la = S.nLat[u], lb = S.nLat[v];
      if ((la < s && lb < s) || (la > n && lb > n)) continue;
      const lo = S.nLon[u], lob = S.nLon[v];
      if ((lo < w && lob < w) || (lo > e && lob > e)) continue;
      picked.push(i);
    }
    let list = picked;
    if (picked.length > MAX_DRAW) {
      const bk = S.bucket;
      picked.sort((x, y) => S.er[y * 3 + bk] - S.er[x * 3 + bk]);
      list = picked.slice(0, MAX_DRAW);
    }
    const z = map.getZoom();
    const base = z >= 16 ? 3.4 : z >= 15 ? 2.6 : z >= 14 ? 1.9 : 1.3;
    const floor = floorFor(z);
    let drawn = 0;
    for (const i of list) {
      const r = risk(i, S.bucket);
      if (r < floor) continue;
      const t = (r - floor) / Math.max(0.05, 1 - floor);
      const u = S.eu[i];
      const line = [[S.nLat[u], S.nLon[u]]];
      for (const p of edgeShape(i, u)) line.push(p);
      line.push([S.nLat[S.ev[i]], S.nLon[S.ev[i]]]);
      L.polyline(line, {
        color: bandColor(r), weight: base * (0.8 + 0.6 * t),
        opacity: 0.4 + 0.5 * t, interactive: false, lineCap: 'butt',
      }).addTo(riskLayer);
      drawn++;
    }
    $('lg-count').textContent = drawn.toLocaleString();
  }, 90);
}
map.on('moveend zoomend', drawRisk);

/* ------------------------------------------------------------- markers */
function pin(latlng, color, label) {
  return L.marker(latlng, {
    icon: L.divIcon({
      className: '', iconSize: [13, 13], iconAnchor: [6, 6],
      html: `<div class="pin" style="background:${color}"></div>`,
    }),
    title: label,
  });
}

function redrawPins() {
  pinLayer.clearLayers();
  if (S.origin) {
    pin([S.origin.lat, S.origin.lon], '#211f18', t('pin.start'))
      .bindTooltip(t('pin.start'), { direction: 'top', offset: [0, -8] }).addTo(pinLayer);
  }
  if (S.school) {
    pin([S.school.lat, S.school.lon], '#3c7a4e', S.school.name)
      .bindTooltip(S.school.name, { direction: 'top', offset: [0, -8] }).addTo(pinLayer);
  }
}

/* ------------------------------------------------------------ compute */
/* ---------------------------------------------------------------- transit */
/* Standing at a stop is exposure without progress, so a minute of waiting is
 * charged like this many metres of walking on the same block. Waiting is if
 * anything worse per minute than moving, since you are stationary and
 * predictable, so the rate is set above walking pace on purpose. */
const WAIT_M_PER_MIN = 80;
const MAX_STOP_WALK_M = 900;     // how far a student will walk to a stop
const RIDE_CANDIDATES = 14;      // itineraries worth spending an A* run on

const T = { stops: null, patterns: null, names: null, stopPat: null,
            node: null, grid: null, CELL: 0.006 };

function initTransit(data) {
  T.stops = data.stops; T.patterns = data.patterns; T.names = data.names;
  T.stopPat = new Map();
  data.patterns.forEach((p, pi) => {
    p.s.forEach((sIdx, pos) => {
      let a = T.stopPat.get(sIdx);
      if (!a) T.stopPat.set(sIdx, a = []);
      a.push([pi, pos]);
    });
  });
  T.node = new Int32Array(data.stops.length).fill(-2);   // -2 = not resolved
  T.grid = new Map();
  data.stops.forEach((s, i) => {
    const k = ((Math.floor(s[0] / T.CELL) & 0xffff) << 16)
            | (Math.floor(s[1] / T.CELL) & 0xffff);
    let a = T.grid.get(k);
    if (!a) T.grid.set(k, a = []);
    a.push(i);
  });
}

function stopNode(i) {
  if (T.node[i] === -2) T.node[i] = nearestNode(T.stops[i][0], T.stops[i][1]);
  return T.node[i];
}

function stopsNear(lat, lon, maxM) {
  const out = [];
  const span = Math.ceil(maxM / (T.CELL * 92500)) + 1;
  const ci = Math.floor(lat / T.CELL), cj = Math.floor(lon / T.CELL);
  for (let di = -span; di <= span; di++) {
    for (let dj = -span; dj <= span; dj++) {
      const a = T.grid.get((((ci + di) & 0xffff) << 16) | ((cj + dj) & 0xffff));
      if (!a) continue;
      for (const i of a) {
        const d = metres(lat, lon, T.stops[i][0], T.stops[i][1]);
        if (d <= maxM) out.push({ i, d });
      }
    }
  }
  return out.sort((x, y) => x.d - y.d).slice(0, 40);
}

/* Up to one transfer. Direct rides only covered a minority of real trips: a
 * student in Koreatown heading to a school off Fairfax has no single route, and
 * telling them "walk 8 km instead" is not an answer. Two rides is where most
 * of Los Angeles becomes reachable. We stop there, because a second transfer
 * adds another wait to stand through and is advice nobody follows.
 *
 * Forward pass: everywhere you can get to on one ride from a stop near home.
 * Backward pass: everywhere you can ride to the school from. Any stop in both,
 * or a short walk apart, is a usable transfer. */
const XFER_WALK_M = 260;

function forwardReach(seeds) {
  const best = new Map();
  for (const s of seeds) {
    for (const [pi, posA] of (T.stopPat.get(s.i) || [])) {
      const pat = T.patterns[pi];
      for (let j = posA + 1; j < pat.s.length; j++) {
        const ride = Math.max(0, pat.t[j] - pat.t[posA]) / 60;
        const est = s.d / WALK_MPS / 60 + pat.w + ride;
        const at = pat.s[j];
        const cur = best.get(at);
        if (!cur || est < cur.est) {
          best.set(at, { est, pi, posA, posB: j, seed: s, ride, wait: pat.w });
        }
      }
    }
  }
  return best;
}

function backwardReach(targets) {
  const best = new Map();
  for (const s of targets) {
    for (const [pi, posB] of (T.stopPat.get(s.i) || [])) {
      const pat = T.patterns[pi];
      for (let i = 0; i < posB; i++) {
        const ride = Math.max(0, pat.t[posB] - pat.t[i]) / 60;
        const est = pat.w + ride + s.d / WALK_MPS / 60;
        const from = pat.s[i];
        const cur = best.get(from);
        if (!cur || est < cur.est) {
          best.set(from, { est, pi, posA: i, posB, target: s, ride, wait: pat.w });
        }
      }
    }
  }
  return best;
}

function transitOptions(origin, school, bucket, lambda) {
  if (!T.stops) return [];
  const from = stopsNear(origin.lat, origin.lon, MAX_STOP_WALK_M);
  const to = stopsNear(school.lat, school.lon, MAX_STOP_WALK_M);
  if (!from.length || !to.length) return [];
  const toNear = new Map(to.map(s => [s.i, s.d]));

  const raw = [];

  // ---- direct rides
  for (const fs of from) {
    for (const [pi, posA] of (T.stopPat.get(fs.i) || [])) {
      const pat = T.patterns[pi];
      for (let j = posA + 1; j < pat.s.length; j++) {
        const dOff = toNear.get(pat.s[j]);
        if (dOff === undefined) continue;
        const ride = Math.max(0, pat.t[j] - pat.t[posA]) / 60;
        raw.push({
          legs: [{ pi, posA, posB: j }], xfer: null,
          rideMin: ride, waitMin: pat.w,
          est: fs.d / WALK_MPS / 60 + pat.w + ride + dOff / WALK_MPS / 60,
        });
      }
    }
  }

  // ---- one transfer
  const fwd = forwardReach(from);
  const bwd = backwardReach(to);
  for (const [stopX, f] of fwd) {
    const [lat, lon] = T.stops[stopX];
    const span = Math.ceil(XFER_WALK_M / (T.CELL * 92500)) + 1;
    const ci = Math.floor(lat / T.CELL), cj = Math.floor(lon / T.CELL);
    for (let di = -span; di <= span; di++) {
      for (let dj = -span; dj <= span; dj++) {
        const cell = T.grid.get((((ci + di) & 0xffff) << 16) | ((cj + dj) & 0xffff));
        if (!cell) continue;
        for (const stopY of cell) {
          const b = bwd.get(stopY);
          if (!b) continue;
          if (b.pi === f.pi) continue;              // same bus, not a transfer
          const w = stopX === stopY ? 0 : metres(lat, lon, T.stops[stopY][0], T.stops[stopY][1]);
          if (w > XFER_WALK_M) continue;
          raw.push({
            legs: [{ pi: f.pi, posA: f.posA, posB: f.posB },
                   { pi: b.pi, posA: b.posA, posB: b.posB }],
            xfer: { from: stopX, to: stopY, metres: w },
            rideMin: f.ride + b.ride, waitMin: f.wait + b.wait,
            est: f.est + w / WALK_MPS / 60 + b.est,
          });
        }
      }
    }
  }
  if (!raw.length) return [];
  raw.sort((a, b) => a.est - b.est);

  // ---- cost the plausible handful properly
  const walkCache = new Map();
  const legRoute = (a, b) => {
    const k = `${a}|${b}`;
    if (!walkCache.has(k)) walkCache.set(k, route(a, b, lambda, bucket));
    return walkCache.get(k);
  };
  const srcNode = nearestNode(origin.lat, origin.lon);
  const dstNode = nearestNode(school.lat, school.lon);
  const stopRiskAt = si => {
    const e = firstEdgeAt(stopNode(si));
    return e >= 0 ? risk(e, bucket) : 0.3;
  };

  const out = [];
  const seen = new Set();
  for (const c of raw.slice(0, RIDE_CANDIDATES)) {
    const first = T.patterns[c.legs[0].pi], last = T.patterns[c.legs[c.legs.length - 1].pi];
    const bStop = first.s[c.legs[0].posA];
    const aStop = last.s[c.legs[c.legs.length - 1].posB];
    const key = c.legs.map(l => T.patterns[l.pi].r).join('>') + `|${bStop}|${aStop}`;
    if (seen.has(key)) continue;
    seen.add(key);

    const bn = stopNode(bStop), an = stopNode(aStop);
    if (bn < 0 || an < 0 || bn === an) continue;
    const legA = bn === srcNode ? null : legRoute(srcNode, bn);
    const legB = an === dstNode ? null : legRoute(an, dstNode);
    if ((bn !== srcNode && !legA) || (an !== dstNode && !legB)) continue;

    let waitExp = 0;
    waitExp += stopRiskAt(bStop) * WAIT_M_PER_MIN * first.w;
    if (c.legs.length > 1) {
      waitExp += stopRiskAt(c.xfer.to) * WAIT_M_PER_MIN * last.w;
      waitExp += stopRiskAt(c.xfer.from) * c.xfer.metres;   // the transfer walk
    }
    const walkDist = (legA ? legA.dist : 0) + (legB ? legB.dist : 0)
                   + (c.xfer ? c.xfer.metres : 0);
    const exposure = (legA ? legA.exposure : 0) + (legB ? legB.exposure : 0) + waitExp;
    const timeMin = ((legA ? legA.dist : 0) + (legB ? legB.dist : 0)) / WALK_MPS / 60
                  + (c.xfer ? c.xfer.metres / WALK_MPS / 60 : 0)
                  + c.waitMin + c.rideMin;
    out.push({
      kind: 'transit', legs: c.legs, xfer: c.xfer, bStop, aStop, legA, legB,
      rideMin: c.rideMin, waitMin: c.waitMin, stopRisk: stopRiskAt(bStop),
      dist: walkDist, exposure, timeMin,
      routeLabel: c.legs.map(l => T.patterns[l.pi].r).join(' then '),
      routeNames: c.legs.map(l => T.patterns[l.pi].r),
      isRail: c.legs.every(l => T.patterns[l.pi].k === 'rail'),
    });
  }

  // One itinerary per combination of routes. Three boarding points on the same
  // bus is not three choices, so keep the calmest version of each.
  const best = new Map();
  for (const o of out) {
    const cur = best.get(o.routeLabel);
    if (!cur || o.exposure < cur.exposure) best.set(o.routeLabel, o);
  }
  return [...best.values()].sort((a, b) => a.exposure - b.exposure);
}

function firstEdgeAt(node) {
  return S.head[node] < S.head[node + 1] ? S.eidx[S.head[node]] : -1;
}

/* Exposure in comparable units across modes: total risk-metres over 100, so a
 * bus trip and a walk can be put side by side honestly. Riding scores near zero
 * because the minutes on board are minutes off the street. */
const expUnits = o => o.exposure / 100;
const optTime = o => (o.kind === 'transit' ? o.timeMin : o.r.dist / WALK_MPS / 60);
const optWalk = o => (o.kind === 'transit' ? o.dist : o.r.dist);

const sig = r => r.edges.join(',');

function buildOptions(src, dst, bucket) {
  const seen = new Map();
  for (const lam of LADDER) {
    const r = route(src, dst, lam, bucket);
    if (r && !seen.has(sig(r))) seen.set(sig(r), r);
  }
  const all = [...seen.values()];
  if (!all.length) return null;

  const foot = (r, labelKey, hintKey) =>
    ({ kind: 'foot', r, exposure: r.exposure, labelKey, hintKey });

  const fast = all.reduce((a, b) => (b.dist < a.dist ? b : a));
  const safe = all.reduce((a, b) => (b.exposure < a.exposure ? b : a));
  const out = [foot(fast, 'opt.short', 'opt.shortH')];
  if (sig(safe) === sig(fast)) return out;

  // A middle option only earns its place if it buys more calm per extra metre
  // than the safest route does. Otherwise there are honestly just two choices.
  let mid = null, bestEff = -Infinity;
  for (const m of all) {
    if (sig(m) === sig(fast) || sig(m) === sig(safe)) continue;
    const cut = fast.exposure - m.exposure;
    if (cut <= 0) continue;
    const eff = cut / Math.max(m.dist - fast.dist, 1);
    if (eff > bestEff) { bestEff = eff; mid = m; }
  }
  if (mid) out.push(foot(mid, 'opt.mid', 'opt.midH'));
  out.push(foot(safe, 'opt.safe', 'opt.safeH'));
  return out;
}

/* "35 then 217" reads as a sentence, so the joiner is translated at render time. */
const rideName = o => o.routeNames.join(t('opt.then'));
const optLabel = o => (o.routeNames ? (o.labelKey ? t(o.labelKey, { r: rideName(o) }) : rideName(o))
                                    : t(o.labelKey));
const optHint = o => (o.hintKey ? t(o.hintKey, o.hintVars) + (o.hintXfer ? t('opt.change') : '') : o.hint);
const isShortest = o => o.kind === 'foot' && o.labelKey === 'opt.short';

function compute(fit = true) {
  if (!S.origin || !S.school) return;
  const src = nearestNode(S.origin.lat, S.origin.lon);
  const dst = nearestNode(S.school.lat, S.school.lon);
  if (src < 0 || dst < 0) { toast(t('toast.nostreet')); return; }
  if (src === dst) { toast(t('toast.same')); return; }

  spokeLayer.clearLayers();
  const onFoot = buildOptions(src, dst, S.bucket);
  if (!onFoot) { toast(t('toast.noroute')); return; }

  let opts = onFoot;
  if (S.mode === 'bus') {
    const rides = transitOptions(S.origin, S.school, S.bucket, 3.0);
    if (!rides.length) {
      toast(t('toast.nobus'));
      setDyn($('mode-note'), 'mode.none');
    } else {
      // Always keep the calmest walk on screen, so the bus is compared against
      // the real alternative rather than presented on its own.
      const walkRef = onFoot[onFoot.length - 1];
      opts = rides.slice(0, 3).map(o => ({
        ...o,
        // Rail lines already read as names ("Metro E Line"), so only bus
        // numbers need the word Route in front of them.
        labelKey: /line/i.test(o.routeLabel) ? null : 'opt.route',
        label: o.routeLabel,
        hintKey: 'opt.rideH', hintVars: { n: Math.round(o.rideMin), d: fmtM(o.dist) },
        hintXfer: !!o.xfer,
      }));
      opts.push({ ...walkRef, labelKey: 'opt.walk', hintKey: 'opt.walkH', hintVars: null });
      setDyn($('mode-note'), 'mode.found', { w: WAIT_M_PER_MIN });
    }
  }

  S.routes = opts;
  if (S.pick >= opts.length) S.pick = opts.length - 1;
  $('intro').style.display = 'none';
  $('clear-wrap').style.display = '';
  renderCards();
  select(S.pick, fit);
  // On a phone the results sit below the fold of the sidebar; bring them up
  // when a trip is first planned, not on every window or mode change.
  if (fit) {
    const panes = document.querySelector('.panes');
    const top = panes.scrollTop + $('r-cards').getBoundingClientRect().top
              - panes.getBoundingClientRect().top - 6;
    panes.scrollTo({ top, behavior: 'smooth' });
  }
}

function clearTrip() {
  S.routes = null; S.origin = null; S.pick = 2;
  if (!S.preset) S.school = null;
  routeLayer.clearLayers(); spokeLayer.clearLayers();
  redrawPins();
  $('origin').value = '';
  if (!S.preset) $('school').value = '';
  for (const id of ['r-cards', 'r-because', 'r-hours', 'r-turns', 'r-share']) $(id).style.display = 'none';
  $('clear-wrap').style.display = 'none';
  $('intro').style.display = S.embed ? 'none' : '';
  $('go').disabled = true;
  const p = new URLSearchParams();
  if (S.preset) p.set('school', S.preset.id);
  if (S.lang !== 'en') p.set('lang', S.lang);
  if (S.embed) p.set('embed', '1');
  const qs = p.toString();
  history.replaceState(null, '', location.pathname + (qs ? `?${qs}` : ''));
  document.querySelector('.panes').scrollTo({ top: 0, behavior: 'smooth' });
  if (S.school) map.setView([S.school.lat, S.school.lon], 15);
}
$('clear').addEventListener('click', clearTrip);

/* ----------------------------------------------------------- geolocation */
$('locate').addEventListener('click', () => {
  if (!navigator.geolocation) { toast(t('toast.nogeo')); return; }
  const btn = $('locate');
  btn.disabled = true; btn.textContent = t('geo.wait');
  const done = () => { btn.disabled = false; applyLang(); };
  navigator.geolocation.getCurrentPosition(pos => {
    done();
    const lat = pos.coords.latitude, lon = pos.coords.longitude;
    const b = S.meta.bbox;
    if (lat < b.south || lat > b.north || lon < b.west || lon > b.east) { toast(t('toast.geoout')); return; }
    S.origin = { lat, lon };
    $('origin').value = t('geo.here');
    redrawPins();
    $('go').disabled = !S.school;
    if (S.school) compute(); else map.setView([lat, lon], 15);
  }, () => { done(); toast(t('toast.geofail')); },
  { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 });
});

function renderCards() {
  // Compare against the plain walk: in foot mode the shortest route, in bus
  // mode the walking option pinned to the bottom of the list.
  const ref = S.mode === 'bus'
    ? (S.routes.find(o => o.kind === 'foot') || S.routes[0])
    : S.routes[0];
  const refExp = ref ? ref.exposure : 0;

  $('cards').innerHTML = S.routes.map((o, i) => {
    const cut = refExp > 0 ? Math.round((1 - o.exposure / refExp) * 100) : 0;
    const sub = (o === ref || cut <= 0) ? optHint(o) : t('card.less', { cut });
    const intensity = optWalk(o) > 0 ? o.exposure / optWalk(o) : 0;
    return `<div class="rc${i === S.pick ? ' on' : ''}" data-i="${i}">
      <span class="swatch" style="background:${bandColor(intensity)}"></span>
      <span class="who"><b>${optLabel(o)}</b><small>${sub}</small></span>
      <span class="num"><b>${t('card.min', { n: Math.max(1, Math.round(optTime(o))) })}</b><small>${t('card.sub', { d: fmtM(optWalk(o)), e: expUnits(o).toFixed(1) })}</small></span>
    </div>`;
  }).join('');
  $('r-cards').style.display = '';
}

const stopName = si => T.names[T.stops[si][2]] || t('stop.a');

function routeExposureAt(r, b) {
  let e = 0;
  for (const ei of r.edges) e += S.ed[ei] * risk(ei, b);
  return e;
}

function exposureAt(o, b) {
  if (o.kind !== 'transit') return routeExposureAt(o.r, b);
  const wr = firstEdgeAt(stopNode(o.bStop));
  const sr = wr >= 0 ? risk(wr, b) : o.stopRisk;
  return (o.legA ? routeExposureAt(o.legA, b) : 0)
       + (o.legB ? routeExposureAt(o.legB, b) : 0)
       + sr * WAIT_M_PER_MIN * o.waitMin;
}

function drawWalk(r, colour, weight) {
  L.polyline(routeLatLngs(r), { color: '#fff', weight: weight + 3.5, opacity: .75,
                                interactive: false }).addTo(routeLayer);
  L.polyline(routeLatLngs(r), { color: colour, weight, opacity: 1,
                                lineCap: 'round', interactive: false }).addTo(routeLayer);
}

function drawSelection(o) {
  routeLayer.clearLayers();
  const ref = S.routes.find(isShortest);
  if (ref && ref !== o) {
    L.polyline(routeLatLngs(ref.r), {
      color: '#211f18', weight: 2.5, opacity: .45, dashArray: '3,6',
      interactive: false,
    }).addTo(routeLayer);
  }
  if (o.kind !== 'transit') { drawWalk(o.r, '#3c7a4e', 4.5); return; }

  if (o.legA) drawWalk(o.legA, '#3c7a4e', 4);
  if (o.legB) drawWalk(o.legB, '#3c7a4e', 4);

  for (const leg of o.legs) {
    const pat = T.patterns[leg.pi];
    const stops = pat.s.slice(leg.posA, leg.posB + 1);
    const ride = stops.map(si => [T.stops[si][0], T.stops[si][1]]);
    L.polyline(ride, { color: '#fff', weight: 9, opacity: .8, interactive: false })
      .addTo(routeLayer);
    L.polyline(ride, { color: '#211f18', weight: 5, opacity: 1, lineCap: 'round',
                       interactive: false }).addTo(routeLayer);
    for (const si of stops) {
      L.circleMarker([T.stops[si][0], T.stops[si][1]], {
        radius: 2.6, color: '#211f18', weight: 1, fillColor: '#e8e4d6',
        fillOpacity: 1, interactive: false,
      }).addTo(routeLayer);
    }
  }
  // The transfer walk, drawn so a change of bus is visible rather than implied.
  if (o.xfer && o.xfer.metres > 0) {
    L.polyline([[T.stops[o.xfer.from][0], T.stops[o.xfer.from][1]],
                [T.stops[o.xfer.to][0], T.stops[o.xfer.to][1]]], {
      color: '#3c7a4e', weight: 3, opacity: .95, dashArray: '2,5',
      interactive: false,
    }).addTo(routeLayer);
  }
  const marks = [[o.bStop, t('mk.board')], [o.aStop, t('mk.off')]];
  if (o.xfer) marks.push([o.xfer.to, t('mk.change')]);
  for (const [si, lbl] of marks) {
    L.circleMarker([T.stops[si][0], T.stops[si][1]], {
      radius: 5.5, color: '#211f18', weight: 2, fillColor: '#c8912b', fillOpacity: 1,
    }).bindTooltip(`${lbl}: ${stopName(si)}`, { direction: 'top' }).addTo(routeLayer);
  }
}

function renderWhy(o) {
  const el = $('because');
  const walkRef = S.routes.find(x => x.kind === 'foot'
    && (S.mode === 'bus' || isShortest(x)));

  if (o.kind === 'transit') {
    const cut = walkRef && walkRef.exposure > 0
      ? Math.round((1 - o.exposure / walkRef.exposure) * 100) : 0;
    const ride = o.xfer
      ? t('why.t.ridex', { r: rideName(o), n: Math.round(o.rideMin), stop: stopName(o.xfer.to) })
      : t('why.t.ride', { r: rideName(o), n: Math.round(o.rideMin) });
    const bits = [
      t('why.t.main', { d1: fmtM(o.legA ? o.legA.dist : 0), stop: stopName(o.bStop),
                        w: Math.round(o.waitMin), ride, d2: fmtM(o.legB ? o.legB.dist : 0) }),
      t('why.t.only', { d: fmtM(o.dist) }),
    ];
    if (walkRef) bits.push(cut > 2 ? t('why.t.drops', { cut }) : t('why.t.flat'));
    el.className = 'because' + (cut <= 2 ? ' flat' : '');
    el.innerHTML = bits.join(' ');
  } else {
    const base = (S.routes.find(isShortest) || o).r;
    const ex = explain(o.r, base, S.bucket);
    el.className = 'because' + (ex.flat ? ' flat' : '');
    el.innerHTML = ex.html;
  }
  $('r-because').style.display = '';
}

function renderHours(o) {
  const vals = [0, 1, 2].map(b => exposureAt(o, b) / 100);
  const max = Math.max(...vals, 0.01);
  $('hours').innerHTML = vals.map((v, b) => `
    <div class="hrow${b === S.bucket ? ' now' : ''}">
      <span>${cap(winName(b))}${b === S.bucket ? `<span class="nowtag"> ${t('hours.now')}</span>` : ''}</span>
      <span class="track"><i class="bar" style="width:${(v / max * 100).toFixed(1)}%;background:${bandColor(optWalk(o) ? exposureAt(o, b) / optWalk(o) : 0)}"></i></span>
      <b>${v.toFixed(1)}</b>
    </div>`).join('');
  const worst = vals.indexOf(Math.max(...vals));
  $('hours-note').textContent = t('hours.note', { win: winName(worst), clock: winClock(worst) });
  $('r-hours').style.display = '';
}

const turnRow = (label, len, worst) =>
  `<li><span>${label}</span><span class="m">${len}</span>`
  + `<span class="chip" style="color:${bandColor(worst)}">${Math.round(worst * 100)}</span></li>`;

function renderTurns(o) {
  let html = '';
  if (o.kind === 'transit') {
    if (o.legA) {
      html += turnList(o.legA, S.bucket).map(t =>
        turnRow(t.label, fmtM(t.len), t.worst)).join('');
    }
    o.legs.forEach((leg, k) => {
      const pat = T.patterns[leg.pi];
      const board = pat.s[leg.posA], off = pat.s[leg.posB];
      html += turnRow(t('turn.board', { r: pat.r, stop: stopName(board) }),
                      t('turn.wait', { n: Math.round(pat.w) }), o.stopRisk);
      html += turnRow(t('turn.ride', { n: leg.posB - leg.posA }),
                      t('card.min', { n: Math.round(Math.max(0, pat.t[leg.posB] - pat.t[leg.posA]) / 60) }), 0);
      html += turnRow(t('turn.off', { stop: stopName(off) }), '', o.stopRisk);
      if (k === 0 && o.xfer && o.xfer.metres > 0) {
        html += turnRow(t('turn.xfer', { stop: stopName(o.xfer.to) }),
                        fmtM(o.xfer.metres), o.stopRisk);
      }
    });
    if (o.legB) {
      html += turnList(o.legB, S.bucket).map(t =>
        turnRow(t.label, fmtM(t.len), t.worst)).join('');
    }
  } else {
    html = turnList(o.r, S.bucket).slice(0, 60).map(t =>
      turnRow(t.label, fmtM(t.len), t.worst)).join('');
  }
  $('turnlist').innerHTML = html;
  $('r-turns').style.display = '';
}

function select(i, fit = true) {
  S.pick = i;
  const o = S.routes[i];
  [...$('cards').children].forEach((c, k) => c.classList.toggle('on', k === i));

  drawSelection(o);
  renderWhy(o);
  renderHours(o);
  renderTurns(o);
  $('r-share').style.display = '';
  $('report').href = reportUrl();

  writeUrl();
  if (fit) {
    map.fitBounds(L.featureGroup(routeLayer.getLayers()).getBounds().pad(0.16),
                  { animate: false });
  }
}

/* -------------------------------------------------------- school report */
function report(school) {
  const dst = nearestNode(school.lat, school.lon);
  if (dst < 0) { toast(t('toast.rcnostreet')); return; }
  const R = 1200;
  const rows = [];
  spokeLayer.clearLayers();
  routeLayer.clearLayers();

  for (let k = 0; k < N_COMPASS; k++) {
    const th = k * 2 * Math.PI / N_COMPASS;
    const lat = school.lat + (R * Math.cos(th)) / 111320;
    const lon = school.lon + (R * Math.sin(th)) / 92500;
    const src = nearestNode(lat, lon);
    if (src < 0 || src === dst) continue;
    // Lambda 0: what a student walks without this tool, which is what makes a
    // direction dangerous in the first place.
    const r = route(src, dst, 0, S.bucket);
    if (!r) continue;
    rows.push({ k, r });
  }
  if (!rows.length) { toast(t('toast.rcnone')); return; }

  rows.sort((a, b) => b.r.score - a.r.score);

  for (const row of rows) {
    L.polyline(routeLatLngs(row.r), {
      color: bandColor(row.r.score / 100), weight: 3.5, opacity: .9,
      interactive: false, lineCap: 'round',
    }).addTo(spokeLayer);
  }
  pinLayer.clearLayers();
  pin([school.lat, school.lon], '#211f18', school.name)
    .bindTooltip(school.name, { direction: 'top', offset: [0, -8] }).addTo(pinLayer);

  S.report = { school, rows, bucket: S.bucket };
  renderReport();
  map.fitBounds(L.featureGroup(spokeLayer.getLayers()).getBounds().pad(0.08),
                { animate: false });
}

function renderReport() {
  const { school, rows, bucket } = S.report;
  const worst = rows[0], best = rows[rows.length - 1];
  $('rc-title').innerHTML = t('rc.title', { n: rows.length, win: winName(bucket) });
  $('rc-body').innerHTML = rows.map(row => {
    const cls = row === worst ? ' class="worst"' : row === best ? ' class="best"' : '';
    return `<tr${cls}><td class="dir"><span class="swatch" style="background:${bandColor(row.r.score / 100)}"></span>${compassName(row.k)}</td>`
      + `<td>${fmtM(row.r.dist)}</td><td class="sc">${Math.round(row.r.score)}</td></tr>`;
  }).join('');
  const ratio = best.r.score > 0 ? (worst.r.score / best.r.score) : 0;
  const vars = { school: school.name, worst: compassName(worst.k), best: compassName(best.k),
                 ratio: ratio.toFixed(1) };
  $('rc-note').innerHTML = `${t(ratio >= 1.15 ? 'rc.ratio' : 'rc.same', vars)} ${t('rc.tail')}`;
  $('rc-out').style.display = '';
}

/* --------------------------------------------------------- autocomplete */
function attachAC(inputId, listId, search, onPick, opts = {}) {
  const input = $(inputId), list = $(listId);
  let items = [], sel = -1, timer = null, inflight = null;

  const close = () => { list.classList.remove('on'); sel = -1; };
  const note = (cls, msg) => {
    items = [];
    list.innerHTML = `<div class="${cls}">${msg}</div>`;
    list.classList.add('on');
  };
  const render = () => {
    if (!items.length) { close(); return; }
    list.innerHTML = items.map((it, i) =>
      `<div${i === sel ? ' class="sel"' : ''} data-i="${i}">${it.label}`
      + (it.sub ? `<small>${it.sub}</small>` : '') + '</div>').join('');
    list.classList.add('on');
  };

  input.addEventListener('input', () => {
    clearTimeout(timer);
    // A keystroke cancels the lookup already in the air, so results never
    // arrive out of order and a remote geocoder sees one request per pause.
    if (inflight) { inflight.abort(); inflight = null; }
    const q = input.value.trim();
    if (q.length < 2) { items = []; close(); return; }
    timer = setTimeout(async () => {
      const ctl = new AbortController();
      inflight = ctl;
      if (opts.remote) note('busy', t('ac.busy'));
      try {
        items = (await search(q, ctl.signal)) || [];
      } catch (e) {
        if (e.name === 'AbortError') return;
        note('none', e.offline ? t('ac.offline') : t('ac.none'));
        return;
      } finally {
        if (inflight === ctl) inflight = null;
      }
      if (ctl.signal.aborted) return;
      if (!items.length) { note('none', t('ac.none')); return; }
      sel = -1; render();
    }, opts.remote ? 420 : 200);
  });

  input.addEventListener('keydown', e => {
    if (!list.classList.contains('on') || !items.length) return;
    if (e.key === 'ArrowDown') { sel = Math.min(items.length - 1, sel + 1); render(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { sel = Math.max(0, sel - 1); render(); e.preventDefault(); }
    else if (e.key === 'Enter') {
      e.preventDefault();
      onPick(items[sel < 0 ? 0 : sel]); close();
    } else if (e.key === 'Escape') close();
  });

  list.addEventListener('mousedown', e => {
    const d = e.target.closest('div[data-i]'); if (!d) return;
    e.preventDefault();
    onPick(items[+d.dataset.i]); close();
  });
  input.addEventListener('blur', () => setTimeout(close, 140));
}

const searchSchools = q => {
  const v = q.toLowerCase();
  return S.schools
    .filter(s => s.name.toLowerCase().includes(v))
    .slice(0, 8)
    .map(s => ({ label: s.name, sub: `${s.level} / ${s.city}`, school: s }));
};

/* ------------------------------------------------------- cross streets */
/* "Hauser & Venice" is how people in Los Angeles actually say where they are,
 * and it is the one kind of place a geocoder handles badly. The graph already
 * carries a name for most blocks, so an intersection is just a node shared by
 * a block of one name and a block of the other. That makes this instant,
 * exact to the graph the router uses, and available offline. */
const XSTREET_RE = /^\s*(.+?)(?:\s*[&\/+@]\s*|\s+(?:and|at|y|con)\s+)(.+?)\s*$/i;
const ABBREV = {
  blvd: 'boulevard', bl: 'boulevard', ave: 'avenue', av: 'avenue', st: 'street',
  dr: 'drive', pl: 'place', rd: 'road', hwy: 'highway', pkwy: 'parkway',
  ln: 'lane', ct: 'court', ter: 'terrace', n: 'north', s: 'south', e: 'east',
  w: 'west',
};
const normName = s => s.toLowerCase().replace(/[.,']/g, ' ').split(/\s+/)
  .filter(Boolean).map(w => ABBREV[w] || w).join(' ');

function nameIndex() {
  if (S.nameEdges) return S.nameEdges;
  const m = new Map();
  const len = new Float64Array(S.names.length);
  for (let i = 0; i < S.nEdges; i++) {
    const n = S.ename[i];
    if (n === NO_NAME) continue;
    let a = m.get(n); if (!a) m.set(n, a = []);
    a.push(i);
    len[n] += S.ed[i];
  }
  S.nameEdges = m;
  S.nameLen = len;
  S.nameNorm = S.names.map(normName);
  return m;
}

/* Street names matching one typed side, best first: whole-word matches beat
 * substring matches, then the street with the most mapped length wins, so
 * "Pico" means West Pico Boulevard rather than Pico Place. */
function matchStreets(part) {
  const q = normName(part);
  if (q.length < 3) return [];
  const idx = nameIndex();
  const out = [];
  for (const [n] of idx) {
    const nm = S.nameNorm[n];
    if (!nm.includes(q)) continue;
    const word = new RegExp(`(^|\\s)${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(\\s|$)`).test(nm);
    out.push({ n, score: (word ? 0 : 1e9) - S.nameLen[n] });
  }
  return out.sort((a, b) => a.score - b.score).slice(0, 8).map(x => x.n);
}

function crossStreets(q) {
  const m = XSTREET_RE.exec(q);
  if (!m || !S.ename) return [];
  const A = matchStreets(m[1]), B = matchStreets(m[2]);
  if (!A.length || !B.length) return [];
  const idx = nameIndex();
  const out = [], seenPair = new Set();
  for (const a of A) {
    const nodesA = new Set();
    for (const ei of idx.get(a)) { nodesA.add(S.eu[ei]); nodesA.add(S.ev[ei]); }
    for (const b of B) {
      if (a === b) continue;
      const key = a < b ? `${a}|${b}` : `${b}|${a}`;
      if (seenPair.has(key)) continue;
      // Sidewalks are mapped as separate ways, so one crossing yields several
      // shared nodes a few metres apart. Cluster them and keep the centre of
      // the biggest cluster, which is the real intersection.
      const hits = [];
      for (const ei of idx.get(b)) {
        for (const v of [S.eu[ei], S.ev[ei]]) if (nodesA.has(v)) hits.push(v);
      }
      if (!hits.length) continue;
      seenPair.add(key);
      const clusters = [];
      for (const v of hits) {
        const lat = S.nLat[v], lon = S.nLon[v];
        let c = clusters.find(x => metres(x.lat, x.lon, lat, lon) < 90);
        if (!c) clusters.push(c = { lat, lon, n: 0, slat: 0, slon: 0 });
        c.n++; c.slat += lat; c.slon += lon; c.lat = c.slat / c.n; c.lon = c.slon / c.n;
      }
      clusters.sort((x, y) => y.n - x.n);
      const c = clusters[0];
      out.push({ label: `${S.names[a]} &amp; ${S.names[b]}`, sub: t('ac.xstreet'),
                 lat: c.lat, lon: c.lon, xstreet: true });
      if (out.length >= 6) return out;
    }
  }
  return out;
}

/* Remote geocoding. Nominatim first, bounded to the study area so "Main
 * Street" lands in Los Angeles rather than Ohio; Photon as a second opinion
 * when Nominatim is empty, rate-limited or down. Both are free public
 * services, which is why a keystroke cancels the previous request and the
 * cross-street path above never touches them at all. */
async function geocode(q, signal) {
  const b = S.meta.bbox;
  const inside = p => p.lat >= b.south && p.lat <= b.north && p.lon >= b.west && p.lon <= b.east;

  const nominatim = async () => {
    const url = `${NOMINATIM}?format=jsonv2&limit=6&addressdetails=0`
      + `&countrycodes=us&bounded=1`
      + `&viewbox=${b.west},${b.north},${b.east},${b.south}`
      + `&accept-language=${S.lang === 'es' ? 'es' : 'en'}`
      + `&q=${encodeURIComponent(q)}`;
    const res = await fetch(url, { signal });
    if (!res.ok) throw new Error(`nominatim ${res.status}`);
    return (await res.json()).map(p => {
      const bits = p.display_name.split(',').map(x => x.trim());
      return { label: bits.slice(0, 2).join(', '), sub: bits.slice(2, 5).join(', '),
               lat: +p.lat, lon: +p.lon };
    }).filter(inside);
  };

  const photon = async () => {
    const url = `${PHOTON}?q=${encodeURIComponent(q)}&limit=6&lang=en`
      + `&bbox=${b.west},${b.south},${b.east},${b.north}`
      + `&lat=${((b.south + b.north) / 2).toFixed(4)}&lon=${((b.west + b.east) / 2).toFixed(4)}`;
    const res = await fetch(url, { signal });
    if (!res.ok) throw new Error(`photon ${res.status}`);
    return ((await res.json()).features || []).map(f => {
      const p = f.properties || {}, [lon, lat] = f.geometry.coordinates;
      const line1 = p.housenumber && p.street ? `${p.housenumber} ${p.street}` : (p.name || p.street || '');
      const line2 = [p.district, p.city || p.county, p.postcode].filter(Boolean).join(', ');
      return { label: line1 || line2, sub: line1 ? line2 : '', lat, lon };
    }).filter(p => p.label && inside(p));
  };

  let failures = 0;
  for (const fn of [nominatim, photon]) {
    try {
      const r = await fn();
      if (r.length) return r;
    } catch (e) {
      if (e.name === 'AbortError') throw e;
      failures++;
    }
  }
  if (failures === 2) { const err = new Error('lookup unavailable'); err.offline = true; throw err; }
  return [];
}

async function searchPlaces(q, signal) {
  const local = crossStreets(q);
  if (local.length) return local;
  return geocode(q, signal);
}

/* ------------------------------------------------------------ url state */
function writeUrl() {
  if (!S.origin || !S.school) return;
  const p = new URLSearchParams();
  p.set('from', `${S.origin.lat.toFixed(5)},${S.origin.lon.toFixed(5)}`);
  p.set('to', S.school.id || `${S.school.lat.toFixed(5)},${S.school.lon.toFixed(5)}`);
  p.set('when', String(S.bucket));
  p.set('mode', S.mode);
  p.set('pick', String(S.pick));
  if (S.lang !== 'en') p.set('lang', S.lang);
  if (S.embed) p.set('embed', '1');
  history.replaceState(null, '', `${location.pathname}?${p}`);
}

/* The link a school pastes into its own site, or texts to families. It carries
 * the school and the language, and nothing about any one student's home. */
function presetUrl(school) {
  const p = new URLSearchParams();
  p.set('school', school.id);
  if (S.lang !== 'en') p.set('lang', S.lang);
  return `${location.origin}${location.pathname}?${p}`;
}

function reportUrl() {
  const link = location.href;
  const title = `Route problem: ${S.school ? S.school.name : 'unknown school'}`;
  const body = `**What looks wrong?**\n\n(describe the block or street)\n\n**The trip:** ${link}\n`;
  return 'https://github.com/safe-routes-la/safe-routes-la.github.io/issues/new'
    + `?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}

function readUrl() {
  const p = new URLSearchParams(location.search);

  // A school on its own: the page a school hands out, with nothing else set.
  const presetId = p.get('school');
  if (presetId) {
    const sc = S.schools.find(s => s.id === presetId);
    if (sc) {
      S.preset = sc; S.school = sc;
      $('school').value = sc.name;
      $('rc-school').value = sc.name; S.rcSchool = sc; $('rc-run').disabled = false;
    }
  }
  const from = p.get('from'), to = p.get('to');
  if (!from || !to) return false;
  const [flat, flon] = from.split(',').map(Number);
  if (!isFinite(flat) || !isFinite(flon)) return false;
  S.origin = { lat: flat, lon: flon };
  $('origin').value = `${flat.toFixed(5)}, ${flon.toFixed(5)}`;

  let sc = S.schools.find(s => s.id === to);
  if (!sc && to.includes(',')) {
    const [tlat, tlon] = to.split(',').map(Number);
    if (isFinite(tlat) && isFinite(tlon)) sc = { name: t('dest.custom'), lat: tlat, lon: tlon };
  }
  if (!sc) return false;
  S.school = sc;
  $('school').value = sc.name;

  const m = p.get('mode');
  if (m === 'bus' || m === 'foot') {
    S.mode = m;
    [...$('mode').children].forEach(c => c.classList.toggle('on', c.dataset.m === m));
  }
  const w = +p.get('when');
  if (w >= 0 && w <= 2) setWindow(w, false);
  const k = +p.get('pick');
  if (k >= 0 && k <= 2) S.pick = k;
  return true;
}

/* ---------------------------------------------------------------- UI */
function setWindow(b, recompute = true) {
  S.bucket = b;
  [...$('when').children].forEach(c => c.classList.toggle('on', +c.dataset.b === b));
  $('lg-when').textContent = winName(b);
  drawRisk();
  if (recompute && S.origin && S.school) compute(false);
}

document.querySelector('.tabs').addEventListener('click', e => {
  const t = e.target.closest('.tab'); if (!t) return;
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
  document.querySelectorAll('.pane').forEach(x => x.classList.remove('on'));
  t.classList.add('on');
  $('p-' + t.dataset.p).classList.add('on');
  if (t.dataset.p !== 'school') spokeLayer.clearLayers();
});

$('when').addEventListener('click', e => {
  const d = e.target.closest('div[data-b]'); if (!d) return;
  setWindow(+d.dataset.b);
});

$('mode').addEventListener('click', e => {
  const d = e.target.closest('div[data-m]'); if (!d) return;
  S.mode = d.dataset.m;
  [...$('mode').children].forEach(c => c.classList.toggle('on', c === d));
  S.pick = 0;
  if (S.origin && S.school) compute(false);
});

$('cards').addEventListener('click', e => {
  const c = e.target.closest('.rc'); if (!c) return;
  select(+c.dataset.i);
});

map.on('click', ev => {
  S.origin = { lat: ev.latlng.lat, lon: ev.latlng.lng };
  $('origin').value = `${S.origin.lat.toFixed(5)}, ${S.origin.lon.toFixed(5)}`;
  redrawPins();
  $('go').disabled = !S.school;
  if (S.school) compute();
});

$('go').addEventListener('click', () => compute());

$('share').addEventListener('click', async () => {
  writeUrl();
  try {
    await navigator.clipboard.writeText(location.href);
    $('share').textContent = t('share.done');
    setTimeout(() => applyLang(), 2200);
  } catch (e) {
    toast(t('toast.copyfail'));
  }
});

$('print').addEventListener('click', () => {
  if (!S.routes) { toast(t('toast.print')); return; }
  buildPrintCard();
  window.print();
});

/* ---------------------------------------------------------- print card */
/* A sheet a student can carry: the streets in order, the tradeoff in one line,
 * and the link that reopens the same trip. Text only, so it prints on anything
 * and photocopies cleanly. */
function buildPrintCard() {
  const o = S.routes[S.pick];
  const b = S.bucket;
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const vals = [0, 1, 2].map(k => exposureAt(o, k) / 100);
  const max = Math.max(...vals, 0.01);
  const row = (label, m, worst) =>
    `<li><span>${esc(label)}</span><span class="m">${esc(m)}</span>`
    + `<span class="c">${worst == null ? '' : Math.round(worst * 100)}</span></li>`;

  let turns = '';
  if (o.kind === 'transit') {
    if (o.legA) turns += turnList(o.legA, b).map(x => row(x.label, fmtM(x.len), x.worst)).join('');
    o.legs.forEach((leg, k) => {
      const pat = T.patterns[leg.pi];
      turns += row(t('turn.board', { r: pat.r, stop: stopName(pat.s[leg.posA]) }),
                   t('turn.wait', { n: Math.round(pat.w) }), o.stopRisk);
      turns += row(t('turn.ride', { n: leg.posB - leg.posA }),
                   t('card.min', { n: Math.round(Math.max(0, pat.t[leg.posB] - pat.t[leg.posA]) / 60) }), null);
      turns += row(t('turn.off', { stop: stopName(pat.s[leg.posB]) }), '', o.stopRisk);
      if (k === 0 && o.xfer && o.xfer.metres > 0) {
        turns += row(t('turn.xfer', { stop: stopName(o.xfer.to) }), fmtM(o.xfer.metres), o.stopRisk);
      }
    });
    if (o.legB) turns += turnList(o.legB, b).map(x => row(x.label, fmtM(x.len), x.worst)).join('');
  } else {
    turns = turnList(o.r, b).map(x => row(x.label, fmtM(x.len), x.worst)).join('');
  }

  const mode = t(o.kind === 'transit' ? 'pc.mode.bus' : 'pc.mode.foot');
  const date = new Date().toLocaleDateString(S.lang === 'es' ? 'es-US' : 'en-US',
    { year: 'numeric', month: 'long', day: 'numeric' });

  $('printcard').innerHTML = `
    <div class="k">${t('pc.k')}</div>
    <h1>${esc(S.school.name)}<small>${t('pc.from', { from: esc($('origin').value) })}</small></h1>
    <div class="meta">${t('pc.when', { win: winName(b), clock: winClock(b), mode })}</div>
    <table class="sum">
      <tr><td>${t('pc.opt')}</td><td>${esc(optLabel(o))}</td></tr>
      <tr><td>${t('pc.time')}</td><td>${t('card.min', { n: Math.max(1, Math.round(optTime(o))) })}</td></tr>
      <tr><td>${t('pc.walk')}</td><td>${fmtM(optWalk(o))}</td></tr>
      <tr><td>${t('pc.exp')}</td><td>${expUnits(o).toFixed(1)}</td></tr>
    </table>
    <div class="why">${$('because').innerHTML}</div>
    <h2>${t('pc.turns')}</h2>
    <ol>${turns}</ol>
    <h2>${t('pc.hours')}</h2>
    <div class="hours">${vals.map((v, k) =>
      `<div><span>${cap(winName(k))}</span><span class="t"><i style="width:${(v / max * 100).toFixed(0)}%"></i></span><b>${v.toFixed(1)}</b></div>`).join('')}</div>
    <div class="foot">
      <div>${t('pc.open')}: <span class="url">${esc(location.href)}</span></div>
      <div style="margin-top:4pt">${t('pc.foot')}</div>
      <div style="margin-top:4pt">${t('pc.printed', { date })}</div>
    </div>`;
}

/* -------------------------------------------------------- preset / embed */
function renderPreset() {
  const el = $('preset');
  if (!S.preset) { el.style.display = 'none'; return; }
  el.innerHTML = t('preset', { school: S.preset.name,
    href: location.pathname + (S.lang !== 'en' ? `?lang=${S.lang}` : '') });
  el.style.display = '';
}

function renderEmbed() {
  const sc = S.rcSchool || S.preset;
  const el = $('r-embed');
  if (!sc) { el.style.display = 'none'; return; }
  const url = presetUrl(sc);
  $('embed-code').value =
    `<iframe src="${url}&embed=1" width="100%" height="640" style="border:0" `
    + `title="Safe Routes to School: ${sc.name.replace(/"/g, '')}" loading="lazy"></iframe>\n`
    + `<!-- ${url} -->`;
  el.style.display = '';
}

$('embed-copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('embed-code').value);
    $('embed-copy').textContent = t('emb.done');
    setTimeout(() => applyLang(), 2200);
  } catch (e) {
    $('embed-code').select();
    toast(t('toast.copyfail'));
  }
});

$('lang').addEventListener('click', e => {
  const d = e.target.closest('span[data-l]'); if (!d) return;
  setLang(d.dataset.l);
});

/* ------------------------------------------------------------- offline */
/* The service worker keeps the page and its 5 MB graph on the device, so a
 * student with no data plan can still plan a walk after the first visit. The
 * basemap is not cached (it is CARTO's to serve), which is why the offline
 * note says the background will be missing. */
function renderNet() {
  const el = $('net');
  if (!navigator.onLine) { el.innerHTML = t('net.off'); el.classList.add('show'); return; }
  if (S.saved) { el.innerHTML = t('net.saved'); el.classList.add('show'); return; }
  el.classList.remove('show');
}
window.addEventListener('online', renderNet);
window.addEventListener('offline', renderNet);

function registerOffline() {
  if (!('serviceWorker' in navigator)) return;
  if (location.protocol !== 'https:' && location.hostname !== 'localhost'
      && location.hostname !== '127.0.0.1') return;
  navigator.serviceWorker.register('sw.js').then(reg => {
    if (!reg) return;
    const ready = () => { S.saved = true; renderNet(); };
    if (reg.active) ready();
    else {
      const w = reg.installing || reg.waiting;
      if (w) w.addEventListener('statechange', () => { if (w.state === 'activated') ready(); });
    }
  }).catch(e => console.warn('offline copy not available', e));
}

$('demo').addEventListener('click', () => {
  const sc = S.schools.find(s => /Enriched Studies/i.test(s.name)) || S.schools[0];
  S.school = sc;
  S.origin = { lat: 34.0380, lon: -118.3620 };
  $('school').value = sc.name;
  $('origin').value = 'Near Hauser & Venice, Mid-City';
  setWindow(2, false);
  redrawPins();
  $('go').disabled = false;
  compute();
});

$('t-risk').addEventListener('click', e => {
  S.showRisk = !S.showRisk;
  e.target.classList.toggle('on', S.showRisk);
  drawRisk();
});
$('t-schools').addEventListener('click', e => {
  S.showSchools = !S.showSchools;
  e.target.classList.toggle('on', S.showSchools);
  if (S.showSchools) {
    if (!schoolLayer.getLayers().length) {
      for (const s of S.schools) {
        L.circleMarker([s.lat, s.lon], {
          radius: 2.5, color: '#211f18', weight: 1, fillOpacity: .45,
        }).bindTooltip(s.name, { direction: 'top' }).addTo(schoolLayer);
      }
    }
    schoolLayer.addTo(map);
  } else map.removeLayer(schoolLayer);
});

$('rc-run').addEventListener('click', () => {
  if (S.rcSchool) report(S.rcSchool);
});

/* -------------------------------------------------------------- boot */
async function fetchGraph(onPct) {
  if (typeof DecompressionStream === 'function') {
    try {
      const res = await fetch('data/graph.bin.gz');
      if (res.ok && res.body) {
        const total = +(res.headers.get('content-length') || 0);
        let got = 0;
        const counter = new TransformStream({
          transform(chunk, ctrl) {
            got += chunk.length;
            if (total) onPct(got / total, got, total);
            ctrl.enqueue(chunk);
          },
        });
        const buf = await new Response(
          res.body.pipeThrough(counter).pipeThrough(new DecompressionStream('gzip'))
        ).arrayBuffer();
        // A host that sets Content-Encoding: gzip has the browser inflate for
        // us, so inflating twice yields garbage rather than throwing. Check the
        // magic before trusting it.
        if (buf.byteLength > 24 && new Uint32Array(buf, 0, 1)[0] === MAGIC) return buf;
        console.warn('inflated graph failed its magic check, using graph.bin');
      }
    } catch (e) {
      console.warn('gzip path unavailable, using graph.bin', e);
    }
  }
  const res = await fetch('data/graph.bin');
  if (!res.ok) throw new Error(`graph.bin: HTTP ${res.status}`);
  return res.arrayBuffer();
}

function windowForNow() {
  const h = new Date().getHours();
  if (h >= 5 && h < 10) return 0;
  if (h >= 10 && h < 17) return 1;
  return 2;
}

async function boot() {
  const [meta, schools, names, transit] = await Promise.all([
    fetch('data/graph_meta.json').then(r => r.json()),
    fetch('data/schools.json').then(r => r.json()),
    fetch('data/street_names.json').then(r => r.json()),
    fetch('data/transit.json').then(r => r.json()).catch(() => null),
  ]);
  S.meta = meta; S.schools = schools; S.names = names;
  if (transit) initTransit(transit);
  else {
    // Without the feed the bus option cannot work, so retire it rather than
    // leaving a control that silently does nothing.
    const bus = document.querySelector('#mode div[data-m="bus"]');
    if (bus) { bus.style.display = 'none'; }
  }
  $('boot-sub').textContent =
    t('boot.sub', { n: meta.crimes.toLocaleString(), km: meta.km.toLocaleString() });

  $('lg-scale').innerHTML =
    BANDS.map(b => `<i style="background:${b.hex}"></i>`).join('');

  const buf = await fetchGraph((pct, got, total) => {
    $('boot-bar').style.width = `${(pct * 100).toFixed(0)}%`;
    $('boot-sub').textContent =
      `${(got / 1e6).toFixed(1)} of ${(total / 1e6).toFixed(1)} MB`;
  });

  $('boot-msg').textContent = t('boot.build');
  $('boot-bar').style.width = '100%';
  decode(buf);
  buildAdjacency();
  buildIndex();
  new StreetTiles({ zIndex: 0, minZoom: 12, updateWhenIdle: true }).addTo(map);

  attachAC('school', 'ac-school', q => searchSchools(q), it => {
    S.school = it.school;
    $('school').value = it.school.name;
    redrawPins();
    $('go').disabled = !S.origin;
    if (S.origin) compute(); else map.setView([it.school.lat, it.school.lon], 15);
  });

  attachAC('origin', 'ac-origin', searchPlaces, it => {
    S.origin = { lat: it.lat, lon: it.lon };
    $('origin').value = it.label.replace(/&amp;/g, '&');
    redrawPins();
    $('go').disabled = !S.school;
    if (S.school) compute(); else map.setView([it.lat, it.lon], 15);
  }, { remote: true });

  attachAC('rc-school', 'ac-rc', q => searchSchools(q), it => {
    S.rcSchool = it.school;
    $('rc-school').value = it.school.name;
    $('rc-run').disabled = false;
    renderEmbed();
  });

  const now = windowForNow();
  const restored = readUrl();
  if (!restored) {
    setWindow(now, false);
    const clock = new Date().toLocaleTimeString(S.lang === 'es' ? 'es-US' : 'en-US',
      { hour: 'numeric', minute: '2-digit' });
    setDyn($('when-note'), 'when.now', { clock, win: winName(now) });
  } else {
    setDyn($('when-note'), 'when.restored');
  }
  if (S.preset && !restored) {
    map.setView([S.preset.lat, S.preset.lon], 15);
    redrawPins();
  }
  applyLang();

  $('boot').classList.add('done');
  drawRisk();
  if (restored) { redrawPins(); compute(); }
  registerOffline();
}

/* Language and embed mode are decided before anything loads, so the loading
 * screen itself is already in the right language. */
(function early() {
  const p = new URLSearchParams(location.search);
  let l = p.get('lang');
  if (!l) { try { l = localStorage.getItem('srs-lang'); } catch (e) { /* ignore */ } }
  if (!l && /^es\b/i.test(navigator.language || '')) l = 'es';
  if (l && LANGS[l]) S.lang = l;
  if (p.get('embed') === '1') { S.embed = true; document.body.classList.add('embed'); }
  applyLang();
})();

boot().catch(err => {
  $('boot').classList.remove('done');
  $('boot-msg').textContent = t('boot.fail');
  $('boot-sub').textContent = err.message;
  console.error(err);
});
