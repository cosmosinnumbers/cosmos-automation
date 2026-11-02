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
import os
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
BUDGET_S = 600          # the whole run never lasts more than 10 minutes
T0 = time.time()


class Throttled(Exception):
    """Openverse answered 429: anonymous searches are capped hard (a handful an hour); stop instead of waiting."""


def token() -> str | None:
    """OAuth2 client-credentials token when the repo has OPENVERSE_CLIENT_ID / OPENVERSE_CLIENT_SECRET (free
    registration at api.openverse.org/v1/auth_tokens/register/): the limits are then far higher."""
    cid, sec = os.environ.get("OPENVERSE_CLIENT_ID"), os.environ.get("OPENVERSE_CLIENT_SECRET")
    if not (cid and sec):
        return None
    r = requests.post("https://api.openverse.org/v1/auth_tokens/token/", headers=HEAD, timeout=30,
                      data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec})
    r.raise_for_status()
    return r.json()["access_token"]


def search(q: str, n: int = 20) -> list[dict]:
    params = {"q": q, "license": "cc0", "category": "sound_effect", "page_size": n, "mature": "false"}
    r = requests.get(API, params=params, headers=HEAD, timeout=20)
    if r.status_code == 429:
        raise Throttled(r.headers.get("Retry-After", "?"))
    r.raise_for_status()
    return r.json().get("results", [])


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
    tok = token()
    if tok:
        HEAD["Authorization"] = f"Bearer {tok}"
        print("Openverse: authenticated (OPENVERSE_CLIENT_ID/SECRET)", flush=True)
    else:
        print("Openverse: anonymous (very low rate limit: add OPENVERSE_CLIENT_ID / OPENVERSE_CLIENT_SECRET)", flush=True)
    throttled = False
    # kinds with the fewest sounds first, so repeated runs fill the gaps even when throttled
    order = sorted(QUERIES, key=lambda k: sum(1 for it in reg if it["kind"] == k))
    for kind in order:
        qs = QUERIES[kind]
        if throttled or time.time() - T0 > BUDGET_S:
            break
        got = sum(1 for it in reg if it["kind"] == kind)
        for q in qs:
            if got >= per:
                break
            try:
                res = search(q)
            except Throttled as e:
                print(f"{kind}: Openverse 429 (retry-after {e}): stopping, run again later or add the API key", flush=True)
                throttled = True
                break
            except Exception as e:  # noqa: BLE001
                print(f"{kind}: search '{q}' failed: {e}", flush=True)
                continue
            print(f"{kind}: '{q}' -> {len(res)} CC0 results", flush=True)
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
        print(f"== {kind}: {got} sounds", flush=True)
    if not dry:
        reg_path.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"library: {len(reg)} sounds")


if __name__ == "__main__":
    main()
