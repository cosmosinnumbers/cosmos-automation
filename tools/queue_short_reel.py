"""Queue the daily Short as an Instagram Reel (no Claude, no PC): runs after shorts-build.

  python tools/queue_short_reel.py [--tag a1031-slug] [--dry-run]

Takes the release of shorts-build (default: the newest a<MMDD>-* of today, Europe/Rome), copies its mp4 into
media/shorts/ and appends an `ig-reel` item to queues/meta-queue.json. publish.yml publishes it at the minute.
Pacing: Instagram counts 24 h between Reels on the real publication time, so the slot is at least 24 h + 2 min after
the last Reel (published in logs/meta-publish-log.jsonl or already queued), between 20:48 and 21:10 Rome time;
otherwise the next day. A Short whose slot would be more than 2 days away is news that went stale: not queued. Old media/shorts files (published, >7 days) are deleted. Needs GH_TOKEN and GITHUB_REPOSITORY.
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

ROOT = Path(__file__).resolve().parents[1]
REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
TZ = ZoneInfo("Europe/Rome")
QUEUE, LOG, MEDIA = ROOT / "queues" / "meta-queue.json", ROOT / "logs" / "meta-publish-log.jsonl", ROOT / "media" / "shorts"
LAUNCH9_UNTIL = datetime(2026, 12, 1, tzinfo=TZ)
DRY = "--dry-run" in sys.argv


def gh(*a) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(a[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def release(now: datetime) -> dict:
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=15"))
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else None
    rel = next((r for r in rels if (r["tag_name"] == tag if tag else r["tag_name"].startswith(f"a{now:%m%d}-"))), None)
    if not rel:
        sys.exit(f"No Short release for today ({now:%m%d}): nothing to queue.")
    return rel


def stamp(at: str) -> datetime:
    return datetime.strptime(at, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


def last_reel(queue: list) -> datetime | None:
    """Latest Instagram Reel, published (real time in the log) or still queued."""
    times = []
    if LOG.exists():
        for line in LOG.read_text("utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("p") == "ig" and e.get("k") == "reel":
                times.append(datetime.fromtimestamp(int(e["at"]), TZ))
    times += [stamp(i["at"]) for i in queue if i.get("action") == "ig-reel"]
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


def caption(title: str, now: datetime) -> str:
    code = " · code LAUNCH9" if now < LAUNCH9_UNTIL else ""
    return (f"{title.replace(' #shorts', '').strip()}\n\nFull video on YouTube: @CosmosinNumbers (link in bio)\n"
            f"📘 LOOK UP stargazing guide: link in bio{code}\n\nSources in the YouTube description. "
            "Synthetic voice; script drafted with AI assistance and fact-checked.\n#space #astronomy #science")


def main():
    now = datetime.now(TZ)
    rel = release(now)
    ref = f"sr-{rel['tag_name']}"
    queue = json.loads(QUEUE.read_text("utf-8")) if QUEUE.exists() else []
    if any(i.get("ref") == ref for i in queue):
        print(f"{ref} is already queued.")
        return
    mp4 = next((a for a in rel["assets"] if a["name"].endswith(".mp4")), None)
    if not mp4:
        sys.exit(f"{rel['tag_name']}: no mp4 in the release.")
    when = slot(now, last_reel(queue))
    item = {"ref": ref, "at": f"{when:%Y-%m-%d %H:%M}", "action": "ig-reel",
            "video_url": f"media/shorts/{rel['tag_name']}.mp4", "caption": caption(rel["name"], now)}
    print(json.dumps(item, ensure_ascii=False, indent=1))
    if (when.date() - now.date()).days > 2:
        print(f"Slot {item['at']} is more than 2 days away: Short not queued (the Reels backlog is full).")
        return
    if DRY:
        return
    MEDIA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        gh("release", "download", rel["tag_name"], "--repo", REPO, "-p", mp4["name"], "-D", d)
        (MEDIA / f"{rel['tag_name']}.mp4").write_bytes((Path(d) / mp4["name"]).read_bytes())
    queue.append(item)
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=1) + "\n", "utf-8")
    cutoff = now - timedelta(days=7)
    for f in MEDIA.glob("*.mp4"):
        if datetime.fromtimestamp(f.stat().st_mtime, TZ) < cutoff and f.stem != rel["tag_name"]:
            f.unlink()
    print(f"queued {ref} at {item['at']}")


if __name__ == "__main__":
    main()
