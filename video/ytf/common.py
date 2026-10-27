"""Shared paths, brand constants and small helpers for the Cosmos in Numbers pipeline."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "assets" / "fonts"
W, H, FPS = 1920, 1080, 30

BRAND = {
    "space": (11, 16, 38),       # #0B1026
    "cyan": (79, 209, 197),      # #4FD1C5
    "amber": (246, 173, 85),     # #F6AD55
    "star": (247, 250, 252),     # #F7FAFC
    "dust": (138, 148, 166),     # #8A94A6
}
HEX = {k: "#%02X%02X%02X" % v for k, v in BRAND.items()}

CHANNEL = "Cosmos in Numbers"


def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, **kw)
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace") if isinstance(r.stderr, bytes) else r.stderr
        sys.exit(f"command failed ({r.returncode}): {' '.join(map(str, cmd[:6]))} ...\n{err[-2000:]}")
    return r


def media_duration(path: Path) -> float:
    import re
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True)
    m = re.search(rb"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        sys.exit(f"cannot read duration of {path}")
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=100)


def load_json(path: Path):
    return json.loads(Path(path).read_text("utf-8"))


def save_json(path: Path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


@lru_cache(maxsize=64)
def font(kind: str, size: int, weight: int = 400):
    """kind: 'display' (Space Grotesk) or 'text' (Inter). Static instances cut from the
    OFL variable fonts (see assets/fonts), picked by nearest weight."""
    from PIL import ImageFont
    if kind == "display":
        name = "SpaceGrotesk-Bold.ttf" if weight >= 600 else "SpaceGrotesk-Medium.ttf"
    else:
        name = "Inter-Bold.ttf" if weight >= 700 else "Inter-SemiBold.ttf" if weight >= 550 else "Inter-Regular.ttf"
    return ImageFont.truetype(str(FONTS / name), size)


def setup_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager
    for p in FONTS.glob("*-*.ttf"):  # static instances only
        font_manager.fontManager.addfont(str(p))
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": HEX["space"], "axes.facecolor": HEX["space"],
        "savefig.facecolor": HEX["space"], "text.color": HEX["star"],
        "axes.labelcolor": HEX["star"], "xtick.color": HEX["dust"], "ytick.color": HEX["dust"],
        "axes.edgecolor": HEX["dust"], "font.family": "Inter", "font.size": 22,
        "axes.titlesize": 34, "axes.titleweight": "bold", "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.color": "#1E2748",
        "grid.linewidth": 1.0,
    })
    return plt


def env_espeak():
    """Point phonemizer at a system eSpeak NG on Windows if one is installed; elsewhere
    (or without it) kokoro-onnx falls back to the library bundled by espeakng-loader."""
    dll = Path(r"C:\Program Files\eSpeak NG\libespeak-ng.dll")
    if dll.exists():
        os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", str(dll))
