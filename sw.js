/* Offline copy of Safe Routes to School.
 *
 * After one visit the page, the router and the 5 MB scored graph live on the
 * device, so a student with no data plan can still plan a walk. The basemap
 * tiles and address lookup are third-party services and are never cached:
 * offline, the route draws over a blank background and addresses come from a
 * dropped pin or a shared link instead.
 *
 * Bump VERSION whenever anything in data/ changes; the old cache is dropped on
 * the next activation. */
const VERSION = 'srs-2026-09-03';

const SHELL = [
  './', 'index.html', 'app.js', 'es.js', 'manifest.webmanifest',
  'icon.svg', 'icon-192.png', 'icon-512.png',
  'vendor/leaflet/leaflet.js', 'vendor/leaflet/leaflet.css',
  'vendor/leaflet/images/marker-icon.png', 'vendor/leaflet/images/marker-shadow.png',
];
const DATA = [
  'data/graph_meta.json', 'data/schools.json', 'data/street_names.json',
  'data/transit.json', 'data/graph.bin.gz',
];
const NEVER = /cartocdn\.com|nominatim\.openstreetmap\.org|fonts\.g|github\.com/;

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(VERSION);
    await c.addAll([...SHELL, ...DATA]);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k !== VERSION) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || NEVER.test(req.url)) return;
  const url = new URL(req.url);
  const isData = url.origin === location.origin && url.pathname.includes('/data/');

  e.respondWith((async () => {
    const c = await caches.open(VERSION);
    if (isData) {
      // Data is versioned by VERSION, so the copy on the device is the copy.
      const hit = await c.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok) c.put(req, res.clone());
      return res;
    }
    // Everything else: fresh when online so a deploy shows up at once, and
    // the saved copy when the network is gone.
    try {
      const res = await fetch(req);
      if (res.ok) c.put(req, res.clone());
      return res;
    } catch (err) {
      const hit = await c.match(req, { ignoreSearch: url.origin === location.origin });
      if (hit) return hit;
      throw err;
    }
  })());
});
