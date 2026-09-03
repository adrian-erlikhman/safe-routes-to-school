# Safe Routes to School

Walking directions for Los Angeles students, built from where students actually
get robbed rather than from distance alone.

**[safe-routes-la.github.io](https://safe-routes-la.github.io)**

Pick a school, type where you start, and the app offers three routes with the
tradeoff spelled out: how much longer each one takes, how much calmer it is, and
which street it avoids to get there. Everything runs in the browser. There is no
server behind the page.

It speaks Spanish ([safe-routes-la.github.io/?lang=es](https://safe-routes-la.github.io/?lang=es)),
prints a one-page walking card for a student without a phone, gives every school
its own link and an embeddable version, and keeps working with no data
connection after the first visit.

## Since the competition

The entry placed third in the Young Coders' Sphere Code for Transportation
challenge in August 2026. What has shipped since, in the order it mattered:

| | Why |
|---|---|
| **Spanish, one tap** | Most LAUSD families speak Spanish at home. A safety tool a parent cannot read is not a safety tool. The switch covers the route explanations, the bus directions, the school report and the printed card, sticks between visits, and follows shared links. |
| **Printable walking card** | The streets in order with each block's score, the tradeoff in one line, the same trip at the other two hours, and the link that reopens it. One sheet, black and white, for a student who does not carry a phone. |
| **Cross streets, offline** | "Hauser & Venice" is how people here say where they are, and it is the one input geocoders handle badly. An intersection is a node shared by a block of each name, so it is resolved on the device from the street graph itself. A "use my location" button covers the other common case. |
| **A page per school** | `?school=<id>` opens the planner with the school chosen. The School tab writes the snippet a school website can paste, and the same link works in a newsletter or a text to families. |
| **The map draws its own streets** | The graph holds every walkable block, so a canvas layer under the tiles renders them. When the tile host is unreachable, the route still sits on a street map. |
| **Works offline** | A service worker keeps the page and the 5 MB scored graph on the device, and the site installs to a home screen. No data plan needed after the first load. |
| **Report a problem** | Every route links to a pre-filled issue with the trip attached, for the student or parent who knows a block better than the data does. |

Details in [`CHANGELOG.md`](CHANGELOG.md). Screenshots in
[`docs/screenshots/`](docs/screenshots/).

## Why we built it

Between 2020 and 2024, 1,838 children aged 10 to 18 were robbed on the streets
of Los Angeles. 1,026 of those robberies happened during school commute hours,
which is 56% of them packed into about five hours of the day.

Those robberies are not scattered at random. They repeat in specific places, and
every one of those places is already published in the city's open data. What no
map app does is route around them.

The federal Safe Routes to School program has existed since 1971 and deals
almost entirely with cars: crosswalks, speed bumps, crossing guards. Ask a
student in Los Angeles what worries them on the walk home and traffic is rarely
the answer. This models the thing they do name.

## What it does

Three routes, not one, because there is no single right answer about how much
detour a walk is worth:

| | What it is |
|---|---|
| Shortest | What a map app hands you |
| Balanced | The most calm per extra step |
| Safest | Lowest exposure the model can find |

Then it explains itself. A real result, walking to LACES in Mid City after dark:

> Skips 552 m of South Fairfax Avenue, which scores 65 at this hour. Goes along
> Venice Boulevard instead, at 20. Costs you 3 minutes. Total exposure drops 50%.

Underneath that you get the same route scored at each hour of the day, and a
street by street list you can actually follow while walking.

There is also a school report, which scores all sixteen directions a student
might approach a school from. For LACES in the evening, walking in from the
south southeast means 2.5 times the exposure of walking in from the east
northeast. That is the version a principal or a council member can act on,
rather than advice for one student.

## Walking or riding

The bus changes the problem rather than just the route. Minutes on board are
minutes off the street, so for longer trips the calmest option is usually not a
walking route at all.

Switch to bus and rail and the app finds single-ride itineraries: walk to a
stop, wait, ride, walk the rest. A real trip from south of USC up to LACES:

| | Time | On foot | Exposure |
|---|---|---|---|
| Walking the whole way | 118 min | 9.34 km | 22.8 |
| Route 35/38 | 43 min | 1.98 km | 8.1 |

Faster and 65% less exposure, because only 1.98 km of it happens on a sidewalk.

Waiting is treated honestly. Standing at a stop is exposure without progress, so
a minute of waiting is charged like 80 m of walking on that block, which is
above walking pace on purpose. A stop on a bad corner is not a safe place to
spend eight minutes, and the model should not pretend otherwise.

Transfers are out of scope. A student changing buses twice to shave exposure is
advice nobody follows, and every extra leg adds another wait to stand through.

## How it works

### The data

| Source | What we take | Records |
|---|---|---|
| [LAPD crime data, 2020 to 2024](https://data.lacity.org/Public-Safety/Crime-Data-from-2020-to-Present/2nrs-mtv8) | Violent incidents in public pedestrian space | 85,634 |
| [LA Bureau of Street Lighting](https://maps.lacity.org/lahub/rest/services/Bureau_of_Street_Lighting/MapServer) | Streetlight locations | 128,534 |
| [California Department of Education](https://www.cde.ca.gov/ds/si/ds/pubschls.asp) | Public school locations | 668 in area |
| [OpenStreetMap](https://www.openstreetmap.org) via Overpass | Walkable street network | 431,599 blocks |
| [LA Metro GTFS](https://developer.metro.net/gtfs-schedule-data/) bus and rail | Stops, ride times, headways | 5,395 stops |

### What we threw away

Most of the modelling judgement went into filtering rather than into the maths.

The raw LAPD file holds roughly a million records. We keep only offences that
threaten someone walking down a street, so robbery, assault, criminal threats
and brandishing a weapon stay while property crime and fraud go. A stolen
catalytic converter tells you nothing about whether a child is safe on that
block.

A second filter keeps only incidents that happened in public space: street,
sidewalk, alley, bus stop, park, underpass. That one drops about 81,000 records
that happened indoors, and it matters more than anything else we did. Domestic
violence is serious, and it is also not a hazard of walking past a building.
Counting it would have marked ordinary residential neighbourhoods as dangerous
to walk through, which would have been both wrong and the kind of wrong that
does real damage.

### Scoring a block

Every surviving incident is weighted by severity, by how recently it happened
(exponential decay on a 2.5 year half life), and by whether the victim was a
child. Crimes against children count triple, because a crime against a
13 year old tells you more about the risk to a 13 year old than a crime against
an adult does.

Incidents then spread out as Gaussian kernels with a 120 m bandwidth. We chose
120 m to match how coarsely LAPD records locations, not to suggest we know
better than that. Each block is sampled every 25 m, scored, and ranked against
every other block, so 90 means the block is worse than 90% of Los Angeles at
that hour.

Two normalisation choices matter here.

**Rates, not counts.** The three windows cover unequal spans, and evening covers
12 hours, so it would look worst simply for being longest. Dividing by span
gives something we did not expect:

| Window | Incidents | Span | Per hour |
|---|---|---|---|
| Morning, 5am to 10am | 10,261 | 5 h | 2,052 |
| Afternoon, 10am to 5pm | 29,721 | 7 h | **4,246** |
| Evening, 5pm to 5am | 45,652 | 12 h | 3,804 |

The afternoon walk home is the worst hour of a student's day, worse hour for
hour than after dark. That is the same 2pm to 6pm window the robbery figure
points at, and we were not looking for it.

**Pooled ranking.** Scores are ranked against the pooled distribution of all
three windows rather than each window separately. Ranking each window on its own
forces all three to an identical distribution, which quietly erases the fact
that some hours are genuinely more dangerous, and that was the whole reason for
having windows. Pooling keeps them comparable, so 70 means the same danger at
8am as at 9pm.

After that, streetlights earn a block up to 35% off its score, capped so a well
lit block in a bad area never comes out looking calm. Wide arterials take a
penalty and footpaths get a small credit.

### Choosing a route

Streets are cut into blocks at real intersections, using shared OpenStreetMap
node IDs rather than rounded coordinates, and reduced to the largest connected
component. Routing is A\*, minimising:

```
cost(block) = length × (1 + λ · risk^1.5)
```

The three options are the same search at three values of λ. A fixed pair of
values often returns the same path twice, because past some threshold the search
has already avoided everything it can, so the app walks a ladder of seven values
and keeps only the routes that differ.

The 1.5 exponent tolerates slightly elevated blocks while avoiding genuinely bad
ones firmly. A linear penalty produces mushy routes that dodge everything a
little and nothing much.

Every block multiplier is at least 1, so straight line distance never
overestimates what is left to walk. The heuristic is admissible, which means the
route is provably the cheapest one under this cost and not an approximation.

### Naming the streets

OpenStreetMap maps most Los Angeles sidewalks as separate footways with no name,
so 68% of blocks started out unnamed and the directions read "unnamed path" for
whole kilometres. Each unnamed block now inherits the name of the nearest named
block running roughly parallel to it, within 25 m and 35 degrees. That took
named coverage from 32% to 71% and is what lets the app say "Venice Boulevard"
instead of drawing a line and leaving you to guess.

### Getting it into a browser

431,599 blocks as JSON costs 40 MB and a multi second parse on the main thread.
The same data packed as typed arrays is 10.8 MB, ships pre-gzipped at 5.2 MB,
and is usable the moment it lands because the browser can view the buffer
directly. Douglas-Peucker at 10 m drops 358,000 of the 385,000 shape points,
which no 4 pixel wide line could have shown anyway.

The kernel density is evaluated by rasterising incidents onto a 20 m grid and
convolving with a Gaussian, rather than by running a radius query per sample
point. Both give the same answer for a fixed bandwidth, but the convolution
turns about four million spatial queries into three filters, which is the
difference between minutes and hours when you want to re-tune the weights.

## Checking that it works

`pipeline/validate.py` re-implements the browser's cost function in Python and
compares A\* against plain Dijkstra on random pairs. Identical costs mean the
heuristic really is admissible. Settling 14% to 45% of the nodes means it is
doing real work instead of degenerating into Dijkstra.

```
A* optimality vs Dijkstra (identical cost required):
  0: lam=0.0  bucket=am    cost=    1,607.0  settled dijkstra= 3,632 astar=   590  (16% of the work)  MATCH
  1: lam=2.0  bucket=pm    cost=    2,851.6  settled dijkstra= 4,922 astar= 1,327  (27% of the work)  MATCH
  2: lam=5.0  bucket=night cost=    3,501.8  settled dijkstra=   841 astar=   376  (45% of the work)  MATCH
  3: lam=0.0  bucket=am    cost=    1,884.0  settled dijkstra= 7,858 astar= 1,117  (14% of the work)  MATCH
  4: lam=2.0  bucket=pm    cost=    3,338.0  settled dijkstra= 9,203 astar= 2,874  (31% of the work)  MATCH
  5: lam=5.0  bucket=night cost=    2,090.3  settled dijkstra= 2,775 astar= 1,019  (37% of the work)  MATCH
  -> PASS
```

It also checks the model earns its keep. Six random evening trips:

```
    1429 m ->   1452 m (+ 1.6%)   exposure      747 ->      603  (+19.2%)
    1785 m ->   1802 m (+ 1.0%)   exposure      276 ->      157  (+43.1%)
    1711 m ->   1815 m (+ 6.1%)   exposure      351 ->      239  (+31.9%)
    1568 m ->   1696 m (+ 8.2%)   exposure      562 ->      349  (+37.9%)
    1801 m ->   2183 m (+21.2%)   exposure      581 ->      237  (+59.3%)
    1371 m ->   1382 m (+ 0.8%)   exposure      810 ->      601  (+25.9%)
  -> exposure reduced on 6/6 trips
```

And that the windows are substantive. Morning and evening risk correlate at
0.90, but 78,669 blocks differ by more than 0.15 between them, which is more
than enough to change a route.

## Running it

```bash
pip install numpy scipy
```

Fetch the source data. This pulls about 100 MB into `.cache/`, resumes if it
fails, and is the slow part because the public Overpass instance rate limits.

```bash
python pipeline/fetch_crime.py && python pipeline/fetch_lights.py && python pipeline/fetch_schools.py && python pipeline/fetch_osm.py
```

Build the scored graph into `data/`, then check it:

```bash
python pipeline/build_graph.py && python pipeline/validate.py
```

Serve it. The site is static, so anything will do:

```bash
python -m http.server 8000
```

### Pointing it at another city

One bounding box in `pipeline/config.py` is the only Los Angeles specific thing
here. Change `BBOX`, swap `SOCRATA_CRIME` for that city's incident dataset, and
re-run. The kernel density, the lighting credit, the graph build and the router
are all city agnostic. Chicago, New York, Seattle, Denver, Austin, Baltimore,
Toronto and London all publish incident data in a compatible shape.

## Layout

```
index.html  app.js        the whole front end, no build step and no framework
es.js                     Spanish; a third language is one more file like it
sw.js  manifest.webmanifest   offline copy and home-screen install
vendor/leaflet/           Leaflet 1.9.4, vendored so offline never needs a CDN
data/                     what the site serves: graph.bin.gz, schools, names, transit
docs/screenshots/         what the features look like
pipeline/
  config.py               study area, crime filters, model weights
  fetch_crime.py          LAPD incidents through the Socrata API
  fetch_lights.py         streetlights through the city's ArcGIS MapServer
  fetch_schools.py        the state school directory
  fetch_osm.py            walkable streets, tiled across Overpass mirrors
  geo.py                  local planar projection
  build_graph.py          intersection splitting, risk model, binary packing
  validate.py             graph checks and the A* optimality proof
  fetch_transit.py        LA Metro GTFS reduced to stops, ride times, headways
```

## What this cannot tell you

Stating these plainly makes the tool more useful rather than less.

Reported crime is not all crime. Reporting rates vary between neighbourhoods and
with immigration status, so a low score partly reflects who calls the police.

Locations are approximate, because LAPD rounds coordinates to protect victims.
The 120 m bandwidth is chosen to match that, and the app should not be read as
knowing which side of a street something happened on.

The data stops in December 2024, when LAPD moved to a new records system. What
we have is complete and stable for those five years, and it is also not live.

Scores are relative to Los Angeles. A 20 means quiet by the standards of this
city, which is not the same as quiet.

Most importantly, this is a second opinion about a walk rather than a promise
about one. An empty street the model likes can still be worse than a busy one it
marks down, and you know things about your own neighbourhood that a crime table
does not record.

## Credits

Crime records are published by the City of Los Angeles under the LA Open Data
terms. The street network is OpenStreetMap, licensed ODbL. Basemap tiles are
CARTO. Address lookup uses Nominatim. School locations come from the California
Department of Education. Transit stops and schedules are LA Metro's GTFS feeds.
The map library is [Leaflet](https://leafletjs.com), BSD-2, vendored under
`vendor/leaflet/`.
