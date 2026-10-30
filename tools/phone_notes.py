"""Release notes made for the phone: everything to copy into the YouTube app, then the fact check.

  python tools/phone_notes.py <upload.md> <factcheck.md> <out.md>

The owner uploads the Short from the phone (decision of 30/10/2026): the release page must show the title and the
description ready to copy, without opening other files. TikTok gets only clips of the long videos, not these Shorts.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def section(text, name):
    m = re.search(rf"^## {name}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def main():
    upload, fact, out = (Path(a) for a in sys.argv[1:4])
    up = upload.read_text("utf-8")
    title = section(up, "Title")
    desc = section(up, "Description").strip("`").strip()
    dur = re.search(r"Duration: ([\d.]+)s", up)
    notes = [
        "## 1. Video",
        "Scarica il file .mp4 qui sotto (Assets) e salvalo nella galleria del telefono.",
        "",
        "## 2. Titolo YouTube (copia)",
        "```", title, "```",
        "",
        "## 3. Descrizione YouTube (copia)",
        "```", desc, "```",
        "",
        "## 4. Impostazioni nell'app YouTube",
        "- Pubblico: No, non è destinato ai bambini",
        "- Contenuti alterati o sintetici: No",
        "- Visibilità: Programma per oggi alle 21:00 (se l'app non lo permette: Pubblica alle 21:00)",
        f"- Durata: {dur.group(1)} s" if dur else "",
        "",
        "---",
        "",
        fact.read_text("utf-8").strip(),
    ]
    out.write_text("\n".join(notes) + "\n", "utf-8")


if __name__ == "__main__":
    main()
