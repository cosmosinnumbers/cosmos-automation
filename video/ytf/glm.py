"""GLM (Z.ai / Zhipu) as a writer, reviewer and scene director: an OpenAI-compatible chat endpoint.

Secrets (repo, never in chat): GLM_API_KEY. Optional variables/secrets:
  GLM_BASE_URL  default https://api.z.ai/api/paas/v4   (Coding Plan keys: https://api.z.ai/api/coding/paas/v4)
  GLM_MODELS    comma list, first is tried first; default: the newest glm-5.x text models of the key's /models list
                (glm-5.3 on 02/11/2026), then glm-5.3 / glm-5.2 as hard-coded fallbacks.
chat() returns (raw text, parsed JSON) or None, never raises: callers fall back to the next provider (Gemini, Groq).
Every JSON answer goes through the caller's `check` before it is used, like any other writer's.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

BASE = "https://api.z.ai/api/paas/v4"
FALLBACK_MODELS = "glm-5.3,glm-5.2"


def available() -> bool:
    return bool(os.environ.get("GLM_API_KEY"))


def _base() -> str:
    return (os.environ.get("GLM_BASE_URL") or BASE).rstrip("/")


def models(key: str) -> list[str]:
    """GLM_MODELS if set, else the key's own /models list (newest glm-5.x text models first), else the fallbacks."""
    env = [m.strip() for m in os.environ.get("GLM_MODELS", "").split(",") if m.strip()]
    if env:
        return env
    ids: list[str] = []
    try:
        r = requests.get(f"{_base()}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
        ids = [m["id"] for m in r.json().get("data", [])]
    except Exception as e:  # noqa: BLE001
        print(f"  GLM model list failed ({type(e).__name__}): using the defaults", flush=True)
    good = [i for i in ids if re.fullmatch(r"glm-5(\.\d+)?(-flash)?", i)]   # text models only: no -v, -air, -image, -voice

    def rank(i: str):
        v = [int(x) for x in re.findall(r"\d+", i)] or [0]
        return (v, "flash" not in i)

    good.sort(key=rank, reverse=True)
    out = good[:3] or FALLBACK_MODELS.split(",")
    print("  GLM models:", ", ".join(out), flush=True)
    return out


def chat(messages: list[dict], *, check=None, temperature: float = 0.4, max_tokens: int = 8000,
         thinking: bool = False, timeout: int = 180):
    """messages: the Gemini-style list used everywhere in this repo ([{role: user|model, parts: [{text}]}]).
    check(json) -> list[str] of problems; an answer with problems goes to the next model. `thinking` turns on GLM's
    reasoning mode (slower, better for fact checking and code-like output)."""
    key = os.environ.get("GLM_API_KEY")
    if not key:
        return None
    chat_msgs = [{"role": "assistant" if m["role"] == "model" else "user",
                  "content": "".join(p.get("text", "") for p in m["parts"])} for m in messages]
    for model in models(key)[:3]:
        body = {"model": model, "messages": chat_msgs, "temperature": temperature, "max_tokens": max_tokens,
                "response_format": {"type": "json_object"}, "thinking": {"type": "enabled" if thinking else "disabled"}}
        for attempt in range(2):
            try:
                r = requests.post(f"{_base()}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                                  json=body, timeout=timeout)
            except requests.RequestException as e:
                print(f"  GLM {model}: {type(e).__name__}", flush=True)
                break
            if r.status_code == 400 and "thinking" in body:     # an older endpoint that does not know the field
                body.pop("thinking")
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                print(f"  GLM {model} HTTP {r.status_code}: retrying", flush=True)
                time.sleep(8)
                continue
            if r.status_code != 200:
                print(f"  GLM {model} HTTP {r.status_code}: {r.text[:200]}", flush=True)
                break
            try:
                text = r.json()["choices"][0]["message"]["content"] or ""
                data = json.loads(text[text.index("{"): text.rindex("}") + 1])
            except (ValueError, KeyError, IndexError, TypeError) as e:
                print(f"  GLM {model}: unusable answer ({type(e).__name__})", flush=True)
                break
            problems = check(data) if check else []
            if problems:
                print(f"  GLM {model}: answer rejected ({'; '.join(problems)[:200]})", flush=True)
                break
            print(f"  written by GLM {model}", flush=True)
            return text, data
    return None
