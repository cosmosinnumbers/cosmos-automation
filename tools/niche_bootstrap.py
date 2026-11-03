"""Make a clean copy of the Cosmos engine for a new niche repo (owner 03/11/2026: "copia tutto il motore").

  python tools/niche_bootstrap.py <out_dir> [--niche stickman] [--name "Channel name"]

Copies every tracked file except Cosmos-only data (logs, queues, media, reserve videos, long videos, reports,
analytics, research of other niches, learned weights), then makes the copy SAFE:
- every scheduled trigger is switched off (commented) except research and niche-scan: no publisher can run before
  the new channel has its own accounts and tokens; each one is re-enabled in its own PR (prompt, phase 8);
- repo variables needed later are listed in docs/BOOTSTRAP.md (all publishers start disabled);
- empty logs/ and queues/ with the files the tools expect;
- config/channel.json with the niche, name and status.
Never copies secrets (GitHub never returns them; tools/copy_secrets.py does that inside Actions).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = ("logs/", "queues/", "media/", "reserve/", "longform/", "reports/", "07-analytics/", "research/")
EXCLUDE_FILES = {"GUIDA-TELEFONO.txt", "NOTA-DA-ALTRA-SESSIONE.md", "config/experiments-state.json",
                 "config/viral-weights.json", "config/sky-calendar.json", "config/engage.json",
                 "docs/imposta-segreti-github.ps1", "docs/SKILL-cosmos-daily-content.new.md",
                 ".github/workflows/niche-bootstrap.yml", ".github/workflows/launch9.yml"}
KEEP_UNDER_EXCLUDED = ("research/niches/{niche}.json", "research/{niche}/", "longform/README.md", "reserve/README.md")
KEEP_SCHEDULE = {"research.yml", "niche-scan.yml"}


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l]


def wanted(path: str, niche: str) -> bool:
    keep = tuple(k.format(niche=niche) for k in KEEP_UNDER_EXCLUDED)
    if path.startswith(keep) or path in keep:
        return True
    if path in EXCLUDE_FILES or path.startswith(EXCLUDE_DIRS):
        return False
    return True


def disable_schedule(text: str) -> tuple[str, bool]:
    """Comment out the 'schedule:' block of a workflow (keeps workflow_dispatch and others)."""
    lines, out, i, changed = text.splitlines(), [], 0, False
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(\s*)schedule:\s*$", ln)
        if m:
            ind = len(m.group(1))
            out.append(f"{' ' * ind}# schedule:  (spento dal bootstrap: si riaccende quando il canale è pronto)")
            i += 1
            while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > ind):
                out.append(f"{' ' * ind}#{lines[i][ind:]}" if lines[i].strip() else lines[i])
                i += 1
            changed = True
            continue
        out.append(ln)
        i += 1
    res = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    # a workflow left with no trigger at all is invalid: make sure workflow_dispatch exists
    if changed and "workflow_dispatch" not in res:
        res = res.replace("\non:\n", "\non:\n  workflow_dispatch:\n", 1)
    return res, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--niche", default="stickman")
    ap.add_argument("--name", default="")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists() and any(p.name != ".git" for p in out.iterdir()):
        sys.exit(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    copied, off = 0, []
    for f in tracked():
        if not wanted(f, a.niche):
            continue
        src, dst = ROOT / f, out / f
        if not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if f.startswith(".github/workflows/") and Path(f).name not in KEEP_SCHEDULE:
            txt, changed = disable_schedule(src.read_text("utf-8"))
            dst.write_text(txt, "utf-8")
            if changed:
                off.append(Path(f).name)
        else:
            shutil.copy2(src, dst)
        copied += 1
    for d in ("logs", "queues", "reports", f"research/{a.niche}"):
        (out / d).mkdir(parents=True, exist_ok=True)
        (out / d / ".gitkeep").touch()
    (out / "config" / "viral-weights.json").write_text("{}\n", "utf-8")
    (out / "config" / "experiments-state.json").write_text("{}\n", "utf-8")
    (out / "config" / "channel.json").write_text(json.dumps({
        "niche": a.niche, "name": a.name or "(da decidere)", "language": "en", "created": time.strftime("%Y-%m-%d"),
        "source_repo": "cosmosinnumbers/cosmos-automation", "status": "bootstrap: publishers off",
        "prompt": "docs/PROMPT-nicchia-stickman.md"}, indent=2, ensure_ascii=False) + "\n", "utf-8")
    (out / "README.md").write_text(f"""# {a.name or a.niche} automation (privato)

Copia pulita del motore di Cosmos in Numbers (`cosmosinnumbers/cosmos-automation`, {time.strftime('%d/%m/%Y')}) per la
nicchia **{a.niche}**. Il piano a fasi è in `docs/PROMPT-nicchia-stickman.md`; cosa fa solo Simone in
`docs/AZIONI-SIMONE-stickman.md`.

Stato: **bootstrap**. Tutti i workflow programmati sono spenti tranne la ricerca (`research.yml`, `niche-scan.yml`).
Si riaccendono uno alla volta, con una PR, quando il canale ha account, token e i primi video verificati.
Workflow spenti: {', '.join(sorted(off))}.

Tutto gira su GitHub Actions. Segreti mai nel codice, nei log o in chat.
""", "utf-8")
    (out / "docs" / "BOOTSTRAP.md").write_text(f"""# Bootstrap ({time.strftime('%d/%m/%Y')})

- File copiati: {copied}. Esclusi: dati di Cosmos ({', '.join(EXCLUDE_DIRS)}), stato appreso, calendario del cielo.
- Workflow programmati spenti: {', '.join(sorted(off))}.
- Variabili del repo da impostare quando serve (Settings → Secrets and variables → Actions → Variables), tutte
  **false** finché il canale non è pronto: `YT_ENABLED`, `META_ENABLED`, `THREADS_ENABLED`, `TIKTOK_ENABLED`,
  `X_ENABLED`, `SECOND_SHORT_ENABLED`.
- Testi, link e profili ancora di Cosmos (BRAND, PROFILES, CTA, Gumroad LOOK UP) da rinominare nella fase 4 del prompt.
""", "utf-8")
    print(f"copied {copied} files into {out}; schedules off: {len(off)}")


if __name__ == "__main__":
    main()
