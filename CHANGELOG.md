# Changelog

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
