"""No text that stays (owner 21/11/2026): headline fades out, clips go full screen, clean covers."""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video" / "ytf"))
sys.path.insert(0, str(ROOT / "tools"))
import clip  # noqa: E402
import clip_full  # noqa: E402
import fullbleed  # noqa: E402


def test_headline_fades_out():
    h = fullbleed.Headline("A star spinning 261 times a second", "NASA · NEW")
    assert h.visible(1.0)
    assert 2.0 < h.out_at < 3.2
    assert not h.visible(h.out_at + fullbleed.HEAD_FADE + 0.01)
    f = Image.new("RGB", (1080, 1920), (40, 40, 40))
    h.draw(f, 1.5)
    assert np.asarray(f).std() > 0                      # drawn while visible
    g = Image.new("RGB", (1080, 1920), (40, 40, 40))
    h.draw(g, 6.0)
    assert np.asarray(g).std() == 0                     # nothing on screen afterwards


def test_clip_layout_default_is_full(monkeypatch):
    monkeypatch.delenv("CLIP_LAYOUT", raising=False)
    assert clip.layout() == "full"
    monkeypatch.setenv("CLIP_LAYOUT", "box")
    assert clip.layout() == "box"


def test_caption_chunks_from_srt():
    caps = [(10.0, 12.0, "Some planned passes may come within"), (12.2, 14.0, "twenty-five kilometers of it.")]
    ch = clip_full.caption_chunks(caps, 10.0, 5.0)
    words = [w for c in ch for _, w in c[2]]
    assert words == "Some planned passes may come within twenty-five kilometers of it.".split()
    assert all(len(c[2]) <= 4 for c in ch)
    assert ch[0][0] == 0.0 and ch[-1][1] == 4.0
    starts = [t for c in ch for t, _ in c[2]]
    assert starts == sorted(starts)


def test_subject_ignores_generic_words():
    assert clip_full.subject("Juno's Ganymede Close-up", "img_ganymede") == {"juno", "ganymede"}


def test_assign_prefers_pictures_the_clip_names(tmp_path):
    pics = [{"key": k, "words": w} for k, w in (("img_europa", {"europa"}), ("img_callisto", {"callisto"}),
                                                ("img_clipper", {"clipper"}))]
    shots = [{"t0": 0, "t1": 5, "graphic": True}, {"t0": 5, "t1": 10, "graphic": True},
             {"t0": 10, "t1": 15, "graphic": False}]
    caps = [(0, 5, "Clipper flies past Europa"), (5, 10, "close to the surface"), (10, 15, "of Europa")]
    clip_full.assign(shots, pics, caps, 0.0)
    got = [s.get("pic", {}).get("key") for s in shots]
    assert "img_callisto" not in got                    # never a moon the clip does not talk about
    assert got[0] != got[1] and got[2] is None


def test_analyse_splits_graphics_from_pictures(tmp_path):
    ff = clip.ffmpeg_exe()
    mp4 = tmp_path / "long.mp4"
    navy = "0x0b1026"
    r = subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:d=2:r=30",
                        "-f", "lavfi", "-i", f"color={navy}:s=320x180:d=2:r=30", "-filter_complex",
                        "[0][1]concat=n=2:v=1", "-pix_fmt", "yuv444p", str(mp4)], capture_output=True)
    assert r.returncode == 0, r.stderr
    shots = clip_full.analyse(mp4, 0.0, 4.0)
    assert [s["graphic"] for s in shots] == [False, True]
    assert abs(shots[1]["t0"] - 2.0) < 0.1


def test_cover_is_full_frame(tmp_path):
    import reel_cover
    mp4 = tmp_path / "c.mp4"
    subprocess.run([reel_cover.ffmpeg(), "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=540x960:d=3",
                    "-pix_fmt", "yuv420p", str(mp4)], check=True)
    out = Image.open(reel_cover.build(str(mp4), "Why Clipper won't orbit Europa", tmp_path / "c.jpg"))
    a = np.asarray(out.convert("RGB")).astype(int)
    assert out.size == (1080, 1920)
    assert a[300:900].std() > 40                        # the top half is the sharp frame, not a dark card
