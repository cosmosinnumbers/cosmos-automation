"""ManyChat-style engagement for Cosmos in Numbers, run by GitHub Actions (engage.yml), no Claude tokens.

  python tools/engage.py run [--dry-run] [--only yt,ig,fb,th,dm]   answer new comments (and DMs, see below)
  python tools/engage.py cta [--dry-run]                           channel comment with LOOK UP under each new public video

Every comment on our own posts (YouTube, Instagram, Facebook Page, Threads) not answered yet gets one reply:
- keyword flows (config/engage.json): SKY -> free chapter, GUIDE -> LOOK UP on Gumroad, VIDEO -> latest long video.
  A keyword counts in short comments (<= keyword_max_words) or when written in capitals ("comment SKY").
- anything else: Gemini reads the comment and either picks one of the flows above, writes a short reply
  (no links, no invented numbers) or skips it (spam, insults, bots).
Links: Facebook and Threads get the link in the public reply; Instagram "link in bio" (links in IG comments are
not clickable and look like spam); YouTube points to the pinned comment (links in replies end up in spam).
DMs (ENGAGE_DM=true, only after Meta App Review grants instagram_manage_messages / pages_messaging with Advanced
Access): Instagram and Facebook keyword comments get a private reply in DM (one per comment, within 7 days) plus a
short public "sent you a DM"; messages in the inbox get the flow or the menu, only inside Meta's 24-hour window.

Idempotent: logs/engage-log.jsonl (one line per handled comment or message, never answered twice; a comment the
owner already answered by hand is skipped). Caps per run and per 24h, short random pauses. Instagram or Facebook
restriction errors create logs/ENGAGE_PAUSE_<IG|FB|TH|YT> and stop that platform until the file is deleted.
No likes, follows, or comments on other people's posts: replies on our own posts only.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402
import meta_api  # noqa: E402

CFG = json.loads((creds.REPO / "config" / "engage.json").read_text("utf-8"))
LOG = "engage-log.jsonl"
CTA_LOG = creds.LOGS / "cta-comments.json"
TH = "https://graph.threads.net/v1.0"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DRY = "--dry-run" in sys.argv
DM_ENABLED = os.environ.get("ENGAGE_DM", "false").lower() == "true"
URL = re.compile(r"https?://\S+|www\.\S+", re.I)
RESTRICTED = re.compile(r'"code":\s*(4|17|32|368|613)\b|temporarily blocked|action is blocked', re.I)
AUTH = re.compile(r'"code":\s*(190|200|10)\b|invalid_grant|OAuthException|unauthorized', re.I)
PROBLEMS: list[str] = []  # make the workflow fail (GitHub e-mail) after the other platforms ran


# ---------- helpers ----------

def safe(fn, *a, **kw):
    """Run an API call that may sys.exit or raise; return (result, error text)."""
    try:
        return fn(*a, **kw), None
    except SystemExit as e:
        return None, str(e)[:400]
    except Exception as e:  # noqa: BLE001 - one comment failing must not stop the run
        return None, f"{type(e).__name__}: {str(e)[:400]}"


def age_days(ts: str) -> float:
    t = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+0000", "+00:00"))
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400


def paused(p: str) -> bool:
    return (creds.LOGS / f"ENGAGE_PAUSE_{p.upper()}").exists()


def pause_platform(p: str, why: str):
    if not DRY:
        (creds.LOGS / f"ENGAGE_PAUSE_{p.upper()}").write_text(f"{datetime.now(creds.TZ):%Y-%m-%d %H:%M} {why}\n", "utf-8")
    PROBLEMS.append(f"{p}: paused after a restriction error ({why[:120]}). Check the account, then delete "
                    f"logs/ENGAGE_PAUSE_{p.upper()}.")


class Book:
    """Log of handled ids + caps per platform."""

    def __init__(self):
        self.ev = creds.events(LOG)
        fails: dict[str, int] = {}
        for e in self.ev:
            if not e.get("ok") and not e.get("skip"):
                fails[e["id"]] = fails.get(e["id"], 0) + 1
        # answered or deliberately skipped = done; a failed attempt is retried once
        self.done = {e["id"] for e in self.ev if e.get("ok") or e.get("skip")} | {i for i, n in fails.items() if n >= 2}
        self.run: dict[str, int] = {}

    def left(self, p: str) -> int:
        per_run, per_day = CFG["caps"][p][:2]
        now = time.time()
        day = sum(1 for e in self.ev if e["p"] == p and e.get("ok") and e["at"] > now - 86400)
        return min(per_run - self.run.get(p, 0), per_day - day)

    def write(self, entry: dict):
        entry = {"at": int(time.time()), **entry}
        if DRY:
            print("  [dry]", json.dumps(entry, ensure_ascii=False)[:300])
            return
        creds.append(LOG, entry)
        self.ev.append(entry)
        self.done.add(entry["id"])

    def sent(self, p: str):
        self.run[p] = self.run.get(p, 0) + 1
        if not DRY:
            time.sleep(random.uniform(*CFG["caps"][p][2:4]))


# ---------- YouTube ----------

_yt = None


def yt():
    global _yt
    if _yt is None:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        raw = os.environ.get("YOUTUBE_TOKEN_JSON")
        info = json.loads(raw) if raw else json.loads((creds.LOCAL_SECRETS / "token.json").read_text("utf-8"))
        _yt = build("youtube", "v3", credentials=Credentials.from_authorized_user_info(info), cache_discovery=False)
    return _yt


_channel: dict = {}


def yt_channel():
    if not _channel:
        ch = yt().channels().list(part="contentDetails", mine=True).execute()["items"][0]
        _channel.update(id=ch["id"], uploads=ch["contentDetails"]["relatedPlaylists"]["uploads"])
    return _channel


def yt_videos(n=25):
    ids = [i["contentDetails"]["videoId"] for i in yt().playlistItems().list(
        part="contentDetails", playlistId=yt_channel()["uploads"], maxResults=n).execute()["items"]]
    if not ids:
        return []
    return yt().videos().list(part="snippet,status,contentDetails", id=",".join(ids)).execute()["items"]


def iso_seconds(d: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    return ((dd * 24 + h) * 60 + mi) * 60 + s


_latest: dict = {}


def latest_long_video():
    """Newest public YouTube video longer than 3 minutes (the 'VIDEO' flow); channel page if unknown."""
    if not _latest:
        _latest.update(title="our latest full video", url=CFG["links"]["channel"])
        vids, err = safe(yt_videos, 50)
        for v in vids or []:
            if v["status"]["privacyStatus"] == "public" and iso_seconds(v["contentDetails"]["duration"]) > 180:
                _latest.update(title=v["snippet"]["title"], url=f"https://youtu.be/{v['id']}")
                break
    return _latest


def fetch_yt(book):
    me, out = yt_channel()["id"], []
    for v in yt_videos():
        if v["status"]["privacyStatus"] != "public":
            continue
        for t in yt().commentThreads().list(part="snippet,replies", videoId=v["id"], maxResults=100,
                                            order="time").execute().get("items", []):
            s = t["snippet"]["topLevelComment"]["snippet"]
            mine = lambda c: c.get("authorChannelId", {}).get("value") == me  # noqa: E731
            if t["id"] in book.done or mine(s) or age_days(s["publishedAt"]) > CFG["max_age_days"]:
                continue
            answered = any(mine(r["snippet"]) for r in t.get("replies", {}).get("comments", []))
            out.append({"p": "yt", "id": t["id"], "text": s.get("textOriginal", ""), "who": s.get("authorDisplayName"),
                        "at": s["publishedAt"], "on": v["snippet"]["title"], "answered": answered})
    return out


def reply_yt(c, text):
    yt().comments().insert(part="snippet", body={"snippet": {"parentId": c["id"], "textOriginal": text}}).execute()


# ---------- Instagram / Facebook ----------

def meta():
    return meta_api.cfg()


def fetch_ig(book):
    m = meta()
    tok, ig = m["page_token"], m["ig_user_id"]
    me = meta_api.call("GET", ig, params={"access_token": tok, "fields": "username"})["username"]
    out = []
    media = meta_api.call("GET", f"{ig}/media", params={"access_token": tok, "limit": 25,
                          "fields": "id,caption,timestamp,comments_count"})["data"]
    for md in media:
        if not md.get("comments_count") or age_days(md["timestamp"]) > 90:
            continue
        cm = meta_api.call("GET", f"{md['id']}/comments", params={"access_token": tok, "limit": 100,
                           "fields": "id,text,username,timestamp,replies{username}"}).get("data", [])
        for x in cm:
            if x["id"] in book.done or x.get("username") == me or age_days(x["timestamp"]) > CFG["max_age_days"]:
                continue
            answered = any(r.get("username") == me for r in x.get("replies", {}).get("data", []))
            out.append({"p": "ig", "id": x["id"], "text": x.get("text", ""), "who": x.get("username"),
                        "at": x["timestamp"], "on": (md.get("caption") or "")[:300], "answered": answered})
    return out


def fetch_fb(book):
    m = meta()
    tok, page = m["page_token"], m["page_id"]
    out = []
    for edge in ("videos", "published_posts"):
        r, err = safe(meta_api.call, "GET", f"{page}/{edge}", params={
            "access_token": tok, "limit": 25, "fields": "id,created_time," + ("description" if edge == "videos" else "message")})
        for o in (r or {}).get("data", []):
            if age_days(o["created_time"]) > 90:
                continue
            cr, err = safe(meta_api.call, "GET", f"{o['id']}/comments", params={
                "access_token": tok, "limit": 100, "filter": "toplevel",
                "fields": "id,message,from,created_time,comments.limit(25){from}"})
            for x in (cr or {}).get("data", []):
                if (x["id"] in book.done or x.get("from", {}).get("id") == page
                        or age_days(x["created_time"]) > CFG["max_age_days"]):
                    continue
                answered = any(rp.get("from", {}).get("id") == page for rp in x.get("comments", {}).get("data", []))
                out.append({"p": "fb", "id": x["id"], "text": x.get("message", ""), "who": x.get("from", {}).get("name", "?"),
                            "at": x["created_time"], "on": (o.get("message") or o.get("description") or "")[:300],
                            "answered": answered})
    return out


def reply_ig(c, text):
    meta_api.call("POST", f"{c['id']}/replies", params={"access_token": meta()["page_token"], "message": text})


def reply_fb(c, text):
    meta_api.call("POST", f"{c['id']}/comments", params={"access_token": meta()["page_token"], "message": text})


def private_reply(c, text):
    """One DM per comment, within 7 days (Meta 'private replies'). Needs Advanced Access, see docs/engage.md."""
    m = meta()
    sender = m["ig_user_id"] if c["p"] == "ig" else m["page_id"]
    meta_api.call("POST", f"{sender}/messages", params={"access_token": m["page_token"]},
                  json={"recipient": {"comment_id": c["id"]}, "message": {"text": text}})


# ---------- Threads ----------

def th_cfg():
    return creds.load("threads")


def th_get(path, **params):
    r = requests.get(f"{TH}/{path}", params={**params, "access_token": th_cfg()["token"]}, timeout=60)
    j = r.json()
    if r.status_code != 200 or "error" in j:
        raise SystemExit(f"Threads API {r.status_code}: {j.get('error', j)}")
    return j


def fetch_th(book):
    me, out = th_cfg()["user_id"], []
    for post in th_get(f"{me}/threads", fields="id,text,timestamp", limit=25).get("data", []):
        if post.get("timestamp") and age_days(post["timestamp"]) > 90:
            continue
        for x in th_get(f"{post['id']}/replies", fields="id,text,username,timestamp,is_reply_owned_by_me,has_replies"
                        ).get("data", []):
            if x["id"] in book.done or x.get("is_reply_owned_by_me") or not x.get("timestamp") \
                    or age_days(x["timestamp"]) > CFG["max_age_days"]:
                continue
            answered = bool(x.get("has_replies")) and any(
                r.get("is_reply_owned_by_me") for r in th_get(f"{x['id']}/replies", fields="id,is_reply_owned_by_me"
                                                               ).get("data", []))
            out.append({"p": "th", "id": x["id"], "text": x.get("text") or "", "who": x.get("username"),
                        "at": x["timestamp"], "on": (post.get("text") or "")[:300], "answered": answered})
    return out


def reply_th(c, text):
    import threads_api  # same publisher as the queue: logged as a reply, not counted by the 3-posts-a-day pacing
    threads_api.publish(threads_api.build(text[:500], reply_to=c["id"]), f"engage-{c['id']}")


# ---------- deciding ----------

def keyword_flow(text: str):
    low = text.lower()
    words = re.findall(r"[a-z0-9']+", low)
    for flow, keys in CFG["keywords"].items():
        for k in keys:
            if re.search(rf"\b{re.escape(k)}\b", low) and (
                    len(words) <= CFG["keyword_max_words"] or re.search(rf"\b{re.escape(k.upper())}\b", text)):
                return flow
    return None


AI_PROMPT = """You answer comments for a social media account. {channel}
The comment was left under our post: "{on}"
Comment by {who}: "{text}"

Decide ONE intent:
- "free": they want the free chapter / free sample / something free to start stargazing
- "guide": they ask how to learn stargazing, what to read, where to buy, the price, a book or guide
- "video": they ask for the full video, the source video, or where to watch more
- "reply": any other genuine comment or question worth a short answer
- "skip": spam, bots, self-promotion, insults, provocations, politics, or nothing to say
For "reply", write the reply in English, max {max_chars} characters, warm and specific to what they said.
Rules for the reply: no links, no hashtags, no prices, never invent numbers or facts; state a fact only if it is
well established and you are certain (otherwise thank them and invite them to watch the full video); never claim to
be a human; at most one emoji.
Answer with JSON only: {{"intent": "...", "reply": "..."}}"""


def ai_config():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        f = creds.LOCAL_SECRETS / "gemini.json"
        if not f.exists():
            return None
        j = json.loads(f.read_text("utf-8"))
        return {"api_key": j["api_key"], "model": j.get("model", "gemini-3.8-flash")}
    return {"api_key": key, "model": os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")}


def ai_decide(c):
    cfg = ai_config()
    if not (cfg and CFG["ai"]["enabled"]):
        return None
    body = {"contents": [{"parts": [{"text": AI_PROMPT.format(
        channel=CFG["ai"]["channel"], on=c["on"][:300].replace('"', "'"), who=c["who"] or "someone",
        text=c["text"][:800].replace('"', "'"), max_chars=CFG["ai"]["max_chars"])}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.6}}
    for model in (cfg["model"], cfg["model"], "gemini-3.6-flash"):
        try:
            r = requests.post(GEMINI.format(model=model), params={"key": cfg["api_key"]}, json=body, timeout=90)
        except requests.RequestException:
            continue
        if r.status_code in (429, 500, 503):
            time.sleep(10)
            continue
        if r.status_code != 200:
            return None
        try:
            txt = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
            j = json.loads(txt)
        except (KeyError, IndexError, ValueError):
            return None
        intent = j.get("intent") if j.get("intent") in ("free", "guide", "video", "reply", "skip") else "skip"
        reply = URL.sub("", j.get("reply") or "").strip()[:CFG["ai"]["max_chars"]]
        if intent == "reply" and not reply:
            intent = "skip"
        return {"intent": intent, "reply": reply}
    return None  # Gemini down: the comment stays for the next run


def fill(flow: str, p: str) -> dict:
    code = CFG["code_line"] if date.today() <= date.fromisoformat(CFG["code_until"]) else ""
    vals = {"code_line": code, "video_title": "", "video_url": ""}
    if flow == "free":
        vals["link"] = CFG["links"]["free_chapter"].format(src=f"{p}_auto")
    elif flow == "guide":
        vals["link"] = CFG["links"]["guide"]
    else:
        v = latest_long_video()
        vals.update(link=v["url"], video_title=v["title"], video_url=v["url"])
    return vals


def text_for(flow: str, kind: str, p: str) -> str:
    return re.sub(r"[ \t]+\n|[ \t]{2,}", lambda m: "\n" if "\n" in m.group() else " ",
                  CFG["texts"][flow][kind].format(**fill(flow, p))).strip()


REPLY = {"yt": reply_yt, "ig": reply_ig, "fb": reply_fb, "th": reply_th}


def handle(book, c):
    p = c["p"]
    if c["answered"]:  # the owner (or an older task) already answered by hand
        book.write({"p": p, "id": c["id"], "ok": False, "skip": "already answered"})
        return
    flow, ai = keyword_flow(c["text"]), None
    if not flow:
        ai = ai_decide(c)
        if ai is None:
            print(f"  {p} {c['id']}: no keyword and no AI answer, left for the next run")
            return
        flow = ai["intent"] if ai["intent"] in ("free", "guide", "video") else None
        if ai["intent"] == "skip":
            book.write({"p": p, "id": c["id"], "ok": False, "skip": "ai: skip", "text": c["text"][:120]})
            return
    steps = []  # (callable, text, label)
    if flow and p in ("ig", "fb") and DM_ENABLED and age_days(c["at"]) <= CFG["dm_max_age_days"]:
        steps = [(private_reply, text_for(flow, "dm", p), "dm"), (REPLY[p], text_for(flow, "public_dm_sent", p), "public")]
    elif flow:
        kind = "youtube" if p == "yt" else "public_bio" if p == "ig" else "public_link"
        steps = [(REPLY[p], text_for(flow, kind, p), "public")]
    else:
        steps = [(REPLY[p], ai["reply"], "public")]
    print(f"  {p} @{c['who']}: {c['text'][:80]!r} -> {flow or 'ai reply'}")
    if DRY:
        for _, t, label in steps:
            print(f"    [dry] {label}: {t[:200]!r}")
        book.sent(p)
        return
    errs, dm_ok = [], False
    if steps[0][2] == "dm":
        _, err = safe(private_reply, c, steps[0][1])
        if err:  # DM refused (no Advanced Access, window closed...): public reply with the link instead
            errs.append(f"dm: {err}")
            steps = [(REPLY[p], text_for(flow, "public_bio" if p == "ig" else "public_link", p), "public-fallback")]
        else:
            dm_ok, steps = True, steps[1:]
    for fn, t, label in steps:
        _, err = safe(fn, c, t)
        if err:
            errs.append(f"{label}: {err}")
    ok = dm_ok or not any(not e.startswith("dm:") for e in errs)
    book.write({"p": p, "id": c["id"], "ok": ok, "flow": flow or "ai", "who": c["who"], "comment": c["text"][:200],
                "reply": steps[-1][1][:300] if steps else "", **({"err": " | ".join(errs)[:500]} if errs else {})})
    print("    ", "OK" if ok else "FAILED", " | ".join(errs)[:300])
    for e in errs:
        if RESTRICTED.search(e):
            pause_platform(p, e)
        elif AUTH.search(e):
            PROBLEMS.append(f"{p}: token or permission error: {e[:200]}")
    book.sent(p)


# ---------- DM inbox (only with ENGAGE_DM=true) ----------

def dm_inbox(book):
    m = meta()
    tok, page, ig = m["page_token"], m["page_id"], m["ig_user_id"]
    for platform, sender in (("instagram", ig), ("messenger", page)):
        convs, err = safe(meta_api.call, "GET", f"{page}/conversations", params={
            "access_token": tok, "platform": platform, "limit": 25,
            "fields": "updated_time,messages.limit(1){id,message,from,created_time}"})
        if err:
            PROBLEMS.append(f"dm {platform}: {err[:200]}")
            continue
        for cv in (convs or {}).get("data", []):
            if book.left("dm") <= 0:
                return
            msgs = cv.get("messages", {}).get("data", [])
            if not msgs:
                continue
            last = msgs[0]
            who = last.get("from", {})
            if who.get("id") in (page, ig) or last["id"] in book.done or age_days(last["created_time"]) > 0.95:
                continue  # we spoke last, already handled, or outside Meta's 24-hour window
            c = {"p": "dm", "id": last["id"], "text": last.get("message", ""), "who": who.get("username") or who.get("name"),
                 "at": last["created_time"], "on": "a direct message", "answered": False}
            flow = keyword_flow(c["text"])
            ai = None if flow else ai_decide(c)
            if ai and ai["intent"] in ("free", "guide", "video"):
                flow = ai["intent"]
            if ai and ai["intent"] == "skip":
                book.write({"p": "dm", "id": c["id"], "ok": False, "skip": "ai: skip"})
                continue
            text = text_for(flow, "dm", platform[:2]) if flow else (
                (ai["reply"] + "\n\n" if ai and ai["reply"] else "") + CFG["texts"]["dm_menu"])
            print(f"  dm {platform} {c['who']}: {c['text'][:80]!r} -> {flow or 'menu'}")
            if DRY:
                print(f"    [dry] {text[:200]!r}")
                book.sent("dm")
                continue
            body = {"recipient": {"id": who["id"]}, "message": {"text": text}}
            if platform == "messenger":
                body["messaging_type"] = "RESPONSE"
            _, err = safe(meta_api.call, "POST", f"{sender}/messages", params={"access_token": tok}, json=body)
            book.write({"p": "dm", "id": c["id"], "ok": err is None, "flow": flow or "menu", "who": c["who"],
                        "comment": c["text"][:200], "reply": text[:300], **({"err": err} if err else {})})
            if err and RESTRICTED.search(err):
                pause_platform("dm", err)
                return
            book.sent("dm")


# ---------- commands ----------

FETCH = {"yt": fetch_yt, "ig": fetch_ig, "fb": fetch_fb, "th": fetch_th}


def cmd_run(only):
    book = Book()
    for p, fetch in FETCH.items():
        if only and p not in only:
            continue
        if paused(p):
            print(p, f"paused (delete logs/ENGAGE_PAUSE_{p.upper()} to resume)")
            continue
        found, err = safe(fetch, book)
        if err:
            print(p, "skipped:", err[:300])
            PROBLEMS.append(f"{p}: could not read comments: {err[:200]}")
            continue
        found.sort(key=lambda c: c["at"])  # oldest first
        print(p, len(found), "new comments")
        for c in found:
            if book.left(p) <= 0 or paused(p):
                print(p, "cap reached for this run / 24h")
                break
            handle(book, c)
    if DM_ENABLED and (not only or "dm" in only) and not paused("dm"):
        _, err = safe(dm_inbox, book)
        if err:
            PROBLEMS.append(f"dm: {err[:200]}")
    print("replies this run:", book.run or 0)


CTA = ("📘 LOOK UP, our beginner's stargazing guide by the numbers (no telescope needed): {guide}\n{code_line}\n"
       "🔭 Want a taste first? Comment SKY and we'll send you the free chapter.")
CTA_MARKS = ("gumroad.com/l/look-up", "look-up.html")


def cmd_cta():
    """One channel comment with the LOOK UP link under every public video that has none (pinning stays manual)."""
    posted = json.loads(CTA_LOG.read_text("utf-8")) if CTA_LOG.exists() else {}
    me, n = yt_channel()["id"], 0
    code = CFG["code_line"] if date.today() <= date.fromisoformat(CFG["code_until"]) else ""
    text = CTA.format(guide=CFG["links"]["guide"], code_line=code).replace("\n\n", "\n")
    for v in yt_videos():
        if v["status"]["privacyStatus"] != "public" or v["id"] in posted:
            continue
        threads = yt().commentThreads().list(part="snippet", videoId=v["id"], maxResults=100).execute().get("items", [])
        if any(t["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {}).get("value") == me
               and any(k in t["snippet"]["topLevelComment"]["snippet"]["textOriginal"] for k in CTA_MARKS)
               for t in threads):
            posted[v["id"]] = "already had a channel CTA"
            continue
        if n >= 5:
            break
        print("CTA ->", v["id"], v["snippet"]["title"][:60])
        n += 1
        if DRY:
            continue
        r = yt().commentThreads().insert(part="snippet", body={"snippet": {"videoId": v["id"], "topLevelComment": {
            "snippet": {"textOriginal": text}}}}).execute()
        posted[v["id"]] = f"{datetime.now(creds.TZ):%Y-%m-%d} {r['id']} (pin it in Studio)"
        time.sleep(3)
    if not DRY:
        creds.LOGS.mkdir(exist_ok=True)
        CTA_LOG.write_text(json.dumps(posted, indent=1, ensure_ascii=False), "utf-8")
    print("CTA comments posted:", n)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = [x for x in sys.argv[1:] if x != "--dry-run"]
    if not a or a[0] not in ("run", "cta"):
        sys.exit(__doc__)
    only = set(a[a.index("--only") + 1].split(",")) if "--only" in a else set()
    if a[0] == "run":
        cmd_run(only)
    else:
        _, err = safe(cmd_cta)
        if err:
            PROBLEMS.append(f"cta: {err[:300]}")
    if PROBLEMS:
        print("\nPROBLEMS:\n- " + "\n- ".join(PROBLEMS))
        sys.exit(1)


if __name__ == "__main__":
    main()
