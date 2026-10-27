"""Daily news Short built in the cloud (GitHub Actions, shorts-build.yml): Gemini writes, the code checks and renders.

  python auto_short.py [--dry-run] [--topic "<hint>"] [--spec <file.json>]

1. Gemini (with Google Search) picks ONE space news of the last 7 days from a primary source (NASA, ESA, JPL,
   ESA/Webb, ESO, STScI, NOIRLab...) not used yet, and writes title, headline, 85-110 words of narration (key
   number in the first sentence, no intro), sources and 3 queries for real footage.
2. Fact check by code: every source must answer 200 from an allowed domain, and every number in the narration
   must appear in the text of a source. Missing numbers go back to Gemini once; if still missing, no Short.
3. Real footage from the NASA Image and Video Library (no key): at least 2 clips, the first on screen from the
   first second, plus one NASA image when found. Credits and licences in assets.yaml, as for the manual Shorts.
4. short.py renders it (Kokoro voice 1.2, burned-in captions, LOOK UP end card, generated music) and writes
   out/upload.md with title, description (Gumroad line, sources, credits, AI disclosures) and Studio settings.
Output: build/auto/<id>/ (the workflow publishes it as a GitHub release: video + upload.md + factcheck.md).
Never uploads anywhere: YouTube goes through Studio until Google approves the API audit.
--spec skips Gemini (a JSON with the same fields), for tests.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import stock  # noqa: E402
from common import ROOT, media_duration, save_yaml  # noqa: E402

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ALLOWED = ("nasa.gov", "esa.int", "esawebb.org", "esahubble.org", "eso.org", "stsci.edu", "noirlab.edu",
           "jpl.nasa.gov", "caltech.edu", "jaxa.jp", "cfa.harvard.edu", "nature.com", "science.org", "arxiv.org",
           "iau.org", "aas.org", "usgs.gov", "noaa.gov")
UA = {"User-Agent": "Mozilla/5.0 (CosmosInNumbers fact check)"}
OUT = ROOT / "build" / "auto"
DRY = "--dry-run" in sys.argv

PROMPT = """You are the news writer of "Cosmos in Numbers", a faceless English YouTube Shorts channel about space:
real NASA/ESA footage and data, every number with a primary source. Today is {today}.
Use Google Search to find ONE space or astronomy news story published in the last 7 days by a primary source
(nasa.gov, science.nasa.gov, jpl.nasa.gov, esa.int, esawebb.org, esahubble.org, eso.org, stsci.edu, noirlab.edu,
or the peer-reviewed paper). Pick the one with the most striking, concrete number. {hint}
Do NOT pick any of these topics, already used: {used}

Write the Short:
- "narration": 85 to 110 words, plain spoken English. First sentence = the key number, no greeting or intro
  ("Did you know", "In this video" are forbidden). Short sentences. Every number must be written exactly as it
  appears in the sources (digits, e.g. "161,000", "3.2"). No number that is not in the sources. Say "about" for
  rounded values. End with one sentence of why it matters.
- "title": max 80 characters plus " #shorts", curiosity + the number, no clickbait lies.
- "headline": max 45 characters, shown on screen above the footage.
- "slug": 2-4 lowercase words joined by "-".
- "sources": 1-3 objects {{"title": "...", "url": "..."}} with the exact URL of the primary page(s) you used.
- "description_intro": 1-2 sentences with source name and date.
- "footage_queries": 3 short search queries (2-4 words) for the NASA Image and Video Library that will return
  REAL footage or visualizations related to the story (mission name, telescope, planet).
- "image_query": 1 query for a related NASA image.
Answer with JSON only, no markdown fences:
{{"slug": "", "title": "", "headline": "", "narration": "", "description_intro": "", "sources": [], "footage_queries": [], "image_query": ""}}"""

FIX = """Some numbers in your narration do not appear in the text of the sources you gave: {missing}.
Rewrite the narration (same rules) using only numbers that appear verbatim in the sources, or change the sources
to the primary pages that contain them. Answer with the full JSON again, same fields."""


FEEDS = ["https://www.nasa.gov/news-release/feed/", "https://www.nasa.gov/feed/", "https://science.nasa.gov/feed/",
         "https://www.jpl.nasa.gov/feeds/news", "https://www.esa.int/rssfeed/Our_Activities/Space_Science",
         "https://www.esa.int/rssfeed/Science_Exploration", "https://esawebb.org/news/feed/",
         "https://esahubble.org/news/feed/", "https://www.eso.org/public/news/feed/", "https://noirlab.edu/public/news/feed/"]

RSS_PROMPT = """You are the news writer of "Cosmos in Numbers", a faceless English YouTube Shorts channel about space:
real NASA/ESA footage and data, every number with a primary source. Today is {today}.
Below are recent news items from primary sources, each with an excerpt of its page. Pick the ONE with the most
striking, concrete number that is NOT in this list of topics already used: {used}
{hint}
{items}

Write the Short using ONLY facts and numbers that appear in the excerpt of the item you pick:
- "narration": 85 to 110 words, plain spoken English. First sentence = the key number, no greeting or intro
  ("Did you know", "In this video" are forbidden). Short sentences. Every number exactly as written in the excerpt
  (digits). Say "about" for rounded values. End with one sentence of why it matters.
- "title": max 80 characters plus " #shorts", curiosity + the number, no clickbait lies.
- "headline": max 45 characters, shown on screen above the footage.
- "slug": 2-4 lowercase words joined by "-".
- "sources": [{{"title": "...", "url": "<the item's url, exactly>"}}]
- "description_intro": 1-2 sentences with source name and date.
- "footage_queries": 3 short queries (2-4 words) for the NASA Image and Video Library (mission, telescope, planet).
- "image_query": 1 query for a related NASA image.
Answer with JSON only:
{{"slug": "", "title": "", "headline": "", "narration": "", "description_intro": "", "sources": [], "footage_queries": [], "image_query": ""}}"""


def gemini(messages, search=True):
    """(raw text, parsed JSON). search=True uses Google Search grounding; a 429 there means no grounding quota."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("No GEMINI_API_KEY secret.")
    model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    body = {"contents": messages, "generationConfig": {"temperature": 0.4}}
    if search:
        body["tools"] = [{"google_search": {}}]
    else:
        body["generationConfig"]["responseMimeType"] = "application/json"
    codes = []
    for attempt in range(2 if search else 5):
        m = model if attempt < 3 else "gemini-3.6-flash"
        try:
            r = requests.post(GEMINI.format(model=m), params={"key": key}, json=body, timeout=180)
        except requests.RequestException as e:
            codes.append(type(e).__name__)
            time.sleep(20)
            continue
        codes.append(f"{m}:{r.status_code}")
        if r.status_code in (429, 500, 503):
            print(f"  Gemini {m} HTTP {r.status_code}: {r.text[:200]}", flush=True)
            time.sleep(15 if search else 30 * (attempt + 1))
            continue
        if r.status_code != 200:
            sys.exit(f"Gemini error {r.status_code}: {r.text[:300]}")
        parts = r.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts)
        mt = re.search(r"\{.*\}", text, re.S)
        if not mt:
            sys.exit(f"Gemini did not return JSON: {text[:300]}")
        return text, json.loads(mt.group())
    if search:
        return None, None  # caller falls back to the RSS feeds without grounding
    sys.exit(f"Gemini unavailable: {', '.join(codes)}")


def rss_items(days=7, n=10):
    """Recent items of the primary-source feeds, newest first, with an excerpt of each page."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    items = []
    for url in FEEDS:
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code != 200:
                print("  feed", r.status_code, url)
                continue
            root = ET.fromstring(r.content)
        except Exception as e:  # noqa: BLE001
            print("  feed failed", url, type(e).__name__)
            continue
        for it in root.iter("item"):
            link, title, date = it.findtext("link"), it.findtext("title"), it.findtext("pubDate")
            try:
                d = parsedate_to_datetime(date)
            except Exception:  # noqa: BLE001
                continue
            if link and title and (datetime.now(d.tzinfo) - d).days <= days:
                items.append({"title": title.strip(), "url": link.strip(), "date": d})
    items.sort(key=lambda x: x["date"], reverse=True)
    seen, out = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        try:
            it["text"] = " ".join(page_text(it["url"]).split())[:2500]
        except Exception:  # noqa: BLE001
            continue
        out.append(it)
        if len(out) >= n:
            break
    print(f"  {len(out)} recent items from the feeds")
    return out


def write_spec(today, hint):
    """Grounded search first; without grounding quota, the RSS feeds of the agencies."""
    used = used_topics()
    msgs = [{"role": "user", "parts": [{"text": PROMPT.format(today=today, hint=hint, used=used)}]}]
    raw, spec = gemini(msgs, search=True)
    if spec:
        return msgs, raw, spec, True
    print("Google Search grounding unavailable: using the agencies' RSS feeds")
    items = rss_items()
    if not items:
        sys.exit("No recent item readable from the feeds: no Short today.")
    block = "\n\n".join(f"[{i}] {it['title']} ({it['date']:%Y-%m-%d})\nURL: {it['url']}\nEXCERPT: {it['text']}"
                         for i, it in enumerate(items, 1))
    msgs = [{"role": "user", "parts": [{"text": RSS_PROMPT.format(today=today, hint=hint, used=used, items=block)}]}]
    raw, spec = gemini(msgs, search=False)
    return msgs, raw, spec, False


def used_topics() -> str:
    seen = []
    f = ROOT / "governance" / "argomenti-usati.md"
    if f.exists():
        seen.append(f.read_text("utf-8")[-3000:])
    seen += [p.name for p in (ROOT / "04-produzione" / "shorts").glob("*") if p.is_dir()]
    r = subprocess.run(["gh", "release", "list", "--limit", "60", "--json", "name"], capture_output=True, text=True)
    if r.returncode == 0:
        seen += [x["name"] for x in json.loads(r.stdout or "[]")]
    return "; ".join(s.replace("\n", " ") for s in seen)[-5000:]


def page_text(url: str) -> str:
    host = urllib.parse.urlparse(url).hostname or ""
    if not any(host == d or host.endswith("." + d) for d in ALLOWED):
        raise ValueError(f"not a primary source domain: {host}")
    r = requests.get(url, headers=UA, timeout=60, allow_redirects=True)
    if r.status_code != 200:
        raise ValueError(f"HTTP {r.status_code}")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", r.text, flags=re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", t))


def numbers(text: str) -> list[str]:
    return [n.rstrip(".,") for n in re.findall(r"\d[\d,.]*", text) if n.rstrip(".,")]


def check(spec) -> tuple[list[str], list[str], str]:
    """(missing numbers, source problems, report). A number matches with or without thousands separators."""
    texts, problems = [], []
    for s in spec.get("sources", []):
        try:
            texts.append(page_text(s["url"]))
        except Exception as e:  # noqa: BLE001
            problems.append(f"{s.get('url')}: {e}")
    blob = " ".join(texts)
    flat = blob.replace(",", "").replace(" ", "").replace("\xa0", "")
    missing = []
    for n in dict.fromkeys(numbers(spec["narration"])):
        if n in blob or n.replace(",", "") in flat:
            continue
        if re.fullmatch(r"20\d\d", n):  # a year (dates are checked by the source date)
            continue
        missing.append(n)
    words = len(spec["narration"].split())
    rep = [f"# Fact check automatico ({datetime.now():%Y-%m-%d %H:%M})", "",
           f"- Parole: {words} (85-110)", f"- Fonti lette: {len(texts)}/{len(spec.get('sources', []))}"]
    rep += [f"- PROBLEMA fonte: {p}" for p in problems]
    rep += [f"- Numeri nella narrazione: {', '.join(dict.fromkeys(numbers(spec['narration']))) or 'nessuno'}",
            f"- Numeri NON trovati nelle fonti: {', '.join(missing) or 'nessuno'}"]
    if not 70 <= words <= 125:
        problems.append(f"narration has {words} words")
    if not texts:
        problems.append("no readable primary source")
    return missing, problems, "\n".join(rep) + "\n"


def nasa_items(query, media):
    q = urllib.parse.quote(query)
    return stock.nasa(f"/search?q={q}&media_type={media}")["collection"]["items"]


def nasa_image(query, news_dir, assets):
    for it in nasa_items(query, "image")[:5]:
        d = it["data"][0]
        files = stock.get_json(f"https://images-assets.nasa.gov/image/{urllib.parse.quote(d['nasa_id'])}/collection.json", {})
        jpg = next((f for t in ("~large.jpg", "~medium.jpg", "~orig.jpg") for f in files if f.endswith(t)), None)
        if not jpg:
            continue
        rel = f"assets/stock/nasa-img-{re.sub(r'[^A-Za-z0-9_-]', '_', d['nasa_id'])}.jpg"
        stock.download(jpg.replace("http://", "https://"), news_dir / rel)
        concept = any(w in (d.get("description", "") + d["title"]).lower() for w in ("concept", "illustration", "rendering", "artist"))
        assets["img_main"] = {"file": rel, "type": "image", "kind": "illustration" if concept else "photo",
                              "title": d["title"], "source": f"https://images.nasa.gov/details/{d['nasa_id']}",
                              "credit": "NASA" + (f"/{d['center']}" if d.get("center") else ""),
                              "license": "NASA media usage guidelines (generally not copyrighted; no endorsement, no logos)",
                              "check": "ok"}
        return "img_main"
    return None


def footage(spec, news_dir) -> list[dict]:
    """Download >= 2 NASA clips and maybe 1 image; return the visuals list (clip first)."""
    news_dir.mkdir(parents=True, exist_ok=True)
    picked, seen = [], set()
    for q in spec.get("footage_queries", [])[:4]:
        try:
            items = nasa_items(q, "video")
        except Exception as e:  # noqa: BLE001
            print("  NASA search failed:", q, e)
            continue
        for it in items[:6]:
            sid = it["data"][0]["nasa_id"]
            if sid in seen:
                continue
            seen.add(sid)
            key = f"vid_{len(picked) + 1}"
            try:
                stock.get("nasa-video", sid, news_dir, key)
            except BaseException as e:  # noqa: BLE001 - a broken item must not stop the others
                print("  skip", sid, str(e)[:120])
                continue
            picked.append(key)
            break
        if len(picked) >= 3:
            break
    if len(picked) < 2:
        sys.exit(f"Only {len(picked)} NASA clips found: Short not built (rule: at least 2 real clips).")
    assets = stock.load_yaml(news_dir / "assets.yaml")
    img = None
    if spec.get("image_query"):
        try:
            img = nasa_image(spec["image_query"], news_dir, assets)
        except Exception as e:  # noqa: BLE001
            print("  NASA image failed:", e)
    save_yaml(news_dir / "assets.yaml", assets)
    visuals = []
    for k in picked:
        dur = media_duration(news_dir / assets[k]["file"])
        visuals.append({"src": k, "start": round(min(8.0, dur * 0.2), 1)})  # skip title cards at the start
    if img:
        visuals.insert(1, {"src": img, "motion": "zoom_in"})
    return visuals


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    today = datetime.now().strftime("%Y-%m-%d")
    if "--spec" in a:
        spec = json.loads(Path(a[a.index("--spec") + 1]).read_text("utf-8"))
        missing, problems, report = check(spec)
    else:
        hint = f"Prefer this topic if there is fresh news on it: {a[a.index('--topic') + 1]}." if "--topic" in a else ""
        msgs, raw, spec, search = write_spec(today, hint)
        missing, problems, report = check(spec)
        if missing or problems:
            print("first draft rejected:", missing, problems)
            msgs += [{"role": "model", "parts": [{"text": raw}]},
                     {"role": "user", "parts": [{"text": FIX.format(missing=", ".join(missing) or "none") +
                                                 (" Source problems: " + "; ".join(problems) if problems else "")}]}]
            raw, spec = gemini(msgs, search=search)
            if not spec:
                sys.exit("Gemini unavailable for the correction: no Short today.")
            missing, problems, report = check(spec)
    print(report)
    if missing or problems:
        sys.exit("FACT CHECK FAILED: no Short today. " + "; ".join(problems + [f"number {n} not in sources" for n in missing]))
    slug = re.sub(r"[^a-z0-9-]", "", spec["slug"].lower())[:40] or "news"
    sid = f"a{datetime.now():%m%d}-{slug}"
    base = OUT / sid
    news_dir, short_dir = base / "material", base / "short"
    print("Short:", sid, "|", spec["title"])
    print(spec["narration"])
    if DRY:
        print("DRY-RUN: no footage, no render.")
        return
    visuals = footage(spec, news_dir)
    srcs = [{"id": f"S{i}", "title": s["title"], "url": s["url"]} for i, s in enumerate(spec["sources"], 1)]
    save_yaml(news_dir / "script.yaml", {"sources": srcs})
    short_dir.mkdir(parents=True, exist_ok=True)
    title = spec["title"] if "#shorts" in spec["title"] else spec["title"].strip() + " #shorts"
    save_yaml(short_dir / "short.yaml", {
        "id": sid, "title": title, "headline": spec["headline"], "voice": "af_heart", "speed": 1.2,
        "assets_from": "../material", "music": {"seed": int(datetime.now().strftime("%j")), "mood": "wonder"},
        "sources": [s["id"] for s in srcs], "description_intro": spec["description_intro"],
        "narration": spec["narration"], "visuals": visuals})
    (base / "factcheck.md").write_text(report + "\n## Fonti\n" + "\n".join(f"- {s['title']}: {s['url']}" for s in srcs)
                                       + "\n\nScritto da Gemini, controllato dal codice: rileggere prima di pubblicare.\n", "utf-8")
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "short.py"), str(short_dir)])
    if r.returncode:
        sys.exit("short.py failed")
    mp4 = short_dir / "out" / f"{sid}.mp4"
    dur = media_duration(mp4)
    if not 20 <= dur <= 60:
        sys.exit(f"QC: duration {dur:.1f}s outside 20-60 s")
    meta = {"id": sid, "title": title, "duration": round(dur, 1), "mp4": str(mp4),
            "upload": str(short_dir / "out" / "upload.md"), "factcheck": str(base / "factcheck.md")}
    (base / "result.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), "utf-8")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"id={sid}\ndir={base}\n")
    print("OK", json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
