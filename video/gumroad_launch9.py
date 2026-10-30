"""End of the COSMOS9 launch price on Gumroad (owner decision: $9 until 30/11/2026), run by launch9.yml.

  python tools/gumroad_launch9.py [--dry-run]

Finds the LOOK UP product and its offer code COSMOS9 with the Gumroad API (token in secrets/gumroad.json,
"access_token") and deletes the code, only from 30/11/2026 23:30 Italian time onwards. Before that, or with
--dry-run, it only prints what it would do. If the code is already gone it says so and exits 0.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.gumroad.com/v2"
CODE, PERMALINK = "COSMOS9", "look-up"
NOT_BEFORE = datetime(2026, 11, 30, 23, 30, tzinfo=ZoneInfo("Europe/Rome"))


def main():
    dry = "--dry-run" in sys.argv
    f = ROOT / "secrets" / "gumroad.json"
    if not f.exists():
        sys.exit("Missing GUMROAD_JSON secret (secrets/gumroad.json with access_token).")
    tok = {"access_token": json.loads(f.read_text("utf-8"))["access_token"]}
    prods = requests.get(f"{API}/products", params=tok, timeout=60).json().get("products", [])
    p = next((x for x in prods if x.get("custom_permalink") == PERMALINK or "look-up" in (x.get("short_url") or "")
              or x.get("name", "").upper().startswith("LOOK UP")), None)
    if not p:
        sys.exit("LOOK UP not found among the Gumroad products.")
    codes = requests.get(f"{API}/products/{p['id']}/offer_codes", params=tok, timeout=60).json().get("offer_codes", [])
    c = next((x for x in codes if x.get("name", "").upper() == CODE), None)
    if not c:
        print(f"{CODE} not found on {p['name']}: nothing to do (already removed).")
        return
    print(f"{CODE} on {p['name']}: used {c.get('times_used', '?')} times.")
    if dry or datetime.now(ZoneInfo("Europe/Rome")) < NOT_BEFORE:
        print(f"DRY-RUN / too early: would delete {CODE} (not before {NOT_BEFORE:%d/%m/%Y %H:%M}).")
        return
    r = requests.delete(f"{API}/products/{p['id']}/offer_codes/{c['id']}", params=tok, timeout=60).json()
    if not r.get("success"):
        sys.exit(f"Gumroad refused the delete: {r.get('message', r)}")
    print(f"{CODE} deleted: the price of LOOK UP is back to the full price.")


if __name__ == "__main__":
    main()
