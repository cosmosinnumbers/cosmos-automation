"""Scan a new niche on YouTube with the official Data API (read-only, no scraping, no downloads) and let Gemini
confirm the visual style from the thumbnails. Built for the stick man explainer niche (owner 03/11/2026).

  python tools/niche_scan.py <niche>          config: research/niches/<niche>.json ("scan" block)

Writes research/<niche>/scan-<YYYY-MM-DD>.json and .md:
- videos found by the scan queries in two windows (last 30 days = what is viral now, last 365 days = proven formats),
  with views/day, engagement, duration, title features;
- channels with subscribers, age, total videos, median views of the found videos and an "outlier" score
  (views per subscriber), so young channels that blow up stand out;
- style check: Gemini looks at the thumbnails in batches of 10 and says if they are stick figure / simple 2D drawings
  (no key or quota out = "unknown", the report says so);
- title patterns of the style-confirmed videos (length, question, number, "what if", "every", "why", "you").
Also writes research/<niche>/watchlist.json (style-confirmed videos, fastest first) for tools/gemini_watch.py.
Quota: ~100 units per search; with the default 14 queries x 2 windows it uses ~3,000 of the 10,000 daily units.
"""
from __future__ import annotations

import base64
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
YT = "https://www.googleapis.com/youtube/v3"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
STYLE_PROMPT = """These are {n} YouTube thumbnails, numbered 1 to {n} in order.
For each one say if the main artwork is a STICK FIGURE or very simple hand-drawn/2D flat character animation
(stick man, round-head doodle, whiteboard doodle) as opposed to real footage, 3D/CGI, a real person, or detailed
anime/cartoon art. Reply with JSON only: [{{"i": 1, "stick": true|false, "style": "3-6 words", "colors": "2-4 words"}}, ...]."""


def iso_dur(s: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def title_features(t: str) -> dict:
    low = t.lower()
    return {"chars": len(t), "words": len(t.split()), "question": "?" in t, "number": bool(re.search(r"\d", t)),
            "what_if": "what if" in low, "every": low.startswith("every ") or " every " in low,
            "why": low.startswith("why"), "how": low.startswith("how"), "you": bool(re.search(r"\byou(r)?\b", low)),
            "explained": "explained" in low, "emoji": bool(re.search(r"[\U0001F300-\U0001FAFF]", t)),
            "caps_word": bool(re.search(r"\b[A-Z]{3,}\b", t))}


def yt_get(path: str, **params) -> dict:
    r = requests.get(f"{YT}/{path}", params=params, timeout=30).json()
    if "error" in r:
        raise RuntimeError(f"YouTube API: {r['error'].get('message', '')[:160]}")
    return r


def search(key: str, queries: list[str], days: int, per_query: int, region: str) -> dict[str, list[str]]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found: dict[str, list[str]] = {}
    for q in queries:
        r = yt_get("search", key=key, q=q, part="id", type="video", order="viewCount", publishedAfter=since,
                   maxResults=per_query, relevanceLanguage="en", regionCode=region)
        for it in r.get("items", []):
            found.setdefault(it["id"]["videoId"], []).append(q)
    return found


def videos(key: str, ids: list[str]) -> list[dict]:
    out, now = [], datetime.now(timezone.utc)
    for i in range(0, len(ids), 50):
        r = yt_get("videos", key=key, id=",".join(ids[i:i + 50]), part="snippet,statistics,contentDetails")
        for v in r.get("items", []):
            st, sn = v["statistics"], v["snippet"]
            pub = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
            age = max((now - pub).days, 1)
            views, likes, comm = int(st.get("viewCount", 0)), int(st.get("likeCount", 0)), int(st.get("commentCount", 0))
            th = sn.get("thumbnails", {})
            out.append({"id": v["id"], "title": sn["title"], "channel": sn["channelTitle"], "channel_id": sn["channelId"],
                        "published": sn["publishedAt"][:10], "age_days": age,
                        "duration_s": iso_dur(v["contentDetails"].get("duration", "")),
                        "views": views, "views_per_day": views // age, "likes": likes, "comments": comm,
                        "engagement": round((likes + comm) / max(views, 1), 4),
                        "thumb": (th.get("high") or th.get("medium") or th.get("default") or {}).get("url", ""),
                        "tags": sn.get("tags", [])[:15], "features": title_features(sn["title"])})
    return out


def channels(key: str, ids: list[str]) -> dict[str, dict]:
    out, now = {}, datetime.now(timezone.utc)
    for i in range(0, len(ids), 50):
        r = yt_get("channels", key=key, id=",".join(ids[i:i + 50]), part="snippet,statistics")
        for c in r.get("items", []):
            st, sn = c["statistics"], c["snippet"]
            created = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
            out[c["id"]] = {"title": sn["title"], "handle": sn.get("customUrl", ""), "created": sn["publishedAt"][:10],
                            "age_days": max((now - created).days, 1), "country": sn.get("country", ""),
                            "subs": int(st.get("subscriberCount", 0)) if not st.get("hiddenSubscriberCount") else None,
                            "total_views": int(st.get("viewCount", 0)), "video_count": int(st.get("videoCount", 0))}
    return out


def gemini_cfg():
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return {"api_key": k, "model": os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")}
    f = ROOT / "secrets" / "gemini.json"
    return json.loads(f.read_text("utf-8")) if f.exists() else None


def style_check(vids: list[dict], cfg: dict | None, batch: int = 10) -> str:
    """Sets v["style"] = {"stick": bool|None, ...}. Returns a short status for the report."""
    if not cfg:
        for v in vids:
            v["style"] = {"stick": None}
        return "Gemini non configurato: stile non verificato (stick = sconosciuto)."
    done = failed = 0
    models = [cfg.get("model", "gemini-3.8-flash"), "gemini-3.6-flash"]
    for i in range(0, len(vids), batch):
        chunk = vids[i:i + batch]
        parts = []
        for v in chunk:
            try:
                img = requests.get(v["thumb"], timeout=20).content
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img).decode()}})
            except requests.RequestException:
                parts.append({"text": "(thumbnail missing)"})
        parts.append({"text": STYLE_PROMPT.format(n=len(chunk))})
        body = {"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json"}}
        res = None
        for attempt in range(4):
            try:
                r = requests.post(GEMINI.format(model=models[0] if attempt < 2 else models[1]),
                                  params={"key": cfg["api_key"]}, json=body, timeout=120)
            except requests.RequestException:
                continue
            if r.status_code in (429, 500, 503):
                time.sleep(20 * (attempt + 1))
                continue
            if r.status_code == 200:
                try:
                    txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
                    res = {int(x["i"]): x for x in json.loads(txt)}
                except (KeyError, ValueError, TypeError):
                    res = None
            break
        for n, v in enumerate(chunk, 1):
            x = (res or {}).get(n)
            v["style"] = {"stick": bool(x.get("stick")), "style": x.get("style", ""), "colors": x.get("colors", "")} if x else {"stick": None}
        if res:
            done += len(chunk)
        else:
            failed += len(chunk)
        time.sleep(4)  # free tier: stay under the per-minute limit
    return f"Stile verificato da Gemini sulle miniature: {done} video; non verificati: {failed}."


def pct(values: list[bool]) -> str:
    return f"{round(100 * sum(values) / len(values))}%" if values else "n/d"


def report(niche: str, cfg_n: dict, vids: list[dict], chans: dict, style_status: str) -> str:
    stick = [v for v in vids if v["style"].get("stick")]
    pool = stick or vids
    L = [f"# {cfg_n.get('name', niche)}: scansione nicchia ({time.strftime('%d/%m/%Y')})", "",
         f"Fonte: YouTube Data API (ricerca per query, ordinata per visualizzazioni), {len(vids)} video unici, "
         f"{len(chans)} canali. {style_status}", "",
         "Le visualizzazioni sono pubbliche al momento della scansione; i ricavi non sono misurabili da qui (stima solo con RPM di nicchia).", ""]
    # channels ranked by views of their style-confirmed videos and by outlier ratio
    by_ch: dict[str, list[dict]] = {}
    for v in pool:
        by_ch.setdefault(v["channel_id"], []).append(v)
    rows = []
    for cid, vs in by_ch.items():
        c = chans.get(cid, {})
        med = int(statistics.median(x["views"] for x in vs))
        subs = c.get("subs") or 0
        rows.append((med, cid, c, vs, round(med / subs, 2) if subs else None))
    rows.sort(key=lambda r: -r[0])
    L += ["## Canali (solo stile stick man confermato, se disponibile)", "",
          "| Canale | Iscritti | Età canale (gg) | Video totali | Views totali | Video trovati | Mediana views trovate | Views/iscritti |",
          "|---|---|---|---|---|---|---|---|"]
    for med, cid, c, vs, ratio in rows[:30]:
        L.append(f"| [{c.get('title', vs[0]['channel'])}](https://www.youtube.com/channel/{cid}) {c.get('handle', '')} | "
                 f"{c.get('subs') if c.get('subs') is not None else 'nascosti'} | {c.get('age_days', '?')} | {c.get('video_count', '?')} | "
                 f"{c.get('total_views', '?')} | {len(vs)} | {med} | {ratio if ratio is not None else 'n/d'} |")
    L += ["", "## Video più veloci (views/giorno)", "",
          "| Titolo | Canale | Pubblicato | Durata | Views | Views/giorno | Engagement | Stile |", "|---|---|---|---|---|---|---|---|"]
    for v in sorted(pool, key=lambda v: -v["views_per_day"])[:40]:
        d = v["duration_s"]
        L.append(f"| [{v['title']}](https://www.youtube.com/watch?v={v['id']}) | {v['channel']} | {v['published']} | "
                 f"{d // 60}:{d % 60:02d} | {v['views']} | {v['views_per_day']} | {v['engagement']} | {v['style'].get('style', '')} |")
    feats = [v["features"] for v in pool]
    durs = [v["duration_s"] for v in pool if v["duration_s"]]
    L += ["", "## Schema dei titoli (video stick man)", "",
          f"- Lunghezza media: {round(statistics.mean(f['chars'] for f in feats)) if feats else 'n/d'} caratteri, "
          f"{round(statistics.mean(f['words'] for f in feats), 1) if feats else 'n/d'} parole.",
          f"- Domanda: {pct([f['question'] for f in feats])} · numero: {pct([f['number'] for f in feats])} · \"What if\": "
          f"{pct([f['what_if'] for f in feats])} · \"Every\": {pct([f['every'] for f in feats])} · inizia con Why: "
          f"{pct([f['why'] for f in feats])} · How: {pct([f['how'] for f in feats])} · \"you/your\": {pct([f['you'] for f in feats])} · "
          f"\"explained\": {pct([f['explained'] for f in feats])} · emoji: {pct([f['emoji'] for f in feats])} · parola MAIUSCOLA: "
          f"{pct([f['caps_word'] for f in feats])}.",
          f"- Durata: mediana {int(statistics.median(durs)) // 60} min {int(statistics.median(durs)) % 60} s; "
          f"Short (≤60 s): {pct([d <= 60 for d in durs])}; 8-20 min: {pct([480 <= d <= 1200 for d in durs])}; oltre 20 min: "
          f"{pct([d > 1200 for d in durs])}." if durs else "- Durata: n/d.",
          "", "## Da quali ricerche arrivano", ""]
    qcount: dict[str, int] = {}
    for v in pool:
        for q in v.get("queries", []):
            qcount[q] = qcount.get(q, 0) + 1
    L += [f"- {q}: {n} video" for q, n in sorted(qcount.items(), key=lambda x: -x[1])]
    return "\n".join(L) + "\n"


def main(niche: str):
    cfg_n = json.loads((ROOT / "research" / "niches" / f"{niche}.json").read_text("utf-8"))
    sc = cfg_n.get("scan", {})
    kf = ROOT / "secrets" / "youtube_key.txt"
    key = os.environ.get("YOUTUBE_API_KEY") or (kf.read_text().strip() if kf.exists() else None)
    if not key:
        sys.exit("YOUTUBE_API_KEY not configured.")
    found: dict[str, list[str]] = {}
    for days in sc.get("windows_days", [30, 365]):
        for vid, qs in search(key, sc["queries"], days, sc.get("per_query", 25), cfg_n.get("region", "US")).items():
            found.setdefault(vid, [])
            found[vid] += [f"{q} ({days}g)" for q in qs]
    vids = videos(key, list(found))
    for v in vids:
        v["queries"] = sorted(set(found.get(v["id"], [])))
    vids = [v for v in vids if v["views"] >= sc.get("min_views", 20000)]
    vids.sort(key=lambda v: -v["views_per_day"])
    vids = vids[:sc.get("max_videos", 150)]
    chans = channels(key, sorted({v["channel_id"] for v in vids}))
    status = style_check(vids, gemini_cfg())
    folder = ROOT / "research" / niche
    folder.mkdir(parents=True, exist_ok=True)
    day = time.strftime("%Y-%m-%d")
    (folder / f"scan-{day}.json").write_text(json.dumps({"date": day, "style_status": status, "videos": vids,
                                                         "channels": chans}, indent=1, ensure_ascii=False), "utf-8")
    (folder / f"scan-{day}.md").write_text(report(niche, cfg_n, vids, chans, status), "utf-8")
    watch = [v for v in vids if v["style"].get("stick")] or vids
    (folder / "watchlist.json").write_text(json.dumps({"youtube": {"videos": watch}}, indent=1, ensure_ascii=False), "utf-8")
    print(f"{len(vids)} videos, {len(chans)} channels, {sum(1 for v in vids if v['style'].get('stick'))} stick-style. {status}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
