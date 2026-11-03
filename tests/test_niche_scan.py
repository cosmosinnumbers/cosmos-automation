import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import niche_scan as ns  # noqa: E402


def test_iso_duration():
    assert ns.iso_dur("PT12M5S") == 725
    assert ns.iso_dur("PT1H") == 3600
    assert ns.iso_dur("P1DT1S") == 86401
    assert ns.iso_dur("bad") == 0


def test_title_features():
    f = ns.title_features("What If You Stopped Sleeping for 30 Days?")
    assert f["what_if"] and f["question"] and f["number"] and f["you"]
    assert not ns.title_features("Every Level of Wealth Explained")["question"]
    assert ns.title_features("Every Level of Wealth Explained")["every"]


def test_style_check_without_gemini():
    vids = [{"thumb": ""}]
    assert "non configurato" in ns.style_check(vids, None)
    assert vids[0]["style"]["stick"] is None


def test_report_runs_on_unknown_style():
    v = {"id": "x", "title": "Why Rome Fell", "channel": "C", "channel_id": "c1", "published": "2026-10-01",
         "duration_s": 600, "views": 100000, "views_per_day": 3000, "engagement": 0.03, "queries": ["q (30g)"],
         "features": ns.title_features("Why Rome Fell"), "style": {"stick": None}}
    md = ns.report("stickman", {"name": "Test"}, [v], {"c1": {"title": "C", "subs": 1000, "age_days": 90}}, "s")
    assert "Why Rome Fell" in md and "100.0" in md
