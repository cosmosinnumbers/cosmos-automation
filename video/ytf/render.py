"""Frame-accurate 16:9 render: real images with slow camera moves, original charts,
title cards, on-screen credits, chapter lower-thirds, crossfades, ducked score.

Frames are drawn with Pillow and piped to ffmpeg (libx264). Output:
  <video>/build/video_noaudio.mp4, mix.wav, <video>/out/<id>.mp4, shots.json
"""
from __future__ import annotations

import json
import math
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import director
import motion
import music
import sfx
from common import BRAND, FPS, H, W, ffmpeg_exe, font, load_json, run, save_json

ZMAX = 1.12
XFADE = 12  # frames


# ---------- timeline ----------
def build_shots(script: dict, timings: dict) -> list[dict]:
    segs = timings["segments"]
    total = timings["duration"]
    shots = []
    for i, (seg, st) in enumerate(zip(script["segments"], segs)):
        t0 = 0.0 if i == 0 else st["start"]
        t1 = total if i == len(segs) - 1 else segs[i + 1]["start"]
        visuals = seg["visuals"]
        weights = seg.get("weights") or [1.0] * len(visuals)
        span, acc = t1 - t0, t0
        for j, (v, w) in enumerate(zip(visuals, weights)):
            d = span * w / sum(weights)
            shots.append({"start": acc, "end": acc + d, "visual": v, "segment": seg["id"],
                          "chapter": seg.get("chapter") if j == 0 else None})
            acc += d
    return shots


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# ---------- backgrounds ----------
@lru_cache(maxsize=4)
def starfield(seed: int = 11) -> Image.Image:
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(seed)
    cw, ch = int(W * ZMAX), int(H * ZMAX)
    base = np.zeros((ch, cw, 3), dtype=np.float32)
    base[:] = np.array(BRAND["space"], dtype=np.float32)
    # soft nebula: two low-frequency colour fields
    for col, amp in ((BRAND["cyan"], 0.10), ((120, 80, 200), 0.12)):
        f = gaussian_filter(rng.standard_normal((ch // 8, cw // 8)), 9)
        f = (f - f.min()) / (f.max() - f.min() + 1e-9)
        f = np.array(Image.fromarray((f * 255).astype(np.uint8)).resize((cw, ch), Image.BICUBIC), dtype=np.float32) / 255
        base += (f[..., None] ** 3) * np.array(col, dtype=np.float32) * amp
    stars = np.zeros((ch, cw), dtype=np.float32)
    n = 2600
    ys, xs = rng.integers(0, ch, n), rng.integers(0, cw, n)
    stars[ys, xs] = rng.pareto(2.2, n).clip(0, 6) * 60
    glow = gaussian_filter(stars, 1.2) * 3 + stars
    base += glow[..., None]
    return Image.fromarray(base.clip(0, 255).astype(np.uint8))


# ---------- visual preparation ----------
def dark_border(img: Image.Image):
    """Mean colour of a 2% frame when it is near-black (a space photo), else None.
    Such images extend into a plain field instead of a blurred copy, so no box shows."""
    w, h = img.size
    m = max(2, round(min(w, h) * 0.02))
    px = [img.crop(b).resize((1, 1), Image.BOX).getpixel((0, 0))
          for b in ((0, 0, w, m), (0, h - m, w, h), (0, 0, m, h), (w - m, 0, w, h))]
    if max(max(c) for c in px) > 14:
        return None
    return tuple(sum(c[i] for c in px) // 4 for i in range(3))


def prepare_image(path: Path, fit: str | None = None) -> Image.Image:
    """Return a ZMAX-sized 16:9 canvas. Wide images fill it; others (or fit='contain',
    used for infographics whose labels must stay visible) sit whole on a blurred copy."""
    img = Image.open(path).convert("RGB")
    cw, ch = int(W * ZMAX), int(H * ZMAX)
    ar = img.width / img.height
    if fit != "contain" and 1.3 <= ar <= 2.6:
        s = max(cw / img.width, ch / img.height)
        img = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.LANCZOS)
        x, y = (img.width - cw) // 2, (img.height - ch) // 2
        return img.crop((x, y, x + cw, y + ch))
    dark = dark_border(img)
    if dark:
        bg = Image.new("RGB", (cw, ch), dark)
    else:
        s = max(cw / img.width, ch / img.height)
        bg = img.resize((math.ceil(img.width * s), math.ceil(img.height * s)), Image.BILINEAR)
        x, y = (bg.width - cw) // 2, (bg.height - ch) // 2
        bg = bg.crop((x, y, x + cw, y + ch)).filter(ImageFilter.GaussianBlur(40))
        bg = Image.blend(bg, Image.new("RGB", bg.size, BRAND["space"]), 0.55)
    s = min(cw * 0.94 / img.width, ch * 0.94 / img.height)
    fg = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    bg.paste(fg, ((cw - fg.width) // 2, (ch - fg.height) // 2))
    return bg


def text_overlay(lines: list[tuple[str, object, tuple]], pad=(28, 16), bg=(0, 0, 0, 150), radius=10,
                 center: bool = False) -> Image.Image:
    """lines: [(text, font, rgb)] stacked; returns RGBA box."""
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    sizes = [tmp.textbbox((0, 0), t, font=f) for t, f, _ in lines]
    w = max(b[2] - b[0] for b in sizes) + pad[0] * 2
    h = sum(b[3] - b[1] for b in sizes) + pad[1] * 2 + 10 * (len(lines) - 1)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if bg:
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=bg)
    y = pad[1]
    for (t, f, col), b in zip(lines, sizes):
        x = (w - (b[2] - b[0])) // 2 - b[0] if center else pad[0] - b[0]
        d.text((x, y - b[1]), t, font=f, fill=col)
        y += b[3] - b[1] + 10
    return im


def credit_overlay(credit: str, label: str | None, what: str = "Image") -> list[tuple[Image.Image, tuple[int, int]]]:
    out = []
    if credit:
        ov = text_overlay([(f"{what}: {credit}", font("text", 22, 500), BRAND["star"])], pad=(16, 10), bg=(0, 0, 0, 140), radius=6)
        out.append((ov, (W - ov.width - 36, H - ov.height - 30)))
    if label:
        ov = text_overlay([(label.upper(), font("display", 24, 700), BRAND["space"])], pad=(16, 10), bg=BRAND["amber"] + (235,), radius=6)
        out.append((ov, (36, 32)))
    return out


def chapter_overlay(title: str, number: int | None) -> Image.Image:
    lines = []
    if number is not None:
        lines.append((f"CHAPTER {number:02d}", font("display", 30, 700), BRAND["cyan"]))
    lines.append((title, font("display", 64, 700), BRAND["star"]))
    box = text_overlay(lines, pad=(36, 22), bg=(11, 16, 38, 210), radius=8)
    d = ImageDraw.Draw(box)
    d.rectangle((0, 0, 8, box.height), fill=BRAND["cyan"] + (255,))
    return box


def title_card(text: str, sub: str | None, accent: str = "cyan") -> Image.Image:
    lines = [(text, font("display", 150 if len(text) < 14 else 104, 700), BRAND[accent])]
    if sub:
        lines.append((sub, font("text", 50, 500), BRAND["star"]))
    return text_overlay(lines, pad=(10, 10), bg=None, center=True)


def paste(frame: Image.Image, ov: Image.Image, xy, alpha: float = 1.0):
    if alpha <= 0:
        return
    if alpha < 1:
        a = ov.getchannel("A").point(lambda v: int(v * alpha))
        ov = ov.copy(); ov.putalpha(a)
    frame.paste(ov, xy, ov)


# ---------- motion graphics (owner's feedback 26/10/2026: counters, kinetic text, animated charts) ----------
def ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def fmt_num(v: float, decimals: int) -> str:
    return f"{v:,.{decimals}f}"


def counter_frame(bg: Image.Image, v: dict, t: float) -> Image.Image:
    """A number counting from `from` to `value` in `count` seconds, then holding; prefix/suffix and a sub-line."""
    f = bg.copy()
    p = ease_out(t / v.get("count", 2.0))
    val = v.get("from", 0) + (v["value"] - v.get("from", 0)) * p
    txt = f"{v.get('prefix', '')}{fmt_num(val, v.get('decimals', 0))}{v.get('suffix', '')}"
    final = f"{v.get('prefix', '')}{fmt_num(v['value'], v.get('decimals', 0))}{v.get('suffix', '')}"
    size = 170 if len(final) <= 10 else 130 if len(final) <= 16 else 100
    big = font("display", size, 700)
    d = ImageDraw.Draw(f)
    fb = d.textbbox((0, 0), final, font=big)        # layout on the final width, so the number never jumps
    x0 = (W - (fb[2] - fb[0])) // 2 - fb[0]
    y0 = H // 2 - (fb[3] - fb[1]) // 2 - (40 if v.get("sub") else 0) - fb[1]
    if v.get("label"):
        lf = font("display", 44, 700)
        lb = d.textbbox((0, 0), v["label"].upper(), font=lf)
        d.text(((W - (lb[2] - lb[0])) // 2 - lb[0], y0 + fb[1] - 90), v["label"].upper(), font=lf, fill=BRAND["cyan"])
    tb = d.textbbox((0, 0), txt, font=big)
    d.text((x0 + (fb[2] - tb[2]), y0), txt, font=big, fill=BRAND[v.get("accent", "amber")])
    if v.get("sub"):
        a = ease((t - v.get("count", 2.0) * 0.7) / 0.5)
        sub = text_overlay([(v["sub"], font("text", 50, 500), BRAND["star"])], pad=(10, 6), bg=None, center=True)
        paste(f, sub, ((W - sub.width) // 2, y0 + fb[3] + 40), a)
    return f


def kinetic_frame(bg: Image.Image, v: dict, t: float, dur: float) -> Image.Image:
    """Words pop in one after another (scale 1.35 -> 1, fade), centred and wrapped; `accent` words in amber."""
    f = bg.copy()
    words = v["text"].split()
    accent = {w.upper().strip(".,!?") for w in v.get("accent", [])}
    fnt = font("display", v.get("size", 120 if len(words) <= 6 else 96), 700)
    d = ImageDraw.Draw(f)
    space = d.textbbox((0, 0), " ", font=fnt)[2]
    lines, cur, cw = [], [], 0
    for w in words:
        ww = d.textbbox((0, 0), w, font=fnt)[2]
        if cur and cw + space + ww > W - 220:
            lines.append((cur, cw)); cur, cw = [], 0
        cur.append((w, ww)); cw += (space if cw else 0) + ww
    lines.append((cur, cw))
    lh = fnt.size * 1.15
    y = H / 2 - lh * len(lines) / 2
    stagger = min(0.32, 0.55 * dur / max(1, len(words)))
    k = 0
    for line, lw in lines:
        x = (W - lw) / 2
        for w, ww in line:
            p = ease_out((t - k * stagger) / 0.35)
            if p > 0:
                col = BRAND["amber"] if w.upper().strip(".,!?") in accent else BRAND["star"]
                s = 1.35 - 0.35 * p
                im = Image.new("RGBA", (int(ww * 1.4) + 20, int(lh * 1.5)), (0, 0, 0, 0))
                ImageDraw.Draw(im).text((10, int(lh * 0.1)), w, font=fnt, fill=col + (int(255 * p),))
                im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
                # scale around the word's own centre, so every word lands exactly on its final position
                f.paste(im, (int(x + ww / 2 - (10 + ww / 2) * s), int(y + lh / 2 - (lh * 0.1 + lh / 2) * s)), im)
            x += ww + space
            k += 1
        y += lh
    return f


def bars_frame(bg: Image.Image, v: dict, t: float, dur: float) -> Image.Image:
    """Horizontal bars that grow one after another (log scale if `log`), value labels fade in at the end of each bar.
    items: [{label, value, display}], title, note (source line)."""
    f = bg.copy()
    d = ImageDraw.Draw(f)
    items = v["items"]
    tf, lf, vf, nf = font("display", 56, 700), font("display", 38, 700), font("text", 34, 600), font("text", 24, 500)
    d.text((110, 70), v.get("title", ""), font=tf, fill=BRAND["star"])
    if v.get("note"):
        d.text((110, H - 70), v["note"], font=nf, fill=BRAND["dust"])
    vals = [it["value"] for it in items]
    if v.get("log"):
        lo = math.log10(min(vals)) - 0.6
        span = math.log10(max(vals)) - lo
        frac = [(math.log10(x) - lo) / span for x in vals]
    else:
        frac = [x / max(vals) for x in vals]
    top, bottom = 190, H - 130
    row = (bottom - top) / len(items)
    bh = min(64, row * 0.62)
    x0, xmax = 470, W - 330
    stagger = min(1.6, 0.7 * dur / len(items))
    for i, (it, fr) in enumerate(zip(items, frac)):
        p = ease_out((t - 0.3 - i * stagger) / 0.9)
        y = top + i * row + (row - bh) / 2
        if t < 0.1 + i * stagger:
            continue
        lb = d.textbbox((0, 0), it["label"], font=lf)
        d.text((x0 - 30 - (lb[2] - lb[0]), y + bh / 2 - (lb[3] + lb[1]) / 2), it["label"], font=lf, fill=BRAND["star"])
        w = max(6, (xmax - x0) * fr * p)
        col = BRAND["amber"] if it.get("hi") else BRAND["cyan"]
        d.rounded_rectangle((x0, y, x0 + w, y + bh), radius=int(bh / 3), fill=col)
        if p > 0.85:
            d.text((x0 + w + 22, y + bh / 2 - 20), it.get("display", ""), font=vf, fill=BRAND["star"])
    return f


# ---------- motion graphics, round 2 (owner 30/10/2026: "animazioni più carine", from the competitor analysis:
# numbers shown as physical comparisons, running clocks, A-vs-B reveals) ----------
def _sphere(r: int, col: tuple) -> Image.Image:
    """A lit sphere (radial gradient + rim), RGBA, diameter 2r."""
    r = max(2, r)
    yy, xx = np.mgrid[-r:r, -r:r].astype(np.float32) + 0.5
    d = np.sqrt(xx ** 2 + yy ** 2) / r
    light = np.clip(1.15 - np.sqrt((xx / r + 0.35) ** 2 + (yy / r + 0.35) ** 2) * 0.75, 0.25, 1.15)
    rgb = np.clip(np.array(col, np.float32)[None, None, :] * light[..., None], 0, 255)
    a = np.clip((1 - d) * r, 0, 1) * 255
    return Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA")


def scale_frame(bg: Image.Image, v: dict, t: float, dur: float) -> Image.Image:
    """Objects side by side at true relative size (diameter ∝ value), growing one after another.
    items: [{label, value, display}], title, note."""
    f = bg.copy()
    d = ImageDraw.Draw(f)
    items = v["items"]
    tf, lf, vf, nf = font("display", 58, 700), font("display", 40, 700), font("text", 32, 600), font("text", 24, 500)
    if v.get("title"):
        tb = d.textbbox((0, 0), v["title"], font=tf)
        d.text(((W - (tb[2] - tb[0])) // 2, 70), v["title"], font=tf, fill=BRAND["star"])
    if v.get("note"):
        d.text((110, H - 64), v["note"], font=nf, fill=BRAND["dust"])
    vmax = max(it["value"] for it in items)
    gap = 70
    maxd = min(560, (W - 240 - gap * (len(items) - 1)) / max(1.0, sum(it["value"] for it in items) / vmax))
    diam = [max(6, maxd * it["value"] / vmax) for it in items]
    total = sum(diam) + gap * (len(items) - 1)
    x, base = (W - total) / 2, H * 0.66
    stagger = min(1.4, 0.6 * dur / len(items))
    cols = [BRAND["cyan"], BRAND["amber"], (150, 120, 230), (110, 200, 160), BRAND["star"]]
    for i, (it, dm) in enumerate(zip(items, diam)):
        p = ease_out((t - 0.2 - i * stagger) / 0.8)
        if p > 0:
            s = _sphere(int(dm * p / 2), cols[i % len(cols)])
            f.paste(s, (int(x + dm / 2 - s.width / 2), int(base - s.height)), s)
            a = int(255 * min(1, p * 1.5))
            lb = d.textbbox((0, 0), it["label"], font=lf)
            d.text((x + dm / 2 - (lb[2] - lb[0]) / 2, base + 24), it["label"], font=lf, fill=BRAND["star"] + (a,))
            if it.get("display") and p > 0.8:
                vb = d.textbbox((0, 0), it["display"], font=vf)
                d.text((x + dm / 2 - (vb[2] - vb[0]) / 2, base + 80), it["display"], font=vf, fill=BRAND["amber"])
        x += dm + gap
    return f


def timer_frame(bg: Image.Image, v: dict, t: float, dur: float) -> Image.Image:
    """A clock that runs (accelerated) up to `seconds`, with a progress ring; `display` is the spoken value."""
    f = bg.copy()
    d = ImageDraw.Draw(f)
    run_s = min(v.get("count", 3.0), dur * 0.7)
    p = ease_out(t / run_s)
    s = v["seconds"] * p
    if v["seconds"] >= 2 * 86400:
        txt, final = f"{s / 86400:,.0f} days", f"{v['seconds'] / 86400:,.0f} days"
    elif v["seconds"] >= 3600:
        txt = f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}"
        final = f"{int(v['seconds'] // 3600):02d}:00:00"
    else:
        txt, final = f"{int(s // 60):02d}:{s % 60:05.2f}", "00:00.00"
    cx, cy, r = W // 2, H // 2 - 10, 330
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=BRAND["dust"], width=6)
    d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * p, fill=BRAND["cyan"], width=14)
    big = font("display", 120 if len(final) <= 5 else 100 if len(final) <= 8 else 84, 700)
    fb = d.textbbox((0, 0), final, font=big)
    tb = d.textbbox((0, 0), txt, font=big)
    x0 = cx - (fb[2] - fb[0]) // 2 - fb[0]
    d.text((x0 + (fb[2] - tb[2]), cy - (fb[3] - fb[1]) // 2 - fb[1]), txt, font=big, fill=BRAND["amber"])
    if v.get("label"):
        lf = font("display", 46, 700)
        lb = d.textbbox((0, 0), v["label"].upper(), font=lf)
        d.text((cx - (lb[2] - lb[0]) // 2, cy - r - 90), v["label"].upper(), font=lf, fill=BRAND["cyan"])
    if v.get("display"):
        a = ease((t - run_s) / 0.5)
        sub = text_overlay([(v["display"], font("text", 54, 600), BRAND["star"])], pad=(10, 6), bg=None, center=True)
        paste(f, sub, ((W - sub.width) // 2, cy + r + 30), a)
    return f


def compare_frame(bg: Image.Image, v: dict, t: float, dur: float) -> Image.Image:
    """Two numbers counting up side by side, then the ratio between them (computed, marked ≈)."""
    f = bg.copy()
    d = ImageDraw.Draw(f)
    a, b = v["items"][:2]
    if v.get("title"):
        tf = font("display", 56, 700)
        tb = d.textbbox((0, 0), v["title"], font=tf)
        d.text(((W - (tb[2] - tb[0])) // 2, 80), v["title"], font=tf, fill=BRAND["star"])
    for k, (it, cx, col) in enumerate(((a, W // 4 + 20, BRAND["cyan"]), (b, 3 * W // 4 - 20, BRAND["amber"]))):
        p = ease_out((t - 0.2 - k * 0.6) / 1.4)
        if p <= 0:
            continue
        lf = font("display", 50, 700)
        lb = d.textbbox((0, 0), it["label"].upper(), font=lf)
        d.text((cx - (lb[2] - lb[0]) // 2, H // 2 - 170), it["label"].upper(), font=lf, fill=BRAND["star"])
        dec = it.get("decimals", 0)
        txt = f"{it['value'] * p:,.{dec}f}{it.get('suffix', '')}"
        big = font("display", 120 if len(txt) <= 9 else 88, 700)
        tb = d.textbbox((0, 0), txt, font=big)
        d.text((cx - (tb[2] - tb[0]) // 2, H // 2 - 60), txt, font=big, fill=col)
    d.line((W // 2, H // 2 - 180, W // 2, H // 2 + 120), fill=BRAND["dust"], width=3)
    lo, hi = sorted([a["value"], b["value"]])
    if lo > 0:
        ratio = hi / lo
        rt = f"≈ {ratio:,.0f}×" if ratio >= 10 else f"≈ {ratio:,.1f}×"
        al = ease((t - 2.4) / 0.5)
        ov = text_overlay([(rt, font("display", 96, 700), BRAND["amber"])], pad=(30, 14), bg=(11, 16, 38, 220), radius=12)
        paste(f, ov, ((W - ov.width) // 2, H // 2 + 170), al)
    return f


@lru_cache(maxsize=8)
def dim_image(path: str, amount: float = 0.6) -> Image.Image:
    img = prepare_image(Path(path)).resize((W, H), Image.LANCZOS)
    return Image.blend(img, Image.new("RGB", img.size, BRAND["space"]), amount)


# ---------- shot renderer ----------
class Shot:
    def __init__(self, shot: dict, video: Path, assets: dict, chapter_no: int | None):
        self.s, self.v = shot, shot["visual"]
        self.n = max(1, round((shot["end"] - shot["start"]) * FPS))
        self.overlays = []
        kind = self.v["type"]
        if kind == "image":
            a = assets[self.v["src"]]
            self.canvas = prepare_image(video / a["file"], self.v.get("fit"))
            label = self.v.get("label") or ("Artist's concept" if a.get("kind") == "illustration" else None)
            self.overlays = credit_overlay(a["credit"], label)
        elif kind == "chart":
            a = assets[self.v["src"]]
            chart = Image.open(video / a["file"]).convert("RGB").resize((W, H), Image.LANCZOS)
            cw, ch = int(W * ZMAX), int(H * ZMAX)
            self.canvas = Image.new("RGB", (cw, ch), BRAND["space"])
            self.canvas.paste(chart, ((cw - W) // 2, (ch - H) // 2))
            if a.get("credit"):
                self.overlays = credit_overlay(a["credit"], None)
        elif kind == "title":
            self.canvas = starfield(self.v.get("seed", 11)).copy()
            card = title_card(self.v["text"], self.v.get("sub"), self.v.get("accent", "cyan"))
            self.title = (card, ((W - card.width) // 2, (H - card.height) // 2))
        elif kind == "video":   # real footage (stock.py: NASA, ESA, Pexels, Pixabay), never from other YouTube channels
            a = assets[self.v["src"]]
            self.reader = VideoReader(video / a["file"], W, H, self.v.get("start", 0.0))
            label = self.v.get("label") or ("Artist's concept" if a.get("kind") == "illustration" else None)
            self.overlays = credit_overlay(a.get("credit", ""), label, "Video")
        elif kind == "fx":   # one of the 11 Remotion scenes, already rendered to an mp4 by render_video
            self.reader = VideoReader(Path(self.v["file"]), W, H, 0.0, grade=False)
        elif kind in ("counter", "kinetic", "bars", "scale", "timer", "compare"):
            bg = self.v.get("bg")
            self.canvas = (dim_image(str(video / assets[bg]["file"]), self.v.get("dim", 0.62)) if bg
                           else starfield(self.v.get("seed", 11)).resize((W, H), Image.BILINEAR))
            if bg and assets[bg].get("credit"):
                self.overlays = credit_overlay(assets[bg]["credit"], None)
        else:
            raise ValueError(f"unknown visual type {kind}")
        # no "Intro" lower-third: the video opens straight on the hook (owner's feedback 26/10/2026)
        self.chapter = (chapter_overlay(shot["chapter"], chapter_no)
                        if shot.get("chapter") and shot["chapter"].lower() != "intro" else None)

    def camera(self, i: int) -> tuple[float, float, float]:
        p = ease(i / max(1, self.n - 1))
        motion = self.v.get("motion", "zoom_in" if self.v["type"] == "image" else "static")
        if self.v["type"] == "chart":
            return 1.0 + 0.04 * p + 0.06, 0.5, 0.5   # gentle push on a chart
        return {
            "zoom_in": (1.0 + (ZMAX - 1.0) * p, 0.5, 0.5),
            "zoom_out": (ZMAX - (ZMAX - 1.0) * p, 0.5, 0.5),
            "pan_left": (ZMAX * 0.96, 0.62 - 0.24 * p, 0.5),
            "pan_right": (ZMAX * 0.96, 0.38 + 0.24 * p, 0.5),
            "pan_up": (ZMAX * 0.96, 0.5, 0.62 - 0.24 * p),
            "static": (1.03, 0.5, 0.5),
        }[motion]

    def frame(self, i: int) -> Image.Image:
        t = i / FPS
        kind, dur = self.v["type"], self.n / FPS
        if kind in ("video", "fx"):
            f = self.reader.next()
            if i == self.n - 1:
                self.reader.close()
        elif kind == "counter":
            f = counter_frame(self.canvas, self.v, t)
        elif kind == "kinetic":
            f = kinetic_frame(self.canvas, self.v, t, dur)
        elif kind == "bars":
            f = bars_frame(self.canvas, self.v, t, dur)
        elif kind == "scale":
            f = scale_frame(self.canvas, self.v, t, dur)
        elif kind == "timer":
            f = timer_frame(self.canvas, self.v, t, dur)
        elif kind == "compare":
            f = compare_frame(self.canvas, self.v, t, dur)
        else:
            z, cx, cy = self.camera(i)
            cw, ch = self.canvas.size
            bw, bh = cw / z, ch / z  # z=1 shows the whole canvas, z=ZMAX shows native pixels
            x0 = (cw - bw) * cx
            y0 = (ch - bh) * cy
            f = self.canvas.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + bw, y0 + bh))
        if self.v["type"] == "chart" and self.v.get("anim") == "reveal":
            p = ease(t / 1.4)
            if p < 1:
                cut = int(W * p)
                bg = Image.new("RGB", (W, H), BRAND["space"])
                bg.paste(f.crop((0, 0, cut, H)), (0, 0))
                f = bg
        if self.v["type"] == "title":
            card, xy = self.title
            paste(f, card, xy, ease(t / 0.7))
        for ov, xy in self.overlays:
            paste(f, ov, xy, ease((t - 0.3) / 0.6))
        if self.v.get("stickman"):  # recurring human scale over the real image (owner 31/10/2026)
            import stickman
            f = stickman.overlay(f, self.v["stickman"], t)
        if self.chapter is not None and t < 4.0:
            a = ease((t - 0.2) / 0.5) * (1 - ease((t - 3.3) / 0.6))
            paste(f, self.chapter, (80, H - self.chapter.height - 120), a)
        return f


def render_video(script: dict, video: Path, assets: dict, timings: dict) -> list[dict]:
    build = video / "build"
    shots = build_shots(script, timings)
    save_json(build / "shots.json", shots)
    plan = motion_plan(script, video, assets, shots, timings)
    total_frames = round(timings["duration"] * FPS)
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(build / "video_noaudio.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    written, prev_last, chapter_no = 0, None, 0
    for k, sh in enumerate(shots):
        if sh.get("chapter") and sh["chapter"].lower() not in ("intro", "outro"):
            chapter_no += 1
            # titles that already carry their own number ("Step 9: ...") get no "CHAPTER NN" line
            num = None if sh["chapter"].lower().startswith("step ") else chapter_no
        else:
            num = None
        fxv = plan["fx"].get(str(k))
        shot = Shot({**sh, "visual": fxv} if fxv else sh, video, assets, num)
        n = shot.n if k < len(shots) - 1 else total_frames - written
        trans = plan["transitions"].get(str(k))
        for i in range(n):
            f = shot.frame(i)
            if plan["hook"] is not None and written + i < plan["hook_frames"]:
                f = plan["hook"].next()   # 01 Orbit over the first second and a half
            if trans == "glitch" and i < 8:
                f = motion.glitch(f, i, 8, seed=k)
            elif trans == "zoomthrough" and i < 7:
                f = motion.zoom_into(f, (i + 1) / 7)
            elif prev_last is not None and i < XFADE:
                f = Image.blend(prev_last, f, ease((i + 1) / XFADE))
            if script.get("progress_bar"):  # thin progress line at the bottom (retention cue)
                ImageDraw.Draw(f).rectangle((0, H - 6, int(W * (written + i) / total_frames), H), fill=BRAND["cyan"])
            proc.stdin.write(f.tobytes())
            last = f
        written += n
        prev_last = last
        print(f"  shot {k + 1}/{len(shots)} [{sh['visual']['type']}] {n / FPS:.1f}s", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg video encode failed")
    if plan["hook"] is not None:
        plan["hook"].close()
    return shots


def motion_plan(script: dict, video: Path, assets: dict, shots: list[dict], timings: dict) -> dict:
    """The director's choices for a long video, rendered with Remotion. Saves build/motion_plan.json (the sound
    events, read again by render_audio). Without Remotion, or with `motion: false` in script.yaml: no effects."""
    build = video / "build"
    empty = {"fx": {}, "transitions": {}, "hook": None, "hook_frames": 0}
    if script.get("motion") is False:
        save_json(build / "motion_plan.json", {"events": []})
        return empty
    p = director.plan_long(script, shots, timings, script.get("brand", "cosmos"))
    srcs = []
    for a in assets.values():
        if a.get("type") in ("video", "image") and (video / a["file"]).exists():
            srcs.append((video / a["file"], a["type"], 2.0))
    tiles = motion.tiles(srcs[:6], per_clip=2) if motion.available() else []
    brand = script.get("brand", "cosmos")
    jobs = []
    for k, f in p["fx"].items():
        frames = max(8, round((shots[k]["end"] - shots[k]["start"]) * FPS))
        props = {"brand": brand, "tiles": tiles, **f["props"], "width": W, "height": H, "fps": FPS, "frames": frames}
        if f["effect"] == "framebreak" and f.get("src") in assets and assets[f["src"]]["type"] == "image":
            props["poster"] = motion._uri(Image.open(video / assets[f["src"]]["file"]), 720)
        jobs.append({"effect": f["effect"], "out": str(build / f"fx_{k:03d}_{f['effect']}.mp4"), "props": props, "k": k})
    hook_out = str(build / "fx_hook_orbit.mp4")
    jobs.append({"effect": "orbit", "out": hook_out, "k": -1,
                 "props": {"brand": brand, "tiles": tiles, **p["hook"]["props"], "width": W, "height": H, "fps": FPS,
                           "frames": round(p["hook"]["t1"] * FPS)}})
    done = motion.render_jobs([{kk: j[kk] for kk in ("effect", "out", "props")} for j in jobs], build)
    fx = {str(j["k"]): {"type": "fx", "file": j["out"], "effect": j["effect"]} for j in jobs if j["k"] >= 0 and j["out"] in done}
    events = list(p["events"]) if done else [e for e in p["events"] if e[1] in ("glitch", "whoosh", "impact")]
    save_json(build / "motion_plan.json", {"events": events, "fx": fx, "transitions": p["transitions"]})
    hook = VideoReader(Path(hook_out), W, H, 0.0, grade=False) if hook_out in done else None
    return {"fx": fx, "transitions": {str(k): v for k, v in p["transitions"].items()}, "hook": hook,
            "hook_frames": round(p["hook"]["t1"] * FPS) if hook else 0}


def render_audio(script: dict, video: Path, timings: dict, shots: list[dict], total: float | None = None,
                 events: list | None = None, music_file: Path | None = None, out: str = "mix.wav"):
    """Voice + ducked score + effects. `total` > narration length pads the voice with silence (Shorts' CTA tail);
    `events` are extra sound events (Shorts); long videos read build/motion_plan.json written by render_video.
    `music_file` replaces the generated score (the social variant's trending sound, looped); `out` is the mix name."""
    build = video / "build"
    dur = total or timings["duration"]
    m = script.get("music", {})
    music_wav = build / ("music.wav" if music_file is None else "music_social.wav")
    if music_file is None:
        music.write(music_wav, music.ambient_track(dur, m.get("seed", 7), m.get("mood", "calm")))
    else:
        run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", music_file,
             "-t", f"{dur:.3f}", "-ac", "2", "-ar", "48000", "-af", f"afade=t=out:st={max(0.0, dur - 1.0):.3f}:d=1",
             music_wav])
    events = [tuple(e) for e in (events or [])]
    mp = build / "motion_plan.json"
    if events == [] and mp.exists():
        events = [tuple(e) for e in load_json(mp).get("events", [])]
    for sh in shots:
        if sh.get("chapter") and sh["start"] > 1:
            events.append((sh["start"], "whoosh"))
        elif script.get("cut_sfx") and sh["start"] > 1:  # a soft swish on every cut
            events.append((sh["start"], "swish"))
        if (sh["visual"]["type"] == "chart" and sh["visual"].get("anim") == "reveal") or sh["visual"]["type"] in (
                "counter", "scale", "compare"):
            events.append((sh["start"] + 0.2, "ping"))
        if sh["visual"]["type"] == "timer":
            events.append((sh["start"] + min(sh["visual"].get("count", 3.0), (sh["end"] - sh["start"]) * 0.7), "ping"))
    music.write(build / "sfx.wav", sfx.track(dur, events, seed=m.get("seed", 7)))
    graph = (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={dur:.3f},asplit=2[v][vsc];"
             "[1:a]volume=0.32[m];[m][vsc]sidechaincompress=threshold=0.02:ratio=8:attack=40:release=700[md];"
             "[2:a]volume=0.7[s];[v][md][s]amix=inputs=3:normalize=0:duration=first[mx]")
    base = [ffmpeg_exe(), "-hide_banner", "-y", "-i", build / "narration.wav", "-i", music_wav,
            "-i", build / "sfx.wav"]
    r = run(base + ["-filter_complex", graph + ";[mx]loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json[a]",
                    "-map", "[a]", "-f", "null", "-"])
    txt = r.stderr.decode("utf-8", "replace")
    meas = json.loads(txt[txt.rindex("{"): txt.rindex("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
          f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:"
          f"offset={meas['target_offset']}:linear=true")
    run(base + ["-filter_complex", graph + f";[mx]{ln}[a]", "-map", "[a]", "-ar", "48000", build / out])
    return meas


def mux(video: Path, out_name: str) -> Path:
    build, out = video / "build", video / "out"
    out.mkdir(exist_ok=True)
    dest = out / f"{out_name}.mp4"
    run([ffmpeg_exe(), "-hide_banner", "-y", "-i", build / "video_noaudio.mp4", "-i", build / "mix.wav",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
         "-movflags", "+faststart", dest])
    return dest


class VideoReader:
    """Frames of a stock clip, scaled and cropped to fill w x h at the project frame rate, looped
    if the shot is longer than the clip. Audio of the clip is never used."""

    def __init__(self, path: Path, w: int, h: int, start: float = 0.0, grade: bool = True):
        self.w, self.h = w, h
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS}"
        if grade:   # stock footage: a touch darker and calmer, so it sits with the brand (not our own graphics)
            vf += ",eq=saturation=0.85:brightness=-0.03"
        self.cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error"] + (["-stream_loop", "-1"] if grade else []) + [
                    "-ss", str(start), "-i", str(path), "-an", "-vf", vf,
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE)
        self.last = None

    def next(self) -> Image.Image:
        buf = self.proc.stdout.read(self.w * self.h * 3)
        if len(buf) == self.w * self.h * 3:
            self.last = Image.frombytes("RGB", (self.w, self.h), buf)
        return (self.last or Image.new("RGB", (self.w, self.h), BRAND["space"])).copy()

    def close(self):
        try:
            self.proc.kill()
        except OSError:
            pass
