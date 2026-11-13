"""What is visible in the night sky, computed (no LLM, no web): the data behind the free sky calendar and the sky CTAs.

  python tools/sky.py window [--start YYYY-MM-DD] [--days 30] [--out FILE]   # JSON for the next N nights
  python tools/sky.py tonight [--date YYYY-MM-DD]                            # the lines of one night (text)
  python tools/sky.py calendar [--days 75]      # refresh config/sky-calendar.json (events for the sky_tonight Shorts)

Everything is computed with PyEphem (the XEphem/libastro engine, VSOP87 planets) for an observer at 40° north,
the latitude of Madrid, New York and Beijing; the shower peaks come from the solar longitudes of the IMO Meteor
Shower Calendar (https://www.imo.net/resources/calendar/), their rates are the IMO zenithal hourly rates.
Dates are UTC: for a viewer they can shift by one day, so the texts say "around".
Why this exists (sales review 13/11/2026): the product is a stargazing guide, the content was space trivia. A viewer
who is told what to look at tonight is the viewer who buys a guide to the sky.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime, timedelta, timezone

import ephem

LAT = "40"
PLANETS = [("Mercury", ephem.Mercury), ("Venus", ephem.Venus), ("Mars", ephem.Mars), ("Jupiter", ephem.Jupiter),
           ("Saturn", ephem.Saturn)]
# name, solar longitude of the peak (J2000, degrees), zenithal hourly rate, parent body: IMO Meteor Shower Calendar
SHOWERS = [("Quadrantids", 283.15, 80, "asteroid 2003 EH1"), ("Lyrids", 32.32, 18, "Comet Thatcher"),
           ("Eta Aquariids", 45.5, 50, "Comet Halley"), ("Perseids", 140.0, 100, "Comet Swift-Tuttle"),
           ("Orionids", 208.0, 20, "Comet Halley"), ("Leonids", 235.27, 15, "Comet Tempel-Tuttle"),
           ("Geminids", 262.2, 150, "asteroid 3200 Phaethon"), ("Ursids", 270.7, 10, "Comet Tuttle")]
SUPERMOON_KM = 362_000   # a full Moon closer than this is called a supermoon here (mean distance: 384,400 km)
AU_KM = 149_597_870.7
COMPASS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]


def dt(d) -> datetime:
    return ephem.Date(d).datetime().replace(tzinfo=timezone.utc)


def sun_lon(t) -> float:
    """Ecliptic longitude of the Sun, J2000, degrees."""
    s = ephem.Sun(t)
    eq = ephem.Equatorial(s.a_ra, s.a_dec, epoch=ephem.J2000)
    return math.degrees(ephem.Ecliptic(eq, epoch=ephem.J2000).lon) % 360


def shower_peak(lon: float, start: datetime) -> datetime:
    """First time after `start` when the Sun reaches the shower's solar longitude."""
    t = ephem.Date(start)
    diff = (lon - sun_lon(t)) % 360
    t = ephem.Date(t + diff / 360 * 365.2422)
    for _ in range(8):   # Newton steps: the Sun moves ~0.9856 degrees a day
        err = ((lon - sun_lon(t) + 180) % 360) - 180
        t = ephem.Date(t + err / 0.9856)
    return dt(t)


def observer(day: date) -> ephem.Observer:
    o = ephem.Observer()
    o.lat, o.lon, o.elevation, o.pressure = LAT, "0", 0, 0
    o.date = datetime(day.year, day.month, day.day, 12)
    return o


def planet_state(cls, day: date) -> dict:
    """Where the planet is 45 min after sunset and 45 min before sunrise, at 40° N."""
    o = observer(day)
    sun = ephem.Sun()
    sunset, sunrise = o.next_setting(sun), o.next_rising(sun)
    out = {}
    for key, t in (("evening", ephem.Date(sunset + 45 * ephem.minute)), ("morning", ephem.Date(sunrise - 45 * ephem.minute))):
        o.date = t
        p = cls(o)
        out[key] = {"alt": round(math.degrees(p.alt)), "dir": COMPASS[int((math.degrees(p.az) + 22.5) // 45) % 8]}
    o.date = datetime(day.year, day.month, day.day, 12)
    p = cls(o)
    elong = math.degrees(p.elong)
    eve, mor = out["evening"]["alt"] >= 8, out["morning"]["alt"] >= 8
    if abs(elong) >= 150:
        when = "all night"
    elif eve and (not mor or elong > 0):
        when = "evening"
    elif mor:
        when = "before dawn"
    elif abs(elong) < 15:
        when = "hidden in the Sun's glare"
    else:
        when = "too low to see well"
    at = out["evening"] if when in ("evening", "all night") else out["morning"]
    return {"when": when, "dir": at["dir"], "alt": at["alt"], "mag": round(p.mag, 1), "elong": round(elong),
            "constellation": ephem.constellation(p)[1]}


def planet_line(name: str, a: dict, b: dict) -> dict:
    def where(s):
        if s["when"] in ("hidden in the Sun's glare", "too low to see well"):
            return s["when"]
        h = "low" if s["alt"] < 15 else "high" if s["alt"] > 45 else "midway up"
        tail = "after sunset" if s["when"] != "before dawn" else "before sunrise"
        return f"{s['when']}, {h} in the {s['dir']} {tail}"
    text = where(a) if where(a) == where(b) else f"{where(a)}; by the end of the period: {where(b)}"
    return {"name": name, "text": text, "mag": a["mag"], "constellation": a["constellation"], "when": a["when"],
            "visible": a["when"] not in ("hidden in the Sun's glare", "too low to see well")}


def moon_events(start: datetime, days: int) -> list[dict]:
    end, ev = start + timedelta(days=days), []
    for label, fn in (("New Moon", ephem.next_new_moon), ("First quarter", ephem.next_first_quarter_moon),
                      ("Full Moon", ephem.next_full_moon), ("Last quarter", ephem.next_last_quarter_moon)):
        t = fn(start)
        while dt(t) < end:
            e = {"at": dt(t).isoformat(timespec="minutes"), "date": dt(t).date().isoformat(), "kind": "moon", "name": label}
            if label == "Full Moon":
                km = round(ephem.Moon(t).earth_distance * AU_KM, -2)
                e["distance_km"] = int(km)
                if km < SUPERMOON_KM:
                    e["name"] = "Full Moon (supermoon)"
            ev.append(e)
            t = fn(ephem.Date(t + 1))
    return ev


def pairings(start: datetime, days: int) -> list[dict]:
    """Moon close to a naked-eye planet (geocentric, under 6 degrees, Moon at least 25 degrees from the Sun)."""
    out = []
    for name, cls in PLANETS:
        best, prev = None, None
        for h in range(days * 24 + 1):
            t = ephem.Date(start + timedelta(hours=h))
            m, p, s = ephem.Moon(t), cls(t), ephem.Sun(t)
            sep = math.degrees(ephem.separation(m, p))
            if sep < 6 and (best is None or sep < best[0]):
                best = (sep, t, math.degrees(ephem.separation(m, s)), math.degrees(ephem.separation(p, s)), m.phase)
            if best and prev is not None and sep > 6 and prev <= 6:
                if best[2] >= 25 and best[3] >= 15:
                    d = dt(best[1])
                    out.append({"at": d.isoformat(timespec="minutes"), "date": d.date().isoformat(), "kind": "pairing",
                                "name": f"Moon near {name}", "planet": name, "separation_deg": round(best[0]),
                                "moon_lit_pct": round(best[4])})
                best = None
            prev = sep
    return out


def showers(start: datetime, days: int) -> list[dict]:
    out, end = [], start + timedelta(days=days)
    for name, lon, zhr, parent in SHOWERS:
        t = shower_peak(lon, start - timedelta(days=1))
        if start <= t < end:
            out.append({"at": t.isoformat(timespec="minutes"), "date": t.date().isoformat(), "kind": "meteors",
                        "name": f"{name} meteor shower peak", "shower": name, "zhr": zhr, "parent": parent,
                        "moon_lit_pct": round(ephem.Moon(ephem.Date(t)).phase)})
    return out


def seasons(start: datetime, days: int) -> list[dict]:
    out, end = [], start + timedelta(days=days)
    for label, fn in (("solstice", ephem.next_solstice), ("equinox", ephem.next_equinox)):
        t = dt(fn(start))
        if t < end:
            month = {12: "December", 6: "June", 3: "March", 9: "September"}[t.month]
            out.append({"at": t.isoformat(timespec="minutes"), "date": t.date().isoformat(), "kind": "season",
                        "name": f"{month} {label}"})
    return out


def window(start: date, days: int = 30) -> dict:
    s = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    last = start + timedelta(days=days - 1)
    planets = [planet_line(n, planet_state(c, start + timedelta(days=3)), planet_state(c, last - timedelta(days=3)))
               for n, c in PLANETS]
    events = sorted(moon_events(s, days) + pairings(s, days) + showers(s, days) + seasons(s, days), key=lambda e: e["at"])
    return {"start": start.isoformat(), "end": last.isoformat(), "days": days, "latitude": "40° N",
            "method": "Computed with PyEphem for 40° N. Meteor shower peaks and rates: IMO Meteor Shower Calendar. "
                      "Dates are UTC and can shift by one day where you live.",
            "planets": planets, "events": events}


def fmt_day(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.strftime('%b')} {d.day}"


def event_text(e: dict) -> str:
    """One plain sentence per event: used by the PDF and by the posts."""
    if e["kind"] == "meteors":
        moon = ("a dark sky, the Moon is out of the way" if e["moon_lit_pct"] < 35 else
                "a bright Moon will hide the faint ones" if e["moon_lit_pct"] > 65 else "some moonlight")
        return (f"{e['shower']} peak: up to {e['zhr']} meteors an hour under a perfect dark sky, debris of {e['parent']}. "
                f"Moon {e['moon_lit_pct']}% lit: {moon}. Best after midnight.")
    if e["kind"] == "pairing":
        return f"The Moon ({e['moon_lit_pct']}% lit) passes about {e['separation_deg']}° from {e['planet']}: the easiest way to find the planet."
    if e["kind"] == "moon" and "distance_km" in e:
        extra = " A supermoon: closer than usual, so slightly bigger and brighter." if "supermoon" in e["name"] else ""
        return f"Full Moon, {e['distance_km']:,} km away.{extra}"
    if e["kind"] == "moon":
        return {"New Moon": "New Moon: the darkest nights of the month, best for faint stars and the Milky Way.",
                "First quarter": "First quarter Moon: half lit in the evening, the best phase to see craters with binoculars.",
                "Last quarter": "Last quarter Moon: rises around midnight, evenings stay dark."}[e["name"]]
    if "solstice" in e["name"]:
        return f"{e['name']}: the longest night of the year in one hemisphere, the shortest in the other."
    return f"{e['name']}: day and night are almost equal everywhere."


def tonight(day: date) -> dict:
    """What to say about one night: the visible planets and the events within 2 days."""
    w = window(day, 3)
    planets = [planet_line(n, planet_state(c, day), planet_state(c, day)) for n, c in PLANETS]
    moon = ephem.Moon(datetime(day.year, day.month, day.day, 20))
    return {"date": day.isoformat(), "moon_lit_pct": round(moon.phase),
            "planets": [p for p in planets if p["visible"]], "events": w["events"]}


MONTH = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
         "November", "December"]


def calendar(start: date, days: int = 75) -> list[dict]:
    """Events worth a 'sky tonight' Short, for config/sky-calendar.json: showers, full Moons, the Moon next to a
    bright planet, solstices. The hint carries the date only: the writer takes every number from primary sources."""
    out = []
    for e in window(start, days)["events"]:
        d = date.fromisoformat(e["date"])
        when = f"{d.day} {MONTH[d.month - 1]} {d.year}"
        if e["kind"] == "meteors":
            hint = f"the {e['shower']} meteor shower peak around {when}, debris of {e['parent']}: when and where to look and how many to expect"
        elif e["kind"] == "moon" and e["name"].startswith("Full Moon"):
            hint = (f"the full Moon of {when}" + (", a supermoon: how much closer and bigger it really is" if "supermoon" in e["name"]
                    else ": why the Moon looks huge near the horizon and how far it really is"))
        elif e["kind"] == "pairing" and e["planet"] in ("Venus", "Jupiter", "Saturn", "Mars") and e["separation_deg"] <= 4:
            hint = (f"the Moon passing close to {e['planet']} around {when}: how to use the Moon to find the planet with "
                    f"your own eyes, and {e['planet']}'s real numbers")
        elif e["kind"] == "season":
            hint = f"the {e['name']} of {when}: why it happens and what changes in the sky"
        else:
            continue
        out.append({"date": e["date"], "name": e["name"].replace(" meteor shower", ""), "hint": hint, "computed": True})
    return out


def write_calendar(start: date, days: int):
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / "config" / "sky-calendar.json"
    cfg = json.loads(f.read_text("utf-8")) if f.exists() else {"events": []}
    new = calendar(start, days)
    days_new = {(e["date"], e["name"].split()[0]) for e in new}
    # hand-written events stay unless the computed list has the same event on the same day; old computed ones go
    keep = [e for e in cfg.get("events", []) if not e.get("computed") and e.get("date", "") >= start.isoformat()
            and (e["date"], e["name"].split()[0]) not in days_new
            and not any(abs((date.fromisoformat(e["date"]) - date.fromisoformat(n["date"])).days) <= 2
                        and e["name"].split()[0] == n["name"].split()[0] for n in new)]
    cfg["events"] = sorted(keep + new, key=lambda e: e["date"])
    f.write_text(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"sky calendar: {len(new)} computed + {len(keep)} hand-written events")


def main():
    a = sys.argv[1:]
    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a else default
    cmd = a[0] if a else "window"
    if cmd == "tonight":
        t = tonight(date.fromisoformat(opt("--date", date.today().isoformat())))
        print(f"{t['date']} · Moon {t['moon_lit_pct']}% lit")
        for p in t["planets"]:
            print(f"- {p['name']} (mag {p['mag']}, in {p['constellation']}): {p['text']}")
        for e in t["events"]:
            print(f"* {fmt_day(e['date'])}: {event_text(e)}")
        return
    if cmd == "calendar":
        return write_calendar(date.fromisoformat(opt("--start", date.today().isoformat())), int(opt("--days", "75")))
    w = window(date.fromisoformat(opt("--start", date.today().isoformat())), int(opt("--days", "30")))
    for e in w["events"]:
        e["text"] = event_text(e)
    s = json.dumps(w, indent=1, ensure_ascii=False)
    if opt("--out"):
        open(opt("--out"), "w", encoding="utf-8").write(s + "\n")
        print(f"sky window {w['start']} .. {w['end']}: {len(w['events'])} events, "
              f"{sum(p['visible'] for p in w['planets'])} planets visible -> {opt('--out')}")
    else:
        print(s)


if __name__ == "__main__":
    main()
