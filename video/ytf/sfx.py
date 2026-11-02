"""Sound design for the motion graphics: the right sound, at the exact frame, at the right level.

Three layers, in this order (owner's request 02/11/2026):
  1. Library: CC0 sound effects found on Openverse (api.openverse.org) by tools/sfx_library.py, trimmed and
     normalised into assets/sfx/openverse/<kind>_<n>.wav, with title, author, page and licence of every file in
     assets/sfx/library.json. Only CC0: no credit to track, no "all rights reserved" sound ever enters a video.
  2. Placement: every visual event of the timeline (scene start, glitch, crash zoom, keystroke, poster burst,
     counter landing...) becomes (time, kind); PEAK aligns the loudest point of each sound on that frame and
     LEVEL sets its mix level, under the voice (render.render_audio ducks the music, not the effects).
  3. Synthesis: when the library has nothing for a kind, the sound is generated here with numpy (our own sound,
     nothing for Content ID to match), so a video never waits on the network.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
LIB = Path(__file__).resolve().parents[2] / "assets" / "sfx"

# mix level (linear gain on a peak-normalised sound) and how early to start it so its peak lands on the event
LEVEL = {"whoosh": 0.42, "swish": 0.22, "impact": 0.55, "riser": 0.30, "glitch": 0.34, "key": 0.20, "pop": 0.30,
         "slap": 0.50, "shatter": 0.40, "ding": 0.26, "shimmer": 0.20, "tick": 0.14, "ping": 0.18}
PEAK = {"whoosh": 0.45, "swish": 0.30, "riser": 1.2, "impact": 0.0, "glitch": 0.0, "key": 0.0, "pop": 0.0,
        "slap": 0.0, "shatter": 0.0, "ding": 0.0, "shimmer": 0.1, "tick": 0.0, "ping": 0.0}
MAX_LEN = {"whoosh": 1.2, "swish": 0.8, "impact": 2.0, "riser": 1.6, "glitch": 0.5, "key": 0.15, "pop": 0.4,
           "slap": 0.7, "shatter": 1.6, "ding": 1.5, "shimmer": 2.0, "tick": 0.1, "ping": 0.8}


def _bp(x, lo, hi):
    sos = butter(2, [max(20, lo), min(hi, SR / 2 - 100)], "band", fs=SR, output="sos")
    return sosfilt(sos, x)


def _lp(x, fc):
    return sosfilt(butter(2, min(fc, SR / 2 - 100), "low", fs=SR, output="sos"), x)


def _t(sec):
    return np.arange(int(sec * SR)) / SR


# ---------- synthesised kit (layer 3) ----------
def whoosh(rng, length=0.9):
    n = int(length * SR)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    blocks = 24
    for b in range(blocks):
        lo, hi = b * n // blocks, (b + 1) * n // blocks
        fc = 300 * (12 ** (b / blocks))
        out[lo:hi] = _bp(noise[lo:hi], fc * 0.7, fc * 1.4)
    return out * np.sin(np.linspace(0, np.pi, n)) ** 2


def impact(rng, length=1.6):
    t = _t(length)
    f = 38 + 70 * np.exp(-t * 18)                       # pitch drop: the "boom"
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    crack = _bp(rng.standard_normal(len(t)), 900, 6000) * np.exp(-t * 40) * 0.6
    return np.tanh((body + crack) * 1.8)


def riser(rng, length=1.4):
    t = _t(length)
    k = t / length
    noise = _bp(rng.standard_normal(len(t)), 400, 9000) * k ** 2.2
    tone = np.sin(2 * np.pi * np.cumsum(180 + 900 * k ** 2) / SR) * k ** 3 * 0.4
    return (noise + tone) * np.minimum(1, (length - t) / 0.03)


def glitch(rng, length=0.32):
    n = int(length * SR)
    out = np.zeros(n)
    i = 0
    while i < n:                                         # short random bursts: bit-crushed noise and square buzz
        seg = int(rng.uniform(0.008, 0.04) * SR)
        kind = rng.integers(3)
        tt = np.arange(seg) / SR
        if kind == 0:
            s = np.sign(np.sin(2 * np.pi * rng.uniform(80, 900) * tt))
        elif kind == 1:
            s = np.round(rng.standard_normal(seg) * 3) / 3
        else:
            s = np.zeros(seg)
        out[i:i + seg] = s[: n - i] * rng.uniform(0.4, 1)
        i += seg
    return _lp(out, 9000)


def key(rng, length=0.09):
    t = _t(length)
    click = _bp(rng.standard_normal(len(t)), 1800, 7000) * np.exp(-t * 160)
    thock = np.sin(2 * np.pi * rng.uniform(180, 260) * t) * np.exp(-t * 90) * 0.5
    return click + thock


def pop(rng, length=0.25):
    t = _t(length)
    f = 900 * np.exp(-t * 30) + 260
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22)


def slap(rng, length=0.5):
    t = _t(length)
    paper = _bp(rng.standard_normal(len(t)), 300, 5000) * np.exp(-t * 28)
    thud = np.sin(2 * np.pi * 85 * t) * np.exp(-t * 14) * 0.7
    return paper + thud


def shatter(rng, length=1.3):
    t = _t(length)
    out = _bp(rng.standard_normal(len(t)), 2500, 12000) * np.exp(-t * 5) * 0.5
    for _ in range(26):                                  # glassy shards
        at = int(rng.uniform(0, 0.7) * SR)
        f = rng.uniform(2500, 7000)
        tt = np.arange(len(t) - at) / SR
        out[at:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * rng.uniform(25, 60)) * rng.uniform(0.2, 0.6)
    return out + impact(rng, length) * 0.6


def ding(rng, length=1.2):
    t = _t(length)
    return (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t)
            + 0.25 * np.sin(2 * np.pi * 2637 * t)) * np.exp(-t * 4.5)


def shimmer(rng, length=1.8):
    t = _t(length)
    out = np.zeros(len(t))
    for k, f in enumerate((1046.5, 1318.5, 1568.0, 2093.0)):
        out += np.sin(2 * np.pi * f * t + k) * (0.5 + 0.5 * np.sin(2 * np.pi * (3 + k) * t))
    return out * np.sin(np.linspace(0, np.pi, len(t))) ** 2


def tick(rng, length=0.05):
    t = _t(length)
    return _bp(rng.standard_normal(len(t)), 3000, 9000) * np.exp(-t * 300)


def ping(rng, length=0.7):
    t = _t(length)
    return (np.sin(2 * np.pi * 880 * t) + 0.5 * np.sin(2 * np.pi * 1320 * t)) * np.exp(-t * 7)


SYNTH = {"whoosh": whoosh, "swish": lambda r: whoosh(r, 0.6), "impact": impact, "riser": riser, "glitch": glitch,
         "key": key, "pop": pop, "slap": slap, "shatter": shatter, "ding": ding, "shimmer": shimmer, "tick": tick,
         "ping": ping}


# ---------- library (layer 1) ----------
@lru_cache(maxsize=1)
def library() -> dict[str, list[Path]]:
    """{kind: [wav, ...]} from assets/sfx/library.json; only CC0 entries whose file exists."""
    reg = LIB / "library.json"
    if not reg.exists():
        return {}
    out: dict[str, list[Path]] = {}
    for it in json.loads(reg.read_text("utf-8")):
        p = LIB / it["file"]
        if it.get("license", "").lower() == "cc0" and p.exists():
            out.setdefault(it["kind"], []).append(p)
    return out


@lru_cache(maxsize=64)
def _load(path: str) -> np.ndarray:
    import soundfile as sf
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != SR:
        x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x)
    return x


def sound(kind: str, rng) -> np.ndarray:
    """A peak-normalised mono sound of this kind: a library file when there is one (picked at random, so two
    videos never sound the same), else synthesised."""
    files = library().get(kind)
    if files and rng.random() < 0.85:
        x = _load(str(files[int(rng.integers(len(files)))])).astype(np.float64)
    else:
        x = SYNTH.get(kind, SYNTH["pop"])(rng)
    x = x[: int(MAX_LEN.get(kind, 2.0) * SR)]
    fade = min(len(x), int(0.01 * SR))
    if fade:
        x[-fade:] *= np.linspace(1, 0, fade)
    return x / (np.abs(x).max() + 1e-9)


def track(duration: float, events: list[tuple[float, str]], seed: int = 3) -> np.ndarray:
    """Stereo effects track: each (time, kind) placed so its peak lands on `time`, at LEVEL[kind], with a small
    random stereo position (keys and ticks spread, impacts centred)."""
    rng = np.random.default_rng(seed)
    out = np.zeros((int(duration * SR) + 2 * SR, 2), dtype=np.float32)
    for at, kind in sorted(events):
        s = sound(kind, rng) * LEVEL.get(kind, 0.25) * rng.uniform(0.85, 1.0)
        pan = 0.0 if kind in ("impact", "riser", "slap") else rng.uniform(-0.35, 0.35)
        start = int(max(0.0, at - PEAK.get(kind, 0.0)) * SR)
        end = min(len(out), start + len(s))
        if end <= start:
            continue
        out[start:end, 0] += (s[: end - start] * (1 - pan) / 1.0).astype(np.float32)
        out[start:end, 1] += (s[: end - start] * (1 + pan) / 1.0).astype(np.float32)
    return np.tanh(out[: int(duration * SR)] * 1.1) / 1.1  # soft limit where hits overlap


def credits() -> list[str]:
    """One line per library sound actually present (CC0 needs no credit; listed for transparency and audits)."""
    reg = LIB / "library.json"
    if not reg.exists():
        return []
    return [f"{it['title']} by {it.get('creator') or 'unknown'} ({it['license'].upper()}) {it['page']}"
            for it in json.loads(reg.read_text("utf-8")) if (LIB / it["file"]).exists()]
