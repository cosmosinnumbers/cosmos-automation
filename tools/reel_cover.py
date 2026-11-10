"""Cover (thumbnail) for Instagram/Facebook Reels, so the profile grid never shows the first frame of the video.

  python tools/reel_cover.py <mp4> "<title>" [out.jpg]      build a cover locally (check it by eye)

Why (owner 10/11/2026, screenshot of the Reels grid): with no cover_url Instagram takes the first frame. Our clips
open on a transition (c1110-ess-clip-a: a flat grey frame) or on a dark frame with small text, so the grid showed a
grey square and near-black tiles.

The cover: 1080x1920 JPEG, background = the frame of the clip with the most detail (blurred, darkened), brand line,
the key number of the title very big (amber) and the title in white. All text sits in the central 1080x1080
square (y 420-1500), safe both for the 3:4 grid crop (y 240-1680) and the old 1:1 crop. Only our own fonts (OFL)
and frames of our own video: no outside assets.

Hosting: Instagram fetches cover_url itself, so the JPEG goes to cosmosinnumbers.github.io/media/covers/ (secret
PAGES_TOKEN, as carousel_build.py). Without PAGES_TOKEN, or if the upload fails, best_offset() gives a thumb_offset
(ms) on the most detailed frame instead: never the first frame.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "assets" / "fonts"
W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 420, 1500  # central 1080x1080
BRAND = {"space": (11, 16, 38), "cyan": (79, 209, 197), "amber": (246, 173, 85), "star": (247, 250, 252),
         "dust": (138, 148, 166)}
PAGES = "https://api.github.com/repos/cosmosinnumbers/cosmosinnumbers.github.io/contents/media/covers"
PUBLIC = "https://cosmosinnumbers.github.io/media/covers"
RAW = "https://raw.githubusercontent.com/cosmosinnumbers/cosmosinnumbers.github.io/main/media/covers"
# a number with its unit: "8 minutes", "1.3 seconds", "45.22 km", "1,200 light-years", "499 s", "4.6 billion"
NUM = re.compile(r"(\d[\d,.]*\s*(?:%|(?:billion|million|trillion|thousand)\b)?\s*"
                 r"(?:light[- ]years?|light[- ]days?|years?|seconds?|minutes?|hours?|days?|km/s|km|miles?|times|"
                 r"degrees|°C|K|kg|tons?|s)?\b)", re.I)


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def duration(mp4: str) -> float:
    r = subprocess.run([ffmpeg(), "-i", str(mp4)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def frame(mp4: str, t: float, out: Path) -> Path | None:
    subprocess.run([ffmpeg(), "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1",
                    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", str(out)],
                   capture_output=True)
    return out if out.exists() and out.stat().st_size else None


def detail(path: Path) -> float:
    """Contrast + brightness of a frame: flat grey or near-black frames score low."""
    from PIL import Image, ImageStat
    g = Image.open(path).convert("L").resize((108, 192))
    st = ImageStat.Stat(g)
    return st.stddev[0] + 0.25 * st.mean[0]


def best_frame(mp4: str, tmp: Path, n: int = 10) -> tuple[Path | None, float]:
    """The most detailed frame between 15% and 85% of the clip (never the opening transition)."""
    d = duration(mp4) or 10.0
    best, best_t, score = None, d * 0.4, -1.0
    for i in range(n):
        t = d * (0.15 + 0.7 * i / max(n - 1, 1))
        f = frame(mp4, t, tmp / f"f{i}.png")
        if f and (s := detail(f)) > score:
            best, best_t, score = f, t, s
    return best, best_t


def best_offset(mp4: str) -> int:
    """thumb_offset in ms for the most detailed frame (fallback when the cover cannot be hosted)."""
    with tempfile.TemporaryDirectory() as d:
        return int(best_frame(mp4, Path(d))[1] * 1000)


def font(name: str, size: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONTS / name), size)


def wrap(draw, text: str, f, width: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=f) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


def fit(draw, text: str, name: str, start: int, width: int, max_lines: int, floor: int = 56):
    size = start
    while size > floor:
        f = font(name, size)
        lines = wrap(draw, text, f, width)
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= width for l in lines):
            return f, lines
        size -= 6
    f = font(name, floor)
    return f, wrap(draw, text, f, width)[:max_lines]


def clean_title(title: str) -> str:
    t = re.sub(r"#\w+", "", title.split("\n")[0]).strip()
    return re.sub(r"\s+", " ", t) or "Cosmos in Numbers"


def key_number(title: str) -> str | None:
    m = NUM.search(title)
    if not m:
        return None
    n = m[1].strip(" ,.")
    return n if re.search(r"\d", n) and len(n) <= 18 else None


def build(mp4: str, title: str, out: str | Path) -> Path:
    from PIL import Image, ImageDraw, ImageFilter
    title = clean_title(title)
    out = Path(out)
    with tempfile.TemporaryDirectory() as d:
        bg_path, _ = best_frame(mp4, Path(d))
        bg = Image.open(bg_path).convert("RGB") if bg_path else Image.new("RGB", (W, H), BRAND["space"])
    bg = bg.resize((W, H)).filter(ImageFilter.GaussianBlur(34))
    # darken towards the brand navy, stronger in the middle where the text is
    shade = Image.new("RGB", (W, H), BRAND["space"])
    mask = Image.new("L", (W, H))
    md = ImageDraw.Draw(mask)
    for y in range(H):
        mid = 1 - abs(y - H / 2) / (H / 2)
        md.line([(0, y), (W, y)], fill=int(175 + 60 * mid))
    im = Image.composite(shade, bg, mask)
    dr = ImageDraw.Draw(im)
    # a few stars so even a black clip gives a "space" cover
    import random
    rnd = random.Random(title)
    for _ in range(140):
        x, y, r = rnd.randrange(W), rnd.randrange(H), rnd.choice((1, 1, 1, 2, 2, 3))
        c = rnd.randrange(120, 230)
        dr.ellipse((x - r, y - r, x + r, y + r), fill=(c, c, min(255, c + 20)))

    margin = 80
    width = W - 2 * margin
    num = key_number(title)
    brand_f = font("SpaceGrotesk-Bold.ttf", 40)
    blocks = []  # (lines, font, colour, line gap)
    if num:
        nf, nl = fit(dr, num.upper(), "SpaceGrotesk-Bold.ttf", 230, width, 2, 110)
        blocks.append((nl, nf, BRAND["amber"], 1.0))
    tf, tl = fit(dr, title.upper(), "SpaceGrotesk-Bold.ttf", 120 if not num else 84, width, 5 if not num else 4)
    blocks.append((tl, tf, BRAND["star"], 1.12))

    heights = []
    for lines, f, _, gap in blocks:
        heights.append(sum(int(f.size * gap) for _ in lines))
    total = 60 + sum(heights) + 50 * (len(blocks) - 1) + 120  # brand line, gap, blocks, CTA
    y = SAFE_TOP + max(0, (SAFE_BOTTOM - SAFE_TOP - total) // 2)
    dr.text((W // 2, y), "COSMOS IN NUMBERS", font=brand_f, fill=BRAND["cyan"], anchor="mt")
    y += 60 + 20
    for (lines, f, colour, gap), h in zip(blocks, heights):
        for line in lines:
            dr.text((W // 2 + 3, y + 4), line, font=f, fill=(0, 0, 0), anchor="mt")  # soft drop shadow
            dr.text((W // 2, y), line, font=f, fill=colour, anchor="mt")
            y += int(f.size * gap)
        y += 50
    # accent bar under the text block
    dr.rounded_rectangle((W // 2 - 90, y, W // 2 + 90, y + 10), radius=5, fill=BRAND["cyan"])
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "JPEG", quality=90, optimize=True)
    return out


def host(path: Path, name: str) -> str | None:
    """Upload to cosmosinnumbers.github.io/media/covers/<name> and return a URL that answers 200, else None."""
    tok = (os.environ.get("PAGES_TOKEN") or "").strip()
    if not tok:
        print("cover: no PAGES_TOKEN, using thumb_offset")
        return None
    head = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    api = f"{PAGES}/{name}"
    try:
        old = requests.get(api, headers=head, timeout=60)
        body = {"message": f"media: copertina Reel {name}", "content": base64.b64encode(path.read_bytes()).decode()}
        if old.status_code == 200:
            body["sha"] = old.json()["sha"]
        r = requests.put(api, headers=head, timeout=120, json=body)
        if r.status_code not in (200, 201):
            print(f"cover: github.io upload HTTP {r.status_code}, using thumb_offset")
            return None
        for url, wait in ((f"{PUBLIC}/{name}", 180), (f"{RAW}/{name}", 30)):  # Pages deploys in ~1 min
            end = time.time() + wait
            while time.time() < end:
                if requests.head(url, timeout=30, allow_redirects=True).status_code == 200:
                    return url
                time.sleep(10)
    except requests.RequestException as e:
        print(f"cover: hosting failed ({type(e).__name__}), using thumb_offset")
        return None
    print("cover: not reachable yet, using thumb_offset")
    return None


def for_reel(mp4: str, title: str) -> dict:
    """Extra params for the IG REELS container: {"cover_url": ...} or {"thumb_offset": ms}. Never raises."""
    try:
        name = re.sub(r"[^a-z0-9-]+", "-", Path(mp4).stem.lower()).strip("-")[:60] or "reel"
        cover = build(mp4, title, Path(tempfile.gettempdir()) / f"{name}.jpg")
        url = host(cover, f"{name}.jpg")
        if url:
            print("cover:", url)
            return {"cover_url": url}
    except Exception as e:  # noqa: BLE001  (a cover must never block the Reel)
        print(f"cover: build failed ({type(e).__name__}: {str(e)[:120]}), using thumb_offset")
    try:
        return {"thumb_offset": str(best_offset(mp4))}
    except Exception:  # noqa: BLE001
        return {"thumb_offset": "2000"}


def local_cover(mp4: str, title: str) -> Path | None:
    """The cover JPEG on disk (Facebook takes it as the `thumb` file), or None."""
    try:
        name = re.sub(r"[^a-z0-9-]+", "-", Path(mp4).stem.lower()).strip("-")[:60] or "reel"
        return build(mp4, title, Path(tempfile.gettempdir()) / f"{name}-fb.jpg")
    except Exception as e:  # noqa: BLE001
        print(f"cover: build failed ({type(e).__name__}), Facebook picks its own")
        return None


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    print(build(a[0], a[1], a[2] if len(a) > 2 else Path(a[0]).with_suffix(".cover.jpg")))
    print(json.dumps({"key_number": key_number(clean_title(a[1]))}))
