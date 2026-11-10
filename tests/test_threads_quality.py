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


# Short of 10/11/2026 (clip of a long video): the 21:00 post said "Source: NASA" and ended on "Here is your first guess."
CLIP_1110 = {"tag": "c1110-ess-clip-a", "title": "How long does our Sun have left? #shorts",
             "narration": ("How long do you think our Sun has left? The honest answer is stranger than any doomsday "
                           "movie. ESA's article on Gaia gives our Sun an age of around 4.57 billion years: in its "
                           "comfortable middle age. By the end you'll know what Gaia's study of Sun-like stars says "
                           "happens to our Sun as it ages. Here is your first guess. What ends first: life on Earth, "
                           "the planet Mercury, or the Sun itself? Right now the Sun is stable. It fuses hydrogen into "
                           "helium in a core of about 15 million degrees Celsius."),
             "source_list": [{"title": "Full video: The Sun Will Swell 200 Times Wider: How It All Ends",
                              "url": "https://youtu.be/u7PXkWj6q9c"}]}


def test_clip_source_from_narration_not_default_nasa():
    assert t.source_line(CLIP_1110) == "Source: ESA."


def test_source_from_agency_url_first():
    s = dict(CLIP_1110, source_list=[{"title": "x", "url": "https://youtu.be/a"},
                                     {"title": "y", "url": "https://www.eso.org/public/news/eso2601/"}])
    assert t.source_line(s) == "Source: ESO."


def test_no_agency_points_to_full_video():
    s = dict(CLIP_1110, narration="The Sun is a star. It is big.")
    assert "YouTube" in t.source_line(s) and "NASA" not in t.source_line(s)


def test_post_never_ends_on_lead_in():
    text = t.fit(["How long does our Sun have left?", CLIP_1110["narration"], "Source: ESA.\n" + t.DISCLOSURE], 500)
    body = text.split("\n\n")[1]
    assert not body.endswith("Here is your first guess.")
    assert len(text) <= 500


def test_video_reply_not_labelled_source():
    t.host_video = lambda tag: None
    from datetime import datetime
    it = t.video(datetime(2026, 11, 10), CLIP_1110)
    assert it["replies"][0].startswith("Full video:")
    assert "Source: NASA" not in it["text"] and "Source: ESA." in it["text"]
