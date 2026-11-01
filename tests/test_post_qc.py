"""Offline checks of tools/post_qc.py, the quality gate of every post (owner request 1/11/2026).

  python tests/test_post_qc.py      (or: pytest tests/)
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cta  # noqa: E402
import post_qc as q  # noqa: E402
import threads_build as t  # noqa: E402

# the post that went out on 1/11/2026 at 12:00 (deleted by hand)
BAD_1101 = ("APOD: 2026 November 1 – Colors of the Moon\n\nAPOD Science APOD APOD: 2026 November 1 –… Today’s APOD "
            "Archive Submissions Index Search Calendar RSS Education About Discuss APOD Astronomy Picture of the Day "
            "Discover the cosmos! Each day a different image or photograph of our fascinating universe is featured, "
            "along with a brief explanation written by a professional astronomer. Colors of the Moon Explanation: What "
            "color is the Moon?\n\nSource: NASA (01 Nov 2026).")
EXPL = ("What color is the Moon? It depends on the night – and the time. Outside of the Earth's atmosphere, the dark "
        "Moon, which shines by reflected sunlight, appears a magnificently brown-tinged gray.")
GOOD = ("What color is the Moon?\n\nIt depends on the night – and the time. Outside of the Earth's atmosphere, the dark "
        "Moon, which shines by reflected sunlight, appears a magnificently brown-tinged gray.\n\nSource: NASA Astronomy "
        "Picture of the Day, \"Colors of the Moon\" (1 Nov 2026).\n"
        "https://science.nasa.gov/image-article/apod-2026-november-1-colors-of-the-moon/")
TODAY = date(2026, 11, 1)
NO_TRENDS = {}

# NASA Planetary Fact Sheet values (nssdc.gsfc.nasa.gov/planetary/factsheet/), offline copy for the test
P = ["MERCURY", "VENUS", "EARTH", "MOON", "MARS", "JUPITER", "SATURN", "URANUS", "NEPTUNE", "PLUTO"]
SHEET = {k: dict(zip(P, v.split())) for k, v in {
    "Mass (10 24 kg)": "0.330 4.87 5.97 0.073 0.642 1898 568 86.8 102 0.0130",
    "Diameter (km)": "4879 12,104 12,756 3475 6792 142,984 120,536 51,118 49,528 2376",
    "Gravity (m/s 2 )": "3.7 8.9 9.8 1.6 3.7 23.1 9.0 8.7 11.0 0.7",
    "Length of Day (hours)": "4222.6 2802.0 24.0 708.7 24.7 9.9 10.7 17.2 16.1 153.3",
    "Orbital Period (days)": "88.0 224.7 365.2 27.3* 687.0 4331 10,747 30,589 59,800 90,560",
    "Escape Velocity (km/s)": "4.3 10.4 11.2 2.4 5.0 59.5 35.5 21.3 23.5 1.3"}.items()}


def errs(text, **kw):
    kw.setdefault("today", TODAY)
    return q.errors_of(kw.pop("platform", "threads"), kw.pop("kind", "news"), text, **kw)


def test_bad_apod_of_1101_blocked():
    e = errs(BAD_1101)
    assert any("menu" in x for x in e), e


def test_good_apod_passes_and_numbers_match_source():
    assert errs(GOOD, source_text=EXPL + " Colors of the Moon 1 Nov 2026") == []


def test_cut_sentence_and_truncated_link_blocked():
    cut = "Webb finds carbon\n\nWebb has found carbon dioxide in the atmosphere of a planet 700 light-years and\n\nSource: NASA."
    assert any("cut" in x for x in errs(cut))
    assert any("truncated" in x for x in errs(GOOD.replace("colors-of-the-moon/", "colors-of…")))


def test_html_and_placeholders_blocked_then_cleaned():
    dirty = GOOD.replace("brown-tinged", "brown&amp;tinged")
    assert any("HTML" in x for x in errs(dirty))
    r = q.review({"ref": "th-news-1101-x", "text": dirty, "replies": []}, "threads", "news", today=TODAY)
    assert r["ok"] and r["fixed"] and "&amp;" not in r["fixed"]["text"]


def test_launch9_and_code_rules():
    assert any("LAUNCH9" in x for x in errs(GOOD, replies=["LOOK UP: https://cosmosinnumbers.gumroad.com/l/look-up\nCode LAUNCH9"]))
    assert any("COSMOS9" in x for x in errs(GOOD, replies=["LOOK UP: https://cosmosinnumbers.gumroad.com/l/look-up"]))
    for text in cta.TEXTS:  # every rotating CTA reply is valid
        assert errs(GOOD, replies=[text]) == [], text
    assert errs(GOOD, replies=["LOOK UP: https://cosmosinnumbers.gumroad.com/l/look-up"], today=date(2026, 12, 2)) == []


def test_gumroad_and_hashtags_not_in_threads_post():
    assert any("first reply" in x for x in errs(GOOD + "\nhttps://cosmosinnumbers.gumroad.com/l/look-up COSMOS9"))
    assert any("hashtags" in x for x in errs(GOOD.replace("What color", "#Moon What color")))


def test_source_required():
    assert any("source" in x for x in errs(GOOD.split("\n\nSource")[0]))


def test_length_limits():
    assert any("too long" in x for x in errs(GOOD + " " + "word " * 100))
    assert any("poll" in x for x in errs("Today's quiz 🪐 Which planet is the densest?\n\nAnswer tomorrow.",
                                         kind="quiz", poll=["Earth", "A very long planet name option"],
                                         replies=["Data: NASA Planetary Fact Sheet"]))


def test_tiktok_rules():
    ok = "Saturn would float in a bathtub 🪐\n\nFull video on YouTube: @CosmosinNumbers\n#space #astronomy"
    assert errs(ok, platform="tiktok", kind="reel") == []
    assert any("TikTok" in x for x in errs(ok + "\nLOOK UP guide, code COSMOS9", platform="tiktok", kind="reel"))
    assert any("Full video" in x for x in errs("Saturn would float in a bathtub.", platform="tiktok", kind="reel"))


def test_duplicates():
    assert any("duplicate" in x for x in errs(GOOD, recent=[GOOD.replace("2026", "2025")]))
    quiz = "Today's quiz 🪐 Which of these planets is the densest?\n\nAnswer tomorrow."
    assert any("same quiz" in x for x in errs(quiz, kind="quiz", recent=[quiz], replies=["Data: NASA"]))


def test_score_prefers_hook_numbers_and_trends():
    weak = ("Photo Release: New image\n\nThe observatory released a new image of a region of the sky today, "
            "processed by the team.\n\nSource: ESO (1 Nov 2026).")
    strong = ("Saturn is 9 times wider than Earth 🪐\n\nNASA lists 120,536 km for Saturn and 12,756 km for Earth. "
              "Measured across the equator.\n\nData: NASA Planetary Fact Sheet.")
    trend = {"saturn": 3.0, "earth": 2.0}
    assert q.score("threads", "news", strong, trend_words=trend)[0] > q.score("threads", "news", weak, trend_words=trend)[0] + 25
    assert q.score("threads", "news", strong, trend_words=trend)[0] >= q.MIN_SCORE


def test_data_post_reserve_is_valid():
    seen = set()
    for d in range(1, 15):
        item = t.data_post(datetime(2026, 11, d), [], SHEET)
        assert item and item["ref"].startswith("th-data-")
        r = q.review(item, "threads", "data", today=TODAY)
        assert r["ok"], (item["text"], r["errors"])
        assert r["score"] >= q.MIN_SCORE, (item["text"], r["score"])
        seen.add(item["ref"])
    assert len(seen) > 5  # varies with the day
    used = [t.data_post(datetime(2026, 11, 1), [], SHEET)]
    assert t.data_post(datetime(2026, 11, 1), used, SHEET)["ref"] != used[0]["ref"]  # never the same pair twice


def test_kind_of():
    assert q.kind_of({"ref": "th-quiz-1101-density-min", "poll": ["a", "b"]}, "threads") == "quiz"
    assert q.kind_of({"ref": "th-a1031-iss"}, "threads") == "video"
    assert q.kind_of({"ref": "sr-a1031-x", "action": "ig-reel"}, "ig") == "reel"


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
