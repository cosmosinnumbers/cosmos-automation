"""Offline checks of tools/self_heal.py (autofix of failed workflows, owner request 02/11/2026).

  python -m pytest -q tests/test_self_heal.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import self_heal as s  # noqa: E402


def test_config_matches_workflow_list():
    import yaml
    wf = yaml.safe_load((s.ROOT / ".github/workflows/self-heal.yml").read_text("utf-8"))
    listed = set(wf[True]["workflow_run"]["workflows"])  # PyYAML reads the key "on" as True
    assert listed == set(s.CFG["workflows"])
    names = {yaml.safe_load(p.read_text("utf-8"))["name"] for p in (s.ROOT / ".github/workflows").glob("*.yml")}
    assert listed <= names, listed - names
    for never in ("launch9", "threads-delete", "tiktok-auth", "self-heal"):
        assert never not in listed


def test_risky_paths_and_words():
    plain = "+    x = compute(y)\n-    x = compute(z)\n"
    assert s.risky(plain, ["tools/phone_notes.py"]) == ""
    assert "run_slot" in s.risky(plain, ["tools/run_slot.py"])
    assert "queues/" in s.risky(plain, ["queues/meta-queue.json"]) or s.risky(plain, ["queues/meta-queue.json"])
    assert s.risky(plain, [".github/workflows/publish.yml"])
    assert s.risky("+    requests.delete(url)\n", ["tools/phone_notes.py"])
    assert s.risky("+    tok = os.environ['THREADS_TOKEN']\n", ["tools/phone_notes.py"])
    big = "".join(f"+ line {i}\n" for i in range(200))
    assert "grande" in s.risky(big, ["tools/phone_notes.py"])


def test_forbidden_paths():
    assert s.forbidden(".github/workflows/publish.yml")
    assert s.forbidden("secrets/api.env")
    assert s.forbidden("../etc/passwd")
    assert s.forbidden("tools/does_not_exist.py")
    assert s.forbidden("tools/phone_notes.py") == ""


def test_apply_edits_all_or_nothing(tmp_path, monkeypatch):
    (tmp_path / "tools").mkdir()
    f = tmp_path / "tools" / "a.py"
    f.write_text("x = 1\ny = 2\n", "utf-8")
    monkeypatch.setattr(s, "ROOT", tmp_path)
    # second edit does not match: nothing is written
    why = s.apply_edits([{"path": "tools/a.py", "old": "x = 1", "new": "x = 3"},
                         {"path": "tools/a.py", "old": "z = 9", "new": "z = 0"}])
    assert "0 times" in why and f.read_text("utf-8") == "x = 1\ny = 2\n"
    assert s.apply_edits([{"path": "tools/a.py", "old": "y = 2", "new": "y = 5"}]) == ""
    assert f.read_text("utf-8") == "x = 1\ny = 5\n"
    assert s.apply_edits([]) == "no edits"


def test_parse_and_related_files():
    assert s.parse('bla {"kind": "code", "edits": []} bla') == {"kind": "code", "edits": []}
    assert s.parse("not json") is None
    log = ('Traceback (most recent call last):\n  File "/home/runner/work/cosmos-automation/cosmos-automation/'
           'tools/threads_build.py", line 12, in <module>\nKeyError: x\nRun python tools/post_qc.py')
    files = dict(s.related_files(log, "run: python tools/health.py"))
    assert files["tools/threads_build.py"] == [12]
    assert "tools/post_qc.py" in files and "tools/health.py" in files


def test_limits(tmp_path, monkeypatch):
    log = tmp_path / "autofix-log.jsonl"
    monkeypatch.setattr(s, "LOG", log)
    monkeypatch.setattr(s, "WF", "metrics")
    assert s.over_limit() == ""
    now = int(s.time.time())
    log.write_text(json.dumps({"wf": "metrics", "at": now - 3600}) + "\n", "utf-8")
    assert "metrics" in s.over_limit()
    monkeypatch.setattr(s, "WF", "research")
    log.write_text("".join(json.dumps({"wf": f"w{i}", "at": now - 60}) + "\n" for i in range(4)), "utf-8")
    assert "al giorno" in s.over_limit()
