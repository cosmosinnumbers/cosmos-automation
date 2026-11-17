import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import clock  # noqa: E402

CFG = json.loads((ROOT / "config" / "clock.json").read_text("utf-8"))


def _at(s):  # Italian time -> aware datetime
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=clock.TZ)


def test_publish_due_from_its_time_for_an_hour():
    names = lambda now: [(j["workflow"], j["at"]) for j, _ in clock.due_jobs(CFG, _at(now))]
    assert ("publish.yml", "11:45") not in names("2026-11-18 11:40")
    assert ("publish.yml", "11:45") in names("2026-11-18 11:45")
    assert ("publish.yml", "11:45") in names("2026-11-18 12:40")
    assert ("publish.yml", "11:45") not in names("2026-11-18 12:50")


def test_italian_time_in_summer_too():
    # 11:45 CEST = 09:45 UTC: no second set of summer crons is needed
    now = datetime(2027, 6, 1, 9, 46, tzinfo=timezone.utc)
    assert ("publish.yml", "11:45") in [(j["workflow"], j["at"]) for j, _ in clock.due_jobs(CFG, now)]


def test_already_started_ignores_workflow_run_and_older_runs():
    since = datetime(2026, 11, 18, 10, 43, tzinfo=timezone.utc)
    runs = [{"event": "workflow_run", "created_at": "2026-11-18T10:50:00Z"},
            {"event": "schedule", "created_at": "2026-11-18T09:00:00Z"}]
    assert not clock.already_started(runs, since)
    assert clock.already_started(runs + [{"event": "workflow_dispatch", "created_at": "2026-11-18T10:45:05Z"}], since)


def test_every_job_targets_an_existing_dispatchable_workflow():
    for job in CFG["jobs"]:
        wf = (ROOT / ".github" / "workflows" / job["workflow"]).read_text("utf-8")
        assert "workflow_dispatch:" in wf
        for key in job.get("inputs", {}):
            assert f"      {key}:" in wf, (job["workflow"], key)
