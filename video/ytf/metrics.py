"""Daily metrics snapshot for every Cosmos channel (read-only, free API quotas, never publishes).

  python metrics.py all                  every source below, one snapshot per object per day
  python metrics.py youtube|instagram|facebook|threads|gumroad|comments
  python metrics.py yt-auth              one-time Google consent for YouTube Analytics (yt-analytics.readonly),
                                         token in secrets/token_analytics.json (the owner clicks "Allow")
  python metrics.py defs                 rewrite 07-analytics/metrics/DEFINIZIONI.md
  python metrics.py manual <channel> <rows.json>   readings from TikTok Studio / Gumroad Analytics (Chrome)

Output: 07-analytics/metrics/<channel>.jsonl, one JSON line per object (video, post, account) per reading day:
  {"read_at", "date", "channel", "level", "id", "title", "kind", "published", "metrics": {...}, "missing": {...}}
A re-run on the same day replaces that day's lines. A metric the API refuses is never estimated: it goes in
"missing" with the reason (the reports print it as "non misurato"). X and TikTok are not read here:
X reads cost money and the account is empty by choice; TikTok has no approved API (weekly from TikTok Studio).
Secrets are read from secrets/*.json only and never printed.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import meta_api  # noqa: E402

ROOT = meta_api.ROOT
OUT = ROOT / "07-analytics" / "metrics"
SECRETS = ROOT / "secrets"
SINCE = "2026-10-01"  # channels opened in October 2026

DEFS = {
    "youtube": {
        "views": "Visualizzazioni totali dalla pubblicazione (Data API videos.statistics.viewCount; per gli Short YouTube conta ogni avvio, dal 31/03/2025).",
        "likes": "Mi piace totali (Data API).",
        "comments": "Commenti totali (Data API).",
        "an_views": "Visualizzazioni dal 01/10/2026 a oggi secondo YouTube Analytics (possono differire da views per ritardo e filtri antispam).",
        "minutes_watched": "Minuti di visione stimati (Analytics estimatedMinutesWatched).",
        "avg_view_duration_s": "Durata media di visione in secondi (Analytics averageViewDuration).",
        "avg_view_pct": "Percentuale media visualizzata (Analytics averageViewPercentage; per gli Short può superare 100 con le ripetizioni).",
        "r5": "Quota di spettatori ancora presenti al 5% del video (curva di ritenzione, audienceWatchRatio; solo organico).",
        "r25": "Quota ancora presente al 25% del video.", "r50": "Quota ancora presente al 50% del video.", "r75": "Quota ancora presente al 75% del video.",
        "r100": "Quota ancora presente alla fine (per gli Short pu\u00f2 superare 1 se si rivede).",
        "worst_drop": "Calo massimo tra due punti consecutivi della curva (1% del video).", "worst_drop_at_pct": "A che % del video avviene il calo massimo.",
        "subs_gained": "Iscritti guadagnati dal video (Analytics subscribersGained).",
        "shares": "Condivisioni (Analytics shares).",
        "link_clicks": "Non esposti dalle API: i clic sui link in descrizione non sono misurati.",
    },
    "instagram": {
        "views": "Visualizzazioni (Graph API insights 'views': volte in cui il contenuto è stato riprodotto o mostrato).",
        "reach": "Account unici che hanno visto il contenuto (stima di Meta).",
        "saved": "Salvataggi.", "shares": "Condivisioni.", "likes": "Mi piace.", "comments": "Commenti.",
        "total_interactions": "Somma di mi piace, salvataggi, commenti e condivisioni meno quelli annullati.",
        "avg_watch_ms": "Reel: tempo medio di visione in millisecondi (ig_reels_avg_watch_time).",
        "watch_total_ms": "Reel: tempo totale di visione in millisecondi (ig_reels_video_view_total_time).",
        "replies": "Storie: risposte.",
        "acct_profile_views": "Account: visite al profilo nel giorno precedente (profile_views, period=day).",
        "acct_website_clicks": "Account: clic sul link del profilo nel giorno precedente (website_clicks).",
        "acct_reach": "Account: copertura del giorno precedente.",
        "acct_followers": "Account: follower totali (followers_count).",
    },
    "facebook": {
        "views": "Reel: riproduzioni iniziali (blue_reels_play_count). Post e caroselli: visualizzazioni (post_media_view).",
        "plays_total": "Reel: riproduzioni totali, ripetizioni incluse (fb_reels_total_plays).",
        "reach": "Post e caroselli: persone uniche (post_total_media_view_unique). Per i Reel non esposta (post_impressions_unique non più valida).",
        "clicks": "Post: clic sul post (post_clicks).",
        "avg_watch_ms": "Reel: tempo medio di visione in millisecondi (post_video_avg_time_watched).",
        "likes": "Mi piace.", "comments": "Commenti.", "shares": "Condivisioni.",
        "acct_followers": "Pagina: follower totali (followers_count).",
        "acct_page_views": "Pagina: visualizzazioni della Pagina del giorno precedente (page_views_total).",
    },
    "threads": {
        "views": "Visualizzazioni del post (Threads insights 'views').",
        "likes": "Mi piace.", "replies": "Risposte.", "reposts": "Repost.", "quotes": "Citazioni.", "shares": "Condivisioni.",
    },
    "gumroad": {
        "sales": "Vendite totali del prodotto (Gumroad API products.sales_count).",
        "revenue_usd": "Incasso lordo in dollari (products.sales_usd_cents / 100).",
        "visits": "Visite alla pagina prodotto: non esposte dall'API, si leggono da Gumroad → Analytics (pagina, a mano o con Chrome).",
    },
}


def now():
    return dt.datetime.now(dt.timezone.utc)


def save(channel: str, rows: list[dict]):
    """Append today's snapshot, replacing any earlier reading of the same day."""
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{channel}.jsonl"
    today = now().date().isoformat()
    old = [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()] if p.exists() else []
    fresh = {(r["level"], r["id"]) for r in rows}
    keep = [r for r in old if not (r["date"] == today and (r["level"], r["id"]) in fresh)]
    stamp = now().isoformat(timespec="seconds")
    for r in rows:
        r.update(read_at=stamp, date=today, channel=channel)
    with p.open("w", encoding="utf-8") as f:
        for r in keep + rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    miss = sorted({k for r in rows for k in r.get("missing", {})})
    print(f"{channel}: {len(rows)} righe -> {p.relative_to(ROOT)}" + (f" | non misurato: {', '.join(miss)}" if miss else ""))


def row(level, oid, title="", kind="", published="", metrics=None, missing=None):
    return {"level": level, "id": str(oid), "title": (title or "")[:90].replace("\n", " "), "kind": kind,
            "published": published, "metrics": metrics or {}, "missing": missing or {}}


def g(path, **params):
    """Meta GET that returns (json, error) instead of exiting."""
    try:
        return meta_api.call("GET", path, params={"access_token": meta_api.cfg()["page_token"], **params}), None
    except SystemExit as e:
        return None, str(e)[:200]


def insights(obj_id, names, edge="insights", **extra):
    """Ask each metric separately so one unsupported metric does not hide the others."""
    got, miss = {}, {}
    for n in names:
        j, err = g(f"{obj_id}/{edge}", metric=n, **extra)
        if err:
            miss[n] = err
            continue
        for d in (j or {}).get("data", []):
            v = d.get("total_value", {}).get("value") if "total_value" in d else (d.get("values") or [{}])[-1].get("value")
            got.setdefault(d["name"], v)  # first entry = lifetime/total; later ones are daily breakdowns
    return got, miss


# ---------- YouTube ----------
AN_SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly", "https://www.googleapis.com/auth/youtube.readonly"]
AN_TOKEN = SECRETS / "token_analytics.json"


def yt_analytics(interactive=False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(str(AN_TOKEN), AN_SCOPES) if AN_TOKEN.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            return None
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS / "client_secret.json"), AN_SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
    AN_TOKEN.write_text(creds.to_json(), "utf-8")
    return build("youtubeAnalytics", "v2", credentials=creds)


def retention_curve(an, vid):
    """Per-video retention curve (audienceWatchRatio per 1% of elapsed time) -> list of 100 floats, or None."""
    r = an.reports().query(ids="channel==MINE", startDate=SINCE, endDate=now().date().isoformat(),
                           dimensions="elapsedVideoTimeRatio", metrics="audienceWatchRatio",
                           filters=f"video=={vid};audienceType==ORGANIC", sort="elapsedVideoTimeRatio").execute()
    rows = r.get("rows") or []
    return [round(x[1], 3) for x in rows] or None


def curve_summary(curve):
    """Where viewers leave: watch ratio at 3 s-equivalent (first 5%), at 25/50/75/100% and the steepest drop."""
    if not curve:
        return {}
    n = len(curve)
    at = lambda f: curve[min(n - 1, int(f * (n - 1)))]  # noqa: E731
    drops = [(curve[i] - curve[i + 1], i + 1) for i in range(n - 1)]
    d, pos = max(drops)
    return {"r5": at(.05), "r25": at(.25), "r50": at(.5), "r75": at(.75), "r100": at(1.0),
            "worst_drop": round(d, 3), "worst_drop_at_pct": pos}


def youtube():
    import yt_api
    from stats import iso_seconds
    yt = yt_api.service()
    ch = yt.channels().list(part="contentDetails,statistics", mine=True).execute()["items"][0]
    ids = [i["contentDetails"]["videoId"] for i in yt.playlistItems().list(
        part="contentDetails", playlistId=ch["contentDetails"]["relatedPlaylists"]["uploads"], maxResults=50).execute()["items"]]
    vids = [v for v in yt.videos().list(part="snippet,statistics,status,contentDetails", id=",".join(ids)).execute()["items"]
            if v["status"]["privacyStatus"] == "public"]
    an, an_err = None, "manca il consenso yt-analytics.readonly (metrics.py yt-auth)"
    try:
        an = yt_analytics()
    except Exception as e:  # noqa: BLE001
        an_err = f"{type(e).__name__}: {str(e)[:150]}"
    per = {}
    if an and vids:
        try:
            r = an.reports().query(ids="channel==MINE", startDate=SINCE, endDate=now().date().isoformat(), dimensions="video",
                                   metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,shares",
                                   filters="video==" + ",".join(v["id"] for v in vids), maxResults=200).execute()
            cols = [c["name"] for c in r["columnHeaders"]]
            per = {x[0]: dict(zip(cols, x)) for x in r.get("rows", [])}
            an_err = None
        except Exception as e:  # noqa: BLE001
            an_err = f"{type(e).__name__}: {str(e)[:150]}"
    rows = []
    for v in vids:
        st, sn = v["statistics"], v["snippet"]
        m = {"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)), "comments": int(st.get("commentCount", 0))}
        miss = {"link_clicks": "non esposto dalle API"}
        a = per.get(v["id"])
        if a:
            m.update(an_views=a["views"], minutes_watched=a["estimatedMinutesWatched"], avg_view_duration_s=a["averageViewDuration"],
                     avg_view_pct=round(a["averageViewPercentage"], 1), subs_gained=a["subscribersGained"], shares=a["shares"])
            try:
                curve = retention_curve(an, v["id"])
                m.update(curve_summary(curve))
                if curve:
                    with open(ROOT / "logs" / "video-metrics.jsonl", "a", encoding="utf-8") as f:
                        f.write(json.dumps({"id": v["id"], "title": sn["title"], "date": now().date().isoformat(), "curve": curve}) + "\n")
            except Exception as e:  # noqa: BLE001
                miss["retention_curve"] = f"{type(e).__name__}: {str(e)[:100]}"
        elif an_err:
            miss.update({k: an_err for k in ("avg_view_duration_s", "avg_view_pct", "subs_gained", "shares")})
        kind = "short" if iso_seconds(v["contentDetails"]["duration"]) <= 180 else "long"
        rows.append(row("video", v["id"], sn["title"], kind, sn["publishedAt"], m, miss))
    s = ch["statistics"]
    rows.append(row("account", ch["id"], "@CosmosinNumbers", "channel", "",
                    {"subscribers": int(s.get("subscriberCount", 0)), "views": int(s.get("viewCount", 0)), "videos": int(s.get("videoCount", 0))}))
    save("youtube", rows)


# ---------- Instagram ----------
def instagram():
    ig = meta_api.cfg()["ig_user_id"]
    media, err = g(f"{ig}/media", limit=50, fields="id,caption,timestamp,media_product_type,media_type,like_count,comments_count,permalink")
    if err:
        return save("instagram", [row("account", ig, missing={"all": err})])
    rows = []
    for m in media.get("data", []):
        if m["timestamp"][:10] < SINCE:
            continue
        reel = m.get("media_product_type") == "REELS"
        names = ["views", "reach", "saved", "shares", "total_interactions"] + (["ig_reels_avg_watch_time", "ig_reels_video_view_total_time"] if reel else [])
        got, miss = insights(m["id"], names)
        met = {"likes": m.get("like_count"), "comments": m.get("comments_count"), **got}
        met = {{"ig_reels_avg_watch_time": "avg_watch_ms", "ig_reels_video_view_total_time": "watch_total_ms"}.get(k, k): v for k, v in met.items()}
        kind = "reel" if reel else "carousel" if m.get("media_type") == "CAROUSEL_ALBUM" else m.get("media_type", "").lower()
        rows.append(row("post", m["id"], m.get("caption"), kind, m["timestamp"], met, miss))
    st, _ = g(f"{ig}/stories", fields="id,timestamp,caption")
    for s in (st or {}).get("data", []):  # Stories live 24 h: only the daily run sees them
        got, miss = insights(s["id"], ["views", "reach", "replies", "shares", "total_interactions"])
        rows.append(row("story", s["id"], s.get("caption"), "story", s["timestamp"], got, miss))
    acct, miss = insights(ig, ["profile_views", "website_clicks", "reach"], period="day", metric_type="total_value")
    info, e2 = g(ig, fields="followers_count,media_count")
    met = {f"acct_{k}": v for k, v in acct.items()}
    if info:
        met["acct_followers"] = info.get("followers_count")
    rows.append(row("account", ig, "@cosmos.innumbers", "account", "", met, {f"acct_{k}": v for k, v in miss.items()} | ({"acct_followers": e2} if e2 else {})))
    save("instagram", rows)


# ---------- Facebook ----------
def facebook():
    page = meta_api.cfg()["page_id"]
    rows = []
    reels, err = g(f"{page}/video_reels", limit=50, fields="id,description,created_time")
    reel_ids = set()
    for v in (reels or {}).get("data", []):
        reel_ids.add(v["id"])
        got, miss = insights(v["id"], ["blue_reels_play_count", "fb_reels_total_plays", "post_video_avg_time_watched"],
                             edge="video_insights")
        d, _ = g(v["id"], fields="likes.summary(true),comments.summary(true)")
        met = {"views": got.get("blue_reels_play_count"), "plays_total": got.get("fb_reels_total_plays"),
               "avg_watch_ms": got.get("post_video_avg_time_watched")}
        if d:
            met.update(likes=d["likes"]["summary"]["total_count"], comments=d["comments"]["summary"]["total_count"])
        rows.append(row("post", v["id"], v.get("description"), "reel", v["created_time"], {k: x for k, x in met.items() if x is not None}, miss))
    posts, perr = g(f"{page}/published_posts", limit=50,
                    fields="id,message,created_time,shares,reactions.summary(true),comments.summary(true),attachments{media_type}")
    for p in (posts or {}).get("data", []):
        if p["created_time"][:10] < SINCE:
            continue
        att = ((p.get("attachments") or {}).get("data") or [{}])[0].get("media_type", "")
        if att == "video":
            continue  # the Reel line above already counts it
        got, miss = insights(p["id"], ["post_media_view", "post_total_media_view_unique", "post_clicks"])
        met = {"views": got.get("post_media_view"), "reach": got.get("post_total_media_view_unique"), "clicks": got.get("post_clicks"), "likes": p["reactions"]["summary"]["total_count"],
               "comments": p["comments"]["summary"]["total_count"], "shares": p.get("shares", {}).get("count", 0)}
        rows.append(row("post", p["id"], p.get("message"), "carousel" if att == "album" else att or "text",
                        p["created_time"], {k: x for k, x in met.items() if x is not None}, miss))
    acct, miss = insights(page, ["page_views_total", "page_post_engagements"], period="day")
    info, e2 = g(page, fields="followers_count,fan_count")
    met = {"acct_page_views": acct.get("page_views_total"), "acct_post_engagements": acct.get("page_post_engagements")}
    if info:
        met["acct_followers"] = info.get("followers_count")
    extra = {"reels": err} if err else {}
    if perr:
        extra["posts"] = perr
    rows.append(row("account", page, "Cosmos in Numbers (Pagina)", "account", "", {k: x for k, x in met.items() if x is not None},
                    {**miss, **extra, **({"acct_followers": e2} if e2 else {})}))
    save("facebook", rows)


# ---------- Threads ----------
def threads():
    import requests
    c = json.loads((SECRETS / "threads.json").read_text("utf-8"))

    def th(path, **params):
        r = requests.get(f"https://graph.threads.net/v1.0/{path}", params={**params, "access_token": c["token"]}, timeout=60)
        j = r.json()
        return (None, str(j.get("error", {}).get("message", j))[:200]) if r.status_code != 200 or "error" in j else (j, None)

    posts, err = th(f"{c['user_id']}/threads", fields="id,text,timestamp,media_type,permalink,is_quote_post", limit=50)
    if err:
        return save("threads", [row("account", c["user_id"], missing={"all": err})])
    rows = []
    for p in posts.get("data", []):
        j, e = th(f"{p['id']}/insights", metric="views,likes,replies,reposts,quotes,shares")
        met = {d["name"]: (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value")) for d in (j or {}).get("data", [])}
        miss = {} if j else {k: e for k in ("views", "likes", "replies", "reposts", "quotes", "shares")}
        rows.append(row("post", p["id"], p.get("text"), (p.get("media_type") or "").lower(), p.get("timestamp", ""), met, miss))
    save("threads", rows)


# ---------- Gumroad ----------
def gumroad():
    f = SECRETS / "gumroad.json"
    if not f.exists():
        return save("gumroad", [row("product", "look-up", "LOOK UP", "product", "", {},
                                    {"sales": "manca secrets/gumroad.json (token di Gumroad)", "revenue_usd": "idem",
                                     "visits": "non esposte dall'API"})])
    import requests
    tok = json.loads(f.read_text("utf-8"))["access_token"]
    j = requests.get("https://api.gumroad.com/v2/products", params={"access_token": tok}, timeout=60).json()
    rows = []
    for p in j.get("products", []):
        rows.append(row("product", p["id"], p["name"], "product", "",
                        {"sales": p.get("sales_count"), "revenue_usd": (p.get("sales_usd_cents") or 0) / 100, "price_usd": p.get("price", 0) / 100,
                         "published": p.get("published")}, {"visits": "non esposte dall'API"}))
    save("gumroad", rows or [row("product", "?", missing={"all": str(j)[:200]})])


# ---------- comments ----------
def comments():
    import comments as cm
    cm.KEEP_ALL = True
    out = []
    for p, fn in (("yt", cm.fetch_yt), ("ig", cm.fetch_ig), ("fb", cm.fetch_fb), ("th", cm.fetch_th)):
        try:
            fn(out, set())
        except (SystemExit, Exception) as e:  # noqa: BLE001
            print("comments", p, "skipped:", str(e)[:150])
    rows = [row("comment", c["id"], c["on"], c["p"], c.get("at") or "", {"text": c["text"], "who": c.get("who")}) for c in out]
    save("comments", rows)


def write_defs():
    lines = ["# Definizioni delle metriche (07-analytics/metrics/)", "",
             "Generato da `tools/ytf/metrics.py defs`. Ogni riga dei file `.jsonl` porta `read_at` (ora UTC di lettura) e `date`.",
             "Una metrica rifiutata dall'API va in `missing` con il motivo: nei rapporti si scrive \"non misurato\", mai una stima.", ""]
    for ch, d in DEFS.items():
        lines += [f"## {ch}", ""] + [f"- `{k}`: {v}" for k, v in d.items()] + [""]
    lines += ["## x", "", "- Non letto: l'account è vuoto per scelta e la lettura via API è a pagamento.", "",
              "## tiktok", "", "- Non letto via API (nessuna app approvata): lettura settimanale da TikTok Studio, in `tiktok.jsonl` a mano.", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "DEFINIZIONI.md").write_text("\n".join(lines), "utf-8")
    print("scritto", (OUT / "DEFINIZIONI.md").relative_to(ROOT))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "tools"))
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    jobs = {"youtube": youtube, "instagram": instagram, "facebook": facebook, "threads": threads, "gumroad": gumroad, "comments": comments}
    if cmd == "all":
        for name, fn in jobs.items():
            try:
                fn()
            except Exception as e:  # noqa: BLE001 - one source failing must not stop the others
                print(name, "FALLITO:", type(e).__name__, str(e)[:200])
        write_defs()
    elif cmd in jobs:
        jobs[cmd]()
    elif cmd == "yt-auth":
        yt_analytics(interactive=True)
        print("YouTube Analytics autorizzato: token in secrets/token_analytics.json")
    elif cmd == "defs":
        write_defs()
    elif cmd == "manual" and len(sys.argv) == 4:
        # manual <channel> <rows.json>: readings taken by hand or with Chrome (TikTok Studio, Gumroad Analytics);
        # every row must say where it was read in metrics.source
        rows = json.loads(Path(sys.argv[3]).read_text("utf-8"))
        save(sys.argv[2], [row(r["level"], r["id"], r.get("title", ""), r.get("kind", ""), r.get("published", ""),
                               r.get("metrics"), r.get("missing")) for r in rows])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
