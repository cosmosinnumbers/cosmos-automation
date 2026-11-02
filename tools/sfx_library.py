"""Build the sound-effects library from Openverse (CC0 only): python tools/sfx_library.py [--per-kind 4] [--dry-run]

For every kind used by video/ytf/sfx.py (whoosh, impact, glitch, key...) searches api.openverse.org (anonymous,
no key: basic searches are open) for short sound effects with license=cc0, downloads them, converts them with
ffmpeg to 48 kHz mono WAV, trims the leading silence, cuts them to the kind's max length and normalises the peak.
Files: assets/sfx/openverse/<kind>_<n>.wav; register: assets/sfx/library.json (title, creator, page, original
URL, licence, kind) so every sound in a video can be traced back to its source and licence.
Never takes CC-BY, BY-SA, NC or ND sounds: the YouTube videos only use material that needs no permission.
Kinds that find nothing keep the synthesised sound of sfx.py. Run by .github/workflows/sfx-library.yml.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import requests
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video" / "ytf"))
import sfx  # noqa: E402
from common import ffmpeg_exe  # noqa: E402

API = "https://api.openverse.org/v1/audio/"
OUT = ROOT / "assets" / "sfx"
QUERIES = {
    "whoosh": ["whoosh", "swoosh transition"], "swish": ["swish", "air swipe"], "impact": ["cinematic impact", "boom hit"],
    "riser": ["riser", "rising sweep"], "glitch": ["glitch", "digital glitch"], "key": ["typewriter key", "keyboard click"],
    "pop": ["pop", "bubble pop"], "slap": ["paper slap", "paper drop"], "shatter": ["glass shatter", "glass break"],
    "ding": ["ding", "bell chime"], "shimmer": ["shimmer", "sparkle"], "tick": ["tick", "click short"],
}
HEAD = {"User-Agent": "cosmos-automation/1.0 (sound library; github.com/cosmosinnumbers)"}


def search(q: str, n: int = 20) -> list[dict]:
    params = {"q": q, "license": "cc0", "category": "sound_effect", "page_size": n, "mature": "false"}
    for k in range(3):
        r = requests.get(API, params=params, headers=HEAD, timeout=30)
        if r.status_code == 429:
            time.sleep(10 * (k + 1))
            continue
        r.raise_for_status()
        return r.json().get("results", [])
    return []


def convert(raw: bytes, kind: str) -> np.ndarray | None:
    r = subprocess.run([ffmpeg_exe(), "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", str(sfx.SR),
                        "-f", "f32le", "pipe:1"], input=raw, capture_output=True, timeout=120)
    if r.returncode or not r.stdout:
        return None
    x = np.frombuffer(r.stdout, dtype=np.float32).copy()
    if len(x) < sfx.SR * 0.03:
        return None
    peak = np.abs(x).max()
    if peak < 1e-3:
        return None
    on = int(np.argmax(np.abs(x) > peak * 0.05))
    x = x[max(0, on - int(0.005 * sfx.SR)):][: int(sfx.MAX_LEN[kind] * sfx.SR)]
    fade = min(len(x), int(0.01 * sfx.SR))
    x[-fade:] *= np.linspace(1, 0, fade)
    return x / (np.abs(x).max() + 1e-9) * 0.89


def main():
    per = int(sys.argv[sys.argv.index("--per-kind") + 1]) if "--per-kind" in sys.argv else 4
    dry = "--dry-run" in sys.argv
    reg_path = OUT / "library.json"
    reg = json.loads(reg_path.read_text("utf-8")) if reg_path.exists() else []
    have = {it["id"] for it in reg}
    (OUT / "openverse").mkdir(parents=True, exist_ok=True)
    for kind, qs in QUERIES.items():
        got = sum(1 for it in reg if it["kind"] == kind)
        for q in qs:
            if got >= per:
                break
            try:
                res = search(q)
            except Exception as e:  # noqa: BLE001
                print(f"{kind}: search '{q}' failed: {e}")
                continue
            for it in res:
                if got >= per:
                    break
                if it["id"] in have or (it.get("license") or "").lower() != "cc0":
                    continue
                dur = (it.get("duration") or 0) / 1000
                if dur and dur > 12:   # long recordings are ambiences, not hits
                    continue
                print(f"{kind}: {it['title'][:60]} ({it.get('creator')}, {it['license']}) {it.get('foreign_landing_url')}")
                if dry:
                    got += 1
                    continue
                try:
                    raw = requests.get(it["url"], headers=HEAD, timeout=60).content
                    x = convert(raw, kind)
                except Exception as e:  # noqa: BLE001
                    print("   download failed:", e)
                    continue
                if x is None:
                    print("   unusable audio")
                    continue
                name = f"openverse/{kind}_{re.sub(r'[^a-z0-9]', '', it['id'].lower())[:12]}.wav"
                sf.write(str(OUT / name), x, sfx.SR, subtype="PCM_16")
                reg.append({"id": it["id"], "kind": kind, "file": name, "title": it["title"],
                            "creator": it.get("creator"), "license": "cc0",
                            "license_url": it.get("license_url"), "page": it.get("foreign_landing_url"),
                            "source": it.get("source") or it.get("provider"), "url": it["url"], "query": q})
                have.add(it["id"])
                got += 1
        print(f"== {kind}: {got} sounds")
    if not dry:
        reg_path.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"library: {len(reg)} sounds")


if __name__ == "__main__":
    main()
