import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reel_cover  # noqa: E402


def test_key_number():
    assert reel_cover.key_number("The Sun you see is 8 minutes old") == "8 minutes"
    assert reel_cover.key_number("The Moon you see is 1.3 seconds old") == "1.3 seconds"
    assert reel_cover.key_number("45.22 km: the longest drive on another world") == "45.22 km"
    assert reel_cover.key_number("How long does our Sun have left?") is None


def test_clean_title():
    assert reel_cover.clean_title("Ghost Nebula #shorts\n\nFull video") == "Ghost Nebula"


def test_build_and_fallback(tmp_path, monkeypatch):
    mp4 = tmp_path / "clip.mp4"
    # grey first second, then a bright test pattern: the cover and the offset must skip the grey frame
    r = subprocess.run([reel_cover.ffmpeg(), "-loglevel", "error", "-f", "lavfi", "-i", "color=gray:s=270x480:d=1",
                        "-f", "lavfi", "-i", "testsrc=s=270x480:d=4", "-filter_complex", "[0][1]concat=n=2:v=1",
                        "-pix_fmt", "yuv420p", str(mp4)], capture_output=True)
    if r.returncode:
        import pytest
        pytest.skip("no ffmpeg")
    out = reel_cover.build(str(mp4), "The Sun you see is 8 minutes old", tmp_path / "c.jpg")
    from PIL import Image
    assert Image.open(out).size == (1080, 1920)
    assert reel_cover.best_offset(str(mp4)) > 1000
    monkeypatch.delenv("PAGES_TOKEN", raising=False)
    assert "thumb_offset" in reel_cover.for_reel(str(mp4), "x")
