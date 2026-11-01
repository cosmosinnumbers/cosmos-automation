"""Daily Threads posts without an LLM (owner decision 30/10/2026): adds today's items to queues/threads-queue.json.

  python tools/threads_build.py [--date 2026-11-01] [--only news,quiz,video] [--dry-run]

- 12:00 news: the newest on-topic item (last 3 days) of the agencies' feeds (NASA, JPL, ESA, ESA/Webb, ESA/Hubble,
  ESO, NOIRLab), text copied from the page (title + lead sentences), never rewritten. One reply with a sentence of
  the article that holds a number, and the link. Every number is checked against the page with auto_short.check().
- 16:00 quiz: a poll built from the NASA Planetary Fact Sheet table (nssdc.gsfc.nasa.gov/planetary/factsheet/),
  3 planets whose values differ clearly; yesterday's answer (field "answer" of the previous quiz) on top.
- 21:00 video: the Short of the day (release a<MMDD>-* of shorts-build), text from its checked narration and
  source. The video file needs a public URL: threads_api.short_video() looks for it at publish time, otherwise
  the post goes out as text (the Short itself is on YouTube at 21:00).
LOOK UP stays out of the posts: threads_api adds it as the first reply (cta.py). Topic tag: one per post.
Pacing: max 3 posts a day, 3 h apart (12, 16, 21) and threads_api.guard() at publish time. A slot that already
has an item (any ref) is left alone, so manual items always win. Needs gh (GH_TOKEN) for the release.
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import creds  # noqa: E402

QUEUE = creds.QUEUES / "threads-queue.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
FACTSHEET = "https://nssdc.gsfc.nasa.gov/planetary/factsheet/"
UA = {"User-Agent": "Mozilla/5.0 (CosmosInNumbers fact check)"}
SLOTS = {"news": "12:00", "quiz": "16:00", "video": "21:00"}
DISCLOSURE = "Narration: synthetic voice; script AI-assisted, checked by a human. Full videos on YouTube: @CosmosinNumbers"
DRY = "--dry-run" in sys.argv

# topic tag from the words of the post (Threads accepts one per post), first match wins
TAGS = [(r"\bwebb\b|jwst", "JWST"), (r"hubble", "Hubble"), (r"\bmars\b|perseverance|curiosity", "Mars"),
        (r"\bmoon\b|lunar|artemis", "Moon"), (r"\bsun\b|solar", "Sun"), (r"jupiter|europa", "Jupiter"),
        (r"saturn|titan|enceladus", "Saturn"), (r"asteroid|comet|meteor", "Asteroids"),
        (r"exoplanet", "Exoplanets"), (r"galax|black hole|nebula|star\b|stars\b", "Astronomy"),
        (r"\besa\b", "ESA"), (r"\bnasa\b", "NASA")]
AGENCY = [("esawebb.org", "ESA/Webb"), ("esahubble.org", "ESA/Hubble"), ("esa.int", "ESA"), ("eso.org", "ESO"),
          ("noirlab.edu", "NOIRLab"), ("jpl.nasa.gov", "NASA/JPL"), ("nasa.gov", "NASA")]


def tag_for(text: str, default="Space") -> str:
    return next((t for p, t in TAGS if re.search(p, text, re.I)), default)


def sentences(text: str) -> list[str]:
    text = re.sub(r"\s*(\[(…|\.\.\.)\]|…)\s*$", "", " ".join(text.split()))
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])", text) if s.strip()]


def fit(parts: list[str], limit: int) -> str:
    """Join paragraphs; drop trailing sentences of the second paragraph until the text fits."""
    head, body, tail = parts[0], parts[1], parts[2:]
    ss = sentences(body)
    while ss:
        t = "\n\n".join([head, " ".join(ss), *tail])
        if len(t) <= limit:
            return t
        ss.pop()
    return "\n\n".join([head, *tail])[:limit]


def load_queue() -> list[dict]:
    return json.loads(QUEUE.read_text("utf-8")) if QUEUE.exists() else []


def gh(*a) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(a[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


# ---------- news ----------

# news articles only (no mission, gallery, photojournal, Earth or community pages), about space
NEWS_URL = re.compile(r"jpl\.nasa\.gov/news/|esa\.int/Science_Exploration/|esawebb\.org/news/|esahubble\.org/news/|"
                      r"eso\.org/public/news/|noirlab\.edu/public/news/|nasa\.gov/news-release/|"
                      r"science\.nasa\.gov/missions/|nasa\.gov/(solar-system|universe|image-article|missions)/", re.I)
SPACE = re.compile(r"planet|star\b|stars|galax|nebula|telescope|webb|hubble|mars|moon|lunar|asteroid|comet|"
                   r"\bsun\b|solar|orbit|spacecraft|astronaut|space station|exoplanet|black hole|universe|cosmic|"
                   r"jupiter|saturn|uranus|neptune|venus|mercury|pluto|voyager|meteorite|supernova|light-year", re.I)
JUNK = re.compile(r"credit|min read|©|appeared first on|enable javascript|image processing|<img|photo release|"
                  r"organisation release", re.I)


def lead_of(url: str, summary: str) -> list[str]:
    """Lead sentences as written by the agency: og:description of the page, else the feed summary."""
    try:
        page = requests.get(url, headers=UA, timeout=60).text
        m = re.search(r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="([^"]+)"', page, re.I)
        import html
        text = html.unescape(m.group(1)) if m else summary
    except requests.RequestException:
        text = summary
    text = re.sub(r"<[^>]+>", " ", text)
    return [s for s in sentences(text) if len(s) > 40 and not JUNK.search(s)]


# ---------- quality filter and APOD ----------

# site menus scraped as text (1/11/2026: the APOD post carried the whole science.nasa.gov/apod navigation bar)
MENU_PHRASE = re.compile(r"astronomy picture of the day|discover the cosmos|today[’']s apod|apod archive|"
                         r"each day a different image|tomorrow[’']s picture", re.I)
MENU_WORD = re.compile(r"\b(Archive|Submissions|Index|Search|Calendar|RSS|Discuss)\b")


def bad_text(text: str) -> str | None:
    """Why a post body is not publishable (menu text, too short, cut mid-sentence), or None if it is fine.
    Single menu words count only in pairs, so a real sentence with 'search' or 'index' still passes."""
    t = " ".join(text.split())
    if MENU_PHRASE.search(t):
        return f"menu text ({MENU_PHRASE.search(t).group()!r})"
    if len(set(MENU_WORD.findall(t))) >= 2:
        return f"menu words {sorted(set(MENU_WORD.findall(t)))}"
    if len(t) < 80:
        return f"too short ({len(t)} chars)"
    if not re.search(r"[.!?][\"'”’)]?$", t):
        return "does not end with a full sentence"
    return None


APOD_PAGE = re.compile(r"science\.nasa\.gov/image-article/apod-|apod\.nasa\.gov/apod/ap\d{6}", re.I)
APOD_API = "https://api.nasa.gov/planetary/apod"


def plain(fragment: str) -> str:
    """HTML to text; inline tags (links in the APOD explanation) vanish without leaving a space inside words."""
    import html
    t = re.sub(r"</?(a|i|b|em|strong|span|sup|sub)\b[^>]*>", "", fragment, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+([,.;:!?])", r"\1", " ".join(t.split()))


def apod_explanation(text: str) -> str:
    """Only the explanation: after 'Explanation:', up to "Tomorrow's picture"; '--' becomes a dash."""
    text = re.split(r"Explanation:\s*", text, maxsplit=1)[-1]
    text = re.split(r"Tomorrow[’']s picture", text, maxsplit=1)[0]
    return " ".join(text.replace(" -- ", " – ").replace("--", " – ").split())


def apod(day: datetime, page_url: str) -> dict | None:
    """Today's APOD: title, explanation, credit. 1) the official API (key from NASA_API_KEY, else DEMO_KEY),
    accepted only if it answers for that date with a real title and a clean explanation (on 1/11/2026 it
    returned 'NASA Science' and the NASA logo); 2) the APOD page itself, text between 'Explanation:' and
    "Tomorrow's picture". Returns None if neither is clean."""
    key = os.environ.get("NASA_API_KEY") or "DEMO_KEY"
    try:
        j = requests.get(APOD_API, params={"api_key": key, "date": f"{day:%Y-%m-%d}", "thumbs": "true"}, timeout=60).json()
        ex = apod_explanation(j.get("explanation", ""))
        if j.get("date") == f"{day:%Y-%m-%d}" and j.get("title") and "nasa science" not in j["title"].lower() \
                and not bad_text(ex):
            return {"title": j["title"].strip(), "explanation": ex, "credit": (j.get("copyright") or "").strip(),
                    "media_type": j.get("media_type", "image"), "via": "api"}
        print(f"  APOD API unusable for {day:%Y-%m-%d} (title {j.get('title')!r}, date {j.get('date')}): page instead")
    except (requests.RequestException, ValueError) as e:
        print(f"  APOD API failed ({type(e).__name__}): page instead")
    try:
        page = requests.get(page_url, headers=UA, timeout=60).text
    except requests.RequestException as e:
        print(f"  APOD page failed ({type(e).__name__})")
        return None
    body = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    text = plain(body)
    if "Explanation:" not in text:
        print("  APOD page without 'Explanation:'")
        return None
    m = re.search(r"Explanation:", text)
    title = re.search(r"([^.!?]{3,80}?)\s+Explanation:", text[max(0, m.start() - 200):m.end()])
    og = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page, re.I)
    if og:  # "APOD: 2026 November 1 – Colors of the Moon - NASA Science"
        name = re.sub(r"\s+-\s+NASA Science$", "", plain(og.group(1)))
        name = re.sub(r"^APOD:\s*\d{4} \w+ \d{1,2}\s*[–-]\s*", "", name)
    else:
        name = title.group(1).split(".")[-1].strip() if title else ""
    credit = re.search(r"Credit(?: & Copyright)?:\s*(.+?)\s+(?:Authors|A service of|Explanation)", text)
    return {"title": name, "explanation": apod_explanation(text), "credit": credit.group(1).strip() if credit else "",
            "media_type": "video" if re.search(r"<iframe[^>]+(youtube|vimeo)", page, re.I) else "image", "via": "page"}


def apod_item(day: datetime, it: dict) -> dict | None:
    """12:00 post from the APOD of the day: title, the first sentences of the explanation (whole sentences only,
    max 500 chars), 'Source: NASA APOD (date)' and the link. Text only: APOD images are often copyrighted by the
    photographer, and a video APOD needs no thumbnail this way. The next sentence of the explanation is the reply."""
    a = apod(it["date"].replace(tzinfo=None), it["url"])
    if not a or not a["title"] or bad_text(a["explanation"]):
        print(f"  APOD skipped {it['url']}: {'no clean text' if not a else bad_text(a['explanation']) or 'no title'}")
        return None
    ss = sentences(a["explanation"])
    n = 3 if ss and ss[0].endswith("?") else 2  # an opening question gets two sentences of answer
    src = f"Source: NASA APOD ({it['date'].day} {it['date']:%b %Y}).\n{it['url']}"
    head = f"{a['title']} (NASA Astronomy Picture of the Day)" + (" 🎬" if a["media_type"] == "video" else "")
    text = fit([head, " ".join(ss[:n]), src], 500)
    used = [s for s in ss if s in text]
    if len(used) < 1 or bad_text(" ".join(used)):
        print(f"  APOD skipped {it['url']}: explanation does not fit")
        return None
    rest = [s for s in ss[len(used):] if not s.endswith("?")][:2]
    reply = " ".join(rest)
    while len(reply) > 420 and len(rest) > 1:
        rest.pop()
        reply = " ".join(rest)
    reply = (reply + (f"\n\nImage: {a['credit']}." if a["credit"] else "")).strip()
    print(f"  APOD via {a['via']}: {a['title']!r}")
    return {"ref": f"th-news-{day:%m%d}-apod-{slug(a['title'])}", "at": f"{day:%Y-%m-%d} {SLOTS['news']}",
            "tag": tag_for(a["title"] + " " + text), "text": text, "replies": [reply] if reply else [],
            "news_title": it["title"]}


def news(day: datetime, queue: list[dict], short_urls: set[str]) -> dict | None:
    import auto_short as a
    used = {u.rstrip("/") for i in queue for u in re.findall(r"https?://\S+", " ".join([i["text"], *i.get("replies", [])]))}
    used |= {u.rstrip("/") for u in short_urls}
    used_titles = {i.get("news_title") for i in queue}
    items = [it for it in a.rss_items(days=3, n=20) if NEWS_URL.search(it["url"]) and it["url"].rstrip("/") not in used
             and SPACE.search(it["title"] + " " + it["summary"][:400]) and len(it["title"].split()) >= 4]
    cands = []
    for it in items:
        title = re.sub(r"^(Photo|Organisation|Science|Press) Release:\s*", "", it["title"]).rstrip(".")
        if title in used_titles or title in {c[1]["title"] for c in cands}:  # same story on two agency sites
            continue
        it["title"] = title
        lead = lead_of(it["url"], it["summary"])
        if lead or APOD_PAGE.search(it["url"]):
            cands.append((0 if a.numbers(" ".join(lead[:2])) else 1, it, lead))
    cands.sort(key=lambda c: (c[0], -c[1]["date"].timestamp()))
    for _, it, lead in cands:
        url = it["url"]
        if APOD_PAGE.search(url):  # the APOD page has no article lead: its explanation, cleaned
            item = apod_item(day, it)
            if item:
                return item
            continue
        agency = next((n for d, n in AGENCY if d in url), "NASA")
        title = it["title"]
        src = f"Source: {agency} ({it['date']:%d %b %Y})."
        why = bad_text(" ".join(lead[:3]))
        if why:
            print(f"  news skipped {url}: {why}")
            continue
        text = fit([title, " ".join(lead[:3]), src], 500)
        if len(text) < 120:
            continue
        lead_nums = set(a.numbers(text))
        extra = next((s for s in sentences(it["text"]) if s not in text and 40 < len(s) < 300 and a.numbers(s)
                      and set(a.numbers(s)) - lead_nums and not JUNK.search(s) and not re.search(r"image:|photo:", s, re.I)), None)
        reply = f"{extra}\n\n{url}" if extra and len(extra) + len(url) < 480 else f"Read more: {url}"
        missing, problems, _ = a.check({"narration": text + " " + reply, "sources": [{"url": url}]})
        problems = [p for p in problems if "words" not in p and "real numbers" not in p]
        if missing or problems:
            print(f"  news skipped {url}: missing {missing}, {problems}")
            continue
        return {"ref": f"th-news-{day:%m%d}-{slug(title)}", "at": f"{day:%Y-%m-%d} {SLOTS['news']}",
                "tag": tag_for(title + " " + text), "text": text, "replies": [reply], "news_title": title}
    print("No recent feed item usable for the news post.")
    return None


def slug(s: str, n=3) -> str:
    w = [x for x in re.findall(r"[a-z0-9]+", s.lower()) if x not in {"the", "a", "an", "of", "and", "to", "in", "on", "for", "s"}]
    return "-".join(w[:n]) or "post"


# ---------- quiz ----------

PLANETS = ["MERCURY", "VENUS", "EARTH", "MARS", "JUPITER", "SATURN", "URANUS", "NEPTUNE"]
# row label prefix, question (max/min), emoji, answer unit
QUIZZES = [
    ("Diameter", "is the widest", "is the narrowest", "📏", "km across"),
    ("Mass", "is the most massive", "is the least massive", "⚖️", "× 10^24 kg"),
    ("Density", "is the densest", "is the least dense", "🪨", "kg per cubic meter"),
    ("Gravity", "has the strongest surface gravity", "has the weakest surface gravity", "🏋️", "m/s² at the surface"),
    ("Escape Velocity", "has the highest escape velocity", "has the lowest escape velocity", "🚀", "km/s to escape"),
    ("Length of Day", "has the longest day", "has the shortest day", "🕰️", "hours from sunrise to sunrise"),
    ("Orbital Period", "has the longest year", "has the shortest year", "📅", "days per orbit"),
    ("Orbital Velocity", "orbits the Sun fastest", "orbits the Sun slowest", "💨", "km/s around the Sun"),
    ("Mean Temperature", "is the hottest on average", "is the coldest on average", "🌡️", "°C on average"),
    ("Number of Moons", "has the most known moons", "has the fewest known moons", "🌙", "known moons"),
    ("Obliquity", "is the most tilted", "is the least tilted", "🌀", "degrees of tilt"),
]


def factsheet() -> dict[str, dict[str, str]]:
    import html
    r = requests.get(FACTSHEET, headers=UA, timeout=60)
    r.raise_for_status()
    rows = []
    for tr in re.findall(r"<tr.*?</tr>", r.text, re.S | re.I):
        rows.append([" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)])
    head = [c.upper() for c in rows[0]]
    if head[1:9] != ["MERCURY", "VENUS", "EARTH", "MOON", "MARS", "JUPITER", "SATURN", "URANUS"]:
        sys.exit(f"NASA fact sheet layout changed: {head}")
    return {row[0]: dict(zip(head[1:], row[1:])) for row in rows[1:] if row and row[0]}


def value(s: str) -> float | None:
    try:
        return float(s.replace(",", "").rstrip("*"))
    except ValueError:
        return None


def quiz(day: datetime, queue: list[dict]) -> dict | None:
    sheet = factsheet()
    recent = [i.get("quiz", "") for i in queue if i.get("poll")][-14:]
    rnd = random.Random(day.strftime("%Y%m%d"))
    choices = [(q, d) for q in QUIZZES for d in (0, 1) if f"{q[0]}-{d}" not in recent]
    rnd.shuffle(choices)
    for (label, qmax, qmin, emo, unit), d in choices:
        row = next((v for k, v in sheet.items() if k.startswith(label)), None)
        if not row:
            continue
        vals = {p: value(row.get(p, "")) for p in PLANETS}
        vals = {p: abs(v) if label == "Length of Day" else v for p, v in vals.items() if v is not None}
        for _ in range(30):
            pick = rnd.sample(sorted(vals), 3)
            vs = sorted(vals[p] for p in pick)
            best = (max if d == 0 else min)(pick, key=lambda p: vals[p])
            # unambiguous: the answer is clearly ahead of the runner-up (15%, or 2 units for small counts)
            other = vs[-2] if d == 0 else vs[1]
            gap = abs(vals[best] - other)
            if gap >= max(0.15 * abs(vals[best]), 0.15 * abs(other), 2 if label == "Number of Moons" else 0):
                break
        else:
            continue
        name = lambda p: p.title()  # noqa: E731
        opts = [name(p) for p in pick]
        raw = row[best].rstrip("*")
        answer = f"{name(best)}, {raw} {unit} (NASA Planetary Fact Sheet)"
        prev = next((i for i in reversed(queue) if i.get("poll") and i["at"] < f"{day:%Y-%m-%d}"), None)
        top = f"Yesterday's answer: {prev['answer']}.\n\n" if prev and prev.get("answer") else ""
        text = f"{top}Today's quiz {emo} Which of these planets {qmax if d == 0 else qmin}?\n\nAnswer tomorrow."
        return {"ref": f"th-quiz-{day:%m%d}-{slug(label, 2)}-{'max' if d == 0 else 'min'}",
                "at": f"{day:%Y-%m-%d} {SLOTS['quiz']}", "tag": "Astronomy", "poll": opts, "text": text,
                "replies": [f"Data: NASA Planetary Fact Sheet, {FACTSHEET}"], "quiz": f"{label}-{d}", "answer": answer}
    print("No unambiguous quiz found.")
    return None


# ---------- video ----------

def todays_short(day: datetime) -> dict | None:
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=15"))
    rel = next((r for r in rels if r["tag_name"].startswith(f"a{day:%m%d}-")), None)
    if not rel:
        return None
    import yaml
    with tempfile.TemporaryDirectory() as d:
        gh("release", "download", rel["tag_name"], "--repo", REPO, "-p", "short.yaml", "-p", "material-script.yaml", "-D", d)
        spec = yaml.safe_load(Path(d, "short.yaml").read_text("utf-8"))
        mat = yaml.safe_load(Path(d, "material-script.yaml").read_text("utf-8")) or {}
    spec["tag"] = rel["tag_name"]
    spec["source_list"] = mat.get("sources", [])
    return spec


def host_video(tag: str):
    """Put the Short on cosmosinnumbers.github.io/media/shorts/<tag>.mp4 (Threads needs a public URL), re-encoded
    in the Threads format (H.264 High, 1080x1920, 30 fps, AAC 48 kHz, faststart). Needs the secret PAGES_TOKEN
    (fine-grained token, only cosmosinnumbers.github.io, Contents: read and write); without it, nothing happens."""
    import base64
    tok = (os.environ.get("PAGES_TOKEN") or "").strip()  # a pasted secret can end with a newline
    if not tok or DRY:
        print(f"  video hosting skipped ({'dry run' if tok else 'no PAGES_TOKEN'}): the 21:00 post goes out as text")
        return
    api = f"https://api.github.com/repos/cosmosinnumbers/cosmosinnumbers.github.io/contents/media/shorts/{tag}.mp4"
    head = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    if requests.get(api, headers=head, timeout=60).status_code == 200:
        print("  video already on github.io")
        return
    import meta_api
    with tempfile.TemporaryDirectory() as d:
        gh("release", "download", tag, "--repo", REPO, "-p", f"{tag}.mp4", "-D", d)
        mp4 = meta_api.ig_ready(str(Path(d) / f"{tag}.mp4"))
        data = base64.b64encode(Path(mp4).read_bytes()).decode()
    r = requests.put(api, headers=head, timeout=300,
                     json={"message": f"media: Short {tag} per Threads", "content": data})
    print(f"  video on github.io: HTTP {r.status_code}")


def video(day: datetime, short: dict) -> dict:
    try:  # hosting is a bonus: without it the 21:00 post still goes out, as text
        host_video(short["tag"])
    except Exception as e:  # noqa: BLE001
        print(f"  video hosting failed ({type(e).__name__}): the 21:00 post goes out as text")
    title = short["title"].replace("#shorts", "").strip()
    src = short["source_list"][0] if short["source_list"] else {}
    agency = next((n for dom, n in AGENCY if dom in src.get("url", "")), "NASA")
    text = fit([title, short["narration"], f"Source: {agency}.\n{DISCLOSURE}"], 500)
    replies = [f"Source: {s['title']}: {s['url']}" for s in short["source_list"][:1]]
    return {"ref": f"th-{short['tag']}", "at": f"{day:%Y-%m-%d} {SLOTS['video']}", "tag": tag_for(title + " " + short["narration"]),
            "text": text, "replies": replies, "short": short["tag"]}


# ---------- main ----------

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    day = datetime.strptime(a[a.index("--date") + 1], "%Y-%m-%d") if "--date" in a else creds.now_local().replace(tzinfo=None)
    only = a[a.index("--only") + 1].split(",") if "--only" in a else list(SLOTS)
    queue = load_queue()
    taken = {i["at"] for i in queue}
    short = todays_short(day) if "video" in only or "news" in only else None
    short_urls = {s["url"] for s in (short or {}).get("source_list", [])}
    added = []
    for kind in only:
        at = f"{day:%Y-%m-%d} {SLOTS[kind]}"
        if at in taken and not DRY:
            print(f"{kind}: slot {at} already has an item, left alone")
            continue
        if at in taken:  # dry run: build it anyway, to show what the generator would post
            print(f"{kind}: slot {at} already has an item; dry run builds it anyway")
        if kind == "video" and not short:
            print(f"video: no Short release a{day:%m%d}-* yet")
            continue
        item = {"news": lambda: news(day, queue, short_urls), "quiz": lambda: quiz(day, queue),
                "video": lambda: video(day, short)}[kind]()
        if item and any(i["ref"] == item["ref"] for i in queue):
            print(f"{kind}: {item['ref']} already queued")
            if DRY:
                print(json.dumps(item, ensure_ascii=False, indent=1))
            continue
        if item:
            if len(item["text"]) > 500 or any(len(r) > 500 for r in item["replies"]) or any(len(o) > 25 for o in item.get("poll", [])):
                sys.exit(f"{item['ref']}: text, reply or poll option too long")
            print(json.dumps(item, ensure_ascii=False, indent=1))
            queue.append(item)
            added.append(item["ref"])
    if not added:
        print("Nothing added.")
        return
    queue.sort(key=lambda i: i["at"])
    if DRY:
        print(f"DRY-RUN: would add {', '.join(added)}")
        return
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"added {', '.join(added)}")


if __name__ == "__main__":
    main()
