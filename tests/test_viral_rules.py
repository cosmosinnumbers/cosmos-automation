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


if __name__ == "__main__":
    test_prompts_format(); test_bad_short_is_rejected(); test_good_short_passes(); print("ok")
