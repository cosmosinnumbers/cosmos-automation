"""Cross-channel learning loop (owner 04/11/2026: "dobbiamo autoaggiustarci e imparare dai dati", "il ciclo guarda
l'andamento di tutti i canali").

  python tools/cross_learn.py learn [--dry-run]     metrics of every channel -> config/cross-weights.json + report
  python tools/cross_learn.py show                  print what the next clip / long video will be steered by

Facts only, no LLM, no network. Reads the latest reading of every post in 07-analytics/metrics/ (YouTube, Instagram,
Facebook, Threads videos, TikTok when tiktok.jsonl exists; Threads text posts are a different product and stay
out), 12 h+ after publication and from the last 45 days.

1. Post score (per channel and kind, e.g. Instagram reel): each metric over the median of the same channel and kind,
   averaged with weights. Instagram reel: views 0.45, average watch time 0.30, engagement (likes + 2 saves + 3 shares
   + 2 comments) 0.25. YouTube Short/long: views 0.5, % viewed 0.5. Facebook, Threads, TikTok: views. Capped at 6.
2. The same content goes out on several channels with different titles: posts are grouped into one item when their
   title words overlap (Jaccard or containment of the shorter title >= 0.5). Item score = weighted mean of its channels (Instagram 0.30, YouTube 0.30,
   TikTok 0.15, Threads 0.15, Facebook 0.10), so a clip that wins on Instagram but dies on YouTube is not a winner.
3. Features of each item: themes (config/themes.json), format and hook (config/formats.json), publication hour,
   short headline. Each value gets a shrunk mean ((sum + 2) / (n + 2), so 1 video never decides) and a lift against
   the items without it. A rule needs n >= 3 and a lift of at least 20%.
4. Hits: an item at >= 2.5x, or a post at >= 3x the median of its channel, becomes a "replicate" brief for the next
   long video (config/cross-weights.json next_long) and is listed first in the report.

Consumers (no human step): tools/day_clip.py picks the unused clip with the best predict() score instead of the
next one in name order (1 day in 5 it explores the least-tried theme); tools/auto_clips.py ranks the segments of a new
long video; video/ytf/longform_auto.py adds writer_block() to the topic planner and uses next_long as the topic hint
when the workflow gives none. Rules are rewritten every day, never piled up.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MDIR = ROOT / "07-analytics" / "metrics"
OUT = ROOT / "config" / "cross-weights.json"
THEMES = ROOT / "config" / "themes.json"
FORMATS = ROOT / "config" / "formats.json"
REPORTS = ROOT / "reports"

CHANNELS = ("youtube", "instagram", "facebook", "threads", "tiktok")
CH_W = {"instagram": 0.30, "youtube": 0.30, "tiktok": 0.15, "threads": 0.15, "facebook": 0.10}
KINDS = {"youtube": {"short", "long"}, "instagram": {"reel"}, "facebook": {"reel"}, "threads": {"video"},
         "tiktok": {"video", "post", "short"}}
MAX_AGE_DAYS, MIN_AGE_H, CAP = 45, 12, 6.0
HIT_ITEM, HIT_POST, MIN_N, MIN_LIFT = 2.5, 3.0, 3, 0.20
STOP = set("a an the of to in on at is are be it its this that and or but for with by from your you we our as was "
           "were will can just about into than full video youtube link bio shorts nasa data real numbers".split())
TZ_IT = timezone(timedelta(hours=1))   # hour buckets in Italian winter time; one hour of summer offset is noise here


def _jl(path: Path) -> list[dict]:
    out = []
    if path.exists():
        for ln in path.read_text("utf-8").splitlines():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def _jload(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def clean_title(t: str) -> str:
    t = re.split(r"\n|full video on youtube|📘", t or "", maxsplit=1, flags=re.I)[0]
    t = re.sub(r"#\w+|\(nasa data\)", " ", t, flags=re.I)
    return " ".join(t.split()).strip(" .:-")


def words(t: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+(?:[.,][0-9]+)?", clean_title(t).lower()) if w not in STOP and len(w) > 1}


def _parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").replace("+0000", "+00:00"))
    except ValueError:
        return None


def latest_posts(today: date) -> list[dict]:
    """Latest reading of every post/video of every channel, with age and kind filters."""
    out = []
    for ch in CHANNELS:
        best: dict[str, dict] = {}
        for r in _jl(MDIR / f"{ch}.jsonl"):
            if r.get("level") not in ("post", "video") or r.get("kind") not in KINDS[ch]:
                continue
            if r["id"] not in best or r.get("read_at", "") > best[r["id"]].get("read_at", ""):
                best[r["id"]] = r
        for r in best.values():
            pub, read = _parse_ts(r.get("published")), _parse_ts(r.get("read_at"))
            if not pub or not read or (read - pub).total_seconds() < MIN_AGE_H * 3600:
                continue
            if (today - pub.date()).days > MAX_AGE_DAYS:
                continue
            title = clean_title(r.get("title", ""))
            if not title:
                continue
            out.append({"channel": ch, "kind": r["kind"], "id": r["id"], "title": title, "published": pub,
                        "m": r.get("metrics") or {}})
    return out


def _engagement(m: dict) -> float | None:
    if m.get("likes") is None and m.get("saved") is None:
        return None
    return (m.get("likes") or 0) + 2 * (m.get("saved") or 0) + 3 * (m.get("shares") or 0) + 2 * (m.get("comments") or 0)


SPEC = {   # channel -> [(weight, getter)]
    "instagram": [(0.45, lambda m: m.get("views")), (0.30, lambda m: m.get("avg_watch_ms")), (0.25, _engagement)],
    "youtube": [(0.5, lambda m: m.get("views")), (0.5, lambda m: m.get("avg_view_pct"))],
    "facebook": [(1.0, lambda m: m.get("views"))],
    "threads": [(1.0, lambda m: m.get("views"))],
    "tiktok": [(1.0, lambda m: m.get("views") or m.get("play_count"))],
}


def score_posts(posts: list[dict]) -> dict:
    """Adds p['score'] (x the median of its channel+kind); returns the medians used."""
    meds = {}
    groups: dict[tuple, list[dict]] = {}
    for p in posts:
        groups.setdefault((p["channel"], p["kind"]), []).append(p)
    for (ch, kind), ps in groups.items():
        spec = SPEC[ch]
        med = []
        for _, get in spec:
            vals = [v for p in ps if (v := get(p["m"])) is not None]
            med.append(statistics.median(vals) if vals else None)
        meds[f"{ch}:{kind}"] = {"posts": len(ps), "median_views": med[0]}
        for p in ps:
            num = den = 0.0
            for (w, get), md in zip(spec, med):
                v = get(p["m"])
                if v is None or not md:
                    continue
                num += w * min(CAP, v / md)
                den += w
            p["score"] = round(num / den, 3) if den else None
    return meds


def overlap(a: set, b: set) -> float:
    """Jaccard, or containment of the shorter title in the longer caption (>= 3 shared words): a Reel caption is
    often the Short title plus a sentence."""
    if not a or not b:
        return 0.0
    small = a if len(a) <= len(b) else b
    inter = len(a & b)
    return max(inter / len(a | b), inter / len(small) if inter >= 3 else 0.0)


def group_items(posts: list[dict]) -> list[dict]:
    """One item per piece of content across channels (title-word overlap)."""
    items: list[dict] = []
    for p in sorted(posts, key=lambda p: p["published"]):
        if p.get("score") is None:
            continue
        w = words(p["title"])
        if not w:
            continue
        best, bj = None, 0.0
        for it in items:
            j = overlap(w, it["words"])
            if j > bj:
                best, bj = it, j
        if best is not None and bj >= 0.5:
            best["posts"].append(p)
            best["words"] |= w
        else:
            items.append({"words": set(w), "posts": [p]})
    for it in items:
        per = {}
        for p in it["posts"]:
            per.setdefault(p["channel"], []).append(p["score"])
        num = sum(CH_W[c] * max(v) for c, v in per.items())
        den = sum(CH_W[c] for c in per)
        it["score"] = round(num / den, 3)
        it["channels"] = {c: round(max(v), 2) for c, v in per.items()}
        it["views"] = sum(int(p["m"].get("views") or 0) for p in it["posts"])
        first = min(it["posts"], key=lambda p: p["published"])
        it["published"] = first["published"]
        # the title people see on the Reel / Short (shortest clean one, usually the headline)
        it["title"] = min((p["title"] for p in it["posts"]), key=len)
        it["text"] = " | ".join(sorted({p["title"] for p in it["posts"]}))
        hours = [p["published"].astimezone(TZ_IT).hour for p in it["posts"] if p["channel"] in ("instagram", "youtube")]
        it["hour"] = min(hours) if hours else None
    return items


def _lib() -> tuple[dict, dict, dict]:
    th = _jload(THEMES, {}).get("themes", {})
    fm = _jload(FORMATS, {})
    return th, fm.get("formats", {}), fm.get("hooks", {})


def labels(text: str) -> dict:
    """Themes, format, hook and title length of a piece of content."""
    th, fm, hk = _lib()
    low = (text or "").lower()
    out = {"theme": [k for k, v in th.items() if re.search(v["match"], low)],
           "format": [k for k, v in fm.items() if re.search(v["match"], low)][:1],
           "hook": [k for k, v in hk.items() if re.search(v.get("match", "$^"), low)][:1],
           "short_headline": ["yes" if len(clean_title(text.split(" | ")[0])) <= 40 else "no"]}
    return out


def features(items: list[dict]) -> dict:
    """{dimension: {value: {mean, n, lift}}}: shrunk mean of item scores with the value, lift vs without."""
    for it in items:
        it["labels"] = labels(it["text"])
        it["labels"]["short_headline"] = ["yes" if len(it["title"]) <= 40 else "no"]
        it["labels"]["hour"] = [f"{it['hour']:02d}" ] if it["hour"] is not None else []
    out: dict[str, dict] = {}
    for dim in ("theme", "format", "hook", "hour", "short_headline"):
        vals = {v for it in items for v in it["labels"].get(dim, [])}
        res = {}
        for v in vals:
            yes = [it["score"] for it in items if v in it["labels"].get(dim, [])]
            no = [it["score"] for it in items if v not in it["labels"].get(dim, [])]
            m_yes = (sum(yes) + 2.0) / (len(yes) + 2)
            m_no = (sum(no) + 2.0) / (len(no) + 2) if no else 1.0
            res[v] = {"mean": round(m_yes, 3), "n": len(yes), "lift": round(m_yes / m_no - 1, 3) if m_no else 0.0}
        out[dim] = dict(sorted(res.items(), key=lambda kv: -kv[1]["mean"]))
    return out


def rules(feat: dict) -> list[str]:
    th, fm, hk = _lib()
    names = {"theme": lambda k: th.get(k, {}).get("label", k), "format": lambda k: fm.get(k, {}).get("label", k),
             "hook": lambda k: hk.get(k, {}).get("label", k), "hour": lambda k: f"ore {k}",
             "short_headline": lambda k: "headline di 40 caratteri o meno" if k == "yes" else "headline lunga"}
    out = []
    for dim, vals in feat.items():
        for k, v in vals.items():
            if v["n"] >= MIN_N and abs(v["lift"]) >= MIN_LIFT:
                out.append({"dim": dim, "value": k, "label": names[dim](k), "lift": v["lift"], "n": v["n"],
                            "do": v["lift"] > 0})
    return sorted(out, key=lambda r: -abs(r["lift"]))


def predict(text: str, weights: dict | None = None) -> float:
    """Expected score (x the median) of a clip/topic from its text, using the learned feature means: the mean of
    the matching themes, format and hook (1.0 = average, no evidence)."""
    w = weights if weights is not None else _jload(OUT, {})
    feat = w.get("features") or {}
    lab = labels(text)
    vals = [feat.get(dim, {}).get(v, {}).get("mean") for dim in ("theme", "format", "hook", "short_headline")
            for v in lab.get(dim, [])]
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else 1.0


def novelty(text: str, weights: dict | None = None) -> int:
    """How often the themes of this text were already measured (lowest = least tried, for exploration)."""
    w = weights if weights is not None else _jload(OUT, {})
    th = (w.get("features") or {}).get("theme", {})
    lab = labels(text)["theme"]
    return min((th.get(k, {}).get("n", 0) for k in lab), default=0)


def writer_block(weights: dict | None = None) -> str:
    """Prompt block for the writers/planners: what the audience watched most across every channel."""
    w = weights if weights is not None else _jload(OUT, {})
    if not w.get("top"):
        return ""
    lines = ["What OUR audience watched most in the last weeks, across YouTube, Instagram, Facebook, Threads and "
             "TikTok (copy the angle and structure, never the same facts):"]
    for t in w["top"][:4]:
        lines.append(f"- '{t['title']}' ({t['score']}x our median; {', '.join(t.get('themes_en') or t['themes']) or 'no theme'})")
    if w.get("prefer_en") or w.get("prefer"):
        lines.append("- Themes that work for us: " + ", ".join((w.get("prefer_en") or w["prefer"])[:4]) + ".")
    if w.get("avoid_en") or w.get("avoid"):
        lines.append("- Themes that underperform for us (only with a much stronger angle): "
                     + ", ".join((w.get("avoid_en") or w["avoid"])[:3]) + ".")
    for r in [r for r in w.get("rules", []) if r["dim"] == "short_headline"][:1]:
        lines.append("- Clip headlines: " + ("40 characters or fewer" if (r["value"] == "yes") == r["do"] else "can be longer") + ".")
    return "\n".join(lines) + "\n"


def next_long(items: list[dict], feat: dict) -> dict | None:
    """Brief for the next long video: the most recent hit, in the same vein (never the same facts)."""
    th, _, _ = _lib()
    hits = [it for it in items if it["score"] >= HIT_ITEM or any(p["score"] >= HIT_POST for p in it["posts"])]
    if not hits:
        return None
    h = max(hits, key=lambda it: (it["published"], it["score"]))
    themes = [th[k].get("en", k) for k in it_themes(h) if k in th]
    return {"from": h["title"], "score": h["score"], "channels": h["channels"], "themes": it_themes(h),
            "hint": (f"Our clip '{h['title']}' was a hit ({h['score']}x our median across channels: "
                     f"{', '.join(f'{c} {v}x' for c, v in h['channels'].items())}). Make the next long video in the "
                     f"same vein ({', '.join(themes) or 'same angle'}): a question with a surprising, measurable answer, "
                     "explained step by step with animated numbers, built so every chapter works as a 30-50 s clip "
                     "on its own. New topic and NEW measured numbers, never the same facts.")}


def it_themes(it: dict) -> list[str]:
    return it.get("labels", {}).get("theme") or labels(it["text"])["theme"]


def learn(today: date, dry: bool = False) -> dict:
    posts = latest_posts(today)
    meds = score_posts(posts)
    items = group_items(posts)
    feat = features(items)
    th, _, _ = _lib()
    rs = rules(feat)
    tfeat = feat.get("theme", {})
    prefer = [th[k]["label"] for k, v in tfeat.items() if v["n"] >= 2 and v["mean"] >= 1.1 and k in th]
    avoid = [th[k]["label"] for k, v in reversed(list(tfeat.items())) if v["n"] >= MIN_N and v["mean"] < 0.85 and k in th]
    prefer_en = [th[k].get("en", k) for k, v in tfeat.items() if v["n"] >= 2 and v["mean"] >= 1.1 and k in th]
    avoid_en = [th[k].get("en", k) for k, v in reversed(list(tfeat.items())) if v["n"] >= MIN_N and v["mean"] < 0.85 and k in th]
    ranked = sorted(items, key=lambda it: -it["score"])
    fmt = lambda it: {"title": it["title"], "score": it["score"], "views": it["views"], "channels": it["channels"],
                      "themes": [th.get(k, {}).get("label", k) for k in it_themes(it)],
                      "themes_en": [th.get(k, {}).get("en", k) for k in it_themes(it)],
                      "published": it["published"].date().isoformat(), "hour": it["hour"]}
    state = {"updated": today.isoformat(), "items": len(items), "posts": len(posts), "channels": meds,
             "top": [fmt(it) for it in ranked[:6]], "bottom": [fmt(it) for it in ranked[-4:][::-1]] if len(ranked) > 6 else [],
             "features": feat, "rules": rs, "prefer": prefer, "avoid": avoid, "prefer_en": prefer_en, "avoid_en": avoid_en, "next_long": next_long(items, feat)}
    if not dry:
        OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1, default=str) + "\n", "utf-8")
        REPORTS.mkdir(exist_ok=True)
        (REPORTS / f"apprendimento-canali-{today.isoformat()}.md").write_text(report(state), "utf-8")
    return state


def report(s: dict) -> str:
    L = [f"# Apprendimento da tutti i canali ({s['updated']})", "",
         f"Post letti: {s['posts']} (solo video: Short, Reel, video Threads/TikTok; almeno 12 ore di vita, ultimi {MAX_AGE_DAYS} giorni), raggruppati in {s['items']} "
         "contenuti (lo stesso video su più canali conta una volta).", "",
         "Punteggio = volte la mediana del canale (1 = nella media). Instagram: views, tempo medio di visione, "
         "interazioni (salvataggi e condivisioni pesano di più); YouTube: views e % visto; Facebook, Threads, TikTok: "
         "views. Contenuto = media pesata dei canali (IG 30%, YT 30%, TikTok 15%, Threads 15%, FB 10%).", "",
         "## Cosa ha funzionato"]
    for t in s["top"]:
        ch = ", ".join(f"{c} {v}x" for c, v in t["channels"].items())
        L.append(f"- **{t['title']}**: {t['score']}x, {t['views']} views totali ({ch}); temi: "
                 f"{', '.join(t['themes']) or '-'}; ore {t['hour']}; {t['published']}")
    if s["bottom"]:
        L += ["", "## Cosa no"]
        for t in s["bottom"]:
            L.append(f"- {t['title']}: {t['score']}x, {t['views']} views ({', '.join(t['themes']) or '-'})")
    L += ["", "## Regole dai dati (almeno 3 contenuti, differenza almeno 20%)"]
    L += [f"- {'SI' if r['do'] else 'NO'}: {r['label']} ({r['dim']}, {'+' if r['lift'] > 0 else ''}{round(r['lift'] * 100)}%, "
          f"n {r['n']})" for r in s["rules"]] or ["- Nessuna ancora: servono più dati."]
    L += ["", "## Temi (media ridotta verso 1 finché i dati sono pochi)"]
    th, _, _ = _lib()
    for k, v in s["features"].get("theme", {}).items():
        L.append(f"- {th.get(k, {}).get('label', k)}: {v['mean']}x su {v['n']} contenuti")
    L += ["", "## Decisioni automatiche"]
    if s["next_long"]:
        L.append(f"- Prossimo video lungo: sulla scia di \"{s['next_long']['from']}\" ({s['next_long']['score']}x). "
                 "longform-auto lo usa come indicazione di argomento quando non ne riceve una.")
    L.append("- Clip del giorno: tools/day_clip.py sceglie la clip non usata con il punteggio previsto più alto "
             "(1 giorno su 5 prova il tema meno testato).")
    L.append("- Clip dei nuovi video lunghi: tools/auto_clips.py ordina i capitoli con gli stessi pesi.")
    L.append("- Lo scrittore dei video lunghi riceve i temi che vanno e quelli da evitare.")
    L += ["", "## Medie per canale", ""]
    L += [f"- {k}: {v['posts']} post, mediana views {v['median_views']}" for k, v in s["channels"].items()]
    return "\n".join(L) + "\n"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    cmd = a[0] if a else "learn"
    today = date.fromisoformat(a[a.index("--date") + 1]) if "--date" in a else date.today()
    if cmd == "learn":
        s = learn(today, dry="--dry-run" in a)
        print(report(s))
    elif cmd == "show":
        print(writer_block() or "(no cross-weights yet)")
        print(json.dumps(_jload(OUT, {}).get("next_long"), ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
