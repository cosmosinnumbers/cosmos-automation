"""Full-bleed Shorts (15/11/2026): 9:16 framings, focus, captions, Scale Compare rule."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import director  # noqa: E402
import fullbleed  # noqa: E402


def _img(tmp_path, size=(1600, 900), spot=(1300, 450)):
    im = Image.new("RGB", size, (5, 5, 12))
    d = ImageDraw.Draw(im)
    d.ellipse((spot[0] - 120, spot[1] - 120, spot[0] + 120, spot[1] + 120), fill=(250, 220, 160))
    p = tmp_path / "a.jpg"
    im.save(p)
    return p


def test_focus_finds_the_subject(tmp_path):
    im = Image.open(_img(tmp_path))
    fx, _ = fullbleed.focus(im, 0.3, 1.0)
    assert fx > 0.65          # the bright disc is on the right


def test_visual_fills_the_frame_and_changes_framing(tmp_path):
    v = fullbleed.Visual(_img(tmp_path), "image")
    a, b = v.frame(0, 0.0), v.frame(1, 0.5)
    assert a.size == (1080, 1920) and b.size == (1080, 1920)
    assert a.tobytes() != b.tobytes()
    # the subject (right side of the source) is inside the crop: the frame is not all dark
    assert max(a.convert("L").getdata()) > 200


def test_boxes_stay_inside_the_canvas(tmp_path):
    for size in ((1600, 900), (900, 900), (700, 1400), (2000, 1000)):
        v = fullbleed.Visual(_img(tmp_path, size, (size[0] // 2, size[1] // 2)), "image")
        for sub in range(8):
            for p in (0.0, 0.5, 1.0):
                x0, y0, x1, y1 = v._box(sub, p)
                assert x0 >= -0.01 and y0 >= -0.01 and x1 <= v.size[0] + 0.01 and y1 <= v.size[1] + 0.01
                assert abs((x1 - x0) / (y1 - y0) - 9 / 16) < 0.01


def test_charts_and_panoramas_stay_whole(tmp_path):
    assert fullbleed.Visual(_img(tmp_path), "chart").mode == "contain"
    assert fullbleed.Visual(_img(tmp_path), "image", fit="contain").mode == "contain"
    assert fullbleed.Visual(_img(tmp_path, (3000, 900), (1500, 450)), "image").mode == "contain"   # panorama


def test_caption_chunks_have_no_orphans():
    timings = {"segments": [{"sentences": [{"text": "A star 33 times heavier than our Sun", "start": 0.0, "end": 3.0}]}]}
    caps = fullbleed.caption_chunks(timings)
    assert all(len(c[2]) >= 2 for c in caps)
    assert sum(len(c[2]) for c in caps) == 8
    assert caps[0][0] == 0.0 and abs(caps[-1][1] - 3.0) < 1e-6


def test_compare_info():
    c = director.compare_info("You would melt near a star 33 times heavier than our Sun.")
    assert c["value"] == 33 and c["word"] == "heavier" and c["refName"] == "the Sun"
    assert "ref" not in c                       # `ref` is reserved by React: the scene would crash
    assert director.compare_info("A planet 24.55 times heavier than Jupiter")["decimals"] == 2
    assert director.compare_info("It is 1,300 times bigger than Earth") is None      # too many dots
    assert director.compare_info("It grew 5 times in 2020") is None


def test_short_plan_uses_scale_compare():
    sents = [("You would melt near a star 33 times heavier than our Sun.", 0.0, 3.6),
             ("And the secret behind its blasts is stranger than its size.", 3.9, 7.5),
             ("Astronomers studied this unstable star inside a galaxy.", 7.8, 12.0),
             ("These observations explain how massive stars evolve.", 12.3, 30.0)]
    timings = {"duration": 30.0, "segments": [{"sentences": [{"text": t, "start": a, "end": b} for t, a, b in sents]}]}
    plan = director.plan_short({"sources_full": []}, timings)
    assert any(i["effect"] == "scalecompare" for i in plan["inserts"])
    assert not any(i["effect"] == "charts" for i in plan["inserts"])
