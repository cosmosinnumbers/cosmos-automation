"""Gumroad UTM tracking links (API v2 /utm_links), run by gumroad-utm.yml.

  python tools/gumroad_utm.py create   # one link per channel x product, idempotent; writes config/gumroad-utm.json
  python tools/gumroad_utm.py stats    # clicks per link -> 07-analytics/metrics/gumroad-utm.jsonl (one row per link per day)

Why: the scorecard says Gumroad visits are "not measured". Each link redirects to the product page with
utm_source/medium/campaign and counts total and unique clicks, so we learn which channel actually sends people.
Links are not used in posts until their short_url has been checked (config/gumroad-utm.json lists them).
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.gumroad.com/v2"
CFG = ROOT / "config" / "gumroad-utm.json"
OUT = ROOT / "07-analytics" / "metrics" / "gumroad-utm.jsonl"
H = {"Authorization": "Bearer " + json.loads((ROOT / "secrets" / "gumroad.json").read_text("utf-8"))["access_token"]}
PRODUCTS = {"look-up": "LOOK UP", "solar-system-20": "Solar System in 20 Numbers (free)",
            "sky-30-nights": "The Next 30 Nights (free sky calendar)"}
CHANNELS = [("youtube", "description"), ("youtube", "comment"), ("threads", "reply"), ("x", "reply"),
            ("instagram", "bio"), ("tiktok", "bio"), ("facebook", "post"), ("github-pages", "site")]


def call(method, path, **kw):
    r = requests.request(method, f"{API}/{path}", headers=H, timeout=60, **kw)
    try:
        return r.json()
    except ValueError:
        return {"success": False, "message": r.text[:200]}


def create():
    prods = {p["custom_permalink"]: p["id"] for p in call("GET", "products").get("products", []) if p.get("custom_permalink")}
    have = {(u["utm_source"], u["utm_medium"], u["utm_campaign"]): u for u in call("GET", "utm_links").get("utm_links", [])}
    cfg = {}
    for perm, name in PRODUCTS.items():
        if perm not in prods:
            print("missing product", perm)
            continue
        for src, med in CHANNELS:
            key = (src, med, perm)
            u = have.get(key)
            if not u:
                j = call("POST", "utm_links", json={"title": f"{name}: {src} {med}", "target_resource_type": "product_page",
                                                     "target_resource_id": prods[perm], "utm_source": src,
                                                     "utm_medium": med, "utm_campaign": perm})
                u = j.get("utm_link")
                if not u:
                    print("FAIL", key, str(j)[:200])
                    continue
            cfg[f"{perm}|{src}|{med}"] = {"short_url": u["short_url"], "utm_url": u.get("utm_url"), "id": u["id"]}
            print("ok", perm, src, med, u["short_url"])
    CFG.parent.mkdir(exist_ok=True)
    CFG.write_text(json.dumps(cfg, indent=1, ensure_ascii=False), "utf-8")


def stats():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for u in call("GET", "utm_links").get("utm_links", []):
        rows.append({"channel": "gumroad-utm", "level": "link", "date": date.today().isoformat(), "read_at": now,
                     "id": u["id"], "title": u["title"], "metrics": {"clicks": u.get("total_clicks"),
                     "unique_clicks": u.get("unique_clicks")}, "source": u["utm_source"], "medium": u["utm_medium"],
                     "campaign": u["utm_campaign"]})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} links; clicks:", {f"{r['source']}/{r['medium']}/{r['campaign']}": r["metrics"]["unique_clicks"] for r in rows})


if __name__ == "__main__":
    {"create": create, "stats": stats}[sys.argv[1]]()
