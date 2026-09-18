"""Sunrise, sunset and the dark fraction of a time bucket, for the study area.

`build_graph.py` gives every block the same streetlight credit in all three
time windows. A lamp cannot reduce risk at 11 a.m., so the credit has to be
scaled by how much of a window is actually dark -- which means knowing when the
sun is down over Los Angeles across a school year.

NOAA's solar position algorithm, which is accurate to well under a minute at
this latitude and needs no data files or dependencies. US daylight saving is
applied by rule (second Sunday in March to first Sunday in November, fixed
since the Energy Policy Act of 2005) rather than from the tz database, so this
does not depend on tzdata being installed.
"""
import datetime as dt
import math

import numpy as np

# Darkness is taken at the end of civil twilight, sun 6 degrees below the
# horizon, rather than at sunset. That is the standard threshold for "artificial
# light is now doing the work", and it is roughly when LA's photocells switch
# the street lighting on. Using sunset itself would credit lamps during the
# half hour when there is still usable daylight.
CIVIL_TWILIGHT_DEG = 96.0

# LAUSD's instructional year: mid-August to mid-June. Averaging over the whole
# calendar year would fold in July, when the walk to school does not happen and
# the evenings are at their longest -- which is exactly the bias this is
# correcting for.
SCHOOL_YEAR_START = (8, 15)
SCHOOL_YEAR_END = (6, 15)

STANDARD_OFFSET_H = -8.0        # Pacific Standard Time


def _dst(d):
    """True if US daylight saving is in force on date `d`."""
    def nth_sunday(year, month, n):
        first = dt.date(year, month, 1)
        return first + dt.timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))
    return nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1)


def _solar_events(d, lat, lon, zenith_deg):
    """Local-clock hours of (dawn, dusk) at `zenith_deg`, or None in polar cases."""
    doy = d.timetuple().tm_yday
    g = 2.0 * math.pi / 365.0 * (doy - 1 + 0.5)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g)
                       - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                       - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    phi = math.radians(lat)
    cos_ha = (math.cos(math.radians(zenith_deg))
              / (math.cos(phi) * math.cos(decl)) - math.tan(phi) * math.tan(decl))
    if not -1.0 <= cos_ha <= 1.0:
        return None
    ha = math.degrees(math.acos(cos_ha))
    offset = STANDARD_OFFSET_H + (1.0 if _dst(d) else 0.0)
    dawn = (720.0 - 4.0 * (lon + ha) - eqtime) / 60.0 + offset
    dusk = (720.0 - 4.0 * (lon - ha) - eqtime) / 60.0 + offset
    return dawn % 24.0, dusk % 24.0


def school_days(year=2024):
    """Every date in one instructional year, August through June."""
    start = dt.date(year - 1, *SCHOOL_YEAR_START)
    end = dt.date(year, *SCHOOL_YEAR_END)
    n = (end - start).days + 1
    return [start + dt.timedelta(days=i) for i in range(n)]


def dark_hours(d, lat, lon, zenith_deg=CIVIL_TWILIGHT_DEG):
    """Boolean over the 24 clock hours: is hour h mostly dark on date `d`?

    An hour is called dark when its midpoint is dark, which is the same
    resolution the crime data has -- LAPD records an incident's hour, not its
    minute, so a finer answer would be spurious.
    """
    ev = _solar_events(d, lat, lon, zenith_deg)
    mid = np.arange(24) + 0.5
    if ev is None:
        return np.ones(24, dtype=bool)
    dawn, dusk = ev
    return ~((mid >= dawn) & (mid < dusk))


def dark_fraction(hours, lat, lon, hour_weights=None, year=2024):
    """Share of a bucket's exposure that happens after dark.

    `hours` is the bucket's clock hours. `hour_weights` optionally weights them
    by how many incidents actually fall in each -- which is the right measure,
    because the credit scales a risk score and risk is where the incidents are,
    not where the clock is. Unweighted it assumes incidents spread evenly
    across the window.
    """
    hours = np.asarray(list(hours), dtype=int)
    w = (np.ones(len(hours)) if hour_weights is None
         else np.asarray([hour_weights[h] for h in hours], dtype=float))
    if w.sum() <= 0:
        w = np.ones(len(hours))
    days = school_days(year)
    acc = np.zeros(len(hours))
    for d in days:
        acc += dark_hours(d, lat, lon)[hours]
    return float((acc / len(days) * w).sum() / w.sum())


if __name__ == "__main__":
    import config as C
    lat = (C.BBOX["south"] + C.BBOX["north"]) / 2
    lon = (C.BBOX["west"] + C.BBOX["east"]) / 2
    print(f"lat {lat:.3f} lon {lon:.3f}  (centre of the study area)")
    for label, d in [("winter solstice", dt.date(2024, 12, 21)),
                     ("summer solstice", dt.date(2024, 6, 21)),
                     ("equinox", dt.date(2024, 3, 20))]:
        rise, set_ = _solar_events(d, lat, lon, 90.833)
        dawn, dusk = _solar_events(d, lat, lon, CIVIL_TWILIGHT_DEG)
        f = lambda h: f"{int(h):02d}:{int(round((h % 1) * 60)):02d}"
        print(f"  {label:16} sunrise {f(rise)}  sunset {f(set_)}   "
              f"civil twilight {f(dawn)} - {f(dusk)}")
