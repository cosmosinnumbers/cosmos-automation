"""Apply the store changes of the 3/11/2026 audit through the Gumroad API v2 (run by gumroad-apply.yml).

  python tools/gumroad_apply.py [lookup] [free] [sky] [profile] [--dry-run]

- lookup : LOOK UP gets the new name, description (products/look-up/description.html), summary, tags, category,
           custom receipt. Price and offer codes are NOT touched (gumroad_offer.py does that).
- free   : creates (or updates, if the permalink exists) the free product "The Solar System in 20 Numbers" ($0+,
           suggested $3) from products/solar-system-20/: PDF uploaded with the presign flow, cover + thumbnail
           uploaded as direct uploads, PDF embedded in the content page, then published.
- sky    : the free rolling sky calendar "The Next 30 Nights" (products/sky-30-nights/, built by sky-calendar.yml):
           created the first time, afterwards the PDF is replaced with the fresh one (same link, new 30 nights).
- profile: store name "Cosmos in Numbers" and the new bio.
Needs a token with the edit_products scope (edit_profile for profile). Endpoints from the open-source Gumroad code
(antiwork/gumroad, app/controllers/api/v2). Tokens and buyer data are never printed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.gumroad.com/v2"
DRY = "--dry-run" in sys.argv
TOK = json.loads((ROOT / "secrets" / "gumroad.json").read_text("utf-8"))["access_token"]
H = {"Authorization": f"Bearer {TOK}"}
FREE = ROOT / "products" / "solar-system-20"

LOOKUP = {
    "name": "LOOK UP: Find Planets, Galaxies and the 2027 Eclipse, No Telescope Needed",
    "custom_summary": "173 pages · 45 outdoor exercises · month-by-month 2027 sky calendar · 14 bonus posters · PDF + EPUB",
    "tags": ["stargazing", "astronomy", "space", "beginner guide", "2027 calendar"],
    "custom_receipt": ("Thanks for picking up LOOK UP! Start with Chapter 1 tonight: it takes 20 minutes and you only "
                       "need your eyes. New space-by-the-numbers videos every week: youtube.com/@CosmosinNumbers. "
                       "After your first clear night, a quick rating here helps other beginners find the book."),
}
FREE_META = {
    "name": "The Solar System in 20 Numbers (Free PDF)",
    "custom_permalink": "solar-system-20",
    "custom_summary": "13 pages · 20 sourced facts · NASA, JPL and IAU data · free",
    "tags": ["astronomy", "solar system", "space facts", "free pdf", "stargazing"],
    "custom_receipt": ("Here's your guide! Read one number a night, then go outside. When you're ready for the real "
                       "sky, LOOK UP is our 173-page beginner's guide: cosmosinnumbers.gumroad.com/l/look-up "
                       "(new videos weekly: youtube.com/@CosmosinNumbers)"),
}
SKY = ROOT / "products" / "sky-30-nights"
SKY_META = {
    "name": "The Next 30 Nights: Free Sky Calendar (No Telescope Needed)",
    "custom_permalink": "sky-30-nights",
    "custom_summary": "3 pages · planets, Moon and meteor showers for the next 30 nights · rebuilt every week · free",
    "tags": ["stargazing", "night sky", "astronomy", "sky calendar", "free pdf"],
    "custom_receipt": ("Here's your sky calendar! Circle one date and go outside that night. It is rebuilt every week: "
                       "come back to the same page for the next 30 nights. Want to know what everything else up there "
                       "is? LOOK UP is our 173-page beginner's guide: cosmosinnumbers.gumroad.com/l/look-up"),
}
BIO = ("**Space, by the numbers.** Every fact checked against NASA, ESA and JPL data, no cosmic fiction.\n\n"
       "New here? Start with the free sky calendar *The Next 30 Nights*, then take *LOOK UP* outside on the next clear night.\n\n"
       "Weekly videos: youtube.com/@CosmosinNumbers")


def call(method: str, path: str, **kw) -> dict:
    if DRY and method != "GET":
        print(f"DRY {method} {path} keys={sorted((kw.get('json') or {}).keys())}")
        return {"success": True, "dry": True}
    r = requests.request(method, f"{API}/{path}", headers=H, timeout=120, **kw)
    try:
        j = r.json()
    except ValueError:
        j = {"success": False, "message": r.text[:300]}
    if r.status_code >= 400 or not j.get("success", True):
        print(f"FAIL {method} {path}: HTTP {r.status_code} {str(j.get('message') or j.get('error') or j)[:400]}")
        if r.status_code in (401, 403):
            sys.exit("The Gumroad token lacks the scope for this call (edit_products / edit_profile).")
    return j


def product_by_permalink(perm: str) -> dict | None:
    for p in call("GET", "products").get("products", []):
        if p.get("custom_permalink") == perm:
            return p
    return None


def taxonomy_id() -> str | None:
    cats = call("GET", "categories").get("categories", [])
    flat = [(str(c.get("path") or c.get("name")), c.get("id")) for c in cats]
    for want in ("astronomy", "science", "education"):
        hit = next(((n, i) for n, i in flat if want in n.lower()), None)
        if hit:
            print("category:", hit[0])
            return hit[1]
    print("category: none matched, left as is. Some:", [n for n, _ in flat[:20]])
    return None


def direct_upload(path: Path, ctype: str) -> str | None:
    data = path.read_bytes()
    blob = {"filename": path.name, "byte_size": len(data), "content_type": ctype,
            "checksum": base64.b64encode(hashlib.md5(data).digest()).decode()}
    j = call("POST", "direct_uploads", json={"blob": blob})
    if j.get("dry"):
        return "dry"
    du = j.get("direct_upload") or {}
    if not du.get("url"):
        print("direct upload refused:", str(j)[:300])
        return None
    r = requests.put(du["url"], data=data, headers=du.get("headers") or {}, timeout=300)
    print(f"uploaded {path.name}: HTTP {r.status_code}")
    return j.get("signed_id") if r.ok else None


def upload_file(path: Path) -> str | None:
    data = path.read_bytes()
    j = call("POST", "files/presign", json={"filename": path.name, "file_size": len(data)})
    if j.get("dry"):
        return "dry"
    parts, size, done = j.get("parts") or [], 100 * 1024 * 1024, []
    for p in parts:
        n = p["part_number"]
        r = requests.put(p["presigned_url"], data=data[(n - 1) * size: n * size], timeout=600)
        if not r.ok:
            print(f"part {n} refused: HTTP {r.status_code}")
            call("POST", "files/abort", json={"upload_id": j["upload_id"], "key": j["key"]})
            return None
        done.append({"part_number": n, "etag": r.headers.get("ETag", "").strip()})
    c = call("POST", "files/complete", json={"upload_id": j["upload_id"], "key": j["key"], "parts": done})
    print(f"uploaded {path.name}")
    return c.get("file_url")


def do_lookup(tax):
    p = product_by_permalink("look-up") or sys.exit("LOOK UP not found")
    body = {**LOOKUP, "description": (ROOT / "products/look-up/description.html").read_text("utf-8")}
    if tax:
        body["taxonomy_id"] = tax
    j = call("PUT", f"products/{p['id']}", json=body)
    print("LOOK UP updated" if j.get("success") else "LOOK UP NOT updated")
    # "look inside" images after the book cover: added once (the product then has more covers than the one cover)
    shots = sorted((ROOT / "products/look-up/previews").glob("*.png"))
    have = len(call("GET", f"products/{p['id']}").get("product", {}).get("covers") or [])
    if DRY or have > 1:
        print(f"look-inside images: {have} covers already there, nothing uploaded")
        return
    for shot in shots:
        sid = direct_upload(shot, "image/png")
        if sid:
            r = call("POST", f"products/{p['id']}/covers", json={"signed_blob_id": sid})
            print("look-inside image", shot.name, "added" if r.get("success") else "NOT added")


def do_free(tax):
    out = FREE / "out"
    p = product_by_permalink(FREE_META["custom_permalink"])
    body = {**FREE_META, "description": (FREE / "description.html").read_text("utf-8"), "price": 0,
            "customizable_price": True, "suggested_price_cents": 300}
    if tax:
        body["taxonomy_id"] = tax
    if p:
        print("free product exists: updating texts and replacing the PDF with the current build")
        url = upload_file(out / "the-solar-system-in-20-numbers.pdf")
        if not url:
            sys.exit("PDF upload failed")
        j = call("PUT", f"products/{p['id']}", json={**body, "files": [{"url": url, "display_name": "The Solar System in 20 Numbers"}]})
        if DRY or not j.get("success"):
            return
        got = call("GET", f"products/{p['id']}").get("product", {}).get("files") or []
        fid = got[-1].get("id") if got else None
        print("files on the product:", len(got), "| embedded file id:", fid)
        if fid:
            call("PUT", f"products/{p['id']}", json={"rich_content": [{"title": "Your guide", "description": {"type": "doc", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Thanks! Here is your guide. Read one number a night, then go outside and look up."}]},
                {"type": "fileEmbed", "attrs": {"id": fid}}]}}]})
        return
    url = upload_file(out / "the-solar-system-in-20-numbers.pdf")
    if not url:
        sys.exit("PDF upload failed")
    j = call("POST", "products", json={**body, "native_type": "ebook", "draft": True,
                                         "files": [{"url": url, "display_name": "The Solar System in 20 Numbers"}]})
    if j.get("dry"):
        return
    prod = j.get("product") or sys.exit(f"create failed: {str(j)[:300]}")
    pid = prod["id"]
    print("created draft", pid)
    show = call("GET", f"products/{pid}").get("product", {})
    files = show.get("files") or prod.get("files") or []
    fid = files[0].get("id") if files else None
    print("file id:", fid)
    if fid:
        page = {"title": "Your guide", "description": {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Thanks! Here is your guide. Read one number a night, then go outside and look up."}]},
            {"type": "fileEmbed", "attrs": {"id": fid}}]}}
        call("PUT", f"products/{pid}", json={"rich_content": [page]})
    for name, kind in (("cover-1280x720.png", "covers"), ("thumbnail-600x600.png", "thumbnail")):
        sid = direct_upload(out / name, "image/png")
        if sid:
            call("POST", f"products/{pid}/{kind}", json={"signed_blob_id": sid})
    e = call("PUT", f"products/{pid}/enable")
    print("published:", e.get("success"), e.get("message", ""))
    final = call("GET", f"products/{pid}").get("product", {})
    print("live at:", final.get("short_url"), "published:", final.get("published"))


def do_sky(tax):
    """Create the free sky calendar, or replace its PDF with this week's build (the link never changes)."""
    out = SKY / "out"
    pdf = out / "the-next-30-nights.pdf"
    if not pdf.exists():
        sys.exit("sky calendar not built: run tools/sky.py window and products/sky-30-nights/build.mjs first")
    p = product_by_permalink(SKY_META["custom_permalink"])
    body = {**SKY_META, "description": (SKY / "description.html").read_text("utf-8"), "price": 0,
            "customizable_price": True, "suggested_price_cents": 200}
    if tax:
        body["taxonomy_id"] = tax
    url = upload_file(pdf)
    if not url:
        sys.exit("PDF upload failed")
    files = [{"url": url, "display_name": "The Next 30 Nights"}]
    if p:
        print("sky calendar exists: replacing the PDF and the texts")
        j = call("PUT", f"products/{p['id']}", json={**body, "files": files})
        pid = p["id"]
        if not j.get("success"):
            sys.exit(f"update failed: {str(j)[:300]}")
    else:
        j = call("POST", "products", json={**body, "native_type": "ebook", "draft": True, "files": files})
        if j.get("dry"):
            return
        pid = (j.get("product") or sys.exit(f"create failed: {str(j)[:300]}"))["id"]
        print("created draft", pid)
    if DRY:
        return
    got = call("GET", f"products/{pid}").get("product", {}).get("files") or []
    fid = got[-1].get("id") if got else None   # the file just uploaded is the last one
    print("files on the product:", len(got), "| embedded file id:", fid)
    if fid:
        page = {"title": "Your sky calendar", "description": {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Here are your next 30 nights. Circle one date, "
             "then go outside and look up. This page is rebuilt every week: download it again any time."}]},
            {"type": "fileEmbed", "attrs": {"id": fid}}]}}
        call("PUT", f"products/{pid}", json={"rich_content": [page]})
    if not p:
        for name, kind in (("cover-1280x720.png", "covers"), ("thumbnail-600x600.png", "thumbnail")):
            sid = direct_upload(out / name, "image/png")
            if sid:
                call("POST", f"products/{pid}/{kind}", json={"signed_blob_id": sid})
        e = call("PUT", f"products/{pid}/enable")
        print("published:", e.get("success"), e.get("message", ""))
    final = call("GET", f"products/{pid}").get("product", {})
    print("live at:", final.get("short_url"), "published:", final.get("published"), "files:", len(final.get("files") or []))


def do_profile():
    j = call("PUT", "user", json={"name": "Cosmos in Numbers", "bio": BIO})
    print("profile updated" if j.get("success") else "profile NOT updated")


def main():
    what = [a for a in sys.argv[1:] if not a.startswith("--")] or ["lookup", "free", "profile"]
    tax = taxonomy_id() if {"lookup", "free", "sky"} & set(what) else None
    if "free" in what:
        do_free(tax)
    if "sky" in what:
        do_sky(tax)
    if "lookup" in what:
        do_lookup(tax)
    if "profile" in what:
        do_profile()


if __name__ == "__main__":
    main()
