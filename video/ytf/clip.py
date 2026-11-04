"""Vertical clip (1080x1920) cut from a finished long video, for Instagram Reels and TikTok.

  python clip.py <long_video_dir> <clip_id> <start_s> <end_s> "<headline>"

Takes out/<id>.mp4 and out/<id>.srt of the long video: the real frames and the real mix (narration + score),
no new voice and no new facts. Layout: headline on top, the 16:9 frame whole in the middle on a blurred
copy of itself, captions burned under it, and for the last 3.5 s the closing card
"FULL VIDEO ON YOUTUBE" + LOOK UP (owner's request 26/10/2026: clips point to YouTube and/or Gumroad).
Motion and sound (owner 04/11/2026, after the light-year clip hit 1,000+ views on Instagram): headline pop-in, slow
push-in on the frame with a punch-in on every caption that brings a number, numbers in amber, a progress bar, and
CC0/synthesised effects (whoosh, ticks on the numbers, hit on the end card) mixed under the long video's audio.
Output: <long_video_dir>/clips/<clip_id>/out/<clip_id>.mp4 and caption.txt. Never uploads.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import render  # noqa: E402
from common import BRAND, FPS, ffmpeg_exe, font, load_yaml, run  # noqa: E402
from short import wrap  # noqa: E402

SW, SH = 1080, 1920
VW, VH = 1080, 608
VIS_Y = 600
END_S = 3.5


def srt_blocks(path: Path):
    out = []
    for b in re.split(r"\n\s*\n", path.read_text("utf-8").strip()):
        lines = b.strip().splitlines()
        if len(lines) < 3:
            continue
        m = re.findall(r"(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        t0, t1 = [int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000 for h, mi, s, ms in m[:2]]
        out.append((t0, t1, " ".join(lines[2:])))
    return out


NUM = re.compile(r"\d")


def zoomed(img: Image.Image, z: float) -> Image.Image:
    """The frame scaled by z around its centre, cropped back to VW x VH."""
    if z <= 1.001:
        return img
    w, h = round(VW * z), round(VH * z)
    big = img.resize((w, h), Image.BILINEAR)
    x, y = (w - VW) // 2, (h - VH) // 2
    return big.crop((x, y, x + VW, y + VH))


def draw_caption_line(d, line: str, f, y: int) -> None:
    """Centered caption line; words with a number in amber (the number is the story)."""
    words = line.split()
    space = d.textbbox((0, 0), " ", font=f)[2]
    widths = [d.textbbox((0, 0), w, font=f)[2] for w in words]
    x = (SW - (sum(widths) + space * (len(words) - 1))) // 2
    for w, wd in zip(words, widths):
        d.text((x, y), w, font=f, fill=BRAND["amber"] if NUM.search(w) else BRAND["star"], stroke_width=6,
               stroke_fill=(0, 0, 0))
        x += wd + space


def sfx_track(build: Path, dur: float, punch_at: list[float]) -> Path | None:
    """Effects track (video/ytf/sfx.py: CC0 library or our own synthesis). None if numpy/soundfile are missing:
    the clip then keeps only the long video's mix."""
    try:
        import soundfile as sf
        import sfx
    except Exception:  # noqa: BLE001
        return None
    ev = [(0.05, "whoosh"), (0.35, "pop")] + [(p, "tick") for p in punch_at if p > 0.8] + [(dur - END_S, "impact")]
    p = build / "sfx.wav"
    sf.write(str(p), sfx.track(dur, ev, seed=len(punch_at) + int(dur)), sfx.SR)
    return p


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    vd, cid, t0, t1, headline = Path(sys.argv[1]).resolve(), sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
    script = load_yaml(vd / "script.yaml")
    src = vd / "out" / f"{script['id']}.mp4"
    caps = srt_blocks(vd / "out" / f"{script['id']}.srt")
    cd = vd / "clips" / cid
    build, out = cd / "build", cd / "out"
    build.mkdir(parents=True, exist_ok=True); out.mkdir(parents=True, exist_ok=True)
    dur = t1 - t0
    n = round(dur * FPS)

    reader = subprocess.Popen([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-ss", str(t0), "-t", str(dur),
                               "-i", str(src), "-an", "-vf", f"scale={VW}:{VH},fps={FPS}", "-f", "rawvideo",
                               "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    writer = subprocess.Popen([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                               "-pix_fmt", "rgb24", "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                               "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(build / "video.mp4")],
                              stdin=subprocess.PIPE)
    head_f, cap_f = font("display", 64, 700), font("display", 64, 700)
    # captions that bring a number: punch-in on the frame + a sound on the beat
    punch_at = [max(0.0, a - t0) for a, b_, c in caps if t0 <= a < t1 - END_S and NUM.search(c)][:8]
    big, mid, small = font("display", 84, 700), font("display", 52, 700), font("text", 38, 600)
    last = Image.new("RGB", (VW, VH), BRAND["space"])
    for i in range(n):
        t = i / FPS
        buf = reader.stdout.read(VW * VH * 3)
        if len(buf) == VW * VH * 3:
            last = Image.frombytes("RGB", (VW, VH), buf)
        # blurred fill behind the frame (blur at low resolution: cheap)
        f = last.resize((54, 96), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3)).resize((SW, SH), Image.BILINEAR)
        f = Image.blend(f, Image.new("RGB", (SW, SH), BRAND["space"]), 0.6)
        # motion (owner 04/11/2026: "più animazioni"): slow push-in over the whole clip + a short punch-in when a
        # caption with a number lands (the 03/11 hit was all animated numbers)
        punch = max((0.045 * (1 - render.ease((t - pt) / 0.35)) for pt in punch_at if 0 <= t - pt < 0.35), default=0.0)
        f.paste(zoomed(last, 1.0 + 0.07 * t / max(dur, 1) + punch), (0, VIS_Y))
        d = ImageDraw.Draw(f)
        # progress bar under the frame: how much is left (keeps people to the end)
        d.rectangle((0, VIS_Y + VH, SW, VIS_Y + VH + 8), fill=(30, 36, 64))
        d.rectangle((0, VIS_Y + VH, int(SW * min(1.0, t / dur)), VIS_Y + VH + 8), fill=BRAND["amber"])
        # headline pops in from above in the first 0.4 s
        k = render.ease_out(t / 0.4)
        y = 190 - int(60 * (1 - k))
        for line in wrap(d, headline.upper(), head_f, SW - 120):
            b = d.textbbox((0, 0), line, font=head_f)
            d.text(((SW - (b[2] - b[0])) // 2 - b[0], y), line, font=head_f,
                   fill=tuple(int(c * k) for c in BRAND["amber"]), stroke_width=4, stroke_fill=(0, 0, 0))
            y += (b[3] - b[1]) + 18
        cap = next((c for a, b_, c in caps if a <= t0 + t < b_), "")
        yy = VIS_Y + VH + 90
        for line in wrap(d, cap, cap_f, SW - 120):
            draw_caption_line(d, line, cap_f, yy)
            bb = d.textbbox((0, 0), line, font=cap_f)
            yy += (bb[3] - bb[1]) + 14
        if t >= dur - END_S:   # closing card over the frame, captions keep running under it
            a = render.ease((t - (dur - END_S)) / 0.4)
            card = Image.new("RGBA", (SW - 80, 440), (11, 16, 38, int(235 * a)))
            cdw = ImageDraw.Draw(card)
            for txt, fnt, col, yy in (("FULL VIDEO ON YOUTUBE", big, BRAND["amber"], 40),
                                      ("@CosmosinNumbers", mid, BRAND["star"], 160),
                                      ("LOOK UP · stargazing guide", small, BRAND["cyan"], 270),
                                      ("link in bio · code COSMOS9", small, BRAND["star"], 330)):
                bb = cdw.textbbox((0, 0), txt, font=fnt)
                cdw.text(((card.width - (bb[2] - bb[0])) // 2 - bb[0], yy), txt, font=fnt, fill=col + (int(255 * a),))
            f.paste(card, (40, VIS_Y + (VH - card.height) // 2), card)
        writer.stdin.write(f.tobytes())
    reader.kill()
    writer.stdin.close(); writer.wait()
    dest = out / f"{cid}.mp4"
    fade = f"afade=t=in:d=0.25,afade=t=out:st={dur - 0.6:.2f}:d=0.6"
    fx = sfx_track(build, dur, punch_at)
    if fx:   # sound design on top of the long video's own mix: whoosh in, a tick on every number, hit on the end card
        run([ffmpeg_exe(), "-hide_banner", "-y", "-i", build / "video.mp4", "-ss", str(t0), "-t", str(dur), "-i", src,
             "-i", fx, "-filter_complex", f"[1:a]{fade}[m];[2:a]volume=0.8[f];[m][f]amix=inputs=2:duration=first:normalize=0[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", dest])
    else:
        run([ffmpeg_exe(), "-hide_banner", "-y", "-i", build / "video.mp4", "-ss", str(t0), "-t", str(dur), "-i", src,
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", fade, "-c:a", "aac", "-b:a", "192k", "-shortest",
             "-movflags", "+faststart", dest])
    (out / "caption.txt").write_text(
        f"{headline}\n\nFull video on YouTube: \"{script['title']}\" @CosmosinNumbers (link in bio)\n"
        "📘 LOOK UP stargazing guide: link in bio · code COSMOS9\n\n"
        "Sources in the YouTube description. Synthetic voice; script drafted with AI assistance and fact-checked.\n"
        "#space #astronomy #science\n", "utf-8")
    print(f"-> {dest} ({dur:.1f}s, from {t0:.1f}s of {src.name})")


if __name__ == "__main__":
    main()
