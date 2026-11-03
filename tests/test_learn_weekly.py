import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import learn_weekly as lw  # noqa: E402


def row(i, title, views, pct):
    return {"id": str(i), "title": title, "kind": "short", "read_at": "2026-11-02",
            "metrics": {"views": views, "avg_view_pct": pct, "avg_view_duration_s": 30 * pct / 100}}


def test_clear_effect_becomes_rule():
    rows = [row(i, f"{i} Earths fit inside Jupiter", 900, 60) for i in range(4)] + \
           [row(10 + i, "A quiet story about space", 100, 40) for i in range(4)]
    res = lw.analyse(rows)
    assert res["features"]["short:number_in_title"]["rule"].startswith("put a concrete number")


def test_too_few_videos_no_rules():
    assert lw.analyse([row(1, "x", 10, 50)])["features"] == {}


if __name__ == "__main__":
    test_clear_effect_becomes_rule(); test_too_few_videos_no_rules(); print("ok")
