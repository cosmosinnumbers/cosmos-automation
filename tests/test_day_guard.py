"""Offline checks of the self-repair added on 04/11/2026 (owner: "voglio che il sistema si autorisolva"):
tools/day_guard.py, the known failures of tools/self_heal.py, the reserve clip of tools/day_clip.py and
tools/git_sync.sh.

  python -m pytest -q tests/test_day_guard.py
"""
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import creds  # noqa: E402
import day_guard as g  # noqa: E402
import self_heal as s  # noqa: E402

TZ = creds.TZ
WED = datetime(2026, 11, 4, tzinfo=TZ)
MON = datetime(2026, 11, 9, tzinfo=TZ)


# ---------------------------------------------------------------- self-heal: known failures
@pytest.mark.parametrize("log, kind", [
    ("error: cannot pull with rebase: You have unstaged changes.\nerror: Please commit or stash them.", "git"),
    (" ! [rejected]        main -> main (fetch first)\nerror: failed to push some refs to 'https://x'", "git"),
    ("04/11: no unused clip of a public long video and no reserve clip: no short video today.", "clip"),
    ("googleapiclient.errors.HttpError: uploadLimitExceeded", "upload"),
    ('{"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}}', "quota"),
    ("requests.exceptions.ConnectionError: Connection reset by peer", "transient"),
    ("Gemini HTTP 503 Service Unavailable", "transient"),
])
def test_known_failures(log, kind):
    assert s.known_failure(log)["kind"] == kind


def test_unknown_failure_goes_to_the_autofix():
    assert s.known_failure("Traceback ...\nKeyError: 'title'") is None
    assert s.known_failure("checked the quota page: fine") is None  # the word alone is not a quota error


def test_known_entries_are_complete():
    for k in s.CFG["known"]:
        assert k["kind"] and k["label"] and k["waits_s"] and k["issue_kind"] in s.KIND_IT, k
        assert sum(k["waits_s"]) <= 45 * 60  # inside the self-heal job timeout
        for wf, _inputs in k.get("before", []):
            assert (ROOT / ".github/workflows" / wf).exists(), wf
            assert Path(wf).stem not in s.CFG["workflows"]  # never a workflow self-heal follows: no loop


# ---------------------------------------------------------------- day guard: Threads slots
def test_slot_times():
    assert g.slot_at(WED, "quiz") == "17:55" and g.slot_at(MON, "quiz") == "16:00"
    assert g.slot_at(MON, "news") == "12:00" and g.slot_at(WED, "video") == "21:00"


def run_threads(monkeypatch, day, now, queue_items, log=()):
    calls = []
    monkeypatch.setattr(g, "queue", lambda ch: list(queue_items))
    monkeypatch.setattr(g.creds, "events", lambda name: list(log))
    monkeypatch.setattr(g, "tool", lambda name, *a: calls.append((name, a)) or (0, ""))
    monkeypatch.setattr(g, "DRY", True)
    g.ensure_threads(day, now, [])
    return calls


def test_all_slots_missing_in_the_morning(monkeypatch):
    calls = run_threads(monkeypatch, WED, WED.replace(hour=11, minute=30), [])
    assert calls == [("threads_build", ("--date", "2026-11-04", "--only", "news,quiz,video"))]


def test_slots_already_queued_are_left_alone(monkeypatch):
    q = [{"ref": "th-news-1104-x", "at": "2026-11-04 12:00"}, {"ref": "th-quiz-1104-x", "at": "2026-11-04 17:55"},
         {"ref": "th-c1104-p4-clip-e", "at": "2026-11-04 21:00"}]
    assert run_threads(monkeypatch, WED, WED.replace(hour=11, minute=30), q) == []


def test_old_slot_is_missed_not_posted_late(monkeypatch):
    # Monday 17:30: news of 12:00 is 5.5 h old (missed), quiz of 16:00 is 90 min old (still made), video to make
    calls = run_threads(monkeypatch, MON, MON.replace(hour=17, minute=30), [])
    assert calls == [("threads_build", ("--date", "2026-11-09", "--only", "quiz,video"))]


def test_slot_already_out_with_another_time(monkeypatch):
    out = int(WED.replace(hour=12, minute=4).timestamp())
    log = [{"p": "threads", "k": "text", "at": out, "ref": "th-news-1104-apod"},
           {"p": "threads", "k": "reply", "at": out, "ref": "th-quiz-1104-r1"}]  # a reply does not count
    calls = run_threads(monkeypatch, WED, WED.replace(hour=11, minute=30), [], log)
    assert calls == [("threads_build", ("--date", "2026-11-04", "--only", "quiz,video"))]


# ---------------------------------------------------------------- day guard: late items
def late(monkeypatch, now, items, done=()):
    monkeypatch.setattr(g, "queue", lambda ch: items if ch == "threads" else [])
    monkeypatch.setattr(g, "done_refs", lambda ch: set(done))
    return g.late_items(now)


def test_late_quiz_is_published_now(monkeypatch):
    q = [{"ref": "th-quiz-1109-a", "at": "2026-11-09 16:00"}, {"ref": "th-c1109-v", "at": "2026-11-09 21:00"}]
    assert late(monkeypatch, MON.replace(hour=17, minute=30), q) == ["threads:th-quiz-1109-a"]


def test_late_item_already_out_or_too_close_to_the_next(monkeypatch):
    q = [{"ref": "th-quiz-1109-a", "at": "2026-11-09 16:00"}, {"ref": "th-c1109-v", "at": "2026-11-09 21:00"}]
    assert late(monkeypatch, MON.replace(hour=17, minute=30), q, done={"th-quiz-1109-a"}) == []
    assert late(monkeypatch, MON.replace(hour=17, minute=50), q) == []  # 21:00 is less than 3 h 20 min away


def test_not_late_yet_or_too_old(monkeypatch):
    q = [{"ref": "th-news-1109-a", "at": "2026-11-09 12:00"}]
    assert late(monkeypatch, MON.replace(hour=11, minute=30), q) == []
    assert late(monkeypatch, MON.replace(hour=17, minute=30), q) == []


# ---------------------------------------------------------------- day guard: issues
def test_close_resolved(monkeypatch):
    issues = [
        {"number": 50, "title": "Autofix: threads-build non riparato", "updatedAt": "2026-11-04T15:05:00Z"},
        {"number": 61, "title": "Autofix: publish non riparato", "updatedAt": "2026-11-05T12:00:00Z"},
        {"number": 51, "title": "Canali non allineati 04/11/2026", "updatedAt": "2026-11-04T21:26:15Z"},
        {"number": 70, "title": "Controllo giornaliero 05/11/2026", "updatedAt": "2026-11-05T16:40:00Z"},
        {"number": 28, "title": "Scaletta della settimana 03/11 - 09/11/2026", "updatedAt": "2026-11-03T11:05:43Z"},
    ]
    runs = {"threads-build": {"conclusion": "success", "created_at": "2026-11-05T06:40:12Z", "html_url": "u"},
            "publish": {"conclusion": "success", "created_at": "2026-11-05T10:45:00Z", "html_url": "u"}}
    closed = []
    monkeypatch.setattr(g, "open_issues", lambda: issues)
    monkeypatch.setattr(g, "last_auto_run", lambda name: runs.get(name))
    monkeypatch.setattr(g, "clean_day", lambda d: d.day == 5)
    monkeypatch.setattr(g, "close", lambda n, why, dry: closed.append(n))
    monkeypatch.setattr(g.creds, "now_local", lambda: datetime(2026, 11, 6, 11, 30, tzinfo=TZ))
    g.close_resolved(dry=True)
    # 50: a later automatic run succeeded; 61: the success is older than the issue; 51: 5/11 was clean;
    # 70: no clean day after 5/11 yet; 28 is not an alert of the guard
    assert closed == [50, 51]


# ---------------------------------------------------------------- day_clip: reserve clip
def test_reserve_clip(monkeypatch, tmp_path):
    import day_clip
    cfg = tmp_path / "clip-reserve.json"
    cfg.write_text('{"reuse_after_days": 30}', "utf-8")
    monkeypatch.setattr(day_clip, "RESERVE", cfg)
    monkeypatch.setattr(day_clip, "longs", lambda cutoff: [{"ref": "lf-p4", "id": "v4", "when": 1}])
    rels = [{"tag_name": "lf-p4", "assets": [{"name": "p4-clip-d.mp4"}, {"name": "p4-clip-e.mp4"}]},
            {"tag_name": "c1003-p4-clip-d", "created_at": "2026-10-03T05:50:00Z"},
            {"tag_name": "c1010-p4-clip-e", "created_at": "2026-10-10T05:50:00Z"}]
    day = datetime(2026, 11, 7, tzinfo=TZ)
    assert day_clip.reserve(day, rels)[2] == "p4-clip-d"  # the oldest use, 35 days ago
    assert day_clip.reserve(datetime(2026, 10, 20, tzinfo=TZ), rels) is None  # nothing 30 days old yet
    cfg.write_text('{"reuse_after_days": 0}', "utf-8")
    assert day_clip.reserve(day, rels) is None  # off


# ---------------------------------------------------------------- git_sync.sh
@pytest.mark.skipif(not shutil.which("bash") or not shutil.which("git"), reason="needs bash and git")
def test_git_sync_with_unstaged_changes_and_a_concurrent_push(tmp_path):
    def git(cwd, *a):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout

    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    a, b = tmp_path / "a", tmp_path / "b"
    git(tmp_path, "clone", "-q", str(remote), str(a))
    for c in (a,):
        git(c, "config", "user.name", "t"); git(c, "config", "user.email", "t@t")
    (a / "logs").mkdir()
    (a / ".gitattributes").write_text("logs/*.jsonl merge=union\n", "utf-8")
    (a / "logs" / "qc-log.jsonl").write_text('{"n": 0}\n', "utf-8")
    (a / "queue.json").write_text("[]\n", "utf-8")
    (a / "other.txt").write_text("x\n", "utf-8")
    git(a, "add", "-A"); git(a, "commit", "-q", "-m", "init"); git(a, "push", "-q", "origin", "main")
    git(tmp_path, "clone", "-q", str(remote), str(b))
    git(b, "config", "user.name", "u"); git(b, "config", "user.email", "u@u")
    # another run pushes first, appending to the same log
    with (b / "logs" / "qc-log.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"n": "b"}\n')
    git(b, "commit", "-q", "-am", "b"); git(b, "push", "-q", "origin", "main")
    # this run: the queue committed, the log appended but not added, another file left modified (the 4/11 case)
    (a / "queue.json").write_text('[{"ref": "th-news"}]\n', "utf-8")
    git(a, "commit", "-q", "-am", "queue")
    with (a / "logs" / "qc-log.jsonl").open("a", encoding="utf-8") as f:
        f.write('{"n": "a"}\n')
    (a / "other.txt").write_text("y\n", "utf-8")
    r = subprocess.run(["bash", str(ROOT / "tools" / "git_sync.sh"), "log: test"], cwd=a, capture_output=True,
                       text=True, env={**__import__("os").environ, "GITHUB_REF_NAME": "main"})
    assert r.returncode == 0, r.stderr
    git(b, "pull", "-q")
    log = (b / "logs" / "qc-log.jsonl").read_text("utf-8")
    assert '"b"' in log and '"a"' in log  # both appends kept (union)
    assert "th-news" in (b / "queue.json").read_text("utf-8")
    assert (a / "other.txt").read_text("utf-8") == "y\n"  # the unstaged file is back, not pushed
    assert (b / "other.txt").read_text("utf-8") == "x\n"


# ---------------------------------------------------------------- self-heal: flow of a known failure
def fake_heal(monkeypatch, tmp_path, wf, log, results):
    outs, started = {}, []
    monkeypatch.setattr(s, "WF", wf)
    monkeypatch.setattr(s, "TMP", tmp_path)
    monkeypatch.setattr(s, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(s.time, "sleep", lambda t: None)
    monkeypatch.setattr(s, "failed_logs", lambda: ("job build", log))
    monkeypatch.setattr(s, "rerun_and_wait", lambda: results.pop(0))
    monkeypatch.setattr(s, "dispatch_and_wait", lambda f, i: started.append(f) or "success")
    monkeypatch.setattr(s, "after_recovery", lambda: started.append("after_recovery"))
    monkeypatch.setattr(s, "output", lambda **kv: outs.update(kv))
    s.cmd_retry()
    return outs, started


def test_known_git_failure_is_repaired_by_a_later_rerun(monkeypatch, tmp_path):
    # the 4/11 case: 2 normal re-runs fail, the first repair re-run (after git_sync is on main) succeeds
    outs, _ = fake_heal(monkeypatch, tmp_path, "threads-build", "error: cannot pull with rebase: You have unstaged changes.",
                        ["failure", "failure", "success"])
    assert outs == {"result": "recovered"}


def test_missing_clip_makes_the_clip_first(monkeypatch, tmp_path):
    outs, started = fake_heal(monkeypatch, tmp_path, "youtube-upload", "no Short release c1105-* yet",
                              ["failure", "failure", "success"])
    assert outs == {"result": "recovered"} and started[0] == "long-clips.yml"


def test_quota_still_failing_skips_the_llm(monkeypatch, tmp_path):
    outs, _ = fake_heal(monkeypatch, tmp_path, "publish", '"status": "RESOURCE_EXHAUSTED"',
                        ["failure", "failure", "failure", "failure"])
    assert outs == {"result": "failed"}
    monkeypatch.setattr(s, "run_info", lambda: {"path": ".github/workflows/publish.yml", "head_sha": "x"})
    s.cmd_diagnose()
    st = __import__("json").loads((tmp_path / "state.json").read_text("utf-8"))
    assert outs["status"] == "skip" and st["kind"] == "quota" and "1 tentativi" in st["diagnosis"]
