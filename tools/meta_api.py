"""Meta Graph API helper for the Cosmos in Numbers Facebook Page and Instagram account.

  python meta_api.py setup <user_token>                       exchange for a never-expiring Page token -> secrets/meta.json
  python meta_api.py check                                    show Page and Instagram account linked to the token
  python meta_api.py fb-reel <mp4> "<caption>" [<unix_time>]  Facebook Page video; with unix_time it is scheduled (10 min–30 days ahead)
  python meta_api.py ig-reel <mp4> "<caption>"                publish an Instagram Reel now (IG API has no native scheduling:
                                                              run it at the release time, e.g. from the weekly task)
  python meta_api.py ig-story|fb-story <mp4|url>             publish a Story now
  python meta_api.py ig-carousel "<caption>" <jpg_url>...     publish an Instagram carousel now (2-10 public JPEG URLs)
  python meta_api.py fb-carousel "<caption>" <unix_time> <jpg_url>...  schedule a Facebook multi-photo post
  python meta_api.py can|log <ig|fb> <reel|story|post> [<unix>]  pacing check / record (manual scheduling)
  python meta_api.py stats                                    last posts with views/likes/comments/shares (FB + IG)

Credentials: secret META_JSON or secrets/meta.json (app_id, app_secret, page_id, page_token, ig_user_id), see creds.py.
Log (single source of truth for pacing): logs/meta-publish-log.jsonl in the cosmos-automation repo.
The app stays in Development mode: it only acts on assets the owner manages, no App Review needed.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402

G = "https://graph.facebook.com/v21.0"
LOG = creds.LOGS / "meta-publish-log.jsonl"

# Anti-ban pacing (Instagram suspended the account on 15/10/2026 after 4 Reels + 3 Stories + profile edits
# in one day on a 1-day-old account). Every publish, API or Business Suite, is checked and logged here.
# (platform, kind) -> (max per 24h, min hours between any two actions on that platform)
WARMUP_UNTIL = 1794700800  # 15/11/2026: first month of a new account
LIMITS_WARMUP = {("ig", "reel"): (1, 20), ("ig", "story"): (1, 4), ("fb", "reel"): (1, 4), ("fb", "story"): (1, 4),
                 ("ig", "post"): (1, 20), ("fb", "post"): (1, 20)}  # carousels / feed posts (owner 22/10/2026)
LIMITS = {("ig", "reel"): (1, 12), ("ig", "story"): (2, 3), ("fb", "reel"): (2, 3), ("fb", "story"): (2, 3),
          ("ig", "post"): (1, 20), ("fb", "post"): (1, 20)}
# Instagram reinstated on 16/10/2026 after the appeal: every other day until 30/10, then the warm-up limits above
IG_SLOW_UNTIL = 1793397600  # 30/10/2026 22:00 UTC
LIMITS_IG_SLOW = {("ig", "reel"): (1, 44), ("ig", "story"): (1, 44), ("ig", "post"): (1, 20)}


def _events():
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text("utf-8").splitlines() if l.strip()]


def guard(platform, kind, at=None):
    """Refuse (exit) if publishing `kind` on `platform` at unix time `at` would break the pacing rules."""
    at = int(at or time.time())
    table = LIMITS_WARMUP if at < WARMUP_UNTIL else LIMITS
    if platform == "ig" and at < IG_SLOW_UNTIL:
        table = LIMITS_IG_SLOW
    maxn, gap_h = table[(platform, kind)]
    ev = _events()
    same = [e for e in ev if e["p"] == platform and e["k"] == kind and abs(e["at"] - at) < 86400]
    if len(same) >= maxn:
        sys.exit(f"PACING: {platform} {kind} already {len(same)} within 24h of that time (max {maxn}). Pick another day.")
    # a Story may accompany its own Reel at the same time; otherwise same-kind actions must be gap_h apart
    near = [e for e in ev if e["p"] == platform and e["k"] == kind and abs(e["at"] - at) < gap_h * 3600]
    if near:
        sys.exit(f"PACING: another {platform} {kind} within {gap_h}h of that time. Space it out.")
    return at


def record(platform, kind, at=None, ref="", item=""):
    """ref = Meta object id (or "business-suite"); item = queue ref, used to skip items already published."""
    e = {"p": platform, "k": kind, "at": int(at or time.time()), "ref": ref}
    if item:
        e["item"] = item
    creds.append(LOG.name, e)


def cfg():
    return creds.load("meta")


def call(method, path, **kw):
    # retry transient network errors; a POST is retried only if it never reached Meta (DNS / connect),
    # so a publish can never be sent twice
    for attempt in range(4):
        try:
            r = requests.request(method, path if path.startswith("http") else f"{G}/{path}", timeout=300, **kw)
            break
        except requests.exceptions.ConnectionError as e:
            unsent = "NameResolution" in repr(e) or "NewConnectionError" in repr(e)
            if attempt == 3 or (method != "GET" and not unsent):
                sys.exit(f"Meta API network error ({method} {path[:40]}): {type(e).__name__}")
            time.sleep(5 * (attempt + 1))
    if r.status_code >= 400:
        sys.exit(f"Meta API error {r.status_code}: {r.text[:500]}")
    return r.json()


def setup(user_token):
    c = cfg()
    long_user = call("GET", "oauth/access_token", params={"grant_type": "fb_exchange_token", "client_id": c["app_id"],
                                                          "client_secret": c["app_secret"], "fb_exchange_token": user_token})["access_token"]
    pages = call("GET", "me/accounts", params={"access_token": long_user, "fields": "id,name,access_token,instagram_business_account"})["data"]
    page = next(p for p in pages if p["id"] == c.get("page_id", "1451788358010023"))
    c.update(page_id=page["id"], page_token=page["access_token"], ig_user_id=page.get("instagram_business_account", {}).get("id"))
    creds.save("meta", c)
    print("saved: page", page["id"], "ig", c["ig_user_id"])


def fb_reel(mp4, caption, when=None, item=""):
    at = guard("fb", "reel", when)
    mp4 = creds.local_media(mp4)
    c = cfg()
    data = {"access_token": c["page_token"], "description": caption}
    if when:
        data.update(published="false", scheduled_publish_time=str(int(when)))
    with open(mp4, "rb") as f:
        r = call("POST", f"https://graph-video.facebook.com/v21.0/{c['page_id']}/videos", data=data, files={"source": f})
    record("fb", "reel", at, r.get("id", ""), item)
    print("facebook video:", r.get("id"), "scheduled" if when else "published")


def ig_reel(mp4, caption, item=""):
    at = guard("ig", "reel")
    mp4 = ig_ready(creds.local_media(mp4))
    c = cfg()
    tok, ig = c["page_token"], c["ig_user_id"]
    cont = call("POST", f"{ig}/media", params={"access_token": tok, "media_type": "REELS", "upload_type": "resumable",
                                               "caption": caption, "share_to_feed": "true"})
    size = Path(mp4).stat().st_size
    with open(mp4, "rb") as f:
        call("POST", cont["uri"], headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}, data=f.read())
    for _ in range(60):
        st = call("GET", cont["id"], params={"access_token": tok, "fields": "status_code"})["status_code"]
        if st == "FINISHED":
            break
        if st == "ERROR":
            sys.exit("instagram processing error")
        time.sleep(10)
    r = call("POST", f"{ig}/media_publish", params={"access_token": tok, "creation_id": cont["id"]})
    record("ig", "reel", at, r["id"], item)
    print("instagram reel:", r["id"])


def ig_ready(mp4):
    """Instagram rejects our CRF/low-bitrate MP4s (error 2207076): re-encode with faststart, ~3.5 Mbps, 48 kHz AAC."""
    import subprocess
    import tempfile
    import imageio_ffmpeg
    out = Path(tempfile.gettempdir()) / (Path(mp4).stem + "_ig.mp4")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(mp4), "-c:v", "libx264",
                    "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p", "-r", "30", "-b:v", "3500k",
                    "-maxrate", "5000k", "-bufsize", "7000k", "-c:a", "aac", "-ar", "48000", "-b:a", "128k",
                    "-movflags", "+faststart", str(out)], check=True)
    return str(out)


def story_cut(mp4, seconds=19):
    """Story teaser: first `seconds` of the Short (Facebook Stories max 20 s), with a 1 s fade-out. -> <name>_story.mp4"""
    import subprocess
    import imageio_ffmpeg
    out = Path(mp4).with_name(Path(mp4).stem + "_story.mp4")
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(mp4), "-t", str(seconds),
                    "-vf", f"fade=t=out:st={seconds - 1}:d=1", "-af", f"afade=t=out:st={seconds - 1}:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-b:v", "3500k", "-c:a", "aac", "-ar", "48000",
                    "-movflags", "+faststart", str(out)], check=True)
    print("story cut:", out)
    return str(out)


def ig_story(mp4, item=""):
    """Instagram Story (video), published now via resumable upload."""
    at = guard("ig", "story")
    mp4 = ig_ready(creds.local_media(mp4))
    c = cfg()
    tok, ig = c["page_token"], c["ig_user_id"]
    cont = call("POST", f"{ig}/media", params={"access_token": tok, "media_type": "STORIES", "upload_type": "resumable"})
    with open(mp4, "rb") as f:
        call("POST", cont["uri"], headers={"Authorization": f"OAuth {tok}", "offset": "0",
                                           "file_size": str(Path(mp4).stat().st_size)}, data=f.read())
    for _ in range(60):
        st = call("GET", cont["id"], params={"access_token": tok, "fields": "status_code"})["status_code"]
        if st == "FINISHED":
            break
        if st == "ERROR":
            sys.exit("instagram story processing error")
        time.sleep(10)
    sid = call("POST", f"{ig}/media_publish", params={"access_token": tok, "creation_id": cont["id"]})["id"]
    record("ig", "story", at, sid, item)
    print("instagram story:", sid)


def fb_story(mp4, item=""):
    """Facebook Page video Story, published now (start -> upload -> finish)."""
    at = guard("fb", "story")
    mp4 = creds.local_media(mp4)
    c = cfg()
    tok, page = c["page_token"], c["page_id"]
    start = call("POST", f"{page}/video_stories", data={"access_token": tok, "upload_phase": "start"})
    with open(mp4, "rb") as f:
        call("POST", start["upload_url"], headers={"Authorization": f"OAuth {tok}", "offset": "0",
                                                   "file_size": str(Path(mp4).stat().st_size)}, data=f.read())
    r = call("POST", f"{page}/video_stories", data={"access_token": tok, "upload_phase": "finish", "video_id": start["video_id"]})
    record("fb", "story", at, str(r.get("post_id", "")), item)
    print("facebook story:", r.get("post_id") or r)


def _wait_ig(cid, tok, what):
    for _ in range(60):
        st = call("GET", cid, params={"access_token": tok, "fields": "status_code"})["status_code"]
        if st == "FINISHED":
            return
        if st == "ERROR":
            sys.exit(f"instagram {what} processing error")
        time.sleep(5)
    sys.exit(f"instagram {what} not ready after 5 minutes, nothing published")


def ig_carousel(urls, caption, item=""):
    """Instagram carousel, published now: 2-10 public JPEG URLs (IG fetches them itself)."""
    if not 2 <= len(urls) <= 10:
        sys.exit("an Instagram carousel needs 2 to 10 images")
    at = guard("ig", "post")
    for u in urls:
        creds.check_url(u)
    c = cfg()
    tok, ig = c["page_token"], c["ig_user_id"]
    kids = []
    for u in urls:
        k = call("POST", f"{ig}/media", params={"access_token": tok, "image_url": u, "is_carousel_item": "true"})["id"]
        _wait_ig(k, tok, "carousel image")
        kids.append(k)
    cont = call("POST", f"{ig}/media", params={"access_token": tok, "media_type": "CAROUSEL", "caption": caption,
                                               "children": ",".join(kids)})["id"]
    _wait_ig(cont, tok, "carousel")
    r = call("POST", f"{ig}/media_publish", params={"access_token": tok, "creation_id": cont})
    record("ig", "post", at, r["id"], item)
    print("instagram carousel:", r["id"])


def fb_carousel(urls, caption, when, item=""):
    """Facebook Page multi-photo post scheduled at unix `when` (photos uploaded unpublished + temporary)."""
    at = guard("fb", "post", when)
    for u in urls:
        creds.check_url(u)
    c = cfg()
    tok, page = c["page_token"], c["page_id"]
    ids = [call("POST", f"{page}/photos", data={"access_token": tok, "url": u, "published": "false",
                                                 "temporary": "true"})["id"] for u in urls]
    data = {"access_token": tok, "message": caption, "published": "false", "scheduled_publish_time": str(int(when))}
    for i, pid in enumerate(ids):
        data[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    r = call("POST", f"{page}/feed", data=data)
    record("fb", "post", at, r.get("id", ""), item)
    print("facebook carousel:", r.get("id"), "scheduled")


def stats():
    c = cfg()
    tok = c["page_token"]
    # posts feed (with shares) needs pages_read_user_content; videos/reels only need pages_read_engagement
    try:
        for p in call("GET", f"{c['page_id']}/published_posts", params={"access_token": tok, "limit": 10,
                      "fields": "created_time,message,shares,reactions.summary(true),comments.summary(true)"})["data"]:
            print("FB post", p["created_time"][:10], "reactions", p["reactions"]["summary"]["total_count"],
                  "comments", p["comments"]["summary"]["total_count"], "shares", p.get("shares", {}).get("count", 0),
                  "|", (p.get("message") or "")[:50].replace("\n", " "))
    except SystemExit as e:
        print("FB posts unavailable:", str(e)[:120])
    try:
        vids = call("GET", f"{c['page_id']}/videos", params={"access_token": tok, "limit": 10,
                    "fields": "created_time,description,views,likes.summary(true),comments.summary(true)"})["data"]
        for v in vids:
            print("FB", v["created_time"][:10], "views", v.get("views"), "likes", v["likes"]["summary"]["total_count"],
                  "comments", v["comments"]["summary"]["total_count"], "|", (v.get("description") or "")[:50].replace("\n", " "))
    except SystemExit as e:
        print("FB stats unavailable:", str(e)[:120])
    if c.get("ig_user_id"):
        for m in call("GET", f"{c['ig_user_id']}/media", params={"access_token": tok, "limit": 10,
                      "fields": "timestamp,caption,like_count,comments_count,media_product_type"})["data"]:
            print("IG", m["timestamp"][:10], m.get("media_product_type"), "likes", m.get("like_count"),
                  "comments", m.get("comments_count"), "|", (m.get("caption") or "")[:50].replace("\n", " "))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, a = sys.argv[1], sys.argv[2:]
    if cmd == "setup":
        # token passed as argument, or pasted by the owner into secrets/meta_user_token.txt (deleted after use)
        f = creds.LOCAL_SECRETS / "meta_user_token.txt"
        setup(a[0] if a else f.read_text("utf-8").strip())
        f.unlink(missing_ok=True)
    elif cmd == "check":
        c = cfg()
        print(call("GET", c["page_id"], params={"access_token": c["page_token"], "fields": "name,instagram_business_account{username}"}))
        d = call("GET", "debug_token", params={"input_token": c["page_token"], "access_token": f"{c['app_id']}|{c['app_secret']}"})["data"]
        left = (d.get("data_access_expires_at", 0) - time.time()) / 86400
        print("token valid:", d.get("is_valid"), "| expires:", "never" if not d.get("expires_at") else d["expires_at"],
              f"| data access expires in {left:.0f} days", "| scopes:", ",".join(d.get("scopes", [])))
        if left < 21:
            print("WARNING: data access expires soon. The owner must regenerate the token (SOP 15.7) before that date.")
    elif cmd == "fb-reel":
        # safety: immediate publishing only with an explicit --now; otherwise a valid future unix time is required
        if len(a) < 3 or not (a[2] == "--now" or a[2].isdigit()):
            sys.exit("fb-reel needs <unix_time> or --now (refusing to publish by accident)")
        when = None if a[2] == "--now" else int(a[2])
        if when and not (time.time() + 600 <= when <= time.time() + 30 * 86400):
            sys.exit("unix_time must be 10 min to 30 days in the future")
        fb_reel(a[0], a[1], when)
    elif cmd == "ig-reel":
        ig_reel(a[0], a[1])
    elif cmd == "ig-carousel":
        ig_carousel(a[1:], a[0])
    elif cmd == "fb-carousel":
        if not (len(a) >= 4 and a[1].isdigit() and time.time() + 600 <= int(a[1]) <= time.time() + 30 * 86400):
            sys.exit('fb-carousel needs "<caption>" <unix_time 10 min-30 days ahead> <jpg_url> <jpg_url>...')
        fb_carousel(a[2:], a[0], int(a[1]))
    elif cmd == "story-cut":
        story_cut(a[0])
    elif cmd == "ig-story":
        ig_story(a[0])
    elif cmd == "fb-story":
        fb_story(a[0])
    elif cmd in ("can", "log"):
        # Business Suite scheduling: `can ig reel <unix>` before scheduling, `log ig reel <unix>` right after
        at = guard(a[0], a[1], int(a[2]) if len(a) > 2 else None)
        if cmd == "log":
            record(a[0], a[1], at, "business-suite")
        print("ok:", cmd, a[0], a[1], at)
    elif cmd == "stats":
        stats()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
