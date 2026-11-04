import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import auto_clips as ac  # noqa: E402
import cross_learn as cl  # noqa: E402


def _post(ch, kind, title, views, extra=None, day=1):
    return {"channel": ch, "kind": kind, "id": f"{ch}{title[:5]}{views}", "title": cl.clean_title(title),
            "published": datetime(2026, 11, day, 20, 0, tzinfo=timezone.utc), "m": {"views": views, **(extra or {})}}


def test_scores_group_across_channels():
    posts = [_post("instagram", "reel", "What a light-year really is  Full video on YouTube: @x", 1172,
                   {"avg_watch_ms": 14683, "likes": 17, "saved": 5, "shares": 1}),
             _post("instagram", "reel", "Ghost Nebula: 1,200 Light-Years Away", 116, {"avg_watch_ms": 6511, "likes": 4}),
             _post("instagram", "reel", "The farthest thing you can see", 212, {"avg_watch_ms": 9173, "likes": 4}),
             _post("facebook", "reel", "What a light-year really is  Full video on YouTube: https://youtu.be/x", 2),
             _post("facebook", "reel", "Boosting Space Station Power to 215 kW", 7)]
    cl.score_posts(posts)
    items = cl.group_items(posts)
    hit = next(it for it in items if it["title"] == "What a light-year really is")
    assert set(hit["channels"]) == {"instagram", "facebook"}
    assert hit["channels"]["instagram"] > 2 and hit["score"] == max(it["score"] for it in items)


def test_caption_contains_short_title():
    a = cl.words("11 Earths Fit Across Jupiter (NASA data) #shorts")
    b = cl.words("11 Earths fit across Jupiter. It is about 143,000 km wide; Earth is just 12,756.")
    assert cl.overlap(a, b) >= 0.5


def test_labels_and_predict_follow_weights():
    lab = cl.labels("What a light-year really is")
    assert "light_distance" in lab["theme"] and "explainer" in lab["theme"]
    w = {"features": {"theme": {"light_distance": {"mean": 2.0, "n": 5}, "explainer": {"mean": 1.6, "n": 3},
                                "planets": {"mean": 0.7, "n": 9}}}}
    assert cl.predict("What a light-year really is", w) > cl.predict("Why Clipper won't orbit Europa", w)
    assert cl.predict("zzz", {}) == 1.0


def test_learn_dry_run_on_repo_metrics():
    s = cl.learn(date(2026, 11, 4), dry=True)
    assert s["items"] > 0 and s["top"]
    assert all(r["n"] >= cl.MIN_N for r in s["rules"])
    assert "Apprendimento" in cl.report(s)


def _srt(script):
    import re
    t, out, n = 0.0, [], 1
    f = lambda x: f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(x % 1 * 1000):03d}"
    for seg in script["segments"]:
        for s in re.split(r"(?<=[.!?])\s+", seg["narration"].replace("\n", " ").strip()):
            d = len(s.split()) / 2.7
            out.append(f"{n}\n{f(t)} --> {f(t + d)}\n{s}\n")
            n, t = n + 1, t + d + 0.3
    return "\n".join(out)


def test_auto_clips_align_and_rank(tmp_path):
    spec = yaml.safe_load((ROOT / "longform" / "p4-light-year-ladder" / "script.yaml").read_text("utf-8"))
    srt = tmp_path / "p4.srt"
    srt.write_text(_srt(spec), "utf-8")
    clips = ac.build("p4-light-year-ladder", srt, n=6, llm=False)
    assert 3 <= len(clips) <= 6
    for c in clips:
        assert ac.MIN_S <= c["end"] - c["start"] <= ac.MAX_S + 0.5
        assert c["headline"] and len(c["headline"]) <= 48
    assert [c["start"] for c in clips] == sorted(c["start"] for c in clips)
    text = ac.dump(clips)
    back = yaml.safe_load(text)
    assert back[0]["id"].startswith("p4-clip-") and "headline" in back[0]


def test_headline_check():
    assert ac.ok_headline("The Sun you see is 8 minutes old", "light takes 8 minutes and 19 seconds")
    assert not ac.ok_headline("The Sun is 9 minutes old", "light takes 8 minutes")
    assert not ac.ok_headline("Use code COSMOS9", "x")
