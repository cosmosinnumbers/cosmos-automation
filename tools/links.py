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


def is_product_link(text: str) -> bool:
    cfg_urls = []
    try:
        cfg_urls = [v["short_url"] for v in json.loads(CFG.read_text("utf-8")).values()]
    except (OSError, ValueError):
        pass
    return "gumroad.com/l/" in text or any(u in text for u in cfg_urls)
