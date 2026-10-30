"""1280x720 thumbnails: a real image, one short bold claim, brand accents.

Three variants per video (A/B/C) so YouTube Studio's A/B test can pick one.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from common import BRAND, font

TW, TH = 1280, 720


def cover(img: Image.Image, w: int, h: int, focus=(0.5, 0.5)) -> Image.Image:
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.LANCZOS)
    x = int((img.width - w) * focus[0]); y = int((img.height - h) * focus[1])
    return img.crop((x, y, x + w, y + h))


def fit_text(draw, text, kind, max_w, start, weight=700, min_size=40):
    size = start
    while size > min_size:
        f = font(kind, size, weight)
        b = draw.textbbox((0, 0), text, font=f)
        if b[2] - b[0] <= max_w:
            return f
        size -= 4
    return font(kind, min_size, weight)


def make(bg_path: Path, lines: list[str], dest: Path, accent="amber", badge="REAL DATA",
         focus=(0.5, 0.5), side="left", highlight: int = 0, label: str | None = None, stickman: bool = False):
    """label: small corner tag, set automatically to "ARTIST'S CONCEPT" for illustrations
    so a thumbnail never passes an illustration off as a photograph."""
    img = cover(Image.open(bg_path).convert("RGB"), TW, TH, focus)
    # darken the text side with a smooth gradient so the claim reads at phone size
    grad = Image.new("L", (TW, TH))
    gd = ImageDraw.Draw(grad)
    for x in range(TW):
        r = x / TW if side == "left" else 1 - x / TW
        gd.line([(x, 0), (x, TH)], fill=int(235 * max(0.0, 1 - r * 1.6)))
    dark = Image.new("RGB", (TW, TH), BRAND["space"])
    img = Image.composite(dark, img, grad)
    d = ImageDraw.Draw(img)
    x0 = 56 if side == "left" else TW // 2 - 20
    y = 120
    max_w = TW // 2 + 60
    for i, line in enumerate(lines):
        f = fit_text(d, line, "display", max_w, 132 if i == highlight else 96)
        col = BRAND[accent] if i == highlight else BRAND["star"]
        b = d.textbbox((0, 0), line, font=f)
        # soft shadow
        sh = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((x0 - b[0] + 4, y - b[1] + 6), line, font=f, fill=(0, 0, 0, 200))
        img.paste(sh.filter(ImageFilter.GaussianBlur(6)), (0, 0), sh.filter(ImageFilter.GaussianBlur(6)))
        d.text((x0 - b[0], y - b[1]), line, font=f, fill=col)
        y += (b[3] - b[1]) + 22
    if badge:
        f = font("display", 34, 700)
        b = d.textbbox((0, 0), badge, font=f)
        bw, bh = b[2] - b[0] + 36, b[3] - b[1] + 22
        bx, by = x0, TH - bh - 52
        d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=8, fill=BRAND["cyan"])
        d.text((bx + 18 - b[0], by + 11 - b[1]), badge, font=f, fill=BRAND["space"])
    if label:
        f = font("text", 22, 600)
        b = d.textbbox((0, 0), label, font=f)
        lw, lh = b[2] - b[0] + 20, b[3] - b[1] + 12
        d.rounded_rectangle((TW - lw - 24, 22, TW - 24, 22 + lh), radius=5, fill=(0, 0, 0))
        d.text((TW - lw - 14 - b[0], 28 - b[1]), label, font=f, fill=BRAND["star"])
    if stickman:  # the channel's human scale, opposite the text
        import stickman as sm
        fig = sm.figure(int(TH * 0.3))
        x = TW - fig.width - 70 if side == "left" else 70
        img.paste(fig, (x, TH - fig.height - 60), fig)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, quality=92)
    return dest
