"""GitHub Actions only: write the repository secrets into secrets/ so the PC tools run unchanged.

  python tools/ci_secrets.py

Env (GitHub secrets) -> file: META_JSON -> meta.json, THREADS_JSON -> threads.json, YOUTUBE_TOKEN_JSON -> token.json,
YOUTUBE_ANALYTICS_TOKEN_JSON -> token_analytics.json, GUMROAD_JSON -> gumroad.json, PEXELS_KEY / PIXABAY_KEY /
UNSPLASH_KEY -> <name>_key.txt, GEMINI_API_KEY -> gemini.json. Missing ones are skipped (the tool that needs them says
so). Nothing is printed except the file names. secrets/ is in .gitignore: never committed.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "secrets"
S.mkdir(exist_ok=True)
MAP = {"META_JSON": "meta.json", "THREADS_JSON": "threads.json", "YOUTUBE_TOKEN_JSON": "token.json",
       "YOUTUBE_ANALYTICS_TOKEN_JSON": "token_analytics.json", "GUMROAD_JSON": "gumroad.json",
       "PEXELS_KEY": "pexels_key.txt", "PIXABAY_KEY": "pixabay_key.txt", "UNSPLASH_KEY": "unsplash_key.txt"}
written = []
for var, name in MAP.items():
    v = os.environ.get(var, "").strip()
    if v:
        (S / name).write_text(v, "utf-8")
        written.append(name)
if os.environ.get("GEMINI_API_KEY"):
    (S / "gemini.json").write_text(json.dumps({"api_key": os.environ["GEMINI_API_KEY"].strip(),
                                               "model": os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")}), "utf-8")
    written.append("gemini.json")
print("secrets written:", ", ".join(written) or "none")
