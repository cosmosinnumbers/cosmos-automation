"""Narration with Kokoro-82M (Apache 2.0, local CPU).

Writes <video>/build/narration.wav and timings.json:
  {"segments": [{"id", "start", "end", "sentences": [{"text", "start", "end"}]}], "duration"}
Pauses are explicit so later steps (shots, captions, chapters) can rely on them.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import soundfile as sf

from common import env_espeak, save_json

SR = 24000
PAUSE_SENTENCE = 0.28
PAUSE_PARAGRAPH = 0.55
PAUSE_SEGMENT = 0.85

_MODEL = {}


def _kokoro():
    if "k" not in _MODEL:
        env_espeak()
        from kokoro_onnx import Kokoro
        cache = Path.home() / ".cache" / "kokoro"
        _MODEL["k"] = Kokoro(str(cache / "kokoro-v1.0.onnx"), str(cache / "voices-v1.0.bin"))
    return _MODEL["k"]


def spoken(text: str) -> str:
    """Text as it should be pronounced (the caption keeps the written form)."""
    t = text
    t = re.sub(r"(\d),(\d{3})", r"\1\2", t)          # 6,445 -> 6445 (Kokoro reads digits well)
    t = t.replace("°C", " degrees Celsius").replace("°F", " degrees Fahrenheit")
    t = t.replace("km/s", " kilometers per second").replace(" km ", " kilometers ")
    t = re.sub(r"(\d) km\b", r"\1 kilometers", t)
    t = re.sub(r"(\d) AU\b", r"\1 astronomical units", t)
    t = t.replace("JWST", "J W S T").replace("~", "about ")
    t = t.replace("—", ", ").replace("–", " to ")
    return t


def split_sentences(par: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“])", par.strip())
    return [p.strip() for p in parts if p.strip()]


def synth(script: dict, build: Path, voice: str | None = None, speed: float | None = None) -> dict:
    k = _kokoro()
    voice = voice or script.get("voice", "af_heart")
    speed = speed or float(script.get("speed", 1.0))
    lang = script.get("lang", "en-us")  # Kokoro language code: en-us, en-gb, es, fr-fr, it, pt-br, hi, ja, cmn
    chunks, t = [], 0.0
    timings = {"segments": [], "voice": voice, "speed": speed}

    def silence(sec):
        nonlocal t
        chunks.append(np.zeros(int(SR * sec), dtype=np.float32))
        t += sec

    silence(0.4)
    for seg in script["segments"]:
        seg_t = {"id": seg["id"], "start": round(t, 3), "sentences": []}
        paragraphs = [p for p in re.split(r"\n\s*\n", seg["narration"].strip()) if p.strip()]
        for pi, par in enumerate(paragraphs):
            for sent in split_sentences(" ".join(par.split())):
                audio, sr = k.create(spoken(sent), voice=voice, speed=speed, lang=lang)
                assert sr == SR, sr
                audio = np.asarray(audio, dtype=np.float32)
                # trim leading/trailing near-silence so pauses stay under our control
                nz = np.where(np.abs(audio) > 0.003)[0]
                if len(nz):
                    audio = audio[max(0, nz[0] - 240): nz[-1] + 480]
                s0 = t
                chunks.append(audio)
                t += len(audio) / SR
                seg_t["sentences"].append({"text": sent, "start": round(s0, 3), "end": round(t, 3)})
                silence(PAUSE_SENTENCE)
            if pi < len(paragraphs) - 1:
                silence(PAUSE_PARAGRAPH - PAUSE_SENTENCE)
        silence(PAUSE_SEGMENT - PAUSE_SENTENCE)
        seg_t["end"] = round(t, 3)
        timings["segments"].append(seg_t)
        print(f"  voice {seg['id']}: {seg_t['end'] - seg_t['start']:.1f}s", flush=True)
    silence(0.6)
    wav = np.concatenate(chunks)
    peak = float(np.max(np.abs(wav))) or 1.0
    wav = (wav / peak * 0.89).astype(np.float32)
    build.mkdir(parents=True, exist_ok=True)
    sf.write(str(build / "narration.wav"), wav, SR)
    timings["duration"] = round(len(wav) / SR, 3)
    save_json(build / "timings.json", timings)
    return timings
