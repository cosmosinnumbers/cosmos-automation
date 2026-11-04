"""Daily guard: today's posts are there, or they are made now (owner 04/11/2026: "voglio che il sistema si autorisolva
senza scrivere a Claude"). On 4/11 threads-build failed all day and Threads posted nothing: nobody noticed until night.

  python tools/day_guard.py [--date 2026-11-05] [--dry-run]     the check of 11:30 and 17:30 (day-guard.yml)
  python tools/day_guard.py --close-only [--dry-run]            only close the issues that are solved

Every step is idempotent (the generators skip what is queued, the publishers skip what is in their logs), so the
guard never makes a double post:
  1. clip of the day: no release c<MMDD>-* yet -> tools/day_clip.py (with its reserve clip);
  2. Meta: tools/queue_short_reel.py (queues the clip of the day if it is not queued);
  3. Threads: a slot of today (news 12:00, quiz 16:00 or 17:55, video 21:00) with no item -> tools/threads_build.py
     --only <those kinds>; a slot already more than LATE_MAX_MIN in the past is left as missed (never late spam);
  4. late items: a queue item of today due in the last LATE_MAX_MIN, not in the logs, whose next post of the same
     channel is still 3 h away (Threads pacing) -> output "late" for day-guard.yml, which starts publish.yml --ref;
  5. tomorrow (17:30 run): the clip of tomorrow exists or day_clip can make it (dry run); else long-clips renders the
     clips of clips.yaml not in the release yet; if still nothing, one issue tonight instead of a silent day;
  6. issues: "Autofix: <workflow> non riparato" closed when the workflow's next automatic run succeeded,
     "Canali non allineati <day>" and "Controllo giornaliero <day>" closed when a later day is clean.
An issue is opened ("Controllo giornaliero <day>") only for what is still missing after these steps.
Needs GH_TOKEN; PAGES_TOKEN and NASA_API_KEY for threads_build. Prints refs only, never a secret.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402
import day_short  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
DRY = "--dry-run" in sys.argv
LATE_MAX_MIN = int(os.environ.get("LATE_MAX_MIN", 120))  # same window as tools/run_slot.py
GAP_MIN = {"threads": 3 * 60 + 5, "x": 3 * 60 + 5}  # posts of the same channel 3 h apart (threads_api / x_api guard)
SLOTS = {"news": "12:00", "quiz": "16:00", "video": "21:00"}  # threads_build.SLOTS, quiz 17:55 Wed-Fri
QUIZ_LATE = {2: "17:55", 3: "17:55", 4: "17:55"}
QUEUES = {"meta": "meta-queue.json", "threads": "threads-queue.json", "x": "x-queue.json", "tiktok": "tiktok-queue.json"}
LOGS = {"threads": "threads-publish-log.jsonl"}
TITLE = "Controllo giornaliero {:%d/%m/%Y}"


def gh(*a, check=True) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode and check:
        raise RuntimeError(f"gh {' '.join(a[:3])} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def tool(name: str, *args) -> tuple[int, str]:
    """Run tools/<name>.py (dry run passed on); (exit code, output). Its output is shown in the log."""
    cmd = [sys.executable, str(ROOT / "tools" / f"{name}.py"), *args] + (["--dry-run"] if DRY else [])
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    out = (r.stdout + r.stderr).strip()
    print(f"$ {name} {' '.join(args)}{' --dry-run' if DRY else ''} -> exit {r.returncode}")
    for line in out.splitlines()[-25:]:
        print(f"  {line}")
    return r.returncode, out


def queue(ch: str) -> list[dict]:
    p = creds.QUEUES / QUEUES[ch]
    return json.loads(p.read_text("utf-8")) if p.exists() else []


def done_refs(ch: str) -> set[str]:
    """Refs already out, given up (missed) or blocked by QC: the same rule as the publisher."""
    import run_slot
    return run_slot.done_refs(ch)


def slot_at(day: datetime, kind: str) -> str:
    return QUIZ_LATE[day.weekday()] if kind == "quiz" and day.weekday() in QUIZ_LATE else SLOTS[kind]


def output(**kv):
    out = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if out:
            with open(out, "a", encoding="utf-8") as f:
                f.write(f"{k}={v}\n")


# ---------------------------------------------------------------- today
def clip_of_day(day: datetime, rels: list[dict]) -> str | None:
    k = day_short.key(day, "c")
    return next((r["tag_name"] for r in rels if r["tag_name"].startswith(f"{k}-")), None)


def ensure_clip(day: datetime, rels: list[dict], missing: list[str]) -> list[dict]:
    if not day_short.clips_mode(day) or clip_of_day(day, rels):
        return rels
    code, out = tool("day_clip", "--date", f"{day:%Y-%m-%d}")
    if DRY:
        return rels
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=100"))
    if not clip_of_day(day, rels):
        missing.append(f"- clip del giorno: nessuna release {day_short.key(day, 'c')}-* (day_clip: "
                       f"{out.splitlines()[-1] if out else code})")
    return rels


def ensure_threads(day: datetime, now: datetime, missing: list[str]):
    q = queue("threads")
    have = {i["at"] for i in q}
    out_today = {e.get("ref", "") for e in creds.events(LOGS["threads"])
                 if e.get("k") != "reply" and creds.day(int(e.get("at", 0))) == f"{day:%Y-%m-%d}"}
    todo, late = [], []
    for kind in SLOTS:
        at = f"{day:%Y-%m-%d} {slot_at(day, kind)}"
        if at in have:
            continue
        if any(r.startswith(f"th-{kind}-") or (kind == "video" and re.match(r"^th-[abcr]\d{4}-", r)) for r in out_today):
            continue  # already out today (an item of another time, e.g. a replacement)
        due = datetime.strptime(at, "%Y-%m-%d %H:%M").replace(tzinfo=creds.TZ)
        if due < now - timedelta(minutes=LATE_MAX_MIN):
            late.append(f"{kind} {at}")
            continue
        todo.append(kind)
    for x in late:
        print(f"threads: {x} is more than {LATE_MAX_MIN} min in the past: left as missed (no late post)")
        missing.append(f"- Threads {x.split()[0]} delle {x[-5:]}: non uscito e ormai fuori orario (saltato, nessun doppione)")
    if not todo:
        print("threads: nothing to make")
        return
    tool("threads_build", "--date", f"{day:%Y-%m-%d}", "--only", ",".join(todo))
    if DRY:
        return
    have = {i["at"] for i in queue("threads")}
    for kind in todo:
        at = f"{day:%Y-%m-%d} {slot_at(day, kind)}"
        if at not in have:
            missing.append(f"- Threads {kind} delle {at[-5:]}: threads_build non ha prodotto il post")


def late_items(now: datetime) -> list[str]:
    """'<channel>:<ref>' of the items of today due in the last LATE_MAX_MIN and not out yet, if the channel's next
    item is far enough (pacing): publish.yml --ref publishes them now."""
    out = []
    for ch in ("threads", "meta", "x"):
        done = done_refs(ch)
        q = sorted(queue(ch), key=lambda i: i.get("at", ""))
        for n, it in enumerate(q):
            at = it.get("at")
            if not at or it["ref"] in done:
                continue
            due = datetime.strptime(at, "%Y-%m-%d %H:%M").replace(tzinfo=creds.TZ)
            if not (now - timedelta(minutes=LATE_MAX_MIN) <= due <= now - timedelta(minutes=10)):
                continue
            nxt = next((datetime.strptime(j["at"], "%Y-%m-%d %H:%M").replace(tzinfo=creds.TZ) for j in q[n + 1:]
                        if j.get("at") and j["ref"] not in done and j["at"] > at), None)
            gap = GAP_MIN.get(ch, 0)
            if gap and nxt and nxt - now < timedelta(minutes=gap + 15):
                print(f"{ch} {it['ref']} ({at}) not published: the next post at {nxt:%H:%M} is less than 3 h away")
                continue
            print(f"{ch} {it['ref']} ({at}) is late and not out: publish.yml --ref {it['ref']}")
            out.append(f"{ch}:{it['ref']}")
    return out


# ---------------------------------------------------------------- tomorrow
def check_tomorrow(day: datetime, rels: list[dict], missing: list[str]):
    t = day + timedelta(days=1)
    if not day_short.clips_mode(t) or clip_of_day(t, rels):
        print(f"tomorrow {t:%d/%m}: {clip_of_day(t, rels) or 'not in clips mode'}")
        return
    global DRY
    dry, DRY = DRY, True  # only see what 06:50 will pick: the release itself is made tomorrow
    code, out = tool("day_clip", "--date", f"{t:%Y-%m-%d}")
    DRY = dry
    if re.search(r"^c\d{4}-\S+: '", out, re.M):
        print(f"tomorrow {t:%d/%m}: the clip of the day is ready to be made")
        return
    unrendered = []
    import yaml
    for d in sorted((ROOT / "longform").glob("*/clips.yaml")):
        rel = next((r for r in rels if r["tag_name"] == f"lf-{d.parent.name}"), None)
        names = {x["name"] for x in (rel or {}).get("assets", [])}
        ids = [c["id"] for c in yaml.safe_load(d.read_text("utf-8")) or []]
        if rel and any(f"{d.parent.name.split('-')[0]}-{c}.mp4" not in names and f"{c}.mp4" not in names for c in ids):
            unrendered.append(d.parent.name)
    for lf in unrendered:
        print(f"tomorrow: clips of {lf} not rendered yet -> long-clips.yml id={lf}")
        if not DRY:
            gh("workflow", "run", "long-clips.yml", "--repo", REPO, "-f", f"id={lf}", "-f", "dry_run=false", check=False)
    if not unrendered:
        missing.append(f"- domani {t:%d/%m}: nessuna clip disponibile (né nuova né di riserva, config/clip-reserve.json): "
                       "serve un video lungo pubblico con clips.yaml")


# ---------------------------------------------------------------- issues
def open_issues() -> list[dict]:
    try:
        return json.loads(gh("issue", "list", "--repo", REPO, "--state", "open", "--limit", "100",
                             "--json", "number,title,updatedAt,createdAt"))
    except RuntimeError as e:
        print(e)
        return []


def close(num: int, why: str, dry: bool):
    print(f"close #{num}: {why}")
    if not dry:
        gh("issue", "close", str(num), "--repo", REPO, "--comment", f"Risolto da solo: {why}\n\n_Chiusa da "
           "tools/day_guard.py._", check=False)


def last_auto_run(name: str) -> dict | None:
    try:
        wfs = json.loads(gh("api", f"repos/{REPO}/actions/workflows?per_page=100"))["workflows"]
        wid = next(w["id"] for w in wfs if w["name"] == name)
        runs = json.loads(gh("api", f"repos/{REPO}/actions/workflows/{wid}/runs?status=completed&per_page=20"))
    except (RuntimeError, StopIteration, KeyError, ValueError):
        return None
    auto = [r for r in runs.get("workflow_runs", []) if r.get("event") in ("schedule", "workflow_run")
            and r.get("conclusion") in ("success", "failure")]
    return auto[0] if auto else None


def clean_day(day: datetime) -> bool:
    """A past day with the Short of the day on every channel (tools/short_sync.check)."""
    import short_sync
    try:
        want, _, problems = short_sync.check(day)
    except SystemExit:
        return False
    return bool(want) and not problems


def close_resolved(dry: bool = DRY):
    today = creds.now_local().replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    clean: dict[str, bool] = {}
    for i in open_issues():
        t = i["title"]
        m = re.match(r"^Autofix: (.+) non riparato$", t)
        if m:
            r = last_auto_run(m.group(1))
            if r and r["conclusion"] == "success" and r["created_at"] > i["updatedAt"]:
                close(i["number"], f"il run automatico di {m.group(1)} del {r['created_at'][:16].replace('T', ' ')} UTC "
                      f"è riuscito ({r['html_url']}).", dry)
            continue
        m = re.match(r"^(?:Canali non allineati|Controllo giornaliero) (\d\d)/(\d\d)/(\d{4})$", t)
        if m:
            d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            later = d + timedelta(days=1)
            while later < today:  # a later full day, already over, with every channel aligned
                key = f"{later:%Y-%m-%d}"
                if key not in clean:
                    clean[key] = clean_day(later)
                if clean[key]:
                    close(i["number"], f"il {later:%d/%m} tutti i canali hanno avuto il video del giorno.", dry)
                    break
                later += timedelta(days=1)


def issue(day: datetime, missing: list[str]):
    title = TITLE.format(day)
    body = ("Il controllo automatico (tools/day_guard.py) ha provato a rimediare da solo ma manca ancora:\n\n" +
            "\n".join(missing) + "\n\nSi chiude da sola quando un giorno successivo esce tutto.")
    print(body)
    if DRY:
        return
    for i in open_issues():
        if i["title"] == title:
            gh("issue", "comment", str(i["number"]), "--repo", REPO, "--body", body, check=False)
            return
    gh("label", "create", "alert", "--repo", REPO, "--color", "B60205", "--description", "Automazione fallita", check=False)
    gh("issue", "create", "--repo", REPO, "--title", title, "--label", "alert", "--body", body, check=False)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv
    if "--close-only" in a:
        close_resolved(DRY)
        return
    now = creds.now_local()
    day = (datetime.strptime(a[a.index("--date") + 1], "%Y-%m-%d").replace(tzinfo=creds.TZ) if "--date" in a
           else now.replace(hour=0, minute=0, second=0, microsecond=0))
    missing: list[str] = []
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=100"))
    rels = ensure_clip(day, rels, missing)
    tool("queue_short_reel")
    ensure_threads(day, now, missing)
    output(late=",".join(late_items(now)))
    if now.hour >= 16:
        check_tomorrow(day, rels, missing)
    close_resolved(DRY)
    if missing:
        issue(day, missing)
    else:
        print("day-guard: everything of today is queued or out")


if __name__ == "__main__":
    main()
