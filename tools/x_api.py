"""X (Twitter) API helper for Cosmos in Numbers.

  python x_api.py check                                  show the account linked to the keys (1 user read, ~$0.01)
  python x_api.py post "<text>" [--media FILE] [--reply "<text>"] [--ref NAME] [--go]
                                                         DRY-RUN by default; --go publishes. --reply chains one post under it.
  python x_api.py next [--go]                            publish the next due item of 07-analytics/x-queue.json
  python x_api.py budget                                 estimated spend this month vs the cap

Credentials: secret X_JSON or secrets/x.json (api_key, api_secret, access_token, access_token_secret, OAuth 1.0a,
app with Read and Write, plus monthly_budget_usd, default 20), see creds.py. Never shared or zipped.
Cost (docs.x.com pricing, checked 19/10/2026, pay-per-use, no free tier for new apps):
$0.015 per post, $0.20 per post containing a URL. The budget cap stops publishing before it is exceeded.
Pacing: up to 3 main posts per day, at least 3 h apart (same rule as Threads), log logs/x-publish-log.jsonl (cosmos-automation repo, the only
source of truth for pacing and spend).
Media upload uses the v2 chunked endpoints (/2/media/upload/initialize|append|finalize): not yet tested live.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from requests_oauthlib import OAuth1

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402
import cta  # noqa: E402
from datetime import date  # noqa: E402

LOG = creds.LOGS / "x-publish-log.jsonl"
QUEUE = creds.QUEUES / "x-queue.json"
API = "https://api.x.com/2"
MAX_PER_DAY, MIN_GAP_H = 3, 3
COST_POST, COST_URL = 0.015, 0.20
URL_RE = re.compile(r"(https?://|www\.)\S+|\b[\w-]+\.(com|io|org|net)/\S*", re.I)


def cfg():
    return creds.load("x")


def auth():
    c = cfg()
    return OAuth1(c["api_key"], c["api_secret"], c["access_token"], c["access_token_secret"])


def call(method, path, **kw):
    r = requests.request(method, f"{API}{path}", auth=auth(), timeout=120, **kw)
    j = r.json() if r.content else {}
    if r.status_code >= 300:
        sys.exit(f"X API {r.status_code}: {j}")
    return j


def events():
    return creds.events(LOG.name)


def cost(text):
    return COST_URL if URL_RE.search(text) else COST_POST


def spent_this_month():
    month = creds.now_local().strftime("%Y-%m")
    return sum(e.get("usd", 0) for e in events()
               if datetime.fromtimestamp(e["at"], creds.TZ).strftime("%Y-%m") == month)


def guard(texts):
    """Return None if posting `texts` now is allowed, else the reason."""
    now = int(time.time())
    main = [e for e in events() if e.get("k") != "reply"]
    if len([e for e in main if creds.day(e["at"]) == creds.day(now)]) >= MAX_PER_DAY:
        return f"PACING: already {MAX_PER_DAY} X posts today."
    if any(now - e["at"] < MIN_GAP_H * 3600 for e in main):
        return f"PACING: another X post within {MIN_GAP_H}h."
    cap = float(cfg().get("monthly_budget_usd", 20))
    need = sum(cost(t) for t in texts)
    if spent_this_month() + need > cap:
        return f"BUDGET: ${spent_this_month():.2f} spent this month, +${need:.2f} would pass the ${cap:.2f} cap."
    return None


def upload(path):
    p = Path(path)
    mime = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}[p.suffix.lower()]
    cat = "tweet_video" if mime == "video/mp4" else "tweet_image"
    init = call("POST", "/media/upload/initialize",
                json={"media_type": mime, "total_bytes": p.stat().st_size, "media_category": cat})
    mid = init["data"]["id"]
    with p.open("rb") as f:
        for i, chunk in enumerate(iter(lambda: f.read(4 * 1024 * 1024), b"")):
            call("POST", f"/media/upload/{mid}/append", data={"segment_index": i}, files={"media": chunk})
    info = call("POST", f"/media/upload/{mid}/finalize").get("data", {}).get("processing_info")
    while info and info.get("state") in ("pending", "in_progress"):
        time.sleep(info.get("check_after_secs", 5))
        info = call("GET", "/media/upload", params={"command": "STATUS", "media_id": mid}).get("data", {}).get("processing_info")
    if info and info.get("state") == "failed":
        sys.exit(f"Media processing failed: {info}")
    return mid


def publish(text, ref, media=None, reply_to=None):
    body = {"text": text}
    if media:
        body["media"] = {"media_ids": [upload(media)]}
    if reply_to:
        body["reply"] = {"in_reply_to_tweet_id": reply_to}
    tid = call("POST", "/tweets", json=body)["data"]["id"]
    url = f"https://x.com/i/web/status/{tid}"
    creds.append(LOG.name, {"p": "x", "k": "reply" if reply_to else ("video" if media else "text"),
                            "at": int(time.time()), "id": tid, "ref": ref, "url": url, "usd": cost(text)})
    return tid, url


def run(text, replies, media, ref, go):
    if len(text) > 280 or any(len(r) > 280 for r in replies):
        sys.exit("Text over 280 characters: shorten it.")
    verdict = guard([text, *replies])
    print(text, f"\n[media: {media}]" if media else "")
    for r in replies:
        print("  reply:", r.replace("\n", " ")[:100])
    print(f"Estimated cost: ${sum(cost(t) for t in [text, *replies]):.3f}")
    print(verdict or "Pacing and budget: OK")
    if not go:
        print("DRY-RUN: nothing sent.")
        return
    ids = {e.get("ref"): e.get("id") for e in events()}
    if ref in ids:  # a retry after a failed reply: never post the main text twice
        pid = ids[ref]
    else:
        if verdict:
            sys.exit(verdict)
        pid, url = publish(text, ref, media=creds.local_media(media) if media else None)
        print(f"Published: {url}")
    for n, r in enumerate(replies, 1):
        rr = f"{ref}-r{n}"
        pid = ids[rr] if rr in ids else publish(r, rr, reply_to=pid)[0]


def cmd_post(args):
    go = "--go" in args
    args = [a for a in args if a != "--go"]
    opt = lambda k: args[args.index(k) + 1] if k in args else None
    run(args[0], [opt("--reply")] if opt("--reply") else [], opt("--media"), opt("--ref") or "manual", go)


def cmd_next(go):
    q = json.loads(QUEUE.read_text("utf-8"))
    done = {e.get("ref") for e in events()}
    now = creds.now_local().strftime("%Y-%m-%d %H:%M")
    item = next((i for i in q if i["ref"] not in done and i["at"] <= now), None)
    if not item:
        print("Nothing due in the X queue.")
        return
    run_item(item, go)


def run_item(item, go):
    """One queue item: text, optional media (public URL on cosmosinnumbers.github.io/media/), replies."""
    if item.get("media"):
        creds.check_url(item["media"])
    replies = item.get("replies", [])
    if "gumroad.com" not in item["text"]:  # product link always in the FIRST reply (link in the post cuts reach)
        replies = cta.first_reply(item["ref"], replies, expired=creds.now_local().date() > date(2026, 11, 30),
                                  source="x", post=item["text"])
    run(item["text"], replies, item.get("media"), item["ref"], go)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    {"check": lambda: print(call("GET", "/users/me")["data"]),
     "post": lambda: cmd_post(a[1:]), "next": lambda: cmd_next("--go" in a),
     "budget": lambda: print(f"${spent_this_month():.2f} this month, cap ${float(cfg().get('monthly_budget_usd', 20)):.2f}")
     }.get(a[0], lambda: sys.exit(__doc__))()
