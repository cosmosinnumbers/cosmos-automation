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
import director  # noqa: E402
import motion  # noqa: E402
import render  # noqa: E402
import meta  # noqa: E402
import voice  # noqa: E402
from common import ROOT, BRAND, CHANNEL, FPS, ffmpeg_exe, font, load_json, load_yaml, run, save_json  # noqa: E402

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


def caption_words(timings):
    """Caption chunks of up to 4 words, each with the start time of every word (karaoke highlight)."""
    out = []
    for seg in timings["segments"]:
        for s in seg["sentences"]:
            wt = director.word_times(s)
            for i in range(0, len(wt), 4):
                g = wt[i:i + 4]
                end = wt[i + 4][0] if i + 4 < len(wt) else s["end"]
                out.append((g[0][0], end, g))
    return out


def draw_caption(d, caps, t, cap_f, y0):
    """The chunk under the voice, centred; the word being spoken in amber and slightly lifted."""
    cur = next((c for c in caps if c[0] <= t < c[1]), None)
    if not cur:
        return
    words = cur[2]
    space = d.textbbox((0, 0), " ", font=cap_f)[2]
    widths = [d.textbbox((0, 0), w, font=cap_f)[2] for _, w in words]
    lines, line, lw = [], [], 0
    for (wt, w), ww in zip(words, widths):
        if line and lw + space + ww > SW - 120:
            lines.append((line, lw)); line, lw = [], 0
        line.append((wt, w, ww)); lw += (space if lw else 0) + ww
    lines.append((line, lw))
    spoken = max((wt for wt, _ in words if wt <= t), default=None)
    y = y0
    for line, lw in lines:
        x = (SW - lw) // 2
        for wt, w, ww in line:
            now = wt == spoken
            lift = 6 if now else 0
            d.text((x, y - lift), w, font=cap_f, fill=BRAND["amber"] if now else BRAND["star"],
                   stroke_width=7, stroke_fill=(0, 0, 0))
            x += ww + space
        y += cap_f.size + 18


def backdrop(frame_vis):
    """Full-frame background: the current footage, heavily blurred and darkened (no flat empty bands)."""
    w = int(VIS_W * 0.47)
    small = frame_vis.resize((54, 96), Image.BILINEAR, box=((VIS_W - w) / 2, 0, (VIS_W + w) / 2, VIS_H))
    small = small.filter(ImageFilter.GaussianBlur(3))
    big = small.resize((SW, SH), Image.BILINEAR)
    return Image.blend(big, Image.new("RGB", (SW, SH), BRAND["space"]), 0.6)


SUBSHOT_S = 3.4   # no picture stays unchanged longer than this: every other sub-shot is a punch-in on the same footage


def punch(frame, sub: int, since: float):
    """Odd sub-shots are a tighter crop (alternating left/right) that pops in over 5 frames: a visible cut."""
    if sub % 2 == 0:
        return frame
    p = render.ease(min(1.0, since * FPS / 5))
    z = 1.0 + 0.2 * p
    w, h = frame.size
    bw, bh = w / z, h / z
    dx = (w - bw) * (0.35 if (sub // 2) % 2 == 0 else 0.65)
    dy = (h - bh) * 0.5
    return frame.resize((w, h), Image.BILINEAR, box=(dx, dy, dx + bw, dy + bh))


def advance(vis, per, t):
    """Under a full-screen scene, keep reading the clip of this moment so the footage resumes in sync."""
    k = min(len(vis) - 1, int(t // per))
    if vis[k][3] == "video":
        vis[k][0].next()


SOCIAL = ROOT / "assets" / "social"


def social_variant(sd, spec, timings, total, events):
    """out/<id>_social.mp4 for Instagram, Facebook and TikTok (owner 02/11/2026: on the other socials trending
    material is allowed): same picture, the generated score replaced by a sound from assets/social/sounds/,
    a library kept apart from YouTube's (YouTube never gets this file). The sound rotates by day of the year, or
    short.yaml `social_sound: <file name>`. No sound in the library: no variant, the socials get the main file."""
    sounds = sorted(p for p in (SOCIAL / "sounds").glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg", ".aac"))
    if not sounds or spec.get("social") is False:
        return None
    from datetime import date
    pick = next((p for p in sounds if p.name == spec.get("social_sound")), None) or sounds[date.today().timetuple().tm_yday % len(sounds)]
    build, out = sd / "build", sd / "out"
    render.render_audio({"music": spec.get("music", {})}, sd, timings, [], total=total, events=events or [(total + 1, "tick")],
                        music_file=pick, out="mix_social.wav")
    dest = out / f"{spec['id']}_social.mp4"
    run([ffmpeg_exe(), "-hide_banner", "-y", "-i", build / "video_noaudio.mp4", "-i", build / "mix_social.wav",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", dest])
    save_json(out / "social.json", {"sound": pick.name})
    return dest


def write_upload(sd, spec, src_dir, assets, dur):
    """out/upload.md: title, description (sources, credits, disclosures), Studio settings."""
    long_src = load_yaml(src_dir / "script.yaml").get("sources", [])
    used = [s for s in long_src if s["id"] in set(spec.get("sources", []))]
    imgs = [assets[v["src"]] for v in spec["visuals"] if assets[v["src"]]["type"] in ("image", "video")]
    credits = sorted({a["credit"] for a in imgs if a.get("credit")})
    product = "📘 LOOK UP, our beginner's stargazing guide: https://cosmosinnumbers.gumroad.com/l/look-up (code COSMOS9 → $9 until Nov 30)"
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
    caps = caption_words(timings)
    brand = spec.get("brand", "cosmos")

    # the director picks the effects from the narration; Remotion renders them (none if Node is missing)
    long_src = load_yaml(src_dir / "script.yaml").get("sources", []) if (src_dir / "script.yaml").exists() else []
    sources_full = [s for s in long_src if s["id"] in set(spec.get("sources", []))] or long_src
    plan = director.plan_short({**spec, "sources_full": sources_full}, timings, brand,
                               cut_times=[k * per for k in range(1, len(vis))]) if spec.get("motion", True) else \
        {"inserts": [], "transitions": [], "tail": 0.0, "events": []}
    plan = director.creative_pass(spec["narration"], plan)
    srcs = [(src_dir / assets[v["src"]]["file"], "video" if assets[v["src"]]["type"] == "video" else "image",
             v.get("start", 0.0)) for v in spec["visuals"] if assets[v["src"]]["type"] in ("video", "image")]
    tiles = motion.tiles(srcs) if plan["inserts"] and motion.available() else []
    jobs = []
    for k, ins in enumerate(plan["inserts"]):
        frames = max(6, round((ins["t1"] - ins["t0"]) * FPS))
        jobs.append({"effect": ins["effect"], "out": str(build / f"fx_{k:02d}_{ins['effect']}.mp4"),
                     "props": {"brand": brand, "tiles": tiles, **ins["props"], "width": SW, "height": SH, "fps": FPS,
                               "frames": frames}})
    done = motion.render_jobs(jobs, build)
    inserts = [dict(ins, file=j["out"]) for ins, j in zip(plan["inserts"], jobs) if j["out"] in done]
    tail = plan["tail"] if any(i["t0"] >= dur - 0.01 for i in inserts) else 0.0
    events = [e for e in plan["events"] if e[0] < dur + tail]
    if not inserts:   # no Remotion: only the live-frame transitions keep their sounds
        events = [e for e in events if e[1] in ("glitch", "whoosh", "impact")]
    save_json(build / "motion_plan.json", {"inserts": [{k: v for k, v in i.items() if k != "props"} for i in inserts],
                                           "transitions": plan["transitions"], "tail": tail, "events": events})
    total = dur + tail
    trans = {round(t * FPS): eff for t, eff in plan["transitions"]}

    head_f = font("display", 66, 700)
    cap_f = font("display", 78, 700)
    head_lines = wrap(ImageDraw.Draw(Image.new("RGB", (8, 8))), spec["headline"].upper(), head_f, SW - 140)
    head = Image.new("RGBA", (SW, 60 + 84 * len(head_lines)), (0, 0, 0, 0))
    dh = ImageDraw.Draw(head)
    y = 10
    for line in head_lines:
        b = dh.textbbox((0, 0), line, font=head_f)
        dh.text(((SW - (b[2] - b[0])) // 2 - b[0], y), line, font=head_f, fill=BRAND["amber"],
                stroke_width=4, stroke_fill=(0, 0, 0))
        y += (b[3] - b[1]) + 18
    VIS_Y = max(150 + y + 20, 470)
    CAP_Y = VIS_Y + VIS_H + 70
    promo = spec.get("promo")

    # fallback CTA (only when the Remotion tail is missing). No discount code on screen: this file also goes to
    # TikTok, where codes are not allowed (owner 26/10/2026); the code stays in the YouTube/Meta descriptions.
    END_CTA_S = 0.0 if tail else spec.get("end_cta_seconds", 3.0)
    end_cta = spec.get("end_cta", ["LOOK UP", "Stargazing guide: link in bio"])
    cta_big, cta_small = font("display", 92, 700), font("text", 38, 600)

    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{SW}x{SH}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-pix_fmt", "yuv420p", str(build / "video_noaudio.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = round(total * FPS)
    readers: dict[int, render.VideoReader] = {}
    last_vis = None
    for i in range(n):
        t = i / FPS
        ins_k = next((k for k, ins in enumerate(inserts) if ins["t0"] <= t < ins["t1"]), None)
        if ins_k is not None:
            if ins_k not in readers:
                readers[ins_k] = render.VideoReader(Path(inserts[ins_k]["file"]), SW, SH, 0.0, grade=False)
            f = readers[ins_k].next()
            show_caps = inserts[ins_k]["captions"]
            credit = label = None
            if t < dur - 0.01:
                advance(vis, per, t)       # keep the clips in sync with the voice under the scene
        else:
            for kk in [k for k in readers if inserts[k]["t1"] <= t]:
                readers.pop(kk).close()
            k = min(len(vis) - 1, int(min(t, dur - 0.001) // per))
            canvas, credit, label, mot, zr = vis[k]
            if t >= dur and last_vis is not None:
                frame_vis = last_vis
            elif mot == "video":
                frame_vis = canvas.next()
            else:
                p = render.ease((t - k * per) / per)
                z = 1.0 + zr * p if mot != "zoom_out" else 1.0 + zr - zr * p
                cw, ch = canvas.size
                bw, bh = cw / z, ch / z
                frame_vis = canvas.resize((VIS_W, VIS_H), Image.BILINEAR, box=((cw - bw) / 2, (ch - bh) / 2, (cw + bw) / 2, (ch + bh) / 2))
            if t < dur:
                rel = t - k * per
                frame_vis = punch(frame_vis, int(rel // SUBSHOT_S), rel % SUBSHOT_S)
            last_vis = frame_vis
            fi = i
            cut = next((c for c in trans if c - 5 <= fi < c + 5), None)
            if cut is not None and trans[cut] == "zoomthrough":
                frame_vis = (motion.zoom_out_of(frame_vis, (fi - cut + 6) / 6) if fi < cut
                             else motion.zoom_into(frame_vis, (fi - cut + 1) / 5))
            f = backdrop(frame_vis)
            f.paste(frame_vis, (0, VIS_Y))
            if cut is not None and trans[cut] == "glitch" and cut - 4 <= fi < cut + 4:
                f = motion.glitch(f, fi - cut + 4, 8, seed=cut)
            show_caps = True
        d = ImageDraw.Draw(f)
        if ins_k is None and credit:
            d.text((24, VIS_Y + VIS_H + 12), (f"Video: {credit}" if vis[min(len(vis) - 1, int(min(t, dur - 0.001) // per))][3] == "video" else f"Image: {credit}")[:80],
                   font=font("text", 22, 500), fill=BRAND["dust"])
        if ins_k is None and label:
            d.rounded_rectangle((24, VIS_Y + 20, 300, VIS_Y + 64), radius=6, fill=BRAND["amber"])
            d.text((38, VIS_Y + 28), label, font=font("display", 24, 700), fill=BRAND["space"])
        if t < dur:   # headline drops in, stays on top of the footage and of the scenes
            a = render.ease(t / 0.35)
            render.paste(f, head, (0, 150 - int((1 - a) * 40)), a)
            d = ImageDraw.Draw(f)
        if promo:
            pf = font("display", 34, 700)
            pb = d.textbbox((0, 0), promo, font=pf)
            pw, ph = pb[2] - pb[0] + 56, pb[3] - pb[1] + 30
            px, py = (SW - pw) // 2, 1505
            d.rounded_rectangle((px, py, px + pw, py + ph), radius=ph // 2, fill=BRAND["amber"])
            d.text((px + 28 - pb[0], py + 15 - pb[1]), promo, font=pf, fill=BRAND["space"])
        if END_CTA_S and t >= dur - END_CTA_S:
            a = min(1.0, (t - (dur - END_CTA_S)) / 0.4)
            band = Image.new("RGBA", (SW, 230), (11, 16, 38, int(225 * a)))
            bd = ImageDraw.Draw(band)
            k1, k2 = end_cta
            b1 = bd.textbbox((0, 0), k1, font=cta_big); b2 = bd.textbbox((0, 0), k2, font=cta_small)
            bd.text(((SW - b1[2]) // 2, 34), k1, font=cta_big, fill=(246, 173, 85, int(255 * a)))
            bd.text(((SW - b2[2]) // 2, 150), k2, font=cta_small, fill=(237, 239, 247, int(255 * a)))
            f.paste(band, (0, VIS_Y + VIS_H - 230), band)
            d = ImageDraw.Draw(f)
        if show_caps and t < dur:
            draw_caption(d, caps, t, cap_f, CAP_Y)
        d.rectangle((0, SH - 8, int(SW * (i + 1) / n), SH), fill=BRAND["cyan"])   # progress bar: retention cue
        proc.stdin.write(f.tobytes())
    proc.stdin.close(); proc.wait()
    for r in readers.values():
        r.close()
    for v_ in vis:
        if v_[3] == "video":
            v_[0].close()

    render.render_audio({"music": spec.get("music", {"seed": 5, "mood": "wonder"})}, sd, timings, [],
                        total=total, events=events or [(total + 1, "tick")])
    dest = out / f"{spec['id']}.mp4"
    run([ffmpeg_exe(), "-hide_banner", "-y", "-i", build / "video_noaudio.mp4", "-i", build / "mix.wav",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", dest])
    social = social_variant(sd, spec, timings, total, events)
    if social:
        print("-> social variant", social)
    write_upload(sd, spec, src_dir, assets, dur)
    save_json(build / "short_meta.json", {"duration": dur, "captions": len(caps)})
    print("->", dest)


if __name__ == "__main__":
    main()
