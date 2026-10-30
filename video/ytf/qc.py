"""Quality & Compliance gate. Writes out/qc.md; any FAIL blocks the upload."""
from __future__ import annotations

import re
from pathlib import Path

from captions import chapters
from common import media_duration

BANNED = [
    (r"\bNASA (?:confirms|confirmed|admits|says)\b", "attributes a statement to NASA: needs a quoted NASA source"),
    (r"\bguarantee", "promise language"),
    (r"\b(?:scientists|experts) (?:are )?(?:baffled|terrified|stunned)\b", "sensational framing"),
    (r"\bproof of (?:aliens|alien life)\b", "unsupported claim"),
]


def check(script: dict, timings: dict, assets: dict, video: Path, loud: dict | None, desc: str) -> tuple[bool, str]:
    rows = []

    def add(ok, item, note=""):
        rows.append(("PASS" if ok else "FAIL", item, note))

    used = [v for seg in script["segments"] for v in seg["visuals"] if v["type"] in ("image", "chart", "video")]
    used += [{"src": v["bg"], "type": "image"} for seg in script["segments"] for v in seg["visuals"] if v.get("bg")]
    missing = [v["src"] for v in used if v["src"] not in assets]
    add(not missing, "Every visual is registered in assets.yaml", ", ".join(missing))
    bad = [k for k in {v["src"] for v in used} if k in assets and assets[k].get("check") != "ok"]
    add(not bad, "Every asset licence check is 'ok'", ", ".join(bad))
    nofile = [k for k in {v["src"] for v in used} if k in assets and not (video / assets[k]["file"]).exists()]
    add(not nofile, "Every asset file exists", ", ".join(nofile))
    nocred = [k for k in {v["src"] for v in used} if k in assets and assets[k]["type"] == "image" and not assets[k].get("credit")]
    add(not nocred, "Every image has an on-screen credit", ", ".join(nocred))

    src_ids = {s["id"] for s in script.get("sources", [])}
    unsourced, unknown = [], []
    for seg in script["segments"]:
        refs = set(seg.get("sources", []))
        unknown += [r for r in refs if r not in src_ids]
        if re.search(r"\d", seg["narration"]) and not refs and seg["id"] not in ("outro",):
            unsourced.append(seg["id"])
    add(not unsourced, "Segments with numbers cite at least one source", ", ".join(unsourced))
    add(not unknown, "Source references resolve", ", ".join(unknown))
    hits = []
    def norm(x):
        return " ".join(re.sub(r"[^a-z0-9 ]", " ", x.lower()).split())

    for seg in script["segments"]:
        # a NASA attribution passes only with the verbatim NASA wording (`nasa_quote`) repeated in the narration
        quoted = seg.get("nasa_quote") and norm(seg["nasa_quote"]) in norm(seg["narration"])
        for pat, why in BANNED:
            if quoted and "NASA" in pat:
                continue
            if re.search(pat, seg["narration"], re.I):
                hits.append(f"{seg['id']}: {why}")
    add(not hits, "No banned / sensational phrasing", "; ".join(hits))

    shots_file = video / "build" / "shots.json"
    if shots_file.exists():   # owner's feedback 26/10/2026: no shot on screen for 40 s or more
        import json
        long_shots = [f"{s['segment']} {s['end'] - s['start']:.0f}s" for s in json.loads(shots_file.read_text("utf-8"))
                      if s["end"] - s["start"] >= 40]
        add(not long_shots, "Every shot < 40 s", ", ".join(long_shots))

    words = sum(len(s["narration"].split()) for s in script["segments"])
    add(True, "Script length", f"{words} words")
    final = video / "out" / f"{script['id']}.mp4"
    if final.exists():
        d = media_duration(final)
        add(d >= 480, "Duration ≥ 8:00 (mid-roll eligible)", f"{d / 60:.2f} min")
    else:
        add(False, "Final video exists", str(final))
    if loud:
        i = float(loud.get("output_i", loud.get("input_i", 0)))
        add(True, "Loudness normalised to -14 LUFS", f"input {loud['input_i']} LUFS → target -14")
    ch = chapters(script, timings)
    gaps = [ch[k + 1][0] - ch[k][0] for k in range(len(ch) - 1)]
    add(len(ch) >= 3 and (not gaps or min(gaps) >= 10), "Chapters: ≥3, first at 0:00, each ≥10 s", f"{len(ch)} chapters")
    add(len(script["title"]) <= 100, "Title ≤ 100 characters", f"{len(script['title'])}")
    add(len(desc) <= 5000, "Description ≤ 5000 characters", f"{len(desc)}")
    tags = ", ".join(script.get("tags", []))
    add(len(tags) <= 500, "Tags ≤ 500 characters", f"{len(tags)}")
    for t in ("thumb_A.jpg", "thumb_B.jpg", "thumb_C.jpg"):
        add((video / "out" / t).exists(), f"Thumbnail {t} exists")

    ok = all(r[0] == "PASS" for r in rows)
    lines = [f"# QC — {script['id']}", "", f"**Result: {'PASS' if ok else 'FAIL'}**", "",
             "| Esito | Controllo | Note |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    lines += ["", "## Approvazioni umane (facoltative dal 26/10/2026: Simone non vuole più aspettare H3/H4; "
              "contano QC PASS e factcheck)", "",
              "- [ ] **H3** Script letto e approvato (fatti, tono, nessuna esagerazione)",
              "- [ ] **H4** Video guardato per intero, metadati e thumbnail approvati → caricare come *Privato*, poi pubblicare/programmare a mano",
              "", "Firma e data: ____________________"]
    (video / "out" / "qc.md").write_text("\n".join(lines) + "\n", "utf-8")
    return ok, "\n".join(lines)
