"""Evening check that every channel carries the same Short of the day (owner 03/11/2026: "voglio che tutto coincida").

  python tools/short_sync.py [--date 2026-11-03] [--dry-run]

Expected Short: tools/day_short.pick(). Looks at YouTube (logs/youtube-publish-log.jsonl), Threads (21:00 item of
queues/threads-queue.json and logs/threads-publish-log.jsonl) and Meta (sr-/fr-/si-/sf- items in
queues/meta-queue.json and logs/meta-publish-log.jsonl; Meta items may sit on a later day for the anti-ban pacing,
so only the Short is compared, not the date). Any other a<MMDD>-* Short of that day, or a channel without the
Short, is a divergence: one issue per day (label alert), never a fix. Prints refs only, never a secret.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402
import day_short  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
DRY = "--dry-run" in sys.argv
META_KINDS = {"sr": "Reel IG", "fr": "Reel FB", "si": "Storia IG", "sf": "Storia FB"}


def gh(*a) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"gh {' '.join(a[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def jsonl(name: str) -> list[dict]:
    p = ROOT / "logs" / name
    out = []
    for line in (p.read_text("utf-8").splitlines() if p.exists() else []):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def queue(name: str) -> list[dict]:
    p = ROOT / "queues" / name
    return json.loads(p.read_text("utf-8")) if p.exists() else []


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    day = datetime.strptime(a[a.index("--date") + 1], "%Y-%m-%d") if "--date" in a else creds.now_local().replace(tzinfo=None)
    k = day_short.key(day)
    rel = day_short.pick(json.loads(gh("api", f"repos/{REPO}/releases?per_page=30")), day)
    if not rel:
        print(f"{k}: no Short release for {day:%d/%m}: nothing to compare.")
        return
    want = rel["tag_name"]
    of_day = lambda ref: ref.split("-", 1)[1] if ref.startswith(("sr-", "fr-", "si-", "sf-", "th-")) else ref  # noqa: E731
    seen: dict[str, set[str]] = {}

    seen["YouTube"] = {e["ref"] for e in jsonl("youtube-publish-log.jsonl")
                       if e.get("k") == "short" and e.get("ref", "").startswith(f"{k}-")}
    th = [i.get("short") or of_day(i.get("ref", "")) for i in queue("threads-queue.json") if i.get("at") == f"{day:%Y-%m-%d} 21:00"]
    th += [of_day(e.get("ref", "")) for e in jsonl("threads-publish-log.jsonl") if e.get("ref", "").startswith(f"th-{k}-") and e.get("k") != "reply"]
    seen["Threads"] = {t for t in th if t.startswith(f"{k}-")}
    meta_refs = [i.get("ref", "") for i in queue("meta-queue.json")] + [e.get("item", "") for e in jsonl("meta-publish-log.jsonl")]
    for pre, name in META_KINDS.items():
        seen[name] = {of_day(r) for r in meta_refs if r.startswith(f"{pre}-{k}-")}

    problems = []
    for ch, tags in seen.items():
        other = sorted(tags - {want})
        if other:
            problems.append(f"- {ch}: {', '.join(other)} invece di {want}")
        elif not tags:
            problems.append(f"- {ch}: nessun post con {want}")
    print(f"{k}: Short of the day {want}")
    for ch, tags in seen.items():
        print(f"  {ch}: {', '.join(sorted(tags)) or '-'}")
    if not problems:
        print("All channels agree.")
        return
    title = f"Canali non allineati {day:%d/%m/%Y}"
    body = (f"Short del giorno (tools/day_short.py): `{want}`.\n\n" + "\n".join(problems) +
            "\n\nControllo automatico di short-sync: nessuna correzione fatta. Per fissare a mano lo Short di un giorno:"
            " `config/day-short.json`.")
    print(body)
    if DRY:
        return
    if title in gh("issue", "list", "--repo", REPO, "--state", "open", "--search", title, "--json", "title", "--jq", ".[].title"):
        print("Issue already open.")
        return
    subprocess.run(["gh", "label", "create", "alert", "--repo", REPO, "--color", "B60205",
                    "--description", "Automazione fallita"], capture_output=True)  # already there: fine
    gh("issue", "create", "--repo", REPO, "--title", title, "--label", "alert", "--body", body)


if __name__ == "__main__":
    main()
