"""Recreate the LOOK UP offer code COSMOS9 with a new fixed discount, run by gumroad-offer.yml (manual only).

  python tools/gumroad_offer.py --off-cents 500 [--dry-run]

Gumroad cannot edit the amount of an existing offer code, so the script deletes COSMOS9 and creates it again with the
new amount (fixed, in cents). The API cannot set an expiry: launch9.yml still deletes COSMOS9 on 30/11/2026 23:30.
Refuses to act if the old code was already used (to keep its history) unless --force.
"""
import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.gumroad.com/v2"
CODE, PERMALINK = "COSMOS9", "look-up"


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--off-cents", type=int, required=True)
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--force", action="store_true")
    o = a.parse_args()
    tok = {"access_token": json.loads((ROOT / "secrets" / "gumroad.json").read_text("utf-8"))["access_token"]}
    prods = requests.get(f"{API}/products", params=tok, timeout=60).json().get("products", [])
    p = next((x for x in prods if x.get("custom_permalink") == PERMALINK), None) or sys.exit("LOOK UP not found.")
    if not 0 < o.off_cents < p["price"]:
        sys.exit(f"--off-cents must be between 1 and {p['price'] - 1}")
    codes = requests.get(f"{API}/products/{p['id']}/offer_codes", params=tok, timeout=60).json().get("offer_codes", [])
    old = next((c for c in codes if c.get("name", "").upper() == CODE), None)
    print(f"LOOK UP ${p['price'] / 100:.2f}; {CODE} now: " + (f"{old.get('amount_cents')} cents off, used {old.get('times_used')}" if old else "missing"))
    print(f"target: {o.off_cents} cents off -> price ${(p['price'] - o.off_cents) / 100:.2f}")
    if old and old.get("amount_cents") == o.off_cents:
        print("already right: nothing to do")
        return
    if old and old.get("times_used") and not o.force:
        sys.exit("COSMOS9 was already used: rerun with --force to replace it")
    if o.dry_run:
        print("DRY-RUN: no change")
        return
    if old:
        r = requests.delete(f"{API}/products/{p['id']}/offer_codes/{old['id']}", params=tok, timeout=60).json()
        r.get("success") or sys.exit(f"delete refused: {r.get('message', r)}")
    r = requests.post(f"{API}/products/{p['id']}/offer_codes", data={**tok, "name": CODE, "amount_off": o.off_cents,
                                                                      "offer_type": "cents"}, timeout=60).json()
    r.get("success") or sys.exit(f"create refused: {r.get('message', r)}")
    print(f"{CODE} recreated: {r['offer_code'].get('amount_cents')} cents off")


if __name__ == "__main__":
    main()
