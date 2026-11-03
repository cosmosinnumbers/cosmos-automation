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
SKIP_GEMINI = False  # act mode with Gemini down: straight to the free writers, no 2-minute retries per call
MOTION = {"counter", "scale", "timer", "compare", "bars", "kinetic"}
REAL = {"footage", "image"}
ANNOUNCE = re.compile(r"\bchapter\b|\bpart (?:one|two|three|four|five|six|seven|eight|\d)\b|\bin this (?:section|part)\b|"
                      r"\b(?:first|next|last|final) (?:part|section)\b", re.I)
VAGUE = re.compile(r"\b(secrets?|myster(?:y|ies)|amazing|insane|shocking|truth|crazy|unbelievable|incredible)\b", re.I)
PRICE = re.compile(r"\$\s?\d|\b\d+ ?(?:dollars|euros?)\b|\bcode\b|\bdiscount\b|COSMOS9|LAUNCH9", re.I)
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
- ONE continuous story, no chapters for the viewer: the JSON groups beats in {chapters} "chapters" only for pacing
  (call them acts). NEVER say "chapter", "part one/two", "section", "first/next part" or announce a structure; move
  from act to act with a pulling sentence ("So if that is true, why would NASA...?"). Every act ends on a question or
  a twist that pulls into the next; escalate the scale or the stakes act by act; the biggest reveal near the end.
  Every act has ONE "wow" moment (a number or a comparison that makes the viewer say "no way"), placed in its first
  third, and opens by answering the question the previous act left hanging, then opens a new one. Every act uses
  at least 3 different image/footage queries.
- A turning point at about two thirds: something the viewer thought was true flips. Re-hook every 30-45 seconds
  with a short pull ("But here is the part nobody mentions.", "And that is not even the strange part.").
ENGAGEMENT (owner 03/11/2026: talk to the person watching, make them take part):
- Speak to the viewer: "you" all through the video (at least one sentence in five), "picture yourself...".
- At least 4 direct questions to the viewer, spread out; the first one in the first minute asks them to bet
  ("Before I tell you, guess: closer to 10 or to 100? Write it in the comments.").
- Exactly 2 beats with "ask": "a short question for the comments, max 12 words" (shown typed on screen): one in
  the first half, one in the last act. The beat's "say" asks it out loud.
- Once, right after the strongest "wow" moment (never at the start): one sentence inviting to follow, e.g.
  "If numbers like this make your day, follow: there is a new one every day."
- MID-VIDEO SPOT: exactly 1 beat with "spot": true between 35% and 65% of the video, right after delivering value:
  2 sentences, max 40 words, saying what LOOK UP is (our beginner's guide to finding in the real sky the things
  we talk about) and "link in the description". Never a price, never a discount code. Its visual is ignored.
- Turn numbers into things people can picture: comparisons of size, travel times, "X Earths would fit".
- Short spoken sentences. Total narration {wmin:,} to {wmax:,} words (the video must last {mmin}-{mmax} minutes):
  beats of 18-28 words each, 8-10 beats per chapter. Count your words before answering.
- Say the numbers as the sources print them, with the same decimals. A number you compute (sum, difference,
  ratio, conversion) is allowed only if that beat has "calc": "6378.1 + 3474.8 = 9852.9" with source numbers on the
  left: the code redoes the arithmetic and rejects mistakes. Otherwise change the sentence, not the number.
- Last act: payoff that echoes the hook, one sentence on why it matters, ONE sentence inviting viewers who want to
  see these objects in the real sky to the beginner's stargazing guide "LOOK UP" (link in the description), then the
  last "ask" question for the comments. "LOOK UP" is written exactly twice: in the spot and in the last 3 beats.

TITLE AND HOOK (copywriting, like the titles growing in the niche this week):
- Title: specific and clear in 2 seconds: the concrete subject plus a real number or a precise contrast
  ("Why NASA Will Fly Past Europa 49 Times", not "The Secret of Europa"); max 60 characters; ONE promise; never a
  vague word on its own (secret, mystery, amazing, insane, shocking, truth, crazy, unbelievable).
- Copy the STRUCTURE of these growing titles, never the words:
{trend_titles}
- The first sentence is the title's promise said differently, with the number or the contrast right away.
- 2 alt_titles with different hooks (paradox, extreme number, comparison, question, "you").

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
{{"id": "2-4 lowercase words joined by -", "title": "max 60 characters: subject + number or contrast, no lie",
 "alt_titles": ["", ""], "description_intro": "2 sentences naming the sources", "tags": ["8-12 search phrases"],
 "hashtags": ["space", "nasa", "astronomy"], "thumbs": [{{"lines": ["2-3 WORDS", "PER LINE"], "query": "NASA image query"}}, 2 more; the third with "stickman": true],
 "chapters": [{{"title": "", "sources": ["S1"], "beats": [{{"say": "", "show": {{}}, "calc": "optional", "ask": "optional", "spot": "optional true"}}]}}]}}"""

REVIEW = """You are a strict science fact-checker. Below are the SOURCES and a SCRIPT written from them. List every
claim in the script that the sources do not support, that overstates them (certainty, "first", "largest", "proves"),
or that is misleading for a general audience. Rounding with "about" is fine. Do not list style issues.
SOURCES:
{sources}

SCRIPT:
{script}

Answer JSON only: {{"issues": [{{"claim": "", "problem": "", "severity": "high|medium|low"}}]}}"""

RETENTION_REVIEW = """You are a YouTube retention editor, ruthless and specific. Read the narration below, written for a faceless
8-15 minute space-data video, and judge only how well it keeps strangers watching (not whether the facts are right).
Score 0-10: hook (does the first 20 s promise something concrete and extreme, no greeting), pacing (new information or
a visual idea every 30-45 s, no flat stretches), clarity (a 12 year old follows every sentence), originality (a
viewer has not heard this exact framing a hundred times), payoff (the end delivers what the hook promised and echoes it),
engagement (it talks to the viewer, asks them things, makes them want to comment; no announced chapters).
List up to 4 weak spots: the chapter number, the quoted weak sentence, why viewers leave there, and a concrete rewrite
instruction. Be honest: a 7 means good, a 9 is rare.
SCRIPT (chapter by chapter):
{script}

Answer JSON only: {{"scores": {{"hook": 0, "pacing": 0, "clarity": 0, "originality": 0, "payoff": 0, "engagement": 0}},
"weak": [{{"chapter": 1, "quote": "", "why": "", "fix": ""}}]}}"""

RETENTION_MIN = {"hook": 7, "pacing": 6, "clarity": 7, "originality": 6, "payoff": 6, "engagement": 7}

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
    if key and not SKIP_GEMINI:
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
    if not out:   # the free writers are often briefly over capacity: one more round after a minute
        print("  no writer answered: one more try in 60 s", flush=True)
        time.sleep(60)
        out = a.backup_llm(msgs)
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


def trend_titles(n: int = 8) -> str:
    """Examples of the formats and hooks growing this week (tools/trend_scout.py), for the title style."""
    files = sorted((ROOT / "research" / "cosmos").glob("trends-*.json"))
    if not files:
        return "- (no trend file this week)"
    try:
        t = json.loads(files[-1].read_text("utf-8"))
    except ValueError:
        return "- (no trend file this week)"
    vids = sorted(t.get("videos", []), key=lambda v: -(v.get("views_per_day") or 0))
    out = [f"- {v['title'][:90]} ({v.get('format')}, {v.get('hook')})" for v in vids if (v.get("seconds") or 0) > 180][:n]
    return "\n".join(out) or "- (no trend file this week)"


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
        msg = f"narration has {words} words (need {wmin:,}-{wmax:,}: the video must last {LEN['mmin']}-{LEN['mmax']} minutes)"
        if words < wmin and chs:   # models write short: say exactly how much to add, act by act
            per = -(-(wmin + 60 - words) // len(chs))
            acts = ", ".join(f"act {i + 1} {sum(len(b.get('say', '').split()) for b in ch.get('beats', []))} words"
                             for i, ch in enumerate(chs))
            msg += (f". ADD about {wmin + 60 - words} words: about {per} more words in EVERY act, i.e. "
                    f"{max(1, round(per / 22))} new beats of ~22 words each per act, with new facts from the sources "
                    f"(no padding). Now: {acts}")
        p.append(msg)
    if not LEN["cmin"] <= len(chs) <= LEN["cmax"]:
        p.append(f"{len(chs)} acts (need {LEN['cmin']}-{LEN['cmax']})")
    recaps = sum(1 for _, b in bs if b.get("recap"))
    if recaps < max(2, LEN["mmin"] // 2 - 1):
        p.append(f"{recaps} recap beats (need one every ~2 minutes: at least {max(2, LEN['mmin'] // 2 - 1)})")
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
            p.append(f"act {i + 1} '{ch.get('title', '')}' has no open question or twist")
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
    # engagement (owner 03/11/2026): one story without announced chapters, talk to the viewer, spot mid-video
    ann = [s[:50] for s in says if ANNOUNCE.search(s)]
    if ann:
        p.append(f"never announce chapters or parts (one continuous story): {ann[:2]}")
    you_q = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.endswith("?") and re.search(r"\byou(r)?\b", s, re.I)]
    if len(you_q) < 4:
        p.append(f"{len(you_q)} direct questions to the viewer (need at least 4, with 'you', spread through the video)")
    asks = [k for k, (_, b) in enumerate(bs) if str(b.get("ask") or "").strip()]
    if len(asks) != 2 or not asks or asks[0] > len(bs) / 2 or asks[-1] < len(bs) * 0.8:
        p.append(f"need exactly 2 'ask' beats (comment questions): one in the first half, one in the last act (found {len(asks)})")
    if any(len(str(bs[k][1]["ask"]).split()) > 12 for k in asks):
        p.append("an 'ask' question is longer than 12 words")
    spots = [k for k, (_, b) in enumerate(bs) if b.get("spot")]
    if len(spots) != 1 or not 0.35 <= spots[0] / max(1, len(bs)) <= 0.65:
        p.append(f"need exactly 1 'spot' beat (LOOK UP guide) between 35% and 65% of the video (found {len(spots)})")
    elif "LOOK UP" not in says[spots[0]] or len(says[spots[0]].split()) > 45:
        p.append("the spot beat must name LOOK UP and say 'link in the description' in max 40 words")
    look = [i for i, s in enumerate(says) if "LOOK UP" in s]
    if len(look) != 2 or look[-1] < len(says) - 3 or (spots and look[0] != spots[0]):
        p.append("LOOK UP must appear exactly twice: in the spot beat and in the last 3 beats")
    if PRICE.search(text):
        p.append("no price, discount or code in the narration (the code is only in the description)")
    for ci, ch in enumerate(chs):
        qs = {(b.get("show") or {}).get("query", "").lower() for b in ch.get("beats", []) if (b.get("show") or {}).get("type") in REAL}
        if len(qs - {""}) < 3:
            p.append(f"act {ci + 1} has {len(qs - {''})} different image/footage queries (need at least 3)")
    t = spec.get("title", "")
    if not (20 <= len(t) <= 66 and re.search(r"\d", t)):
        p.append("title must be 20-60 characters, specific, with the subject and a number")
    if VAGUE.search(t):
        p.append(f"vague word in the title ('{VAGUE.search(t).group(0)}'): name the concrete subject and the number")
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


def retention_review(spec: dict) -> tuple[list[str], dict]:
    """Second critic (Claude when available, else GLM/Groq): scores the script for retention. Returns (problems that
    send the script back for a rewrite, the scores for the report). No critic available -> no gate, no scores."""
    chs = []
    for ci, ch in enumerate(spec.get("chapters", []), 1):
        chs.append(f"## Act {ci} (internal, not shown): {ch.get('title', '')}\n" + "\n".join(f"- {b.get('say', '')}" for b in ch.get("beats", [])))
    msgs = [{"role": "user", "parts": [{"text": RETENTION_REVIEW.format(script="\n\n".join(chs))}]}]
    out = ((claude_cli.chat(msgs, timeout=600) if claude_cli.available() else None)
           or (glm.chat(msgs, thinking=True, temperature=0.3, timeout=300) if glm.available() else None)
           or a.backup_llm(msgs))
    j = out[1] if out else None
    if not j or not isinstance(j.get("scores"), dict):
        return [], {}
    sc = {k: float(v) for k, v in j["scores"].items() if isinstance(v, (int, float))}
    print("  retention scores:", sc)
    probs = [f"retention critic: {k} {sc[k]:.0f}/10 (need {m}+)" for k, m in RETENTION_MIN.items() if k in sc and sc[k] < m]
    if probs:   # only a failing score sends the script back, together with the concrete weak spots
        probs += [f"retention critic, chapter {w.get('chapter')}: '{str(w.get('quote', ''))[:100]}' - {str(w.get('why', ''))[:120]}. "
                  f"Fix: {str(w.get('fix', ''))[:160]}" for w in (j.get("weak") or [])[:4]]
    return probs, sc


# ---------- act mode (owner 03/11/2026: free models only, small blocks) ----------
# Without Gemini the backup writers (Groq free tier: a few thousand tokens a minute) cannot write a 1,400-word
# script in one answer. Act mode asks for an outline, then ONE act per call with only that act's sources, checks
# every act by code and rewrites only the failing ones; the whole script then goes through the same checks as
# before (fact_check, script_check, reviewer per act, retention critic). Nothing is approved that would fail them.

OUTLINE = """You plan the long YouTube video of "Cosmos in Numbers" (faceless, English, real NASA/ESA footage and
data graphics). Topic: {topic}. Angle: {angle}. One continuous story in {acts} acts (internal only, never announced).
Act 1 opens with a hook: a common belief that is wrong or the single most striking number. Each act answers the
question the previous one left hanging, has one "wow" number, escalates, and ends on a question or twist.
A turning point at about two thirds; the last act pays off the hook.
Use ONLY facts in these SOURCE EXCERPTS:
{sources}

Title rules: max 60 characters, the concrete subject plus a real number or a precise contrast, one promise, never a
vague word alone (secret, mystery, amazing, insane, shocking, truth, crazy, unbelievable). Copy the STRUCTURE of
these growing titles, never the words:
{trend_titles}

Answer JSON only:
{{"id": "2-4 lowercase words joined by -", "title": "", "alt_titles": ["", ""],
 "description_intro": "2 sentences naming the sources", "tags": ["8-12 search phrases"],
 "hashtags": ["space", "nasa", "astronomy"],
 "thumbs": [{{"lines": ["2-3 WORDS", "PER LINE"], "query": "NASA image query"}}, 2 more; the third with "stickman": true],
 "acts": [{{"title": "", "sources": ["S1"], "question_answered": "", "wow": "the act's striking fact, from the sources",
   "ends_with": "the question or twist that pulls into the next act"}}]}}"""

ACT = """You write ACT {n} of {total} of a long YouTube video for "Cosmos in Numbers" (faceless, English, synthetic
voice, real NASA/ESA footage, animated data graphics). Title: {title}. Topic: {topic}.
The whole story (internal acts, never announced to the viewer):
{outline}
{previous}
THIS ACT: "{act_title}". It answers: {answered}. Its wow moment (in its first third): {wow}. It ends with: {ends}.

Rules:
- Use ONLY facts and numbers in the SOURCES below; write every number in digits exactly as printed there (say
  "about" when rounding). A computed number needs "calc": "6378.1 + 3474.8 = 9852.9" with source numbers on the left.
  Fact sheets print many values in units like (10^6 km): to say 0.3844 (10^6 km) as 384,400 km write
  "calc": "0.3844 * 1000000 = 384400". Never invent a number, a date, a quote or a mission detail.
- {beats} beats, each 1-2 short spoken sentences of 18-28 words (never over 30) over ONE visual; AT LEAST {words}
  words in total for this act (count them: short acts are rejected). Speak to the viewer ("you", "picture yourself")
  at least once in 5 sentences, and at least one beat is a single direct question to the viewer that contains "you"
  and ends with "?" (e.g. "Can you guess how many Earths fit inside?").
- Visuals ("show"): at least {motion} beats with data graphics and at least {real} beats with real footage or images
  using at least 3 different queries; never three beats in a row with the same type. Types:
  {{"type": "footage", "query": "2-4 words for the NASA video library", "stickman": {{"label": "YOU", "size": "small|tiny|big"}} optional}}
  {{"type": "image", "query": "2-4 words for the NASA image library", "stickman": optional}}
  {{"type": "counter", "value": 384400, "suffix": " km", "label": "EARTH TO MOON", "sub": "short line"}}
  {{"type": "scale", "title": "", "items": [{{"label": "Earth", "value": 12756, "display": "12,756 km"}}, 2-4 items]}}
  {{"type": "timer", "seconds": 500, "label": "SUNLIGHT TO EARTH", "display": "about 8 min 20 s"}}
  {{"type": "compare", "title": "", "items": [{{"label": "", "value": 0, "suffix": ""}}, {{"label": "", "value": 0, "suffix": ""}}]}}
  {{"type": "bars", "title": "", "items": [{{"label": "", "value": 0, "display": ""}}], "log": false, "note": "Source: ..."}}
  {{"type": "kinetic", "text": "max 7 words", "accent": ["ONE", "WORD"]}}
  Values on screen come from the sources too.
- Never say "chapter", "part", "section", "in this video", "did you know"; no greetings; no price, discount or code.
{extra}
SOURCES:
{sources}

Answer JSON only: {{"title": "{act_title}", "beats": [{{"say": "", "show": {{}}}}, ...]}}
A beat may add "calc": "a + b = c" when it says a computed number.{keys}"""


def act_plan(total: int) -> list[dict]:
    """Where the code wants the structural beats (script_check positions): hook in act 1, a comment question in
    act 2 and in the last act, the LOOK UP spot at the start of the middle act, recaps spread out, the follow
    invitation once, the closing LOOK UP line in the last 3 beats."""
    mid = total // 2
    recaps = {1, 2, mid + 1, total - 2} - {0, total - 1}   # at least 3 recaps (one every ~2 minutes)
    out = []
    for i in range(total):
        e = []
        if i == 0:
            e.append("- This is the opening: the FIRST sentence (max 14 words) is a question or a promise built on the "
                     "most striking number or a wrong common belief; within the first 75 words a question to the viewer, "
                     "the stakes and the promise of the payoff (\"by the end you'll know ...\"). Ask the viewer to bet "
                     "(\"guess: closer to 10 or to 100? Write it in the comments.\").")
        if i == 1:
            e.append("- Exactly ONE beat has \"ask\": \"a question for the comments, max 12 words\" and says it out loud.")
        if i in recaps:
            e.append("- Exactly ONE beat has \"recap\": true: one sentence recapping what we know so far plus the next question.")
        if i == mid:
            e.append("- Beat 2 of this act has \"spot\": true: 2 sentences, max 40 words, saying what LOOK UP is (our "
                     "beginner's guide to finding in the real sky the things we talk about) and \"link in the "
                     "description\". \"LOOK UP\" appears nowhere else in this act.")
        if i == 2:
            e.append("- Right after the wow moment, one sentence inviting to follow: \"If numbers like this make your "
                     "day, follow: there is a new one every day.\"")
        if i == total - 1:
            e.append("- This is the last act: payoff that echoes the opening hook, one sentence on why it matters; in "
                     "the LAST 3 beats ONE sentence inviting viewers who want to see these objects in the real sky to "
                     "the beginner's stargazing guide \"LOOK UP\" (link in the description), and the very last beat "
                     "has \"ask\": \"a question for the comments, max 12 words\".")
        if i not in (mid, total - 1):
            e.append("- Do not write \"LOOK UP\" in this act.")
        if i not in (1, total - 1):
            e.append("- No beat with \"ask\" in this act.")
        keys = []
        if i in recaps:
            keys.append('ONE beat adds "recap": true.')
        if i in (1, total - 1):
            keys.append('ONE beat adds "ask": "the comment question".')
        if i == mid:
            keys.append('Beat 2 adds "spot": true.')
        out.append({"extra": "\n".join(e), "keys": (" " + " ".join(keys)) if keys else " No other keys.",
                    "ask": i in (1, total - 1), "spot": i == mid,
                    "recap": i in recaps, "lookup": i in (mid, total - 1)})
    return out


def flag_true(v) -> bool:
    return v is True or str(v).strip().lower() == "true"


def flag_text(v) -> str:
    """An "ask" question, or "" for the placeholders models copy from the template."""
    s = str(v or "").strip()
    return "" if s.lower() in {"", "optional", "none", "no", "false", "null", "n/a"} else s


def clean_flags(act: dict) -> dict:
    """Drop placeholder flags, so script_check counts only real ones."""
    for b in act["beats"]:
        for k in ("ask", "spot", "recap"):
            if k in b and not (flag_text(b[k]) if k == "ask" else flag_true(b[k])):
                b.pop(k)
        for k in ("spot", "recap"):
            if k in b:
                b[k] = True
    return act


def act_check(act: dict, rule: dict, words: int, sources: list[dict]) -> list[str]:
    """The script_check rules that can be judged on one act, plus its numbers against the sources."""
    p, bs = [], [b for b in act.get("beats", []) if isinstance(b, dict)]
    says = [str(b.get("say", "")) for b in bs]
    n = len(" ".join(says).split())
    if not words - 25 <= n <= words + 60:   # 6 acts at the low end still make the script's minimum
        p.append(f"this act has {n} words: write {words} (about {round(words / 22)} beats of ~22 words), "
                 f"{'ADD' if n < words else 'CUT'} about {abs(words - n)} words with facts from the sources")
    long = [s[:40] for s in says if len(s.split()) > 32]
    if long:
        p.append(f"{len(long)} beats over 30 words: {long[:2]}")
    kinds = [(b.get("show") or {}).get("type") for b in bs]
    if sum(k in MOTION for k in kinds) < 0.4 * len(kinds) - 0.5:
        p.append(f"only {sum(k in MOTION for k in kinds)}/{len(kinds)} beats are data graphics (need 40%)")
    if sum(k in REAL for k in kinds) < 0.3 * len(kinds) - 0.5:
        p.append(f"only {sum(k in REAL for k in kinds)}/{len(kinds)} beats are real footage or images (need 30%)")
    if [i for i in range(2, len(kinds)) if kinds[i] == kinds[i - 1] == kinds[i - 2]]:
        p.append("three equal visuals in a row")
    if [k for k in kinds if k not in MOTION | REAL]:
        p.append(f"unknown visual types {set(k for k in kinds if k not in MOTION | REAL)}")
    qs = {(b.get("show") or {}).get("query", "").lower() for b in bs if (b.get("show") or {}).get("type") in REAL} - {""}
    if len(qs) < 3:
        p.append(f"{len(qs)} different image/footage queries (need at least 3)")
    asks = [b for b in bs if flag_text(b.get("ask"))]
    if len(asks) != (1 if rule["ask"] else 0):
        p.append(f"{len(asks)} beats with \"ask\" (need {1 if rule['ask'] else 0})")
    if any(len(str(b["ask"]).split()) > 12 for b in asks):
        p.append("an \"ask\" question is longer than 12 words")
    spots = [k for k, b in enumerate(bs) if flag_true(b.get("spot"))]
    if len(spots) != (1 if rule["spot"] else 0):
        p.append(f"{len(spots)} beats with \"spot\" (need {1 if rule['spot'] else 0})")
    elif spots and ("LOOK UP" not in says[spots[0]] or len(says[spots[0]].split()) > 45):
        p.append("the spot beat must name LOOK UP and say 'link in the description' in max 40 words")
    look = [k for k, s in enumerate(says) if "LOOK UP" in s]
    if not rule["lookup"] and look:
        p.append("\"LOOK UP\" must not appear in this act")
    if rule["lookup"] and not rule["spot"] and (len(look) != 1 or look[0] < len(says) - 3):
        p.append("\"LOOK UP\" exactly once, in the last 3 beats")
    if rule["recap"] and not any(flag_true(b.get("recap")) for b in bs):
        p.append("one beat must have \"recap\": true")
    if not any(s.strip().endswith("?") and re.search(r"\byou(r)?\b", s, re.I)
               for s in re.split(r"(?<=[.!?])\s+", " ".join(says))):
        p.append("no direct question to the viewer with 'you'")
    text = " ".join(says)
    if ANNOUNCE.search(text) or PRICE.search(text):
        p.append("never announce chapters or parts, never a price, discount or code")
    found = fact_check({"chapters": [act]}, sources)
    if any(q.startswith(("number", "calc uses")) for q in found):
        found.append("for every number above: use it exactly as printed in the SOURCES, or add a calc that converts "
                     "a printed value (e.g. 0.3844 * 1000000 = 384400), or remove the sentence")
    return p + found


def act_sources(sources: list[dict], ids: list, budget: int = 6500, hint: str = "") -> list[dict]:
    """The act's sources, plus any other source that prints a number named in the act's outline (hint)."""
    pick = [s for s in sources if s["id"] in set(ids or [])] or sources[:2]
    nums = [n.replace(",", "") for n in a.numbers(hint) if len(n.replace(",", "").replace(".", "")) > 2]
    for s in sources:
        flat = s["text"].replace(",", "")
        if s not in pick and any(n in flat for n in nums) and len(pick) < 4:
            pick.append(s)
    per = max(1200, budget // len(pick))
    return [{**s, "text": s["text"][:per]} for s in pick]


EXTEND = """The act below is {short} words too short. Write {k} NEW beats (18-28 words each, same rules, only facts and
numbers from the SOURCES, new information, no repetition) that go just before its last 2 beats, so the act still
ends on its question or twist. Mix the visuals: at least one data graphic and one footage or image.
ACT:
{act}

SOURCES:
{sources}

Answer JSON only: {{"beats": [{{"say": "", "show": {{}}}}]}}"""


def extend_act(act: dict, short: int, src: list[dict], sources: list[dict]) -> dict:
    """Free models write 150-190 words an answer: instead of rewriting a short act, add the missing beats. A new
    beat is kept only if it passes the fact check on its own and uses a known visual type."""
    k = min(5, max(2, -(-short // 22) + 1))
    _, out = llm([{"role": "user", "parts": [{"text": EXTEND.format(
        short=short, k=k, act=json.dumps({"beats": act["beats"]}, ensure_ascii=False),
        sources="\n\n".join(f"[{s['id']}] {s['title']} ({s['url']})\n{s['text']}" for s in src))}]}])
    new = [b for b in (out or {}).get("beats", []) if isinstance(b, dict) and b.get("say")]
    for b in new:
        for k2 in ("ask", "spot", "recap"):
            b.pop(k2, None)
    good = [b for b in new[:k] if (b.get("show") or {}).get("type") in MOTION | REAL and len(str(b["say"]).split()) <= 32
            and "LOOK UP" not in str(b["say"]) and not fact_check({"chapters": [{"beats": [b]}]}, sources)]
    print(f"  extend: {len(new)} new beats, {len(good)} kept "
          f"(+{sum(len(str(b['say']).split()) for b in good)} words)", flush=True)
    new = good
    bs = act["beats"]
    return {**act, "beats": bs[:-2] + new + bs[-2:] if len(bs) > 2 else bs + new}


def write_by_acts(p: dict, sources: list[dict]) -> tuple[dict, list[str]]:
    total = LEN["cmax"]   # more, shorter acts: each answer of a free model stays small
    excerpt = "\n\n".join(f"[{s['id']}] {s['title']} ({s['url']})\n{s['text'][:1100]}" for s in sources)
    msgs = [{"role": "user", "parts": [{"text": OUTLINE.format(topic=p.get("topic"), angle=p.get("angle"),
             acts=total, sources=excerpt, trend_titles=trend_titles(5))}]}]
    for rnd in range(3):   # free models sometimes answer one act only: ask again, saying how many
        raw, out = llm(msgs)
        acts = [x for x in (out.get("acts") or []) if isinstance(x, dict)][:total]
        print(f"Outline, draft {rnd + 1}: {len(acts)} acts")
        if len(acts) >= LEN["cmin"]:
            break
        msgs = msgs[:1] + [{"role": "model", "parts": [{"text": raw}]}, {"role": "user", "parts": [{"text":
                f"Your outline has {len(acts)} acts. Answer again with the same JSON and EXACTLY {total} objects in "
                "\"acts\", one per act, covering the whole story from the hook to the payoff."}]}]
    else:
        sys.exit(f"Act mode: the outline has {len(acts)} acts after 3 drafts (need {LEN['cmin']}-{total}).")
    total = len(acts)
    spec = {k: out.get(k) for k in ("id", "title", "alt_titles", "description_intro", "tags", "hashtags", "thumbs")}
    outline = "\n".join(f"{i + 1}. {x.get('title', '')}: {x.get('question_answered', '')} -> {x.get('ends_with', '')}"
                        for i, x in enumerate(acts))
    words = -(-(LEN["wmin"] + 120) // total)
    rules, history, chapters = act_plan(total), [], []
    for i, x in enumerate(acts):
        src = act_sources(sources, x.get("sources"), hint=" ".join(str(x.get(k, "")) for k in ("wow", "question_answered", "ends_with")))
        prev = (f"The previous act ended with: \"{chapters[-1]['beats'][-1].get('say', '')}\" - open by answering it."
                if chapters and chapters[-1].get("beats") else "")
        msgs = [{"role": "user", "parts": [{"text": ACT.format(
            n=i + 1, total=total, title=spec.get("title"), topic=p.get("topic"), outline=outline, previous=prev,
            act_title=x.get("title", f"Act {i + 1}"), answered=x.get("question_answered", ""), wow=x.get("wow", ""),
            ends=x.get("ends_with", ""), beats=round((words + 30) / 22), words=words + 30,
            motion=round((words + 30) / 22 * 0.45), real=round((words + 30) / 22 * 0.35), extra=rules[i]["extra"],
            keys=rules[i]["keys"],
            sources="\n\n".join(f"[{s['id']}] {s['title']} ({s['url']})\n{s['text']}" for s in src))}]}]
        best = None
        for rnd in range(4):
            raw, act = llm(msgs)
            act = clean_flags({"title": act.get("title") or x.get("title", ""), "sources": x.get("sources") or [],
                               "beats": [b for b in act.get("beats", []) if isinstance(b, dict)]})
            probs = act_check(act, rules[i], words, sources)
            for _ in range(2):   # short act: add beats instead of rewriting it
                m = re.match(r"this act has (\d+) words", probs[0]) if probs else None
                if not m or int(m.group(1)) >= words:
                    break
                longer = clean_flags(extend_act(act, words + 15 - int(m.group(1)), src, sources))
                lp = act_check(longer, rules[i], words, sources)
                if len(lp) > len(probs) or len(longer["beats"]) == len(act["beats"]):
                    break
                act, probs = longer, lp
            history.append(f"Act {i + 1}, draft {rnd + 1}: {len(probs)} problem(s)" + "".join(f"\n  - {q}" for q in probs))
            print(history[-1])
            if best is None or len(probs) < len(best[2]):
                best = (raw, act, probs)
            if not probs:
                break
            raw, act, probs = best   # the next draft fixes the best one so far, never a worse one
            msgs = msgs[:1] + [{"role": "model", "parts": [{"text": raw}]},
                               {"role": "user", "parts": [{"text": FIX.format(problems="\n".join(f"- {q}" for q in probs))
                                                          .replace("whole script", "whole act")}]}]
        else:
            sys.exit(f"CHECKS FAILED: act {i + 1} still fails after 4 drafts: no long video this week.\n" + "\n".join(history))
        chapters.append(act)
    spec["chapters"] = chapters
    return spec, history


def review_by_acts(spec: dict, sources: list[dict]) -> list[str]:
    """The fact reviewer act by act, each with the sources of that act: small requests for the free models."""
    out = []
    for ci, ch in enumerate(spec.get("chapters", []), 1):
        part = {"chapters": [ch]}
        out += [f"act {ci}: {x}" for x in review(part, act_sources(sources, ch.get("sources"), 7000))]
    return out


def gemini_up() -> bool:
    """One tiny request: is any Gemini model answering on this key right now?"""
    import os
    import requests
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return False
    for m in a.gemini_models(key)[:2]:
        try:
            r = requests.post(a.GEMINI.format(model=m), params={"key": key}, timeout=60, json={
                "contents": [{"role": "user", "parts": [{"text": "Answer JSON only: {\"ok\": true}"}]}],
                "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 20}})
            if r.status_code == 200:
                return True
            print(f"  Gemini {m} HTTP {r.status_code}", flush=True)
        except requests.RequestException as e:
            print(f"  Gemini {m}: {type(e).__name__}", flush=True)
    return False


REPAIR = """Here is ACT {n} of the script (JSON). The checks of the whole script found these problems in it:
{problems}
Rewrite the whole act fixing every point, same JSON format and rules as before (beats of 18-28 words, about {words}
words, only numbers from the SOURCES, keep its "ask"/"spot"/"recap" beats where they are).
ACT:
{act}

SOURCES:
{sources}

Answer JSON only: {{"title": "", "beats": [...]}}"""


def repair_acts(spec: dict, problems: list[str], sources: list[dict], history: list[str]) -> None:
    """Rewrite only the acts the problems point to (act N, chapter N, or the act holding a wrong number); problems
    about the whole script go to the acts that can fix them (shortest acts for length, every act otherwise)."""
    chs, total = spec["chapters"], len(spec["chapters"])
    words = -(-(LEN["wmin"] + 120) // total)
    rules = act_plan(total)
    todo: dict[int, list[str]] = {}
    for q in problems:
        if q.startswith(("title must", "vague word")):
            continue
        m = re.search(r"\b(?:act|chapter) (\d+)", q)
        num = re.match(r"number ([\d,.]+) is not", q)
        if m and 1 <= int(m.group(1)) <= total:
            hit = [int(m.group(1)) - 1]
        elif num:
            hit = [i for i, ch in enumerate(chs) if any(num.group(1) in json.dumps(b) for b in ch["beats"])] or [0]
        elif q.startswith("narration has"):
            n = [len(" ".join(b.get("say", "") for b in ch["beats"]).split()) for ch in chs]
            hit = [i for i in range(total) if n[i] < words] or list(range(total))
        else:
            hit = list(range(total))
        for i in hit:
            todo.setdefault(i, []).append(q)
    for i, probs in sorted(todo.items()):
        src = act_sources(sources, chs[i].get("sources"))
        msgs = [{"role": "user", "parts": [{"text": REPAIR.format(
            n=i + 1, problems="\n".join(f"- {q}" for q in probs), words=words, act=json.dumps(
                {"title": chs[i]["title"], "beats": chs[i]["beats"]}, ensure_ascii=False),
            sources="\n\n".join(f"[{s['id']}] {s['title']} ({s['url']})\n{s['text']}" for s in src))}]}]
        for rnd in range(2):
            raw, act = llm(msgs)
            act = clean_flags({"title": chs[i]["title"], "sources": chs[i].get("sources") or [],
                               "beats": [b for b in act.get("beats", []) if isinstance(b, dict)]})
            left = act_check(act, rules[i], words, sources)
            history.append(f"Repair act {i + 1}, draft {rnd + 1}: {len(left)} problem(s)" + "".join(f"\n  - {q}" for q in left))
            print(history[-1])
            if not left:
                chs[i] = act
                break
            msgs = msgs[:1] + [{"role": "model", "parts": [{"text": raw}]},
                               {"role": "user", "parts": [{"text": FIX.format(problems="\n".join(f"- {q}" for q in left))
                                                          .replace("whole script", "whole act")}]}]
    if any(q.startswith(("title must", "vague word")) for q in problems):
        _, t = llm([{"role": "user", "parts": [{"text": (
            f"Script topic: {spec.get('title')}. Opening: {chs[0]['beats'][0].get('say', '')}\nWrite a YouTube title: "
            "20-60 characters, the concrete subject plus a real number from the script, one promise, no vague words "
            "(secret, mystery, amazing, insane, shocking, truth, crazy, unbelievable). Answer JSON only: {\"title\": \"\"}")}]}])
        spec["title"] = (t or {}).get("title") or spec.get("title")


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


def add_stickmen(segments: list[dict], want: int = 6) -> int:
    """The stick man (human scale) on at least `want` image/footage beats, spread through the video: the code adds the
    missing ones itself (the writers often forget the field), on the beats whose narration talks about size."""
    have = sum(1 for seg in segments for v in seg["visuals"] if v.get("stickman"))
    cands = [v for seg in segments for v in seg["visuals"] if v["type"] in ("image", "video") and not v.get("stickman")]
    need = max(0, want - have)
    if need and cands:
        step = len(cands) / need
        for k in range(min(need, len(cands))):
            cands[int(k * step)]["stickman"] = {"label": "YOU", "size": "tiny"}
    return sum(1 for seg in segments for v in seg["visuals"] if v.get("stickman"))


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
            if b.get("spot"):   # mid-video LOOK UP spot: Phone Screens scene (director), kinetic text if Remotion fails
                v = {"type": "kinetic", "text": "LOOK UP · link in the description", "accent": ["LOOK", "UP"], "spot": True}
            if not v:  # nothing found: the line on screen as kinetic text
                v = {"type": "kinetic", "text": " ".join(say.split()[:7]), "accent": []}
            if str(b.get("ask") or "").strip():   # comment question typed on screen (director: Typewriter)
                v["ask"] = " ".join(str(b["ask"]).split())[:80]
            visuals.append(v)
            weights.append(max(4, len(say.split())))
            says.append(say)
        # owner 03/11/2026: no chapters for the viewer (no cards, no list in the description); the act only paces
        segments.append({"id": f"c{ci + 1}", "act": "Intro" if ci == 0 else ch.get("title", f"Part {ci + 1}"),
                         "sources": [x for x in ch.get("sources", []) if x in {s['id'] for s in sources}] or ["S1"],
                         "narration": " ".join(says), "visuals": visuals, "weights": weights})
    if real < 6:
        sys.exit(f"Only {real} real NASA visuals found: no long video this week.")
    add_stickmen(segments)
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
              "description_intro": spec.get("description_intro", ""), "progress_bar": True, "cut_sfx": True, "chapters": False,
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
        mmin=LEN["mmin"], mmax=LEN["mmax"], chapters=f"{LEN['cmin']} to {LEN['cmax']}", trend_titles=trend_titles())}]}]
    history, scores = [], {}
    acts = "--full" not in args   # act mode by default: small blocks work for Gemini and for the free writers
    if acts:   # outline + one act per call, same checks on the whole script (owner 03/11/2026)
        global SKIP_GEMINI
        SKIP_GEMINI = not gemini_up()   # Gemini over quota: no 2-minute retries before every small call
        print("Act mode: one act per call" + (" (Gemini unavailable)" if SKIP_GEMINI else ""))
        spec, history = write_by_acts(p, sources)
        for rnd in range(3):
            problems = fact_check(spec, sources) + script_check(spec)
            if not [x for x in problems if x.startswith("number")]:
                problems += review_by_acts(spec, sources)
                if not problems:
                    rprobs, scores = retention_review(spec)
                    problems += rprobs if rnd < 2 else []
            history.append(f"Whole script, check {rnd + 1}: {len(problems)} problem(s)" + "".join(f"\n  - {x}" for x in problems))
            print(history[-1])
            if not problems:
                break
            if rnd < 2:
                repair_acts(spec, problems, sources, history)
        else:
            sys.exit("CHECKS FAILED in act mode: no long video this week.\n" + "\n".join(history))
    for rnd in range(0 if acts else 4):
        raw, spec = llm(msgs)
        problems = fact_check(spec, sources) + script_check(spec)
        if not [x for x in problems if x.startswith("number")]:  # the reviewer only on drafts whose numbers are clean
            problems += review(spec, sources)
            if rnd < 3 and not problems:   # last round: the critic's score is reported, not a reason to throw the script away
                rprobs, scores = retention_review(spec)
                problems += rprobs
            elif not problems:
                _, scores = retention_review(spec)
        history.append(f"Round {rnd + 1}: {len(problems)} problem(s)" + "".join(f"\n  - {x}" for x in problems))
        print(history[-1])
        if not problems:
            break
        msgs += [{"role": "model", "parts": [{"text": raw}]},
                 {"role": "user", "parts": [{"text": FIX.format(problems="\n".join(f"- {x}" for x in problems))}]}]
    else:
        if not acts:   # act mode skips this loop: its checks already passed above
            sys.exit("CHECKS FAILED after 4 drafts: no long video this week.\n" + "\n".join(history))
    words = sum(len(b.get("say", "").split()) for _, b in beats(spec))
    report = "\n".join([f"# Controlli automatici ({datetime.now():%Y-%m-%d %H:%M})", "",
                        f"Argomento: {p.get('topic')} ({p.get('angle')})", f"Parole: {words}; capitoli: {len(spec['chapters'])}; "
                        f"battute: {len(beats(spec))}", "", "## Esito per giro", *history, "",
                        "## Fonti", *[f"- {s['id']} {s['title']}: {s['url']}" for s in sources], "",
                        f"Punteggi del critico di ritenzione (0-10): {', '.join(f'{k} {v:.0f}' for k, v in scores.items()) or 'critico non disponibile'}", "",
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
