"""YouTube Shorts scheduling from GitHub Actions: OFF until Google approves the API audit.

  python tools/yt_publish.py [--dry-run]

queues/youtube-queue.json items: {"ref", "at" (Italian time = publishAt), "video_url", "title", "description", "tags"}.
Uploads each item not yet in logs/youtube-publish-log.jsonl as private with publishAt (YouTube releases it).
Needs YT_ENABLED=true and the secret YOUTUBE_TOKEN_JSON (authorized-user JSON of the Cosmos channel, same
content as secrets/token.json). Before the audit, API uploads stay locked private: keep using YouTube Studio.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402

LOG = "youtube-publish-log.jsonl"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if os.environ.get("YT_ENABLED", "false").lower() != "true":
        sys.exit("YouTube publishing is off (YT_ENABLED=false) until Google approves the API audit.")
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    qf = creds.QUEUES / "youtube-queue.json"
    q = json.loads(qf.read_text("utf-8")) if qf.exists() else []
    done = {e.get("ref") for e in creds.events(LOG)}
    todo = [i for i in q if i["ref"] not in done and creds.stamp(i["at"]) > datetime.now().timestamp() + 900]
    if not todo:
        print("Nothing to schedule on YouTube.")
        return
    info = json.loads(os.environ.get("YOUTUBE_TOKEN_JSON") or (creds.LOCAL_SECRETS / "token.json").read_text("utf-8"))
    yt = build("youtube", "v3", credentials=Credentials.from_authorized_user_info(info), cache_discovery=False)
    for it in todo:
        when = datetime.fromtimestamp(creds.stamp(it["at"]), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if "--dry-run" in sys.argv:
            creds.check_url(it["video_url"])
            print("would schedule", it["ref"], when)
            continue
        body = {"snippet": {"title": it["title"], "description": it["description"], "tags": it.get("tags", []),
                            "categoryId": "28", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                "status": {"privacyStatus": "private", "publishAt": when, "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": False}}
        media = MediaFileUpload(creds.local_media(it["video_url"]), mimetype="video/mp4", resumable=True)
        vid = yt.videos().insert(part="snippet,status", body=body, media_body=media).execute()["id"]
        creds.append(LOG, {"p": "youtube", "k": "short", "at": creds.stamp(it["at"]), "id": vid, "ref": it["ref"]})
        print("scheduled", it["ref"], vid, when)


if __name__ == "__main__":
    main()
