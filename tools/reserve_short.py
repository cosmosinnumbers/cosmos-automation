"""Reserve Short: when every attempt of the day failed, publish the next ready Short of reserve/ as today's release.

  python tools/reserve_short.py [--dry-run]

reserve/<id>/ holds <id>.mp4, upload.md and factcheck.md of a Short already checked by a human (owner decision
30/10/2026: "riserva di Short dati già controllati"), and optionally `expires` (YYYY-MM-DD, last valid day).
The release is "a<MMDD>-reserve-<id>", so queue-short-reel and the phone notes treat it like any daily Short.
The folder is then removed from reserve/ (git keeps it in the history). Needs GH_TOKEN and GITHUB_REPOSITORY.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESERVE = ROOT / "reserve"
DRY = "--dry-run" in sys.argv


def ready():
    for d in sorted(p for p in RESERVE.glob("*") if p.is_dir()):
        mp4, up, fc = d / f"{d.name}.mp4", d / "upload.md", d / "factcheck.md"
        exp = d / "expires"
        if exp.exists() and date.fromisoformat(exp.read_text("utf-8").strip()) < date.today():
            print(f"reserve {d.name}: expired, skipped")
            continue
        if mp4.exists() and up.exists() and fc.exists():
            return d, mp4, up, fc
        print(f"reserve {d.name}: incomplete (needs {d.name}.mp4, upload.md, factcheck.md), skipped")
    return None


def main():
    pick = ready()
    if not pick:
        sys.exit("Reserve empty: no Short today.")
    d, mp4, up, fc = pick
    tag = f"a{datetime.now():%m%d}-reserve-{d.name}"[:60]
    title = next((l.strip() for l in up.read_text("utf-8").split("## Title", 1)[-1].splitlines() if l.strip()), d.name)
    print(f"reserve Short: {tag} | {title}")
    if DRY:
        return
    notes = ROOT / "build" / "reserve-phone.md"
    notes.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "tools" / "phone_notes.py"), str(up), str(fc), str(notes)], check=True)
    rel_mp4 = notes.parent / f"{tag}.mp4"
    shutil.copy(mp4, rel_mp4)
    subprocess.run(["gh", "release", "create", tag, "--title", title, "--notes-file", str(notes),
                    str(rel_mp4), str(up), str(fc)], check=True)
    shutil.rmtree(d)
    print(f"released {tag}; {d.name} removed from reserve/")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"used={d.name}\n")


if __name__ == "__main__":
    main()
