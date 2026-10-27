"""Weekly YouTube stats snapshot for every video on the channel (read-only).

  python stats.py            -> appends to 07-analytics/youtube-stats.csv and prints a ranked table

Columns: date, video_id, kind (long/short), title, published, views, likes, comments,
views_per_day, like_rate (likes/views), comment_rate. Shares and retention are not exposed by the
Data API; they need YouTube Analytics (yt-analytics.readonly) and are read from Studio instead.
"""
from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from yt_api import ROOT, service  # noqa: E402

OUT = ROOT / "07-analytics" / "youtube-stats.csv"


def iso_seconds(d: str) -> int:
    import re
    h, m, s = (int(x or 0) for x in re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d).groups())
    return h * 3600 + m * 60 + s


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    yt = service()
    ch = yt.channels().list(part="contentDetails,statistics", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = [i["contentDetails"]["videoId"] for i in
           yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50).execute()["items"]]
    today = dt.date.today()
    rows = []
    for v in yt.videos().list(part="snippet,statistics,status,contentDetails", id=",".join(ids)).execute()["items"]:
        if v["status"]["privacyStatus"] != "public":
            continue
        st, sn = v["statistics"], v["snippet"]
        views, likes, comments = (int(st.get(k, 0)) for k in ("viewCount", "likeCount", "commentCount"))
        pub = dt.date.fromisoformat(sn["publishedAt"][:10])
        days = max(1, (today - pub).days)
        kind = "short" if iso_seconds(v["contentDetails"]["duration"]) <= 180 else "long"
        rows.append({"date": today.isoformat(), "video_id": v["id"], "kind": kind, "title": sn["title"][:80],
                     "published": pub.isoformat(), "views": views, "likes": likes, "comments": comments,
                     "views_per_day": round(views / days, 1),
                     "like_rate": round(likes / views, 4) if views else 0,
                     "comment_rate": round(comments / views, 4) if views else 0})
    # one snapshot per video per day: a re-run on the same day replaces that day's rows instead of duplicating them
    OUT.parent.mkdir(exist_ok=True)
    fields = list(rows[0].keys()) if rows else None
    old = list(csv.DictReader(OUT.open(encoding="utf-8"))) if OUT.exists() else []
    fields = fields or (list(old[0].keys()) if old else ["date"])
    fresh = {(r["date"], r["video_id"]) for r in rows}
    keep = {(r["date"], r["video_id"]): r for r in old if (r["date"], r["video_id"]) not in fresh}
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(list(keep.values()) + rows)
    s = ch["statistics"]
    print(f"channel: subs={s.get('subscriberCount')} views={s.get('viewCount')} videos={s.get('videoCount')}")
    for r in sorted(rows, key=lambda r: -r["views_per_day"]):
        print(f"{r['kind']:5} {r['views_per_day']:>7}/d views={r['views']:<6} likes={r['likes']:<4} "
              f"comments={r['comments']:<3} {r['title']}")


if __name__ == "__main__":
    main()
