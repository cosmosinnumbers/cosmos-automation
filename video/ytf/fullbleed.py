"""Full-bleed vertical layout for the Shorts (owner 15/11/2026: "voglio più visual subito sui miei video").

Before: the footage sat in a 1080x900 box (47% of the frame) between a headline band and a caption band.
Now the picture fills the whole 1080x1920 frame, like the Shorts that travel in this niche:
  - every clip and image is cropped to 9:16 around its most interesting area (focus(): edges + brightness)
  - a visual is never held still: every SUB_S seconds the framing changes (push-in, detail, pan, pull-out), so one
    NASA picture gives three different shots and the viewer sees a cut every ~2.5 s
  - charts, `fit: contain` pictures and very wide panoramas stay whole on a blurred copy of themselves
  - headline and captions sit on top of the picture over a soft dark gradient, inside the safe area of
    Shorts/Reels/TikTok (nothing important in the bottom 20% or under the right-hand buttons)
  - captions: 3 words at a time, the spoken word bigger and amber with a pop
  - the first half second is a zoom burst + flash with the headline slamming in word by word (the hook)
short.yaml `layout: box` (or env SHORT_LAYOUT=box) gives the old boxed layout back.
"""
from __future__ import annotations

import base64
import io
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

import render
from common import BRAND, FPS, ffmpeg_exe, font

SW, SH = 1080, 1920
SUB_S = 2.6                 # target seconds of one framing
RW, RH = 1708, 960          # clips are read at this size (16:9 cover) and cropped per frame
CAP_Y = 1270                # captions: above the title/buttons area of the apps
HEAD_Y = 170                # headline: below the top bar of the apps
EQ_FULL = "eq=saturation=1.12:contrast=1.07"   # footage look: a touch more punch (the box layout dimmed it)

# framing patterns: (name, zoom from, zoom to, pan from, pan to); pan in units of the free travel (-1..1)
PATTERNS = {
    "image": [("push", 1.00, 1.14, 0.0, 0.0), ("detail", 1.36, 1.46, 0.55, 0.75), ("pan", 1.08, 1.08, -0.8, 0.8),
              ("pull", 1.30, 1.08, -0.35, 0.0)],
    "video": [("push", 1.00, 1.06, 0.0, 0.0), ("detail", 1.20, 1.24, 0.6, 0.6), ("pan", 1.04, 1.04, -0.6, 0.6),
              ("pull", 1.16, 1.04, -0.4, 0.0)],
    "contain": [("push", 1.00, 1.05, 0.0, 0.0), ("pull", 1.06, 1.01, 0.0, 0.0)],
}


def focus(img: Image.Image, fw: float, fh: float) -> tuple[float, float]:
    """Centre (0..1, 0..1) of the fw x fh window (fractions of the image) with the most detail: edges plus bright
    areas, so a planet, a spacecraft or a face is not cut off by the 9:16 crop. Flat pictures give the centre."""
    g = np.asarray(img.convert("L").resize((96, 96), Image.BILINEAR)).astype(np.float32) / 255.0
    e = np.abs(np.diff(g, axis=0, prepend=g[:1])) + np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    e = e + 0.35 * np.clip(g - g.mean(), 0, 1)
    out = []
    for axis, frac in ((0, fw), (1, fh)):          # columns for x, rows for y
        prof = e.sum(axis=axis)
        n = max(1, min(96, round(96 * frac)))
        if n >= 96 or prof.sum() < 1e-3:
            out.append(0.5)
            continue
        c = np.convolve(prof, np.ones(n), mode="valid")
        centre = 1 - np.abs(np.linspace(-1, 1, len(c))) * 0.12     # light preference for the middle
        k = int(np.argmax(c * centre))
        out.append((k + n / 2) / 96)
    return out[0], out[1]


class Visual:
    """One entry of short.yaml `visuals`, ready to give 1080x1920 frames."""

    def __init__(self, path: Path, kind: str, start: float = 0.0, fit: str | None = None, credit: str = "",
                 label: str | None = None, index: int = 0):
        self.credit, self.label, self.index = credit, label, index
        self.is_video = kind == "video"
        self.reader = None
        if self.is_video:
            self.mode = "video"
            self.reader = render.VideoReader(path, RW, RH, start, eq=EQ_FULL)
            self.canvas = None
            self.size = (RW, RH)
            self.fx, self.fy = 0.5, 0.5
            self._still_src = (path, start)
            return
        img = Image.open(path).convert("RGB")
        ar = img.width / img.height
        if kind == "chart" or fit == "contain" or ar > 2.4:   # a 9:16 crop of a panorama shows 15% of it: noise
            self.mode = "contain"
            self.canvas = contain_canvas(img, kind)
            self.fx, self.fy = 0.5, 0.5
        else:
            self.mode = "image"
            img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.08)).enhance(1.05)
            s = max(SH * 1.15 / img.height, SW * 1.15 / img.width)
            img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
            hh = min(img.height, img.width * 16 / 9)
            self.fx, self.fy = focus(img, hh * 9 / 16 / img.width, hh / img.height)
            self.canvas = img
        self.size = self.canvas.size

    def _box(self, sub: int, p: float) -> tuple[float, float, float, float]:
        pats = PATTERNS[self.mode]
        name, z0, z1, a0, a1 = pats[(sub + self.index) % len(pats)]
        if (self.index + sub // len(pats)) % 2:      # mirror the sideways moves every other time
            a0, a1 = -a0, -a1
        e = render.ease(p)
        z = z0 + (z1 - z0) * e
        pan = a0 + (a1 - a0) * (p if name == "pan" else e)     # a pan travels at constant speed
        wc, hc = self.size
        hh = min(hc, wc * 16 / 9)
        hw = hh * 9 / 16
        w, h = hw / z, hh / z
        travel = min((wc - w) / 2, 0.24 * wc)
        cx = min(max(self.fx * wc + pan * travel, w / 2), wc - w / 2)
        cy = min(max(self.fy * hc, h / 2), hc - h / 2)
        return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2

    def frame(self, sub: int, p: float) -> Image.Image:
        src = self.reader.next() if self.is_video else self.canvas
        return src.resize((SW, SH), Image.BILINEAR, box=self._box(sub, min(1.0, max(0.0, p))))

    def skip(self):
        """Under a full-screen scene: keep the clip running so the footage resumes in sync with the voice."""
        if self.is_video:
            self.reader.next()

    def still(self, at: float = 0.0) -> Image.Image:
        """A 9:16 still of this visual (for the background of a scene or a cover), without touching the reader."""
        if not self.is_video:
            return self.canvas.resize((SW // 2, SH // 2), Image.BILINEAR, box=self._box(0, 0.5))
        path, start = self._still_src
        r = subprocess.run([ffmpeg_exe(), "-loglevel", "error", "-ss", f"{start + max(0.0, at):.2f}", "-i", str(path),
                            "-frames:v", "1", "-vf", f"scale={RW}:{RH}:force_original_aspect_ratio=increase,crop={RW}:{RH}",
                            "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=90)
        img = Image.open(io.BytesIO(r.stdout)).convert("RGB")
        return img.resize((SW // 2, SH // 2), Image.BILINEAR, box=self._box(0, 0.5))

    def close(self):
        if self.reader:
            self.reader.close()


def contain_canvas(img: Image.Image, kind: str) -> Image.Image:
    """Charts, infographics and banners stay whole: the picture across the full width, on a blurred, darkened
    copy of itself (charts: on the brand background)."""
    cw, ch = round(SW * 1.08), round(SH * 1.08)
    if kind == "chart":
        bg = Image.new("RGB", (cw, ch), BRAND["space"])
    else:
        s = max(cw / img.width, ch / img.height)
        bg = img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.BILINEAR)
        x, y = (bg.width - cw) // 2, (bg.height - ch) // 2
        bg = bg.crop((x, y, x + cw, y + ch)).filter(ImageFilter.GaussianBlur(36))
        bg = Image.blend(bg, Image.new("RGB", bg.size, BRAND["space"]), 0.45)
    s = min(cw * 0.94 / img.width, ch * 0.5 / img.height)
    fg = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    bg.paste(fg, ((cw - fg.width) // 2, round(ch * 0.47 - fg.height / 2)))
    return bg


def data_uri(img: Image.Image, w: int = 540) -> str:
    img = img.convert("RGB").resize((w, max(1, round(img.height * w / img.width))), Image.BILINEAR)
    b = io.BytesIO()
    img.save(b, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def scrim() -> Image.Image:
    """Dark gradient under the headline (top) and under the captions (bottom) plus a light vignette: the text is
    readable on any picture and the middle of the frame stays clean."""
    y = np.arange(SH, dtype=np.float32)[:, None]
    x = np.arange(SW, dtype=np.float32)[None, :]
    top = np.clip(1 - y / 640, 0, 1) ** 1.6 * 205
    bot = np.clip((y - 1000) / 760, 0, 1) ** 1.3 * 225
    vig = np.clip((np.hypot((x - SW / 2) / (SW * 0.75), (y - SH / 2) / (SH * 0.75)) - 0.55) / 0.6, 0, 1) * 110
    a = np.clip(np.maximum(np.maximum(top, bot) + np.zeros_like(x), vig), 0, 255).astype(np.uint8)
    out = np.zeros((SH, SW, 4), np.uint8)
    out[..., :3] = (5, 8, 20)
    out[..., 3] = a
    return Image.fromarray(out, "RGBA")


# ---------- text ----------
_FONTS: dict[int, object] = {}


def _f(size: int):
    size = int(round(size / 2) * 2)
    if size not in _FONTS:
        _FONTS[size] = font("display", size, 700)
    return _FONTS[size]


def caption_chunks(timings: dict, n: int = 3) -> list[tuple[float, float, list[tuple[float, str]]]]:
    """Caption chunks of up to n words with the start time of every word. A lonely last word joins the chunk
    before it (no one-word orphan flashes)."""
    import director
    out = []
    for seg in timings["segments"]:
        for s in seg["sentences"]:
            wt = director.word_times(s)
            groups = [wt[i:i + n] for i in range(0, len(wt), n)]
            if len(groups) > 1 and len(groups[-1]) == 1 and len(groups[-1][0][1]) <= 6:
                groups[-2] = groups[-2] + groups.pop()
            for gi, g in enumerate(groups):
                end = groups[gi + 1][0][0] if gi + 1 < len(groups) else s["end"]
                out.append((g[0][0], end, g))
    return out


def _pop(dt: float, dur: float = 0.14) -> float:
    """0 -> 1 with a small overshoot: the pop of a word or a chunk."""
    x = min(1.0, max(0.0, dt / dur))
    return 1 - (1 - x) ** 3 + 0.35 * math.sin(math.pi * x) * (1 - x)


def draw_caption(d: ImageDraw.ImageDraw, caps, t: float, size: int = 90, y0: int = CAP_Y):
    """The chunk under the voice, centred. The spoken word is amber and bigger (it pops when it starts); the
    whole chunk pops in when it appears."""
    cur = next((c for c in caps if c[0] <= t < c[1]), None)
    if not cur:
        return
    words = cur[2]
    k = 0.86 + 0.14 * _pop(t - cur[0], 0.12)
    base = _f(size * k)
    space = d.textbbox((0, 0), " ", font=base)[2] * 0.9
    spoken = max((wt for wt, _ in words if wt <= t), default=None)
    items = []
    for wt, w in words:
        now = wt == spoken
        f = _f(size * k * (1.0 + 0.16 * _pop(t - wt))) if now else base
        items.append((w, f, now, d.textbbox((0, 0), w, font=f)[2]))
    lines, line, lw = [], [], 0.0
    for it in items:
        if line and lw + space + it[3] > SW - 150:
            lines.append((line, lw)); line, lw = [], 0.0
        lw += (space if line else 0) + it[3]
        line.append(it)
    lines.append((line, lw))
    y = y0
    for line, lw in lines:
        x = (SW - lw) / 2
        for w, f, now, ww in line:
            yy = y + (base.size - f.size) * 0.6
            d.text((x + 4, yy + 6), w, font=f, fill=(0, 0, 0), stroke_width=9, stroke_fill=(0, 0, 0))   # soft drop
            d.text((x, yy), w, font=f, fill=BRAND["amber"] if now else BRAND["star"], stroke_width=8,
                   stroke_fill=(0, 0, 0))
            x += ww + space
        y += round(base.size * 1.16)


class Headline:
    """The headline on top of the picture: slams in word by word during the hook, then stays."""

    def __init__(self, text: str, tag: str | None = None, size: int = 78):
        self.tag = tag
        d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
        words = text.upper().split()
        while True:
            f = _f(size)
            space = d.textbbox((0, 0), " ", font=f)[2]
            lines, cur, lw = [], [], 0
            for w in words:
                ww = d.textbbox((0, 0), w, font=f)[2]
                if cur and lw + space + ww > SW - 130:
                    lines.append((cur, lw)); cur, lw = [], 0
                lw += (space if cur else 0) + ww
                cur.append((w, ww))
            lines.append((cur, lw))
            if len(lines) <= 3 or size <= 56:
                break
            size -= 6
        self.f, self.space = f, space
        self.words = []          # (word, x, y)
        y = HEAD_Y + (64 if tag else 0)
        for line, lw in lines:
            x = (SW - lw) // 2
            for w, ww in line:
                self.words.append((w, x, y))
                x += ww + space
            y += round(f.size * 1.1)
        self.bottom = y
        self.step = min(0.09, 0.7 / max(1, len(self.words)))

    def draw(self, frame: Image.Image, t: float):
        d = ImageDraw.Draw(frame)
        if self.tag:
            tf = _f(30)
            b = d.textbbox((0, 0), self.tag, font=tf)
            w, h = b[2] - b[0] + 44, 50
            a = _pop(t - 0.05, 0.2)
            x, y = (SW - w) // 2, HEAD_Y - 6 - round((1 - a) * 30)
            if a > 0.05:
                d.rounded_rectangle((x, y, x + w, y + h), radius=25, fill=BRAND["amber"])
                d.text((x + 22 - b[0], y + (h - (b[3] - b[1])) // 2 - b[1]), self.tag, font=tf, fill=BRAND["space"])
        for i, (w, x, y) in enumerate(self.words):
            dt = t - (0.12 + i * self.step)
            if dt < 0:
                break
            a = _pop(dt, 0.16)
            fresh = dt < 0.1                      # the word that has just landed is white, then turns amber
            f = self.f if dt > 0.16 else _f(self.f.size * (1.25 - 0.25 * a))
            d.text((x - (f.size - self.f.size) * 0.3, y - (f.size - self.f.size) * 0.5), w, font=f,
                   fill=BRAND["star"] if fresh else BRAND["amber"], stroke_width=6, stroke_fill=(0, 0, 0))

    def hits(self) -> list[float]:
        return [0.12 + i * self.step for i in range(len(self.words))]


def hook_burst(frame: Image.Image, t: float) -> Image.Image:
    """First 0.4 s: the picture crashes in from a 1.35x zoom and a white flash fades (the scroll-stopper)."""
    if t >= 0.4:
        return frame
    e = 1 - (1 - t / 0.4) ** 3
    z = 1.35 - 0.35 * e
    bw, bh = SW / z, SH / z
    f = frame.resize((SW, SH), Image.BILINEAR, box=((SW - bw) / 2, (SH - bh) / 2, (SW + bw) / 2, (SH + bh) / 2))
    if t < 0.2:
        f = Image.blend(f, Image.new("RGB", f.size, (247, 250, 252)), 0.55 * (1 - t / 0.2))
    return f


def small_text(d: ImageDraw.ImageDraw, xy, text: str, size: int = 24):
    d.text(xy, text, font=font("text", size, 600), fill=(215, 220, 232), stroke_width=3, stroke_fill=(0, 0, 0))


def label_pill(d: ImageDraw.ImageDraw, xy, text: str):
    f = _f(26)
    b = d.textbbox((0, 0), text, font=f)
    x, y = xy
    d.rounded_rectangle((x, y, x + b[2] - b[0] + 32, y + 46), radius=8, fill=BRAND["amber"])
    d.text((x + 16 - b[0], y + 23 - (b[3] - b[1]) / 2 - b[1]), text, font=f, fill=BRAND["space"])
