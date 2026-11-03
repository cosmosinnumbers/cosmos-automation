import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import video_qc as q  # noqa: E402


def make(path, video, audio, dur=30, size="1080x1920"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"{video}{':' if '=' in video else '='}s={size}:r=30:d={dur}",
                    "-f", "lavfi", "-i", audio, "-t", str(dur), "-pix_fmt", "yuv420p", "-shortest", str(path)], check=True)


def test_good_video_passes():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ok.mp4"
        # moving test pattern + a tone around -14 LUFS
        make(p, "testsrc2", f"sine=f=440:d=30,volume=2.3")
        r = q.analyse(str(p), "short")
        assert not [e for e in r["errors"] if "loudness" in e or "audio" in e or "static" in e or "black" in e], r
        assert r["metrics"]["duration"] > 29


def test_static_silent_video_is_blocked():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bad.mp4"
        make(p, "color=c=black", "anullsrc=r=44100:cl=stereo", dur=30)
        r = q.analyse(str(p), "short")
        txt = " ".join(r["errors"])
        assert r["errors"] and r["score"] == 0, r
        assert "silent" in txt and ("black" in txt or "static" in txt), r


def test_wrong_size_and_duration():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "tiny.mp4"
        make(p, "testsrc2", "sine=f=440:d=5,volume=2.3", dur=5, size="640x360")
        r = q.analyse(str(p), "short")
        assert any("1080x1920" in e for e in r["errors"]) and any("duration" in e for e in r["errors"])


def test_loop_echo_warning():
    s = {"narration": "A day on Venus is longer than its year. It lasts 243 days. The reason is strange. Thanks."}
    assert q.words("Venus day year") & q.words("A day on Venus")
    assert not (q.words(s["narration"].split(". ")[0]) & q.words("Thanks."))


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print(n, "ok")
