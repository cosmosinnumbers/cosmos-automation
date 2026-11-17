"""External clock: start the time-critical workflows at their Italian time (17/11/2026).

From 15/11/2026 GitHub started the scheduled runs of this repository 1-10 hours late or skipped them, so the
Threads news (12:00), the quiz (16:00) and the 15:00 Short were missed every day. cron-job.org now starts
clock.yml every 5 minutes (workflow_dispatch is not delayed like schedule); this script starts each job of
config/clock.json once, from its time until window_min later, unless a schedule or dispatch run of that workflow
was already created since then (an on-time GitHub cron run or a previous tick). Standard library only.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Rome")
ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"


def due_jobs(cfg: dict, now: datetime) -> list[tuple[dict, datetime]]:
    """Jobs whose Italian time is in [at, at + window_min] today (now is aware, any zone)."""
    now = now.astimezone(TZ)
    out = []
    for job in cfg["jobs"]:
        h, m = map(int, job["at"].split(":"))
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if t <= now <= t + timedelta(minutes=cfg.get("window_min", 60)):
            out.append((job, t))
    return out


def already_started(runs: list[dict], since: datetime) -> bool:
    """A schedule/dispatch run created at or after `since` (workflow_run chains do not count: they only check)."""
    for r in runs:
        if r.get("event") not in ("schedule", "workflow_dispatch"):
            continue
        created = datetime.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if created >= since:
            return True
    return False


def _api(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                                          "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28",
                                          "User-Agent": "cosmos-automation-clock"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else None


def main():
    dry = "--dry-run" in sys.argv
    repo = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
    ref = os.environ.get("CLOCK_REF", "main")
    cfg = json.loads((ROOT / "config" / "clock.json").read_text("utf-8"))
    now = datetime.now(timezone.utc)
    print(f"tick {now.astimezone(TZ):%Y-%m-%d %H:%M} Europe/Rome")
    for job, t in due_jobs(cfg, now):
        wf = job["workflow"]
        # 2 min of slack: a GitHub cron run that fired on time just before the job's minute counts as started
        since = t.astimezone(timezone.utc) - timedelta(minutes=2)
        created = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        runs = _api("GET", f"/repos/{repo}/actions/workflows/{wf}/runs?created=%3E%3D{created}&per_page=20")
        if already_started(runs.get("workflow_runs", []), since):
            print(f"{wf} {job['at']}: already started, nothing to do")
            continue
        inputs = {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in job.get("inputs", {}).items()}
        if dry:
            print(f"{wf} {job['at']}: WOULD start with {inputs}")
            continue
        _api("POST", f"/repos/{repo}/actions/workflows/{wf}/dispatches", {"ref": ref, "inputs": inputs})
        print(f"{wf} {job['at']}: started with {inputs}")


if __name__ == "__main__":
    main()
