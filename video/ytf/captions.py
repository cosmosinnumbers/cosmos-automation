"""Closed captions (SRT) from the per-sentence timings written by voice.py.

Each sentence was synthesised on its own, so its start/end are exact; inside a
sentence the time is shared out by character count, which is close enough for
caption blocks of one or two short lines.
"""
from __future__ import annotations

from pathlib import Path

MAX_LINE = 42


def ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def chunk(words: list[str]) -> list[str]:
    """Greedy blocks of at most two lines of MAX_LINE characters."""
    blocks, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if len(trial) > MAX_LINE * 2 - 4 and cur:
            blocks.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        text = " ".join(b)
        if len(text) > MAX_LINE:
            # break the block into two balanced lines
            best = min(range(1, len(b)), key=lambda k: abs(len(" ".join(b[:k])) - len(" ".join(b[k:]))))
            text = " ".join(b[:best]) + "\n" + " ".join(b[best:])
        out.append(text)
    return out


def write_srt(timings: dict, dest: Path) -> int:
    n, lines = 0, []
    for seg in timings["segments"]:
        for s in seg["sentences"]:
            blocks = chunk(s["text"].split())
            total = sum(len(b) for b in blocks)
            t = s["start"]
            for b in blocks:
                d = (s["end"] - s["start"]) * len(b) / total
                n += 1
                lines += [str(n), f"{ts(t)} --> {ts(t + d)}", b, ""]
                t += d
    dest.write_text("\n".join(lines), "utf-8")
    return n


def chapters(script: dict, timings: dict) -> list[tuple[float, str]]:
    out = []
    for seg, st in zip(script["segments"], timings["segments"]):
        if seg.get("chapter"):
            out.append((0.0 if not out else st["start"], seg["chapter"]))
    return out
