import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import meta_api  # noqa: E402


def _log(tmp_path, monkeypatch, events):
    log = tmp_path / "meta-publish-log.jsonl"
    log.write_text("".join(json.dumps(e) + "\n" for e in events), "utf-8")
    monkeypatch.setattr(meta_api, "LOG", log)


def test_daily_reel_a_few_minutes_early_is_allowed(tmp_path, monkeypatch):
    # 16/11 20:51:28 Reel, 17/11 20:51:20 Reel: same daily slot, must not be blocked (bug of 17/11/2026)
    _log(tmp_path, monkeypatch, [{"p": "ig", "k": "reel", "at": 1794858688, "ref": "x"}])
    assert meta_api.guard("ig", "reel", 1794858688 + 86400 - 8)


def test_two_reels_same_day_still_blocked(tmp_path, monkeypatch):
    _log(tmp_path, monkeypatch, [{"p": "ig", "k": "reel", "at": 1794858688, "ref": "x"}])
    with pytest.raises(SystemExit):
        meta_api.guard("ig", "reel", 1794858688 + 13 * 3600)
