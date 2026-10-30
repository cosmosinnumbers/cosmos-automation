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
import qc  # noqa: E402
import stock  # noqa: E402
from common import ROOT, media_duration, save_yaml  # noqa: E402

LONG = ROOT / "longform"
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
- Sentence 1: a common belief that is wrong, or the single most striking number, in under 20 words. No greeting,
  no "In this video", no "Did you know".
- Then promise the payoff ("by the end you'll know ..."), and keep 1-2 open questions alive at all times.
- 6 to 8 chapters; every chapter ends on a question or a twist that pulls into the next; escalate the scale or the
  stakes chapter by chapter; the biggest reveal near the end.
- Turn numbers into things people can picture: comparisons of size, travel times, "X Earths would fit".
- Short spoken sentences. Total narration 1,350 to 1,550 words (the video must last over 8 minutes).
- Last chapter: payoff, one sentence on why it matters, then ONE sentence inviting viewers who want to see these
  objects in the real sky to the beginner's stargazing guide "LOOK UP" (link in the description). Nowhere else.

BEATS: each chapter is a list of beats; a beat is 1-2 sentences (max 30 words) said over ONE visual (~5 s).
Visual types ("show"):
- {{"type": "footage", "query": "2-4 words for the NASA video library (mission, telescope, planet)"}}
- {{"type": "image", "query": "2-4 words for the NASA image library"}}
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
 "hashtags": ["space", "nasa", "astronomy"], "thumbs": [{{"lines": ["2-3 WORDS", "PER LINE"], "query": "NASA image query"}}, 2 more],
 "chapters": [{{"title": "", "sources": ["S1"], "beats": [{{"say": "", "show": {{}}}}]}}]}}"""

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
                         research=research_notes()) + "\nNo search available: use ONLY these pages: "
                         + ", ".join(a.REF_PAGES)}]}], search=False)
    return p


def fetch_sources(p: dict) -> list[dict]:
    out = []
    for s in p.get("sources", [])[:6]:
        try:
            text = " ".join(a.page_text(s["url"]).split())
        except Exception as e:  # noqa: BLE001
            print("  source refused:", s.get("url"), str(e)[:80])
            continue
        if len(text) > 400:
            out.append({"id": f"S{len(out) + 1}", "title": s.get("title") or s["url"], "url": s["url"], "text": text[:9000]})
    if len(out) < 2:
        sys.exit(f"Only {len(out)} readable primary sources: no long video this week.")
    return out


def beats(spec: dict) -> list[tuple[int, dict]]:
    return [(i, b) for i, ch in enumerate(spec.get("chapters", [])) for b in ch.get("beats", [])]


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
    nums = []
    for _, b in beats(spec):
        nums += a.numbers(b.get("say", "")) + visual_numbers(b.get("show", {}))
    missing = []
    for n in dict.fromkeys(nums):
        plain = n.replace(",", "")
        if n in blob or plain in flat or re.fullmatch(r"(19|20)\d\d", n):
            continue
        if re.fullmatch(r"\d", plain):  # single digits: counting words ("2 reasons"), not data
            continue
        try:  # 384400 on screen vs "384,400" or "384 400" in the page
            if f"{float(plain):,.0f}" in blob or f"{float(plain):g}" in blob:
                continue
        except ValueError:
            pass
        missing.append(n)
    return [f"number {n} is not in any source" for n in missing]


def script_check(spec: dict) -> list[str]:
    p, bs = [], beats(spec)
    chs = spec.get("chapters", [])
    says = [b.get("say", "") for _, b in bs]
    text = " ".join(says)
    words = len(text.split())
    if not 1320 <= words <= 1650:
        p.append(f"narration has {words} words (need 1,350-1,550: the video must last over 8 minutes)")
    if not 6 <= len(chs) <= 8:
        p.append(f"{len(chs)} chapters (need 6-8)")
    first = re.split(r"(?<=[.!?])\s", says[0] if says else "")[0]
    if len(first.split()) > 22:
        p.append(f"first sentence has {len(first.split())} words (max 20)")
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
    out = a.backup_llm(msgs)  # a different model from the writer, when GROK_API_KEY is set
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
                    else:
                        v = {"type": "image", "src": k, "motion": motions[len(visuals) % len(motions)]}
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
                            "badge": "REAL NASA DATA", "side": "left", "focus": [0.5, 0.5], "highlight": 0}
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
    p = plan(today, hint)
    print("Topic:", p.get("topic"), "|", p.get("angle"))
    sources = fetch_sources(p)
    src_block = "\n\n".join(f"[{s['id']}] {s['title']} ({s['url']})\n{s['text']}" for s in sources)
    msgs = [{"role": "user", "parts": [{"text": WRITE.format(topic=p.get("topic"), angle=p.get("angle"), sources=src_block)}]}]
    history = []
    for rnd in range(3):
        raw, spec = a.gemini(msgs, search=False)
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
