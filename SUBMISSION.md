# YCS "Code for Transportation" submission

Fill in the team name and members, then paste the rest into the form.

- Live site: https://safe-routes-la.github.io
- Code: https://github.com/safe-routes-la/safe-routes-la.github.io
- Video script and shot list: `VIDEO.md`

---

## Team name

`fill in`

## Team members

Adrian Erlikhman, Michael `<surname>`

## Project description

**Safe Routes to School** / https://safe-routes-la.github.io

Between 2020 and 2024, 1,838 children aged 10 to 18 were robbed on the streets
of Los Angeles, and 1,026 of those robberies happened during school commute
hours. That is 56% of them inside five hours of the day, on blocks the city
already publishes in its open data. No map app routes around them. Ours does.
You pick a school, type your address, and get three routes with the reasoning
written out: skips 552 m of South Fairfax Avenue, which scores 65 at this hour,
goes along Venice Boulevard instead at 20, costs you three minutes, halves your
total exposure. You can check that rather than having to trust it.

Buses change the problem, because minutes on board are minutes off the street.
Exposition and Normandie up to LACES is 118 minutes and 9.3 km of sidewalk on
foot, against 40 minutes and 750 m of walking on Route 206 changing to Route
33, which cuts exposure by 80%. We plan one transfer and charge for waiting,
since a minute at a stop costs the same as 80 m of walking there. Splitting by
hour also turned up something we were not looking for: per hour the afternoon
walk home is worse than after dark, 4,246 incidents against 3,804, so the most
dangerous hour of a student's day is the one nobody supervises.

Underneath are 85,634 violent incidents, 128,534 streetlights, 5,395 transit
stops and 431,599 scored blocks, though most of the judgement went into
filtering rather than the maths. We keep only offences that threaten someone
walking, and only those in public space, which drops 81,000 indoor incidents.
Domestic violence is serious and is also not a hazard of walking past a
building, so counting it would have branded ordinary residential neighbourhoods
dangerous and damaged the places this is meant to help. Crimes against children
count triple. Routing is A* minimising length times (1 + lambda times risk to
the 1.5), and because every block multiplier is at least 1 the straight line
heuristic is admissible, making each route provably the cheapest rather than a
good guess. `validate.py` confirms that against Dijkstra.

There is no server behind any of it. The graph is built offline and packed into
a 5 MB binary, so the router runs in your browser and the site costs nothing to
host, which puts a copy within reach of any city. One bounding box in a config
file is the only Los Angeles specific thing here, and Chicago, Seattle, Toronto
and London publish compatible data. The project touches SDG 11 on safe
transport for children, SDG 4 on safe access to education, SDG 16 on violence
against children, and SDG 10, since the students carrying this risk are the
ones without a car or a ride. The limits are stated in the app itself:
reporting rates vary, locations are rounded to protect victims, and the data
stops in December 2024. It is a second opinion about a walk, not a promise
about one. For a lot of students walking is the only transport they have, and
we made it safer.

---

## Video link

`fill in, and check sharing is set to anyone with the link`

## Code link

https://github.com/safe-routes-la/safe-routes-la.github.io

## Parental consent

Yes
