"""claude_cli.chat with a simulated CLI: JSON parsing, check() rejection, no secret = no call, failures fall through."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import claude_cli as c  # noqa: E402

c._BIN[:] = ["/fake/claude"]
calls = []


def fake(out="", code=0, err=""):
    def run(cmd, **kw):
        calls.append((cmd, kw.get("input", "")))
        return subprocess.CompletedProcess(cmd, code, out, err)
    return run


msgs = [{"role": "user", "parts": [{"text": "hello"}]}]
os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
assert c.chat(msgs) is None and not calls, "without a secret nothing is called"

os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "x"
c.subprocess.run = fake('Sure:\n{"ok": true}')
t, j = c.chat(msgs)
assert j == {"ok": True} and calls[-1][0][:2] == ["/fake/claude", "-p"] and "hello" in calls[-1][1]
assert c.chat(msgs, check=lambda d: ["bad"]) is None, "a rejected answer falls through"
c.subprocess.run = fake("no json here")
assert c.chat(msgs) is None
c.subprocess.run = fake("", 1, "auth error")
assert c.chat(msgs) is None
print("claude_cli: ok")
