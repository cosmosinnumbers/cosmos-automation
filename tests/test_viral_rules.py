import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import auto_short as a  # noqa: E402


def test_prompts_format():
    a.PROMPT.format(today="x", hint="", used="", rules=a.VIRAL_RULES)
    a.RSS_PROMPT.format(today="x", hint="", used="", items="", rules=a.VIRAL_RULES)
    a.REF_PROMPT.format(today="x", used="", items="", rules=a.VIRAL_RULES)


def test_bad_short_is_rejected():
    bad = {"narration": "Did you know that Venus has a very long day that is longer than its year on the whole? Subscribe now."}
    p = a.viral_problems(bad)
    assert len(p) >= 3


def test_good_short_passes():
    good = {"narration": "A day on Venus is longer than its year. It lasts 243 Earth days. The reason is stranger than the number. "
                         "Venus spins backward. So a day on Venus is longer than its year."}
    assert a.viral_problems(good) == []


def test_punch_in_changes_odd_subshots():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
    import short
    from PIL import Image, ImageDraw
    f = Image.new("RGB", (400, 300), (0, 0, 0))
    ImageDraw.Draw(f).rectangle((0, 0, 200, 150), fill=(255, 255, 255))
    assert short.punch(f, 0, 0).tobytes() == f.tobytes()
    assert short.punch(f, 1, 1.0).tobytes() != f.tobytes()


if __name__ == "__main__":
    test_prompts_format(); test_bad_short_is_rejected(); test_good_short_passes(); test_punch_in_changes_odd_subshots(); print("ok")
