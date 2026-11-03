"""Daily Short on YouTube via the API, public at 21:00 Rome time (owner decision 30/10/2026, after the test
upload C-BKdHUodpE stayed public).

  python tools/yt_short_upload.py [--tag a1031-slug] [--dry-run] [--now]

Takes today's release of shorts-build (a<MMDD>-*, reserve Shorts included), title and description from its
upload.md (LOOK UP line, sources, credits, synthetic voice and AI disclosure), uploads the mp4 as public.
Timing: the 20:45 slot of youtube-upload.yml waits for UPLOAD_AT (21:00); earlier runs (after shorts-build) only
check and exit, unless --now or --tag is given. Never twice: logs/youtube-publish-log.jsonl (ref = tag) and the
titles already on the channel. 2 attempts, then exit 1 (the workflow opens an issue). Credentials: secret
YOUTUBE_TOKEN_JSON (authorized-user JSON), never printed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402

TZ = ZoneInfo("Europe/Rome")
LOG = "youtube-publish-log.jsonl"
REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
UPLOAD_AT = os.environ.get("UPLOAD_AT", "21:00")
PREFIX = os.environ.get("SHORT_PREFIX", "a")   # "b" = second Short of the day (hot news), public at 15:00
DRY = "--dry-run" in sys.argv


def gh(*a) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(a[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def release(now, tag):
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=20"))
    return next((r for r in rels if (r["tag_name"] == tag if tag else r["tag_name"].startswith(f"{PREFIX}{now:%m%d}-"))), None)


def section(md, name):
    m = re.search(rf"^## {name}\s*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return re.sub(r"^```\w*\s*$", "", m.group(1), flags=re.M).strip() if m else ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    tag = a[a.index("--tag") + 1] if "--tag" in a else None
    now = datetime.now(TZ)
    rel = release(now, tag)
    if not rel:
        print(f"No Short release {'%s' % tag if tag else 'for today'}: nothing to upload.")
        return
    ref = rel["tag_name"]
    if ref in {e.get("ref") for e in creds.events(LOG)}:
        print(f"{ref}: already uploaded (log).")
        return
    h, m = map(int, UPLOAD_AT.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if not (tag or "--now" in a) and now < target - timedelta(minutes=25):
        print(f"{ref}: ready, upload at {UPLOAD_AT}.")
        return
    with tempfile.TemporaryDirectory() as d:
        gh("release", "download", ref, "--repo", REPO, "-p", "*.mp4", "-p", "upload.md", "-D", d)
        md = (Path(d) / "upload.md").read_text("utf-8")
        mp4 = next(p for p in Path(d).glob("*.mp4") if not p.name.endswith("_social.mp4"))  # YouTube: never the social variant
        title = section(md, "Title").splitlines()[0].strip()
        desc = section(md, "Description")
        if not title or "LOOK UP" not in desc:
            sys.exit(f"{ref}: upload.md without title or LOOK UP line: not uploaded.")
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        info = json.loads(os.environ.get("YOUTUBE_TOKEN_JSON") or (creds.LOCAL_SECRETS / "token.json").read_text("utf-8"))
        yt = build("youtube", "v3", credentials=Credentials.from_authorized_user_info(info), cache_discovery=False)
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        for it in yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50).execute()["items"]:
            if it["snippet"]["title"].strip().lower() == title.lower():
                vid = it["snippet"]["resourceId"]["videoId"]
                print(f"{ref}: already on the channel ({vid}), not uploaded again.")
                if not DRY:
                    creds.append(LOG, {"p": "youtube", "k": "short", "at": int(time.time()), "id": vid, "ref": ref,
                                       "note": "found on the channel"})
                return
        print(f"{ref}: '{title}' ({mp4.stat().st_size // 1024} KB), public at {UPLOAD_AT}")
        if DRY:
            print("DRY-RUN: nothing uploaded.")
            return
        wait = (target - datetime.now(TZ)).total_seconds()
        if 0 < wait < 3600 and not (tag or "--now" in a):
            time.sleep(wait)
        body = {"snippet": {"title": title, "description": desc, "tags": re.findall(r"#(\w+)", desc),
                            "categoryId": "28", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": False, "license": "youtube", "embeddable": True}}
        for attempt in (1, 2):
            try:
                req = yt.videos().insert(part="snippet,status", body=body,
                                         media_body=MediaFileUpload(str(mp4), mimetype="video/mp4", chunksize=-1,
                                                                    resumable=True))
                resp = None
                while resp is None:
                    _, resp = req.next_chunk()
                break
            except Exception as e:  # noqa: BLE001
                print(f"attempt {attempt} failed: {type(e).__name__}: {str(e)[:200]}")
                if attempt == 2:
                    sys.exit(f"{ref}: YouTube upload failed twice.")
                time.sleep(60)
        vid = resp["id"]
        creds.append(LOG, {"p": "youtube", "k": "short", "at": int(time.time()), "id": vid, "ref": ref})
        print(f"uploaded {ref}: https://youtu.be/{vid} privacy={resp['status'].get('privacyStatus')}")


if __name__ == "__main__":
    main()
