"""Let Gemini watch the top competitor videos of a research report (by URL, nothing downloaded, no Claude tokens).

  python tools/gemini_watch.py <niche> [n] [source.json]   research/<niche>/<latest>.json (or source.json, e.g.
                                                            research/stickman/watchlist.json) -> research/<niche>/gemini-<YYYY-MM-DD>.md

Picks the n (default 3) videos with most views per day not analysed yet (research/<niche>/gemini-seen.json).
Key: env GEMINI_API_KEY (GitHub secret) or secrets/gemini.json {"api_key", "model"}. Read-only on YouTube.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PROFILES = {  # format concept of each channel and the paid product it pushes
    "cosmos": "Cosmos in Numbers: faceless space channel, real NASA/ESA footage and data, news + data Shorts and long videos; "
              "sells LOOK UP, a $14 beginner stargazing guide on Gumroad",
    "companies": "Companies in Numbers: faceless business channel, company rises and collapses told through numbers from filings; "
                 "sells The Collapse Files ($9) on Gumroad; never investment advice",
    "stickman": "new faceless explainer channel (to launch) in the viral stick man style: simple original 2D stick figure "
                "animations that explain interesting things (what if, history, psychology, money, science) for a broad "
                "audience; will sell a low-price digital product on Gumroad; everything drawn by us in code (Remotion)",
}
EXTRA = {  # extra questions per niche, appended to PROMPT
    "stickman": """
8. Art style (to rebuild it ORIGINALLY in code, never copy): background colour, line thickness and colour, character
   design (head shape, eyes, expressions, props), how many distinct drawings/scenes per minute, how the camera moves
   (pan, zoom, cut), how objects/numbers/maps/labels are drawn, colour palette (max 5), transitions.
9. Voice and script: voice gender/tone/speed (words per minute estimate), humour type, sentences per scene, how often
   the narrator addresses "you", running jokes or recurring character.
10. Title and thumbnail: title formula, thumbnail composition (characters, text words, colours, emotion).
11. Production cost guess: could it be produced automatically with code-drawn stick figures + TTS + simple motion? What
    is the hardest part to automate?""",
}
PROMPT = """You are analysing a viral competitor video for a faceless channel ({profile}).
Answer in Italian, concise, with timestamps (mm:ss). Sections:
1. Hook: exact first spoken sentence and what is on screen in the first 3 seconds.
2. Structure: promise, key beats, twists, ending/CTA, with timestamps.
3. Pacing: approximate cuts per minute, on-screen text, graphics, music, voice style and speed.
4. Visuals: type of footage (real agency footage, CGI, stock, artist's concepts), how numbers are shown.
5. Why it works: 3 concrete reasons.
6. What our channel should adapt to its own format (as a testable hypothesis with a metric) and what to avoid.
7. Monetization: how this creator makes money beyond ads (sponsors, own products, links, memberships), and which
   product or offer could fit our channel's audience.
Only describe what you actually see and hear; write "non verificabile" when unsure. Do not invent figures."""


def config():
    if os.environ.get("GEMINI_API_KEY"):
        return {"api_key": os.environ["GEMINI_API_KEY"], "model": os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")}
    f = ROOT / "secrets" / "gemini.json"
    if not f.exists():
        sys.exit("No Gemini key: set the GEMINI_API_KEY secret (or secrets/gemini.json locally).")
    return json.loads(f.read_text("utf-8"))


def watch(url, cfg, niche):
    body = {"contents": [{"parts": [{"file_data": {"file_uri": url}},
                                    {"text": PROMPT.format(profile=PROFILES.get(niche, niche)) + EXTRA.get(niche, "")}]}]}
    models = [cfg.get("model", "gemini-3.8-flash"), "gemini-3.6-flash"]  # fallback when the newest model is overloaded
    for attempt in range(4):
        model = models[0] if attempt < 2 else models[1]
        try:
            r = requests.post(API.format(model=model), params={"key": cfg["api_key"]}, json=body, timeout=300)
        except requests.RequestException as e:  # timeout or dropped connection: same as overload
            print("  retry after", type(e).__name__, flush=True)
            continue
        if r.status_code in (429, 500, 503):  # rate limit or "high demand": wait and retry
            time.sleep(60 * (attempt + 1))
            continue
        j = r.json()
        if r.status_code != 200:
            return None, f"ERRORE Gemini {r.status_code}: {j.get('error', {}).get('message', j)}"
        return model, "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
    return None, "ERRORE Gemini: modello sovraccarico, troppo lento o limite gratuito; riprovo al prossimo giro."


def main(niche, n=3, source=None):
    folder = ROOT / "research" / niche
    reports = [Path(source)] if source else sorted(p for p in folder.glob("*.json") if p.stem[:4].isdigit())
    if not reports:
        sys.exit(f"No research report in {folder}.")
    videos = json.loads(reports[-1].read_text("utf-8")).get("youtube", {}).get("videos", [])
    seen_f = folder / "gemini-seen.json"
    seen = set(json.loads(seen_f.read_text("utf-8"))) if seen_f.exists() else set()
    todo = sorted((v for v in videos if v["id"] not in seen), key=lambda v: -v.get("views_per_day", 0))[:n]
    if not todo:
        print("Nothing new to analyse.")
        return
    cfg = config()
    out = [f"# {niche}: competitor analizzati da Gemini ({time.strftime('%d/%m/%Y')})\n"]
    ok = 0
    for v in todo:
        url = f"https://www.youtube.com/watch?v={v['id']}"
        print("Watching", url, flush=True)
        model, text = watch(url, cfg, niche)
        out.append(f"## {v.get('title', '')} ({v.get('channel', '')})\n{url} · {v.get('views', '?')} visualizzazioni, "
                   f"{v.get('views_per_day', '?')} al giorno, pubblicato {v.get('published', '?')}"
                   f"{f' · analisi {model}' if model else ''}\n\n{text}\n")
        if model:  # failed videos stay unseen and are retried next run
            seen.add(v["id"])
            ok += 1
    if not ok:
        print("Every analysis failed; no report written.")
        return
    (folder / f"gemini-{time.strftime('%Y-%m-%d')}.md").write_text("\n".join(out), "utf-8")
    seen_f.write_text(json.dumps(sorted(seen), indent=0), "utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3, sys.argv[3] if len(sys.argv) > 3 else None)
