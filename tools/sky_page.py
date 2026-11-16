"""The free sky calendar as a web page: cosmosinnumbers.github.io/sky.html (run every Monday by sky-calendar.yml).

  python tools/sky_page.py [--dry-run]     writes products/sky-30-nights/out/sky.html, then saves it on the site

Why (funnel review 16/11/2026): the calendar lived only behind the Gumroad checkout (email, then download) and had
0 downloads; the clicks its links showed were link-preview robots. A page asks nothing: it opens from any bio or
post, search engines can read it, and it carries the three next steps in order: the printable PDF, the email form
(Gumroad followers: no new account, the list stays where the products are) and LOOK UP (Gumroad and, once live, Amazon).
Same data as the PDF (products/sky-30-nights/out/sky.json, tools/sky.py: PyEphem, no LLM). Needs PAGES_TOKEN.
"""
import base64
import html
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import links

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "products" / "sky-30-nights" / "out"
API = "https://api.github.com/repos/cosmosinnumbers/cosmosinnumbers.github.io/contents"
ICON = {"moon": "🌙", "meteors": "☄️", "pairing": "✨"}
CODE_UNTIL = date(2026, 11, 30)


def follow_form(note: str = "New sky calendars and new guides by email. No spam, one click to leave.") -> str:
    """Gumroad's own follow form: the address goes straight to the store's followers, we never see or keep it here."""
    sid = links.store("gumroad_seller_id")
    if not sid:
        return ""
    return ('<form class="follow" action="https://app.gumroad.com/follow_from_embed_form" method="post">'
            f'<input type="hidden" name="seller_id" value="{sid}">'
            '<input type="email" name="email" required placeholder="Your email address" aria-label="Your email address">'
            '<button type="submit">Get updates by email</button>'
            f'<small>{html.escape(note)} Handled by Gumroad (<a href="privacy.html">privacy</a>).</small></form>')


def day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%a} {d.day} {d:%b}"


def build(sky: dict, today: date | None = None) -> str:
    today = today or date.today()
    e = html.escape
    start, end = date.fromisoformat(sky["start"]), date.fromisoformat(sky["end"])
    span = f"{start.day} {start:%B} to {end.day} {end:%B %Y}"
    planets = "".join(f"<li><strong>{e(p['name'])}</strong>: {e(p['text'])}"
                      + (f" <span class='mut'>(magnitude {p['mag']}, in {e(p['constellation'])})</span>" if p.get("visible") else "")
                      + "</li>" for p in sky["planets"])
    events = "".join(f"<tr><td>{ICON.get(ev['kind'], '•')} {day(ev['date'])}</td><td><strong>{e(ev['name'])}</strong><br>"
                     f"<span class='mut'>{e(ev['text'])}</span></td></tr>" for ev in sky["events"])
    pdf, look, am = links.link(links.SKY, "github-pages", "site"), links.link(links.LOOK_UP, "github-pages", "site"), links.amazon()
    price = "$7.41 with code COSMOS9 until 30 November, then $14" if today <= CODE_UNTIL else "$14"
    desc = f"What you can see in the night sky from {span}: the planets, the Moon and meteor showers, no telescope needed. Free, rebuilt every week."
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>What to See in the Night Sky: {start.day} {start:%b} to {end.day} {end:%b %Y} · Cosmos in Numbers</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{links.sky_page()}">
<meta property="og:title" content="The Next 30 Nights: what to see in the sky, no telescope needed">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{links.store('site')}sky-cover.png">
<link rel="icon" type="image/png" sizes="1024x1024" href="logo.png"><link rel="apple-touch-icon" href="logo.png"><link rel="stylesheet" href="style.css">
<style>
table{{border-collapse:collapse;width:100%}} td{{padding:10px 8px;border-top:1px solid #2a3458;vertical-align:top}} td:first-child{{white-space:nowrap;font-weight:600}}
.box{{background:#151c33;border:2px solid var(--acc);border-radius:14px;padding:16px 18px;margin:26px 0}} .box h2{{margin-top:0}}
.follow{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}} .follow input[type=email]{{flex:1 1 220px;padding:11px 12px;border-radius:8px;border:1px solid #2a3458;background:#0b1020;color:var(--fg);font:inherit}}
.follow button{{background:var(--acc);color:#0b1020;font:inherit;font-weight:700;padding:11px 18px;border:0;border-radius:8px;cursor:pointer}} .follow small{{flex-basis:100%;color:var(--mut)}}
</style></head>
<body><main>
<nav class="top"><a class="brand" href="index.html"><img src="logo.png" width="36" height="36" alt="Cosmos in Numbers logo"><span>Cosmos in Numbers</span></a>
<a href="sky.html">Sky this month</a><a href="look-up.html">LOOK UP guide</a><a href="links.html">Links</a></nav>
<h1>What to see in the night sky: the next 30 nights</h1>
<p class="mut">{span} · mid-northern latitudes ({e(sky['latitude'])}) · no telescope needed · rebuilt every Monday</p>

<h2>Which bright dots are planets</h2>
<ul>{planets}</ul>
<p class="mut">Tip: a planet shines with a steady light, a star twinkles.</p>

<h2>Dates to circle</h2>
<table>{events}</table>

<div class="box"><h2>Take it outside</h2>
<p>The same 30 nights as a 3-page PDF with two sky charts (evening and dawn) and the Moon drawn night by night.</p>
<p><a class="btn" href="{pdf}">Get the free PDF</a></p>
{follow_form()}</div>

<div class="box"><h2>Want to know what everything else up there is?</h2>
<p><strong>LOOK UP</strong> is our beginner's guide to the night sky: 173 pages, 45 field exercises, a month-by-month 2027 sky calendar and the 2 August 2027 total solar eclipse. Eyes and ordinary binoculars only. 30-day refund.</p>
<p><a class="btn" href="{look}">Get LOOK UP (PDF + EPUB)</a>{f'<a class="btn" style="background:transparent;color:var(--acc);border:2px solid var(--acc)" href="{am}">{links.amazon_formats()[0].upper() + links.amazon_formats()[1:]} edition on Amazon</a>' if am else ''}</p>
<p class="mut">{price}. <a href="look-up.html">Read Chapter 1 free</a>.</p></div>

<p class="mut" style="font-size:.9em">{e(sky['method'])}</p>
<footer><p><a href="index.html">About</a> · <a href="privacy.html">Privacy</a> · <a href="https://www.youtube.com/@CosmosinNumbers">YouTube</a></p>
<p class="mut">© {today.year} Cosmos in Numbers. The layout and the calculations were made with the help of AI tools.</p></footer>
</main></body></html>
"""


def put(name: str, data: bytes, message: str, head: dict) -> bool:
    import requests
    cur = requests.get(f"{API}/{name}", headers=head, timeout=60).json()
    if cur.get("content") and base64.b64decode(cur["content"]) == data:
        print(name, "already right")
        return True
    r = requests.put(f"{API}/{name}", headers=head, timeout=180, json={
        "message": message, "content": base64.b64encode(data).decode(), **({"sha": cur["sha"]} if "sha" in cur else {})})
    print(name, "saved" if r.status_code in (200, 201) else f"NOT saved: HTTP {r.status_code} {r.text[:200]}")
    return r.status_code in (200, 201)


def sitemap() -> bytes:
    site = links.store("site")
    urls = "".join(f"<url><loc>{site}{p}</loc></url>" for p in ("", "sky.html", "look-up.html", "links.html"))
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'.encode()


def main():
    page = build(json.loads((OUT / "sky.json").read_text("utf-8"))).encode("utf-8")
    (OUT / "sky.html").write_bytes(page)
    print("sky.html:", len(page), "bytes")
    if "--dry-run" in sys.argv:
        return
    tok = (os.environ.get("PAGES_TOKEN") or "").strip() or sys.exit("no PAGES_TOKEN")
    head = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    ok = put("sky.html", page, "site: sky.html, the next 30 nights", head)
    cover = OUT / "cover-1280x720.png"
    if cover.exists():
        put("sky-cover.png", cover.read_bytes(), "site: cover of the sky page", head)
    put("sitemap.xml", sitemap(), "site: sitemap", head)
    put("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {links.store('site')}sitemap.xml\n".encode(), "site: robots.txt", head)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
