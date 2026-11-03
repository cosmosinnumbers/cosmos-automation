import json
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import experiments as ex  # noqa: E402
import trend_scout as ts  # noqa: E402

LIB = ts.load_formats()


def test_classify_titles():
    assert ts.classify("SIZE OF SOLAR SYSTEM! 💀", LIB)["format"] == "scale_zoom"
    assert ts.classify("The Lid NASA Couldn't Open", LIB)["format"] == "mission_glitch"
    assert ts.classify("Why Nothing Can Survive Venus", LIB)["format"] == "survive_x"
    assert ts.classify("Solar System's Biggest Lie!", LIB)["hook"] == "paradox"
    assert ts.classify("11 Earths Fit Across Jupiter", LIB)["theme"] == "jupiter"


def test_trend_scores_and_saturation():
    research = {"youtube": {"videos": [
        {"id": "a", "title": "Ant vs the Universe size comparison", "views_per_day": 1000, "duration": "PT45S"},
        {"id": "b", "title": "Why nothing can survive Venus", "views_per_day": 500, "duration": "PT50S"},
        {"id": "c", "title": "The probe that failed", "views_per_day": 100, "duration": "PT10M"}],
        "audience_questions": ["Why does the Moon look close to Earth in the sky?", "x?"]}}
    res = ts.analyse(research, LIB, {"a": 500}, {})
    assert list(res["formats"])[0] == "scale_zoom" and res["formats"]["scale_zoom"]["accelerating"]
    sat = ts.analyse(research, LIB, {}, {"scale_zoom": 3})
    assert sat["formats"]["scale_zoom"]["score"] < res["formats"]["scale_zoom"]["score"]
    assert res["audience_questions"] == ["Why does the Moon look close to Earth in the sky?"]


def test_thompson_converges_on_best_arm():
    rng = random.Random(1)
    state = {"good": {"n": 40, "wins": 30, "losses": 10}, "bad": {"n": 40, "wins": 8, "losses": 32}}
    picks = [ex.thompson(["good", "bad"], state, {}, rng, set())[0] for _ in range(500)]
    assert picks.count("good") > 400


def test_exploration_picks_least_tried():
    rng = random.Random(0)
    state = {"a": {"n": 10, "wins": 9, "losses": 1}, "b": {"n": 0}}
    whys = [ex.thompson(["a", "b"], state, {}, rng, set()) for _ in range(300)]
    explored = [a for a, why in whys if why.startswith("esplorazione")]
    assert explored and set(explored) == {"b"}


def test_arms_decision_and_follow_ups():
    today = date(2026, 11, 10)
    rows = [{"id": str(i), "title": f"t{i}", "published": "2026-11-05", "score": 2.5 if i == 0 else 1.4,
             "views": 10, "pct": 50, "labels": {"format": "scale_zoom", "hook": "comparison"}} for i in range(5)]
    st = ex.arms(rows, "format", today)
    assert st["scale_zoom"]["decision"] == "vince" and st["scale_zoom"]["n"] == 5
    ups = ex.follow_ups(rows, [], today)
    assert len(ups) == 2 and all(u["format"] == "scale_zoom" and u["from_id"] == "0" for u in ups)
    assert ex.follow_ups(rows, ups, today) == []   # never twice for the same hit


def test_plan_respects_weekly_cap(tmp_path, monkeypatch):
    log = tmp_path / "experiments.jsonl"
    log.write_text("\n".join(json.dumps({"date": "2026-11-0%d" % d, "labels": {"format": "scale_zoom"}}) for d in (1, 2, 3)), "utf-8")
    monkeypatch.setattr(ex, "LOG", log)
    monkeypatch.setattr(ex, "IDEAS", tmp_path / "ideas.json")
    monkeypatch.setattr(ex, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(ts, "SKY", tmp_path / "none.json")
    for s in range(30):
        p = ex.plan(date(2026, 11, 4), seed=str(s))
        assert p["format"] != "scale_zoom" and p["hook"] in LIB["hooks"]


def test_sky_event_first(tmp_path, monkeypatch):
    sky = tmp_path / "sky.json"
    sky.write_text(json.dumps({"events": [{"date": "2026-11-17", "name": "Leonids peak", "hint": "the Leonids"}]}), "utf-8")
    monkeypatch.setattr(ts, "SKY", sky)
    monkeypatch.setattr(ex, "LOG", tmp_path / "none.jsonl")
    monkeypatch.setattr(ex, "IDEAS", tmp_path / "ideas.json")
    p = ex.plan(date(2026, 11, 16), seed="x")
    assert p["format"] == "sky_tonight" and p["topic"] == "the Leonids"
    assert ex.plan(date(2026, 11, 16), evergreen=True, seed="x")["format"] != "sky_tonight"


def test_format_rules_in_writer_prompt():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
    import auto_short as a
    txt = a.format_rules("quiz_guess", "question")
    assert "FORMAT quiz_guess" in txt and "HOOK question" in txt and "format_fit" in txt
    assert a.format_rules("nope", "nope") == ""
