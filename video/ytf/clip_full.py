"""Full-screen layout of the vertical clips (owner 21/11/2026, screenshot of the Shorts tab: "I like more clean
thumbnails like the purple one, full screen video, and don't put any label that stays in the video").

Before: the 16:9 frame of the long video sat in a 1080x608 box on a blurred copy of itself, with the headline
fixed on top for the whole clip and a caption band under the box. The grid of the channel showed a band of title,
a small picture and a band of text: the "purple" Short (b1119, full-bleed NASA picture) was the only clean one.

Now (clip.py, default layout; env CLIP_LAYOUT=box gives the old look back):
  - the picture fills the whole 1080x1920 frame. The clip is split into shots (cuts of the long video):
      * picture shots (photo, render, footage) are cropped to 9:16 around their most detailed area, with a slow
        push-in and a punch-in on every number (the corner labels of the long video stay outside the crop);
      * graphic shots of the long video (navy cards, dot charts, wide text layouts: a 9:16 crop of them is a
        broken word) are covered by the long video's own NASA pictures/footage (assets.yaml, matched to the words
        of the shot), framed like the full-bleed Shorts (fullbleed.Visual: a new framing every ~2.6 s);
        no picture at all: the frame whole on a blurred copy of itself.
  - no text that stays: the headline only slams in during the 1.7 s opener; then only the captions under the
    voice (3 words, the spoken word amber, fullbleed.draw_caption), the thin progress bar, and the closing card
    "FULL VIDEO ON YOUTUBE" in the last 3.5 s. "ARTIST'S CONCEPT" (honesty, owner rule) shows 1.5 s when an
    illustration starts, never for the whole shot.
Audio is untouched: the long video's own mix (clip.py adds the effects).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import fullbleed
import motion
import render
from common import BRAND, FPS, ffmpeg_exe, font, load_yaml

SW, SH = 1080, 1920
LW, LH = 96, 54                 # analysis size
FW, FH = 1920, 1080             # the long video is read at this size
NAVY = np.array(BRAND["space"], np.int16)
CUT_DIFF = 22.0                 # mean abs difference (0-255) between analysis frames = a cut
GRAPHIC_NAVY = 0.35             # share of brand-navy pixels above which a shot is one of our graphic cards
MIN_SHOT = 0.35
# the 9:16 window (608 px of 1920) stays off the image credit of the long video (bottom-right, x > 1750) and
# off its left edge; the chapter lower third is handled by chapter_card()
FX_MIN, FX_MAX = 0.36, 0.74
GRAPHIC_PART = 6.5              # seconds of one picture over a long graphic stretch
LABEL_S = 1.5
NUM = re.compile(r"\d")
STOP = set("the a an of and or to in on at for from with by is are was were be it its this that these those as "
           "into than then over under about after before our their his her new".split())


# ---------- analysis ----------
def analyse(src: Path, t0: float, dur: float) -> list[dict]:
    """Shots of the clip: [{t0, t1, graphic, fx, illus}] in clip time (0..dur)."""
    raw = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-ss", str(t0), "-t", str(dur),
                          "-i", str(src), "-an", "-vf", f"scale={LW}:{LH},fps={FPS}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    n = len(raw) // (LW * LH * 3)
    if n == 0:
        return [{"t0": 0.0, "t1": dur, "graphic": False, "fx": 0.5, "illus": False}]
    a = np.frombuffer(raw[:n * LW * LH * 3], np.uint8).reshape(n, LH, LW, 3).astype(np.int16)
    navy = (np.abs(a - NAVY).sum(-1) < 30).mean(axis=(1, 2))
    diff = np.r_[0, np.abs(a[1:] - a[:-1]).mean(axis=(1, 2, 3))]
    cuts = [0] + [i for i in range(1, n) if diff[i] > CUT_DIFF] + [n]
    shots = []
    for s, e in zip(cuts, cuts[1:]):
        if e <= s:
            continue
        if shots and (e - s) / FPS < MIN_SHOT:      # a flash / a transition frame: part of the shot before
            shots[-1]["e"] = e
            continue
        shots.append({"s": s, "e": e})
    if len(shots) > 1 and (shots[0]["e"] - shots[0]["s"]) / FPS < MIN_SHOT:   # a fade-in frame at the start
        shots[1]["s"] = 0
        shots.pop(0)
    out = []
    for sh in shots:
        s, e = sh["s"], sh["e"]
        mid = a[(s + e) // 2].astype(np.uint8)
        graphic = float(np.median(navy[s:e])) > GRAPHIC_NAVY
        fx, _ = fullbleed.focus(Image.fromarray(mid), (FH * 9 / 16) / FW, 1.0)
        base = {"graphic": graphic, "fx": min(FX_MAX, max(FX_MIN, fx)), "illus": False}
        # graphic cards that fade into each other give no cut: a long graphic stretch gets several pictures
        parts = max(1, round((e - s) / FPS / GRAPHIC_PART)) if graphic else 1
        for j in range(parts):
            out.append({**base, "t0": (s + (e - s) * j / parts) / FPS, "t1": (s + (e - s) * (j + 1) / parts) / FPS})
    out[0]["t0"] = 0.0
    out[-1]["t1"] = max(out[-1]["t1"], dur)
    return out


def chapter_card(frame: Image.Image) -> bool:
    """The long video's chapter lower third ("CHAPTER 02 / Why fly by instead of orbit", x 80-980, y 825-960 at
    1920x1080, with a cyan bar on its left): a label the 9:16 crop must not show half of."""
    b = np.asarray(frame.crop((81, 845, 87, 940))).astype(np.int16)
    return bool((np.abs(b - np.array(BRAND["cyan"], np.int16)).sum(-1) < 90).mean() > 0.6)


def is_illustration(frame: Image.Image) -> bool:
    """The long video marks illustrations with an amber "ARTIST'S CONCEPT" pill top-left (x 36-200, y 32-48 at
    1920x1080): the crop leaves it out, so the clip shows its own pill for LABEL_S seconds."""
    r = np.asarray(frame.crop((20, 20, 220, 56))).astype(np.int16)
    return bool((np.abs(r - np.array(BRAND["amber"], np.int16)).sum(-1) < 60).mean() > 0.12)


# ---------- pictures of the long video ----------
def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP}


GENERIC = set("close closeup image images view views artist artists concept illustration photo picture mosaic color "
              "colour true false data nasa esa jpl caltech hubble webb telescope space".split())


def subject(title: str, key: str) -> set[str]:
    """What a picture shows: the capitalised words of its title and the words of its key, without generic ones
    ("Juno's Ganymede Close-up" -> juno, ganymede: "close passes" in the voice is not a match)."""
    caps = " ".join(re.findall(r"\b[A-Z][\w-]*", title))
    return {w for w in words(f"{caps} {key.replace('_', ' ')}") if w not in GENERIC and w != "img"}


def pictures(vd: Path) -> list[dict]:
    """Photos, illustrations and footage of the long video that exist on disk (no charts: they are graphics)."""
    p = vd / "assets.yaml"
    if not p.exists():
        return []
    out = []
    for key, a in (load_yaml(p) or {}).items():
        if not isinstance(a, dict) or a.get("type") not in ("image", "video") or a.get("kind") == "chart":
            continue
        f = vd / a.get("file", "")
        if f.exists() and a.get("check", "ok") == "ok":
            out.append({"key": key, "file": f, "type": a["type"], "illus": a.get("kind") == "illustration",
                        "credit": a.get("credit", ""), "words": subject(a.get("title", ""), key)})
    return out


def assign(shots: list[dict], pics: list[dict], caps: list, t_off: float) -> None:
    """Every graphic shot gets a picture of something the clip talks about, preferring one named in that very
    shot; a picture already used counts less (a 40 s clip about Clipper must not show the same render 4 times)."""
    used: dict[str, int] = {}
    clip_said = words(" ".join(c for a, b, c in caps if a < t_off + shots[-1]["t1"] and b > t_off))
    # a picture of something the clip never names (Callisto in a clip about Europa) would mislead: only when
    # nothing in the clip matches any picture title, every picture is allowed
    pics = [p for p in pics if p["words"] & clip_said] or pics
    for sh in shots:
        if not sh["graphic"] or not pics:
            continue
        said = words(" ".join(c for a, b, c in caps if a < t_off + sh["t1"] and b > t_off + sh["t0"]))
        best = max(pics, key=lambda p: (min(1, len(p["words"] & said)) - 0.75 * used.get(p["key"], 0),
                                        len(p["words"] & said)))
        used[best["key"]] = used.get(best["key"], 0) + 1
        sh["pic"] = best


# ---------- captions ----------
def caption_chunks(caps: list, t_off: float, dur: float, n: int = 3):
    """fullbleed.draw_caption chunks from the .srt blocks of the long video: every block's words spread over its
    time by length (the long video has no word timings in the release), up to n words per chunk."""
    out = []
    for a, b, text in caps:
        a, b = a - t_off, b - t_off
        if b <= 0 or a >= dur:
            continue
        ws = text.split()
        if not ws:
            continue
        lens = np.array([len(w) + 2 for w in ws], float)
        starts = a + (b - a) * np.r_[0, np.cumsum(lens)[:-1]] / lens.sum()
        wt = list(zip(starts.tolist(), ws))
        groups = [wt[i:i + n] for i in range(0, len(wt), n)]
        if len(groups) > 1 and len(groups[-1]) == 1:
            tail = groups.pop()
            groups[-1] = groups[-1] + tail
        for gi, g in enumerate(groups):
            end = groups[gi + 1][0][0] if gi + 1 < len(groups) else b
            out.append((g[0][0], end, g))
    return out


def scrim() -> Image.Image:
    """Dark gradient under the captions only (no headline on top any more) plus a light vignette."""
    y = np.arange(SH, dtype=np.float32)[:, None]
    x = np.arange(SW, dtype=np.float32)[None, :]
    top = np.clip(1 - y / 300, 0, 1) ** 2 * 90          # just enough for the app's own top bar
    bot = np.clip((y - 1050) / 700, 0, 1) ** 1.3 * 215
    vig = np.clip((np.hypot((x - SW / 2) / (SW * 0.75), (y - SH / 2) / (SH * 0.75)) - 0.55) / 0.6, 0, 1) * 100
    al = np.clip(np.maximum(np.maximum(top, bot) + np.zeros_like(x), vig), 0, 255).astype(np.uint8)
    out = np.zeros((SH, SW, 4), np.uint8)
    out[..., :3] = (5, 8, 20)
    out[..., 3] = al
    return Image.fromarray(out, "RGBA")


def label(d: ImageDraw.ImageDraw, text: str, a: float):
    f = font("display", 28, 700)
    b = d.textbbox((0, 0), text, font=f)
    w = b[2] - b[0] + 34
    x, y = 40, 150 - round((1 - a) * 20)
    d.rounded_rectangle((x, y, x + w, y + 48), radius=10, fill=BRAND["amber"])
    d.text((x + 17 - b[0], y + 24 - (b[3] - b[1]) / 2 - b[1]), text, font=f, fill=BRAND["space"])


def contain(frame: Image.Image) -> Image.Image:
    """Last resort for a graphic shot with no picture: the frame whole over a blurred copy of itself."""
    return fullbleed.contain_canvas(frame, "image").resize((SW, SH), Image.BILINEAR)


# ---------- render ----------
def frames(src: Path, vd: Path, t0: float, dur: float, caps: list, headline: str, writer, hook_s: float,
           whip_s: float, end_s: float, punch_at: list[float], slam, card) -> list[float]:
    """Writes every frame of the clip to writer.stdin. Returns the landing times of the opener words (sound)."""
    shots = analyse(src, t0, dur)
    pics = pictures(vd)
    assign(shots, pics, caps, t0)
    g = sum(1 for s in shots if s["graphic"])
    print(f"  full layout: {len(shots)} shots, {g} graphic -> "
          f"{sum(1 for s in shots if s.get('pic'))} covered by pictures ({len(pics)} available)")
    chunks = caption_chunks(caps, t0, dur)
    sc = scrim()
    reader = subprocess.Popen([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-ss", str(t0), "-t", str(dur),
                               "-i", str(src), "-an", "-vf", f"scale={FW}:{FH},fps={FPS}", "-f", "rawvideo",
                               "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    visuals: dict[int, fullbleed.Visual] = {}
    n = round(dur * FPS)
    last = Image.new("RGB", (FW, FH), BRAND["space"])
    slams: list[float] = []
    k = 0
    for i in range(n):
        t = i / FPS
        buf = reader.stdout.read(FW * FH * 3)
        if len(buf) == FW * FH * 3:
            last = Image.frombytes("RGB", (FW, FH), buf)
        while k < len(shots) - 1 and t >= shots[k]["t1"]:
            if k in visuals:
                visuals.pop(k).close()
            k += 1
        sh = shots[k]
        rel, span = t - sh["t0"], max(0.1, sh["t1"] - sh["t0"])
        if "seen" not in sh and rel >= min(1.2, span / 2):   # past the cross-fade into the shot
            sh["seen"] = True
            sh["illus"] = not sh["graphic"] and is_illustration(last)
        punch = max((0.05 * (1 - render.ease((t - pt) / 0.35)) for pt in punch_at if 0 <= t - pt < 0.35),
                    default=0.0)
        illus = sh["illus"]
        if sh["graphic"] and sh.get("pic"):
            if k not in visuals:
                p = sh["pic"]
                visuals[k] = fullbleed.Visual(p["file"], p["type"], index=k)
            v = visuals[k]
            n_sub = max(1, round(span / fullbleed.SUB_S))
            sub_len = span / n_sub
            sub = min(n_sub - 1, int(rel // sub_len))
            f = v.frame(sub, (rel - sub * sub_len) / sub_len)
            if punch > 0.005:
                f = zoom(f, 1 + punch)
            illus = sh["pic"]["illus"]
        elif sh["graphic"]:
            f = contain(last)
        else:
            z = (1.0 + 0.07 * rel / span + punch)
            low = chapter_card(last)
            if low:   # the long video's chapter lower third is on screen: frame only what is above it
                z = max(z, FH / 800)
            hh = FH / z
            hw = hh * 9 / 16
            cx = min(max(sh["fx"] * FW, hw / 2), FW - hw / 2)
            cy = hh / 2 if low else FH / 2
            f = last.resize((SW, SH), Image.BILINEAR, box=(cx - hw / 2, cy - hh / 2, cx + hw / 2, cy + hh / 2))
        if punch > 0.005:
            f = rgb_split(f, int(punch * 200))
        if t < hook_s:   # Katana opener: the full-screen picture dithered and dimmed, the headline slams on top
            bg = motion.dither(f.resize((SW // 8, SH // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3))
                               .resize((SW, SH), Image.BILINEAR), 4, 8)
            bg = Image.blend(bg, Image.new("RGB", (SW, SH), BRAND["space"]), 0.5)
            d = ImageDraw.Draw(bg)
            slams = slam(d, headline, t)
            hit = max((1 - (t - a) / 0.1 for a in slams if 0 <= t - a < 0.1), default=0.0)
            if hit > 0:
                bg = bg.transform(bg.size, Image.AFFINE, (1, 0, int(14 * hit) * (1 if i % 2 else -1), 0, 1, int(8 * hit)))
            if t - slams[0] < 0.07:
                bg = Image.blend(bg, Image.new("RGB", (SW, SH), (247, 250, 252)), 0.6)
            writer.stdin.write(bg.tobytes())
            continue
        f.paste(sc, (0, 0), sc)
        d = ImageDraw.Draw(f)
        rl = t - max(sh["t0"], hook_s + whip_s)       # an illustration under the opener gets its label after it
        if illus and 0 <= rl < LABEL_S + 0.3:
            a = min(1.0, rl / 0.2, (LABEL_S + 0.3 - rl) / 0.3)
            if a > 0.05:
                label(d, "ARTIST'S CONCEPT", a)
        if t < dur - end_s:
            fullbleed.draw_caption(d, chunks, t, size=84)
        else:
            card(f, t)
        d.rectangle((0, SH - 8, int(SW * (i + 1) / n), SH), fill=BRAND["cyan"])
        if t < hook_s + whip_s:
            f = motion.whip_in(f, (t - hook_s) / whip_s)
        writer.stdin.write(f.tobytes())
    reader.kill()
    for v in visuals.values():
        v.close()
    return slams


def zoom(img: Image.Image, z: float) -> Image.Image:
    w, h = img.width / z, img.height / z
    return img.resize(img.size, Image.BILINEAR, box=((img.width - w) / 2, (img.height - h) / 2,
                                                     (img.width + w) / 2, (img.height + h) / 2))


def rgb_split(img: Image.Image, px: int) -> Image.Image:
    if px < 1:
        return img
    a = np.asarray(img.convert("RGB")).copy()
    a[..., 0] = np.roll(a[..., 0], -px, axis=1)
    a[..., 2] = np.roll(a[..., 2], px, axis=1)
    return Image.fromarray(a)
