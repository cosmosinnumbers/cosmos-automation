"""Vertical clip (1080x1920) cut from a finished long video, for Instagram Reels and TikTok.

  python clip.py <long_video_dir> <clip_id> <start_s> <end_s> "<headline>"

Takes out/<id>.mp4 and out/<id>.srt of the long video: the real frames and the real mix (narration + score),
no new voice and no new facts. Layout: headline on top, the 16:9 frame whole in the middle on a blurred
copy of itself, captions burned under it, and for the last 3.5 s the closing card
"FULL VIDEO ON YOUTUBE" + LOOK UP (owner's request 26/10/2026: clips point to YouTube and/or Gumroad).
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
        f.paste(last, (0, VIS_Y))
        d = ImageDraw.Draw(f)
        y = 190
        for line in wrap(d, headline.upper(), head_f, SW - 120):
            b = d.textbbox((0, 0), line, font=head_f)
            d.text(((SW - (b[2] - b[0])) // 2 - b[0], y), line, font=head_f, fill=BRAND["amber"],
                   stroke_width=4, stroke_fill=(0, 0, 0))
            y += (b[3] - b[1]) + 18
        cap = next((c for a, b_, c in caps if a <= t0 + t < b_), "")
        yy = VIS_Y + VH + 90
        for line in wrap(d, cap, cap_f, SW - 120):
            bb = d.textbbox((0, 0), line, font=cap_f)
            d.text(((SW - (bb[2] - bb[0])) // 2 - bb[0], yy), line, font=cap_f, fill=BRAND["star"],
                   stroke_width=6, stroke_fill=(0, 0, 0))
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
