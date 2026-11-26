import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import day_short  # noqa: E402

DAY = datetime(2026, 11, 26)


def test_news_short_when_no_clip_left(monkeypatch):
    monkeypatch.setattr(day_short, "clips_mode", lambda d: True)
    rels = [{"tag_name": "a1126-europa", "created_at": "2026-11-25T19:35:44Z"},
            {"tag_name": "b1126-hot", "created_at": "2026-11-26T11:00:00Z"}]
    assert day_short.pick(rels, DAY)["tag_name"] == "a1126-europa"
    assert day_short.pick(rels, DAY, "b")["tag_name"] == "b1126-hot"


def test_clip_still_wins(monkeypatch):
    monkeypatch.setattr(day_short, "clips_mode", lambda d: True)
    rels = [{"tag_name": "a1126-europa", "created_at": "2026-11-25T19:35:44Z"},
            {"tag_name": "c1126-p7-clip-a", "created_at": "2026-11-26T06:00:00Z"}]
    assert day_short.pick(rels, DAY)["tag_name"] == "c1126-p7-clip-a"


def test_nothing_at_all(monkeypatch):
    monkeypatch.setattr(day_short, "clips_mode", lambda d: True)
    assert day_short.pick([{"tag_name": "a1125-x"}], DAY) is None
