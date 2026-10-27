"""Vertical Shorts (1080x1920) cut from a long video's verified material.

  python short.py <short_dir> [--reuse-voice | --meta-only]

<short_dir>/short.yaml:
  id, title, headline, voice, speed, assets_from (long-video dir), narration,
  visuals: [{src, motion, start}], sources: [{id,title,url}], description_intro
  A visual can be an image/chart or a video clip (type: video in assets.yaml, from stock.py: NASA, Pexels, Pixabay).
  No channel banner on screen (owner's decision 22/10/2026); add `promo:` to a short.yaml only if wanted.
Re-uses the long video's assets.yaml (same licences, same credits) and sources.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import render  # noqa: E402
import meta  # noqa: E402
import voice  # noqa: E402
from common import BRAND, CHANNEL, FPS, ffmpeg_exe, font, load_json, load_yaml, run, save_json  # noqa: E402

SW, SH = 1080, 1920
VIS_W, VIS_H = 1080, 900          # visual box (taller since 22/10/2026: more room for real footage)
ZOOM = {"image": 0.10, "chart": 0.04}   # charts barely move so axis labels never leave the box


def short_canvas(path, kind, fit=None):
    """Canvas 1.12x the visual box. Photos fill it when the aspect allows; charts, infographics
    and square images sit whole (charts on the brand background, the rest on a blurred copy)."""
    img = Image.open(path).convert("RGB")
    cw, ch = int(VIS_W * 1.12), int(VIS_H * 1.12)
    ar = img.width / img.height
    if kind == "chart":
        bg = Image.new("RGB", (cw, ch), BRAND["space"])
        s = min(cw / (1 + ZOOM["chart"]) * 0.97 / img.width, ch / (1 + ZOOM["chart"]) * 0.97 / img.height)
    elif fit != "contain" and 1.15 <= ar <= 1.8:
        s = max(cw / img.width, ch / img.height)
        img = img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.LANCZOS)
        x, y = (img.width - cw) // 2, (img.height - ch) // 2
        return img.crop((x, y, x + cw, y + ch))
    else:
        dark = render.dark_border(img)
        if dark:
            bg = Image.new("RGB", (cw, ch), dark)
        else:
            s = max(cw / img.width, ch / img.height)
            bg = img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.BILINEAR)
            x, y = (bg.width - cw) // 2, (bg.height - ch) // 2
            bg = bg.crop((x, y, x + cw, y + ch)).filter(ImageFilter.GaussianBlur(40))
            bg = Image.blend(bg, Image.new("RGB", bg.size, BRAND["space"]), 0.55)
        s = min(cw / 1.10 * 0.96 / img.width, ch / 1.10 * 0.96 / img.height)
    fg = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    bg.paste(fg, ((cw - fg.width) // 2, (ch - fg.height) // 2))
    return bg


def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textbbox((0, 0), t, font=f)[2] <= max_w:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def caption_chunks(timings):
    out = []
    for seg in timings["segments"]:
        for s in seg["sentences"]:
            words = s["text"].split()
            groups = [words[i:i + 4] for i in range(0, len(words), 4)]
            total = sum(len(" ".join(g)) for g in groups)
            t = s["start"]
            for g in groups:
                d = (s["end"] - s["start"]) * len(" ".join(g)) / total
                out.append((t, t + d, " ".join(g)))
                t += d
    return out


def write_upload(sd, spec, src_dir, assets, dur):
    """out/upload.md: title, description (sources, credits, disclosures), Studio settings."""
    long_src = load_yaml(src_dir / "script.yaml").get("sources", [])
    used = [s for s in long_src if s["id"] in set(spec.get("sources", []))]
    imgs = [assets[v["src"]] for v in spec["visuals"] if assets[v["src"]]["type"] in ("image", "video")]
    credits = sorted({a["credit"] for a in imgs if a.get("credit")})
    product = "📘 LOOK UP, our beginner's stargazing guide: https://cosmosinnumbers.gumroad.com/l/look-up (code LAUNCH9 → $9 until Nov 30)"
    lines = [product, "", spec["description_intro"].strip(), "", "Sources:", *[f"- {s['title']} — {s['url']}" for s in used], ""]
    if credits:
        lines += ["Images and footage: " + "; ".join(credits) + ".", meta.NO_ENDORSEMENT, ""]
    lines += [*meta.DISCLOSURES, "", "Full video on the channel. #shorts #space"]
    desc = "\n".join(lines)
    md = [f"# {spec['id']}", "", "Visibility: **Private** until H4.", ""]
    if spec.get("publish_note"):
        md += [f"> **Before publishing:** {spec['publish_note']}", ""]
    md += ["## Title", spec["title"], "", "## Description", "```", desc, "```", "", "## Studio settings",
           "- Audience: **No, it's not made for kids**",
           "- Altered or synthetic content: **No** — real imagery and charts; the synthetic narrator does not "
           "impersonate a real person",
           f"- Related video: the long video in `{spec['assets_from'].split('/')[-1]}` (must already be public)",
           f"- Captions are burned in. Duration: {dur:.1f}s"]
    (sd / "out" / "upload.md").write_text("\n".join(md) + "\n", "utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sd = Path(sys.argv[1]).resolve()
    spec = load_yaml(sd / "short.yaml")
    src_dir = (sd / spec["assets_from"]).resolve()
    assets = load_yaml(src_dir / "assets.yaml")
    build = sd / "build"; out = sd / "out"; build.mkdir(exist_ok=True); out.mkdir(exist_ok=True)
    if "--meta-only" in sys.argv:
        write_upload(sd, spec, src_dir, assets, load_json(build / "short_meta.json")["duration"])
        return
    script = {"voice": spec.get("voice", "af_heart"), "speed": spec.get("speed", 1.2), "lang": spec.get("lang", "en-us"),
              "segments": [{"id": "short", "narration": spec["narration"]}]}
    if "--reuse-voice" in sys.argv and (build / "timings.json").exists():
        timings = load_json(build / "timings.json")
    else:
        timings = voice.synth(script, build)
    dur = timings["duration"]
    print(f"short narration {dur:.1f}s")

    # prepare visuals for the box under the headline
    vis = []
    for v in spec["visuals"]:
        a = assets[v["src"]]
        label = "ARTIST'S CONCEPT" if a.get("kind") == "illustration" else None
        if a["type"] == "video":   # real footage: frames read in order while the clip is on screen
            clip = render.VideoReader(src_dir / a["file"], VIS_W, VIS_H, v.get("start", 0.0))
            vis.append((clip, a.get("credit", ""), label, "video", 0))
            continue
        kind = "chart" if a["type"] == "chart" else "image"
        canvas = short_canvas(src_dir / a["file"], kind, v.get("fit"))
        vis.append((canvas, a.get("credit", ""), label, v.get("motion", "zoom_in"), ZOOM[kind]))
    per = dur / len(vis)
    caps = caption_chunks(timings)

    head_f = font("display", 66, 700)
    cap_f = font("display", 70, 700)
    small = font("text", 26, 500)
    base = Image.new("RGB", (SW, SH), BRAND["space"])
    d0 = ImageDraw.Draw(base)
    y = 150
    for line in wrap(d0, spec["headline"].upper(), head_f, SW - 140):
        b = d0.textbbox((0, 0), line, font=head_f)
        d0.text(((SW - (b[2] - b[0])) // 2 - b[0], y), line, font=head_f, fill=BRAND["amber"])
        y += (b[3] - b[1]) + 18
    VIS_Y = max(y + 30, 470)
    CAP_Y = VIS_Y + VIS_H + 70
    # no channel tagline or "Full video on YouTube" banner by default (owner, 22/10/2026)
    promo = spec.get("promo")
    if promo:
        pf = font("display", 34, 700)
        pb = d0.textbbox((0, 0), promo, font=pf)
        pw, ph = pb[2] - pb[0] + 56, pb[3] - pb[1] + 30
        px, py = (SW - pw) // 2, 1505
        d0.rounded_rectangle((px, py, px + pw, py + ph), radius=ph // 2, fill=BRAND["amber"])
        d0.text((px + 28 - pb[0], py + 15 - pb[1]), promo, font=pf, fill=BRAND["space"])

    END_CTA_S = spec.get("end_cta_seconds", 3.0)
    end_cta = spec.get("end_cta", ["LOOK UP", "Stargazing guide: link in bio · code LAUNCH9"])
    cta_big, cta_small = font("display", 92, 700), font("text", 38, 600)

    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-pix_fmt", "yuv420p", str(build / "video_noaudio.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = round(dur * FPS)
    for i in range(n):
        t = i / FPS
        k = min(len(vis) - 1, int(t // per))
        canvas, credit, label, motion, zr = vis[k]
        if motion == "video":
            frame_vis = canvas.next()
        else:
            p = render.ease((t - k * per) / per)
            z = 1.0 + zr * p if motion != "zoom_out" else 1.0 + zr - zr * p
            cw, ch = canvas.size
            bw, bh = cw / z, ch / z
            frame_vis = canvas.resize((VIS_W, VIS_H), Image.BILINEAR, box=((cw - bw) / 2, (ch - bh) / 2, (cw + bw) / 2, (ch + bh) / 2))
        f = base.copy()
        f.paste(frame_vis, (0, VIS_Y))
        d = ImageDraw.Draw(f)
        if credit:
            d.text((24, VIS_Y + VIS_H + 12), (f"Video: {credit}" if motion == "video" else f"Image: {credit}")[:80], font=font("text", 22, 500), fill=BRAND["dust"])
        if label:
            d.rounded_rectangle((24, VIS_Y + 20, 300, VIS_Y + 64), radius=6, fill=BRAND["amber"])
            d.text((38, VIS_Y + 28), label, font=font("display", 24, 700), fill=BRAND["space"])
        if t >= dur - END_CTA_S:
            # end-of-video CTA (owner's rule, 17/10/2026): keyword comment + free chapter, every Short
            a = min(1.0, (t - (dur - END_CTA_S)) / 0.4)
            band = Image.new("RGBA", (SW, 230), (11, 16, 38, int(225 * a)))
            bd = ImageDraw.Draw(band)
            k1, k2 = end_cta
            b1 = bd.textbbox((0, 0), k1, font=cta_big); b2 = bd.textbbox((0, 0), k2, font=cta_small)
            bd.text(((SW - b1[2]) // 2, 34), k1, font=cta_big, fill=(246, 173, 85, int(255 * a)))
            bd.text(((SW - b2[2]) // 2, 150), k2, font=cta_small, fill=(237, 239, 247, int(255 * a)))
            f.paste(band, (0, VIS_Y + VIS_H - 230), band)
            d = ImageDraw.Draw(f)
        cap = next((c for a_, b_, c in caps if a_ <= t < b_), "")
        if cap:
            yy = CAP_Y
            for line in wrap(d, cap, cap_f, SW - 140):
                bb = d.textbbox((0, 0), line, font=cap_f)
                x = (SW - (bb[2] - bb[0])) // 2 - bb[0]
                d.text((x, yy), line, font=cap_f, fill=BRAND["star"], stroke_width=6, stroke_fill=(0, 0, 0))
                yy += (bb[3] - bb[1]) + 14
        proc.stdin.write(f.tobytes())
    proc.stdin.close(); proc.wait()
    for v_ in vis:
        if v_[3] == "video":
            v_[0].close()

    render.render_audio({"music": spec.get("music", {"seed": 5, "mood": "wonder"})}, sd, timings, [])
    dest = out / f"{spec['id']}.mp4"
    run([ffmpeg_exe(), "-hide_banner", "-y", "-i", build / "video_noaudio.mp4", "-i", build / "mix.wav",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", dest])
    write_upload(sd, spec, src_dir, assets, dur)
    save_json(build / "short_meta.json", {"duration": dur, "captions": len(caps)})
    print("->", dest)


if __name__ == "__main__":
    main()
