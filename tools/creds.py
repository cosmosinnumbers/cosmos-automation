"""Paths, credentials and small helpers shared by the publishing tools.

Credentials: environment variable <NAME>_JSON (GitHub Actions secret) if set, otherwise
<COSMOS_SECRETS>/<name>.json on the owner's PC (default ../Progetto-YouTube-Faceless/secrets).
Values are never printed. Refreshed tokens go back where they came from: the GitHub secret
(via `gh secret set`, needs GH_SECRETS_TOKEN) or the local file.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

REPO = Path(__file__).resolve().parents[1]
LOGS = REPO / "logs"
QUEUES = REPO / "queues"
LOCAL_SECRETS = Path(os.environ.get("COSMOS_SECRETS", REPO.parent / "Progetto-YouTube-Faceless" / "secrets"))
TZ = ZoneInfo("Europe/Rome")  # every "at" in the queues is Italian local time "YYYY-MM-DD HH:MM"


def mask(data) -> None:
    """Hide every credential value in the Actions log (the repo is public since 07/11/2026, and so are its run logs).
    GitHub masks a secret only as the whole string: the single values inside a JSON secret and refreshed tokens
    would otherwise show in clear if an error message ever printed them."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    vals = data.values() if isinstance(data, dict) else data if isinstance(data, list) else [data]
    for v in vals:
        if isinstance(v, (dict, list)):
            mask(v)
        elif isinstance(v, str) and len(v) >= 8 and "\n" not in v:
            print(f"::add-mask::{v}", flush=True)


def load(name: str) -> dict:
    env = os.environ.get(f"{name.upper()}_JSON")
    if env:
        data = json.loads(env)
        mask(data)
        return data
    if name == "tiktok" and os.environ.get("TIKTOK_CLIENT_KEY"):  # first setup: two plain secrets, no JSON to type
        return {"client_key": os.environ["TIKTOK_CLIENT_KEY"].strip(),
                "client_secret": os.environ.get("TIKTOK_CLIENT_SECRET", "").strip(),
                "redirect_uri": (os.environ.get("TIKTOK_REDIRECT_URI") or "https://cosmosinnumbers.github.io/tiktok-callback.html").strip()}
    p = LOCAL_SECRETS / f"{name}.json"
    if not p.exists():
        sys.exit(f"Missing credentials: secret {name.upper()}_JSON or file {p}")
    return json.loads(p.read_text("utf-8"))


def save(name: str, data: dict):
    var = f"{name.upper()}_JSON"
    mask(data)
    if os.environ.get(var) or os.environ.get("GITHUB_ACTIONS"):  # in Actions the secret is created if missing
        tok, repo = os.environ.get("GH_SECRETS_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
        if not (tok and repo):
            sys.exit(f"Refreshed {name} token could not be saved: GH_SECRETS_TOKEN not configured.")
        r = subprocess.run(["gh", "secret", "set", var, "--repo", repo], input=json.dumps(data), text=True,
                           capture_output=True, env={**os.environ, "GH_TOKEN": tok})
        if r.returncode:
            sys.exit(f"Could not update secret {var} (gh exit code {r.returncode}).")
        os.environ[var] = json.dumps(data)
        print(f"secret {var} updated")
    else:
        (LOCAL_SECRETS / f"{name}.json").write_text(json.dumps(data, indent=2), "utf-8")


def now_local() -> datetime:
    return datetime.now(TZ)


def day(ts: int) -> str:
    """Italian calendar day of a unix time (daily post caps count per day, not per rolling 24h)."""
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d")


def stamp(at: str) -> int:
    """'YYYY-MM-DD HH:MM' Italian time -> unix seconds."""
    return int(datetime.strptime(at, "%Y-%m-%d %H:%M").replace(tzinfo=TZ).timestamp())


def check_url(url: str):
    """Refuse media that is not reachable: a file of the repo must exist, a URL must answer HTTP 200."""
    if not url.startswith("http"):
        if not Path(url).is_file():
            sys.exit(f"Media file not in the repo: {url}")
        return
    r = requests.head(url, allow_redirects=True, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Media not reachable (HTTP {r.status_code}): {url}")


def local_media(src: str) -> str:
    """Path for an uploader: a local file as is, a URL downloaded to a temp file (after a 200 check)."""
    if not src.startswith("http"):
        return src
    r = requests.get(src, timeout=300)
    if r.status_code != 200:
        sys.exit(f"Media not reachable (HTTP {r.status_code}): {src}")
    out = Path(tempfile.gettempdir()) / Path(src.split("?")[0]).name
    out.write_bytes(r.content)
    return str(out)


def events(log: str) -> list[dict]:
    p = LOGS / log
    return [json.loads(l) for l in p.read_text("utf-8").splitlines() if l.strip()] if p.exists() else []


def append(log: str, entry: dict):
    LOGS.mkdir(exist_ok=True)
    with (LOGS / log).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
