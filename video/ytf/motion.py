"""Bridge between the Python renderer and the Remotion scenes in motion/ (the 11 effects).

  render_jobs(jobs, workdir) -> {out_path: True}   batch render, one Chrome session
  tiles(clips_or_images)    -> [data URI]          stills of our own footage for the cards of the scenes
  glitch(frame, k, n, seed) / zoom_out(frame, p) / zoom_in(frame, p)
                                                    the Glitch (10) and Zoom-through (03) transitions applied to the
                                                    live frames at a cut between two real clips
  whip_out(frame, p) / whip_in(frame, p) / dither(frame, k, n)
                                                    the Katana whip-pan and 1-bit dither transitions, same idea
  typewriter_keys(text, fps, start)                 keystroke frames (scene props) = click times (sound design)

If Node or the motion/ project are missing, or a scene fails, the caller keeps the plain footage: a video is never
lost because of an effect.
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from common import ROOT, ffmpeg_exe

MOTION = ROOT / "motion"

# frames of each scene when the director gives no length (30 fps)
DEFAULT_FRAMES = {"orbit": 54, "vertigo": 75, "zoomthrough": 10, "headlines": 90, "papercut": 90, "charts": 90,
                  "phonescreens": 75, "framebreak": 75, "pullback": 75, "glitch": 8, "typewriter": 90,
                  # Katana kit (06/11/2026): kinetic slam type, 1-bit impact frame, product-launch light sweep,
                  # rapid flash-cut montage
                  "katanatype": 75, "impactframe": 66, "lightsweep": 84, "flashcuts": 75}
EFFECTS = tuple(DEFAULT_FRAMES)


def available() -> bool:
    if os.environ.get("MOTION_DISABLED") == "1":
        return False
    return bool(shutil.which("node")) and (MOTION / "node_modules" / "@remotion" / "renderer").exists()


def render_jobs(jobs: list[dict], workdir: Path, timeout: int = 1500) -> dict[str, bool]:
    """jobs: [{effect, out, props}] (props carry width/height/fps/frames). Returns {out: True} for the ones that
    rendered. Never raises."""
    if not jobs or not available():
        if jobs:
            print("  motion: Remotion not available, effects skipped")
        return {}
    workdir.mkdir(parents=True, exist_ok=True)
    jf = workdir / "motion_jobs.json"
    jf.write_text(json.dumps(jobs), "utf-8")
    try:
        r = subprocess.run(["node", str(MOTION / "render.mjs"), str(jf)], capture_output=True, text=True,
                           timeout=timeout, cwd=str(MOTION))
    except (subprocess.TimeoutExpired, OSError) as e:
        print("  motion: render failed:", e)
        return {}
    done = {}
    for line in r.stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("ok") and Path(d["ok"]).exists():
            done[d["ok"]] = True
            print(f"  motion: {d['effect']} {d['s']:.1f}s")
        elif d.get("fail"):
            print(f"  motion: {d['effect']} FAILED {d['error'][:200]}")
    if r.returncode and not done:
        print("  motion: node exited", r.returncode, r.stderr[-800:])
    return done


def _uri(img: Image.Image, w: int = 360) -> str:
    img = img.convert("RGB")
    img = img.resize((w, max(1, round(img.height * w / img.width))), Image.LANCZOS)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def tiles(sources: list[tuple[Path, str, float]], per_clip: int = 3, limit: int = 12) -> list[str]:
    """sources: [(path, 'video'|'image', start_s)]. Stills of our own (public-domain) footage as small JPEG data
    URIs, for the cards of the scenes."""
    out = []
    for path, kind, start in sources:
        try:
            if kind == "image":
                out.append(_uri(Image.open(path)))
                continue
            for k in range(per_clip):
                t = start + 1.0 + k * 2.5
                r = subprocess.run([ffmpeg_exe(), "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(path),
                                    "-frames:v", "1", "-vf", "scale=480:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                                   capture_output=True, timeout=60)
                if r.stdout:
                    out.append(_uri(Image.open(io.BytesIO(r.stdout))))
        except Exception as e:  # noqa: BLE001 - a missing still only means a generated card
            print("  motion: still skipped", path, e)
        if len(out) >= limit:
            break
    return out[:limit]


def typewriter_keys(text: str, fps: int = 30, start: int = 6, cps: float = 22.0, seed: int = 1) -> list[float]:
    """Frame of each keystroke: natural speed with small jitter, a short pause after spaces and punctuation."""
    rng = np.random.default_rng(seed)
    keys, f = [], float(start)
    for ch in text:
        keys.append(round(f, 2))
        step = fps / cps * rng.uniform(0.7, 1.3)
        if ch in " ":
            step *= 1.3
        if ch in ".,:!?\n":
            step *= 3.0
        f += step
    return keys


# ---------- live-frame transitions (same look as the Glitch and Zoom-through scenes) ----------
def glitch(frame: Image.Image, k: int, n: int = 8, seed: int = 0) -> Image.Image:
    """Frame k of n of the Glitch: red and blue split sideways, horizontal bands jump, scanlines; strongest in the
    middle of the n frames, clean at both ends."""
    a = np.asarray(frame).copy()
    h, w, _ = a.shape
    rng = np.random.default_rng(seed * 101 + k)
    amp = int((1 - abs((k + 0.5) / n - 0.5) * 2) * w * 0.035) + 2
    out = a.copy()
    out[..., 0] = np.roll(a[..., 0], amp, axis=1)
    out[..., 2] = np.roll(a[..., 2], -amp, axis=1)
    for _ in range(int(rng.integers(4, 10))):
        y0 = int(rng.integers(0, h - 4))
        bh = int(rng.integers(4, max(5, h // 14)))
        out[y0:y0 + bh] = np.roll(out[y0:y0 + bh], int(rng.integers(-w // 8, w // 8)), axis=1)
    out[::4] = (out[::4] * 0.75).astype(np.uint8)
    return Image.fromarray(out)


def _zoom(frame: Image.Image, s: float, blur: float) -> Image.Image:
    w, h = frame.size
    bw, bh = w / s, h / s
    f = frame.resize((w, h), Image.BILINEAR, box=((w - bw) / 2, (h - bh) / 2, (w + bw) / 2, (h + bh) / 2))
    return f.filter(ImageFilter.GaussianBlur(blur)) if blur > 0.5 else f


def zoom_out_of(frame: Image.Image, p: float) -> Image.Image:
    """Outgoing half of the Zoom-through: crash into the centre (p 0->1)."""
    return _zoom(frame, 1 + 3.5 * p ** 2.2, 14 * p ** 2)


def zoom_into(frame: Image.Image, p: float) -> Image.Image:
    """Incoming half: land in the new layer from 0.6 scale-up with a short flash (p 0->1)."""
    f = _zoom(frame, 1 + 0.6 * (1 - p) ** 3, 8 * (1 - p) ** 3)
    if p < 0.35:
        f = Image.blend(f, Image.new("RGB", f.size, (247, 250, 252)), 0.5 * (1 - p / 0.35))
    return f


# ---------- Katana kit transitions (06/11/2026) ----------
def _hblur(a: np.ndarray, px: int) -> np.ndarray:
    """Horizontal motion blur: average of `px` shifted copies (box blur along x), cheap enough per frame."""
    if px < 2:
        return a
    c = np.cumsum(np.pad(a.astype(np.float32), ((0, 0), (px, 0), (0, 0)), mode="edge"), axis=1)
    return ((c[:, px:] - c[:, :-px]) / px).astype(np.uint8)


def whip_out(frame: Image.Image, p: float) -> Image.Image:
    """Outgoing half of the whip pan: the picture slides left faster and faster, smeared by motion blur (p 0->1)."""
    a = np.asarray(frame.convert("RGB"))
    w = a.shape[1]
    e = p ** 2.4
    out = np.roll(a, -int(w * 0.45 * e), axis=1)
    return Image.fromarray(_hblur(out, int(w * 0.25 * e)))


def whip_in(frame: Image.Image, p: float) -> Image.Image:
    """Incoming half: the new picture arrives from the right with the blur settling to sharp (p 0->1)."""
    a = np.asarray(frame.convert("RGB"))
    w = a.shape[1]
    e = (1 - p) ** 2.4
    out = np.roll(a, int(w * 0.45 * e), axis=1)
    return Image.fromarray(_hblur(out, int(w * 0.25 * e)))


_BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) / 16.0


def dither(frame: Image.Image, k: int, n: int = 8, dark=(11, 16, 38), light=(247, 250, 252)) -> Image.Image:
    """Frame k of n of the 1-bit dither transition: the picture turns into a two-colour ordered-dither print
    (brand navy and white) at the middle of the n frames, with big pixels, then dissolves back to colour."""
    a = np.asarray(frame.convert("RGB")).astype(np.float32)
    h, w, _ = a.shape
    s = 1 - abs((k + 0.5) / n - 0.5) * 2            # 0 at the ends, 1 in the middle
    cell = max(2, int(round(2 + s * 4)))           # bigger pixels at the peak
    small = Image.fromarray(a.astype(np.uint8)).resize((max(1, w // cell), max(1, h // cell)), Image.BILINEAR)
    g = np.asarray(small.convert("L")).astype(np.float32) / 255.0
    g = np.clip((g - 0.5) * 1.6 + 0.5, 0, 1)
    th = np.tile(_BAYER, (g.shape[0] // 4 + 1, g.shape[1] // 4 + 1))[: g.shape[0], : g.shape[1]]
    bit = (g > th)[..., None]
    one = np.where(bit, np.array(light, np.float32), np.array(dark, np.float32))
    one = np.asarray(Image.fromarray(one.astype(np.uint8)).resize((w, h), Image.NEAREST)).astype(np.float32)
    mix = min(1.0, s * 1.6)
    return Image.fromarray((a * (1 - mix) + one * mix).astype(np.uint8))
