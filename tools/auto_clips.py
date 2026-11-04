"""Clips of a new long video, chosen by code (memory 04/11/2026: "longform-auto non crea clips.yaml", it was written
by hand from the .srt). Every short video is a clip of a long one, so this decides what goes out on every channel.

  python tools/auto_clips.py <id> <path/to/id.srt> [--max 8] [--dry-run]

1. Times: the narration of script.yaml segments (and its paragraphs) is aligned to the .srt of the finished video
   (word stream, first words of each paragraph searched near the expected place), so a clip starts and ends on a
   caption boundary, never mid-sentence.
2. Candidates: inside each chapter, consecutive paragraphs grouped into 25-55 s pieces (the 03/11 hit "What a
   light-year really is" was 46 s of one chapter).
3. Ranking: motion graphics in the chapter (counter, kinetic, scale, compare, timer, bars, chart: the hit was all
   animated numbers) + the score that the cross-channel learning loop predicts for the chapter and its text
   (tools/cross_learn.py). The best `--max` clips, at least 8 s apart, kept in video order.
4. Headline: one short line (<= 40 characters, learned rule) from the writers (Gemini, then the backups), checked:
   no digit that is not in the clip's narration, no price/code; otherwise the chapter title.
Output: longform/<id>/clips.yaml in the hand-written format ({id, start, end, headline}); long-clips renders them.
Never overwrites an existing clips.yaml.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import cross_learn  # noqa: E402

MOTION = {"counter", "kinetic", "scale", "compare", "timer", "bars", "chart", "orbit", "headlines", "typewriter"}
MIN_S, MAX_S, GAP_S = 25.0, 55.0, 8.0
BAD = re.compile(r"\$|\bcode\b|discount|COSMOS9|LAUNCH9|subscribe|link in bio", re.I)


def norm(t: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", t.lower().replace(",", ""))


def srt_cues(text: str) -> list[tuple[float, float, str]]:
    out = []
    for b in re.split(r"\n\s*\n", text.strip()):
        lines = b.strip().splitlines()
        if len(lines) < 3:
            continue
        m = re.findall(r"(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if len(m) < 2:
            continue
        t0, t1 = [int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000 for h, mi, s, ms in m[:2]]
        out.append((t0, t1, " ".join(lines[2:])))
    return out


def word_stream(cues):
    """[(word, cue index)] of the whole .srt."""
    return [(w, i) for i, (_, _, txt) in enumerate(cues) for w in norm(txt)]


def locate(stream, words: list[str], guess: int, window: int = 80) -> int | None:
    """Index in the stream where `words` (first 4) start, searched around `guess`."""
    key = words[:4]
    if not key:
        return None
    lo, hi = max(0, guess - window), min(len(stream), guess + window)
    best = None
    for i in range(lo, hi):
        if [w for w, _ in stream[i:i + len(key)]] == key:
            if best is None or abs(i - guess) < abs(best - guess):
                best = i
    return best


def paragraphs(spec: dict) -> list[dict]:
    """[{seg, chapter, text, motion}] in narration order."""
    out = []
    for s in spec.get("segments", []):
        if re.search(r"outro|subscribe|look.?up|cta|credits", f"{s.get('id', '')} {s.get('chapter', '')}", re.I):
            continue   # the call to action is not a clip: every clip already ends on the YouTube + LOOK UP card
        kinds = [str(v.get("type", "")) for v in s.get("visuals", []) or []]
        motion = sum(k in MOTION for k in kinds) / max(1, len(kinds))
        for p in [p.strip() for p in str(s.get("narration", "")).split("\n\n") if p.strip()]:
            out.append({"seg": s.get("id"), "chapter": str(s.get("chapter") or s.get("id") or ""), "text": p,
                        "motion": motion})
    return out


def timed(paras: list[dict], cues) -> list[dict]:
    """Adds start/end (cue boundaries) to every paragraph found in the .srt."""
    stream = word_stream(cues)
    total = sum(len(norm(p["text"])) for p in paras) or 1
    pos, found = 0, []
    for p in paras:
        w = norm(p["text"])
        guess = round(pos * len(stream) / total)
        i = locate(stream, w, guess)
        pos += len(w)
        if i is not None:
            p["i"] = i
            found.append(p)
    for a, b in zip(found, found[1:] + [None]):
        a["start"] = cues[stream[a["i"]][1]][0]
        last_cue = (stream[b["i"]][1] - 1) if b else len(cues) - 1
        a["end"] = cues[max(stream[a["i"]][1], last_cue)][1]
    return [p for p in found if p["end"] > p["start"]]


def candidates(paras: list[dict]) -> list[dict]:
    """Consecutive paragraphs of the same chapter, 25-55 s."""
    out = []
    for i in range(len(paras)):
        for j in range(i, len(paras)):
            if paras[j]["seg"] != paras[i]["seg"]:
                break
            dur = paras[j]["end"] - paras[i]["start"]
            if dur > MAX_S:
                break
            if dur >= MIN_S:
                text = " ".join(p["text"] for p in paras[i:j + 1])
                out.append({"start": round(paras[i]["start"], 1), "end": round(paras[j]["end"], 1),
                            "chapter": paras[i]["chapter"], "text": text, "motion": paras[i]["motion"],
                            "first": paras[i] is paras[0] or paras[i - 1]["seg"] != paras[i]["seg"]})
    return out


def rank(cands: list[dict], weights: dict | None = None) -> list[dict]:
    w = weights if weights is not None else cross_learn._jload(cross_learn.OUT, {})
    for c in cands:
        c["score"] = round(cross_learn.predict(f"{c['chapter']} | {c['text'][:300]}", w) + 0.6 * c["motion"]
                           + (0.1 if c["first"] else 0.0) - 0.004 * abs(c["end"] - c["start"] - 42), 3)
    return sorted(cands, key=lambda c: -c["score"])


def pick(cands: list[dict], n: int) -> list[dict]:
    chosen: list[dict] = []
    for c in cands:
        if all(c["end"] + GAP_S <= o["start"] or c["start"] >= o["end"] + GAP_S for o in chosen):
            chosen.append(c)
        if len(chosen) >= n:
            break
    return sorted(chosen, key=lambda c: c["start"])


def chapter_headline(ch: str, text: str = "", title: str = "") -> str:
    """Fallback headline: the chapter title, else the first sentence when short, else the long video's title."""
    h = re.sub(r"^(step|part|chapter)\s*\d+\s*[:.\-]\s*", "", ch, flags=re.I).strip()
    if h and not re.fullmatch(r"(intro|introduction|hook|outro|conclusion)", h, re.I) and len(h.split()) >= 2:
        return (h[:1].upper() + h[1:])[:48]
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0] if text else ""
    if 8 <= len(first) <= 48:
        return first.rstrip(".")
    t = re.split(r"[:?]", title)[0].strip() if title else ""
    return t[:48] or "The full story in numbers"


def ok_headline(h: str, text: str) -> bool:
    if not h or len(h) > 48 or BAD.search(h) or "\n" in h:
        return False
    digits = set(re.findall(r"\d+(?:[.,]\d+)?", h))
    return digits <= set(re.findall(r"\d+(?:[.,]\d+)?", text))


def llm_headlines(clips: list[dict], title: str) -> list[str | None]:
    """One headline per clip from the writers, or None (the caller falls back to the chapter title)."""
    if os.environ.get("AUTO_CLIPS_LLM", "1") == "0":
        return [None] * len(clips)
    sys.path.insert(0, str(ROOT / "video" / "ytf"))
    try:
        import auto_short as a  # noqa: E402
    except Exception as e:  # noqa: BLE001
        print(f"no writer ({type(e).__name__})")
        return [None] * len(clips)
    block = "\n".join(f"{i + 1}. [{c['chapter']}] {c['text'][:600]}" for i, c in enumerate(clips))
    prompt = (f"These are {len(clips)} clips (30-55 s, vertical, Instagram Reels / YouTube Shorts / TikTok) cut from "
              f"our long video \"{title}\". Write ONE on-screen headline per clip, in English, 40 characters or "
              "fewer, that makes a scroller stop and watch: a plain-words promise of the payoff (like \"What a "
              "light-year really is\" or \"The Sun you see is 8 minutes old\"). No clickbait words, no emojis, no "
              "hashtags, and a number only if it is in that clip's text.\n\n" + block +
              '\n\nAnswer JSON only: {"headlines": ["...", "..."]}')
    msgs = [{"role": "user", "parts": [{"text": prompt}]}]
    out = None
    try:
        out = a.gemini(msgs, search=False)
    except SystemExit:
        out = None
    except Exception as e:  # noqa: BLE001
        print(f"Gemini: {type(e).__name__}")
    if not out or not (out[1] or {}).get("headlines"):
        try:
            out = a.backup_llm(msgs)
        except Exception as e:  # noqa: BLE001
            print(f"backup writer: {type(e).__name__}")
            out = None
    heads = list(((out or (None, {}))[1] or {}).get("headlines") or [])
    return [str(heads[i]).strip().strip('"') if i < len(heads) and heads[i] else None for i in range(len(clips))]


def build(vid: str, srt_path: Path, n: int = 8, llm: bool = True) -> list[dict]:
    d = ROOT / "longform" / vid
    spec = yaml.safe_load((d / "script.yaml").read_text("utf-8"))
    cues = srt_cues(srt_path.read_text("utf-8"))
    paras = timed(paragraphs(spec), cues)
    print(f"{vid}: {len(cues)} captions, {len(paras)} paragraphs aligned")
    clips = pick(rank(candidates(paras)), n)
    heads = llm_headlines(clips, spec.get("title", vid)) if llm else [None] * len(clips)
    out, seen = [], set()
    for k, (c, h) in enumerate(zip(clips, heads)):
        if not (h and ok_headline(h, c["text"])):
            h = chapter_headline(c["chapter"], c["text"], spec.get("title", ""))
        if h.lower() in seen:
            h = f"{h} (part {k + 1})"
        seen.add(h.lower())
        out.append({"id": f"{vid.split('-')[0]}-clip-{chr(97 + k)}", "start": c["start"], "end": c["end"],
                    "headline": h, "_score": c["score"]})
    return out


def dump(clips: list[dict]) -> str:
    lines = ["# written by tools/auto_clips.py: ranked by motion graphics + cross-channel learning (config/cross-weights.json)"]
    for c in clips:
        h = c["headline"].replace('"', "'")
        lines.append(f'- {{id: {c["id"]}, start: {c["start"]}, end: {c["end"]}, headline: "{h}"}}  # score {c["_score"]}')
    return "\n".join(lines) + "\n"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    vid, srt = a[0], Path(a[1])
    n = int(a[a.index("--max") + 1]) if "--max" in a else 8
    dest = ROOT / "longform" / vid / "clips.yaml"
    if dest.exists() and "--force" not in a:
        print(f"{dest} exists: left as it is")
        return
    clips = build(vid, srt, n, llm="--no-llm" not in a)
    text = dump(clips)
    print(text)
    if not clips:
        sys.exit("no clip found (srt not aligned?)")
    if "--dry-run" not in a:
        dest.write_text(text, "utf-8")
        print(f"-> {dest}")


if __name__ == "__main__":
    main()
