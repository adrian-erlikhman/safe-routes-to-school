# YCS Impact Award: answers

Form: https://forms.gle/wPg5yoMKnZKYvHnS6 (from the 3 September 2026 email).
The award is monthly and tied to the month of the competition, so this entry is
for **August 2026**. Every number below is either in the repository or in the
YCS results email; nothing is estimated.

If you have real usage numbers (GitHub Insights, then Traffic, gives unique
visitors for the last 14 days; a school or a class you showed it to), add one
sentence to the impact answer. It is complete without them.

---

## What are some new features or improvements your project has had since the competition? (100 word min)

Since the competition we have kept shipping. The whole interface now switches
to Spanish with one tap, covering the route explanations, the bus directions,
the school report and the printed card, because most LAUSD families speak
Spanish at home and a safety tool a parent cannot read is not a safety tool.
Any route prints as a one-page walking card, the streets in order with each
block's score, for a student who does not carry a phone. Cross streets like
"Hauser & Venice", which is how people in Los Angeles actually say where they
are, are now resolved on the device from the street graph itself, instantly and
offline, with a second geocoder as backup for full addresses. A "use my
location" button starts a route from wherever the student is standing. A school
can paste a two-line snippet into its own website, or send a link, that opens
the planner with that school already chosen. The site installs to a home screen
and keeps working with no data connection after the first visit, since the 5 MB
scored graph and the router live on the device. Every route carries a
report-a-problem link, and we removed our last CDN dependency so nothing about
the page relies on a third party staying up.

## What real-world impact has your project achieved so far? Specify any metrics. (150 word min)

The clearest impact so far is what the tool can show, and that it is live,
free and usable by anyone in Los Angeles today at safe-routes-la.github.io. It
scores 431,599 blocks of central Los Angeles at three times of day from 85,634
violent incidents, 128,534 streetlights and 5,395 transit stops, and covers 668
public schools, each with its own link and a sixteen-direction approach report
that a principal can act on. On six random evening trips the validation script
reduced exposure on all six, by 19% to 59%, for detours ranging from under a
minute to 21 minutes. The worked example, a walk to LACES in Mid City, halves
exposure for three extra minutes; a nine kilometre trip from Exposition Park by
bus cuts exposure 65% and is faster than walking. The per-hour analysis
surfaced a finding nobody had put in front of us: the afternoon walk home is,
hour for hour, more dangerous than after dark, 4,246 incidents per hour against
3,804, which is now the strongest argument we have when we talk to a school.
The judges placed it third in Code for Transportation and cited its potential
for real-world impact. Since then it has become usable by the families it is
for: in Spanish, on a phone with no data plan, from a cross street rather than
a street address, and on paper.

## What are your next steps for expanding on the impact of your project? (150 word min)

Three directions. First, into schools rather than onto screens. The school
report scores all sixteen approaches to a campus and names the worst one; we
plan to run it for every LAUSD high school in the study area and hand each
principal a one-page result showing where a crossing guard, a lighting request
or a walking group would do the most good, starting with LACES and the campuses
around Mid City and Koreatown. Second, families. The Spanish version and the
printable cards exist for households without a phone or a data plan, so we want
to distribute cards through counsellors and parent centres at the start of the
spring semester and measure whether they get used. Third, make it someone
else's too. The only Los Angeles specific thing in the pipeline is one bounding
box, and Chicago, New York, Seattle, Toronto and London publish compatible
data; we will stand up a second city as proof, document the process, and invite
student teams elsewhere to run their own. Alongside that: refresh the data once
LAPD's new records feed is stable, add a privacy-respecting count of routes
planned so we can report real usage instead of estimates, and bring the
per-hour finding to LADOT's Safe Routes to School program, which today plans
almost entirely around traffic.

## How has YCS helped you grow your skills and what have you learned? (100 word min)

YCS gave us a deadline and a rubric, and both changed how we build.
Technically we went further than in any class: A* with a provable admissibility
argument, kernel density estimation over a street graph, LA Metro's GTFS feed
reduced to something a browser can plan with, a hand-packed binary format that
turned 40 MB of JSON into 5 MB, and since then service workers and a full
translation layer. The bigger lesson was judgement. The most important
decisions in this project were about what to throw away, and explaining why
dropping 81,000 indoor incidents was the right call taught us that a model is
an argument you have to be able to defend out loud. The three-minute video
forced us to say what the project is in plain words, which is harder than the
code. And placing third, then being asked to show impact, pushed us from a
project that works to one that people can actually use: a version in the
language families speak, a card for a student without a phone, a page a school
can embed.

## Files to upload (up to 10, 10 MB each)

Ready in `docs/screenshots/`, numbered in upload order. They were captured
from the site with the map's own street layer (no tile labels); if you prefer
the labelled CARTO background, retake them on the live site.

1. `01-spanish-route.png`: the worked example in Spanish, three options and the reasoning.
2. `02-cross-streets.png`: "Pico / La Brea" resolving on the device.
3. `03-bus-or-rail.png`: bus options with the walk for comparison.
4. `04-school-report.png`: sixteen approaches to LACES, ranked.
5. `05-walking-card.png`: the printed walking card.
6. `06-phone.png`: the phone layout, Spanish.
7. `07-school-embed.png`: the school-preset page a school website embeds.
8. `08-offline.png`: the site running with no connection.
9. The Code for Transportation results email or the certificate.
10. The competition video, or a link to it in the comments box.

## Any additional comments?

Live site: https://safe-routes-la.github.io (Spanish:
https://safe-routes-la.github.io/?lang=es). Code:
https://github.com/safe-routes-la/safe-routes-la.github.io. Team: Adrian
Erlikhman, Ryan Erlikhman, Michael Tarekegn. We would be glad to be included in
the winner spotlight and to have the project featured on the YCS site.
