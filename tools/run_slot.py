"""Publish every queue item due in this slot (GitHub Actions entry point, also runnable on the PC).

  python tools/run_slot.py [--dry-run] [--only meta,threads,x,tiktok] [--ref REF]

Picks items whose "at" (Italian time) is between LATE_MAX_MIN ago and AHEAD_MIN from now, skips those already in
the logs (idempotent), waits for the exact minute, publishes, and commits the logs after every item (in Actions).
Each item gets at most 1 new attempt; failures make the run exit 1 with a clear list (GitHub e-mails the owner).
Channels: META_ENABLED, THREADS_ENABLED, X_ENABLED (default true), TIKTOK_ENABLED (default false until the
TikTok audit is approved and a public test post is verified).
--dry-run: no publishing, no commit; checks queues, media URLs (HTTP 200), pacing and credentials.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402

AHEAD_MIN = int(os.environ.get("AHEAD_MIN", 25))
LATE_MAX_MIN = int(os.environ.get("LATE_MAX_MIN", 120))  # GitHub cron can start late; older items are "missed"
DEFAULTS = {"meta": "true", "threads": "true", "x": "true", "tiktok": "false"}
QUEUE = {"meta": "meta-queue.json", "threads": "threads-queue.json", "x": "x-queue.json", "tiktok": "tiktok-queue.json"}
LOG = {"meta": "meta-publish-log.jsonl", "threads": "threads-publish-log.jsonl", "x": "x-publish-log.jsonl",
       "tiktok": "tiktok-publish-log.jsonl"}
META_KIND = {"ig-carousel": ("ig", "post"), "ig-reel": ("ig", "reel"), "ig-story": ("ig", "story"),
             "fb-story": ("fb", "story")}


def enabled(ch):
    return os.environ.get(f"{ch.upper()}_ENABLED", DEFAULTS[ch]).lower() == "true"


def done_refs(ch):
    ev = creds.events(LOG[ch]) + creds.events("missed-log.jsonl")
    return {e.get("item") if ch == "meta" else e.get("ref") for e in ev} - {None}


def has_creds(ch):
    name = {"meta": "meta", "threads": "threads", "x": "x", "tiktok": "tiktok"}[ch]
    return bool(os.environ.get(f"{name.upper()}_JSON")) or (creds.LOCAL_SECRETS / f"{name}.json").exists()


def run_meta(item, go):
    import meta_api
    act = item["action"]
    if act not in META_KIND:
        sys.exit(f"unknown meta action {act}")
    if not go:
        meta_api.guard(*META_KIND[act], creds.stamp(item["at"]))  # exits with PACING if not allowed at that time
        for u in item.get("images") or [item["video_url"]]:
            creds.check_url(u)
        print(f"{item['ref']}: {act} OK (pacing and media)")
        return
    if act == "ig-carousel":
        meta_api.ig_carousel(item["images"], item["caption"], item["ref"])
    elif act == "ig-reel":
        meta_api.ig_reel(item["video_url"], item["caption"], item["ref"])
    elif act == "ig-story":
        meta_api.ig_story(item["video_url"], item["ref"])
    elif act == "fb-story":
        meta_api.fb_story(item["video_url"], item["ref"])


def run(ch, item, go):
    if ch == "meta":
        return run_meta(item, go)
    mod = __import__({"threads": "threads_api", "x": "x_api", "tiktok": "tiktok_api"}[ch])
    mod.run_item(item, go)


def commit(msg):
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    subprocess.run(["git", "add", "logs"], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return
    subprocess.run(["git", "commit", "-q", "-m", msg], check=True)
    for _ in range(4):
        subprocess.run(["git", "pull", "-q", "--rebase"], check=False)
        if subprocess.run(["git", "push", "-q"]).returncode == 0:
            return
        time.sleep(5)
    sys.exit("could not push the logs after 4 attempts")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "--dry-run" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else list(QUEUE)
    one = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    now = time.time()
    due, missed, problems = [], [], []
    for ch in only:
        qf = creds.QUEUES / QUEUE[ch]
        if not qf.exists():
            continue
        done = done_refs(ch)
        for it in json.loads(qf.read_text("utf-8")):
            at = it.get("at")
            if not at or it["ref"] in done or (one and it["ref"] != one):
                continue
            t = creds.stamp(at)
            if one or now - LATE_MAX_MIN * 60 <= t <= now + AHEAD_MIN * 60:
                due.append((t, ch, it))
            elif now - 86400 < t < now - LATE_MAX_MIN * 60:
                missed.append((ch, it["ref"], at))
    due.sort(key=lambda d: d[0])
    print(f"{'DRY RUN ' if dry else ''}slot {creds.now_local():%Y-%m-%d %H:%M} Europe/Rome: "
          f"{len(due)} due item(s), {len(missed)} missed")
    for ch, ref, at in missed:
        # a missed item is skipped on purpose (never published late): a warning, not a failure of the slot
        print(f"MISSED {ch} {ref} (due {at}): the run started too late, skipped")
        if not dry:
            creds.append("missed-log.jsonl", {"p": ch, "ref": ref, "due": at, "at": int(now)})
    if missed and not dry:
        commit("log: missed items")
    for t, ch, it in due:
        label = f"{ch} {it['ref']} ({it['at']})"
        if not enabled(ch):
            print(f"SKIP {label}: {ch.upper()}_ENABLED is false")
            continue
        if not has_creds(ch):
            problems.append(f"FAILED {label}: credentials for {ch} are not configured")
            continue
        if not dry and t > time.time():
            time.sleep(t - time.time())
        for attempt in (1, 2):
            try:
                run(ch, it, go=not dry)
                break
            except SystemExit as e:
                msg = str(e.code) if e.code not in (None, 0) else ""
                if not msg:
                    break
                # Meta/TikTok: published and logged, failed afterwards -> no retry. Threads/X retry only the
                # missing replies (run_item never re-posts a main post already in the log).
                if not dry and ch in ("meta", "tiktok") and it["ref"] in done_refs(ch):
                    print(f"WARNING {label}: published, then: {msg}")
                    break
                if dry or msg.startswith(("PACING", "BUDGET")):
                    problems.append(f"{'CHECK' if dry else 'FAILED'} {label}: {msg}")
                    break
                if attempt == 2:
                    problems.append(f"FAILED {label} after 2 attempts: {msg}")
                else:
                    print(f"attempt 1 failed for {label}: {msg}; retrying in 60 s")
                    time.sleep(60)
            except Exception as e:  # network errors raised by requests etc.
                if attempt == 2 or dry:
                    problems.append(f"FAILED {label}: {type(e).__name__}: {str(e)[:200]}")
                else:
                    print(f"attempt 1 failed for {label}: {type(e).__name__}; retrying in 60 s")
                    time.sleep(60)
        if not dry:
            commit(f"log: {ch} {it['ref']}")  # whatever was published (even partially) is in the log
    for p in problems:
        print(p)
    if problems:
        sys.exit(f"{len(problems)} problem(s) in this slot, see above.")
    print("slot completed")


if __name__ == "__main__":
    main()
