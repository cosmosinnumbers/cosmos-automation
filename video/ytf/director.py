"""The director: picks which of the 11 motion-graphics effects goes where, from the content of the narration.

Rules (one effect per job, never two heavy scenes closer than MIN_GAP seconds):
  01 Orbit         first 1.8 s of every Short and long video: the hook, labelled with the source agency
  06 Charts        the first sentence with a real number (not a year, not a name like X-59): counter + bar wave
  02 Vertigo       a later number in a "shock" sentence (times, record, largest, billion, faster...)
  08 Frame Break   a contrast sentence (but, however, actually, turns out...): the mid-video reset
  09 Pullback      a big-picture sentence (whole, entire, all of, total, system...)
  05 Paper Cut     a short sentence in the middle third, words pressed in sync with the voice
  04 Headlines     when the story has 2+ primary sources and nothing else fits the middle: their real titles
  03 Zoom-through / 10 Glitch   the cuts between real clips (glitch before a contrast, zoom-through otherwise)
  07 Phone Screens + 11 Typewriter   the closing CTA: our Gumroad guide on a phone, then a typed follow line
The CTA on screen never shows a discount code (the same file goes to TikTok, where codes are not allowed):
the code is only in the YouTube/Meta descriptions.
Every placed effect also returns its sound events (sfx.py): the sound lands on the exact frame of the visual hit.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

FPS = 30
MIN_GAP = 3.0   # seconds between two full-screen scenes (half of it each side)
SHOCK = re.compile(r"\b(times|record|largest|biggest|smallest|fastest|hottest|coldest|first|billion|trillion|"
                   r"million|faster|hotter|colder|deeper|heavier|farther|further|never|only|most|least)\b", re.I)
CONTRAST = re.compile(r"\b(but|however|yet|actually|surprising(ly)?|turns out|instead|unexpected(ly)?|"
                      r"in fact|wrong|mystery)\b", re.I)
BIG = re.compile(r"\b(whole|entire|all of|altogether|in total|total|overall|system|together|every)\b", re.I)
UNITS = {"kilometers": "km", "kilometres": "km", "km": "km", "miles": "mi", "meters": "m", "metres": "m",
         "percent": "%", "%": "%", "degrees": "°", "kelvin": "K", "years": "years", "days": "days", "hours": "h",
         "minutes": "min", "seconds": "s", "billion": "billion", "million": "million", "trillion": "trillion",
         "times": "×", "tons": "t", "tonnes": "t", "kilograms": "kg", "kg": "kg", "light-years": "light-years",
         "km/h": "km/h", "mph": "mph", "watts": "W", "kilowatts": "kW", "megawatts": "MW", "feet": "ft"}
AGENCY = [("jpl.nasa.gov", "NASA JPL"), ("nasa.gov", "NASA"), ("esawebb.org", "ESA/WEBB"), ("esahubble", "ESA/HUBBLE"),
          ("esa.int", "ESA"), ("eso.org", "ESO"), ("stsci.edu", "STScI"), ("noirlab.edu", "NOIRLab"),
          ("sec.gov", "SEC FILINGS")]

PRODUCT = {
    "cosmos": {"product": "LOOK UP", "productSub": "Beginner's stargazing guide",
               "labels": ["Stargazing guide", "No telescope needed", "Link in bio"],
               "type": ["new space number daily", "follow + LOOK UP in bio"]},
    "companies": {"product": "THE NUMBERS", "productSub": "Company data pack",
                  "labels": ["Real filings", "Clean data", "Link in bio"],
                  "type": ["new company story daily", "follow + data in bio"]},
}


# ---------- reading the narration ----------
def sentences(timings: dict) -> list[dict]:
    out = []
    for seg in timings["segments"]:
        for s in seg["sentences"]:
            out.append({"start": s["start"], "end": s["end"], "text": s["text"]})
    return out


def word_times(sent: dict) -> list[tuple[float, str]]:
    """Start time of every word, spread over the sentence by length (the voice has no word timestamps)."""
    words = sent["text"].split()
    total = sum(len(w) + 1 for w in words) or 1
    t, out = sent["start"], []
    for w in words:
        out.append((t, w))
        t += (sent["end"] - sent["start"]) * (len(w) + 1) / total
    return out


def real_numbers(text: str) -> list[re.Match]:
    out = []
    for m in re.finditer(r"(?<![A-Za-z0-9.,-])(\d[\d,]*(?:\.\d+)?)", text):
        tok = m.group(1).rstrip(",")
        if re.fullmatch(r"(19|20)\d\d", tok):          # a year
            continue
        if re.search(r"[A-Za-z]-$", text[: m.start()]):  # X-59, JWST-1: names
            continue
        out.append(m)
    return out


def number_info(text: str) -> dict | None:
    """First real number of a sentence as counter props: value, decimals, suffix (unit), display, sub."""
    ms = real_numbers(text)
    if not ms:
        return None
    m = ms[0]
    tok = m.group(1).rstrip(",")
    try:
        value = float(tok.replace(",", ""))
    except ValueError:
        return None
    dec = len(tok.split(".")[1]) if "." in tok else 0
    rest = text[m.end():].strip()
    rng_m = re.match(r"(?:to|-|–)\s*(\d[\d,]*(?:\.\d+)?)\s*", rest)
    low = None
    if rng_m:   # "15 to 25 kilometers": show the range, count up to the top value
        low, tok = tok, rng_m.group(1).rstrip(",")
        value = float(tok.replace(",", ""))
        dec = len(tok.split(".")[1]) if "." in tok else 0
        rest = rest[rng_m.end():]
    words = rest.split()
    unit, used = "", 0
    if words:
        w0 = words[0].lower().strip(".,;:")
        if w0 in UNITS:
            unit, used = UNITS[w0], 1
            if w0 in ("billion", "million", "trillion") and len(words) > 1 and words[1].lower().strip(".,;:") in UNITS:
                unit += " " + UNITS[words[1].lower().strip(".,;:")]
                used = 2
    if rest[:1] == "%":
        unit = "%"
    suffix = unit if unit in ("%", "°", "×") else (" " + unit if unit else "")
    sub = " ".join(words[used:used + 6]).strip(" ,.;:")
    if not sub:
        sub = " ".join(text[: m.start()].split()[-5:]).strip(" ,.;:")
    out = {"value": value, "decimals": dec, "suffix": suffix, "sub": sub[:42], "display": f"{tok}{suffix}"}
    if low is not None:
        out.update({"from": float(low.replace(",", "")), "display": f"{low}–{tok}{suffix}"})
    return out


def agency(sources: list[dict]) -> str:
    for s in sources or []:
        host = urlparse(s.get("url", "")).netloc.lower()
        for dom, name in AGENCY:
            if dom in host:
                return name
    return "REAL DATA"


def _short_title(t: str, n: int = 60) -> str:
    t = re.sub(r"\s+[-|–]\s+.*$", "", t or "").strip()
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


# ---------- sound events of each effect (seconds from the start of the effect) ----------
def effect_sounds(effect: str, dur: float, props: dict) -> list[tuple[float, str]]:
    if effect == "orbit":
        return [(0.0, "whoosh"), (8 / FPS, "pop"), (0.55, "impact")]
    if effect == "vertigo":
        return [(0.0, "riser"), (2 / FPS, "impact"), (0.4, "shimmer")]
    if effect == "zoomthrough":
        return [(0.0, "whoosh"), (6 / FPS, "impact")]
    if effect == "glitch":
        return [(0.0, "glitch")]
    if effect == "headlines":
        return [(0.0, "swish"), (10 / FPS, "pop"), (0.4, "shimmer")]
    if effect == "papercut":
        return [(0.0, "slap")] + [(w["at"], "key") for w in props.get("words", [])]
    if effect == "charts":
        land = min(dur * 0.6, 1.6)
        return [(0.0, "swish")] + [((4 + i * 2.2) / FPS, "tick") for i in range(0, 16, 2)] + [(land, "ding")]
    if effect == "phonescreens":
        return [(0.0, "whoosh"), (0.3, "shimmer")] + [((8 + i * 7) / FPS, "pop") for i in range(len(props.get("labels", [])))]
    if effect == "framebreak":
        burst = round(dur * FPS * 0.52) / FPS
        return [(0.0, "swish"), (burst - 0.9, "riser"), (burst, "shatter")]
    if effect == "pullback":
        return [(0.1, "whoosh"), (dur * 0.7, "pop"), (dur * 0.72, "ding")]
    if effect == "typewriter":
        return [(0.0, "swish")] + [(k / FPS, "key") for k in props.get("keys", [])]
    return []


# ---------- Shorts ----------
def plan_short(spec: dict, timings: dict, brand: str = "cosmos", n_cuts: int = 0, cut_times=(),
               max_total: float = 58.0) -> dict:
    """Return {inserts: [{effect, t0, t1, props, captions}], transitions: [(t, effect)], tail: s, events: [(t, kind)]}.
    Times in seconds on the Short's timeline (narration starts at 0)."""
    dur = timings["duration"]
    sents = sentences(timings)
    src = spec.get("sources_full") or []
    inserts: list[dict] = []
    busy: list[tuple[float, float]] = []

    def free(t0, t1, gap=MIN_GAP * 0.5):
        # after the hook a short beat of footage is enough (0.5 s): the first number must land while it is spoken
        return all(t1 + gap <= a or t0 >= b + (0.5 if a == 0.0 else gap) for a, b in busy)

    def add(effect, t0, t1, props, captions=True):
        inserts.append({"effect": effect, "t0": t0, "t1": t1, "props": props, "captions": captions})
        busy.append((t0, t1))

    # 01 Orbit: the hook
    add("orbit", 0.0, min(1.8, dur * 0.1), {"label": agency(src) + " · NEW"})
    # 06 Charts: first sentence with a real number
    used = set()
    for i, s in enumerate(sents):
        info = number_info(s["text"])
        if info and s["start"] < dur - 4:
            t0 = max(2.4, s["start"] + 0.1)
            t1 = min(t0 + 3.0, dur - 3.0)
            if t1 - t0 >= 2.0 and free(t0, t1):
                add("charts", t0, t1, {**info, "label": agency(src) + " data"})
                used.add(i)
                break
    # middle: one or two scenes, by content
    for i, s in enumerate(sents):
        if i in used or s["start"] < 4 or s["end"] > dur - 3.5 or len(inserts) >= 4:
            continue
        txt = s["text"]
        info = number_info(txt)
        t0 = s["start"] + 0.05
        if CONTRAST.search(txt):
            t1 = min(t0 + 2.6, dur - 3.5)
            if t1 - t0 >= 2.0 and free(t0, t1):
                add("framebreak", t0, t1, {"text": ""})
                used.add(i)
        elif info and SHOCK.search(txt):
            t1 = min(t0 + 2.6, dur - 3.5)
            if t1 - t0 >= 2.0 and free(t0, t1):
                add("vertigo", t0, t1, {"text": info["display"], "sub": info["sub"]})
                used.add(i)
        elif BIG.search(txt):
            t1 = min(t0 + 2.6, dur - 3.5)
            if t1 - t0 >= 2.2 and free(t0, t1):
                add("pullback", t0, t1, {"text": _short_title(txt, 46)})
                used.add(i)
    if len(inserts) < 4:   # 05 Paper Cut on a short sentence of the middle third, else 04 Headlines
        for i, s in enumerate(sents):
            words = s["text"].split()
            if i in used or not (dur * 0.3 <= s["start"] <= dur * 0.72) or not 3 <= len(words) <= 10:
                continue
            t0, t1 = s["start"] - 0.15, min(s["end"] + 0.5, s["start"] + 3.2)
            if free(t0, t1):
                ws = [{"text": w, "at": round(max(0.0, wt - t0), 2)} for wt, w in word_times(s)]
                add("papercut", t0, t1, {"words": ws, "accent": [w for w in words if real_numbers(w)][:2]}, captions=False)
                break
        else:
            if len(src) >= 2:
                mid = dur * 0.5
                if free(mid, mid + 2.6):
                    add("headlines", mid, mid + 2.6, {"headlines": [_short_title(s.get("title", "")) for s in src],
                                                      "sources": [agency([s]) for s in src]})
    # cuts between clips: glitch before a contrast, zoom-through otherwise
    transitions = []
    for t in cut_times:
        if not free(t - 0.3, t + 0.3, gap=0.2):
            continue
        nxt = next((s for s in sents if s["start"] >= t - 0.4), None)
        transitions.append((t, "glitch" if nxt and CONTRAST.search(nxt["text"]) else "zoomthrough"))
    # 07 + 11: closing CTA after the voice (only if the Short stays under max_total)
    cta = PRODUCT.get(brand, PRODUCT["cosmos"])
    tail = 0.0
    if dur + 3.9 <= max_total:
        tail = 3.9
        add("phonescreens", dur, dur + 1.5, {"product": cta["product"], "productSub": cta["productSub"],
                                              "labels": cta["labels"]}, captions=False)
        text = "\n".join(cta["type"])
        add("typewriter", dur + 1.5, dur + tail, {"lines": cta["type"], "keys": _keys(text)}, captions=False)
    elif dur + 2.4 <= max_total + 1.5:
        tail = 2.4
        text = "\n".join(cta["type"])
        add("typewriter", dur, dur + tail, {"lines": cta["type"], "keys": _keys(text, cps=30)}, captions=False)
    events = []
    for ins in inserts:
        events += [(ins["t0"] + a, k) for a, k in effect_sounds(ins["effect"], ins["t1"] - ins["t0"], ins["props"])]
    for t, eff in transitions:
        events += [(t + a - (4 / FPS if eff == "glitch" else 6 / FPS), k) for a, k in effect_sounds(eff, 0.3, {})]
    return {"inserts": sorted(inserts, key=lambda x: x["t0"]), "transitions": transitions, "tail": tail,
            "events": sorted(events)}


def _keys(text: str, cps: float = 24.0) -> list[float]:
    import motion
    return motion.typewriter_keys(text, FPS, start=5, cps=cps)


# ---------- long videos ----------
def plan_long(script: dict, shots: list[dict], timings: dict, brand: str = "cosmos") -> dict:
    """Turn some shots of a long video into effects (visual type 'fx'), mark chapter cuts for transitions, and
    list the sound events. Returns {fx: {shot_index: {effect, props}}, transitions: {shot_index: effect},
    events: [(t, kind)], hook: {...}}."""
    dur = timings["duration"]
    fx, transitions, events = {}, {}, []
    last = -99.0
    srcs = script.get("sources", [])
    say = {}
    for seg in script.get("segments", []):
        say[seg["id"]] = seg.get("narration", "")
    counters = 0
    mid_done = False
    for i, sh in enumerate(shots):
        v = sh["visual"]
        t0, t1 = sh["start"], sh["end"]
        d = t1 - t0
        if i and sh.get("chapter") and sh["chapter"].lower() not in ("intro",):
            transitions[i] = "glitch" if len(transitions) % 2 else "zoomthrough"
        if i == 0 or d < 2.0 or t0 - last < 12 or t1 > dur - 4:
            continue
        text = say.get(sh["segment"], "")
        kind = v.get("type")
        pick = None
        if kind == "counter":
            counters += 1
            if counters % 2 == 1:
                info = {"value": v["value"], "decimals": v.get("decimals", 0), "prefix": v.get("prefix", ""),
                        "suffix": v.get("suffix", ""), "label": v.get("label", "Real data"), "sub": v.get("sub", "")}
                pick = ("charts", info)
        elif kind == "kinetic":
            words = v.get("text", "").split()
            if SHOCK.search(v.get("text", "")) and real_numbers(v.get("text", "")):
                info = number_info(v["text"]) or {}
                pick = ("vertigo", {"text": info.get("display", v["text"]), "sub": info.get("sub", "")})
            elif 2 <= len(words) <= 9:
                step = min(0.38, d * 0.6 / max(1, len(words)))
                pick = ("papercut", {"words": [{"text": w, "at": round(0.2 + k * step, 2)} for k, w in enumerate(words)],
                                     "accent": v.get("accent", [])})
        elif kind in ("image", "video") and not mid_done and abs(t0 - dur / 2) < dur * 0.12 and CONTRAST.search(text):
            pick = ("framebreak", {"text": ""})
            mid_done = True
        elif kind in ("image", "video") and BIG.search(text) and t0 > dur * 0.6:
            pick = ("pullback", {"text": _short_title(text.split(".")[0], 46)})
        if pick:
            fx[i] = {"effect": pick[0], "props": pick[1], "src": v.get("src")}
            last = t0
            events += [(t0 + a, k) for a, k in effect_sounds(pick[0], d, pick[1])]
    # 07 Phone Screens on the closing LOOK UP beat (our guide on a phone, never a discount code on screen)
    k = len(shots) - 1
    if shots and "look up" in say.get(shots[k]["segment"], "").lower() and shots[k]["end"] - shots[k]["start"] >= 2.5:
        cta = PRODUCT.get(brand, PRODUCT["cosmos"])
        props = {"product": cta["product"], "productSub": cta["productSub"], "labels": cta["labels"]}
        fx[k] = {"effect": "phonescreens", "props": props, "src": shots[k]["visual"].get("src")}
        events += [(shots[k]["start"] + a, kk) for a, kk in effect_sounds("phonescreens", 3.0, props)]
    if len(srcs) >= 2 and len(shots) > 2 and 1 not in fx:
        fx[1] = {"effect": "headlines", "props": {"headlines": [_short_title(s.get("title", "")) for s in srcs],
                                                  "sources": [agency([s]) for s in srcs]}, "src": shots[1]["visual"].get("src")}
        events += [(shots[1]["start"] + a, k) for a, k in effect_sounds("headlines", 2.6, {})]
    for i, eff in transitions.items():
        events += [(shots[i]["start"] + a - (4 / FPS if eff == "glitch" else 6 / FPS), k) for a, k in effect_sounds(eff, 0.3, {})]
    hook = {"effect": "orbit", "t0": 0.0, "t1": 1.8, "props": {"label": agency(srcs) + " · REAL DATA"}}
    events += effect_sounds("orbit", 1.8, {})
    return {"fx": fx, "transitions": transitions, "events": sorted(events), "hook": hook}
