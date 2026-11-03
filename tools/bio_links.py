"""Put the tracked Gumroad links in the profile texts that the APIs allow (run by bio-links.yml).

  python tools/bio_links.py facebook|youtube [--dry-run]

- facebook : Page "website" + "about" (Graph API, token META_JSON; needs pages_manage_metadata).
- youtube  : channel description gets the free-PDF and LOOK UP lines on top (channels.update, token YOUTUBE_TOKEN_JSON).
Instagram, TikTok, Threads and X bios have no write API: the same links are given to the owner to paste.
The current values are printed first (public text) so a change can be undone by hand. Idempotent.
"""
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "video"))
DRY = "--dry-run" in sys.argv
GR = {"Authorization": "Bearer " + json.loads((ROOT / "secrets" / "gumroad.json").read_text("utf-8"))["access_token"]}


def utm(campaign: str, source: str, medium: str) -> str:
    for u in requests.get("https://api.gumroad.com/v2/utm_links", headers=GR, timeout=60).json().get("utm_links", []):
        if (u["utm_campaign"], u["utm_source"], u["utm_medium"]) == (campaign, source, medium):
            return u["short_url"]
    sys.exit(f"UTM link {campaign}/{source}/{medium} missing: run gumroad-utm create first")


def facebook():
    import creds
    c = creds.load("meta")
    G, pid, tok = "https://graph.facebook.com/v21.0", c["page_id"], c["page_token"]
    cur = requests.get(f"{G}/{pid}", params={"access_token": tok, "fields": "website,about,description"}, timeout=60).json()
    print("current:", json.dumps(cur, ensure_ascii=False))
    free = utm("solar-system-20", "facebook", "post")
    about = "Space, by the numbers. Every fact checked against NASA, ESA and JPL data. Free PDF: The Solar System in 20 Numbers (link below)."
    print("new website:", free, "| about:", len(about), "chars")
    if DRY:
        return
    r = requests.post(f"{G}/{pid}", data={"access_token": tok, "website": free, "about": about}, timeout=60)
    print("facebook:", r.status_code, r.text[:300])


def youtube():
    from ytf import yt_api
    yt = yt_api.service()
    ch = yt.channels().list(part="brandingSettings", mine=True).execute()["items"][0]
    b = ch["brandingSettings"]
    cur = b.get("channel", {}).get("description", "")
    print("current description:\n" + cur + "\n---")
    free, look = utm("solar-system-20", "youtube", "description"), utm("look-up", "youtube", "description")
    if free in cur:
        print("already done")
        return
    new = (f"🆓 Free PDF, The Solar System in 20 Numbers: {free}\n"
           f"📘 LOOK UP, our beginner's stargazing guide: {look}\n\n{cur}")
    print("new description:\n" + new)
    if DRY:
        return
    b.setdefault("channel", {})["description"] = new
    yt.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": b}).execute()
    print("youtube: updated")


if __name__ == "__main__":
    {"facebook": facebook, "youtube": youtube}[sys.argv[1]]()
