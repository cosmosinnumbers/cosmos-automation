"""Copy the SHARED secrets of this repo into a new niche repo (owner 03/11/2026), inside GitHub Actions only.

  python tools/copy_secrets.py <owner/repo>      env: the secrets to copy + COPY_TOKEN (needs "Secrets: write" on target)

Values come from the workflow env (GitHub never returns secret values through the API) and go straight to
`gh secret set` on stdin: never printed, never written to disk. Channel-specific secrets (Meta, Threads, TikTok, X,
YouTube channel token, Gumroad, Pages) are NOT copied: the new channel gets its own. From YOUTUBE_TOKEN_JSON only the
OAuth client (client_id, client_secret, token_uri) is copied as YOUTUBE_CLIENT_JSON, without Cosmos' refresh token, so
the new channel can be authorised from the cloud. Writes a names-only report to reports/bootstrap-<repo>.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ["GEMINI_API_KEY", "GROK_API_KEY", "GLM_API_KEY", "GLM_BASE_URL", "GLM_MODELS", "BACKUP_LLM_URL",
          "BACKUP_LLM_MODELS", "BACKUP_LLM_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "YOUTUBE_API_KEY",
          "FREESOUND_API_KEY", "OPENVERSE_CLIENT_ID", "OPENVERSE_CLIENT_SECRET", "REDDIT_JSON", "NASA_API_KEY",
          "GH_SECRETS_TOKEN"]


def values() -> dict[str, str]:
    out = {n: os.environ[n] for n in SHARED if os.environ.get(n, "").strip()}
    raw = os.environ.get("YOUTUBE_TOKEN_JSON", "")
    if raw.strip():
        try:
            t = json.loads(raw)
            client = {k: t[k] for k in ("client_id", "client_secret") if t.get(k)}
            if len(client) == 2:
                client["token_uri"] = t.get("token_uri", "https://oauth2.googleapis.com/token")
                out["YOUTUBE_CLIENT_JSON"] = json.dumps(client)
        except ValueError:
            pass
    return out


def main(target: str) -> int:
    tok = os.environ.get("COPY_TOKEN", "").strip()
    if not tok:
        sys.exit("COPY_TOKEN missing: set BOOTSTRAP_TOKEN (or extend GH_SECRETS_TOKEN to the new repo).")
    env = {**os.environ, "GH_TOKEN": tok}
    ok, failed = [], []
    vals = values()
    for name, val in vals.items():
        r = subprocess.run(["gh", "secret", "set", name, "--repo", target], input=val, text=True,
                           capture_output=True, env=env)
        (ok if r.returncode == 0 else failed).append(name)
        if r.returncode:  # gh never echoes the value; keep only the first line of the error
            print(f"{name}: failed ({(r.stderr or '').strip().splitlines()[:1]})")
    missing = [n for n in SHARED if n not in vals]
    rep = ROOT / "reports" / f"bootstrap-{target.split('/')[-1]}.md"
    rep.parent.mkdir(exist_ok=True)
    rep.write_text(f"# Segreti copiati in {target} ({time.strftime('%d/%m/%Y %H:%M')})\n\n"
                   f"- Copiati ({len(ok)}): {', '.join(ok) or 'nessuno'}\n"
                   f"- Falliti ({len(failed)}): {', '.join(failed) or 'nessuno'}\n"
                   f"- Non presenti in cosmos-automation: {', '.join(missing) or 'nessuno'}\n"
                   "- Mai copiati (servono quelli del nuovo canale): META_JSON, THREADS_JSON, TIKTOK_*, X_JSON, "
                   "YOUTUBE_TOKEN_JSON, YOUTUBE_ANALYTICS_TOKEN_JSON, GUMROAD_JSON, PAGES_TOKEN\n", "utf-8")
    print(f"copied {len(ok)}, failed {len(failed)}, missing {len(missing)}")
    return 1 if failed or not ok else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
