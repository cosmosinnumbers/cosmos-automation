"""Fetch again the NASA material of a Short that is already out (release tag), for a before/after render.

  python tools/demo_assets.py <release-tag> <out_dir>

Reads the release's material-assets.yaml, downloads every item from the NASA library again (same ids) into
<out_dir>/material/, keeps the first 45 s of each clip (720p) and copies short.yaml to <out_dir>/short/.
"""
from __future__ import annotations

import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import stock  # noqa: E402
from common import ffmpeg_exe, load_yaml, save_yaml  # noqa: E402

REPO = "cosmosinnumbers/cosmos-automation"


def main():
    tag, out = sys.argv[1], Path(sys.argv[2])
    mat, short = out / "material", out / "short"
    mat.mkdir(parents=True, exist_ok=True); short.mkdir(parents=True, exist_ok=True)
    base = f"https://github.com/{REPO}/releases/download/{tag}/"
    stock.download(base + "material-assets.yaml", mat / "assets.yaml")
    stock.download(base + "material-script.yaml", mat / "script.yaml")
    stock.download(base + "short.yaml", short / "short.yaml")
    assets = load_yaml(mat / "assets.yaml")
    for key, a in assets.items():
        nid = urllib.parse.unquote(a["source"].rsplit("/details/", 1)[1])
        kind = "video" if a["type"] == "video" else "image"
        files = stock.get_json(f"https://images-assets.nasa.gov/{kind}/{urllib.parse.quote(nid)}/collection.json", {})
        if kind == "video":
            mp4 = [f for f in files if f.endswith(".mp4")]
            pick = next((f for t in ("~medium", "~large", "~mobile", "~small") for f in mp4 if t in f), mp4[0])
            raw = mat / "raw.mp4"
            stock.download(pick.replace("http://", "https://"), raw)
            a["file"] = f"assets/stock/{key}.mp4"
            (mat / a["file"]).parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([ffmpeg_exe(), "-loglevel", "error", "-y", "-i", str(raw), "-t", "45", "-an",
                            "-vf", "scale=-2:720", "-c:v", "libx264", "-crf", "21", str(mat / a["file"])], check=True)
            raw.unlink()
        else:
            jpg = next((f for t in ("~large.jpg", "~medium.jpg", "~orig.jpg") for f in files if f.endswith(t)), None)
            a["file"] = f"assets/stock/{key}.jpg"
            stock.download(jpg.replace("http://", "https://"), mat / a["file"])
        print(key, a["file"], (mat / a["file"]).stat().st_size)
    save_yaml(mat / "assets.yaml", assets)


if __name__ == "__main__":
    main()
