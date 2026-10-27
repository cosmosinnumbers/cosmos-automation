"""Original ambient score and sound effects, synthesised from scratch with numpy.

No samples, no third-party loops: the channel owns every sound it publishes,
so there is nothing for Content ID to match and no licence to track.
"""
from __future__ import annotations

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 48000

# Chord sets (MIDI notes). Slow, open voicings that sit under a voice.
MOODS = {
    "calm": [[45, 52, 57, 59, 64], [41, 48, 53, 57, 64], [48, 55, 60, 62, 67], [43, 50, 55, 59, 62]],
    "wonder": [[50, 57, 62, 64, 69], [46, 53, 58, 62, 65], [43, 50, 55, 57, 62], [45, 52, 57, 61, 64]],
    "tense": [[45, 52, 55, 60, 63], [44, 51, 56, 59, 63], [41, 48, 53, 56, 60], [43, 50, 55, 58, 62]],
}


def midi_hz(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def _env(n, attack, release):
    e = np.ones(n, dtype=np.float32)
    a, r = int(attack * SR), int(release * SR)
    e[:a] = np.linspace(0, 1, a, dtype=np.float32) ** 2
    e[-r:] *= np.linspace(1, 0, r, dtype=np.float32) ** 2
    return e


def _comb(x, d, g):
    """y[n] = x[n] + g*y[n-d], computed one delay-length block at a time."""
    y = np.empty_like(x)
    y[:d] = x[:d]
    for i in range(d, len(x), d):
        j = min(i + d, len(x))
        y[i:j] = x[i:j] + g * y[i - d:j - d]
    return y


def _allpass(x, d, g):
    """y[n] = -g*x[n] + x[n-d] + g*y[n-d], block-wise like _comb."""
    y = np.empty_like(x)
    y[:d] = -g * x[:d]
    for i in range(d, len(x), d):
        j = min(i + d, len(x))
        y[i:j] = -g * x[i:j] + x[i - d:j - d] + g * y[i - d:j - d]
    return y


def _schroeder(x, rng):
    """Small stereo reverb: 4 combs + 2 allpasses per channel."""
    out = []
    for ch in range(2):
        acc = np.zeros_like(x)
        for d in (1557, 1617, 1491, 1422):
            acc += _comb(x, int(d * (1.0 + 0.03 * ch) * SR / 44100), 0.84)
        y = acc / 4
        for d in (225, 556):
            y = _allpass(y, int(d * SR / 44100), 0.5)
        out.append(y.astype(np.float32))
    return np.stack(out, axis=1)


def ambient_loop(seed: int = 7, mood: str = "calm", chord_sec: float = 16.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    chords = MOODS[mood]
    order = list(range(len(chords))) * 2
    n_chord = int(chord_sec * SR)
    total = n_chord * len(order)
    t = np.arange(n_chord + int(4 * SR)) / SR  # each chord rings 4 s into the next
    dry = np.zeros(total + int(4 * SR), dtype=np.float32)
    lp = butter(2, 1400, "low", fs=SR, output="sos")
    for i, ci in enumerate(order):
        start = i * n_chord
        pad = np.zeros(len(t), dtype=np.float32)
        for note in chords[ci]:
            f = midi_hz(note)
            for det in (-0.35, 0.0, 0.42):  # three detuned partials = slow chorus
                ph = rng.uniform(0, 2 * np.pi)
                pad += (np.sin(2 * np.pi * (f + det) * t + ph) + 0.18 * np.sin(2 * np.pi * 2 * (f + det) * t)).astype(np.float32)
        pad *= _env(len(t), 5.0, 7.0) / 15
        dry[start:start + len(t)] += sosfilt(lp, pad).astype(np.float32)
        # sub drone on the root
        root = midi_hz(chords[ci][0] - 12)
        dry[start:start + len(t)] += (0.22 * np.sin(2 * np.pi * root * t) * _env(len(t), 4.0, 6.0)).astype(np.float32)
        # a few soft "star" chimes
        for _ in range(rng.integers(2, 5)):
            at = start + int(rng.uniform(0, chord_sec - 4) * SR)
            note = rng.choice(chords[ci]) + 24
            n = int(3.5 * SR)
            tt = np.arange(n) / SR
            chime = np.sin(2 * np.pi * midi_hz(note) * tt) * np.exp(-tt * 1.6) * 0.05
            dry[at:at + n] += chime.astype(np.float32)
    # soft filtered noise = "space air"
    noise = rng.standard_normal(len(dry)).astype(np.float32)
    noise = sosfilt(butter(2, 380, "low", fs=SR, output="sos"), noise).astype(np.float32) * 0.05
    dry += noise
    wet = _schroeder(dry, rng)
    st = np.stack([dry, dry], axis=1) * 0.55 + wet * 0.6
    # wrap the ringing tail onto the start so the loop is seamless
    tail = st[total:]
    st = st[:total].copy()
    st[:len(tail)] += tail
    st /= np.max(np.abs(st)) + 1e-9
    return (st * 0.7).astype(np.float32)


def ambient_track(duration: float, seed: int = 7, mood: str = "calm") -> np.ndarray:
    loop = ambient_loop(seed, mood)
    n = int(duration * SR)
    reps = int(np.ceil(n / len(loop))) + 1
    track = np.tile(loop, (reps, 1))[:n]
    fade = int(3 * SR)
    track[:fade] *= np.linspace(0, 1, fade)[:, None]
    track[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return track


def whoosh(rng, length=0.9):
    n = int(length * SR)
    noise = rng.standard_normal(n).astype(np.float32)
    out = np.zeros(n, dtype=np.float32)
    # sweep a band-pass upward in short blocks
    blocks = 24
    for b in range(blocks):
        lo, hi = b * n // blocks, (b + 1) * n // blocks
        fc = 300 * (12 ** (b / blocks))
        sos = butter(2, [fc * 0.7, min(fc * 1.4, SR / 2 - 100)], "band", fs=SR, output="sos")
        out[lo:hi] = sosfilt(sos, noise[lo:hi])
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (out * env * 0.5).astype(np.float32)


def ping(length=0.7):
    n = int(length * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * 880 * t) + 0.5 * np.sin(2 * np.pi * 1320 * t)) * np.exp(-t * 7)
    return (s * 0.18).astype(np.float32)


def sfx_track(duration: float, events: list[tuple[float, str]], seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    track = np.zeros((int(duration * SR) + SR, 2), dtype=np.float32)
    for at, kind in events:
        snd = whoosh(rng) if kind == "whoosh" else ping()
        # whoosh peaks at its middle: start it early so the peak lands on the cut
        start = int(max(0.0, at - (0.45 if kind == "whoosh" else 0.0)) * SR)
        end = min(len(track), start + len(snd))
        track[start:end] += snd[: end - start, None]
    return track[: int(duration * SR)]


def write(path, data):
    sf.write(str(path), data, SR, subtype="PCM_16")
