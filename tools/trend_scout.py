"""Trend scout (viral engine, step 1): what is going viral in the niche, as data the engine uses.

  python tools/trend_scout.py [niche] [--date YYYY-MM-DD]

Reads the research of tools/research.py (research/<niche>/<YYYY-Www>.json: YouTube videos of the last 30 days ranked
by views per day, audience questions, Reddit, Instagram hashtags, Google Trends), the format library
(config/formats.json) and our own experiments (logs/experiments.jsonl), and writes:
- research/<niche>/trends-<date>.json: every growing video classified by format, hook and theme (rules on the title,
  no LLM), with acceleration against the previous trends file; a trend score per format and per theme; the
  audience questions; the sky events of the next days (config/sky-calendar.json).
- research/<niche>/trends-<date>.md: the same, short, for humans.

Score of a format = sum of views/day of its videos / median views/day of the week, + 25% if the format is
accelerating, - 30% for each of our videos in that format in the last 7 days beyond the first (saturation).
Only official APIs and files already produced by research.yml: no scraping. Runs in research.yml after research.py.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMATS = ROOT / "config" / "formats.json"
SKY = ROOT / "config" / "sky-calendar.json"
EXPERIMENTS = ROOT / "logs" / "experiments.jsonl"

THEMES = {
    "black_hole": r"black ?hole", "sun": r"\bsun\b|solar flare|solar storm", "moon": r"\bmoon\b|lunar",
    "mars": r"\bmars\b|martian|rover", "jupiter": r"jupiter|\bio\b|europa", "saturn": r"saturn|titan|enceladus",
    "venus": r"venus", "mercury": r"mercury", "earth": r"\bearth\b|ocean|climate", "iss": r"\biss\b|space station",
    "artemis": r"artemis|orion|\bsls\b", "telescope": r"webb|jwst|hubble|telescope|roman",
    "small_bodies": r"asteroid|comet|meteor|bennu|interstellar", "galaxy": r"galax|milky way|andromeda|universe|cosmos",
    "light_speed": r"speed of light|light-?year|faster than light|\blight\b", "solar_system": r"solar system|planets?\b",
    "stars": r"\bstars?\b|nebula|supernova|neutron|pulsar", "spaceflight": r"spacex|starship|rocket|launch|astronaut",
}


def load_formats() -> dict:
    return json.loads(FORMATS.read_text("utf-8"))


def iso_seconds(d: str | None) -> int | None:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    return None if not m else int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0)


def classify(title: str, lib: dict) -> dict:
    """Format, hook and theme of a title. First matching format in the library order; 'other' if none."""
    t = title.lower()
    fmt = next((k for k, f in lib["formats"].items() if re.search(f["match"], t)), "other")
    hook = next((k for k, h in lib["hooks"].items() if re.search(h["match"], t)), "other")
    theme = next((k for k, rx in THEMES.items() if re.search(rx, t)), "other")
    return {"format": fmt, "hook": hook, "theme": theme, "emoji": bool(re.search(r"[\U0001F300-\U0001FAFF]", title))}


def our_recent(days: int = 7, today: date | None = None) -> dict:
    """Count of OUR videos per format in the last `days` days (logs/experiments.jsonl)."""
    today = today or date.today()
    out: dict = {}
    if not EXPERIMENTS.exists():
        return out
    for ln in EXPERIMENTS.read_text("utf-8").splitlines():
        try:
            r = json.loads(ln)
            d = date.fromisoformat(r["date"][:10])
        except (ValueError, KeyError):
            continue
        if 0 <= (today - d).days < days:
            f = r.get("labels", {}).get("format", "other")
            out[f] = out.get(f, 0) + 1
    return out


def sky_events(today: date, ahead: int = 10) -> list[dict]:
    if not SKY.exists():
        return []
    evs = json.loads(SKY.read_text("utf-8")).get("events", [])
    out = []
    for e in evs:
        try:
            d = date.fromisoformat(e["date"])
        except (ValueError, KeyError):
            continue
        if 0 <= (d - today).days <= ahead:
            out.append({**e, "in_days": (d - today).days})
    return sorted(out, key=lambda e: e["in_days"])


def previous(folder: Path, today: date) -> dict:
    """views/day by video id in the latest trends file before today (for the acceleration)."""
    olds = sorted(p for p in folder.glob("trends-*.json") if p.stem[7:] < today.isoformat())
    if not olds:
        return {}
    try:
        return {v["id"]: v["views_per_day"] for v in json.loads(olds[-1].read_text("utf-8"))["videos"]}
    except (ValueError, KeyError):
        return {}


def analyse(research: dict, lib: dict, prev: dict, ours: dict) -> dict:
    vids = []
    for v in research.get("youtube", {}).get("videos", []):
        c = classify(v.get("title", ""), lib)
        vpd = v.get("views_per_day") or 0
        acc = None if v["id"] not in prev or not prev[v["id"]] else round(vpd / prev[v["id"]] - 1, 3)
        vids.append({"id": v["id"], "title": v["title"], "channel": v.get("channel"), "published": v.get("published"),
                     "seconds": iso_seconds(v.get("duration")), "views": v.get("views"), "views_per_day": vpd,
                     "engagement": v.get("engagement"), "acceleration": acc, **c})
    med = statistics.median([v["views_per_day"] for v in vids]) if vids else 1
    med = med or 1

    def score(key):
        groups: dict = {}
        for v in vids:
            groups.setdefault(v[key], []).append(v)
        out = {}
        for k, vs in groups.items():
            s = sum(v["views_per_day"] for v in vs) / med
            accs = [v["acceleration"] for v in vs if v["acceleration"] is not None]
            accelerating = bool(accs) and statistics.mean(accs) > 0
            if accelerating:
                s *= 1.25
            sat = max(0, ours.get(k, 0) - 1) if key == "format" else 0
            s *= 0.7 ** sat
            out[k] = {"score": round(s, 2), "videos": len(vs), "accelerating": accelerating,
                      "engagement": round(statistics.mean([v["engagement"] or 0 for v in vs]), 4),
                      "ours_7d": ours.get(k, 0) if key == "format" else None,
                      "examples": [v["title"] for v in sorted(vs, key=lambda v: -v["views_per_day"])[:2]]}
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["score"]))

    yt = research.get("youtube", {})
    raw_q = (yt.get("audience_questions") or []) + (research.get("reddit", {}).get("audience_questions") or [])
    questions = list(dict.fromkeys(" ".join(q.split()) for q in raw_q))
    ig = research.get("instagram", {}) or {}
    ig_types: dict = {}
    for posts in ig.values() if isinstance(ig, dict) else []:
        for p in posts if isinstance(posts, list) else []:
            ig_types.setdefault(p.get("type", "?"), []).append(p.get("likes") or 0)
    return {"videos": vids, "formats": score("format"), "hooks": score("hook"), "themes": score("theme"),
            "short_share": round(sum(1 for v in vids if (v["seconds"] or 999) <= 180) / len(vids), 2) if vids else None,
            "audience_questions": [q for q in questions if 15 <= len(q) <= 200 and q.endswith("?") and q.isascii()][:15],
            "instagram_median_likes": {k: statistics.median(v) for k, v in ig_types.items()},
            "median_views_per_day": med}


def report(res: dict, niche: str, today: date) -> str:
    L = [f"# Trend della nicchia {niche} ({today:%d/%m/%Y})", "",
         "Classificazione automatica dei titoli in crescita (tools/trend_scout.py, nessun LLM). Punteggio = views/giorno "
         "del formato sulla mediana, +25% se accelera, -30% per ogni nostro video dello stesso formato oltre il primo negli ultimi 7 giorni.", ""]
    for key, name in (("formats", "Formati"), ("hooks", "Hook"), ("themes", "Temi")):
        L += [f"## {name}", "", "| | Punteggio | Video | Accelera | Esempio |", "|---|---|---|---|---|"]
        L += [f"| {k} | {v['score']} | {v['videos']} | {'sì' if v['accelerating'] else 'no'} | {(v['examples'] or [''])[0][:60]} |"
              for k, v in list(res[key].items())[:8]]
        L.append("")
    if res.get("sky"):
        L += ["## Eventi del cielo in arrivo", ""] + [f"- {e['date']}: {e['name']} (tra {e['in_days']} giorni)" for e in res["sky"]] + [""]
    if res["audience_questions"]:
        L += ["## Domande dell'audience (idee per audience_question)", ""] + [f"- {q}" for q in res["audience_questions"][:8]] + [""]
    if res["instagram_median_likes"]:
        L += ["## Instagram: like medi per tipo di post", ""] + [f"- {k}: {v:,.0f}" for k, v in res["instagram_median_likes"].items()] + [""]
    return "\n".join(L)


def main():
    a = sys.argv[1:]
    niche = next((x for x in a if not x.startswith("--") and not re.fullmatch(r"\d{4}-\d\d-\d\d", x)), "cosmos")
    today = date.fromisoformat(a[a.index("--date") + 1]) if "--date" in a else date.today()
    folder = ROOT / "research" / niche
    week = folder / f"{today:%G-W%V}.json"
    if not week.exists():
        cands = sorted(folder.glob("20??-W??.json"))
        if not cands:
            sys.exit(f"no research file in {folder}: run tools/research.py first")
        week = cands[-1]
    research = json.loads(week.read_text("utf-8"))
    res = analyse(research, load_formats(), previous(folder, today), our_recent(today=today))
    res.update({"niche": niche, "date": today.isoformat(), "source": week.name, "sky": sky_events(today)})
    (folder / f"trends-{today}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), "utf-8")
    md = report(res, niche, today)
    (folder / f"trends-{today}.md").write_text(md, "utf-8")
    print(md)


if __name__ == "__main__":
    main()
