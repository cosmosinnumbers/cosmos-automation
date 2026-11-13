"""Threads API helper for Cosmos in Numbers (Threads profile = Instagram @cosmos.innumbers).

  python threads_api.py check                           show the profile linked to the token
  python threads_api.py refresh                         extend the long-lived token another 60 days (token must be >24h old)
  python threads_api.py next [--go]                     publish the next due item of queues/threads-queue.json
  python threads_api.py perms                           permissions of the token (is threads_delete granted?)
  python threads_api.py delete REF [--go]               delete a published thread (main post + its replies), found
                                                        by queue ref in the log; without --go only shows it

Rebuilt on 26/10/2026 after the 24/10 version was overwritten by mistake: same interface as x_api.py
(run_item for run_slot.py, credentials via creds.py). OAuth setup (auth-url, setup) stays in
Progetto-YouTube-Faceless/tools/threads_api.py on the PC.
Credentials: secret THREADS_JSON or secrets/threads.json (app_id, app_secret, redirect_uri, user_id, token, token_at).
Pacing: up to 3 main posts per day, at least 3 h apart (owner decision 18/10/2026, replies not counted),
log logs/threads-publish-log.jsonl (the only source of truth).
API: https://developers.facebook.com/docs/threads (500-char text, link_attachment and polls only on TEXT posts).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402
import cta  # noqa: E402

LOG = creds.LOGS / "threads-publish-log.jsonl"
QUEUE = creds.QUEUES / "threads-queue.json"
G = "https://graph.threads.net"
MAX_PER_DAY, MIN_GAP_H = 3, 3


def cfg():
    return creds.load("threads")


def call(method, path, **params):
    r = requests.request(method, f"{G}{path}", params=params if method == "GET" else None,
                         data=params if method == "POST" else None, timeout=60)
    j = r.json()
    if r.status_code != 200 or "error" in j:
        sys.exit(f"Threads API {r.status_code}: {j.get('error', j)}")
    return j


def events():
    return creds.events(LOG.name)


def main_posts():
    """Main posts still online, for pacing. A deleted post (k "deleted") no longer counts; a post that replaces a
    deleted one ("replaces": ref) keeps the time of the post it replaces, so a correction does not shift the slots."""
    ev = events()
    gone = {e["id"] for e in ev if e.get("k") == "deleted"}
    first = {e.get("ref"): e["at"] for e in ev if e.get("k") not in ("reply", "deleted")}
    return [{**e, "at": first.get(e.get("replaces"), e["at"])} for e in ev
            if e.get("k") not in ("reply", "deleted") and e.get("id") not in gone]


def guard():
    """Return None if a main post now is allowed, else the reason."""
    now = int(time.time())
    main = main_posts()
    if len([e for e in main if creds.day(e["at"]) == creds.day(now)]) >= MAX_PER_DAY:
        return f"PACING: already {MAX_PER_DAY} Threads posts today."
    if any(now - e["at"] < MIN_GAP_H * 3600 for e in main):
        return f"PACING: another Threads post within {MIN_GAP_H}h."
    return None


def cmd_refresh():
    c = cfg()
    j = call("GET", "/refresh_access_token", grant_type="th_refresh_token", access_token=c["token"])
    c.update(token=j["access_token"], token_at=int(time.time()))
    creds.save("threads", c)
    print(f"Token refreshed, ~{j.get('expires_in', 0) // 86400} days left.")


def cmd_check():
    c = cfg()
    me = call("GET", "/v1.0/me", fields="id,username", access_token=c["token"])
    age = (time.time() - c.get("token_at", 0)) / 86400
    print(f"@{me.get('username')} token age {age:.0f} days (refresh before 60)")


def cmd_perms():
    """Scopes of the token through debug_token; prints whether deleting posts (threads_delete) is allowed."""
    c = cfg()
    r = requests.get(f"{G}/v1.0/debug_token", params={"input_token": c["token"], "access_token": c["token"]}, timeout=60)
    data = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("data") or {}
    scopes = data.get("scopes")
    if scopes is None:
        print(f"debug_token not available (HTTP {r.status_code}): permissions unknown, a delete attempt will tell")
        return
    print("scopes:", ", ".join(scopes))
    print("threads_delete:", "YES" if "threads_delete" in scopes else "NO (re-authorise the app with threads_delete)")


def cmd_delete(ref, go):
    """Delete the thread published for queue ref REF: main post first, then its replies (REF-r1, REF-r2...).
    The ids come only from the log, and each post is read back first: it must belong to this profile. A post
    already deleted by hand in the app is only logged as deleted (k "deleted", by "hand"), so pacing forgets it."""
    c = cfg()
    ev = events()
    gone = {e["id"] for e in ev if e.get("k") == "deleted"}
    posts = [e for e in ev if e.get("k") != "deleted" and e.get("id") not in gone
             and (e.get("ref") == ref or (e.get("ref") or "").startswith(f"{ref}-r"))]
    posts.sort(key=lambda e: (e.get("ref") != ref, e.get("ref")))
    if not posts or posts[0].get("ref") != ref:
        sys.exit(f"No online main post with ref {ref} in {LOG.name}.")
    me = call("GET", "/v1.0/me", fields="id,username", access_token=c["token"])
    online = []
    for e in posts:
        r = requests.get(f"{G}/v1.0/{e['id']}", timeout=60, params={
            "fields": "id,username,text,timestamp,permalink", "access_token": c["token"]})
        p = r.json()
        if r.status_code != 200 or "error" in p:  # already gone (deleted by hand in the app): only the log changes
            print(f"{e['ref']}  {e['id']}  not online any more (HTTP {r.status_code}): logged as deleted")
            if go:
                creds.append(LOG.name, {"p": "threads", "k": "deleted", "at": int(time.time()), "id": e["id"],
                                        "ref": e["ref"], "by": "hand"})
            continue
        if p.get("username") != me.get("username"):
            sys.exit(f"{e['id']} belongs to @{p.get('username')}, not @{me.get('username')}: nothing deleted.")
        print(f"{e['ref']}  {e['id']}  {p.get('timestamp')}  {p.get('permalink')}\n    {(p.get('text') or '')[:120]!r}")
        online.append(e)
    if not go:
        print("DRY-RUN: nothing deleted.")
        return
    for e in online:
        r = requests.delete(f"{G}/v1.0/{e['id']}", params={"access_token": c["token"]}, timeout=60)
        j = r.json() if r.content else {}
        if r.status_code != 200 or "error" in j:
            sys.exit(f"Delete {e['ref']} ({e['id']}) failed: HTTP {r.status_code} {j.get('error', j)}")
        creds.append(LOG.name, {"p": "threads", "k": "deleted", "at": int(time.time()), "id": e["id"], "ref": e["ref"]})
        print(f"Deleted {e['ref']} ({e['id']})")

def fb_video_url(video_id):
    """Fresh public MP4 URL of a Reel already on the Cosmos Facebook Page (CDN link, valid for hours)."""
    m = creds.load("meta")
    r = requests.get(f"https://graph.facebook.com/v21.0/{video_id}",
                     params={"fields": "source", "access_token": m["page_token"]}, timeout=60).json()
    if "source" not in r:
        sys.exit(f"No source URL for Facebook video {video_id}: {r.get('error', r)}")
    return r["source"]


def short_video(tag, go=False):
    """Public MP4 of the Short of the day (Threads needs a URL), or None: then the post goes out as text.
    1) cosmosinnumbers.github.io/media/shorts/<tag>.mp4; 2) at publish time, the Facebook Reel of the same Short
    (queue ref fr-<tag>, published a moment before in the same slot) through its CDN source URL."""
    url = f"https://cosmosinnumbers.github.io/media/shorts/{tag}.mp4"
    try:
        if requests.head(url, allow_redirects=True, timeout=30).status_code == 200:
            return url
    except requests.RequestException:
        pass
    fb = next((e.get("ref") for e in creds.events("meta-publish-log.jsonl") if e.get("item") == f"fr-{tag}"), None)
    if fb and go:
        try:
            return fb_video_url(fb)
        except SystemExit as e:  # still processing on Facebook: text only
            print(f"  Facebook source not ready: {e}")
    return None


def build(text, image=None, video=None, link=None, tag=None, poll=None, reply_to=None):
    if len(text) > 500:
        sys.exit(f"Text is {len(text)} chars (max 500).")
    if (image or video) and (link or poll):
        sys.exit("link_attachment and polls work only on TEXT posts.")
    body = {"media_type": "VIDEO" if video else "IMAGE" if image else "TEXT", "text": text}
    if tag:  # one topic tag per post (Threads rule), without '#'
        body["topic_tag"] = tag.lstrip("#")
    if poll:  # 2-4 options, max 25 chars each
        body["poll_attachment"] = json.dumps({f"option_{k}": o for k, o in zip("abcd", poll)})
    if reply_to:
        body["reply_to_id"] = reply_to
    if image:
        body["image_url"] = image
    if video:
        body["video_url"] = video
    if link:
        body["link_attachment"] = link
    return body


def publish(body, ref, replaces=None):
    """Create the container, wait until Threads has processed it, publish, log. Returns (id, permalink)."""
    c = cfg()
    cont = call("POST", f"/v1.0/{c['user_id']}/threads", access_token=c["token"], **body)
    for _ in range(40):  # videos can take a few minutes
        time.sleep(30 if body["media_type"] != "TEXT" else 5)
        st = call("GET", f"/v1.0/{cont['id']}", fields="status,error_message", access_token=c["token"])
        if st.get("status") == "FINISHED":
            break
        if st.get("status") in ("ERROR", "EXPIRED"):
            sys.exit(f"Container {st.get('status')}: {st.get('error_message')}")
    else:
        sys.exit("Container not ready after 20 minutes, nothing published.")
    pub = call("POST", f"/v1.0/{c['user_id']}/threads_publish", creation_id=cont["id"], access_token=c["token"])
    link = call("GET", f"/v1.0/{pub['id']}", fields="permalink", access_token=c["token"]).get("permalink", "")
    creds.append(LOG.name, {"p": "threads", "k": "reply" if body.get("reply_to_id") else body["media_type"].lower(),
                            "at": int(time.time()), "id": pub["id"], "ref": ref, "url": link,
                            **({"replaces": replaces} if replaces else {})})
    return pub["id"], link


def run_item(item, go):
    """One queue item: main post (text, poll, link or video) plus chained replies, Gumroad link first."""
    video = item.get("video_url")
    if video:
        creds.check_url(video)
    elif item.get("fb_video") and go:
        video = fb_video_url(item["fb_video"])
    elif item.get("short"):  # generated by threads_build.py: video if public, otherwise text only
        video = short_video(item["short"], go)
        print(f"  video: {video or 'no public URL, text only'}")
    replies = item.get("replies", [])
    if "gumroad.com" not in item["text"]:  # product link always in the FIRST reply (link in the post cuts reach)
        replies = cta.first_reply(item["ref"], replies, expired=creds.now_local().date() > date(2026, 11, 30),
                                  source="threads", post=item["text"])
    body = build(item["text"], video=video, link=item.get("link"), tag=item.get("tag"), poll=item.get("poll"))
    bodies = [build(r) for r in replies]
    verdict = guard()
    print(item["ref"], json.dumps({k: v for k, v in body.items() if k != "video_url"}, ensure_ascii=False))
    for r in replies:
        print("  reply:", r[:80].replace("\n", " "))
    print(verdict or "Pacing: OK")
    if not go:
        print("DRY-RUN: nothing sent.")
        return
    ids = {e.get("ref"): e.get("id") for e in events()}
    if item["ref"] in ids:  # a retry after a failed reply: never post the main text twice
        pid = ids[item["ref"]]
    else:
        if verdict:
            sys.exit(verdict)
        pid, link = publish(body, item["ref"], replaces=item.get("replaces"))
        print(f"Published: {link}")
    for n, r in enumerate(bodies, 1):  # chain: each reply under the previous one
        rr = f"{item['ref']}-r{n}"
        if rr in ids:
            pid = ids[rr]
        else:
            r["reply_to_id"] = pid
            pid = publish(r, rr)[0]


def cmd_next(go):
    q = json.loads(QUEUE.read_text("utf-8"))
    done = {e.get("ref") for e in events()}
    now = creds.now_local().strftime("%Y-%m-%d %H:%M")
    item = next((i for i in q if i["ref"] not in done and i["at"] <= now), None)
    if not item:
        print("Nothing due in the Threads queue.")
        return
    run_item(item, go)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    {"refresh": cmd_refresh, "check": cmd_check, "perms": cmd_perms, "next": lambda: cmd_next("--go" in a),
     "delete": lambda: cmd_delete(a[1], "--go" in a)}.get(a[0], lambda: sys.exit(__doc__))()
