"""Remove from media/ the videos and images already published, so the repo does not grow (owner 30/10/2026).

  python tools/media_cleanup.py [--dry-run]

A file under media/ is kept while a queue item that is not done yet (not in the publish logs or missed-log)
points to it; a file whose items are all done is deleted, and so is a file of media/shorts/ that no item points to.
Git keeps the deleted files in the history: this only stops new commits and checkouts from carrying them.
Runs in queue-short-reel.yml every day.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402
from run_slot import QUEUE, done_refs  # noqa: E402

MEDIA = creds.REPO / "media"


def main():
    pending, done = set(), set()
    for ch, qf in QUEUE.items():
        f = creds.QUEUES / qf
        if not f.exists():
            continue
        finished = done_refs(ch)
        for it in json.loads(f.read_text("utf-8")):
            srcs = [it.get("video_url"), *(it.get("images") or [])]
            local = {s for s in srcs if s and not s.startswith("http")}
            if it["ref"] in finished:
                done |= local
            else:
                pending |= local
    gone = []
    for p in sorted(MEDIA.rglob("*")) if MEDIA.exists() else []:
        if not p.is_file() or p.name == "README.md":
            continue
        rel = p.relative_to(creds.REPO).as_posix()
        if rel in pending:
            continue
        if rel in done or rel.startswith("media/shorts/"):
            gone.append(rel)
            if "--dry-run" not in sys.argv:
                p.unlink()
    print(f"media: {len(gone)} published file(s) removed: {', '.join(gone) or 'none'}; {len(pending)} kept for the queues")


if __name__ == "__main__":
    main()
