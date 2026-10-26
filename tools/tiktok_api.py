"""TikTok Content Posting API (Direct Post) helper for @cosmosinnumbers.

  python tiktok_api.py auth-url                       print the OAuth link the owner opens once (user.info.basic, video.publish)
  python tiktok_api.py setup <code>                   authorization code -> access + refresh token -> TIKTOK_JSON / secrets/tiktok.json
  python tiktok_api.py refresh                        new access token (24 h) from the refresh token (365 days, may rotate)
  python tiktok_api.py check                          creator info: nickname, allowed privacy levels, max video length
  python tiktok_api.py post <mp4|url> "<caption>" [--ref NAME] [--go]
                                                      DRY-RUN by default. Public, comments/duet/stitch on,
                                                      commercial disclosure "Your brand" (brand_organic_toggle).
  python tiktok_api.py next [--go]                    publish the next due item of queues/tiktok-queue.json

Credentials: secret TIKTOK_JSON or secrets/tiktok.json (client_key, client_secret, redirect_uri, open_id,
access_token, expires_at, refresh_token, refresh_expires_at), see creds.py. Never printed.
AI label: off by default (owner decision 24/10/2026). TIKTOK_AIGC_LABEL=true (env) or "aigc_label": true in the
config sets is_aigc. The text disclosure in every caption (synthetic voice, AI-assisted script, human review) stays.
Docs (checked 24/10/2026, pages updated 4/08/2026): developers.tiktok.com/doc/content-posting-api-reference-direct-post,
/doc/oauth-user-access-token-management. Unaudited clients can only post SELF_ONLY to private accounts.
Pacing: max 2 posts per day (13:00 data Short + 21:00 news Short), at least 3 h apart. Log logs/tiktok-publish-log.jsonl.
"""
from __future__ import annotations

import json
import os
import secrets as pysecrets
import sys
import time
import urllib.parse
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402

API = "https://open.tiktokapis.com/v2"
AUTH = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = "user.info.basic,video.publish"
LOG = creds.LOGS / "tiktok-publish-log.jsonl"
QUEUE = creds.QUEUES / "tiktok-queue.json"
MAX_PER_DAY, MIN_GAP_H = 2, 3


def cfg():
    return creds.load("tiktok")


def aigc(c):
    env = os.environ.get("TIKTOK_AIGC_LABEL")
    return (env.lower() == "true") if env else bool(c.get("aigc_label", False))


def oauth(data):
    r = requests.post(f"{API}/oauth/token/", data=data, timeout=60,
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    j = r.json()
    if r.status_code != 200 or "access_token" not in j:
        sys.exit(f"TikTok OAuth error {r.status_code}: {j.get('error')} {j.get('error_description', '')}")
    return j


def store(c, j):
    now = int(time.time())
    c.update(open_id=j["open_id"], access_token=j["access_token"], expires_at=now + int(j["expires_in"]),
             refresh_token=j["refresh_token"], refresh_expires_at=now + int(j["refresh_expires_in"]))
    creds.save("tiktok", c)


def token():
    """A valid access token; refreshed (and saved) when it expires within 10 minutes."""
    c = cfg()
    if c.get("access_token") and c.get("expires_at", 0) > time.time() + 600:
        return c["access_token"]
    if c.get("refresh_expires_at", 0) < time.time() + 7 * 86400:
        print("WARNING: TikTok refresh token expires within 7 days: the owner must redo auth-url + setup.")
    store(c, oauth({"client_key": c["client_key"], "client_secret": c["client_secret"],
                    "grant_type": "refresh_token", "refresh_token": c["refresh_token"]}))
    return cfg()["access_token"]


def call(path, body):
    r = requests.post(f"{API}{path}", json=body, timeout=120,
                      headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json; charset=UTF-8"})
    j = r.json()
    err = j.get("error", {})
    if r.status_code != 200 or err.get("code") not in (None, "ok"):
        sys.exit(f"TikTok API {r.status_code} {path}: {err.get('code')} {err.get('message', '')}")
    return j.get("data", {})


def pacing(at=None):
    at = int(at or time.time())
    ev = creds.events(LOG.name)
    if len([e for e in ev if abs(e["at"] - at) < 86400]) >= MAX_PER_DAY:
        return f"PACING: already {MAX_PER_DAY} TikTok posts within 24h."
    if any(abs(e["at"] - at) < MIN_GAP_H * 3600 for e in ev):
        return f"PACING: another TikTok post within {MIN_GAP_H}h."
    return None


def creator():
    return call("/post/publish/creator_info/query/", {})


def post(src, caption, ref, go):
    if len(caption) > 2200:
        sys.exit("Caption over 2200 characters.")
    c = cfg()
    info = creator()
    print("account:", info.get("creator_nickname"), "| privacy options:", info.get("privacy_level_options"))
    if "PUBLIC_TO_EVERYONE" not in info.get("privacy_level_options", []):
        sys.exit("PUBLIC_TO_EVERYONE not allowed for this client/account (unaudited client or private account).")
    post_info = {"title": caption, "privacy_level": "PUBLIC_TO_EVERYONE", "disable_comment": False,
                 "disable_duet": False, "disable_stitch": False, "brand_content_toggle": False,
                 "brand_organic_toggle": True, "is_aigc": aigc(c)}
    verdict = pacing()
    print(json.dumps({k: v for k, v in post_info.items() if k != "title"}), "|", caption[:80].replace("\n", " "))
    print(verdict or "Pacing: OK")
    if src.startswith("http"):
        creds.check_url(src)
    if not go:
        print("DRY-RUN: nothing sent.")
        return
    if ref in {e.get("ref") for e in creds.events(LOG.name)}:
        print(f"{ref} already published, skipped.")
        return
    if verdict:
        sys.exit(verdict)
    if src.startswith("http"):  # PULL_FROM_URL needs the URL prefix verified in the developer portal
        init = call("/post/publish/video/init/", {"post_info": post_info,
                                                  "source_info": {"source": "PULL_FROM_URL", "video_url": src}})
    else:
        size = Path(src).stat().st_size
        init = call("/post/publish/video/init/", {"post_info": post_info, "source_info": {
            "source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}})
        with open(src, "rb") as f:
            r = requests.put(init["upload_url"], data=f.read(), timeout=600, headers={
                "Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size - 1}/{size}"})
        if r.status_code not in (200, 201):
            sys.exit(f"TikTok upload failed: HTTP {r.status_code}")
    pid = init["publish_id"]
    for _ in range(60):
        time.sleep(10)
        st = call("/post/publish/status/fetch/", {"publish_id": pid})
        if st.get("status") == "PUBLISH_COMPLETE":
            break
        if st.get("status") == "FAILED":
            sys.exit(f"TikTok publish failed: {st.get('fail_reason')}")
    else:
        sys.exit(f"TikTok publish {pid} still processing after 10 minutes: check TikTok Studio before retrying.")
    ids = st.get("publicaly_available_post_id") or []
    url = f"https://www.tiktok.com/@cosmosinnumbers/video/{ids[0]}" if ids else ""
    creds.append(LOG.name, {"p": "tiktok", "k": "video", "at": int(time.time()), "id": str(ids[0]) if ids else pid,
                            "ref": ref, "url": url, "aigc": post_info["is_aigc"]})
    print("Published:", url or pid)


def run_item(item, go):
    post(item["video_url"], item["caption"], item["ref"], go)


def cmd_next(go):
    q = json.loads(QUEUE.read_text("utf-8")) if QUEUE.exists() else []
    done = {e.get("ref") for e in creds.events(LOG.name)}
    now = creds.now_local().strftime("%Y-%m-%d %H:%M")
    item = next((i for i in q if i["ref"] not in done and i["at"] <= now), None)
    if not item:
        print("Nothing due in the TikTok queue.")
        return
    run_item(item, go)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd = a[0]
    if cmd == "auth-url":
        c = cfg()
        q = {"client_key": c["client_key"], "scope": SCOPES, "response_type": "code",
             "redirect_uri": c["redirect_uri"], "state": pysecrets.token_urlsafe(16)}
        print(f"{AUTH}?{urllib.parse.urlencode(q)}")
        print("Open it logged in as @cosmosinnumbers, approve, then copy 'code' from the redirect URL.")
    elif cmd == "setup":
        c = cfg()
        store(c, oauth({"client_key": c["client_key"], "client_secret": c["client_secret"], "grant_type": "authorization_code",
                        "code": urllib.parse.unquote(a[1]), "redirect_uri": c["redirect_uri"]}))
        print("TikTok tokens saved (access 24 h, refresh 365 days).")
    elif cmd == "refresh":
        c = cfg()
        store(c, oauth({"client_key": c["client_key"], "client_secret": c["client_secret"],
                        "grant_type": "refresh_token", "refresh_token": c["refresh_token"]}))
        print("TikTok access token refreshed.")
    elif cmd == "check":
        i = creator()
        print({k: i.get(k) for k in ("creator_nickname", "creator_username", "privacy_level_options",
                                     "max_video_post_duration_sec", "comment_disabled", "duet_disabled", "stitch_disabled")})
    elif cmd == "post":
        go = "--go" in a
        rest = [x for x in a[1:] if x != "--go"]
        ref = rest[rest.index("--ref") + 1] if "--ref" in rest else "manual"
        post(rest[0], rest[1], ref, go)
    elif cmd == "next":
        cmd_next("--go" in a)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
