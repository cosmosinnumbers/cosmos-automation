"""One place for the product links (sales review 13/11/2026).

Before: posts and descriptions used the plain Gumroad URLs, so only the links of the bios were counted and nobody
knew which channel sends buyers. Now every text asks `link(product, source, medium)`: the tracked short link of
config/gumroad-utm.json (made by tools/gumroad_utm.py create) when it exists, the plain product URL otherwise.
"""
from __future__ import annotations

import json
from pathlib import Path

CFG = Path(__file__).resolve().parents[1] / "config" / "gumroad-utm.json"
BASE = "https://cosmosinnumbers.gumroad.com/l/"
LOOK_UP, SKY, FACTS = "look-up", "sky-30-nights", "solar-system-20"
PLAIN = (BASE, "https://gum.co/u/")   # how a product link starts, tracked or not
STORES = CFG.with_name("stores.json")   # Amazon links (empty until the book is live), Gumroad seller id, site


def link(product: str, source: str, medium: str) -> str:
    try:
        cfg = json.loads(CFG.read_text("utf-8"))
    except (OSError, ValueError):
        cfg = {}
    return (cfg.get(f"{product}|{source}|{medium}") or {}).get("short_url") or BASE + product


def free(source: str, medium: str) -> tuple[str, str]:
    """(name, link) of the free product to offer: the sky calendar once it is live (it has tracked links), else the facts PDF."""
    try:
        live = any(k.startswith(SKY + "|") for k in json.loads(CFG.read_text("utf-8")))
    except (OSError, ValueError):
        live = False
    return ("The Next 30 Nights, our free sky calendar", link(SKY, source, medium)) if live else \
           ("The Solar System in 20 Numbers, our free PDF", link(FACTS, source, medium))


def store(key: str) -> str:
    try:
        return str(json.loads(STORES.read_text("utf-8")).get(key) or "").strip()
    except (OSError, ValueError):
        return ""


def amazon() -> str:
    """The Amazon page of LOOK UP once KDP has put it on sale ("" before): the paperback first, it is the edition
    Gumroad cannot offer, and its page links the Kindle one."""
    return store("amazon_paperback") or store("amazon_kindle")


def sky_page(source: str = "") -> str:
    """The sky calendar as a web page on our site: nothing to download, no email asked (funnel review 16/11/2026)."""
    return store("site") + "sky.html" + (f"?src={source}" if source else "")


def is_product_link(text: str) -> bool:
    cfg_urls = []
    try:
        cfg_urls = [v["short_url"] for v in json.loads(CFG.read_text("utf-8")).values()]
    except (OSError, ValueError):
        pass
    am = [u for u in (store("amazon_paperback"), store("amazon_kindle")) if u]
    return "gumroad.com/l/" in text or any(u in text for u in cfg_urls + am)
