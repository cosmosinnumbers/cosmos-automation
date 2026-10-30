"""Build one video end to end (never uploads, never publishes).

  python make.py <video_dir> [--steps voice,render,audio,mux,captions,thumbs,meta,qc]

<video_dir> holds script.yaml, assets.yaml, assets/, charts/ and (optional) thumbs.yaml.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import captions  # noqa: E402
import meta  # noqa: E402
import qc  # noqa: E402
import render  # noqa: E402
import thumb  # noqa: E402
import voice  # noqa: E402
from common import load_json, load_yaml, save_json  # noqa: E402

ALL = ["voice", "render", "audio", "mux", "captions", "thumbs", "meta", "qc"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--steps", default=",".join(ALL))
    a = ap.parse_args()
    video = Path(a.video).resolve()
    build = video / "build"
    build.mkdir(exist_ok=True)
    script = load_yaml(video / "script.yaml")
    assets = load_yaml(video / "assets.yaml") or {}
    steps = a.steps.split(",")
    t0 = time.time()

    if "voice" in steps:
        print("[voice]")
        voice.synth(script, build)
    timings = load_json(build / "timings.json")
    print(f"narration: {timings['duration'] / 60:.2f} min")

    shots = load_json(build / "shots.json") if (build / "shots.json").exists() else None
    if "render" in steps:
        print("[render]")
        shots = render.render_video(script, video, assets, timings)
    if "audio" in steps:
        print("[audio]")
        shots = shots or render.build_shots(script, timings)
        loud = render.render_audio(script, video, timings, shots)
        save_json(build / "loudness.json", loud)
    if "mux" in steps:
        print("[mux]")
        print(" ->", render.mux(video, script["id"]))
    if "captions" in steps:
        n = captions.write_srt(timings, video / "out" / f"{script['id']}.srt")
        print(f"[captions] {n} blocks")
    if "thumbs" in steps and (video / "thumbs.yaml").exists():
        spec = load_yaml(video / "thumbs.yaml")
        for name, t in spec.items():
            thumb.make(video / assets[t["bg"]]["file"], t["lines"], video / "out" / f"thumb_{name}.jpg",
                       accent=t.get("accent", "amber"), badge=t.get("badge", "REAL DATA"),
                       focus=tuple(t.get("focus", (0.5, 0.5))), side=t.get("side", "left"),
                       highlight=t.get("highlight", 0),
                       label="ARTIST'S CONCEPT" if assets[t["bg"]].get("kind") == "illustration" else None)
        print(f"[thumbs] {len(spec)}")
    if "meta" in steps:
        srt = video / "out" / f"{script['id']}.srt"
        nblocks = srt.read_text("utf-8").count(" --> ") if srt.exists() else 0
        print("[meta] ->", meta.write_package(script, timings, assets, video, nblocks))
    if "qc" in steps:
        loud = load_json(build / "loudness.json") if (build / "loudness.json").exists() else None
        desc = (video / "out" / "description.txt").read_text("utf-8") if (video / "out" / "description.txt").exists() else ""
        ok, _ = qc.check(script, timings, assets, video, loud, desc)
        print(f"[qc] {'PASS' if ok else 'FAIL'} -> {video / 'out' / 'qc.md'}")
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
