"""Keep the public site (cosmosinnumbers.github.io) in line with the store (run by site-patch.yml, manual).

  python tools/site_patch.py [--dry-run]

Found on 13/11/2026 while checking the bio links: the site still sold LOOK UP with the code LAUNCH9 at "$9", but the
real Gumroad code is COSMOS9 ($7.41 until 30/11/2026), so every "Get it for $9" button landed on the full price. Here:
- index.html, look-up.html, links.html: LAUNCH9 -> COSMOS9, "$9" -> "$7.41", "30+ outdoor exercises" -> 45;
- links.html: the free sky calendar (tracked link) right under the free chapter;
- look-up-preview.pdf: the tick boxes printed as "±0" become real boxes.
Idempotent: a file that is already right is not touched. Needs PAGES_TOKEN (contents: write on the site repo).
"""
import base64
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com/repos/cosmosinnumbers/cosmosinnumbers.github.io/contents"
DRY = "--dry-run" in sys.argv


def fix_html(name: str, s: str) -> str:
    s = s.replace("LAUNCH9", "COSMOS9")
    s = re.sub(r"\$9(?![\d.])", "$7.41", s)
    s = s.replace("30+ outdoor exercises", "45 outdoor exercises")
    if name == "links.html" and "sky-30-nights" not in s and "data-k=\"sky\"" not in s:
        reg = json.loads((ROOT / "config" / "gumroad-utm.json").read_text("utf-8"))
        url = (reg.get("sky-30-nights|github-pages|site") or {}).get("short_url") or "https://cosmosinnumbers.gumroad.com/l/sky-30-nights"
        link = (f'<a class="l" href="{url}" data-k="sky">🌙 Free: The Next 30 Nights<small>What to see in the sky this month '
                f'· planets, Moon, meteor showers · updated weekly</small></a>\n\n')
        s = s.replace("<!-- 2. Paid product", link + "<!-- 2. Paid product", 1)
    return s


def fix_boxes(data: bytes) -> bytes:
    """The '±0' printed where a tick box should be (a lost font glyph) becomes a drawn box."""
    import pymupdf
    doc, n = pymupdf.open(stream=data, filetype="pdf"), 0
    for pg in doc:
        hits = [pymupdf.Rect(w[:4]) for w in pg.get_text("words") if w[4] == "±0"]
        if not hits:
            continue
        pix = pg.get_pixmap(dpi=72)
        for r in hits:
            c = pix.pixel(int(max(0, r.x0 - 3)), int((r.y0 + r.y1) / 2))
            pg.add_redact_annot(pymupdf.Rect(r.x0 - 0.5, r.y0, r.x1 + 0.5, r.y1), fill=tuple(v / 255 for v in c[:3]))
        pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
        for r in hits:
            cy, x0 = (r.y0 + r.y1) / 2 + 0.6, r.x0 + 0.8
            pg.draw_rect(pymupdf.Rect(x0, cy - 3.6, x0 + 7.2, cy + 3.6), color=(0.11, 0.14, 0.25), width=0.8)
            n += 1
    print("tick boxes redrawn:", n)
    return doc.tobytes(garbage=3, deflate=True) if n else data


def main():
    tok = (os.environ.get("PAGES_TOKEN") or "").strip() or sys.exit("no PAGES_TOKEN")
    head = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    for name in ("index.html", "look-up.html", "links.html", "look-up-preview.pdf"):
        cur = requests.get(f"{API}/{name}", headers=head, timeout=60).json()
        if "sha" not in cur:
            print(name, "not read:", str(cur)[:160])
            continue
        old = base64.b64decode(cur["content"]) if cur.get("content") else requests.get(cur["download_url"], timeout=120).content
        new = fix_boxes(old) if name.endswith(".pdf") else fix_html(name, old.decode("utf-8")).encode("utf-8")
        if new == old:
            print(name, "already right")
            continue
        print(name, "changed:", len(old), "->", len(new), "bytes")
        if DRY:
            continue
        r = requests.put(f"{API}/{name}", headers=head, timeout=180, json={
            "message": f"site: {name} in line with the store (COSMOS9, free sky calendar, tick boxes)",
            "content": base64.b64encode(new).decode(), "sha": cur["sha"]})
        print(name, "saved" if r.status_code in (200, 201) else f"NOT saved: HTTP {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    main()
