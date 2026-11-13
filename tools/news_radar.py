"""News radar: which space stories people are reading TODAY, from free public feeds (no key, no paid scraper).

  python tools/news_radar.py [niche] [--hours 48]      -> research/<niche>/radar-<date>.json and .md

Why (owner 13/11/2026: "ottimizza come cercare notizie, scraping gratuito, trend virali"): the Shorts took the NEWEST
item of the agencies' feeds, whatever it was. The agencies publish a lot that nobody talks about. The radar measures
the heat of a story (how many outlets cover it, how high it is on Reddit and Hacker News, whether people look it up
on Wikipedia and Google) so the writer can pick the story of the day and then tell it from its primary source.

Sources, all public and free; one that fails is skipped and listed under "skipped":
- Google News RSS search (one feed per query of research/niches/<niche>.json "radar_queries"): each entry is one
  outlet covering a story; the number of different outlets on the same story is the main signal.
- Reddit: public RSS of the day's top posts of the niche subreddits (rank = signal).
- Hacker News: Algolia search API, stories of the last hours with their points.
- Wikipedia: official Pageviews API, yesterday's most-read articles that are about space, with the jump over the
  day before.
- Google Trends: the public "trending now" RSS (US and GB), space terms only.
- Agencies (NASA, ESA, ESO, NOIRLab...): the same feeds the Shorts are written from; a story with an agency page has a
  primary source ready ("primary").
Stories that a viewer can go out and SEE (meteor shower, aurora, comet, eclipse, supermoon, planets) are flagged
"sky": that is the public that buys a stargazing guide (sales review 13/11/2026), so they get a bonus.
Nothing here is copied into a video: titles are used to choose the topic, the script comes from the primary source.
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "cosmos-research/1.0 (by cosmosinnumbers; news radar)"}
QUERIES = ["NASA", "astronomy discovery", "space telescope", "night sky tonight", "meteor shower OR aurora OR comet",
           "asteroid", "Mars OR Moon mission", "James Webb"]
SUBS = ["space", "astronomy", "nasa", "spaceporn"]
AGENCY_FEEDS = ["https://www.nasa.gov/news-release/feed/", "https://www.nasa.gov/feed/", "https://science.nasa.gov/feed/",
                "https://www.jpl.nasa.gov/feeds/news/", "https://www.esa.int/rssfeed/Our_Activities/Space_Science",
                "https://esawebb.org/news/feed/", "https://esahubble.org/news/feed/",
                "https://www.eso.org/public/news/feed/", "https://noirlab.edu/public/news/feed/"]
PRIMARY = re.compile(r"nasa\.gov|esa\.int|esawebb\.org|esahubble\.org|eso\.org|noirlab\.edu|jaxa\.jp|stsci\.edu|"
                     r"nature\.com|science\.org|arxiv\.org|iopscience|aanda\.org", re.I)
SPACE = re.compile(r"\b(nasa|esa|spacex|space|astronom|telescope|webb|jwst|hubble|galax|nebula|planet|exoplanet|"
                   r"asteroid|comet|meteor|eclipse|aurora|northern lights|supermoon|moon|lunar|mars|martian|jupiter|"
                   r"saturn|venus|mercury|uranus|neptune|pluto|solar|sun'?s|star|stars|supernova|black hole|quasar|"
                   r"milky way|cosmic|cosmos|universe|orbit|rocket|launch|artemis|starship|voyager|iss|astronaut|"
                   r"interstellar|geminid|perseid|leonid|orionid|quadrantid)", re.I)
OFF = re.compile(r"\b(horoscope|astrolog|zodiac sign|stock|shares|nasdaq|earnings|movie|trailer|netflix|game|nba|nfl|"
                 r"star wars|pop star|rock star|all-star|celebrity|budget cuts?|layoffs?|lawsuit|senate|congress|election|"
                 r"president|military|pentagon|missile|war\b)", re.I)
SKY = re.compile(r"tonight|this week|meteor|shooting stars?|aurora|northern lights|comet|eclipse|supermoon|full moon|"
                 r"blood moon|conjunction|planet parade|planets? align|visible|naked eye|night sky|how to (see|watch)|"
                 r"where to (see|look)|geminid|perseid|leonid|orionid|quadrantid|lyrid", re.I)
STOP = set("the a an and or of to in is it this that for on with you your we are was be at as by from not have has but "
           "they what so if can just do how its about all more one new says said after over into than then will could "
           "may might been were their there these those here when where which while who why first just now out up "
           "scientists researchers astronomers study report video photos image images watch live update news today "
           "space nasa".split())


def keys(title: str) -> set[str]:
    """The words that identify a story: lowercase, 4+ letters (or a number), no filler."""
    t = re.sub(r"\s[-|–]\s[^-|–]{2,40}$", "", title)   # "Headline - Outlet" of Google News
    words = [w for w in re.findall(r"[a-z]{4,}|\d[\d.,]*\d|\d", t.lower().replace("’", "'")) if w not in STOP]
    return {w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w for w in words}   # geminids = geminid


def get(url: str, **kw):
    r = requests.get(url, headers=UA, timeout=30, **kw)
    r.raise_for_status()
    return r


def rss(text: str):
    """(title, link, date, source) of an RSS or Atom feed."""
    root = ET.fromstring(text)
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        f = {c.tag.split("}")[-1]: c for c in it}
        title = html.unescape((f["title"].text or "") if "title" in f else "").strip()
        link = (f["link"].text or f["link"].get("href") or "") if "link" in f else ""
        raw = next((f[k].text for k in ("pubDate", "published", "updated", "date") if k in f and f[k].text), None)
        try:
            d = parsedate_to_datetime(raw) if raw and "," in raw else datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError, AttributeError):
            d = None
        if d and d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        src = (f["source"].text or "") if "source" in f else ""
        if title:
            yield title, link.strip(), d, src.strip()


def google_news(queries: list[str], hours: int) -> list[dict]:
    out = []
    for q in queries:
        r = get("https://news.google.com/rss/search", params={"q": f"{q} when:{max(1, hours // 24)}d", "hl": "en-US",
                                                             "gl": "US", "ceid": "US:en"})
        for title, link, d, src in rss(r.text):
            outlet = src or (title.rsplit(" - ", 1)[-1] if " - " in title else "")
            out.append({"src": "news", "title": re.sub(r"\s-\s[^-]{2,40}$", "", title), "url": link, "date": d, "outlet": outlet})
        time.sleep(1.5)
    return out


def reddit(subs: list[str]) -> list[dict]:
    out = []
    for sub in subs:
        for wait in (6, 25):   # Reddit answers 429 to fast reads: one retry after a longer pause
            r = requests.get(f"https://www.reddit.com/r/{sub}/top/.rss", params={"t": "day", "limit": 10}, headers=UA, timeout=30)
            time.sleep(wait)
            if r.status_code != 429:
                break
        if not r.ok:
            continue
        for rank, (title, link, d, _) in enumerate(rss(r.text), 1):
            out.append({"src": "reddit", "title": title, "url": link, "date": d, "outlet": f"r/{sub}", "rank": rank})
    if not out:
        raise RuntimeError("no subreddit readable")
    return out


def hacker_news(hours: int) -> list[dict]:
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    out, seen = [], set()
    for q in ("nasa", "space telescope", "astronomy", "asteroid", "mars"):
        j = get("https://hn.algolia.com/api/v1/search", params={"query": q, "tags": "story", "hitsPerPage": 20,
                "numericFilters": f"created_at_i>{since},points>15"}).json()
        for h in j.get("hits", []):
            if h["objectID"] in seen:
                continue
            seen.add(h["objectID"])
            out.append({"src": "hn", "title": h.get("title") or "", "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                        "date": datetime.fromtimestamp(h["created_at_i"], timezone.utc), "outlet": "Hacker News", "points": h.get("points") or 0})
    return out


def wikipedia(today: datetime) -> list[dict]:
    def top(day):
        j = get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{day:%Y/%m/%d}").json()
        return {a["article"].replace("_", " "): a["views"] for a in j["items"][0]["articles"]}
    last = None
    for back in (1, 2, 3):   # yesterday's file appears a few hours into the day
        try:
            last, day = top(today - timedelta(days=back)), today - timedelta(days=back)
            break
        except requests.RequestException:
            continue
    if last is None:
        raise RuntimeError("no pageviews file for the last 3 days")
    try:
        prev = top(day - timedelta(days=1))
    except requests.RequestException:
        prev = {}
    out = []
    for art, views in last.items():
        if ":" in art or art in ("Main Page",) or not SPACE.search(art) or OFF.search(art):
            continue
        out.append({"src": "wiki", "title": art, "url": "https://en.wikipedia.org/wiki/" + art.replace(" ", "_"), "date": day,
                    "outlet": "Wikipedia", "views": views, "jump": round(views / prev[art], 2) if prev.get(art) else None})
    return out


def google_trends() -> list[dict]:
    out = []
    for geo in ("US", "GB"):
        r = get("https://trends.google.com/trending/rss", params={"geo": geo})
        for title, link, d, _ in rss(r.text):
            out.append({"src": "trends", "title": title, "url": link, "date": d, "outlet": f"Google Trends {geo}"})
    return out


def agencies() -> list[dict]:
    out = []
    for url in AGENCY_FEEDS:
        try:
            for title, link, d, _ in rss(get(url).text):
                out.append({"src": "agency", "title": title, "url": link, "date": d, "outlet": re.sub(r"^https?://(www\.)?([^/]+)/.*", r"\2", url)})
        except Exception as e:  # noqa: BLE001
            print("  agency feed failed", url, type(e).__name__)
        time.sleep(1)
    if not out:
        raise RuntimeError("no agency feed readable")
    return out


def cluster(items: list[dict]) -> list[dict]:
    """Greedy grouping of the items that tell the same story: 3 shared key words, or 2 when the titles are short."""
    stories: list[dict] = []
    for it in sorted(items, key=lambda i: {"news": 0, "agency": 1, "reddit": 2, "hn": 3, "wiki": 4, "trends": 5}[i["src"]]):
        k = keys(it["title"])
        if not k:
            continue
        best, score = None, 0
        for s in stories:
            common = len(k & s["keys"])
            need = 1 if it["src"] in ("wiki", "trends") and len(k) <= 2 else 2 if min(len(k), len(s["keys"])) <= 4 else 3
            if common >= need and common > score:
                best, score = s, common
        if best:
            best["items"].append(it)
            if it["src"] in ("news", "agency"):
                best["keys"] |= k if len(best["keys"]) < 14 else set()
        elif it["src"] not in ("wiki", "trends") or SPACE.search(it["title"]):
            stories.append({"keys": set(k), "items": [it]})
    return stories


def heat(s: dict) -> float:
    """Outlets on the story + social position + people looking it up; a sky event anyone can see gets a bonus."""
    it = s["items"]
    outlets = {i["outlet"].lower() for i in it if i["src"] == "news" and i["outlet"]}
    h = float(len(outlets))
    h += sum(max(0.0, 3.0 - 0.3 * (i.get("rank", 10) - 1)) for i in it if i["src"] == "reddit")
    h += sum(min(4.0, i.get("points", 0) / 50) for i in it if i["src"] == "hn")
    h += sum(2.0 + min(3.0, (i.get("jump") or 1) - 1) for i in it if i["src"] == "wiki")
    h += 3.0 * sum(1 for i in it if i["src"] == "trends")
    if any(i["src"] == "agency" for i in it):
        h += 1.0
    return round(h * (1.3 if s["sky"] else 1.0), 2)


def build(cfg: dict, hours: int = 48, now: datetime | None = None, fetched: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    jobs = {"news": lambda: google_news(cfg.get("radar_queries") or QUERIES, hours),
            "reddit": lambda: reddit(cfg.get("radar_subreddits") or SUBS), "hn": lambda: hacker_news(hours),
            "wiki": lambda: wikipedia(now), "trends": google_trends, "agency": agencies}
    items, skipped, counts = [], {}, {}
    for name, job in jobs.items():
        try:
            got = fetched[name] if fetched is not None else job()
        except Exception as e:  # noqa: BLE001
            skipped[name] = f"{type(e).__name__}: {str(e)[:120]}"
            print("  skipped", name, skipped[name])
            continue
        got = [i for i in got if (i["src"] in ("wiki", "trends") or SPACE.search(i["title"])) and not OFF.search(i["title"])
               and (i["date"] is None or now - i["date"] <= timedelta(hours=hours if i["src"] != "agency" else 7 * 24))]
        counts[name] = len(got)
        items += got
    stories = []
    for s in cluster(items):
        its = s["items"]
        if not any(i["src"] in ("news", "agency", "reddit", "hn") for i in its):
            continue   # a Wikipedia or Trends term alone is not a story
        s["sky"] = any(SKY.search(i["title"]) for i in its)
        head = next((i for i in its if i["src"] == "agency"), None) or next((i for i in its if i["src"] == "news"), its[0])
        primary = next((i["url"] for i in its if i["src"] == "agency"), None) or next((i["url"] for i in its if PRIMARY.search(i["url"])), None)
        dates = [i["date"] for i in its if i["date"]]
        stories.append({"title": head["title"], "heat": heat(s), "sky": s["sky"], "primary": primary,
                        "outlets": len({i["outlet"].lower() for i in its if i["src"] == "news"}),
                        "signals": sorted({i["src"] for i in its}), "keywords": sorted(s["keys"])[:14],
                        "newest": max(dates).isoformat(timespec="minutes") if dates else None,
                        "links": list(dict.fromkeys([primary or head["url"], head["url"], *[i["url"] for i in its]]))[:4]})
    stories.sort(key=lambda s: -s["heat"])
    return {"date": now.date().isoformat(), "made_at": now.isoformat(timespec="minutes"), "hours": hours,
            "sources": counts, "skipped": skipped, "stories": stories[:25]}


def report(r: dict, niche: str) -> str:
    L = [f"# Radar notizie {niche}: {r['date']}", "",
         f"Storie di spazio più lette nelle ultime {r['hours']} ore, da fonti pubbliche gratuite. Calore = testate che "
         "ne parlano + posizione su Reddit e Hacker News + ricerche su Wikipedia e Google. 🔭 = si può vedere a occhio "
         "nudo (pubblico da guida al cielo). 📄 = c'è già una pagina di un'agenzia come fonte primaria.", "",
         "Fonti lette: " + ", ".join(f"{k} {v}" for k, v in r["sources"].items()) +
         ("" if not r["skipped"] else " · saltate: " + ", ".join(r["skipped"])), "",
         "| Calore | Storia | Testate | Segnali |", "|---|---|---|---|"]
    for s in r["stories"][:15]:
        L.append(f"| {s['heat']} | {'🔭 ' if s['sky'] else ''}{'📄 ' if s['primary'] else ''}[{s['title'][:95]}]({s['links'][0]}) | "
                 f"{s['outlets']} | {', '.join(s['signals'])} |")
    return "\n".join(L) + "\n"


# ---------- read side: used by the writers ----------
def latest(niche: str = "cosmos", max_age_hours: int = 36) -> dict | None:
    files = sorted((ROOT / "research" / niche).glob("radar-*.json"))
    if not files:
        return None
    try:
        r = json.loads(files[-1].read_text("utf-8"))
        age = datetime.now(timezone.utc) - datetime.fromisoformat(r["made_at"])
    except (ValueError, KeyError):
        return None
    return r if age <= timedelta(hours=max_age_hours) else None


def hot_block(niche: str = "cosmos", n: int = 6) -> str:
    """Text for the writer's prompt: today's hottest stories, the ones with a primary source first."""
    r = latest(niche)
    if not r or not r.get("stories"):
        return ""
    top = [s for s in r["stories"] if s["heat"] >= 3][:n]
    if not top:
        return ""
    lines = [f"- {s['title'][:110]} (heat {s['heat']}, {s['outlets']} outlets"
             + (", visible in the sky" if s["sky"] else "") + (f", primary source: {s['primary']}" if s["primary"] else "") + ")"
             for s in top]
    return ("WHAT PEOPLE ARE READING TODAY (news radar, hottest first). Prefer one of these stories IF you can tell it "
            "from a primary source with measured numbers; never use an outlet's wording or numbers that are not in the "
            "primary source:\n" + "\n".join(lines))


def item_heat(title: str, niche: str = "cosmos") -> float:
    """Heat of the radar story that matches a feed item's title (0 when none does)."""
    r = latest(niche)
    if not r:
        return 0.0
    k = keys(title)
    best = 0.0
    for s in r.get("stories", []):
        common = len(k & set(s["keywords"]))
        if common >= (2 if len(k) <= 4 else 3):
            best = max(best, s["heat"])
    return best


def sky_story(niche: str = "cosmos", min_heat: float = 6.0) -> dict | None:
    """The hottest story about something visible in the sky, if it is hot enough (for a sky_tonight Short)."""
    r = latest(niche)
    hits = [s for s in (r or {}).get("stories", []) if s["sky"] and s["heat"] >= min_heat]
    return hits[0] if hits else None


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    niche = a[0] if a else "cosmos"
    hours = int(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 48
    f = ROOT / "research" / "niches" / f"{niche}.json"
    cfg = json.loads(f.read_text("utf-8")) if f.exists() else {}
    r = build(cfg, hours)
    out = ROOT / "research" / niche
    out.mkdir(parents=True, exist_ok=True)
    (out / f"radar-{r['date']}.json").write_text(json.dumps(r, indent=1, ensure_ascii=False) + "\n", "utf-8")
    (out / f"radar-{r['date']}.md").write_text(report(r, niche), "utf-8")
    print(report(r, niche))
    if not r["stories"]:
        print("radar: no story found (all sources skipped?)")


if __name__ == "__main__":
    main()
