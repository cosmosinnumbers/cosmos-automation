"""YouTube Data API helper: thumbnails, captions, banner, watermark. Never publishes anything.

  python yt_api.py auth                         one-time browser consent -> secrets/token.json
  python yt_api.py list                         channel videos with id, title, privacy
  python yt_api.py thumb   <video_id> <jpg>     thumbnails.set   (50 units; needs a phone-verified channel)
  python yt_api.py caption <video_id> <srt>     captions.insert  (400 units, English track)
  python yt_api.py banner  <png>                channelBanners.insert + channels.update (100 units)
  python yt_api.py watermark <png>              watermarks.set, shown at the end of every video (50 units)
  python yt_api.py upload <short_dir> <UTC>     uploads out/<id>.mp4 private, publishAt <UTC>; refuses duplicates

secrets/client_secret.json = OAuth client of type "Desktop app" from the owner's Google Cloud project.
secrets/ is never zipped or shared. No call here changes a video's privacy status.
"""
from __future__ import annotations

import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parents[2]
SECRETS = ROOT / "secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
AUDIT_APPROVED = False  # set True when Google approves the YouTube API audit (submitted 15/10/2026)


def service():
    tok = SECRETS / "token.json"
    creds = Credentials.from_authorized_user_file(str(tok), SCOPES) if tok.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS / "client_secret.json"), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
    tok.write_text(creds.to_json(), "utf-8")
    return build("youtube", "v3", credentials=creds)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmd, args = sys.argv[1], sys.argv[2:]
    yt = service()
    if cmd == "auth":
        ch = yt.channels().list(part="snippet", mine=True).execute()["items"][0]
        print("authorised for channel:", ch["snippet"]["title"], ch["id"])
    elif cmd == "list":
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50).execute()["items"]
        ids = ",".join(i["contentDetails"]["videoId"] for i in items)
        for v in yt.videos().list(part="snippet,status", id=ids).execute()["items"]:
            print(v["id"], v["status"]["privacyStatus"], v["snippet"]["title"])
    elif cmd == "thumb":
        vid, img = args
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(img, mimetype="image/jpeg")).execute()
        print("thumbnail set:", vid)
    elif cmd == "caption":
        vid, srt = args
        body = {"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}}
        r = yt.captions().insert(part="snippet", body=body,
                                 media_body=MediaFileUpload(srt, mimetype="application/octet-stream")).execute()
        print("caption added:", vid, r["id"])
    elif cmd == "banner":
        url = yt.channelBanners().insert(media_body=MediaFileUpload(args[0], mimetype="image/png")).execute()["url"]
        ch = yt.channels().list(part="brandingSettings", mine=True).execute()["items"][0]
        ch["brandingSettings"].setdefault("image", {})["bannerExternalUrl"] = url
        yt.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": ch["brandingSettings"]}).execute()
        print("banner set")
    elif cmd == "schedule":
        # owner-approved scheduled release: stays private until publishAt (UTC, e.g. 2026-10-16T19:00:00Z)
        vid, when = args
        v = yt.videos().list(part="status", id=vid).execute()["items"][0]
        st = v["status"]
        if st["privacyStatus"] != "private":
            sys.exit(f"{vid} is {st['privacyStatus']}, not private: refusing to touch it")
        st["publishAt"] = when
        keep = {k: st[k] for k in ("privacyStatus", "publishAt", "embeddable", "license", "publicStatsViewable",
                                   "selfDeclaredMadeForKids", "containsSyntheticMedia") if k in st}
        r = yt.videos().update(part="status", body={"id": vid, "status": keep}).execute()
        print("scheduled:", vid, r["status"].get("publishAt"), r["status"]["privacyStatus"])
    elif cmd == "find":
        # video id of a web-uploaded file: Studio titles it with the file name (e.g. "n43a venus clouds")
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        for it in yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50).execute()["items"]:
            if it["snippet"]["title"].lower().replace(" ", "-").startswith(args[0].lower()):
                print(it["snippet"]["resourceId"]["videoId"]); break
        else:
            sys.exit(f"no upload titled like {args[0]}")
    elif cmd == "apply":
        # metadata from <short_dir>/out/upload.md + scheduled release (UTC), stays private until then
        import re
        vid, sdir, when = args
        md = (Path(sdir) / "out" / "upload.md").read_text("utf-8")
        title = re.search(r"## Title\n(.+)", md).group(1).strip()
        desc = re.search(r"## Description\n```\n(.*?)\n```", md, re.S).group(1)
        tags = re.findall(r"#(\w+)", desc)
        yt.videos().update(part="snippet,status", body={"id": vid,
            "snippet": {"title": title, "description": desc, "tags": tags, "categoryId": "28",
                        "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": "private", "publishAt": when, "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": False, "license": "youtube", "embeddable": True}}).execute()
        print("applied:", vid, title, when)
    elif cmd == "upload":
        # upload <short_dir> <UTC>: out/<id>.mp4 + out/upload.md, private until publishAt. Refuses duplicates.
        import re
        # until Google approves the API audit, API uploads are locked private by YouTube ("unverified project"):
        # they would never go public. Upload in Studio instead, then `find` + `apply`.
        if not AUDIT_APPROVED:
            sys.exit("upload disabled: YouTube API audit not approved yet (API uploads stay locked private). "
                     "Upload in Studio, then: yt_api.py find <id> && yt_api.py apply <VIDEO_ID> <short_dir> <UTC>")
        sdir, when = Path(args[0]), args[1]
        sid = sdir.name
        md = (sdir / "out" / "upload.md").read_text("utf-8")
        title = re.search(r"## Title\n(.+)", md).group(1).strip()
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        for it in yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=50).execute()["items"]:
            if it["snippet"]["title"].strip() == title or it["snippet"]["title"].lower().startswith(sid.lower()):
                sys.exit(f"{sid}: already on the channel ({it['snippet']['resourceId']['videoId']})")
        desc = re.search(r"## Description\n```\n(.*?)\n```", md, re.S).group(1)
        tags = re.findall(r"#(\w+)", desc)
        body = {"snippet": {"title": title, "description": desc, "tags": tags, "categoryId": "28",
                            "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                "status": {"privacyStatus": "private", "publishAt": when, "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": False, "license": "youtube", "embeddable": True}}
        req = yt.videos().insert(part="snippet,status", body=body,
                                 media_body=MediaFileUpload(str(sdir / "out" / f"{sid}.mp4"), mimetype="video/mp4",
                                                            chunksize=-1, resumable=True))
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        print("uploaded:", resp["id"], title, when)
    elif cmd == "cta-comments":
        # every public video gets ONE channel comment with the keyword CTA + free chapter link (idempotent)
        CTA = ("🔭 Want to see this with your own eyes? Comment SKY 👇 and tell us what you'll look for first.\n"
               "📘 Free chapter of our beginner's stargazing guide (no telescope needed): "
               "https://cosmosinnumbers.github.io/look-up.html")
        MARK = "cosmosinnumbers.github.io/look-up"
        import json
        # local log = hard guarantee of one CTA per video (the API can lag or hold new comments for review)
        LOG = ROOT / "07-analytics" / "cta-comments.json"
        posted = json.loads(LOG.read_text("utf-8")) if LOG.exists() else {}
        ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        me, uploads = ch["id"], ch["contentDetails"]["relatedPlaylists"]["uploads"]
        ids = [i["contentDetails"]["videoId"] for i in
               yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50).execute()["items"]]
        for v in yt.videos().list(part="status,snippet", id=",".join(ids)).execute()["items"]:
            if v["status"]["privacyStatus"] != "public":
                continue
            threads = yt.commentThreads().list(part="snippet", videoId=v["id"], maxResults=100).execute().get("items", [])
            done = any(t["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {}).get("value") == me
                       and MARK in t["snippet"]["topLevelComment"]["snippet"]["textOriginal"] for t in threads)
            if done or v["id"] in posted:
                print("ok (already)", v["id"]); continue
            r = yt.commentThreads().insert(part="snippet", body={"snippet": {"videoId": v["id"],
                "topLevelComment": {"snippet": {"textOriginal": CTA}}}}).execute()
            posted[v["id"]] = r["id"]
            LOG.write_text(json.dumps(posted, indent=1), "utf-8")
            print("posted CTA", v["id"], v["snippet"]["title"][:50])
    elif cmd == "product-line":
        # product-line [VIDEO_ID ...] [--go]: prepend the paid-product line to descriptions (owner 18-19/10/2026,
        # idempotent). No ids = every upload. Dry-run unless --go. Keep title/tags/category as they are.
        LINE = "📘 LOOK UP, our beginner's stargazing guide: https://cosmosinnumbers.gumroad.com/l/look-up (code COSMOS9 → $9 until Nov 30)"
        MARK = "gumroad.com/l/look-up"
        go = "--go" in args
        ids = [a for a in args if a != "--go"]
        if not ids:
            ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
            ids = [i["contentDetails"]["videoId"] for i in yt.playlistItems().list(part="contentDetails",
                   playlistId=ch["contentDetails"]["relatedPlaylists"]["uploads"], maxResults=50).execute()["items"]]
        for v in yt.videos().list(part="snippet", id=",".join(ids)).execute()["items"]:
            s = v["snippet"]
            if MARK in s.get("description", ""):
                print("ok (already)", v["id"], s["title"][:50]); continue
            if not go:
                print("would update", v["id"], s["title"][:50]); continue
            body = {k: s[k] for k in ("title", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage") if k in s}
            body["description"] = LINE + "\n\n" + s.get("description", "")
            yt.videos().update(part="snippet", body={"id": v["id"], "snippet": body}).execute()
            print("updated", v["id"], s["title"][:50])
    elif cmd == "playlist-add":
        # playlist-add <video_id> <news|solar|exo|missions>: series playlists, so viewers binge the next video
        PL = {"news": "PLetGxaN52L6Y", "solar": "PLJNgp_FwSdks", "exo": "PLH71BMQKgUWs", "missions": "PLc-rGSX7mGRo"}
        vid, key = args
        yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": PL[key],
            "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        print("added", vid, "->", key)
    elif cmd == "playlists-public":
        # owner-requested: every playlist of the channel becomes public (private/scheduled videos stay hidden)
        for p in yt.playlists().list(part="snippet,status", mine=True, maxResults=50).execute()["items"]:
            if p["status"]["privacyStatus"] != "public":
                yt.playlists().update(part="snippet,status", body={"id": p["id"], "snippet": {"title": p["snippet"]["title"], "description": p["snippet"]["description"]}, "status": {"privacyStatus": "public"}}).execute()
            print("public:", p["snippet"]["title"])
    elif cmd == "audit":
        ids = ",".join(args)
        for v in yt.videos().list(part="snippet,status,contentDetails", id=ids).execute()["items"]:
            s, st = v["snippet"], v["status"]
            caps = yt.captions().list(part="snippet", videoId=v["id"]).execute()["items"]
            print(v["id"], st["privacyStatus"], st.get("publishAt", "-"), "cat", s.get("categoryId"), "lang", s.get("defaultAudioLanguage"),
                  "kids", st.get("selfDeclaredMadeForKids"), "synthetic", st.get("containsSyntheticMedia"), "tags", len(s.get("tags", [])),
                  "caps", [c["snippet"]["language"] for c in caps], "thumb", "maxres" in s["thumbnails"] or "high" in s["thumbnails"], "|", s["title"][:40])
    elif cmd == "watermark":
        ch = yt.channels().list(part="id", mine=True).execute()["items"][0]["id"]
        body = {"timing": {"type": "offsetFromEnd", "offsetMs": 15000, "durationMs": 15000}, "position": {"type": "corner", "cornerPosition": "topRight"}}
        # httplib2 crashes decoding this endpoint's empty gzip reply, so send it with requests instead
        import json
        from google.auth.transport.requests import AuthorizedSession
        sess = AuthorizedSession(yt._http.credentials)
        b = "cosmos_boundary_7f3a"
        payload = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(body)}\r\n"
                   f"--{b}\r\nContent-Type: image/png\r\n\r\n").encode() + Path(args[0]).read_bytes() + f"\r\n--{b}--".encode()
        r = sess.post("https://www.googleapis.com/upload/youtube/v3/watermarks/set",
                      params={"channelId": ch, "uploadType": "multipart"}, data=payload,
                      headers={"Content-Type": f"multipart/related; boundary={b}", "Accept-Encoding": "identity"})
        print("watermark:", r.status_code, r.text[:300])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
