"""Read-only audit of the Gumroad store, run by gumroad-audit.yml (no PC needed, no changes to the store).

  python tools/gumroad_audit.py

Writes reports/gumroad/:
  - audit-<date>.json : every product field the API gives (name, description, price, sales, tags, covers, files,
    variants, offer codes, custom fields) + sales of the last 90 days (count, country, referrer; no emails).
  - audit-<date>.md   : the same in readable form, plus a checklist of what the public page is missing.
  - page-<permalink>.html / profile.html : the public pages as a visitor sees them (to check copy and layout).
Token in secrets/gumroad.json ("access_token", from the GUMROAD_JSON secret). Buyer emails are never written.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from html import unescape
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "gumroad"
API = "https://api.gumroad.com/v2"
UA = {"User-Agent": "Mozilla/5.0 (cosmos-automation audit)"}


def text(html: str) -> str:
    t = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", html or "", flags=re.I)
    t = re.sub(r"<li[^>]*>", "- ", t, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", unescape(re.sub(r"<[^>]+>", "", t))).strip()


def checks(p: dict, page: str) -> list[str]:
    d = text(p.get("description", ""))
    out = []
    out.append(("OK" if len(d) >= 600 else "DEBOLE") + f": descrizione di {len(d)} caratteri")
    out.append(("OK" if p.get("thumbnail_url") else "MANCA") + ": miniatura quadrata (thumbnail)")
    out.append(("OK" if p.get("preview_url") else "MANCA") + ": cover/anteprima")
    out.append(("OK" if p.get("custom_summary") else "MANCA") + ": riepilogo breve (summary)")
    out.append(("OK" if p.get("tags") else "MANCA") + ": tag per Discover")
    out.append(("OK" if p.get("customizable_price") else "NO") + ": prezzo libero (pay what you want)")
    out.append(("OK" if p.get("custom_receipt") else "MANCA") + ": ricevuta personalizzata (link a YouTube/prossimo prodotto)")
    out.append(("OK" if re.search(r"rating|review", page, re.I) else "?") + ": recensioni sulla pagina")
    out.append(("OK" if p.get("max_purchase_count") is None else "LIMITE") + ": nessun limite di acquisti")
    return out


def main():
    tok = {"access_token": json.loads((ROOT / "secrets" / "gumroad.json").read_text("utf-8"))["access_token"]}
    OUT.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    me = requests.get(f"{API}/user", params=tok, timeout=60).json().get("user", {})
    me = {k: me.get(k) for k in ("name", "bio", "url", "profile_url", "twitter_handle", "display_name")}
    prods = requests.get(f"{API}/products", params=tok, timeout=60).json().get("products", [])
    for p in prods:
        pid = p["id"]
        p["offer_codes"] = requests.get(f"{API}/products/{pid}/offer_codes", params=tok, timeout=60).json().get("offer_codes", [])
        p["variant_categories"] = requests.get(f"{API}/products/{pid}/variant_categories", params=tok, timeout=60).json().get("variant_categories", [])
        p["custom_fields_api"] = requests.get(f"{API}/products/{pid}/custom_fields", params=tok, timeout=60).json().get("custom_fields", [])
    sales, page_no = [], 1
    after = (date.today() - timedelta(days=90)).isoformat()
    while page_no <= 10:
        j = requests.get(f"{API}/sales", params={**tok, "after": after, "page": page_no}, timeout=60).json()
        for s in j.get("sales", []):
            sales.append({k: s.get(k) for k in ("created_at", "product_name", "price", "country", "referrer", "offer_code",
                                                 "refunded", "discover_fee_charged")})
        if not j.get("next_page_url"):
            break
        page_no += 1
    pages = {}
    base = (me.get("url") or "https://cosmosinnumbers.gumroad.com").rstrip("/")
    for name, url in [("profile", base)] + [(f"page-{p.get('custom_permalink') or p['id'][:8]}", p.get("short_url"))
                                            for p in prods if p.get("short_url")]:
        try:
            r = requests.get(url, headers=UA, timeout=60)
            pages[name] = r.text
            (OUT / f"{name}.html").write_text(r.text, "utf-8")
        except requests.RequestException as e:
            pages[name] = ""
            print("page", name, "not read:", e)
    (OUT / f"audit-{today}.json").write_text(json.dumps({"user": me, "products": prods, "sales_90d": sales},
                                                        ensure_ascii=False, indent=1), "utf-8")
    md = [f"# Audit Gumroad {today}", "", f"Profilo: **{me.get('name')}** ({base})", "", f"Bio: {me.get('bio') or '(vuota)'}", "",
          f"Vendite ultimi 90 giorni: **{len(sales)}**"]
    if sales:
        md += [f"- per paese: {dict(Counter(s['country'] for s in sales))}",
               f"- per provenienza: {dict(Counter(s['referrer'] for s in sales))}"]
    for p in prods:
        perm = p.get("custom_permalink") or p["id"][:8]
        md += ["", f"## {p.get('name')}", "",
               f"- link: {p.get('short_url')} · pubblicato: {p.get('published')} · prezzo: ${p.get('price', 0) / 100:.2f}"
               f" · minimo libero: {p.get('customizable_price')} · vendite: {p.get('sales_count')} · incasso: ${(p.get('sales_usd_cents') or 0) / 100:.2f}",
               f"- tag: {p.get('tags')} · summary: {p.get('custom_summary')!r}",
               f"- thumbnail: {p.get('thumbnail_url')} · cover: {p.get('preview_url')}",
               f"- file: {[f.get('name') for f in p.get('file_info', []) or []] if isinstance(p.get('file_info'), list) else p.get('file_info')}",
               f"- codici sconto: {[(c.get('name'), c.get('amount_cents') or c.get('percent_off'), c.get('times_used')) for c in p['offer_codes']]}",
               f"- varianti: {[(v.get('title')) for v in p['variant_categories']]}", "", "### Controlli", ""]
        md += [f"- {c}" for c in checks(p, pages.get(f"page-{perm}", ""))]
        md += ["", "### Descrizione attuale (testo)", "", "```", text(p.get("description", "")), "```"]
    (OUT / f"audit-{today}.md").write_text("\n".join(md) + "\n", "utf-8")
    print(f"audit ok: {len(prods)} products, {len(sales)} sales in 90 days")


if __name__ == "__main__":
    main()
