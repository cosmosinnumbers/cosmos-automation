"""Offline checks of the Threads news quality filter (bug of 1/11/2026: APOD post made of the site menu).

  python tests/test_threads_quality.py      (or: pytest tests/)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import threads_build as t  # noqa: E402

# the body that went out on 1/11/2026 at 12:00
BAD_1101 = ("APOD Science APOD APOD: 2026 November 1 –… Today’s APOD Archive Submissions Index Search Calendar RSS "
            "Education About Discuss APOD Astronomy Picture of the Day Discover the cosmos! Each day a different image "
            "or photograph of our fascinating universe is featured, along with a brief explanation written by a "
            "professional astronomer. Colors of the Moon Explanation: What color is the Moon?")
GOOD = ("What color is the Moon? It depends on the night – and the time. Outside of the Earth's atmosphere, the dark "
        "Moon, which shines by reflected sunlight, appears a magnificently brown-tinged gray.")


def test_menu_text_rejected():
    assert t.bad_text(BAD_1101)


def test_menu_words_without_phrases_rejected():
    assert t.bad_text("Archive Submissions Index Search Calendar RSS Education About Discuss and a long tail of words here.")


def test_short_or_cut_rejected():
    assert t.bad_text("What color is the Moon?")
    assert t.bad_text("Webb has found carbon dioxide in the atmosphere of a planet orbiting a star 700 light-years and")


def test_clean_text_passes():
    assert t.bad_text(GOOD) is None
    # one ordinary word that is also a menu word is fine
    assert t.bad_text("Astronomers search the archive of Hubble images for faint comets and found 12 new ones last year.") is None


def test_apod_explanation_cut():
    page = ("Discover the cosmos! Colors of the Moon Explanation: What color is the Moon? It depends on the night -- and "
            "the time. Tomorrow's picture: open space Date: November 1, 2026")
    assert t.apod_explanation(page) == "What color is the Moon? It depends on the night – and the time."


def test_plain_keeps_words_whole():
    assert t.plain('appears a <a href="x">magnificent</a>ly gray <a href="y">Moon</a>, by light.') == \
        "appears a magnificently gray Moon, by light."


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
