"""Long video on YouTube via the API (owner 03/11/2026: "il caricamento lo fai sempre via api youtube").

  python tools/yt_long_upload.py [--tag lf-<id>] [--replace <videoId>] [--dry-run]

Takes the oldest release lf-<id> of longform-build that is not yet on the channel (logs/youtube-publish-log.jsonl,
ref = tag, plus the titles on the channel) and uploads <id>.mp4 as a SCHEDULED video: private with publishAt on
the next free Sunday at PUBLISH_AT (16:00 Italian time; one long video per Sunday), so YouTube makes it public
by itself. Then: English captions from <id>.srt, thumbnail thumb_A.jpg (needs a verified channel: a failure is
only a warning). Title, description and tags from upload.md; an old launch code in the text becomes COSMOS9.
--replace <videoId> (owner's ok needed: it deletes a video): first deletes that video of ours from the channel and
drops its lines from the log, so the same release (e.g. rebuilt with new animations) is uploaded again on the same Sunday.
Credentials: secret YOUTUBE_TOKEN_JSON (same as the Shorts), never printed. Quota: about 2,100 of 10,000 units.
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
PUBLISH_AT = os.environ.get("LONG_PUBLISH_AT", "16:00")
DRY = "--dry-run" in sys.argv


def gh(*a) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(a[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def youtube():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    info = json.loads(os.environ.get("YOUTUBE_TOKEN_JSON") or (creds.LOCAL_SECRETS / "token.json").read_text("utf-8"))
    return build("youtube", "v3", credentials=Credentials.from_authorized_user_info(info), cache_discovery=False)


def section(md: str, name: str) -> str:
    m = re.search(rf"^## {name}\s*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return re.sub(r"^```\w*\s*$", "", m.group(1), flags=re.M).strip() if m else ""


def clean_description(desc: str) -> str:
    """The launch code of October (LAUNCH9, expired) becomes the current one; the LOOK UP link stays first."""
    desc = re.sub(r"\(code LAUNCH9[^)]*\)", "(code COSMOS9)", desc)
    return desc.replace("LAUNCH9", "COSMOS9")


def tags_of(md: str) -> list[str]:
    raw = section(md, "Tags").splitlines()[0] if section(md, "Tags") else ""
    out, n = [], 0
    for t in (x.strip() for x in raw.split(",")):
        if t and n + len(t) + 2 <= 480:
            out.append(t)
            n += len(t) + 2
    return out


def next_sunday(now: datetime, taken: set[str]) -> datetime:
    """Next Sunday at PUBLISH_AT at least 3 hours away, skipping Sundays that already have a long video."""
    h, m = map(int, PUBLISH_AT.split(":"))
    d = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=(6 - now.weekday()) % 7)
    while d < now + timedelta(hours=3) or d.date().isoformat() in taken:
        d += timedelta(days=7)
    return d


def drop_from_log(vid: str) -> int:
    """Removes the log lines of a deleted video; returns how many."""
    p = creds.LOGS / LOG
    if not p.exists():
        return 0
    lines = p.read_text("utf-8").splitlines()
    keep = [l for l in lines if not l.strip() or json.loads(l).get("id") != vid]
    p.write_text("\n".join(keep) + ("\n" if keep else ""), "utf-8")
    return len(lines) - len(keep)


def pending(tag: str | None) -> list[dict]:
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=100"))
    done = {e.get("ref") for e in creds.events(LOG)}
    lf = [r for r in rels if r["tag_name"].startswith("lf-") and (r["tag_name"] == tag if tag else r["tag_name"] not in done)]
    return sorted(lf, key=lambda r: r["created_at"])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    tag = a[a.index("--tag") + 1] if "--tag" in a else None
    replace = a[a.index("--replace") + 1] if "--replace" in a else None
    if replace:
        old = [e for e in creds.events(LOG) if e.get("id") == replace and e.get("k") == "long"]
        if not old:
            sys.exit(f"--replace {replace}: not a long video in the log, nothing deleted.")
        tag = tag or old[0]["ref"]
        if DRY:
            print(f"DRY-RUN: would delete {replace} ({tag}) and upload the release again.")
        else:
            yt = youtube()
            try:
                yt.videos().delete(id=replace).execute()
                print(f"deleted {replace} ({tag})")
            except Exception as e:  # noqa: BLE001
                if "404" not in str(e) and "videoNotFound" not in str(e):
                    sys.exit(f"delete {replace} failed: {type(e).__name__}: {str(e)[:200]}")
                print(f"{replace} already gone from the channel")
            print(f"log: {drop_from_log(replace)} lines removed")
    rels = pending(tag)
    if not rels:
        print("No long video waiting for YouTube.")
        return
    rel = rels[0]
    ref, vid_id = rel["tag_name"], rel["tag_name"][3:]
    if ref in {e.get("ref") for e in creds.events(LOG)}:
        print(f"{ref}: already uploaded (log).")
        return
    names = {x["name"] for x in rel.get("assets", [])}
    if f"{vid_id}.mp4" not in names or "upload.md" not in names:
        sys.exit(f"{ref}: release without {vid_id}.mp4 or upload.md")
    taken = {e["publish_day"] for e in creds.events(LOG) if e.get("k") == "long" and e.get("publish_day")}
    when = next_sunday(datetime.now(TZ), taken)
    with tempfile.TemporaryDirectory() as d:
        pats = []
        for f in (f"{vid_id}.mp4", "upload.md", f"{vid_id}.srt", "thumb_A.jpg"):
            if f in names:
                pats += ["-p", f]
        gh("release", "download", ref, "--repo", REPO, *pats, "-D", d)
        md = (Path(d) / "upload.md").read_text("utf-8")
        title = section(md, "Title").splitlines()[0].strip()
        desc = clean_description(section(md, "Description"))
        if not title or "LOOK UP" not in desc:
            sys.exit(f"{ref}: upload.md without title or LOOK UP line: not uploaded.")
        tags = tags_of(md)
        print(f"{ref}: '{title}', scheduled public {when:%a %d/%m %H:%M} (Rome), {len(tags)} tags")
        if DRY:
            print("DRY-RUN: nothing uploaded.\n" + desc[:400])
            return
        from googleapiclient.http import MediaFileUpload
        yt = youtube()
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        for it in yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50).execute()["items"]:
            if it["snippet"]["title"].strip().lower() == title.lower() and it["snippet"]["resourceId"]["videoId"] != replace:
                vid = it["snippet"]["resourceId"]["videoId"]
                print(f"{ref}: already on the channel ({vid}), not uploaded again.")
                creds.append(LOG, {"p": "youtube", "k": "long", "at": int(time.time()), "id": vid, "ref": ref, "note": "found on the channel"})
                return
        body = {"snippet": {"title": title, "description": desc, "tags": tags, "categoryId": "28",
                            "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                "status": {"privacyStatus": "private", "publishAt": when.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False, "license": "youtube",
                           "embeddable": True}}
        mp4 = Path(d) / f"{vid_id}.mp4"
        resp = None
        for attempt in (1, 2):
            try:
                req = yt.videos().insert(part="snippet,status", body=body,
                                         media_body=MediaFileUpload(str(mp4), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True))
                while resp is None:
                    _, resp = req.next_chunk()
                break
            except Exception as e:  # noqa: BLE001
                print(f"attempt {attempt} failed: {type(e).__name__}: {str(e)[:200]}")
                if attempt == 2:
                    sys.exit(f"{ref}: YouTube upload failed twice.")
                time.sleep(60)
        vid = resp["id"]
        creds.append(LOG, {"p": "youtube", "k": "long", "at": int(time.time()), "id": vid, "ref": ref,
                           "publish_at": int(when.timestamp()), "publish_day": when.date().isoformat()})
        print(f"uploaded {ref}: https://youtu.be/{vid} public at {when:%d/%m %H:%M}")
        srt = Path(d) / f"{vid_id}.srt"
        if srt.exists():
            try:
                yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}},
                                     media_body=MediaFileUpload(str(srt), mimetype="application/octet-stream")).execute()
                print("  captions: English uploaded")
            except Exception as e:  # noqa: BLE001
                print(f"  WARNING captions not uploaded: {type(e).__name__}: {str(e)[:150]}")
        thumb = Path(d) / "thumb_A.jpg"
        if thumb.exists():
            try:
                yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
                print("  thumbnail: thumb_A.jpg")
            except Exception as e:  # noqa: BLE001
                print(f"  WARNING thumbnail not set (verified channel needed?): {type(e).__name__}: {str(e)[:150]}")


if __name__ == "__main__":
    main()
