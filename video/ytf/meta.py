"""Upload package: title, description (chapters, sources, credits, disclosures), tags."""
from __future__ import annotations

from pathlib import Path

from captions import chapters
from common import CHANNEL

# How each video is made, stated in every description. The narration line must stay literally true:
# scripts are AI-assisted drafts, checked against the cited sources, and approved by a human (H3).
DISCLOSURES = [
    "Charts: made by " + CHANNEL + " from the public data listed above.",
    "Music & sound effects: original, synthesised for this channel.",
    "Narration: a synthetic voice (Kokoro-82M). The script was drafted with AI assistance, checked against the "
    "sources above and approved by a human editor before publication.",
]
NO_ENDORSEMENT = "Use of NASA/ESA imagery does not imply endorsement by NASA or ESA."


def hms(t: float) -> str:
    t = int(t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# free PDF first (review 9/11/2026: 0 free downloads and 4 clicks in a month, a free offer is the easier first click
# and leaves an email), the paid guide right under it
PRODUCT = ("🆓 Free PDF, The Solar System in 20 Numbers: https://cosmosinnumbers.gumroad.com/l/solar-system-20\n"
           "📘 LOOK UP, our beginner's stargazing guide: https://cosmosinnumbers.gumroad.com/l/look-up "
           "(code COSMOS9 → $7.41 until Nov 30)")   # product line first in every YouTube description (owner, 19/10/2026)


def description(script: dict, timings: dict, assets: dict) -> str:
    parts = [PRODUCT, "", script["description_intro"].strip(), ""]
    ch = chapters(script, timings)
    if len(ch) >= 3:
        parts.append("Chapters")
        parts += [f"{hms(t)} {name}" for t, name in ch]
        parts.append("")
    parts.append("Data & sources")
    for s in script.get("sources", []):
        parts.append(f"[{s['id']}] {s['title']} — {s['url']}")
    parts.append("")
    used = {v["src"] for seg in script["segments"] for v in seg["visuals"] if v["type"] in ("image", "chart", "video")}
    used |= {v["bg"] for seg in script["segments"] for v in seg["visuals"] if v.get("bg")}
    imgs = [assets[k] for k in sorted(used) if assets[k]["type"] in ("image", "video")]
    if imgs:
        parts.append("Image and footage credits (shown on screen as well)")
        for a in imgs:
            lab = " — artist's concept" if a.get("kind") == "illustration" else ""
            t = "" if a.get("kind") == "stock" or len(a["title"]) > 30 else a["title"]   # keeps the 5,000-character limit
            parts.append(f"• {t}{lab}: {a['credit']} — {a['source']}" if t or lab else f"• {a['credit']} — {a['source']}")
        parts.append(NO_ENDORSEMENT)
        parts.append("")
    parts += [
        *DISCLOSURES,
        "Spotted an error? Tell us in the comments — corrections are pinned.",
        "",
        " ".join("#" + h for h in script.get("hashtags", [])),
    ]
    return "\n".join(parts).strip() + "\n"


def write_package(script: dict, timings: dict, assets: dict, video: Path, srt_blocks: int) -> Path:
    out = video / "out"
    out.mkdir(exist_ok=True)
    desc = description(script, timings, assets)
    tags = script.get("tags", [])
    lines = [
        f"# Upload package — {script['id']}", "",
        "Visibility on upload: **Private** (publication only after human approval H4).", "",
        "## Title", script["title"], "",
        "## Alternative titles (for Studio A/B test)",
        *[f"- {t}" for t in script.get("alt_titles", [])], "",
        "## Description", "```", desc.rstrip(), "```", "",
        "## Tags", ", ".join(tags), f"({len(', '.join(tags))} characters, limit 500)", "",
        "## Studio settings",
        "- Audience: **No, it's not made for kids**",
        "- Category: Science & Technology · Language: English · Caption language: English",
        f"- Captions: upload `{script['id']}.srt` ({srt_blocks} blocks)",
        "- Altered or synthetic content: **No** — real imagery; illustrations are labelled on screen; "
        "the synthetic narrator does not impersonate a real person (see YouTube help 14328491).",
        "- Paid promotion: No",
        "- End screen: 1 element → playlist 'Real Space, Real Data' [CORSO: one end-screen element]",
        "- Thumbnails: `thumb_A.jpg` (main), `thumb_B.jpg`, `thumb_C.jpg` for Test & Compare",
    ]
    p = out / "upload.md"
    p.write_text("\n".join(lines) + "\n", "utf-8")
    (out / "description.txt").write_text(desc, "utf-8")
    return p
