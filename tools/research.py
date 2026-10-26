"""Weekly niche research with free official APIs only (no scraping): the free alternative to Apify.

  python research.py <niche> [--only youtube,reddit,instagram,trends]

<niche> = research/niches/<niche>.json (keywords, subreddits, hashtags, trends terms).
Output: research/<niche>/<YYYY-Www>.json (raw data) and .md (report read by cosmos-strategy-weekly).

Sources and credentials (secret env var or file in the local secrets folder, see creds.py; a missing one is skipped):
- YouTube Data API v3, key YOUTUBE_API_KEY (or secrets/youtube_key.txt). Free quota 10,000 units/day:
  search = 100 units, videos/commentThreads = 1 unit. Videos of the last 30 days, ranked by views per day.
- Reddit API, secret REDDIT_JSON (client_id, client_secret, user_agent; app type "script", read-only
  application-only OAuth). Top posts of the week per subreddit + keyword search.
- Instagram Graph API hashtag search with the Page token in META_JSON (max 30 distinct hashtags per 7 days).
- Google Trends via pytrends (unofficial, may answer 429: skipped then, never retried in a loop).
Sentiment: VADER on comment and post texts, computed locally (no tokens). Claude reads only the report.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402

OUT = creds.REPO / "research"
YT = "https://www.googleapis.com/youtube/v3"
UA = "cosmos-research/1.0 (by cosmosinnumbers)"
STOP = set("the a an and or of to in is it this that for on with you your i my we are was be at as by from not "
           "have has but they what so if can just do how its about all more one me no like would there their".split())


def secret(name: str, file: str):
    v = os.environ.get(name)
    if v:
        return v
    p = creds.LOCAL_SECRETS / file
    return p.read_text("utf-8").strip() if p.exists() else None


def sentiment(texts):
    """Share of positive / neutral / negative texts (VADER compound >= 0.05 / <= -0.05)."""
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    a, c = SentimentIntensityAnalyzer(), Counter()
    for t in texts:
        s = a.polarity_scores(t)["compound"]
        c["pos" if s >= 0.05 else "neg" if s <= -0.05 else "neu"] += 1
    n = sum(c.values()) or 1
    return {"n": sum(c.values()), **{k: round(c[k] / n, 2) for k in ("pos", "neu", "neg")}}


def top_words(texts, k=15):
    words = Counter(w for t in texts for w in re.findall(r"[a-z][a-z'-]{3,}", t.lower()) if w not in STOP)
    return [w for w, _ in words.most_common(k)]


def questions(texts, k=10):
    qs = [s.strip() for t in texts for s in re.split(r"(?<=[?])\s+", t) if s.strip().endswith("?") and 15 < len(s) < 160]
    return list(dict.fromkeys(qs))[:k]


def youtube(cfg):
    key = secret("YOUTUBE_API_KEY", "youtube_key.txt")
    if not key:
        return {"skipped": "YOUTUBE_API_KEY not configured"}
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = []
    for q in cfg["youtube_queries"]:
        r = requests.get(f"{YT}/search", params={"key": key, "q": q, "part": "id", "type": "video", "order": "viewCount",
                                                  "publishedAfter": since, "maxResults": 15, "relevanceLanguage": "en",
                                                  "regionCode": cfg.get("region", "US")}, timeout=30).json()
        if "error" in r:
            return {"skipped": f"YouTube API: {r['error'].get('message', '')[:120]}"}
        ids += [i["id"]["videoId"] for i in r.get("items", [])]
    ids = list(dict.fromkeys(ids))
    vids = []
    for i in range(0, len(ids), 50):
        r = requests.get(f"{YT}/videos", params={"key": key, "id": ",".join(ids[i:i + 50]),
                                                 "part": "snippet,statistics,contentDetails"}, timeout=30).json()
        for v in r.get("items", []):
            st, sn = v["statistics"], v["snippet"]
            age = max((datetime.now(timezone.utc) - datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))).days, 1)
            views = int(st.get("viewCount", 0))
            vids.append({"id": v["id"], "title": sn["title"], "channel": sn["channelTitle"], "published": sn["publishedAt"][:10],
                         "duration": v["contentDetails"]["duration"], "views": views, "views_per_day": views // age,
                         "likes": int(st.get("likeCount", 0)), "comments": int(st.get("commentCount", 0)),
                         "engagement": round((int(st.get("likeCount", 0)) + int(st.get("commentCount", 0))) / max(views, 1), 4)})
    vids.sort(key=lambda v: v["views_per_day"], reverse=True)
    texts = []
    for v in vids[:8]:  # comments of the 8 fastest-growing videos, for sentiment and audience questions
        r = requests.get(f"{YT}/commentThreads", params={"key": key, "videoId": v["id"], "part": "snippet",
                                                         "order": "relevance", "maxResults": 50, "textFormat": "plainText"}, timeout=30).json()
        texts += [c["snippet"]["topLevelComment"]["snippet"]["textDisplay"] for c in r.get("items", [])]
    return {"videos": vids[:25], "comments_analyzed": len(texts), "sentiment": sentiment(texts),
            "top_words": top_words(texts), "audience_questions": questions(texts)}


def reddit(cfg):
    raw = secret("REDDIT_JSON", "reddit.json")
    if not raw:
        return {"skipped": "REDDIT_JSON not configured"}
    c = json.loads(raw)
    tok = requests.post("https://www.reddit.com/api/v1/access_token", auth=(c["client_id"], c["client_secret"]),
                        data={"grant_type": "client_credentials"}, headers={"User-Agent": c.get("user_agent", UA)}, timeout=30).json()
    if "access_token" not in tok:
        return {"skipped": f"Reddit auth failed: {tok.get('error', tok)}"}
    h = {"Authorization": f"bearer {tok['access_token']}", "User-Agent": c.get("user_agent", UA)}
    posts = []
    for sub in cfg["subreddits"]:
        r = requests.get(f"https://oauth.reddit.com/r/{sub}/top", params={"t": "week", "limit": 25}, headers=h, timeout=30)
        posts += [p["data"] for p in r.json().get("data", {}).get("children", [])] if r.ok else []
        time.sleep(1)  # well under the 100 requests/minute limit
    for kw in cfg["reddit_keywords"]:
        r = requests.get("https://oauth.reddit.com/search", params={"q": kw, "t": "week", "sort": "top", "limit": 25},
                         headers=h, timeout=30)
        posts += [p["data"] for p in r.json().get("data", {}).get("children", [])] if r.ok else []
        time.sleep(1)
    seen, top = set(), []
    for p in sorted(posts, key=lambda p: p.get("score", 0), reverse=True):
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        top.append({"sub": p["subreddit"], "title": p["title"], "score": p["score"], "comments": p["num_comments"],
                    "url": f"https://www.reddit.com{p['permalink']}"})
    texts = [p["title"] + " " + (p.get("selftext") or "")[:500] for p in posts]
    return {"posts": top[:30], "posts_analyzed": len(texts), "sentiment": sentiment(texts),
            "top_words": top_words(texts), "audience_questions": questions(texts)}


def instagram(cfg):
    if not (os.environ.get("META_JSON") or (creds.LOCAL_SECRETS / "meta.json").exists()):
        return {"skipped": "META_JSON not configured"}
    m = creds.load("meta")
    tok, ig, out = m["page_token"], m.get("ig_user_id"), {}
    for tag in cfg["ig_hashtags"]:
        r = requests.get("https://graph.facebook.com/v21.0/ig_hashtag_search",
                         params={"user_id": ig, "q": tag, "access_token": tok}, timeout=30).json()
        if "error" in r:
            out[tag] = {"error": r["error"].get("message", "")[:120]}
            continue
        hid = r["data"][0]["id"]
        r = requests.get(f"https://graph.facebook.com/v21.0/{hid}/top_media",
                         params={"user_id": ig, "access_token": tok, "limit": 25,
                                 "fields": "caption,media_type,like_count,comments_count,permalink,timestamp"}, timeout=30).json()
        media = sorted(r.get("data", []), key=lambda x: x.get("like_count", 0), reverse=True)
        out[tag] = [{"type": x.get("media_type"), "likes": x.get("like_count"), "comments": x.get("comments_count"),
                     "url": x.get("permalink"), "caption": (x.get("caption") or "")[:150]} for x in media[:10]]
    return out


def trends(cfg):
    try:
        from pytrends.request import TrendReq
        t = TrendReq(hl="en-US", tz=0, timeout=(10, 30))
        t.build_payload(cfg["trends_terms"][:5], timeframe="today 3-m")
        df = t.interest_over_time()
        if df.empty:
            return {"skipped": "no data"}
        last, prev = df.tail(4).mean(), df.iloc[-8:-4].mean()
        return {k: {"last_4w": round(float(last[k])), "change": round(float(last[k] - prev[k]))} for k in cfg["trends_terms"][:5]}
    except Exception as e:  # unofficial endpoint: a 429 is normal, the report just says so
        return {"skipped": f"Google Trends unavailable: {type(e).__name__}"}


def report(name, week, d):
    L = [f"# Ricerca settimanale {name}: {week}", "",
         f"Generato {creds.now_local():%d/%m/%Y %H:%M} (ora italiana) da GitHub Actions. Fonti: API ufficiali gratuite; "
         "sentiment calcolato con VADER (positivo/neutro/negativo, quote sul totale dei testi).", ""]
    off = {"skipped": "not run this time (--only)"}
    y = d.get("youtube", off)
    L += ["## YouTube: video della nicchia più in crescita (ultimi 30 giorni, visualizzazioni al giorno)", ""]
    if "skipped" in y:
        L += [f"Saltato: {y['skipped']}", ""]
    else:
        L += ["| Video | Canale | Pubblicato | Views | Views/giorno | Engagement |", "|---|---|---|---|---|---|"]
        L += [f"| [{v['title'][:60]}](https://youtu.be/{v['id']}) | {v['channel']} | {v['published']} | {v['views']:,} | "
              f"{v['views_per_day']:,} | {v['engagement']:.1%} |" for v in y["videos"][:15]]
        s = y["sentiment"]
        L += ["", f"Commenti analizzati: {y['comments_analyzed']} (8 video più in crescita). Sentiment: "
              f"{s['pos']:.0%} positivo, {s['neu']:.0%} neutro, {s['neg']:.0%} negativo.",
              f"Parole più frequenti: {', '.join(y['top_words'])}.", "", "Domande dell'audience:"]
        L += [f"- {q}" for q in y["audience_questions"]] + [""]
    r = d.get("reddit", off)
    L += ["## Reddit: post più votati della settimana", ""]
    if "skipped" in r:
        L += [f"Saltato: {r['skipped']}", ""]
    else:
        L += [f"- [{p['title'][:90]}]({p['url']}) r/{p['sub']}, {p['score']:,} voti, {p['comments']} commenti" for p in r["posts"][:15]]
        s = r["sentiment"]
        L += ["", f"Post analizzati: {r['posts_analyzed']}. Sentiment: {s['pos']:.0%} positivo, {s['neu']:.0%} neutro, "
              f"{s['neg']:.0%} negativo.", f"Parole più frequenti: {', '.join(r['top_words'])}.", "", "Domande ricorrenti:"]
        L += [f"- {q}" for q in r["audience_questions"]] + [""]
    ig = d.get("instagram", off)
    L += ["## Instagram: post migliori per hashtag", ""]
    if "skipped" in ig:
        L += [f"Saltato: {ig['skipped']}", ""]
    for tag, items in ig.items():
        if tag == "skipped":
            continue
        if isinstance(items, dict):
            L += [f"- #{tag}: errore API ({items['error']})"]
            continue
        L += [f"- #{tag}: " + "; ".join(f"[{x['type']}, {x['likes'] or 0} like]({x['url']})" for x in items[:5])]
    tr = d.get("trends", off)
    L += ["", "## Google Trends (interesse medio ultime 4 settimane, variazione sulle 4 precedenti)", ""]
    L += [f"Saltato: {tr['skipped']}"] if "skipped" in tr else [f"- {k}: {v['last_4w']} ({v['change']:+d})" for k, v in tr.items()]
    return "\n".join(L) + "\n"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    niche = sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__)
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else ["youtube", "reddit", "instagram", "trends"]
    cfg = json.loads((OUT / "niches" / f"{niche}.json").read_text("utf-8"))
    week = creds.now_local().strftime("%G-W%V")
    data = {}
    for src in only:
        try:
            data[src] = globals()[src](cfg)
        except Exception as e:  # one broken source never stops the others
            data[src] = {"skipped": f"{type(e).__name__}: {str(e)[:150]}"}
        print(src, "->", data[src].get("skipped", "ok") if isinstance(data[src], dict) else "ok")
    out = OUT / niche
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{week}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
    (out / f"{week}.md").write_text(report(cfg["name"], week, data), "utf-8")
    print(f"report: research/{niche}/{week}.md")


if __name__ == "__main__":
    main()
