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

Katana kit (owner 06/11/2026: "the motion graphics of Higgsfield Katana in my videos"), the viral-edit look:
  12 Katana Type   the short punchy line (was Paper Cut in Shorts): words slam on the beat of the voice
  13 Impact Frame  the shock number (Shorts; alternates with Vertigo in long videos): 1-bit manga freeze + speed lines
  14 Light Sweep   every other counter of a long video: the number revealed like a product launch
  15 Flash Cuts    the second big-picture line (after Pullback): rapid-fire montage of our own stills
  whip / dither    two more live-frame transitions at the cuts, rotating with Zoom-through and Glitch
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


# cut transitions in rotation (glitch is kept for the cut before a contrast line)
CUT_CYCLE = ("whip", "zoomthrough", "dither")
# lead of the transition sound before the cut (seconds): these hit in the middle of their frames
TRANS_LEAD = {"glitch": 4 / FPS, "dither": 4 / FPS, "whip": 5 / FPS, "zoomthrough": 6 / FPS}


# ---------- sound events of each effect (seconds from the start of the effect) ----------
def effect_sounds(effect: str, dur: float, props: dict) -> list[tuple[float, str]]:
    if effect == "katanatype":
        acc = {str(a).upper().strip(".,!?") for a in props.get("accent", [])}
        hot = lambda w: w.upper().strip(".,!?;:") in acc or any(c.isdigit() for c in w)   # noqa: E731
        ws = props.get("words", [])
        return [(0.0, "whoosh")] + [(w["at"], "impact" if hot(w["text"]) else ("slap" if k == 0 else "pop"))
                                    for k, w in enumerate(ws)]
    if effect == "impactframe":
        return [(0.0, "impact"), (1 / FPS, "shatter"), (0.3, "shimmer"), (max(0.5, dur - 10 / FPS), "swish")]
    if effect == "lightsweep":
        land = min(round(dur * FPS * 0.55), 54) / FPS
        return [(0.0, "riser"), (land, "impact"), (land + 0.05, "shimmer")]
    if effect == "flashcuts":
        out, c, step = [(0.0, "whoosh")], 0.0, 7.0
        while c < dur * FPS - 2:
            out.append((c / FPS, "tick"))
            c += round(step)
            step = max(3.0, step * 0.82)
        return out + [(min(dur, 0.9), "impact")]
    if effect == "whip":
        return [(0.0, "whoosh")]
    if effect == "dither":
        return [(0.0, "glitch"), (4 / FPS, "pop")]
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
            t1 = min(t0 + 2.2, dur - 3.5)
            if t1 - t0 >= 1.8 and free(t0, t1):   # Katana impact frame: the number hits like a manga panel
                add("impactframe", t0, t1, {"text": info["display"], "sub": info["sub"]})
                used.add(i)
        elif BIG.search(txt):
            t1 = min(t0 + 2.6, dur - 3.5)
            if t1 - t0 >= 2.2 and free(t0, t1):
                eff = "flashcuts" if any(x["effect"] == "pullback" for x in inserts) else "pullback"
                add(eff, t0, t1, {"text": _short_title(txt, 46 if eff == "pullback" else 28)})
                used.add(i)
    if len(inserts) < 4:   # 12 Katana Type on a short sentence of the middle third, else 04 Headlines
        for i, s in enumerate(sents):
            words = s["text"].split()
            if i in used or not (dur * 0.3 <= s["start"] <= dur * 0.72) or not 3 <= len(words) <= 10:
                continue
            t0, t1 = s["start"] - 0.15, min(s["end"] + 0.5, s["start"] + 3.2)
            if free(t0, t1):
                ws = [{"text": w, "at": round(max(0.0, wt - t0), 2)} for wt, w in word_times(s)]
                add("katanatype", t0, t1, {"words": ws, "accent": [w for w in words if real_numbers(w)][:2]}, captions=False)
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
        transitions.append((t, "glitch" if nxt and CONTRAST.search(nxt["text"]) else CUT_CYCLE[len(transitions) % len(CUT_CYCLE)]))
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
        events += [(t + a - TRANS_LEAD.get(eff, 6 / FPS), k) for a, k in effect_sounds(eff, 0.3, {})]
    return {"inserts": sorted(inserts, key=lambda x: x["t0"]), "transitions": transitions, "tail": tail,
            "events": sorted(events)}


def _keys(text: str, cps: float = 24.0) -> list[float]:
    import motion
    return motion.typewriter_keys(text, FPS, start=5, cps=cps)


# ---------- long videos ----------
MIN_GAP_LONG = 9.0   # seconds between two Remotion scenes in a long video (was 12: one new scene per chapter at least)

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
    counters = chapters = pullbacks = shocks = kinetics = 0
    mid_done = False
    shown = script.get("chapters", True) is not False   # owner 03/11/2026: no chapters for the viewer
    for i, sh in enumerate(shots):
        v = sh["visual"]
        t0, t1 = sh["start"], sh["end"]
        d = t1 - t0
        if v.get("spot") and d >= 2.5:   # mid-video LOOK UP spot: the guide on a phone (never a code on screen)
            cta = PRODUCT.get(brand, PRODUCT["cosmos"])
            props = {"product": cta["product"], "productSub": cta["productSub"], "labels": cta["labels"]}
            fx[i] = {"effect": "phonescreens", "props": props, "src": v.get("src")}
            last = t0
            events += [(t0 + a_, k) for a_, k in effect_sounds("phonescreens", 3.0, props)]
            continue
        if v.get("ask") and d >= 2.5 and t0 - last >= 4 and t1 <= dur - 1:   # question for the comments, typed
            lines = ["> your turn", _short_title(v["ask"], 60)]
            props = {"lines": lines, "keys": _keys("\n".join(lines), cps=26)}
            fx[i] = {"effect": "typewriter", "props": props, "src": v.get("src")}
            last = t0
            events += [(t0 + a_, k) for a_, k in effect_sounds("typewriter", d, props)]
            continue
        act = sh.get("chapter") or sh.get("act")
        if i and act and act.lower() not in ("intro",):
            transitions[i] = ("zoomthrough", "whip", "glitch", "dither")[len(transitions) % 4]
            events.append((max(0.0, t0 - 1.2), "riser"))   # tension before every new chapter (owner 03/11/2026)
            chapters += 1
            # 11 Typewriter: every other chapter opens with its title typed on screen (the 11th effect in long videos)
            if shown and sh.get("chapter") and chapters % 2 == 1 and d >= 2.5 and t0 - last >= 6 and t1 <= dur - 4 and sh["chapter"].lower() != "outro":
                title = _short_title(sh["chapter"], 40)
                lines = [f"chapter {chapters:02d}", title]
                props = {"lines": lines, "keys": _keys("\n".join(lines), cps=26)}
                fx[i] = {"effect": "typewriter", "props": props, "src": v.get("src")}
                last = t0
                events += [(t0 + a, k) for a, k in effect_sounds("typewriter", d, props)]
                continue
        if i == 0 or d < 2.0 or t0 - last < MIN_GAP_LONG or t1 > dur - 4:
            continue
        text = say.get(sh["segment"], "")
        kind = v.get("type")
        pick = None
        if kind == "counter":
            counters += 1
            info = {"value": v["value"], "decimals": v.get("decimals", 0), "prefix": v.get("prefix", ""),
                    "suffix": v.get("suffix", ""), "label": v.get("label", "Real data"), "sub": v.get("sub", "")}
            # odd counters: Charts dashboard; even ones: the Katana product-launch reveal (were plain counters)
            pick = ("charts", info) if counters % 2 == 1 else ("lightsweep", info)
        elif kind == "kinetic":
            words = v.get("text", "").split()
            if SHOCK.search(v.get("text", "")) and real_numbers(v.get("text", "")):
                info = number_info(v["text"]) or {}
                shocks += 1
                pick = ("impactframe" if shocks % 2 else "vertigo", {"text": info.get("display", v["text"]), "sub": info.get("sub", "")})
            elif 2 <= len(words) <= 9:
                step = min(0.38, d * 0.6 / max(1, len(words)))
                kinetics += 1   # Katana Type and Paper Cut take turns: the slam stays special
                pick = ("katanatype" if kinetics % 2 else "papercut",
                        {"words": [{"text": w, "at": round(0.2 + k * step, 2)} for k, w in enumerate(words)],
                         "accent": v.get("accent", [])})
        elif kind in ("image", "video") and not mid_done and abs(t0 - dur / 2) < dur * 0.12 and CONTRAST.search(text):
            pick = ("framebreak", {"text": ""})
            mid_done = True
        elif kind in ("image", "video") and BIG.search(text) and t0 > dur * 0.6 and pullbacks < 2:
            # first Pullback, then the Katana flash-cut montage: the same move tires
            pick = ("pullback", {"text": _short_title(text.split(".")[0], 46)}) if pullbacks == 0 else \
                ("flashcuts", {"text": _short_title(text.split(".")[0], 28)})
            pullbacks += 1
        if pick:
            fx[i] = {"effect": pick[0], "props": pick[1], "src": v.get("src")}
            last = t0
            events += [(t0 + a, k) for a, k in effect_sounds(pick[0], d, pick[1])]
    # 07 Phone Screens on the closing LOOK UP beat (our guide on a phone, never a discount code on screen)
    k = len(shots) - 1
    if k > 0 and k in fx and fx[k]["effect"] == "typewriter":   # the last beat is the comment question: the phone goes before
        k -= 1
    if shots and k not in fx and "look up" in say.get(shots[k]["segment"], "").lower() and shots[k]["end"] - shots[k]["start"] >= 2.5:
        cta = PRODUCT.get(brand, PRODUCT["cosmos"])
        props = {"product": cta["product"], "productSub": cta["productSub"], "labels": cta["labels"]}
        fx[k] = {"effect": "phonescreens", "props": props, "src": shots[k]["visual"].get("src")}
        events += [(shots[k]["start"] + a, kk) for a, kk in effect_sounds("phonescreens", 3.0, props)]
    if len(srcs) >= 2 and len(shots) > 2 and 1 not in fx:
        fx[1] = {"effect": "headlines", "props": {"headlines": [_short_title(s.get("title", "")) for s in srcs],
                                                  "sources": [agency([s]) for s in srcs]}, "src": shots[1]["visual"].get("src")}
        events += [(shots[1]["start"] + a, k) for a, k in effect_sounds("headlines", 2.6, {})]
    for i, eff in transitions.items():
        events += [(shots[i]["start"] + a - TRANS_LEAD.get(eff, 6 / FPS), k) for a, k in effect_sounds(eff, 0.3, {})]
    hook = {"effect": "orbit", "t0": 0.0, "t1": 1.8, "props": {"label": agency(srcs) + " · REAL DATA"}}
    events += effect_sounds("orbit", 1.8, {})
    return {"fx": fx, "transitions": transitions, "events": sorted(events), "hook": hook}


# ---------- optional creative pass by GLM (secret GLM_API_KEY) ----------
CREATIVE = """You direct a vertical space-news Short of "Cosmos in Numbers". Narration (the only facts you may use):
{narration}

Answer JSON only: {{"hook_label": "2-4 words, UPPERCASE, a punchy tag for the opening card (e.g. 'NASA · NEW', 'HUGE NUMBER')",
"accent_words": ["up to 3 words copied from the narration that deserve emphasis"]}}
No invented facts, no numbers that are not in the narration, no discount codes, no emojis."""


def creative_pass(narration: str, plan: dict) -> dict:
    """Let GLM pick the hook tag and the emphasised words; the answer is validated, anything odd keeps the
    deterministic plan. Returns the (possibly updated) plan. Never raises."""
    try:
        import glm
        if not glm.available():
            return plan

        def check(j):
            lab = str(j.get("hook_label", ""))
            bad = []
            if not 2 <= len(lab) <= 28 or not re.fullmatch(r"[A-Za-z0-9 ·\-/&']+", lab):
                bad.append("hook_label")
            if re.search(r"code|cosmos9|discount|free", lab, re.I):
                bad.append("hook_label mentions a code")
            if any(n not in narration for n in re.findall(r"\d+", lab)):
                bad.append("hook_label number not in narration")
            words = j.get("accent_words", [])
            if not isinstance(words, list) or any(str(w).strip(".,!?") not in narration for w in words):
                bad.append("accent_words not in narration")
            return bad

        out = glm.chat([{"role": "user", "parts": [{"text": CREATIVE.format(narration=narration)}]}],
                       check=check, temperature=0.7, max_tokens=400)
        if not out:
            return plan
        j = out[1]
        for ins in plan["inserts"]:
            if ins["effect"] == "orbit":
                ins["props"]["label"] = j["hook_label"].upper()
            if ins["effect"] == "papercut" and j.get("accent_words"):
                ins["props"]["accent"] = [str(w).strip(".,!?") for w in j["accent_words"]][:3]
    except Exception as e:  # noqa: BLE001 - the director must never stop a video
        print("  creative pass skipped:", type(e).__name__, flush=True)
    return plan
