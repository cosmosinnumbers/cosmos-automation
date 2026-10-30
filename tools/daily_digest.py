"""Daily "da caricare" issue: what Simone uploads by hand from the phone (YouTube and TikTok have no approved API).

  python tools/daily_digest.py [--dry-run]

Reads today's (Europe/Rome) items and opens ONE GitHub issue labelled "da-caricare" (the GitHub app notifies the
repo watchers and the people mentioned in DIGEST_MENTION), closing the ones of the previous days:
- YouTube: the Short of today's release a<MMDD>-* made by shorts-build (video link, title, description of upload.md).
- TikTok: the items of queues/tiktok-queue.json with today's date (video link and caption), until TikTok approves the API.
Nothing is uploaded or published from here. Needs GH_TOKEN (issues: write) and GITHUB_REPOSITORY.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
ROOT = Path(__file__).resolve().parents[1]
LABEL = "da-caricare"
GUIDE = f"https://github.com/{REPO}/blob/main/docs/guida-caricare-dal-telefono.txt"
DRY = "--dry-run" in sys.argv


def gh(*args, check=True) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"gh {' '.join(args[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def section(md: str, name: str) -> str:
    """Body of '## <name>' in upload.md, without code fences."""
    m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return re.sub(r"^```\w*\s*$", "", m.group(1), flags=re.M).strip() if m else ""


def youtube_part(today: datetime) -> list[str]:
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=15"))
    rel = next((r for r in rels if r["tag_name"].startswith(f"a{today:%m%d}-")), None)
    if not rel:
        return ["## ▶️ YouTube", "Oggi lo Short automatico non è stato creato (controlla Actions → shorts-build). "
                "Niente da caricare su YouTube."]
    mp4 = next((a for a in rel["assets"] if a["name"].endswith(".mp4")), None)
    md = ""
    with tempfile.TemporaryDirectory() as d:
        gh("release", "download", rel["tag_name"], "--repo", REPO, "-p", "upload.md", "-D", d, check=False)
        if (Path(d) / "upload.md").exists():
            md = (Path(d) / "upload.md").read_text("utf-8")
    title = section(md, "Title") or rel["name"]
    out = ["## ▶️ YouTube (Short)",
           f"1. **Scarica il video:** [{mp4['name'] if mp4 else 'video'}]({mp4['browser_download_url'] if mp4 else rel['html_url']})",
           f"2. **Titolo** (tieni premuto per copiare):", "", f"```\n{title}\n```",
           "3. **Descrizione:**", "", f"```\n{section(md, 'Description') or '(vedi upload.md nella release)'}\n```",
           f"4. Fact check e fonti: [release {rel['tag_name']}]({rel['html_url']}) (file factcheck.md). "
           "Leggi il testo prima di pubblicare."]
    studio = section(md, "Studio settings")
    if studio:
        out += ["", "<details><summary>Impostazioni consigliate</summary>", "", studio, "", "</details>"]
    return out


def tiktok_part(today: datetime) -> list[str]:
    q = ROOT / "queues" / "tiktok-queue.json"
    items = [i for i in (json.loads(q.read_text("utf-8")) if q.exists() else [])
             if str(i.get("at", "")).startswith(f"{today:%Y-%m-%d}")]
    if not items:
        return ["## 🎵 TikTok", "Niente in programma oggi."]
    out = ["## 🎵 TikTok"]
    for i in items:
        url = i.get("video_url") or i.get("video") or ""
        if url and not url.startswith("http"):
            url = f"https://github.com/{REPO}/raw/main/{url}"
        out += [f"**{i.get('ref', '')}**, alle {str(i['at'])[11:16]}: [scarica il video]({url})", "",
                "Didascalia:", "", f"```\n{i.get('caption') or i.get('text') or ''}\n```", ""]
    return out


def main():
    today = datetime.now(ZoneInfo("Europe/Rome"))
    body = [f"📱 **Da caricare oggi dal telefono** ({today:%d/%m/%Y}). Guida: [guida-caricare-dal-telefono.txt]({GUIDE})", ""]
    body += youtube_part(today) + [""] + tiktok_part(today)
    body += ["", "Quando hai finito, chiudi questa issue (Close). Instagram, Facebook e Threads escono da soli dalla coda."]
    mention = os.environ.get("DIGEST_MENTION", "").strip()
    if mention:
        body += ["", f"cc {mention}"]
    text = "\n".join(body) + "\n"
    print(text)
    if DRY:
        return
    gh("label", "create", LABEL, "--repo", REPO, "--color", "0E8A16", "--description", "Contenuti da caricare a mano",
       "--force")
    for n in json.loads(gh("issue", "list", "--repo", REPO, "--label", LABEL, "--state", "open", "--json", "number")):
        gh("issue", "close", str(n["number"]), "--repo", REPO, "--comment", "Sostituita dalla lista di oggi.", check=False)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(text)
    print(gh("issue", "create", "--repo", REPO, "--title", f"📱 Da caricare oggi {today:%d/%m}", "--label", LABEL,
             "--body-file", f.name).strip())


if __name__ == "__main__":
    main()
