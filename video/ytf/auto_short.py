"""Daily news Short built in the cloud (GitHub Actions, shorts-build.yml): Gemini writes, the code checks and renders.

  python auto_short.py [--dry-run] [--topic "<hint>"] [--spec <file.json>] [--format F --hook H [--idea ID --source S]]
       [--hot --prefix b]   second Short of the day: news of the last 48 hours, release b<MMDD>-<slug>

--format/--hook: the variant chosen by tools/experiments.py plan (config/formats.json), added to the writer rules and
saved as labels in result.json, so the metrics can tell which format and hook worked.

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
import claude_cli  # noqa: E402
import glm  # noqa: E402
import stock  # noqa: E402
from common import ROOT, media_duration, save_yaml  # noqa: E402

GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ALLOWED = ("nasa.gov", "esa.int", "esawebb.org", "esahubble.org", "eso.org", "stsci.edu", "noirlab.edu",
           "jpl.nasa.gov", "caltech.edu", "jaxa.jp", "cfa.harvard.edu", "nature.com", "science.org", "arxiv.org",
           "iau.org", "aas.org", "usgs.gov", "noaa.gov")
UA = {"User-Agent": "Mozilla/5.0 (CosmosInNumbers fact check)"}
OUT = ROOT / "build" / "auto"
DRY = "--dry-run" in sys.argv
HOT = "--hot" in sys.argv   # second Short of the day (prefix b): the freshest news, 48 hours at most

VIRAL_RULES = """Retention rules (the Short is judged on how many people stay to the end and watch it again):
- ONE idea, one story. Two or three measured numbers at most, each with a comparison a viewer can picture.
- HOOK = the first sentence, 12 words or fewer, spoken in under 3 seconds: a concrete oddity or a scale comparison
  ("A day on Venus is longer than its year."), never a greeting, never a question about "did you know".
- Open loop: by the second sentence promise something ("and the reason is stranger than the number") and pay it off
  before the end. Sentences of 6 to 12 words, one new fact per sentence, no filler.
- LAST sentence closes the loop by echoing the opening words, so the Short replays seamlessly
  (it can end with the same noun or number that started it). No "subscribe", no "thanks for watching".
- Active voice, present tense, simple words a 12 year old understands.
"""


FORMAT_RULES = ""   # set by main() from --format/--hook (tools/experiments.py plan): the variant under test


def format_rules(fmt: str, hook: str) -> str:
    """Writer lines of the format and hook under test (config/formats.json)."""
    try:
        lib = json.loads((ROOT / "config" / "formats.json").read_text("utf-8"))
    except (OSError, ValueError):
        return ""
    lines = [x for x in (lib["formats"].get(fmt, {}).get("writer"), lib["hooks"].get(hook, {}).get("writer")) if x]
    if not lines:
        return ""
    return ("Variant under test today (follow it, it is how we learn what works):\n- " + "\n- ".join(lines) +
            "\n- Whatever the hook, a measured number from the sources must be in the first or second sentence." +
            '\n- If the sources cannot fit this format, write the best Short you can and add "format_fit": false to the JSON.\n')


def viral_rules() -> str:
    """VIRAL_RULES plus what the weekly learning loop (tools/learn_weekly.py) found worked or failed on this channel,
    plus the format and hook under test (FORMAT_RULES)."""
    return _viral_rules() + FORMAT_RULES


def _viral_rules() -> str:
    try:
        w = json.loads((ROOT / "config" / "viral-weights.json").read_text("utf-8"))
    except (OSError, ValueError):
        return VIRAL_RULES
    extra = []
    if w.get("rules"):
        extra.append("- Learned from our last videos (data, this week): " + "; ".join(w["rules"]) + ".")
    best = [x["title"] for x in w.get("winners", []) if x.get("kind") == "short"][:3]
    worst = [x["title"] for x in w.get("losers", []) if x.get("kind") == "short"][:2]
    if best:
        extra.append("- Our best recent titles (copy the structure, never the topic): " + " | ".join(best) + ".")
    if worst:
        extra.append("- Our weakest recent titles (avoid this kind of framing): " + " | ".join(worst) + ".")
    return VIRAL_RULES + ("\n".join(extra) + "\n" if extra else "")


PROMPT = """You are the news writer of "Cosmos in Numbers", a faceless English YouTube Shorts channel about space:
real NASA/ESA footage and data, every number with a primary source. Today is {today}.
Use Google Search to find ONE space or astronomy news story published in the last 7 days by a primary source
(nasa.gov, science.nasa.gov, jpl.nasa.gov, esa.int, esawebb.org, esahubble.org, eso.org, stsci.edu, noirlab.edu,
or the peer-reviewed paper). Pick the one with the most striking, concrete number. {hint}
Do NOT pick any of these topics, already used: {used}

Write the Short.
{rules}
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
         "https://www.jpl.nasa.gov/feeds/news/", "https://www.esa.int/rssfeed/Our_Activities/Space_Science",
         "https://esawebb.org/news/feed/",
         "https://esahubble.org/news/feed/", "https://www.eso.org/public/news/feed/", "https://noirlab.edu/public/news/feed/"]

RSS_PROMPT = """You are the news writer of "Cosmos in Numbers", a faceless English YouTube Shorts channel about space:
real NASA/ESA footage and data, every number with a primary source. Today is {today}.
Below are recent news items from primary sources, each with an excerpt of its page. Pick the ONE about space or
astronomy (planets, stars, galaxies, telescopes, missions, the Sun, asteroids, astronauts in orbit) with the most
striking, concrete measured number (distance, size, mass, temperature, speed, age, count), NOT in this list of
topics already used: {used}
Never pick aeronautics, aircraft, education, agency business or event pages. If no item has a real measured
number about space, answer only {{"skip": "<why>"}}.
{hint}
{items}

Write the Short using ONLY facts and numbers that appear in the excerpt of the item you pick. At least two
measured numbers from the excerpt must be in the narration; mission or aircraft names with digits do not count.
{rules}
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


_MODELS: list[str] = []


def gemini_models(key) -> list[str]:
    """GEMINI_MODELS first, then every other Flash model this key can call (newest first): a model name that
    disappears or a busy model never stops the Short."""
    if _MODELS:
        return _MODELS
    wanted = [m.strip() for m in os.environ.get("GEMINI_MODELS", "gemini-3.8-flash,gemini-3.6-flash").split(",") if m.strip()]
    avail = []
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 200},
                         timeout=30)
        for m in r.json().get("models", []):
            name = m["name"].split("/")[-1]
            if ("generateContent" in m.get("supportedGenerationMethods", []) and "flash" in name
                    and not re.search(r"image|tts|audio|live|embed|thinking|exp", name)):
                avail.append(name)
    except Exception as e:  # noqa: BLE001
        print("  Gemini model list failed:", type(e).__name__)
    ver = lambda n: [float(x) for x in re.findall(r"\d+(?:\.\d+)?", n)[:1]] or [0.0]  # noqa: E731
    extra = sorted((n for n in avail if n not in wanted), key=lambda n: (ver(n), "lite" not in n, "preview" not in n),
                   reverse=True)
    _MODELS[:] = ([m for m in wanted if not avail or m in avail] + extra)[:5] or wanted
    print("  Gemini models:", ", ".join(_MODELS), flush=True)
    return _MODELS


def gemini(messages, search=True):
    """(raw text, parsed JSON). search=True uses Google Search grounding; a 429 there means no grounding quota."""
    if not search and os.environ.get("LLM_FIRST") == "claude" and claude_cli.available():
        out = claude_cli.chat(messages)   # repo variable LLM_FIRST=claude: Claude (subscription) writes first
        if out:
            return out
    if not search and os.environ.get("LLM_FIRST") == "glm" and glm.available():
        out = glm.chat(messages)   # repo variable LLM_FIRST=glm: GLM writes first, Gemini and Groq are the fallbacks
        if out:
            return out
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("No GEMINI_API_KEY secret.")
    models = gemini_models(key)
    body = {"contents": messages, "generationConfig": {"temperature": 0.4}}
    if search:
        body["tools"] = [{"google_search": {}}]
    else:
        body["generationConfig"]["responseMimeType"] = "application/json"
    codes, dead = [], set()
    # without grounding: up to 10 tries over ~15 minutes, rotating models (a 503 is usually a busy model)
    for attempt in range(2 if search else 10):
        live = [m for m in models if m not in dead]
        if not live:
            break
        m = live[0] if search else live[attempt % len(live)]
        try:
            r = requests.post(GEMINI.format(model=m), params={"key": key}, json=body, timeout=120)
        except requests.RequestException as e:
            codes.append(f"{m}:{type(e).__name__}")
            time.sleep(10)
            continue
        codes.append(f"{m}:{r.status_code}")
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  Gemini {m} HTTP {r.status_code}: {r.text[:200]}", flush=True)
            time.sleep(15 if search else min(150, 20 + 20 * attempt))
            continue
        if r.status_code == 404:  # model name not available on this key: next model
            print(f"  Gemini {m} HTTP 404 (model not available)", flush=True)
            dead.add(m)
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
    print(f"  Gemini unavailable ({', '.join(codes)}): trying the backup writer", flush=True)
    out = backup_llm(messages)
    if out:
        return out
    sys.exit(f"Gemini unavailable: {', '.join(codes)}; backup writer unavailable too.")


def backup_models(base, tok) -> str:
    """Text models the key can call (OpenAI-compatible /models), biggest first: no hard-coded model names."""
    try:
        r = requests.get(f"{base}/models", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        ids = [m["id"] for m in r.json().get("data", [])]
    except Exception as e:  # noqa: BLE001
        print(f"  backup writer: model list failed ({type(e).__name__})", flush=True)
        return ""
    ids = [i for i in ids if not re.search(r"whisper|tts|guard|vision|image|embed|audio|speech|prompt|compound", i)]
    size = lambda i: max([float(x) for x in re.findall(r"(\d+(?:\.\d+)?)b\b", i)] or [0])  # noqa: E731
    ids.sort(key=lambda i: ("versatile" in i, "grok" in i and "mini" not in i, size(i)), reverse=True)
    print("  backup writer models:", ", ".join(ids[:3]) or "none", flush=True)
    return ",".join(ids[:3])


def smaller(chat: list[dict], keep: float = 0.6) -> list[dict]:
    """The same chat with its longest message cut to `keep` of its length: the head (instructions) and the tail
    (the request and the JSON format) stay, the middle (source texts) goes. For the backup writer's token limits."""
    i = max(range(len(chat)), key=lambda j: len(chat[j]["content"]))
    c = chat[i]["content"]
    n = int(len(c) * keep)
    head, tail = c[: int(n * 0.7)], c[len(c) - (n - int(n * 0.7)):]
    return [*chat[:i], {**chat[i], "content": head + "\n[...source text shortened...]\n" + tail}, *chat[i + 1:]]


def backup_llm(messages):
    """Backup writer (owner decision 30/10/2026), only on the RSS path: it writes from the article texts already
    extracted by the code and its draft goes through the same check() as Gemini's. Any OpenAI-compatible
    chat endpoint: secrets BACKUP_LLM_URL / BACKUP_LLM_KEY / BACKUP_LLM_MODELS (e.g. Groq or OpenRouter free tier);
    without them, GitHub Models with the repo token (on 30/10/2026 it answered a bare "OK": treated as unavailable).
    (raw text, parsed JSON) or None.
    GLM (secret GLM_API_KEY, video/ytf/glm.py) comes first when the key exists: the strongest writer of the backups."""
    if claude_cli.available():
        out = claude_cli.chat(messages)
        if out:
            return out
    if glm.available():
        out = glm.chat(messages)
        if out:
            return out
    # GROK_API_KEY (the name the owner used on 30/10/2026): provider from the key prefix, model from its /models list
    key = os.environ.get("BACKUP_LLM_KEY") or os.environ.get("GROK_API_KEY") or os.environ.get("GROQ_API_KEY") or ""
    provider = {"gsk_": "groq", "xai-": "xai"}.get(key[:4], "")
    base = {"groq": "https://api.groq.com/openai/v1", "xai": "https://api.x.ai/v1"}.get(provider)
    if provider:
        print(f"  backup writer provider: {provider}", flush=True)
    url = os.environ.get("BACKUP_LLM_URL") or (f"{base}/chat/completions" if base else
                                               "https://models.github.ai/inference/chat/completions")
    tok = key or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    models = os.environ.get("BACKUP_LLM_MODELS") or (backup_models(base, tok) if base else
                                                     "openai/gpt-4.1-mini,openai/gpt-4o-mini")
    if not tok:
        print("  backup writer: no token", flush=True)
        return None
    chat = [{"role": "assistant" if m["role"] == "model" else "user",
             "content": "".join(p.get("text", "") for p in m["parts"])} for m in messages]
    for model in [m.strip() for m in models.split(",") if m.strip()]:
        msgs, waits = chat, 0
        for shrink in range(6):  # 413 (request over the per-minute token limit): smaller blocks; 429: wait the minute
            try:
                r = requests.post(url, timeout=120, headers={"Authorization": f"Bearer {tok}"},
                                  json={"model": model, "messages": msgs, "temperature": 0.4,
                                        "response_format": {"type": "json_object"}})
                text = r.json()["choices"][0]["message"]["content"] or "" if r.status_code == 200 else ""
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
                print(f"  backup writer {model}: no usable answer ({type(e).__name__})", flush=True)
                r = None
                break
            if r.status_code == 429 and "per minute" in r.text and waits < 2:
                m = re.search(r"try again in ([\d.]+)s", r.text)
                pause = min(70.0, float(m.group(1)) + 2) if m else 62.0
                print(f"  backup writer {model} HTTP 429 (tokens per minute): waiting {pause:.0f} s", flush=True)
                time.sleep(pause)
                waits += 1
                continue
            if r.status_code != 413 or shrink >= 5:
                break
            msgs = smaller(msgs)
            print(f"  backup writer {model} HTTP 413: retrying with the input cut to "
                  f"{sum(len(m['content']) for m in msgs)} chars", flush=True)
        if r is None:
            continue
        if r.status_code != 200:
            print(f"  backup writer {model} HTTP {r.status_code}: {r.text[:200]}", flush=True)
            continue
        mt = re.search(r"\{.*\}", text, re.S)
        if mt:
            print(f"  written by the backup writer {model}", flush=True)
            return text, json.loads(mt.group())
    return None


# Not channel material: aeronautics, education, agency business. Matched on title + URL of the feed items.
OFF_TOPIC = re.compile(r"aeronaut|aircraft|aviation|airplane|x-59|quesst|supersonic|drone|helicopter|wind tunnel|"
                       r"student|educator|internship|\bstem\b|learning resources|contract|award|budget|leadership|"
                       r"administrator|appoint|nominat|partnership|agreement|employee|hiring|career|podcast|webinar|"
                       r"media accredit|ceremony|art contest|biograph|obituar|in memoriam", re.I)


def feed_entries(xml: str):
    """(title, link, date) of an RSS or Atom feed, tolerant of leading junk and of HTML in the fields."""
    from email.utils import parsedate_to_datetime

    def field(block, tag):
        m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", block, re.S | re.I)
        v = m.group(1) if m else ""
        v = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", v, flags=re.S)
        return html.unescape(re.sub(r"<[^>]+>", "", v)).strip()

    for block in re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", xml, re.S | re.I):
        link = field(block, "link")
        if not link:  # Atom: <link href="..."/>
            m = re.search(r"<link\b[^>]*href=[\"']([^\"']+)", block, re.I)
            link = html.unescape(m.group(1)) if m else ""
        raw = field(block, "pubDate") or field(block, "published") or field(block, "updated") or field(block, "dc:date")
        try:
            d = parsedate_to_datetime(raw) if re.match(r"[A-Za-z]{3},", raw) else datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            continue
        if d.tzinfo is None:
            continue
        yield field(block, "title"), link.strip(), d, field(block, "content:encoded") or field(block, "description") \
            or field(block, "summary") or field(block, "content")


def get_feed(url):
    for wait in (0, 20, 60):  # nasa.gov answers 429 to bursts
        time.sleep(wait)
        r = requests.get(url, headers=UA, timeout=30)
        if r.status_code != 429:
            return r
    return r


def rss_items(days=7, n=10):
    """Recent space items of the primary-source feeds, newest first, with an excerpt of each page."""
    items = []
    for url in FEEDS:
        try:
            r = get_feed(url)
            if r.status_code != 200:
                print("  feed", r.status_code, url)
                continue
            found = list(feed_entries(r.text))
        except Exception as e:  # noqa: BLE001
            print("  feed failed", url, type(e).__name__)
            continue
        if not found:
            print("  feed unreadable", url, r.headers.get("content-type"), repr(r.text[:120]))
            continue
        fresh = kept = 0
        for title, link, d, summary in found:
            if not (link and title and (datetime.now(d.tzinfo) - d).days <= days):
                continue
            fresh += 1
            if OFF_TOPIC.search(title + " " + link):
                continue
            kept += 1
            items.append({"title": title, "url": link, "date": d, "feed": url, "summary": " ".join(summary.split())})
        print(f"  feed ok {url}: {len(found)} items, {fresh} recent, {kept} on topic")
        time.sleep(2)
    items.sort(key=lambda x: x["date"], reverse=True)
    seen, out = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        try:
            body = article_text(it["url"])
        except Exception as e:  # noqa: BLE001
            print("  page failed", it["url"], str(e)[:80])
            continue
        # the article body, not the site menus: the feed summary first, then the paragraphs of the page
        it["text"] = (it["summary"] + " " + body).strip()[:3000]
        if len(it["text"]) < 300 or not re.search(r"\d", it["text"]):
            print("  no article text", it["url"], len(it["text"]))
            continue
        out.append(it)
        if len(out) >= n:
            break
    print(f"  {len(out)} recent items from the feeds")
    return out


def write_spec(today, hint):
    """Grounded search first; without grounding quota, the RSS feeds of the agencies."""
    used = used_topics()
    msgs = [{"role": "user", "parts": [{"text": PROMPT.format(today=today, hint=hint, used=used, rules=viral_rules())}]}]
    raw, spec = gemini(msgs, search=True)
    if spec:
        return msgs, raw, spec, True
    print("Google Search grounding unavailable: using the agencies' RSS feeds")
    items = rss_items(days=2 if HOT else 7)   # second Short of the day: only news of the last 48 hours
    if not items:
        sys.exit("No recent item readable from the feeds: no Short today.")
    block = "\n\n".join(f"[{i}] {it['title']} ({it['date']:%Y-%m-%d})\nURL: {it['url']}\nEXCERPT: {it['text']}"
                         for i, it in enumerate(items, 1))
    msgs = [{"role": "user", "parts": [{"text": RSS_PROMPT.format(today=today, hint=hint, used=used, items=block, rules=viral_rules())}]}]
    raw, spec = gemini(msgs, search=False)
    return msgs, raw, spec, False


# Reserve Shorts (owner decision 30/10/2026, option B): numbers that do not expire, from NASA fact sheets.
REF_PAGES = [f"https://nssdc.gsfc.nasa.gov/planetary/factsheet/{p}fact.html"
             for p in ("mercury", "venus", "earth", "moon", "mars", "jupiter", "saturn", "uranus", "neptune", "sun")]
REF_PROMPT = """You are the data writer of "Cosmos in Numbers", a faceless English YouTube Shorts channel about space:
real NASA footage and data, every number with a primary source. Today is {today}.
Below are NASA fact sheets. Write ONE evergreen "data" Short (numbers that do not expire, no news) about the
single most surprising measured number or comparison you can build from ONE or TWO of these sheets, NOT in this
list of topics already used: {used}
{items}

Write the Short using ONLY numbers that appear in the sheets you use. ONE idea, told as a story, not a list:
2 to 3 measured numbers in total (never more than 4), each with a vivid comparison a viewer can picture.
{rules}
Units in spoken words, never symbols ("kilograms per cubic meter", "meters per second", "times Earth"):
no "/", "^" or unit abbreviations in the narration.
- "narration": 80 to 95 words, plain spoken English. First sentence = the key number, no greeting or intro
  ("Did you know", "In this video" are forbidden). Short sentences. Every number exactly as written in the sheet
  (digits). Say "about" for rounded values. End with one sentence of why it matters.
- "title": max 80 characters plus " #shorts", curiosity + the number, ending with "(NASA data)".
- "headline": max 45 characters, shown on screen above the footage.
- "slug": 2-4 lowercase words joined by "-".
- "sources": [{{"title": "NASA <planet> Fact Sheet", "url": "<the sheet url, exactly>"}}]
- "description_intro": 1-2 sentences naming the NASA fact sheet(s).
- "footage_queries": 3 short queries (2-4 words) for the NASA Image and Video Library.
- "image_query": 1 query for a related NASA image.
Answer with JSON only:
{{"slug": "", "title": "", "headline": "", "narration": "", "description_intro": "", "sources": [], "footage_queries": [], "image_query": ""}}"""


def reserve_problems(spec) -> list[str]:
    """Extra rules of the reserve Shorts: they go out with no human reading them first."""
    out, n = [], spec.get("narration", "")
    data = [x for x in dict.fromkeys(numbers(n)) if not re.fullmatch(r"(19|20)\d\d", x)]
    if len(data) > 4:
        out.append(f"{len(data)} numbers in the narration (max 4: one idea, not a list)")
    if re.search(r"/|\^|\b(km|kg|mph)\b|\d\s?(K|m|s)\b|\bm \d\b", n):
        out.append("unit symbols in the narration (the voice must hear words)")
    return out


def write_reserve_spec(today):
    """Evergreen data Short from the NASA fact sheets, no grounding: same writers and same check() as the news."""
    week = int(datetime.now().strftime("%W"))
    pages = REF_PAGES[week % len(REF_PAGES):] + REF_PAGES[:week % len(REF_PAGES)]
    blocks = []
    for i, url in enumerate(pages[:5], 1):
        try:
            text = " ".join(page_text(url).split())[:2500]
        except Exception as e:  # noqa: BLE001
            print("  page failed", url, str(e)[:80])
            continue
        blocks.append(f"[{i}] URL: {url}\nSHEET: {text}")
    if not blocks:
        sys.exit("No NASA fact sheet readable: no reserve Short.")
    msgs = [{"role": "user", "parts": [{"text": REF_PROMPT.format(today=today, used=used_topics(), items="\n\n".join(blocks), rules=viral_rules())}]}]
    raw, spec = gemini(msgs, search=False)
    return msgs, raw, spec, False


def used_topics() -> str:
    seen = []
    f = ROOT / "governance" / "argomenti-usati.md"
    if f.exists():
        seen.append(f.read_text("utf-8")[-3000:])
    seen += [p.name for p in (ROOT / "04-produzione" / "shorts").glob("*") if p.is_dir()]
    seen += [p.name for p in (ROOT / "reserve").glob("*") if p.is_dir()]  # reserve Shorts not yet released
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


def article_text(url: str) -> str:
    """Paragraphs of the article only (no menus, sidebars, footers): <article>/<main> if present, then its <p>s."""
    host = urllib.parse.urlparse(url).hostname or ""
    if not any(host == d or host.endswith("." + d) for d in ALLOWED):
        raise ValueError(f"not a primary source domain: {host}")
    r = requests.get(url, headers=UA, timeout=60, allow_redirects=True)
    if r.status_code != 200:
        raise ValueError(f"HTTP {r.status_code}")
    t = re.sub(r"<(script|style|nav|header|footer|aside|form|noscript)\b[^>]*>.*?</\1>", " ", r.text, flags=re.S | re.I)
    m = re.search(r"<article\b.*?</article>", t, re.S | re.I) or re.search(r"<main\b.*?</main>", t, re.S | re.I)
    def ps(block):
        out = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", x)).split())
               for x in re.findall(r"<p\b[^>]*>(.*?)</p>", block, re.S | re.I)]
        return [x for x in out if len(x) >= 60 and not re.search(r"cookie|subscribe|share this|follow us", x, re.I)]

    paras = ps(m.group()) if m else []
    if sum(map(len, paras)) < 300:  # <article> was only a teaser: every paragraph of the page
        paras = ps(t)
    if not paras and m:  # article without <p>: its plain text
        paras = [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group())).split())]
    meta = re.search(r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="([^"]+)"', r.text, re.I)
    return " ".join(([html.unescape(meta.group(1))] if meta else []) + paras)


def numbers(text: str) -> list[str]:
    return [n.rstrip(".,") for n in re.findall(r"\d[\d,.]*", text) if n.rstrip(".,")]


# talking heads, briefings, title cards, mascots and posters: never the picture of a Short about a measured number
BAD_VISUAL = re.compile(r"presentation|briefing|news conference|press|interview|panel|podcast|episode|report|webcast|"
                        r"emoji|mascot|cartoon|clip ?art|poster|logo|infographic|live ?stream|\bq&a\b|\bsocial\b", re.I)
BAD_OPEN = re.compile(r"^\s*(did you know|in this video|today|welcome|hey|hello|have you ever|what if|imagine)\b", re.I)
BAD_END = re.compile(r"(subscribe|thanks for watching|see you|follow for|like and)", re.I)


def viral_problems(spec) -> list[str]:
    """Hard rules of the retention prompt: they trigger the same one-shot rewrite as a failed fact check."""
    n = spec.get("narration", "")
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", n.strip()) if x.strip()]
    out = []
    if not sents:
        return out
    if len(sents[0].split()) > 16:
        out.append(f"hook has {len(sents[0].split())} words (max 12-16: it must be spoken in under 3 seconds)")
    if BAD_OPEN.search(sents[0]):
        out.append("the opening is a greeting or a 'did you know' question")
    if not re.search(r"\d", sents[0]) and len(sents) > 1 and not re.search(r"\d", sents[1]):
        out.append("no number in the first two sentences")
    if BAD_END.search(sents[-1]):
        out.append("the last sentence is a sign-off: close the loop instead")
    long_ = [x for x in sents if len(x.split()) > 22]
    if long_:
        out.append(f"{len(long_)} sentence(s) over 22 words: split them")
    return out


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
           f"- Parole: {words} (obiettivo 85-110, minimo 60)", f"- Fonti lette: {len(texts)}/{len(spec.get('sources', []))}"]
    rep += [f"- PROBLEMA fonte: {p}" for p in problems]
    rep += [f"- Numeri nella narrazione: {', '.join(dict.fromkeys(numbers(spec['narration']))) or 'nessuno'}",
            f"- Numeri NON trovati nelle fonti: {', '.join(missing) or 'nessuno'}"]
    if not 60 <= words <= 125:  # 60 words at speed 1.2 are ~25 s, still a full Short
        problems.append(f"narration has {words} words")
    data = [n for n in dict.fromkeys(numbers(spec["narration"])) if not re.fullmatch(r"(19|20)\d\d", n)
            and not re.search(rf"[A-Za-z]-?{re.escape(n)}\b", spec["narration"])]  # X-59, JWST-1 are names
    rep.append(f"- Dati numerici (esclusi anni e nomi): {', '.join(data) or 'nessuno'}")
    if len(data) < 2:
        problems.append(f"only {len(data)} real numbers in the narration (need 2: no data, no Short)")
    if OFF_TOPIC.search(" ".join([spec.get("title", ""), spec.get("headline", "")] + [s.get("url", "") for s in spec.get("sources", [])])):
        problems.append("off topic for the channel (aeronautics, education or agency business)")
    if not texts:
        problems.append("no readable primary source")
    vp = viral_problems(spec)
    problems += vp
    rep += [f"- Regole retention: {'; '.join(vp) or 'ok'}"]
    return missing, problems, "\n".join(rep) + "\n"


def nasa_items(query, media):
    q = urllib.parse.quote(query)
    return stock.nasa(f"/search?q={q}&media_type={media}")["collection"]["items"]


def fetch_image(it, news_dir, assets, key):
    """Download one NASA library image item into the material folder and register it. Returns the key or None."""
    d = it["data"][0]
    files = stock.get_json(f"https://images-assets.nasa.gov/image/{urllib.parse.quote(d['nasa_id'])}/collection.json", {})
    jpg = next((f for t in ("~large.jpg", "~medium.jpg", "~orig.jpg") for f in files if f.endswith(t)), None)
    if not jpg:
        return None
    rel = f"assets/stock/nasa-img-{re.sub(r'[^A-Za-z0-9_-]', '_', d['nasa_id'])}.jpg"
    stock.download(jpg.replace("http://", "https://"), news_dir / rel)
    concept = any(w in (d.get("description", "") + d["title"]).lower() for w in ("concept", "illustration", "rendering", "artist"))
    assets[key] = {"file": rel, "type": "image", "kind": "illustration" if concept else "photo",
                   "title": d["title"], "source": f"https://images.nasa.gov/details/{d['nasa_id']}",
                   "credit": "NASA" + (f"/{d['center']}" if d.get("center") else ""),
                   "license": "NASA media usage guidelines (generally not copyrighted; no endorsement, no logos)",
                   "check": "ok"}
    return key


def nasa_image(query, news_dir, assets):
    for it in nasa_items(query, "image")[:5]:
        if fetch_image(it, news_dir, assets, "img_main"):
            return "img_main"
    return None


def footage(spec, news_dir) -> list[dict]:
    """Download >= 2 NASA clips and maybe 1 image; return the visuals list (clip first)."""
    news_dir.mkdir(parents=True, exist_ok=True)
    if not (news_dir / "assets.yaml").exists():  # stock.get reads the register before adding to it
        save_yaml(news_dir / "assets.yaml", {})
    picked, seen, results = [], set(), {}
    stop = set("the and for with from this that nasa space new first about into over than more most what when your are was were has have had its not".split())
    subject = " ".join(spec.get("footage_queries", []) + [spec.get("image_query", "")])
    names = re.findall(r"\b[A-Z][a-z0-9]{3,}\b", spec.get("title", "") + " " + spec.get("headline", ""))   # Mars, Jupiter, Leonid
    names_l = {n.lower() for n in names if n.lower() not in stop | {"will", "apart", "degrees", "every", "hour", "hours", "week", "year"}}
    topic = {w for w in re.findall(r"[a-z0-9]{4,}", (subject + " " + " ".join(names)).lower())
             if w not in stop | {"will", "apart", "degrees", "video", "image", "footage", "science", "visualization"}}

    def relevance(it) -> int:
        """How many story words (mission, object, telescope) appear in the clip's NASA title and description."""
        d = it["data"][0]
        if BAD_VISUAL.search(d.get("title", "")):
            return 0
        hay = (d.get("title", "") + " " + d.get("description", "")[:400] + " " + " ".join(d.get("keywords", []))).lower()
        return sum(1 for w in topic if w in hay)

    strict = [True]

    def take(q, per_query):
        """Download up to per_query new clips of query q; stops at 3 clips in total."""
        if q not in results:
            try:
                results[q] = sorted(nasa_items(q, "video")[:12], key=lambda it: -relevance(it))[:8]  # on-topic first
            except Exception as e:  # noqa: BLE001
                print("  NASA search failed:", q, e)
                results[q] = []
            print(f"  NASA '{q}': {len(results[q])} videos")
        got = 0
        for it in results[q]:
            if got >= per_query or len(picked) >= 4:
                return
            sid = it["data"][0]["nasa_id"]
            if sid in seen:
                continue
            if strict[0] and relevance(it) < 1:   # the viewer sees Hubble repair footage in a Mars story: not shown
                continue
            seen.add(sid)
            key = f"vid_{len(picked) + 1}"
            try:
                stock.get("nasa-video", sid, news_dir, key)
            except BaseException as e:  # noqa: BLE001 - a broken item must not stop the others
                print("  skip", sid, str(e)[:120])
                continue
            picked.append(key)
            got += 1

    queries = [q for q in spec.get("footage_queries", [])[:4] if q.strip()]
    for q in queries:  # one clip per story query first, for variety
        take(q, 1)
    for q in queries:  # then more from the same queries (4 clips: a cut every few seconds, not one long shot)
        if len(picked) < 4:
            take(q, 2)
    assets = stock.load_yaml(news_dir / "assets.yaml")
    # on-topic NASA images (Mars story -> Mars pictures) fill the cuts that no on-topic clip covers
    imgs, seen_img = [], set()
    short_qs = [" ".join(q.split()[:2]) for q in queries] + sorted(names_l)   # long queries find little: try 2 words, then each name
    for q in dict.fromkeys([spec.get("image_query", "")] + queries + short_qs):
        if len(imgs) >= 4 or not q.strip():
            continue
        try:
            items = sorted(nasa_items(q, "image")[:20], key=lambda it: -relevance(it))
        except Exception as e:  # noqa: BLE001
            print("  NASA image search failed:", q, e)
            continue
        print(f"  NASA images '{q}': {len(items)} found, {sum(1 for it in items if relevance(it) >= 1)} on topic")
        for it in items:
            nid = it["data"][0]["nasa_id"]
            if len(imgs) >= 4 or nid in seen_img or relevance(it) < 1:
                continue
            seen_img.add(nid)
            try:
                k = fetch_image(it, news_dir, assets, f"img_{len(imgs) + 1}")
            except BaseException as e:  # noqa: BLE001
                print("  skip image", nid, str(e)[:100])
                continue
            if k:
                imgs.append(k)
    print(f"  on-topic visuals: {len(picked)} clips + {len(imgs)} images (topic words: {sorted(topic)[:8]})")
    if len(picked) < 1 or len(picked) + len(imgs) < 3:
        # not enough on-topic material: old behaviour, key words and generic NASA footage up to 2 real clips
        strict[0] = False
        words = [w for q in queries for w in q.split() if len(w) > 3 and w.lower() not in ("nasa", "with", "from", "space")]
        for q in list(dict.fromkeys(words))[:4] + ["Hubble space telescope", "James Webb Space Telescope", "deep space"]:
            if len(picked) >= 2:
                break
            take(q, 1)
        assets = {**stock.load_yaml(news_dir / "assets.yaml"), **{k: v for k, v in assets.items() if k.startswith("img_")}}
    if len(picked) < 2 and not imgs:
        sys.exit(f"Only {len(picked)} NASA clips found: Short not built (rule: at least 2 real clips).")
    save_yaml(news_dir / "assets.yaml", assets)
    vids = []
    for k in picked:
        dur = media_duration(news_dir / assets[k]["file"])
        vids.append({"src": k, "start": round(min(8.0, dur * 0.2), 1), "_dur": dur})  # skip title cards at the start
    visuals = []
    for n in range(max(len(vids), len(imgs))):   # clip, picture, clip, picture: the look changes at every cut
        if n < len(vids):
            visuals.append({k: v for k, v in vids[n].items() if k != "_dur"})
        if n < len(imgs):
            visuals.append({"src": imgs[n], "motion": "zoom_in" if n % 2 == 0 else "zoom_out"})
    for v in vids:   # a second, different stretch of the longer clips: a real cut at least every ~6 s
        if v["_dur"] >= 16 and len(visuals) < 7:
            visuals.append({"src": v["src"], "start": round(min(v["_dur"] - 7.0, v["_dur"] * 0.55), 1)})
    return visuals


def same_story(slug: str, days: int = 5) -> str | None:
    """Tag of a release of the last `days` days on the same story (a shared word of 5+ letters in the slug)."""
    r = subprocess.run(["gh", "release", "list", "--limit", "20", "--json", "tagName,createdAt"], capture_output=True, text=True)
    if r.returncode:
        return None
    words = {w for w in slug.split("-") if len(w) >= 5}
    cutoff = datetime.now().timestamp() - days * 86400
    for rel in json.loads(r.stdout or "[]"):
        try:
            when = datetime.fromisoformat(rel["createdAt"].replace("Z", "+00:00")).timestamp()
        except (KeyError, ValueError):
            continue
        tag_words = {w for w in rel["tagName"].split("-")[1:] if len(w) >= 5}
        if when >= cutoff and words & tag_words:
            return rel["tagName"]
    return None


def write_checked(a, today, hint):
    """Write the Short, fact-check it, one rewrite if needed: (spec, missing numbers, problems, report)."""
    msgs, raw, spec, search = write_reserve_spec(today) if "--reserve" in a else write_spec(today, hint)
    if spec.get("skip"):
        return spec, [], [], ""
    missing, problems, report = check(spec)
    if "--reserve" in a:
        problems += reserve_problems(spec)
    if missing or problems:
        print("first draft rejected:", missing, problems)
        msgs += [{"role": "model", "parts": [{"text": raw}]},
                 {"role": "user", "parts": [{"text": FIX.format(missing=", ".join(missing) or "none") +
                                             (" Source problems: " + "; ".join(problems) if problems else "")}]}]
        raw, spec = gemini(msgs, search=search)
        if not spec or not spec.get("narration"):
            return {"skip": "the rewrite came back without a narration (" + str((spec or {}).get("skip", "no JSON"))[:120] + ")"}, [], [], ""
        missing, problems, report = check(spec)
        if "--reserve" in a:
            problems += reserve_problems(spec)
    return spec, missing, problems, report


def main():
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # log lines in order in Actions
    global FORMAT_RULES
    a = sys.argv[1:]
    today = datetime.now().strftime("%Y-%m-%d")
    opt = {k: a[a.index(f"--{k}") + 1] for k in ("format", "hook", "idea", "source") if f"--{k}" in a}
    FORMAT_RULES = format_rules(opt.get("format", ""), opt.get("hook", ""))
    t0, timing = time.time(), {}   # seconds per phase (viral engine, step 3: measure before optimising)
    if FORMAT_RULES:
        print("variant:", opt)
    if "--spec" in a:
        spec = json.loads(Path(a[a.index("--spec") + 1]).read_text("utf-8"))
        missing, problems, report = check(spec)
    else:
        hint = f"Prefer this topic if there is fresh news on it: {a[a.index('--topic') + 1]}." if "--topic" in a else ""
        if HOT:
            hint += (" HOT NEWS slot: pick ONLY a story published in the last 48 hours, the one people will talk about today,"
                     " and NOT the topic of today's first Short (in the list of used topics).")
        spec, missing, problems, report = write_checked(a, today, hint)
        if (missing or problems or spec.get("skip")) and FORMAT_RULES:
            # the variant under test did not fit today's material: one plain attempt, never a lost day for a test
            print("variant failed, plain Short instead:", missing, problems, spec.get("skip", ""))
            FORMAT_RULES = ""
            opt = {"source": "fallback", "tried": opt.get("format", "")}   # counted by the weekly cap, never as a result
            hint = ""
            spec, missing, problems, report = write_checked(a, today, hint)
        if spec.get("skip"):
            sys.exit(f"Gemini found no space news with real data today: {spec['skip']}")
    timing["write_s"] = round(time.time() - t0)
    print(report)
    if missing or problems:
        sys.exit("FACT CHECK FAILED: no Short today. " + "; ".join(problems + [f"number {n} not in sources" for n in missing]))
    slug = re.sub(r"[^a-z0-9-]", "", spec["slug"].lower())[:40] or "news"
    if HOT:
        dup = same_story(slug)
        if dup:
            sys.exit(f"HOT slot: the story '{slug}' is already out as {dup}: no second Short today.")
    prefix = a[a.index("--prefix") + 1] if "--prefix" in a else ("r" if "--reserve" in a else "a")
    sid = f"{prefix}{datetime.now():%m%d}-{slug}"
    base = OUT / sid
    news_dir, short_dir = base / "material", base / "short"
    print("Short:", sid, "|", spec["title"])
    print(spec["narration"])
    if DRY:
        print("DRY-RUN: no footage, no render.")
        return
    t1 = time.time()
    visuals = footage(spec, news_dir)
    timing["footage_s"] = round(time.time() - t1)
    t1 = time.time()
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
    timing["render_s"] = round(time.time() - t1)
    timing["total_s"] = round(time.time() - t0)
    mp4 = short_dir / "out" / f"{sid}.mp4"
    dur = media_duration(mp4)
    if not 20 <= dur <= (45 if "--reserve" in a else 60):
        sys.exit(f"QC: duration {dur:.1f}s outside 20-60 s")
    labels = {**opt, "format_fit": spec.get("format_fit", True) is not False, "topic": a[a.index("--topic") + 1] if "--topic" in a else ""}
    if not labels["format_fit"]:
        labels.pop("format", None)   # the writer could not follow it: tools/experiments.py infers it from the title
    meta = {"id": sid, "title": title, "duration": round(dur, 1), "mp4": str(mp4), "narration": spec["narration"],
            "upload": str(short_dir / "out" / "upload.md"), "factcheck": str(base / "factcheck.md"), "labels": labels,
            "timing": timing}
    (base / "result.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), "utf-8")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"id={sid}\ndir={base}\n")
    print("OK", json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
