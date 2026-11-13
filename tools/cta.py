"""Product CTA for Threads and X: always the FIRST reply under the post, with rotating texts (CLAUDE.md, 19/10/2026).

Sales review 13/11/2026 (0 sales, 0 free downloads, about 13 human clicks in 10 days):
- the old lines sold "a guide" in general. Jev (TypeSafe) scored 12 candidate lines for pull on a casual reader:
  the free sky calendar (2.94/4) and "find this yourself tonight" (2.75) won; "If you like these numbers..." (1.18),
  "173 pages, every number sourced" (1.40) and the facts PDF (1.23) were at the bottom. The texts below follow it.
- the links are the tracked ones (tools/links.py), so the daily funnel report can tell which channel sends clicks.
- a post about something visible in the sky gets the lines that tie the guide to going outside tonight.
The text is chosen from the item ref, so a retry always picks the same one.
"""
from __future__ import annotations

import re
import zlib

import links

CODE = "Code COSMOS9 → $7.41 until Nov 30."
SKY_POST = re.compile(r"tonight|meteor|shower|eclipse|supermoon|full moon|new moon|night sky|naked eye|binocular|"
                      r"telescope|visible|look up|stargaz|conjunction|constellation|jupiter|saturn|venus|mars\b|"
                      r"mercury|the moon|andromeda|milky way|apod|picture of the day", re.I)


def texts(source: str = "threads", sky: bool = False) -> list[str]:
    """Each under 280 characters with the links (X counts a URL as 23)."""
    look = links.link(links.LOOK_UP, source, "reply")
    name, free = links.free(source, "reply")
    cal = "sky calendar" in name
    first = (f"🆓 Free: the next 30 nights on one page. Planets, Moon and meteor showers, no telescope: {free}" if cal
             else f"🆓 Free PDF, The Solar System in 20 Numbers: {free}")
    out = [
        f"{first}\nWant to know what everything else up there is? LOOK UP: {look}\n{CODE}",
        f"Want to find this yourself tonight? LOOK UP shows you where to look, no telescope needed: {look}\n{CODE}",
        f"Most people who say \"I can't see anything up there\" were never shown where to look. LOOK UP fixes that: {look}\n{CODE}",
        f"{first}\nThe full beginner's guide to the night sky is LOOK UP: {look}\n{CODE}",
    ]
    if sky:
        out += [
            f"Go out and find it: LOOK UP shows where and when to look, with your eyes or ordinary binoculars: {look}\n{CODE}",
            f"30 nights from \"what is that bright dot?\" to finding another galaxy. The LOOK UP 30-Night Challenge: {look}\n{CODE}",
        ]
    return out


TEXTS = texts() + texts(sky=True)[-2:]   # every text that can go out (tests/test_post_qc.py checks them all)


def first_reply(ref: str, replies: list[str], expired: bool = False, source: str = "threads", post: str = "") -> list[str]:
    own = [r for r in replies if links.is_product_link(r)]
    rest = [r for r in replies if not links.is_product_link(r)]
    pool = texts(source, sky=bool(SKY_POST.search(post)))
    link = own[0] if own else pool[zlib.crc32(ref.encode()) % len(pool)]
    if expired:  # after 30/11/2026 the COSMOS9 price ends: drop the code line
        link = link.replace("\n" + CODE, "").replace(" " + CODE, "")
    return [link, *rest]
