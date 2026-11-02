"""Weekly long video written, checked and approved by code (owner 30/10/2026: "approva i video in automatico").

  python longform_auto.py [--topic "<hint>"] [--dry-run]

1. Plan: Gemini with Google Search picks ONE topic for an 8-10 minute video and 3-6 primary pages (NASA, JPL, ESA,
   ESO, STScI...). Without grounding quota: the NASA fact sheets. The code downloads every page (allowed domain,
   HTTP 200); the writer sees only their text.
2. Script in "beats" (1-2 sentences, one visual each, a new picture every ~5 s), built on what works for the
   competitors (research/cosmos/gemini-*.md): a myth or a striking number in the first sentence, numbers shown as
   physical comparisons (scale, timer, compare, counter), open questions, a re-hook in every chapter, a payoff.
3. Checks, all by code except the reviewer:
   - facts: every number of the narration and of the on-screen visuals is in the text of the sources;
   - reviewer: a second model (Groq if GROK_API_KEY, else Gemini) reads script + sources and lists unsupported or
     overstated claims; any "high" one fails;
   - script: length, hook, beat length, open questions per chapter, share of motion graphics and of real footage,
     no three equal visuals in a row, banned phrasing (qc.BANNED + clichés), LOOK UP only at the end, title.
   Failures go back to the writer (2 rounds max); still failing: exit 1 (the workflow opens an issue).
4. Assets: NASA Image and Video Library (stock.py), credits in assets.yaml; at least 6 real clips or photos.
Output: longform/<id>/ (script.yaml with approved: true, assets.yaml, assets/, thumbs.yaml, factcheck.md); the
workflow commits it and starts longform-build. Never uploads.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import auto_short as a  # noqa: E402
import claude_cli  # noqa: E402
import glm  # noqa: E402
import qc  # noqa: E402
import stock  # noqa: E402
from common import ROOT, media_duration, save_yaml  # noqa: E402

LONG = ROOT / "longform"
FACTSHEETS = ["https://nssdc.gsfc.nasa.gov/planetary/factsheet/"]
# length target: ~163 spoken words a minute at voice speed 1.1 (P6: 1,319 words = 8.23 min at 1.08)
LEN = {"mmin": 8, "mmax": 10, "wmin": 1350, "wmax": 1550, "cmin": 6, "cmax": 8}
DRY = "--dry-run" in sys.argv
MOTION = {"counter", "scale", "timer", "compare", "bars", "kinetic"}
REAL = {"footage", "image"}
CLICHES = [r"\bin this video\b", r"\bdid you know\b", r"\bsmash (?:that|the) like\b", r"\bwithout further ado\b",
           r"\bbuckle up\b", r"\bmind[- ]blowing\b", r"\byou won'?t believe\b", r"\blet'?s dive in\b"]

PLAN = """You plan the weekly long video of "Cosmos in Numbers", a faceless English YouTube channel about space:
real NASA/ESA footage and data, every number from a primary source. Today is {today}. {hint}
Pick ONE topic for an 8-10 minute video that a general audience would click and watch to the end: a question with
a surprising, measurable answer (scale, time, speed, distance, temperature, "what if", ranking, myth vs data),
NOT one of these topics already used: {used}
Ideas that work for the most-watched space channels this week (use the angle, never copy titles or edits):
{research}
Use Google Search to find 3 to 6 primary pages with the numbers you need (nasa.gov, science.nasa.gov, jpl.nasa.gov,
esa.int, esawebb.org, esahubble.org, eso.org, stsci.edu, noirlab.edu, nssdc.gsfc.nasa.gov).
Answer JSON only: {{"topic": "", "angle": "one sentence", "sources": [{{"title": "", "url": ""}}]}}"""

WRITE = """You write the script of a long YouTube video for "Cosmos in Numbers" (faceless, English, synthetic voice,
real NASA/ESA footage, animated data graphics). Topic: {topic}. Angle: {angle}.
Use ONLY facts and numbers that appear in the SOURCES below; write every number in digits exactly as in a source
(say "about" when rounding). Never invent a number, a date, a quote or a mission detail.

RETENTION (this is what keeps people watching to the end):
- Sentence 1 (the first 5 seconds, max 14 words): a question or a promise, built on a common belief that is
  wrong or on the single most striking number. No greeting, no "In this video", no "Did you know".
- The first 30 seconds (about 75 words) decide retention: a question, the stakes, the promise of the payoff ("by the
  end you'll know ..."), and one first surprising fact. Keep 1-2 open questions alive at all times.
- About every 2 minutes (every ~{recap_every} words) one beat is a one-sentence recap of what we know so far plus
  the next question: mark that beat with "recap": true.
- The channel's stick man is the human scale: on footage/image beats where size matters add
  "stickman": {{"label": "YOU", "size": "small|tiny|big"}} (tiny = you are a dot next to this). Use it on at least 6
  beats, spread through the video.
- {chapters} chapters; every chapter ends on a question or a twist that pulls into the next; escalate the scale or the
  stakes chapter by chapter; the biggest reveal near the end.
- Turn numbers into things people can picture: comparisons of size, travel times, "X Earths would fit".
- Short spoken sentences. Total narration {wmin:,} to {wmax:,} words (the video must last {mmin}-{mmax} minutes):
  beats of 18-28 words each, 8-10 beats per chapter. Count your words before answering.
- Say the numbers as the sources print them, with the same decimals. A number you compute (sum, difference,
  ratio, conversion) is allowed only if that beat has "calc": "6378.1 + 3474.8 = 9852.9" with source numbers on the
  left: the code redoes the arithmetic and rejects mistakes. Otherwise change the sentence, not the number.
- Last chapter: payoff, one sentence on why it matters, then ONE sentence inviting viewers who want to see these
  objects in the real sky to the beginner's stargazing guide "LOOK UP" (link in the description). Nowhere else.

BEATS: each chapter is a list of beats; a beat is 1-2 sentences (max 30 words) said over ONE visual (~5 s).
Visual types ("show"):
- {{"type": "footage", "query": "2-4 words for the NASA video library (mission, telescope, planet)", "stickman": optional}}
- {{"type": "image", "query": "2-4 words for the NASA image library", "stickman": optional}}
- {{"type": "counter", "value": 384400, "suffix": " km", "label": "EARTH TO MOON", "sub": "short line"}}
- {{"type": "scale", "title": "", "items": [{{"label": "Earth", "value": 12756, "display": "12,756 km"}}, ...2-4 items]}}
- {{"type": "timer", "seconds": 500, "label": "SUNLIGHT TO EARTH", "display": "about 8 min 20 s"}}
- {{"type": "compare", "title": "", "items": [{{"label": "", "value": 0, "suffix": ""}}, {{"label": "", "value": 0, "suffix": ""}}]}}
- {{"type": "bars", "title": "", "items": [{{"label": "", "value": 0, "display": ""}}], "log": false, "note": "Source: ..."}}
- {{"type": "kinetic", "text": "max 7 words", "accent": ["ONE", "WORD"]}}
At least 40% of beats must be data graphics (counter/scale/timer/compare/bars/kinetic) and at least 30% real
footage or images; never three beats in a row with the same type. Values on screen come from the sources too.

SOURCES:
{sources}

Answer JSON only:
{{"id": "2-4 lowercase words joined by -", "title": "max 70 characters with a number, curiosity, no lie",
 "alt_titles": ["", ""], "description_intro": "2 sentences naming the sources", "tags": ["8-12 search phrases"],
 "hashtags": ["space", "nasa", "astronomy"], "thumbs": [{{"lines": ["2-3 WORDS", "PER LINE"], "query": "NASA image query"}}, 2 more; the third with "stickman": true],
 "chapters": [{{"title": "", "sources": ["S1"], "beats": [{{"say": "", "show": {{}}, "calc": "optional"}}]}}]}}"""

REVIEW = """You are a strict science fact-checker. Below are the SOURCES and a SCRIPT written from them. List every
claim in the script that the sources do not support, that overstates them (certainty, "first", "largest", "proves"),
or that is misleading for a general audience. Rounding with "about" is fine. Do not list style issues.
SOURCES:
{sources}

SCRIPT:
{script}

Answer JSON only: {{"issues": [{{"claim": "", "problem": "", "severity": "high|medium|low"}}]}}"""

FIX = """Your script failed these checks:
{problems}
Rewrite the whole script fixing every point (same JSON format, same rules, only numbers from the sources)."""


def llm(msgs: list) -> tuple[str, dict]:
    """Gemini without search, room for a 15-minute script (maxOutputTokens), JSON checked; a truncated or broken
    answer moves to the next model, then to the backup writer (Groq)."""
    import os
    import time
    import requests
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        for attempt in range(6):
            m = a.gemini_models(key)[attempt % len(a.gemini_models(key))]
            try:
                r = requests.post(a.GEMINI.format(model=m), params={"key": key}, timeout=300, json={
                    "contents": msgs, "generationConfig": {"temperature": 0.5, "responseMimeType": "application/json",
                                                           "maxOutputTokens": 60000}})
                if r.status_code != 200:
                    print(f"  Gemini {m} HTTP {r.status_code}", flush=True)
                    time.sleep(20)
                    continue
                text = "".join(x.get("text", "") for x in r.json()["candidates"][0]["content"]["parts"])
                return text, json.loads(text[text.index("{"): text.rindex("}") + 1])
            except (ValueError, KeyError, IndexError, requests.RequestException) as e:
                print(f"  Gemini {m}: unusable answer ({type(e).__name__})", flush=True)
    out = ((claude_cli.chat(msgs, timeout=900) if claude_cli.available() else None)
           or (glm.chat(msgs, max_tokens=32000, timeout=600) if glm.available() else None) or a.backup_llm(msgs))
    if not out:
        sys.exit("No writer available (Gemini, GLM and backup).")
    return out


def research_notes() -> str:
    notes = sorted((ROOT / "research" / "cosmos").glob("gemini-*.md"))[-3:]
    out = []
    for f in notes:
        for m in re.finditer(r"^## (.+?)\n.*?### 6\.(.*?)(?=^### 7|\Z)", f.read_text("utf-8"), re.S | re.M):
            out.append(f"- {m.group(1)[:90]}: {' '.join(m.group(2).split())[:300]}")
    return "\n".join(out[-6:]) or "- (none this week)"


def used() -> str:
    seen = [p.name for p in LONG.glob("*") if p.is_dir()]
    return "; ".join(seen) + "; " + a.used_topics()[-2500:]


def plan(today: str, hint: str) -> dict:
    msgs = [{"role": "user", "parts": [{"text": PLAN.format(today=today, hint=hint, used=used(), research=research_notes())}]}]
    _, p = a.gemini(msgs, search=True)
    if not p or not p.get("sources"):
        print("No grounded plan: NASA fact sheets instead")
        _, p = a.gemini([{"role": "user", "parts": [{"text": PLAN.format(today=today, hint=hint, used=used(),
                         research=research_notes()) + "\nNo search available: pick a topic that NASA's planetary "
                         "fact sheets (planets, Moon, Sun) can fully answer; the writer gets all of them."}]}], search=False)
        p["sources"] = [{"title": "NASA Planetary Fact Sheet (all planets)", "url": FACTSHEETS[0]}] + [
            {"title": f"NASA {u.split('/')[-1].replace('fact.html', '').title()} Fact Sheet", "url": u} for u in a.REF_PAGES]
    return p


def fetch_sources(p: dict) -> list[dict]:
    out = []
    for s in p.get("sources", [])[:11]:
        try:
            text = " ".join(a.page_text(s["url"]).split())
        except Exception as e:  # noqa: BLE001
            print("  source refused:", s.get("url"), str(e)[:80])
            continue
        if len(text) > 400:
            out.append({"id": f"S{len(out) + 1}", "title": s.get("title") or s["url"], "url": s["url"], "text": text[:7000]})
    if len(out) < 2:
        sys.exit(f"Only {len(out)} readable primary sources: no long video this week.")
    return out


def beats(spec: dict) -> list[tuple[int, dict]]:
    out = []
    for i, ch in enumerate(spec.get("chapters", [])):
        if not isinstance(ch, dict):
            continue
        bs = ch.get("beats", [])
        ch["beats"] = [b if isinstance(b, dict) else {"say": str(b), "show": {"type": "kinetic", "text": str(b)[:40]}}
                       for b in bs]
        out += [(i, b) for b in ch["beats"]]
    return out


def calc_results(spec: dict, blob: str, flat: str) -> tuple[set, list[str]]:
    """Derived numbers declared by the writer as "calc": "6378.1 + 3474.8 = 9852.9": operands must be in the
    sources, the arithmetic is redone here (1% tolerance for rounding). Returns (allowed results, problems)."""
    ok, bad = set(), []
    for _, b in beats(spec):
        c = str(b.get("calc", "")).replace(",", "").replace("×", "*").replace("x", "*")
        if not c or "=" not in c:
            continue
        expr, res = c.rsplit("=", 1)
        if not re.fullmatch(r"[\d.\s+\-*/()]+", expr) or not re.fullmatch(r"\s*[\d.]+\s*", res):
            bad.append(f"calc not readable: {b['calc']}")
            continue
        # operands: source numbers, results of earlier calcs, or powers of ten (unit conversions: 10^6 km -> km)
        prev = {x.replace(",", "") for x in ok}
        missing = [n for n in re.findall(r"\d+(?:\.\d+)?", expr) if n not in flat and len(n) > 1 and n not in prev
                   and n.rstrip("0").rstrip(".") not in prev and not re.fullmatch(r"10*", n)]
        try:
            val, want = eval(expr, {"__builtins__": {}}), float(res)  # noqa: S307 - digits and + - * / ( ) only
        except Exception:  # noqa: BLE001
            bad.append(f"calc not computable: {b['calc']}")
            continue
        if missing:
            bad.append(f"calc uses numbers not in the sources: {', '.join(missing)}")
        elif abs(val - want) > max(0.01 * abs(want), 0.5):
            bad.append(f"calc is wrong: {b['calc']} (correct: {val:,.1f})")
        else:
            ok |= {res.strip(), f"{want:,.0f}", f"{want:,.1f}", f"{round(want):,}", f"{want:g}"}
    return ok, bad


def visual_numbers(show: dict) -> list[str]:
    keep = [show.get(k, "") for k in ("label", "sub", "display", "title", "text", "note")]
    for it in show.get("items", []):
        keep += [it.get("label", ""), it.get("display", "")]
    if show.get("type") == "counter":
        keep.append(f"{show.get('value', '')}")
    return a.numbers(" ".join(str(k) for k in keep))


def fact_check(spec: dict, sources: list[dict]) -> list[str]:
    blob = " ".join(s["text"] for s in sources)
    flat = blob.replace(",", "").replace(" ", "")
    derived, problems = calc_results(spec, blob, flat)
    nums = []
    for _, b in beats(spec):
        nums += a.numbers(b.get("say", "")) + visual_numbers(b.get("show", {}))
    missing = []
    for n in dict.fromkeys(nums):
        plain = n.replace(",", "")
        if n in blob or plain in flat or n in derived or plain in {d.replace(",", "") for d in derived}                 or re.fullmatch(r"(19|20)\d\d", n):
            continue
        if re.fullmatch(r"\d", plain):  # single digits: counting words ("2 reasons"), not data
            continue
        try:  # 384400 on screen vs "384,400" or "384 400" in the page
            if f"{float(plain):,.0f}" in blob or f"{float(plain):g}" in blob:
                continue
        except ValueError:
            pass
        missing.append(n)
    return problems + [f"number {n} is not in any source (add a \"calc\" if it is computed)" for n in missing]


def script_check(spec: dict) -> list[str]:
    p, bs = [], beats(spec)
    chs = spec.get("chapters", [])
    says = [b.get("say", "") for _, b in bs]
    text = " ".join(says)
    words = len(text.split())
    wmin, wmax = LEN["wmin"], LEN["wmax"]
    if not wmin - 30 <= words <= wmax + 100:
        p.append(f"narration has {words} words (need {wmin:,}-{wmax:,}: the video must last {LEN['mmin']}-{LEN['mmax']} minutes)")
    if not LEN["cmin"] <= len(chs) <= LEN["cmax"]:
        p.append(f"{len(chs)} chapters (need {LEN['cmin']}-{LEN['cmax']})")
    recaps = sum(1 for _, b in bs if b.get("recap"))
    if recaps < max(2, LEN["mmin"] // 2 - 1):
        p.append(f"{recaps} recap beats (need one every ~2 minutes: at least {max(2, LEN['mmin'] // 2 - 1)})")
    sticks = sum(1 for _, b in bs if (b.get("show") or {}).get("stickman"))
    if sticks < 6:
        p.append(f"stick man on {sticks} beats (need at least 6, spread through the video)")
    first75 = " ".join(text.split()[:75])
    if "?" not in first75:
        p.append("no question in the first 30 seconds")
    first = re.split(r"(?<=[.!?])\s", says[0] if says else "")[0]
    if len(first.split()) > 16 or not ("?" in first or re.search(r"you('ll| will)|by the end", first, re.I)):
        p.append(f"first sentence ({len(first.split())} words) must be a question or a promise within 5 s (max 14 words)")
    long = [s[:40] for s in says if len(s.split()) > 32]
    if long:
        p.append(f"{len(long)} beats over 30 words (one picture every ~5 s): {long[:3]}")
    for i, ch in enumerate(chs[:-1]):
        tail = " ".join(b.get("say", "") for b in ch.get("beats", [])[-2:])
        if "?" not in " ".join(b.get("say", "") for b in ch.get("beats", [])) and not re.search(r"\bbut\b|\byet\b", tail, re.I):
            p.append(f"chapter {i + 1} '{ch.get('title', '')}' has no open question or twist")
    kinds = [b.get("show", {}).get("type") for _, b in bs]
    n = max(1, len(kinds))
    if sum(k in MOTION for k in kinds) / n < 0.38:
        p.append(f"only {sum(k in MOTION for k in kinds)}/{n} beats are data graphics (need 40%)")
    if sum(k in REAL for k in kinds) / n < 0.28:
        p.append(f"only {sum(k in REAL for k in kinds)}/{n} beats are real footage or images (need 30%)")
    runs = [i for i in range(2, len(kinds)) if kinds[i] == kinds[i - 1] == kinds[i - 2]]
    if runs:
        p.append(f"three equal visuals in a row at beats {runs[:5]}")
    bad = [k for k in kinds if k not in MOTION | REAL]
    if bad:
        p.append(f"unknown visual types {set(bad)}")
    for pat, why in qc.BANNED:
        if re.search(pat, text, re.I):
            p.append(f"banned phrasing: {why}")
    for pat in CLICHES:
        if re.search(pat, text, re.I):
            p.append(f"cliché: {pat}")
    look = [i for i, s in enumerate(says) if "LOOK UP" in s]
    if len(look) != 1 or look[0] < len(says) - 3:
        p.append("LOOK UP must appear exactly once, in the last 3 beats")
    t = spec.get("title", "")
    if not (20 <= len(t) <= 72 and re.search(r"\d", t)):
        p.append("title must be 20-70 characters with a number")
    for _, b in bs:
        s = b.get("show", {})
        if s.get("type") in ("scale", "bars") and len(s.get("items", [])) < 2:
            p.append(f"{s['type']} visual with fewer than 2 items")
        if s.get("type") == "compare" and len(s.get("items", [])) != 2:
            p.append("compare visual needs exactly 2 items")
        if s.get("type") == "timer" and not isinstance(s.get("seconds"), (int, float)):
            p.append("timer without seconds")
    return p


def review(spec: dict, sources: list[dict]) -> list[str]:
    src = "\n\n".join(f"[{s['id']}] {s['url']}\n{s['text'][:6000]}" for s in sources)
    scr = "\n".join(f"- {b.get('say', '')}" for _, b in beats(spec))
    msgs = [{"role": "user", "parts": [{"text": REVIEW.format(sources=src, script=scr)}]}]
    # the reviewer is GLM with reasoning on (the strongest model, and not the Gemini that wrote the script) when
    # GLM_API_KEY exists; else Groq/xAI as before
    out = ((claude_cli.chat(msgs, timeout=600) if claude_cli.available() else None)
           or (glm.chat(msgs, thinking=True, temperature=0.2, timeout=300) if glm.available() else None)
           or a.backup_llm(msgs))
    if not out:
        _, j = a.gemini(msgs, search=False)
    else:
        j = out[1]
    issues = j.get("issues", []) if j else []
    for it in issues:
        print(f"  review [{it.get('severity')}] {it.get('claim', '')[:80]}: {it.get('problem', '')[:120]}")
    return [f"reviewer: '{it.get('claim', '')[:120]}' - {it.get('problem', '')[:160]}"
            for it in issues if str(it.get("severity", "")).lower() == "high"]


# ---------- assets ----------
def nasa_asset(query: str, media: str, vdir: Path, key: str, taken: set) -> str | None:
    try:
        items = a.nasa_items(query, media)[:8]
    except Exception as e:  # noqa: BLE001
        print("  NASA search failed:", query, str(e)[:80])
        return None
    for it in items:
        d = it["data"][0]
        sid = d["nasa_id"]
        if sid in taken:
            continue
        try:
            if media == "video":
                stock.get("nasa-video", sid, vdir, key)
            else:
                files = stock.get_json(f"https://images-assets.nasa.gov/image/{urllib.parse.quote(sid)}/collection.json", {})
                jpg = next((f for t in ("~large.jpg", "~medium.jpg", "~orig.jpg") for f in files if f.endswith(t)), None)
                if not jpg:
                    continue
                rel = f"assets/stock/nasa-img-{re.sub(r'[^A-Za-z0-9_-]', '_', sid)}.jpg"
                stock.download(jpg.replace("http://", "https://"), vdir / rel)
                reg = stock.load_yaml(vdir / "assets.yaml") or {}
                concept = any(w in (d.get("description", "") + d["title"]).lower() for w in ("concept", "illustration", "rendering", "artist"))
                reg[key] = {"file": rel, "type": "image", "kind": "illustration" if concept else "photo", "title": d["title"],
                            "source": f"https://images.nasa.gov/details/{sid}",
                            "credit": "NASA" + (f"/{d['center']}" if d.get("center") else ""),
                            "license": "NASA media usage guidelines (generally not copyrighted; no endorsement, no logos)",
                            "check": "ok"}
                save_yaml(vdir / "assets.yaml", reg)
        except BaseException as e:  # noqa: BLE001
            print("  skip", sid, str(e)[:100])
            continue
        taken.add(sid)
        return key
    return None


def build_folder(spec: dict, sources: list[dict], report: str) -> Path:
    vid = re.sub(r"[^a-z0-9-]", "", spec["id"].lower())[:40] or "video"
    vid = f"{datetime.now():%y%m%d}-{vid}"
    vdir = LONG / vid
    vdir.mkdir(parents=True, exist_ok=True)
    save_yaml(vdir / "assets.yaml", {})
    taken, cache, motions = set(), {}, ["zoom_in", "pan_left", "zoom_out", "pan_right", "pan_up"]
    last_img, real = None, 0
    segments = []
    for ci, ch in enumerate(spec["chapters"]):
        visuals, weights, says = [], [], []
        for b in ch["beats"]:
            s, say = dict(b.get("show", {})), b["say"].strip()
            kind = s.pop("type", "kinetic")
            v = None
            if kind in REAL:
                media = "video" if kind == "footage" else "image"
                q = s.get("query", spec["id"].replace("-", " "))
                k = cache.get((q, media))
                if not k:
                    k = nasa_asset(q, media, vdir, f"{'vid' if media == 'video' else 'img'}_{len(cache) + 1}", taken)
                    if not k and media == "video":  # no clip: a photo of the same subject
                        k = nasa_asset(q, "image", vdir, f"img_{len(cache) + 1}", taken)
                    cache[(q, media)] = k
                if k:
                    real += 1
                    reg = stock.load_yaml(vdir / "assets.yaml")
                    if reg[k]["type"] == "video":
                        dur = media_duration(vdir / reg[k]["file"])
                        v = {"type": "video", "src": k, "start": round(min(8.0, dur * 0.2), 1)}
                        if s.get("stickman"):
                            v["stickman"] = s["stickman"] if isinstance(s["stickman"], dict) else {"label": "YOU"}
                    else:
                        v = {"type": "image", "src": k, "motion": motions[len(visuals) % len(motions)]}
                        if s.get("stickman"):
                            v["stickman"] = s["stickman"] if isinstance(s["stickman"], dict) else {"label": "YOU"}
                        last_img = k
            elif kind in MOTION:
                v = {"type": kind, **{k2: s[k2] for k2 in s if k2 != "query"}}
                if kind == "counter":
                    v.setdefault("count", 1.8)
                    v["value"] = float(v.get("value", 0))
                    v.setdefault("decimals", 0 if float(v["value"]).is_integer() else 1)
                if kind == "timer":
                    v["seconds"] = float(v.get("seconds", 0))
                if kind in ("compare", "scale", "bars"):
                    for it in v.get("items", []):
                        it["value"] = float(it.get("value", 0))
                        it.setdefault("decimals", 0 if it["value"].is_integer() else 1)
                if kind in ("counter", "kinetic", "compare", "timer") and last_img:
                    v.update(bg=last_img, dim=0.7)
            if not v:  # nothing found: the line on screen as kinetic text
                v = {"type": "kinetic", "text": " ".join(say.split()[:7]), "accent": []}
            visuals.append(v)
            weights.append(max(4, len(say.split())))
            says.append(say)
        segments.append({"id": f"c{ci + 1}", "chapter": "Intro" if ci == 0 else ch.get("title", f"Part {ci + 1}"),
                         "sources": [x for x in ch.get("sources", []) if x in {s['id'] for s in sources}] or ["S1"],
                         "narration": " ".join(says), "visuals": visuals, "weights": weights})
    if real < 6:
        sys.exit(f"Only {real} real NASA visuals found: no long video this week.")
    thumbs = {}
    for name, t in zip("ABC", spec.get("thumbs", [])[:3]):
        k = nasa_asset(t.get("query", spec["id"]), "image", vdir, f"thumb_{name}", taken) or last_img
        if k:
            thumbs[name] = {"bg": k, "lines": t.get("lines", [spec["title"][:20]])[:3], "accent": "amber" if name != "B" else "cyan",
                            "badge": "REAL NASA DATA", "side": "left", "focus": [0.5, 0.5], "highlight": 0,
                            "stickman": bool(t.get("stickman")) or name == "C"}
    save_yaml(vdir / "thumbs.yaml", thumbs)
    script = {"id": vid, "title": spec["title"], "alt_titles": spec.get("alt_titles", [])[:2], "voice": "af_heart",
              "speed": 1.1, "music": {"seed": int(datetime.now().strftime("%j")), "mood": "wonder"},
              "hashtags": spec.get("hashtags", ["space", "nasa"])[:3], "tags": spec.get("tags", [])[:12],
              "description_intro": spec.get("description_intro", ""), "progress_bar": True, "cut_sfx": True,
              "approved": True, "approved_by": "longform_auto.py (checks: facts, reviewer, script)",
              "sources": [{"id": s["id"], "title": s["title"], "url": s["url"]} for s in sources], "segments": segments}
    save_yaml(vdir / "script.yaml", script)
    (vdir / "factcheck.md").write_text(report, "utf-8")
    return vdir


def main():
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    args = sys.argv[1:]
    today = datetime.now().strftime("%Y-%m-%d")
    hint = f"Prefer this topic: {args[args.index('--topic') + 1]}." if "--topic" in args else ""
    if "--minutes" in args:  # e.g. 12-16 (owner 31/10/2026 for TON 618)
        lo, hi = (int(x) for x in args[args.index("--minutes") + 1].split("-"))
        LEN.update(mmin=lo, mmax=hi, wmin=lo * 163 + 60, wmax=hi * 150, cmin=max(6, lo // 2), cmax=max(8, hi // 2 + 1))
    if "--sources" in args:  # pages chosen by hand (e.g. when Google Search grounding has no quota)
        urls = [u.strip() for u in args[args.index("--sources") + 1].split(",") if u.strip()]
        _, p = llm([{"role": "user", "parts": [{"text": PLAN.format(today=today, hint=hint, used=used(),
                    research=research_notes()) + " No search: the sources are fixed, give only topic and angle."}]}])
        p["sources"] = [{"title": u, "url": u} for u in urls] + [
            {"title": f"NASA {n.title()} Fact Sheet", "url": f"https://nssdc.gsfc.nasa.gov/planetary/factsheet/{n}fact.html"}
            for n in ("sun", "earth")]
    else:
        p = plan(today, hint)
    print("Topic:", p.get("topic"), "|", p.get("angle"))
    sources = fetch_sources(p)
    src_block = "\n\n".join(f"[{s['id']}] {s['title']} ({s['url']})\n{s['text']}" for s in sources)
    msgs = [{"role": "user", "parts": [{"text": WRITE.format(
        topic=p.get("topic"), angle=p.get("angle"), sources=src_block, recap_every=330, wmin=LEN["wmin"], wmax=LEN["wmax"],
        mmin=LEN["mmin"], mmax=LEN["mmax"], chapters=f"{LEN['cmin']} to {LEN['cmax']}")}]}]
    history = []
    for rnd in range(3):
        raw, spec = llm(msgs)
        problems = fact_check(spec, sources) + script_check(spec)
        if not [x for x in problems if x.startswith("number")]:  # the reviewer only on drafts whose numbers are clean
            problems += review(spec, sources)
        history.append(f"Round {rnd + 1}: {len(problems)} problem(s)" + "".join(f"\n  - {x}" for x in problems))
        print(history[-1])
        if not problems:
            break
        msgs += [{"role": "model", "parts": [{"text": raw}]},
                 {"role": "user", "parts": [{"text": FIX.format(problems="\n".join(f"- {x}" for x in problems))}]}]
    else:
        sys.exit("CHECKS FAILED after 3 drafts: no long video this week.\n" + "\n".join(history))
    words = sum(len(b.get("say", "").split()) for _, b in beats(spec))
    report = "\n".join([f"# Controlli automatici ({datetime.now():%Y-%m-%d %H:%M})", "",
                        f"Argomento: {p.get('topic')} ({p.get('angle')})", f"Parole: {words}; capitoli: {len(spec['chapters'])}; "
                        f"battute: {len(beats(spec))}", "", "## Esito per giro", *history, "",
                        "## Fonti", *[f"- {s['id']} {s['title']}: {s['url']}" for s in sources], "",
                        "Approvato dal codice: ogni numero è nelle fonti, il revisore non ha trovato problemi gravi, "
                        "struttura e ritmo nei limiti. Nessuna revisione umana."]) + "\n"
    print(report)
    if DRY:
        print(json.dumps(spec, ensure_ascii=False, indent=1)[:4000])
        return
    vdir = build_folder(spec, sources, report)
    print("OK", vdir.name)
    import os
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"id={vdir.name}\n")


if __name__ == "__main__":
    main()
