# Changelog

## After the competition (September 2026)

The Code for Transportation entry was judged on 24 August 2026 and placed
third. Everything below shipped afterwards.

- **Spanish.** The whole interface, including the route explanations, the bus
  directions, the school report and the printed card, switches to Spanish with
  one tap (`es.js`). The choice sticks, follows shared links (`?lang=es`), and
  is picked automatically for browsers set to Spanish. A third language is one
  more file shaped like `es.js`.
- **Printable walking card.** Any route prints as a single sheet: the tradeoff
  in one line, the streets in order with each block's score, the same trip at
  the other two hours, and the link that reopens it. For a student who does
  not carry a phone.
- **A page per school.** `?school=<id>` opens the planner with a school already
  chosen. The School tab writes the snippet a school website can paste
  (`&embed=1` hides everything but the planner), and the same link works in a
  newsletter or a text to families.
- **Works offline.** A service worker (`sw.js`) keeps the page, the router and
  the 5 MB scored graph on the device after the first visit, and the site
  installs to a home screen (`manifest.webmanifest`). A student with no data
  plan can still plan a walk; only the basemap tiles are missing offline.
- **The map draws its own streets.** The graph holds every walkable block, so
  a canvas layer under the tiles renders them. When the tile host is
  unreachable, offline or on a school network that blocks it, the route still
  sits on a street map instead of a blank page.
- **Cross streets, on the device.** "Hauser & Venice", "Pico / La Brea",
  "wilshire at western" resolve from the street graph itself: an intersection
  is a node shared by a block of each name. Instant, exact to the graph the
  router uses, and offline. Abbreviations (blvd, ave, st) are understood.
- **Address lookup hardened.** A keystroke cancels the request in the air,
  Photon backs up Nominatim when it is empty or rate-limited, and a failed
  lookup says so instead of pretending nothing matched.
- **Use my location.** One tap starts the route from where the student is
  standing, with a check that they are inside the map area.
- **Small things.** Results scroll into view when a trip is planned, a "start
  over" link clears everything, the explanation never says "skips Venice,
  goes along Venice instead" when both sides of a boulevard share a name.
- **Report a problem.** Every route carries a link that opens a pre-filled
  issue with the trip attached, so a student or parent who knows a block
  better than the data does has somewhere to say so.
- **No CDN.** Leaflet is vendored under `vendor/leaflet/`, so nothing on the
  page depends on a third party being reachable.
- **Transit stops in the Method tab**, an "About this project" note, and
  `app.js` normalised to Unix line endings (it had CRLF endings and a stray
  NUL byte inside a string literal).

## Competition build (24 August 2026)

- Address search, three named route options with the reasoning written out,
  same-route-at-every-hour comparison, street by street directions.
- Bus and rail from LA Metro GTFS, with one transfer and waiting charged as
  exposure.
- School report: sixteen approaches scored and ranked.
- Shareable links.
