"""The short video of the day is a clip of a long video (owner 03/11/2026: "tutti i video corti devono essere
clippate dei video lunghi", every channel, from config/short-source.json "clips_from").

  python tools/day_clip.py [--date 2026-11-08] [--dry-run]

Makes the release c<MMDD>-<clip id> of the day: the vertical clip <clip>.mp4 of a release lf-<id> (cut by
long-clips.yml), renamed <tag>.mp4, with upload.md (title "<headline> #shorts", LOOK UP line on top, link to the full
video), short.yaml (title + the narration of the clip, from the long video's .srt) and material-script.yaml (source:
the full video on YouTube). tools/day_short.py picks it for every channel, so youtube-upload (21:00), threads-build
(21:00 post) and queue-short-reel (Reels and Stories) publish the same clip. News Shorts (a<MMDD>-*) are still built
as a reserve but no longer published.
Rules: only long videos already public on YouTube by 20:00 of that day (logs/youtube-publish-log.jsonl, k=long,
publish_at); oldest long video first, clips in name order; a clip is used once (existing c* releases). No clip left:
no release, nothing goes out that day.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402
import day_short  # noqa: E402
import queue_short_reel as qsr  # noqa: E402

DRY = "--dry-run" in sys.argv
CLIP = re.compile(r"^(.+-clip-[a-z0-9]+)\.mp4$")
COSMOS9_UNTIL = qsr.COSMOS9_UNTIL


def longs(cutoff: datetime) -> list[dict]:
    """Long videos public on YouTube by `cutoff`, oldest first: {ref, id}."""
    out = {}
    for e in creds.events("youtube-publish-log.jsonl"):
        if e.get("k") == "long" and e.get("ref", "").startswith("lf-"):
            if int(e.get("publish_at") or e.get("at") or 0) <= cutoff.timestamp():
                out.setdefault(e["ref"], {"ref": e["ref"], "id": e["id"], "when": int(e.get("publish_at") or e["at"])})
    return sorted(out.values(), key=lambda v: v["when"])


def srt_text(srt: str, t0: float, t1: float) -> str:
    words = []
    for b in re.split(r"\n\s*\n", srt.strip()):
        lines = b.splitlines()
        m = re.findall(r"(\d+):(\d+):(\d+)[,.](\d+)", lines[1]) if len(lines) > 2 else []
        if len(m) < 2:
            continue
        a, z = [int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000 for h, mi, s, ms in m[:2]]
        if a >= t0 - 0.2 and z <= t1 + 0.5:
            words.append(" ".join(lines[2:]))
    return " ".join(words)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    day = (datetime.strptime(a[a.index("--date") + 1], "%Y-%m-%d").replace(tzinfo=qsr.TZ) if "--date" in a
           else creds.now_local())
    if not day_short.clips_mode(day):
        print(f"{day:%d/%m}: before clips_from (config/short-source.json): the Short of the day is the news Short.")
        return
    rels = json.loads(qsr.gh("api", f"repos/{qsr.REPO}/releases?per_page=100"))
    k = day_short.key(day, "c")
    have = next((r["tag_name"] for r in rels if r["tag_name"].startswith(f"{k}-")), None)
    if have:
        print(f"{have}: the clip of the day is already out.")
        return
    used = {r["tag_name"].split("-", 1)[1] for r in rels if re.match(r"^c\d{4}-", r["tag_name"])}
    pick = None
    for lv in longs(day.replace(hour=20, minute=0, second=0, microsecond=0)):
        rel = next((r for r in rels if r["tag_name"] == lv["ref"]), None)
        clips = sorted(m.group(1) for x in (rel or {}).get("assets", []) if (m := CLIP.match(x["name"])))
        free = [c for c in clips if c not in used]
        print(f"{lv['ref']}: {len(clips)} clips, {len(free)} unused")
        if free and not pick:
            pick = (lv, rel, free[0])
    if not pick:
        print(f"{day:%d/%m}: no unused clip of a public long video: no short video today.")
        return
    lv, rel, cid = pick
    tag = f"{k}-{cid}"
    long_title = rel["name"].strip()
    clips_yaml = Path(qsr.ROOT, "longform", lv["ref"][3:], "clips.yaml")
    spec = next((c for c in (yaml.safe_load(clips_yaml.read_text("utf-8")) if clips_yaml.exists() else []) or []
                 if c["id"] == cid), None)
    with tempfile.TemporaryDirectory() as d:
        dl = [cid + "-caption.txt", lv["ref"][3:] + ".srt"]
        qsr.gh("release", "download", lv["ref"], "--repo", qsr.REPO, *sum((["-p", n] for n in dl), []), "-D", d)
        headline = (Path(d) / dl[0]).read_text("utf-8").strip().splitlines()[0].strip()
        narration = srt_text((Path(d) / dl[1]).read_text("utf-8"), spec["start"], spec["end"]) if spec else ""
        url = f"https://youtu.be/{lv['id']}"
        code = " · code COSMOS9" if day < COSMOS9_UNTIL else ""
        title = f"{headline[:90]} #shorts"
        desc = (f"📘 LOOK UP stargazing guide: https://cosmosinnumbers.gumroad.com/l/look-up{code}\n\n"
                f"Full video: {long_title} {url}\n\n{narration}\n\n"
                "Clip of the full video: sources and credits are in its description. Synthetic voice; script drafted "
                "with AI assistance and fact-checked.\n#space #astronomy #science #shorts")
        out = Path(d) / "out"
        out.mkdir()
        (out / "upload.md").write_text(f"## Title\n{title}\n\n## Description\n{desc}\n", "utf-8")
        (out / "short.yaml").write_text(yaml.safe_dump({"title": title, "narration": narration or headline,
                                                        "long": lv["ref"], "clip": cid}, allow_unicode=True), "utf-8")
        (out / "material-script.yaml").write_text(yaml.safe_dump(
            {"sources": [{"title": f"Full video: {long_title}", "url": url}]}, allow_unicode=True), "utf-8")
        print(f"{tag}: '{title}' from {lv['ref']} ({url}); narration {len(narration)} chars")
        if DRY:
            print("DRY-RUN: no release.")
            return
        qsr.gh("release", "download", lv["ref"], "--repo", qsr.REPO, "-p", f"{cid}.mp4", "-D", d)
        (Path(d) / f"{cid}.mp4").rename(out / f"{tag}.mp4")
        qsr.gh("release", "create", tag, "--repo", qsr.REPO, "--title", title,
               "--notes", f"Clip del giorno da {long_title} ({url}). Pubblicata da youtube-upload, threads-build e queue-short-reel.",
               *[str(p) for p in sorted(out.iterdir())])
    print(f"released {tag}")


if __name__ == "__main__":
    main()
