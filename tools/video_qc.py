"""Automatic quality control of a rendered video before it is released (viral prompt, phase D).

  python tools/video_qc.py out.mp4 [--kind short|long] [--script result.json] [--log logs/video-qc-log.jsonl] [--md report.md]

Only ffmpeg/ffprobe (no extra libraries). Two levels:
- ERROR (exit 1, the release is not made): no audio or no picture, wrong format, duration far off, loudness far from
  -14 LUFS or clipping, a black frame run, a static picture for too long, nothing moving in the first 1.5 s.
- WARN (reported in the release notes, score drops): small loudness drift, long silence, few cuts, an ending that
  does not echo the opening, the same cut pattern as the previous video.
Score 0-100 and the reasons go to the log (one JSON line per video) and, with --md, to a markdown block.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMITS = {  # per kind: (min s, max s) hard, (min s, max s) target, longest static shot, wanted max gap between cuts
    "short": {"hard": (12, 65), "target": (25, 45), "static": 4.0, "gap": 6.0},
    "long": {"hard": (120, 1500), "target": (360, 720), "static": 9.0, "gap": 12.0},
}
STOP = set("the a an of to in on is are was were it its and or for with as at by from that this be has have had not no".split())


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # the Actions runners get ffmpeg from this package (no ffprobe there)
    return imageio_ffmpeg.get_ffmpeg_exe()


FFMPEG = _ffmpeg()


def run(cmd: list[str]) -> str:
    cmd = [FFMPEG if c == "ffmpeg" else c for c in cmd]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stderr or "") + (p.stdout or "")


def probe(path: str) -> dict:
    """Same shape as ffprobe -of json, read from the text of `ffmpeg -i` (ffprobe is not always installed)."""
    txt = run(["ffmpeg", "-hide_banner", "-i", path])
    streams, fmt = [], {}
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    if d:
        fmt["duration"] = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    for ln in txt.splitlines():
        m = re.search(r"Stream #\S+: Video: .*?, (\d{2,5})x(\d{2,5})", ln)
        if m:
            streams.append({"codec_type": "video", "width": int(m.group(1)), "height": int(m.group(2))})
        elif re.search(r"Stream #\S+: Audio:", ln):
            streams.append({"codec_type": "audio"})
    return {"streams": streams, "format": fmt}


def loudness(path: str) -> tuple[float | None, float | None]:
    txt = run(["ffmpeg", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", txt)
    return (float(i[-1]) if i else None, float(p[-1]) if p else None)


def silences(path: str, dur: float) -> list[tuple[float, float]]:
    txt = run(["ffmpeg", "-nostats", "-i", path, "-vn", "-af", "silencedetect=noise=-40dB:d=0.6", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", txt)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", txt)]
    out = []
    for k, s in enumerate(starts):
        e = ends[k] if k < len(ends) else dur
        out.append((max(s, 0.0), e))
    return out


def freezes(path: str, min_s: float) -> list[tuple[float, float]]:
    txt = run(["ffmpeg", "-nostats", "-i", path, "-an", "-vf", f"freezedetect=n=0.003:d={min_s}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"freeze_start: (-?[\d.]+)", txt)]
    durs = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", txt)]
    return [(s, durs[k] if k < len(durs) else 999.0) for k, s in enumerate(starts)]


def blacks(path: str) -> list[tuple[float, float]]:
    txt = run(["ffmpeg", "-nostats", "-i", path, "-an", "-vf", "blackdetect=d=0.4:pix_th=0.06", "-f", "null", "-"])
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", txt)]


def cuts(path: str, thr: float = 0.25) -> list[float]:
    txt = run(["ffmpeg", "-nostats", "-i", path, "-an", "-vf", f"select='gt(scene,{thr})',showinfo", "-f", "null", "-"])
    return [round(float(t), 1) for t in re.findall(r"pts_time:([\d.]+)", txt)]


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def analyse(path: str, kind: str = "short", script: dict | None = None, prev_cuts: list[float] | None = None) -> dict:
    lim = LIMITS[kind]
    err, warn = [], []
    info = probe(path)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration") or 0)
    if not v:
        err.append("no video stream")
    if not a:
        err.append("no audio stream")
    if v and kind == "short" and (int(v["width"]), int(v["height"])) != (1080, 1920):
        err.append(f"size {v['width']}x{v['height']}, Shorts must be 1080x1920")
    if not lim["hard"][0] <= dur <= lim["hard"][1]:
        err.append(f"duration {dur:.1f}s outside {lim['hard'][0]}-{lim['hard'][1]}s")
    elif not lim["target"][0] <= dur <= lim["target"][1]:
        warn.append(f"duration {dur:.1f}s outside target {lim['target'][0]}-{lim['target'][1]}s")
    m = {"duration": round(dur, 1)}
    if err and not (v and a):
        return {"errors": err, "warnings": warn, "score": 0, "metrics": m}

    lufs, peak = loudness(path)
    m.update(lufs=lufs, peak_dbfs=peak)
    if lufs is None or lufs < -40:
        err.append("audio is silent")
    else:
        if abs(lufs + 14) > 3:
            err.append(f"loudness {lufs:.1f} LUFS, target -14 (+-1)")
        elif abs(lufs + 14) > 1:
            warn.append(f"loudness {lufs:.1f} LUFS, target -14 (+-1)")
        if peak is not None and peak > -0.1:
            err.append(f"peak {peak:.1f} dBFS: clipping")
        elif peak is not None and peak > -0.5:
            warn.append(f"peak {peak:.1f} dBFS above -0.5")
    sil = [(s, e) for s, e in silences(path, dur) if e - s >= 0.6 and e < dur - 1.0 and s > 0.2]
    if sil:
        warn.append(f"{len(sil)} silence(s) over 0.6 s (first at {sil[0][0]:.1f}s)")
    m["silences"] = len(sil)

    fz = freezes(path, lim["static"])
    m["static_runs"] = len(fz)
    if fz:
        err.append(f"static picture for {max(d for _, d in fz):.1f}s (max {lim['static']:.0f}s) at {fz[0][0]:.1f}s")
    if any(s < 0.1 for s, _ in freezes(path, 1.5)):
        err.append("nothing moves in the first 1.5 s")
    bl = blacks(path)
    m["black_runs"] = len(bl)
    if bl:
        err.append(f"black frames at {bl[0][0]:.1f}-{bl[0][1]:.1f}s")

    cs = cuts(path)
    m["cuts"] = len(cs)
    m["cut_times"] = cs[:60]
    pts = [0.0] + cs + [dur]
    gap = max(b - a_ for a_, b in zip(pts, pts[1:])) if len(pts) > 1 else dur
    m["max_cut_gap"] = round(gap, 1)
    if gap > lim["gap"]:
        warn.append(f"{gap:.1f}s without a cut or a scene change (target {lim['gap']:.0f}s)")
    if prev_cuts and len(cs) >= 4 and cs[:8] == prev_cuts[:8]:
        warn.append("same cut pattern as the previous video (template feel)")

    if script and script.get("narration"):
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", script["narration"].strip()) if x.strip()]
        if len(sents) > 2:
            first, last = words(sents[0]), words(sents[-1])
            if first and not (first & last):
                warn.append("last sentence does not echo the opening (no seamless loop)")
            if len(sents[0].split()) > 16:
                warn.append(f"hook has {len(sents[0].split())} words")

    score = max(0, 100 - 100 * len(err) - 8 * len(warn)) if err else max(0, 100 - 8 * len(warn))
    return {"errors": err, "warnings": warn, "score": score, "metrics": m}


def report_md(name: str, res: dict) -> str:
    lines = [f"## QC video ({name}): {res['score']}/100 " + ("BLOCCATO" if res["errors"] else "ok")]
    lines += [f"- ERRORE: {e}" for e in res["errors"]] + [f"- Avviso: {w}" for w in res["warnings"]]
    m = res["metrics"]
    lines.append(f"- Misure: durata {m.get('duration')} s, {m.get('lufs')} LUFS, picco {m.get('peak_dbfs')} dBFS, "
                 f"{m.get('cuts', '?')} stacchi, pausa max tra stacchi {m.get('max_cut_gap', '?')} s")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--kind", choices=list(LIMITS), default="short")
    ap.add_argument("--script")
    ap.add_argument("--log", default=str(ROOT / "logs" / "video-qc-log.jsonl"))
    ap.add_argument("--md")
    a = ap.parse_args()
    script = json.loads(Path(a.script).read_text("utf-8")) if a.script and Path(a.script).exists() else None
    prev = None
    lp = Path(a.log)
    if lp.exists():
        for ln in lp.read_text("utf-8").splitlines()[::-1]:
            try:
                j = json.loads(ln)
            except ValueError:
                continue
            if j.get("kind") == a.kind:
                prev = j.get("metrics", {}).get("cut_times")
                break
    res = analyse(a.video, a.kind, script, prev)
    md = report_md(Path(a.video).name, res)
    print(md)
    if a.md:
        Path(a.md).write_text(md, "utf-8")
    lp.parent.mkdir(parents=True, exist_ok=True)
    with open(lp, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "video": Path(a.video).name, "kind": a.kind,
                            **res}, ensure_ascii=False) + "\n")
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
