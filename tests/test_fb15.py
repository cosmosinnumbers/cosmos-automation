"""The 15:00 news Short goes to Facebook at 16:00 from 15/11 and never moves the 20:50 slot of the clip."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import queue_short_reel as q  # noqa: E402


def test_fb15_items_do_not_move_the_clip_slot(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "LOG", tmp_path / "log.jsonl")
    now = datetime(2026, 11, 16, 12, 30, tzinfo=q.TZ)
    queue = [{"ref": "fr-b1116-x", "at": "2026-11-16 16:00", "action": "fb-reel"}]
    assert q.last_of(queue, "fb-reel") is None
    last = datetime(2026, 11, 15, 20, 50, tzinfo=q.TZ)
    (tmp_path / "log.jsonl").write_text(json.dumps({"p": "fb", "k": "reel", "at": int(last.timestamp()), "item": "fr-c1115-y"}) + "\n")
    assert q.last_of(queue, "fb-reel") == last
    assert q.slot(now, q.last_of(queue, "fb-reel")).strftime("%H:%M") >= "20:48"


def test_fb15_not_before_15_11(monkeypatch):
    called = []
    monkeypatch.setattr(q, "gh", lambda *a: called.append(a) or "[]")
    q.queue_fb15(datetime(2026, 11, 10, 12, 30, tzinfo=q.TZ))
    assert not called
    q.queue_fb15(datetime(2026, 11, 16, 12, 30, tzinfo=q.TZ))
    assert called
