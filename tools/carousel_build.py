"""Instagram carousel from a winning Short (viral engine, step 5; owner ok 03/11/2026 for more posts).

  python tools/carousel_build.py [--tag <release tag>] [--at "YYYY-MM-DD HH:MM"] [--dry-run]

Picks the best Short of config/experiments-state.json (hits, score >= 1.5 x the median) that has no carousel yet,
or --tag. From its release (short.yaml: title, headline, narration already fact-checked; material-script.yaml:
sources) plus public-domain photos of the NASA Image Library on the same subject, it builds 1080x1350 slides: cover, one slide
per sentence with a number (2-5), a LOOK UP slide (no discount code on the image, ever). The JPEGs go to
cosmosinnumbers.github.io/media/carousels/<tag>/ (secret PAGES_TOKEN; Instagram fetches public URLs) and an
"ig-carousel" item enters queues/meta-queue.json at 19:00 (publish.yml + meta_api.guard: max 1 feed post in 20 h).
No new numbers are written: every slide is a sentence of the checked narration. Nothing without a source.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video" / "ytf"))
sys.path.insert(0, str(ROOT / "tools"))
from common import BRAND, CHANNEL, font, load_yaml  # noqa: E402

CW, CH = 1080, 1350
QUEUE = ROOT / "queues" / "meta-queue.json"
STATE = ROOT / "config" / "experiments-state.json"
PUBLOG = ROOT / "logs" / "youtube-publish-log.jsonl"
REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
PAGES = "https://api.github.com/repos/cosmosinnumbers/cosmosinnumbers.github.io/contents/media/carousels"
PUBLIC = "https://cosmosinnumbers.github.io/media/carousels"
MIN_SCORE = 1.5
DRY = "--dry-run" in sys.argv


def gh(*a) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"gh {' '.join(a[:3])}: {r.stderr.strip()[:200]}")
    return r.stdout


# ---------- slides ----------

def background(seed: int) -> Image.Image:
    from render import starfield
    sf = starfield(seed).convert("RGB")
    s = max(CW / sf.width, CH / sf.height)
    sf = sf.resize((int(sf.width * s) + 1, int(sf.height * s) + 1), Image.LANCZOS)
    return sf.crop((0, 0, CW, CH)).convert("RGBA")


def photo(path: Path, box_h: int) -> Image.Image:
    im = Image.open(path).convert("RGB")
    s = max(CW / im.width, box_h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x, y = (im.width - CW) // 2, (im.height - box_h) // 2
    return im.crop((x, y, x + CW, y + box_h)).convert("RGBA")


def wrap(d, text, f, width):
    lines, line = [], ""
    for w in text.split():
        t = (line + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            line = t
        else:
            lines.append(line)
            line = w
    return lines + [line] if line else lines


def footer(d, n, total):
    d.text((60, CH - 80), CHANNEL, font=font("display", 30, 700), fill=BRAND["cyan"])
    d.text((CW - 60, CH - 80), f"{n}/{total}", font=font("text", 28, 500), fill=BRAND["dust"], anchor="ra")


def fade(im, top, h):
    shade = Image.new("RGBA", (CW, h), BRAND["space"] + (0,))
    dd = ImageDraw.Draw(shade)
    for y in range(h):
        dd.line([(0, y), (CW, y)], fill=BRAND["space"] + (int(255 * y / h),))
    im.alpha_composite(shade, (0, top))


def cover(title, kicker, img, total, credit):
    im = background(len(title))
    if img:
        im.alpha_composite(photo(img, 760), (0, 0))
        fade(im, 340, 420)
    d = ImageDraw.Draw(im)
    if credit:
        d.text((CW - 40, 40), credit[:70], font=font("text", 22, 400), fill=BRAND["dust"], anchor="ra")
    y = 800
    d.text((60, y), kicker.upper(), font=font("text", 32, 700), fill=BRAND["amber"])
    f = font("display", 72, 700)
    for line in wrap(d, title, f, CW - 120)[:4]:
        y += 88
        d.text((60, y), line, font=f, fill=BRAND["star"])
    d.text((60, CH - 150), "Swipe →", font=font("text", 34, 600), fill=BRAND["cyan"])
    footer(d, 1, total)
    return im


def stat(number, text, img, n, total, credit):
    im = background(n * 7)
    top = 380
    if img:
        im.alpha_composite(photo(img, 560), (0, 0))
        fade(im, 360, 200)
        top = 620
    d = ImageDraw.Draw(im)
    if img and credit:
        d.text((CW - 40, 40), credit[:70], font=font("text", 22, 400), fill=BRAND["dust"], anchor="ra")
    size = 170 if len(number) <= 6 else 120
    d.text((60, top), number, font=font("display", size, 700), fill=BRAND["cyan"])
    y = top + size + 40
    f = font("text", 44, 500)
    for line in wrap(d, text, f, CW - 130)[:7]:
        d.text((64, y), line, font=f, fill=BRAND["star"])
        y += 60
    footer(d, n, total)
    return im


def product(n, total):
    im = background(99)
    d = ImageDraw.Draw(im)
    d.text((60, 260), "Want to see it", font=font("display", 80, 700), fill=BRAND["star"])
    d.text((60, 360), "with your own eyes?", font=font("display", 80, 700), fill=BRAND["star"])
    y = 540
    for line in ["LOOK UP: the beginner's stargazing", "guide by the numbers + 2027 sky calendar"]:
        d.text((60, y), line, font=font("text", 44, 600), fill=BRAND["cyan"])
        y += 62
    d.rounded_rectangle((60, 760, CW - 60, 900), radius=24, fill=BRAND["amber"])
    d.text((CW // 2, 830), "Link in bio", font=font("display", 56, 700), fill=BRAND["space"], anchor="mm")
    d.text((60, 960), "Full video on YouTube: @CosmosinNumbers", font=font("text", 36, 500), fill=BRAND["star"])
    footer(d, n, total)
    return im


# ---------- content ----------

NUM = re.compile(r"(?:about |nearly |over |almost )?-?\d[\d,.]*(?:\s?(?:%|°C|°F|°))?(?:\s(?:million|billion|trillion|thousand))?", re.I)


def slides_from(narration: str) -> list[tuple[str, str]]:
    """(big number, sentence) for each sentence with a new number; years alone do not count. At most 5.
    The big number is the one with the most digits ("1 in 2,100" stays whole); a number already shown is skipped."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", narration.strip()) if s.strip()]
    out, shown = [], set()
    for s in sents:
        odds = re.search(r"\b\d+ in [\d,]+\b", s)
        nums = [odds.group(0)] if odds else [m.group(0).strip() for m in NUM.finditer(s)
                                              if not re.fullmatch(r"(19|20)\d\d", m.group(0).strip())]
        nums = [re.sub(r"^(about|nearly|over|almost) ", "", x, flags=re.I) for x in nums]
        nums = [x for x in nums if x not in shown]
        if nums:
            big = max(nums, key=lambda x: len(re.sub(r"\D", "", x)))
            shown.add(big)
            out.append((big, s))
    return out[:5]


def caption(title: str, sources: list[dict], now: datetime) -> str:
    code = " · code COSMOS9" if now < datetime(2026, 12, 1) else ""
    src = "; ".join(s.get("title", "") for s in sources[:2] if s.get("title"))
    return "\n\n".join(filter(None, [
        f"{title} Which number surprised you most?",
        f"Full video on YouTube: @CosmosinNumbers (link in bio)\n📘 LOOK UP stargazing guide: link in bio{code}",
        f"Data: {src}." if src else "",
        "Text from our fact-checked Short, AI-assisted and checked by code against the sources. Images: NASA Image Library (public domain), credited on each slide.",
        "#space #astronomy #nasa #science #universe"]))


BAD = re.compile(r"presentation|briefing|news conference|press|interview|panel|podcast|poster|logo|portrait|award|"
                 r"ceremony|meeting|visit|employee|team photo", re.I)


def nasa_photos(tag: str, n: int, out: Path) -> tuple[list[Path], str]:
    """n photos from the NASA Image Library (public domain) searched with the words of the Short's slug, from the
    most specific query to the shortest. Photos only, never frames of our video (they carry captions)."""
    words = [w for w in tag.split("-")[1:] if w not in {"data", "reserve", "nasa", "new"} and not w[:1].isdigit()]
    seen, files, credits = set(), [], set()
    for k in range(min(3, len(words)), 0, -1):
        q = " ".join(words[:k])
        try:
            items = requests.get("https://images-api.nasa.gov/search", params={"q": q, "media_type": "image"},
                                 timeout=30).json()["collection"]["items"]
        except Exception as e:  # noqa: BLE001
            print("  NASA images failed:", type(e).__name__)
            break
        for it in items[:30]:
            d, links = it["data"][0], it.get("links") or []
            if d["nasa_id"] in seen or BAD.search(d.get("title", "") + " " + " ".join(d.get("keywords", []))) or not links:
                continue
            seen.add(d["nasa_id"])
            url = links[0]["href"].replace("~thumb", "~medium").replace("http://", "https://")
            try:
                r = requests.get(url, timeout=60)
                if r.status_code != 200 or len(r.content) < 20000:
                    continue
                p = out / f"p{len(files)}.jpg"
                p.write_bytes(r.content)
                Image.open(p).verify()
            except Exception:  # noqa: BLE001
                continue
            files.append(p)
            credits.add("NASA" + (f"/{d['center']}" if d.get("center") else ""))
            if len(files) >= n:
                return files, "Images: " + ", ".join(sorted(credits))
        if len(files) >= 2:
            break
    return files, ("Images: " + ", ".join(sorted(credits))) if credits else ""


def pick_tag(queue: list[dict]) -> str | None:
    done = {i["ref"][4:] for i in queue if i.get("ref", "").startswith("car-")}
    state = json.loads(STATE.read_text("utf-8")) if STATE.exists() else {}
    refs = {}
    for ln in PUBLOG.read_text("utf-8").splitlines() if PUBLOG.exists() else []:
        try:
            e = json.loads(ln)
            refs[e["id"]] = e["ref"]
        except (ValueError, KeyError):
            pass
    by_title = {}
    try:   # Shorts uploaded by hand before the API: match the release by its title
        for r in json.loads(gh("api", f"repos/{REPO}/releases?per_page=100")):
            by_title[re.sub(r"#\w+", "", r.get("name") or "").strip().lower()] = r["tag_name"]
    except (RuntimeError, ValueError):
        pass
    for h in state.get("hits", []):
        tag = refs.get(h.get("id")) or by_title.get(h.get("title", "").strip().lower())
        if tag and h.get("score", 0) >= MIN_SCORE and tag not in done:
            return tag
    return None


def host(tag: str, files: list[Path]) -> list[str]:
    tok = (os.environ.get("PAGES_TOKEN") or "").strip()
    if not tok:
        sys.exit("no PAGES_TOKEN: Instagram needs public image URLs, carousel not queued")
    head = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    urls = []
    for f in files:
        api = f"{PAGES}/{tag}/{f.name}"
        if requests.get(api, headers=head, timeout=60).status_code != 200:
            r = requests.put(api, headers=head, timeout=120, json={"message": f"media: carosello {tag}",
                                                                    "content": base64.b64encode(f.read_bytes()).decode()})
            if r.status_code not in (200, 201):
                sys.exit(f"github.io upload {f.name}: HTTP {r.status_code}")
        urls.append(f"{PUBLIC}/{tag}/{f.name}")
    return urls


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    queue = json.loads(QUEUE.read_text("utf-8")) if QUEUE.exists() else []
    tag = a[a.index("--tag") + 1] if "--tag" in a else pick_tag(queue)
    if not tag:
        print(f"No Short with score >= {MIN_SCORE} without a carousel: nothing to do.")
        return
    if any(i.get("ref") == f"car-{tag}" for i in queue):
        print(f"car-{tag} already queued.")
        return
    now = datetime.now()
    at = a[a.index("--at") + 1] if "--at" in a else f"{now:%Y-%m-%d} 19:00"
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        try:
            gh("release", "download", tag, "--repo", REPO, "-p", "short.yaml", "-p", "material-script.yaml", "-D", str(d))
        except RuntimeError as e:
            sys.exit(f"{tag}: release files missing ({e}): no carousel")
        if not (d / "short.yaml").exists():
            sys.exit(f"{tag}: no short.yaml in the release (older Short): no carousel")
        spec = load_yaml(d / "short.yaml")
        sources = (load_yaml(d / "material-script.yaml") or {}).get("sources", []) if (d / "material-script.yaml").exists() else []
        if not sources:
            sys.exit(f"{tag}: no sources: no carousel (every number needs a source)")
        stats = slides_from(spec["narration"])
        if len(stats) < 2:
            sys.exit(f"{tag}: only {len(stats)} sentences with a number: no carousel")
        imgs, credit = nasa_photos(tag, len(stats) + 1, d)
        title = spec["title"].replace("#shorts", "").strip()
        total = len(stats) + 2
        pages = [cover(title, "Real NASA data", imgs[0] if imgs else None, total, credit)]
        pages += [stat(nm, txt, imgs[i + 1] if len(imgs) > i + 1 else None, i + 2, total, credit) for i, (nm, txt) in enumerate(stats)]
        pages.append(product(total, total))
        out = ROOT / "build" / "carousels" / tag
        out.mkdir(parents=True, exist_ok=True)
        files = []
        for i, p in enumerate(pages, 1):
            f = out / f"{i:02d}.jpg"
            p.convert("RGB").save(f, quality=90)
            files.append(f)
    cap = caption(title, sources, now)
    print(f"{tag}: {len(files)} slides -> {out}\n{cap}")
    if DRY:
        return
    item = {"ref": f"car-{tag}", "at": at, "action": "ig-carousel", "images": host(tag, files), "caption": cap}
    queue.append(item)
    QUEUE.write_text(json.dumps(queue, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print("queued", item["ref"], "at", at)


if __name__ == "__main__":
    main()
