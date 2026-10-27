"""Reply to audience comments (owner request 18-19/10/2026), Cosmos in Numbers only.

  python comments.py fetch               unanswered comments -> 07-analytics/comments-inbox.json (read only)
  python comments.py reply <file.json>   post the replies in <file.json>: [{"p": "yt|ig|fb|th", "id": "...", "text": "..."}]

Rules: SKY comments are left to sky_reply.py. Max 20 replies per platform per run, 20-45 s apart.
Idempotent: every reply goes to 07-analytics/replies-log.jsonl and a comment id there is never answered twice.
"""
from __future__ import annotations

import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import meta_api  # noqa: E402

ROOT = meta_api.ROOT
INBOX = ROOT / "07-analytics" / "comments-inbox.json"
LOG = ROOT / "07-analytics" / "replies-log.jsonl"
SKY = re.compile(r"\bsky\b", re.I)
MAX, PAUSE = 20, (20, 45)
KEEP_ALL = False  # metrics.py sets it: every comment, answered or not, SKY included (own comments still skipped)


def done_ids():
    ev = [json.loads(l) for l in LOG.read_text("utf-8").splitlines() if l.strip()] if LOG.exists() else []
    return {e["id"] for e in ev if e.get("ok")}  # failed attempts can be retried


def safe(method, path, **kw):
    try:
        return meta_api.call(method, path, **kw), None
    except SystemExit as e:
        return None, str(e)[:300]


def fetch_yt(out, done):
    import yt_api
    yt = yt_api.service()
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    me, uploads = ch["id"], ch["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50).execute()["items"]
    for v in yt.videos().list(part="snippet,status", id=",".join(i["contentDetails"]["videoId"] for i in items)).execute()["items"]:
        if v["status"]["privacyStatus"] != "public":
            continue
        for t in yt.commentThreads().list(part="snippet,replies", videoId=v["id"], maxResults=100).execute().get("items", []):
            s = t["snippet"]["topLevelComment"]["snippet"]
            mine = lambda c: c.get("authorChannelId", {}).get("value") == me
            if mine(s) or (not KEEP_ALL and (t["id"] in done or SKY.search(s.get("textOriginal", "")))):
                continue
            if not KEEP_ALL and any(mine(r["snippet"]) for r in t.get("replies", {}).get("comments", [])):
                continue
            out.append({"p": "yt", "id": t["id"], "on": v["snippet"]["title"][:70], "who": s.get("authorDisplayName"),
                        "at": s["publishedAt"], "text": s.get("textOriginal", "")})


def fetch_ig(out, done):
    c = meta_api.cfg()
    tok, ig = c["page_token"], c["ig_user_id"]
    me = meta_api.call("GET", ig, params={"access_token": tok, "fields": "username"})["username"]
    media = meta_api.call("GET", f"{ig}/media", params={"access_token": tok, "limit": 25,
                          "fields": "id,caption,comments_count"})["data"]
    for m in media:
        if not m.get("comments_count"):
            continue
        cm = meta_api.call("GET", f"{m['id']}/comments", params={"access_token": tok, "limit": 100,
                           "fields": "id,text,username,timestamp,replies{username}"}).get("data", [])
        for x in cm:
            if x.get("username") == me or (not KEEP_ALL and (x["id"] in done or SKY.search(x.get("text", "")))):
                continue
            if not KEEP_ALL and any(r.get("username") == me for r in x.get("replies", {}).get("data", [])):
                continue
            out.append({"p": "ig", "id": x["id"], "on": (m.get("caption") or "")[:70], "who": x.get("username"),
                        "at": x["timestamp"], "text": x.get("text", "")})


def fetch_fb(out, done):
    c = meta_api.cfg()
    tok, page = c["page_token"], c["page_id"]
    for edge in ("videos", "published_posts"):
        r, err = safe("GET", f"{page}/{edge}", params={"access_token": tok, "limit": 25,
                      "fields": "id,description,message" if edge == "videos" else "id,message"})
        if err:
            print("fb", edge, "skipped:", err)
        for o in (r or {}).get("data", []):
            cr, err = safe("GET", f"{o['id']}/comments", params={"access_token": tok, "limit": 100, "filter": "toplevel",
                           "fields": "id,message,from,created_time,comments.limit(25){from}"})
            for x in (cr or {}).get("data", []):
                if x.get("from", {}).get("id") == page or (not KEEP_ALL and (x["id"] in done or SKY.search(x.get("message", "")))):
                    continue
                if not KEEP_ALL and any(rp.get("from", {}).get("id") == page for rp in x.get("comments", {}).get("data", [])):
                    continue
                out.append({"p": "fb", "id": x["id"], "on": (o.get("message") or o.get("description") or "")[:70],
                            "who": x.get("from", {}).get("name", "?"), "at": x["created_time"], "text": x.get("message", "")})


def th_cfg():
    return json.loads((ROOT / "secrets" / "threads.json").read_text("utf-8"))


def th_get(path, **params):
    import requests
    r = requests.get(f"https://graph.threads.net/v1.0/{path}", params={**params, "access_token": th_cfg()["token"]}, timeout=60)
    j = r.json()
    if r.status_code != 200 or "error" in j:
        raise SystemExit(f"Threads API {r.status_code}: {j.get('error', {}).get('message', j)}")
    return j


def fetch_th(out, done):
    me = th_cfg()["user_id"]
    for p in th_get(f"{me}/threads", fields="id,text", limit=25).get("data", []):
        for x in th_get(f"{p['id']}/replies", fields="id,text,username,timestamp,is_reply_owned_by_me,has_replies").get("data", []):
            if x.get("is_reply_owned_by_me") or (not KEEP_ALL and (x["id"] in done or SKY.search(x.get("text", "") or ""))):
                continue
            if not KEEP_ALL and x.get("has_replies") and any(r.get("is_reply_owned_by_me") for r in
                                             th_get(f"{x['id']}/replies", fields="id,is_reply_owned_by_me").get("data", [])):
                continue
            out.append({"p": "th", "id": x["id"], "on": (p.get("text") or "")[:70], "who": x.get("username"),
                        "at": x.get("timestamp"), "text": x.get("text", "")})


def cmd_fetch():
    out, done = [], done_ids()
    for p, fn in (("yt", fetch_yt), ("ig", fetch_ig), ("fb", fetch_fb), ("th", fetch_th)):
        n = len(out)
        try:
            fn(out, done)
        except SystemExit as e:
            print(p, "skipped:", str(e)[:250])
        except Exception as e:  # noqa: BLE001 - one platform failing must not stop the others
            print(p, "skipped:", type(e).__name__, str(e)[:250])
        print(p, len(out) - n, "unanswered")
    INBOX.write_text(json.dumps(out, indent=1, ensure_ascii=False), "utf-8")
    print("saved", len(out), "->", INBOX.relative_to(ROOT))


def send(p, cid, text):
    if p == "yt":
        import yt_api
        yt_api_service = getattr(send, "yt", None) or yt_api.service()
        send.yt = yt_api_service
        yt_api_service.comments().insert(part="snippet", body={"snippet": {"parentId": cid, "textOriginal": text}}).execute()
        return None
    if p in ("ig", "fb"):
        tok = meta_api.cfg()["page_token"]
        _, err = safe("POST", f"{cid}/replies" if p == "ig" else f"{cid}/comments",
                      params={"access_token": tok, "message": text})
        return err
    if p == "th":
        import threads_api  # tools/threads_api.py: container + publish, logged as a reply (not counted by pacing)
        try:
            threads_api.publish(threads_api.build(text, reply_to=cid), f"reply-{cid}")
            return None
        except SystemExit as e:
            return str(e)[:300]
    return f"unknown platform {p}"


def cmd_reply(path):
    todo, done, count = json.loads(Path(path).read_text("utf-8")), done_ids(), {}
    for r in todo:
        p, cid, text = r["p"], r["id"], r["text"]
        if cid in done or count.get(p, 0) >= MAX:
            continue
        try:
            err = send(p, cid, text)
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:250]}"
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"p": p, "id": cid, "at": int(time.time()), "ok": err is None, "text": text,
                                **({"err": err} if err else {})}, ensure_ascii=False) + "\n")
        print(p, "OK" if err is None else "FAILED", cid, err or "")
        count[p] = count.get(p, 0) + 1
        time.sleep(random.uniform(*PAUSE))
    print("done", count)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "tools"))
    a = sys.argv[1:]
    if a[:1] == ["fetch"]:
        cmd_fetch()
    elif a[:1] == ["reply"] and len(a) == 2:
        cmd_reply(a[1])
    else:
        sys.exit(__doc__)
