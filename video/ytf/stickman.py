"""Original stick man (drawn here, no external asset): the recurring "human scale" of the channel (owner 31/10/2026),
placed over real NASA/ESA images, never instead of them.

figure(height, phase) -> RGBA image; phase in [0, 1) animates a wave of the right arm.
overlay(frame, v, t) draws it on a frame from a visual's "stickman": {"label": "YOU", "size": "small|tiny|big",
"side": "left|right"}; "tiny" makes the point that the human is a dot next to the object.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from common import BRAND, font

INK = (245, 245, 240)


def figure(h: int, phase: float = 0.0, col=INK) -> Image.Image:
    h = max(12, int(h))
    w = int(h * 0.7)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = max(2, round(h / 16))
    cx, head = w / 2, h * 0.11
    hy = head + lw
    d.ellipse((cx - head, hy - head, cx + head, hy + head), outline=col + (255,), width=lw)
    neck, hip = hy + head, h * 0.62
    d.line((cx, neck, cx, hip), fill=col + (255,), width=lw)
    for s in (-1, 1):  # legs
        d.line((cx, hip, cx + s * w * 0.28, h - lw), fill=col + (255,), width=lw)
    sh = neck + (hip - neck) * 0.25
    d.line((cx, sh, cx - w * 0.32, sh + h * 0.2), fill=col + (255,), width=lw)  # left arm down
    ang = math.radians(-30 + 20 * math.sin(phase * 2 * math.pi))  # right arm waving, away from the head
    d.line((cx, sh, cx + math.cos(ang) * w * 0.4, sh + math.sin(ang) * w * 0.4), fill=col + (255,), width=lw)
    return im


def overlay(frame: Image.Image, v: dict, t: float) -> Image.Image:
    W, H = frame.size
    size = {"tiny": 0.045, "small": 0.16, "big": 0.32}.get(v.get("size", "small"), 0.16) * H
    fig = figure(size, (t * 0.8) % 1.0)
    side = v.get("side", "left")
    x = int(W * 0.07) if side == "left" else int(W * 0.93 - fig.width)
    y = int(H * 0.86 - fig.height)
    a = min(1.0, max(0.0, (t - 0.3) / 0.5))
    if a <= 0:
        return frame
    sh = Image.new("RGBA", frame.size, (0, 0, 0, 0))  # soft ground shadow so it reads on bright images
    ImageDraw.Draw(sh).ellipse((x - 10, y + fig.height - 8, x + fig.width + 10, y + fig.height + 10), fill=(0, 0, 0, int(140 * a)))
    frame.paste(sh, (0, 0), sh)
    f2 = fig.copy()
    f2.putalpha(fig.getchannel("A").point(lambda p: int(p * a)))
    frame.paste(f2, (x, y), f2)
    if v.get("label"):
        fnt = font("display", max(22, int(H * 0.03)), 700)
        d = ImageDraw.Draw(frame)
        b = d.textbbox((0, 0), v["label"].upper(), font=fnt)
        tx = x + fig.width / 2 - (b[2] - b[0]) / 2
        d.text((tx, y + fig.height + 14), v["label"].upper(), font=fnt, fill=BRAND["amber"])
    return frame
