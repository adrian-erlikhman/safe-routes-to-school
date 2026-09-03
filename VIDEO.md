# Presentation script for Adrian and Michael

Two speakers, about 3 minutes. Every rubric category is covered and marked in
the margin so you can check nothing is missing before you upload.

Rubric coverage: creativity (25), complexity (15), potential impact (20),
feasibility (10), user interface (20), presentation (10).

## Before you record

Open https://safe-routes-la.github.io and let the graph load, then hard refresh
with Ctrl+Shift+R so you are not running a cached version. Record at 1920x1080
with the sidebar visible. One take if you can manage it.

Set up two trips in advance so you are not typing during the demo:

- Trip A, walking: a school with a start point about 1.5 km away.
- Trip B, transit: something 8 km or more out, for example a start near
  Normandie and Exposition going to LACES. That is where the bus wins by a mile.

Whoever is not speaking should stay silent rather than adding "yeah" or "right".
Hand off cleanly on the marked lines.

---

## 0:00 to 0:25, the problem
**Adrian** / on screen: the Method tab, 1,026 filling the panel

> Between 2020 and 2024, one thousand and twenty-six kids between ten and
> eighteen were robbed on the streets of Los Angeles during school commute
> hours. That is fifty-six percent of every robbery of a kid that age, inside
> about five hours of the day.
>
> Those five hours are the walk to school and the walk home. My friends are in
> that number. That is why we built this.

Stop there. Do not oversell it.

---

## 0:25 to 0:45, why nobody has fixed it
**Michael**

> Every map app will give that kid the shortest way to school. Not one of them
> will give them the safest way.
>
> The federal Safe Routes to School program has existed since 1971, and it is
> almost entirely about cars. Crosswalks, speed bumps, crossing guards. Ask an
> LA teenager what actually scares them walking home and they will not say
> traffic.

*(covers: potential impact, the prompt)*

---

## 0:45 to 1:35, the walking demo
**Adrian** / do this live, trip A

> Pick a school. Type an address, no dropping pins on a map you do not
> recognise. And it gives me three routes instead of one, because there is no
> single right answer about how much detour is worth it.

Click through the three cards so the map line changes.

> Then it explains itself, which is the part I care about. It does not just draw
> a green line. It says: skips five hundred and fifty metres of South Fairfax
> Avenue, which scores sixty-five at this hour, goes along Venice Boulevard
> instead at twenty, costs you three minutes, and total exposure drops fifty
> percent.
>
> That is an argument you can check, not a suggestion you have to trust.

Scroll to the hour comparison.

> Same path at every hour of the day, because risk is not a property of a place
> on its own. It is a property of a place at an hour.

Open the street by street list.

> And it names every street, so you can actually follow it while you walk.

*(covers: user interface, creativity)*

---

## 1:35 to 2:10, the transit demo
**Michael** / switch to Bus or rail, trip B

> Walking is not always the answer, so we added buses and rail from LA Metro's
> published schedule data.
>
> This is the interesting part. Minutes you spend on a bus are minutes you are
> not on the street at all. So for this trip, walking takes a hundred and
> eighteen minutes and covers nine kilometres of sidewalk. Route 206 changing to
> Route 33 takes forty minutes, and only seven hundred and fifty metres of it
> happens on foot. Exposure drops eighty percent.
>
> Faster and safer, which almost never happens.

Point at the wait figure.

> And we are honest about waiting. Standing at a stop is exposure without
> progress, so a minute of waiting is charged like eighty metres of walking on
> that block. A stop on a bad corner is not a safe place to spend eight minutes,
> and the model should not pretend it is.

*(covers: creativity, complexity, the prompt)*

---

## 2:10 to 2:30, the school report
**Adrian** / School tab, run the report

> One route only helps one student. So this scores all sixteen directions a
> student might walk in from.
>
> Approaching this school from the south southeast means two and a half times
> the exposure of coming in from the east northeast. That is a sentence a
> principal can act on. It tells them where to put the crossing guard.

*(covers: potential impact, feasibility)*

---

## 2:30 to 2:50, how it works
**Michael** / Method tab, then a quick cut to validate.py showing PASS

> Underneath this is eighty-five thousand real violent crime records, a hundred
> and twenty-eight thousand streetlights, five thousand transit stops, and four
> hundred and thirty-one thousand blocks of Los Angeles, every one scored.
>
> The filtering mattered more than the maths. Out of about a million records we
> keep only crimes that threaten someone walking, and only the ones in public
> space. That drops eighty-one thousand indoor incidents. Domestic violence is
> serious, and it is also not a hazard of walking past a building. Leaving it in
> would have labelled ordinary residential neighbourhoods as dangerous, and that
> does real harm to the neighbourhoods we are trying to help.
>
> Crimes against children count triple, because a crime against a thirteen year
> old tells you more about the risk to a thirteen year old.
>
> The routing is A-star. Because every block multiplier is at least one,
> straight line distance never overestimates the remaining cost, so the
> heuristic is admissible and the route is provably the cheapest one rather than
> a good guess. We check that against Dijkstra and the costs come out identical.

*(covers: complexity)*

---

## 2:50 to 3:05, scale and close
**Adrian**

> There is no server. The whole thing runs in your browser, so it deploys as
> static files and costs nothing to host. Any city can run its own copy for
> free.
>
> And one bounding box in a config file is the only Los Angeles specific thing
> in it. Chicago, New York, Seattle, Toronto, London all publish the same kind
> of open data. Pointing this somewhere else is configuration, not a rewrite.
>
> It touches four UN development goals: safe cities, quality education, ending
> violence against children, and reduced inequality, because the kids carrying
> this risk are the ones without a car or a ride.
>
> Walking is the most basic form of transportation there is, and for a lot of
> students it is the only one they have. This makes it safer.

*(covers: feasibility, potential impact, two or more SDGs, global scale)*

---

## Rubric checklist

Run through this before uploading.

| Category | Where it lands |
|---|---|
| Creativity (25) | Crime-weighted routing, juvenile weighting, riding as risk avoidance, the school report |
| Complexity (15) | A* with a proven admissible heuristic, kernel density, transit with transfers, custom binary format |
| Potential impact (20) | The 1,026 figure, four named SDGs, the school report, global scale stated explicitly |
| Feasibility (10) | Live public URL, no backend, free hosting, all public data |
| User interface (20) | Address entry, three route cards, plain-language explanation, street list, hour comparison |
| Presentation (10) | Both speakers, live demo of walking and transit, limitations acknowledged |

If you are over time, cut the waiting explanation at 1:35 and the SDG list at
2:50 down to "four UN development goals". Do not cut the demo.

Say the limitations out loud if you have eight spare seconds. The Method tab
lists them, and judges trust a project more when it tells them what it cannot
do.
