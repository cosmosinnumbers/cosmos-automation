"""The Short of the day: ONE release per day for every channel (owner 03/11/2026: "voglio che tutto coincida").

YouTube (yt_short_upload), Threads (threads_build) and the Meta queue (queue_short_reel) all call pick(), so a
second build on the same day (manual dispatch, reserve) never splits the channels. Order:
  1. config/day-short.json: {"a1103": "a1103-swift-space-telescope-reentry"} pins the Short of a day by hand;
  2. the release of that day already on YouTube (logs/youtube-publish-log.jsonl): what went out stays the Short;
  3. else the first release of that day by creation time: later builds the same day are spares, never replacements.
From config/short-source.json "clips_from" (owner 03/11/2026: "tutti i video corti devono essere clippate dei video
lunghi", every channel) the Short of the day is the clip release c<MMDD>-* made by tools/day_clip.py; the news
Shorts a<MMDD>-* stay a reserve; b<MMDD>-* is the 15:00 YouTube Short every day (owner 06/11/2026).
tools/short_sync.py checks every evening that the channels agree and opens an issue when they do not.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "config" / "day-short.json"
SOURCE = ROOT / "config" / "short-source.json"
YT_LOG = ROOT / "logs" / "youtube-publish-log.jsonl"


def key(day: datetime, prefix: str = "a") -> str:
    return f"{prefix}{day:%m%d}"


def clips_mode(day: datetime) -> bool:
    """True from clips_from on: the short video of the day is a clip of a long video."""
    try:
        start = json.loads(SOURCE.read_text("utf-8")).get("clips_from", "")
    except (OSError, ValueError):
        return False
    return bool(start) and f"{day:%Y-%m-%d}" >= start


def pins() -> dict:
    try:
        return json.loads(PINS.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def on_youtube() -> list[str]:
    """Refs in upload order."""
    refs = []
    if YT_LOG.exists():
        for line in YT_LOG.read_text("utf-8").splitlines():
            try:
                refs.append(json.loads(line).get("ref", ""))
            except ValueError:
                continue
    return refs


def pick(rels: list[dict], day: datetime, prefix: str = "a") -> dict | None:
    """The release that is the Short of `day` (releases as returned by the GitHub API), or None."""
    if clips_mode(day) and prefix == "a":
        prefix = "c"   # the 21:00 Short is the clip of a long video
    # prefix "b": the 15:00 news Short (Katana motion graphics) goes out every day on YouTube, clips mode or not
    # (owner 06/11/2026: "Perché non l'hai caricato?" about the 15:00 Short)
    k = key(day, prefix)
    cands = [r for r in rels if r["tag_name"].startswith(f"{k}-") and not r.get("draft")]
    if not cands:
        return None
    pinned = pins().get(k)
    if pinned:
        hit = next((r for r in cands if r["tag_name"] == pinned), None)
        if hit:
            return hit
        print(f"  config/day-short.json pins {pinned} for {k}, but there is no such release: rule 2/3 applies")
    by_tag = {r["tag_name"]: r for r in cands}
    hit = next((by_tag[ref] for ref in on_youtube() if ref in by_tag), None)  # the first one uploaded
    return hit or min(cands, key=lambda r: r.get("created_at") or "")
