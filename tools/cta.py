"""Gumroad CTA for Threads and X: always the FIRST reply under the post, with rotating texts (CLAUDE.md, 19/10/2026).

If a queue item already has a reply with the LOOK UP link, it is moved to the first position; otherwise one of the
rotating texts below is added. The text is chosen from the item ref, so a retry always picks the same one.
"""
from __future__ import annotations

import zlib

LINK = "https://cosmosinnumbers.gumroad.com/l/look-up"
CODE = "Code LAUNCH9 → $9 until Nov 30."
TEXTS = [  # each under 280 characters with the link (X counts a URL as 23)
    f"📘 Want to go further? LOOK UP, our beginner's stargazing guide (no telescope needed): {LINK}\n{CODE}",
    f"🔭 Learn to find these things in the real sky with LOOK UP, our stargazing guide by the numbers: {LINK}\n{CODE}",
    f"Every number in our posts is checked against NASA data. Same for our guide LOOK UP: {LINK}\n{CODE}",
    f"Tonight's sky, explained with real data: LOOK UP, a beginner's guide for eyes and binoculars. {LINK}\n{CODE}",
    f"If you like these numbers, you'll like LOOK UP: what to see, when, and how to find it. {LINK}\n{CODE}",
]


def first_reply(ref: str, replies: list[str], expired: bool = False) -> list[str]:
    own = [r for r in replies if "gumroad.com/l/look-up" in r]
    rest = [r for r in replies if "gumroad.com/l/look-up" not in r]
    link = own[0] if own else TEXTS[zlib.crc32(ref.encode()) % len(TEXTS)]
    if expired:  # after 30/11/2026 the LAUNCH9 price ends: drop the code line
        link = link.replace("\n" + CODE, "").replace(" " + CODE, "")
    return [link, *rest]
