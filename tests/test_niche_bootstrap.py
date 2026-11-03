import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import copy_secrets as cs  # noqa: E402
import niche_bootstrap as nb  # noqa: E402


def test_wanted_excludes_cosmos_data():
    assert not nb.wanted("logs/youtube.jsonl", "stickman")
    assert not nb.wanted("media/p4/a.mp4", "stickman")
    assert not nb.wanted("research/cosmos/2026-W45.json", "stickman")
    assert nb.wanted("research/niches/stickman.json", "stickman")
    assert nb.wanted("research/stickman/scan-2026-11-03.md", "stickman")
    assert nb.wanted("tools/experiments.py", "stickman")
    assert not nb.wanted(".github/workflows/niche-bootstrap.yml", "stickman")


def test_disable_schedule_keeps_dispatch():
    wf = 'name: x\n\non:\n  schedule:\n    - cron: "0 6 * * *"\n    - cron: "0 7 * * *"\n  workflow_dispatch:\n\njobs:\n  a: {}\n'
    out, changed = nb.disable_schedule(wf)
    assert changed and "  # schedule:" in out and '  #  - cron: "0 6 * * *"' in out and "  workflow_dispatch:" in out
    import yaml
    d = yaml.safe_load(out)
    assert "schedule" not in d[True] and "workflow_dispatch" in d[True]


def test_disable_schedule_adds_dispatch_when_alone():
    out, _ = nb.disable_schedule('name: x\non:\n  schedule:\n    - cron: "0 6 * * *"\njobs:\n  a: {}\n')
    assert "workflow_dispatch" in out


def test_copy_secrets_only_oauth_client(monkeypatch):
    for n in cs.SHARED:
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("GROK_API_KEY", "k")
    monkeypatch.setenv("YOUTUBE_TOKEN_JSON", '{"client_id": "a", "client_secret": "b", "refresh_token": "SECRET"}')
    v = cs.values()
    assert v["GROK_API_KEY"] == "k"
    assert "refresh_token" not in v["YOUTUBE_CLIENT_JSON"] and '"client_id": "a"' in v["YOUTUBE_CLIENT_JSON"]
    assert "YOUTUBE_TOKEN_JSON" not in v
