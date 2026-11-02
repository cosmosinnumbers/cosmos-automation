"""Claude as a writer and reviewer through the Claude Code CLI, using the owner's subscription (or an API key).

Secrets (repo, never in chat): CLAUDE_CODE_OAUTH_TOKEN (made on the owner's PC with `claude setup-token`, tied to the
Pro/Max subscription and counted against its limits) or ANTHROPIC_API_KEY. Optional: CLAUDE_MODEL (default "sonnet").
The CLI is installed on first use under ~/.claude-cli (npm, no sudo), so the workflows need no extra step.
chat() has the same shape as glm.chat(): (raw text, parsed JSON) or None, never raises, the caller's `check` validates
the JSON, and every failure falls through to the next provider (Gemini, Groq, GLM).
Repo variable LLM_FIRST=claude puts it ahead of Gemini for the writing without search.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

PREFIX = Path.home() / ".claude-cli"
_BIN: list[str | None] = []


def configured() -> bool:
    return bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"))


def _binary() -> str | None:
    if _BIN:
        return _BIN[0]
    found = shutil.which("claude") or (str(PREFIX / "node_modules" / ".bin" / "claude")
                                       if (PREFIX / "node_modules" / ".bin" / "claude").exists() else None)
    if not found and shutil.which("npm"):
        print("  Claude CLI: installing @anthropic-ai/claude-code", flush=True)
        try:
            subprocess.run(["npm", "install", "--prefix", str(PREFIX), "--no-audit", "--no-fund", "--silent",
                            "@anthropic-ai/claude-code"], check=True, capture_output=True, timeout=240)
            p = PREFIX / "node_modules" / ".bin" / "claude"
            found = str(p) if p.exists() else None
        except Exception as e:  # noqa: BLE001
            print(f"  Claude CLI install failed ({type(e).__name__})", flush=True)
    _BIN.append(found)
    return found


def available() -> bool:
    return configured() and bool(_binary())


def chat(messages: list[dict], *, check=None, temperature: float = 0.4, max_tokens: int = 8000,
         thinking: bool = False, timeout: int = 300):
    """messages: the Gemini-style list used in this repo ([{role, parts: [{text}]}]). temperature and max_tokens exist
    for the same signature as glm.chat and are not used by the CLI."""
    if not configured():
        return None
    exe = _binary()
    if not exe:
        return None
    prompt = "\n\n".join("".join(p.get("text", "") for p in m["parts"]) for m in messages)
    prompt += "\n\nAnswer with a single JSON object and nothing else: no markdown fence, no comment."
    model = os.environ.get("CLAUDE_MODEL") or "sonnet"
    for attempt in range(2):
        try:
            r = subprocess.run([exe, "-p", "--model", model, "--output-format", "text"], input=prompt, text=True,
                               capture_output=True, timeout=timeout, env=os.environ.copy())
        except Exception as e:  # noqa: BLE001
            print(f"  Claude CLI {model}: {type(e).__name__}", flush=True)
            return None
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip().replace("\n", " ")[:200]
            print(f"  Claude CLI {model} exit {r.returncode}: {err}", flush=True)
            if attempt == 0 and ("overloaded" in err.lower() or "rate" in err.lower() or "529" in err):
                continue
            return None
        text = r.stdout or ""
        try:
            data = json.loads(text[text.index("{"): text.rindex("}") + 1])
        except ValueError:
            print(f"  Claude CLI {model}: unusable answer", flush=True)
            return None
        problems = check(data) if check else []
        if problems:
            print(f"  Claude CLI {model}: answer rejected ({'; '.join(problems)[:200]})", flush=True)
            return None
        print(f"  written by Claude ({model})", flush=True)
        return text, data
    return None
