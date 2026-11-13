"""Queue the daily Short on Meta (no Claude, no PC): runs after shorts-build.

  python tools/queue_short_reel.py [--tag a1031-slug] [--dry-run]

Takes the release of shorts-build (default: the Short of the day from tools/day_short.py, the same on every channel), copies its mp4 into
media/shorts/ (plus a 19 s Story cut, <tag>_story.mp4) and appends to queues/meta-queue.json, for publish.yml:
  sr-<tag> ig-reel, fr-<tag> fb-reel (caption with the LOOK UP link: Facebook allows links), si-<tag> ig-story,
  sf-<tag> fb-story (owner 30/10/2026: "Collegare allo Short del giorno Reel FB, Storia IG e Storia FB").
Kinds: env SHORT_META_KINDS (default all four). Pacing: Meta counts 24 h on the real publication time, so each
item's slot is at least 24 h + 2 min after the last one of the same kind (published in logs/meta-publish-log.jsonl
or already queued), between 20:48 and 21:10 Rome time; otherwise the next day. meta_api.guard() checks again at
publish time (warm-up limits until 15/11). A slot more than 2 days away is news that went stale: that kind is not
queued. Published media files are removed by tools/media_cleanup.py. Needs GH_TOKEN and GITHUB_REPOSITORY.

The 15:00 Short (b<MMDD>-*, Katana motion graphics) also goes out as a Facebook Reel at 16:00 (the publish.yml slot after it) from FB15_FROM
(owner 06/11/2026: Facebook from 15/11, when the warm-up ends and FB allows 2 Reels a day 3 h apart; Instagram
keeps its 1 Reel a day, the clip). Those items (ref fr-b...) never move the 20:50 slot of the clip.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import day_short  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
TZ = ZoneInfo("Europe/Rome")
QUEUE, LOG, MEDIA = ROOT / "queues" / "meta-queue.json", ROOT / "logs" / "meta-publish-log.jsonl", ROOT / "media" / "shorts"
COSMOS9_UNTIL = datetime(2026, 12, 1, tzinfo=TZ)
DRY = "--dry-run" in sys.argv


def social_or_main(rel: dict) -> dict | None:
    """The social variant (<tag>_social.mp4, trending sound from assets/social/) when the release has it, else the
    main mp4. YouTube never takes the social file."""
    mp4s = [a for a in rel["assets"] if a["name"].endswith(".mp4")]
    return next((a for a in mp4s if a["name"].endswith("_social.mp4")), None) or next(iter(mp4s), None)


def gh(*a) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(a[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def release(now: datetime) -> dict:
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=30"))
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else None
    # the same Short as YouTube and Threads (tools/day_short.py)
    rel = next((r for r in rels if r["tag_name"] == tag), None) if tag else day_short.pick(rels, now)
    if not rel:
        if tag:
            sys.exit(f"No release {tag}.")
        print(f"No Short release for today ({now:%m%d}) yet: nothing to queue (shorts-build retries at 11:00 and 15:00).")
        sys.exit(0)
    return rel


def stamp(at: str) -> datetime:
    return datetime.strptime(at, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


# action -> (log platform, log kind, ref prefix)
KINDS = {"ig-reel": ("ig", "reel", "sr"), "fb-reel": ("fb", "reel", "fr"), "ig-story": ("ig", "story", "si"),
         "fb-story": ("fb", "story", "sf")}


FB15_FROM = datetime(2026, 11, 15, tzinfo=TZ)


def is_fb15(ref: str) -> bool:
    """The 15:00 Facebook Reel of the news Short: kept out of the 20:50 pacing of the clip."""
    return ref.startswith("fr-b")


def last_of(queue: list, action: str) -> datetime | None:
    """Latest Meta action of this kind, published (real time in the log) or still queued (15:00 FB Reels excluded)."""
    p, k, _ = KINDS[action]
    times = []
    if LOG.exists():
        for line in LOG.read_text("utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("p") == p and e.get("k") == k and not is_fb15(e.get("item", "")):
                times.append(datetime.fromtimestamp(int(e["at"]), TZ))
    times += [stamp(i["at"]) for i in queue if i.get("action") == action and not is_fb15(i.get("ref", ""))]
    return max(times) if times else None


def slot(now: datetime, last: datetime | None) -> datetime:
    day = now.date() if now.hour < 19 else (now + timedelta(days=1)).date()
    while True:
        t = datetime(day.year, day.month, day.day, 20, 48, tzinfo=TZ)
        if last and t < last + timedelta(hours=24, minutes=2):
            t = (last + timedelta(hours=24, minutes=2, seconds=59)).replace(second=0, microsecond=0)
        if t.date() == day and t.hour * 60 + t.minute <= 21 * 60 + 10:
            return t
        day += timedelta(days=1)


def caption(title: str, now: datetime, fb: bool = False) -> str:
    code = " · code COSMOS9" if now < COSMOS9_UNTIL else ""
    import links   # tracked link on Facebook (clickable there); Instagram captions are not clickable: bio
    product = (f"📘 LOOK UP stargazing guide: {links.link(links.LOOK_UP, 'facebook', 'post')}{code}" if fb
               else f"📘 LOOK UP stargazing guide: link in bio{code}")
    return (f"{title.replace(' #shorts', '').strip()}\n\nFull video on YouTube: @CosmosinNumbers"
            f"{'' if fb else ' (link in bio)'}\n{product}\n\nSources in the YouTube description. "
            "Synthetic voice; script drafted with AI assistance and fact-checked.\n#space #astronomy #science")


TT_QUEUE = ROOT / "queues" / "tiktok-queue.json"


def ensure_video(rel: dict, tag: str):
    """media/shorts/<tag>.mp4 from the release (Reels and TikTok upload it from the repo)."""
    video = f"media/shorts/{tag}.mp4"
    mp4 = social_or_main(rel)
    if not mp4:
        sys.exit(f"{tag}: no mp4 in the release.")
    MEDIA.mkdir(parents=True, exist_ok=True)
    if not (ROOT / video).exists():
        with tempfile.TemporaryDirectory() as d:
            gh("release", "download", tag, "--repo", REPO, "-p", mp4["name"], "-D", d)
            (ROOT / video).write_bytes((Path(d) / mp4["name"]).read_bytes())


def tiktok_caption(title: str) -> str:
    """Owner rule 26/10/2026: only "Full video on YouTube", no product, link, code or "link in bio"."""
    return (f"{title.replace(' #shorts', '').replace('#shorts', '').strip()}\n\nFull video on YouTube: @CosmosinNumbers\n\n"
            "Sources in the YouTube description. Synthetic voice; script drafted with AI assistance and fact-checked.\n"
            "#space #astronomy #science")


def queue_tiktok(rel: dict, now: datetime, video: str) -> dict | None:
    """tt-<tag> in queues/tiktok-queue.json at 21:00 (Rome) of the Short's day, only with TIKTOK_ENABLED=true.
    tiktok_api.pacing() keeps max 2 a day, 3 h apart; post_qc checks the caption again at publish time."""
    if os.environ.get("TIKTOK_ENABLED", "false").lower() != "true":
        print("tiktok: TIKTOK_ENABLED is not true, not queued")
        return None
    q = json.loads(TT_QUEUE.read_text("utf-8")) if TT_QUEUE.exists() else []
    ref = f"tt-{rel['tag_name']}"
    if any(i.get("ref") == ref for i in q):
        print(f"tiktok: {ref} already queued")
        return None
    day = now.date() if now.hour * 60 + now.minute < 21 * 60 - 20 else (now + timedelta(days=1)).date()
    item = {"ref": ref, "at": f"{day:%Y-%m-%d} 21:00", "video_url": video, "caption": tiktok_caption(rel["name"])}
    print(json.dumps(item, ensure_ascii=False, indent=1))
    if DRY:
        return None
    q.append(item)
    q.sort(key=lambda i: i["at"])
    TT_QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return item


def queue_fb15(now: datetime) -> None:
    """The 15:00 news Short of today as a Facebook Reel at 16:00 (publish.yml runs at 15:45 for it), from FB15_FROM. meta_api.guard() checks the
    limits again at publish time (FB: 2 Reels in 24 h, 3 h apart)."""
    if now < FB15_FROM or now.hour * 60 + now.minute > 15 * 60 + 30 or "--tag" in sys.argv:
        return
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=30"))
    rel = day_short.pick(rels, now, "b")
    if not rel:
        return
    tag = rel["tag_name"]
    queue = json.loads(QUEUE.read_text("utf-8")) if QUEUE.exists() else []
    ref = f"fr-{tag}"
    if any(i.get("ref") == ref for i in queue):
        print(f"{ref}: already queued")
        return
    item = {"ref": ref, "at": f"{now:%Y-%m-%d} 16:00", "action": "fb-reel", "video_url": f"media/shorts/{tag}.mp4",
            "caption": caption(rel["name"], now, fb=True)}
    print(json.dumps(item, ensure_ascii=False, indent=1))
    if DRY:
        return
    ensure_video(rel, tag)
    queue.append(item)
    queue.sort(key=lambda i: i["at"])
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"queued {ref} {item['at']}")


def main():
    now = datetime.now(TZ)
    queue_fb15(now)
    rel = release(now)
    tag = rel["tag_name"]
    if not tag.startswith("c") and os.environ.get("NEWS_TO_META") == "false" and "--tag" not in sys.argv:
        print(f"{tag}: news Short, not a clip of a long video: Meta takes only clips (owner 03/11/2026).")
        return
    queue = json.loads(QUEUE.read_text("utf-8")) if QUEUE.exists() else []
    kinds = [k for k in os.environ.get("SHORT_META_KINDS", ",".join(KINDS)).split(",") if k in KINDS]
    todo = [k for k in kinds if not any(i.get("ref") == f"{KINDS[k][2]}-{tag}" for i in queue)]
    tt = queue_tiktok(rel, now, f"media/shorts/{tag}.mp4")
    if not todo:
        print(f"{tag}: already queued ({', '.join(kinds)}).")
        if tt:
            ensure_video(rel, tag)
        return
    mp4 = social_or_main(rel)
    if not mp4:
        sys.exit(f"{tag}: no mp4 in the release.")
    video, story = f"media/shorts/{tag}.mp4", f"media/shorts/{tag}_story.mp4"
    new = []
    for k in todo:
        when = slot(now, last_of(queue + new, k))
        item = {"ref": f"{KINDS[k][2]}-{tag}", "at": f"{when:%Y-%m-%d %H:%M}", "action": k,
                "video_url": story if k.endswith("story") else video}
        if k.endswith("reel"):
            item["caption"] = caption(rel["name"], now, fb=k == "fb-reel")
        print(json.dumps(item, ensure_ascii=False, indent=1))
        if (when.date() - now.date()).days > 2:
            print(f"{k}: slot {item['at']} is more than 2 days away: not queued (backlog full).")
            continue
        new.append(item)
    if DRY or not new:
        if tt:
            ensure_video(rel, tag)
        return
    ensure_video(rel, tag)
    if any(i["action"].endswith("story") for i in new) and not (ROOT / story).exists():
        sys.path.insert(0, str(ROOT / "tools"))
        import meta_api
        meta_api.story_cut(str(ROOT / video))  # -> media/shorts/<tag>_story.mp4
    queue += new
    queue.sort(key=lambda i: i["at"])
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"queued {', '.join(i['ref'] + ' ' + i['at'] for i in new)}")


if __name__ == "__main__":
    main()
