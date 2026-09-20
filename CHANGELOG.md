# Changelog

## Dark theme, a first run, and handing the route to a map app (September 2026)

- **New theme.** The warm cream ground is gone. A quiet block on a near-black
  ground can fall almost to the background while a bad one glows, which is a
  contrast range cream could not give — the old map read as a brown smear at
  city zoom. The risk scale is now one hue with stepped lightness rather than
  green→amber→red: risk is a magnitude, and a rainbow ramp invents category
  boundaries the data does not have. Both ramps were checked for monotone
  lightness, step separation and contrast against the ground rather than picked
  by eye. The route line is cool on purpose — nothing on the risk scale is
  cool, so the chosen route can never be read as a risk value.
- **It opens on a finished walk.** The site used to open on a three-step
  instruction list and two empty fields, so the first thing a visitor had to do
  was homework. It now computes an example route on load, scored for the hour it
  actually is, and says plainly that it is an example.
- **Open it somewhere else.** Google Maps, Apple Maps, Waze and GPX.

  None of those apps will draw a route you hand them — they take endpoints and
  run their own router. Sent origin and destination alone, Google returns the
  shortest walk, which is the exact route this app exists to talk you out of:
  measured over 19 random school trips that costs **+350% exposure on average
  and +5,628% at worst**. Google does accept ordered waypoints, so its router
  can be pulled onto our path, but choosing them is not a formula — evenly
  spaced points are non-monotonic, and three of them can land exactly where the
  shortest path already goes. Picking sharp corners plateaus around 66% of the
  route.

  What works is greedy: hand off, find the point our route strays furthest
  from what came back, pin that, repeat. Median **4 waypoints, 96% of the route
  retained, +3.0% exposure**.

  Apple's URL scheme has no waypoint parameter and Waze has neither waypoints
  nor a walking mode, so both get the direct route and the buttons say so.
  GPX is the only format that carries the route exactly; Organic Maps, OsmAnd
  and Komoot all import it.
- Service worker cache bumped, so a returning visitor cannot get the old theme
  against the new code.

## Validation (September 2026)

The model had never been tested against data it had not been fitted on. This
round is about that, and about two bugs found while looking.

- **`validate.py` was reading the wrong bytes.** It skipped the street-name
  section entirely, so every risk statistic it printed was a name id
  reinterpreted as a score, and it read the header as 20 bytes where the writer
  emits 24 — which made it crash outright rather than merely lie. Both fixed;
  it now asserts its own offsets add up to the file size, and reproduces the
  README's table exactly.
- **Holdout evaluation** (`pipeline/eval/holdout.py`). Fits the kernel on
  2020–2023 and scores it against 2024 — hit rate in the worst 1/5/10% of the
  network, PAI and ROC AUC per time window — against three baselines dumb
  enough that beating them means something. Not yet run against Los Angeles;
  `pipeline/eval/holdout_results.md` says so at the top rather than filling
  itself with anything else.
- **The evaluation is itself tested**, against synthetic fixtures with known
  answers. One has structure to find, one has none, and CI fails if the second
  ever stops reporting a null.
- **Sensitivity sweep** (`pipeline/eval/sensitivity.py`). Every constant in
  `config.py` perturbed over a plausible range, ranked by how much of the
  safest route actually changes, against a measured noise floor. Kernel
  bandwidth dominates everything else.
- **The streetlight credit is no longer time-blind.** A lit block used to earn
  the same 35% discount at noon as at midnight. It is now scaled by how much of
  each window is dark, from NOAA sunrise and sunset over the LA school year.
  The shipped graph has not been rebuilt, so the site still serves the old
  surface.
- **Sparse blocks are shrunk towards their neighbourhood** by empirical Bayes,
  with the prior strength fitted rather than chosen. The per-block confidence
  this produces does not fit the binary format, so it is proposed in
  `docs/FORMAT_V3.md` instead of being slipped in.
- **Hygiene.** Pinned `requirements.txt`, an MIT `LICENSE` with the data terms
  spelled out, a GitHub Actions workflow, and `pipeline/check_apis.py` to say
  which upstream is down when a build dies eight minutes in.

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
