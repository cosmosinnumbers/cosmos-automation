"""Self-heal of the GitHub Actions workflows (owner request 02/11/2026: "voglio che ripartano in automatico e che si
autofixino"). Run by .github/workflows/self-heal.yml when a listed workflow fails; config in config/self-heal.json.

  python tools/self_heal.py retry     re-run the failed jobs up to N times with backoff, waiting for each attempt
  python tools/self_heal.py diagnose  read the failed log, ask an LLM (Gemini, Groq, GLM, GitHub Models) for a
                                      diagnosis and a minimal code fix, apply it only if it compiles and the tests
                                      do not get worse
  python tools/self_heal.py finish    take the working-tree fix (from diagnose or from Claude), check it again,
                                      open a PR and merge it only if it is safe; re-run the failed run to verify it;
                                      open an issue for the owner only when the run could not be repaired

Environment: GH_TOKEN, GITHUB_REPOSITORY, RUN_ID, WF_NAME (+ the LLM keys); work files in .autofix/ (git-ignored). Never prints a key.
Safe for publishing: re-runs check out the tip of main (publishers read their logs there and skip what is already
out, so a re-run never publishes twice), and an automatic merge never touches publishers, tokens, queues, logs,
deletions or workflow files (config "risky_paths" / "risky_words"): those fixes stay in an open PR for the owner.
"""
from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config" / "self-heal.json").read_text("utf-8"))
REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
API = f"https://api.github.com/repos/{REPO}"
RUN_ID = os.environ.get("RUN_ID", "")
WF = os.environ.get("WF_NAME", "")
TMP = ROOT / ".autofix"  # git-ignored: context for Claude, state between the steps
STATE = TMP / "state.json"
LOG = ROOT / "logs" / "autofix-log.jsonl"
OWNER = os.environ.get("AUTOFIX_ASSIGNEE", "Redwraith")
BOT = ("cosmos-automation[bot]", "cosmos-automation@users.noreply.github.com")
RUN_URL = f"https://github.com/{REPO}/actions/runs/{RUN_ID}"


# ---------------------------------------------------------------- GitHub helpers
def gh_api(method, path, **kw):
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    r = requests.request(method, path if path.startswith("http") else API + path, headers=h, timeout=60, **kw)
    return r


def output(**kv):
    out = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if out:
            with open(out, "a", encoding="utf-8") as f:
                f.write(f"{k}={v}\n")


def sh(*cmd, check=True, **kw):
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, capture_output=True, **kw)


def wf_cfg():
    return CFG["workflows"].get(WF, {"retries": 0, "autofix": False})


def run_info():
    return gh_api("GET", f"/actions/runs/{RUN_ID}").json()


def wait_run(attempt: int, max_s: int = 100 * 60) -> str:
    """Wait for attempt number `attempt` of the run to complete; its conclusion ('' on timeout)."""
    t0 = time.time()
    while time.time() - t0 < max_s:
        time.sleep(30)
        r = run_info()
        if r.get("run_attempt", 0) >= attempt and r.get("status") == "completed":
            return r.get("conclusion") or ""
    return ""


def rerun_and_wait() -> str:
    before = run_info().get("run_attempt", 1)
    r = gh_api("POST", f"/actions/runs/{RUN_ID}/rerun-failed-jobs")
    if r.status_code >= 300:
        print(f"re-run refused: HTTP {r.status_code} {r.text[:200]}")
        return ""
    print(f"re-run started (attempt {before + 1}), waiting for it", flush=True)
    return wait_run(before + 1)


# ---------------------------------------------------------------- 1. retry
def after_recovery():
    """Start again the workflows that a recovered run would have chained (a re-run made with the Actions token may
    not fire their workflow_run trigger). They are idempotent: what is already queued or out is left alone."""
    for wf_file, inputs in wf_cfg().get("after_recovery", []):
        r = gh_api("POST", f"/actions/workflows/{wf_file}/dispatches", json={"ref": "main", "inputs": inputs})
        print(f"started {wf_file}: HTTP {r.status_code}")


def known_failure(log: str) -> dict | None:
    """The first entry of config "known" whose pattern is in the failed log (owner 04/11/2026: known failures are
    repaired with fixed steps and their own waits, not by the LLM autofix and its 20 h limit)."""
    for k in CFG.get("known", []):
        if re.search(k["pattern"], log, re.I | re.M):
            return k
    return None


def dispatch_and_wait(wf_file: str, inputs: dict, max_s: int = 60 * 60) -> str:
    """Start a workflow (not one of self-heal's: no loop) and wait for its run; its conclusion ('' if unknown)."""
    t0 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = gh_api("POST", f"/actions/workflows/{wf_file}/dispatches", json={"ref": "main", "inputs": inputs})
    print(f"started {wf_file}: HTTP {r.status_code}", flush=True)
    if r.status_code >= 300:
        return ""
    start = time.time()
    while time.time() - start < max_s:
        time.sleep(30)
        runs = gh_api("GET", f"/actions/workflows/{wf_file}/runs",
                      params={"event": "workflow_dispatch", "created": f">={t0}", "per_page": 5}).json()
        done = [x for x in runs.get("workflow_runs", []) if x.get("status") == "completed"]
        if done:
            return done[0].get("conclusion") or ""
    return ""


def heal_known(k: dict) -> bool:
    """Fixed repair of a known failure: the steps in "before" (e.g. make the missing clip), then re-runs after the
    waits of "waits_s". True when a re-run succeeds."""
    waits = k.get("waits_s", [])
    for i, wait in enumerate(waits):
        print(f"{WF}: known failure '{k['kind']}' ({k['label']}): repair {i + 1}/{len(waits)} in {wait} s", flush=True)
        time.sleep(wait)
        for wf_file, inputs in k.get("before", []):
            print(f"  before the re-run: {wf_file} -> {dispatch_and_wait(wf_file, inputs) or 'no result'}", flush=True)
        concl = rerun_and_wait()
        print(f"{WF}: repair {i + 1} -> {concl or 'no result'}", flush=True)
        if concl == "success":
            return True
    return False


def cmd_retry():
    retries = int(wf_cfg().get("retries", 0))
    backoff = CFG.get("backoff_s", [120, 360])
    for i in range(retries):
        wait = backoff[min(i, len(backoff) - 1)]
        print(f"{WF}: failed; new attempt {i + 1}/{retries} in {wait} s", flush=True)
        time.sleep(wait)
        concl = rerun_and_wait()
        print(f"{WF}: attempt {i + 1} -> {concl or 'no result'}", flush=True)
        if concl == "success":
            after_recovery()
            output(result="recovered")
            return
    k = known_failure(failed_logs()[1]) if retries else None
    if k:
        TMP.mkdir(parents=True, exist_ok=True)
        save_state(known=k["kind"])
        if heal_known(k):
            after_recovery()
            output(result="recovered")
            return
    output(result="failed")


# ---------------------------------------------------------------- 2. diagnose
def recent_autofixes():
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text("utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def over_limit() -> str:
    now = time.time()
    a = CFG["autofix"]
    ev = recent_autofixes()
    same = [e for e in ev if e.get("wf") == WF and now - e.get("at", 0) < a["max_per_workflow_hours"] * 3600]
    if same:
        return f"un autofix per {WF} è già stato tentato nelle ultime {a['max_per_workflow_hours']} ore"
    if len([e for e in ev if now - e.get("at", 0) < 86400]) >= a["max_per_day"]:
        return f"limite di {a['max_per_day']} autofix al giorno raggiunto"
    return ""


def failed_logs() -> tuple[str, str]:
    """(job/step names, cleaned tail of the failed jobs' logs)."""
    jobs = gh_api("GET", f"/actions/runs/{RUN_ID}/jobs", params={"filter": "latest"}).json().get("jobs", [])
    names, text = [], []
    for j in jobs:
        if j.get("conclusion") != "failure":
            continue
        steps = [s["name"] for s in j.get("steps", []) if s.get("conclusion") == "failure"]
        names.append(f"job '{j['name']}', step {', '.join(steps) or '?'}")
        r = gh_api("GET", f"/actions/jobs/{j['id']}/logs")
        raw = r.text if r.status_code == 200 else f"(log not available: HTTP {r.status_code})"
        lines = [re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ", "", ln) for ln in raw.splitlines()]
        lines = [ln for ln in lines if ln.strip() and not ln.startswith(("##[group]", "##[endgroup]"))]
        text.append(f"===== job {j['name']} =====\n" + "\n".join(lines[-220:]))
    return "; ".join(names), "\n".join(text)[-24000:]


def related_files(log: str, wf_text: str) -> list[tuple[str, list[int]]]:
    """Repo files named in the traceback (with line numbers) first, then scripts the workflow runs."""
    found: dict[str, list[int]] = {}
    for m in re.finditer(r'File "[^"]*?/((?:tools|video|motion|tests|config)/[^"]+)", line (\d+)', log):
        found.setdefault(m.group(1), []).append(int(m.group(2)))
    for m in re.finditer(r"\b((?:tools|video|motion|tests|config|queues)/[\w./-]+\.(?:py|json|ts|tsx|js|yml|yaml))",
                         log + "\n" + wf_text):
        found.setdefault(m.group(1), [])
    return [(p, ln) for p, ln in found.items() if (ROOT / p).is_file()][:8]


def excerpt(path: str, lines: list[int], budget: int) -> str:
    text = (ROOT / path).read_text("utf-8", errors="replace")
    if len(text) <= budget:
        return text
    src = text.splitlines()
    keep = set()
    for n in lines[-4:] or [1]:
        keep.update(range(max(0, n - 60), min(len(src), n + 40)))
    out, last = [], -2
    for i in sorted(keep):
        if i != last + 1:
            out.append(f"... (line {i + 1})")
        out.append(src[i])
        last = i
    return "\n".join(out)[:budget]


def build_context(budget: int) -> str:
    st = json.loads(STATE.read_text("utf-8"))
    wf_path = st["wf_path"]
    wf_text = (ROOT / wf_path).read_text("utf-8") if wf_path and (ROOT / wf_path).exists() else ""
    parts = [f"WORKFLOW {WF} ({wf_path}) failed: {st['where']}\nRun: {RUN_URL}\n",
             f"----- FAILED LOG (tail) -----\n{st['log'][-min(len(st['log']), budget // 3):]}\n",
             f"----- {wf_path} -----\n{wf_text[:6000]}\n"]
    left = budget - sum(len(p) for p in parts)
    for path, lines in related_files(st["log"], wf_text):
        if left < 1500:
            break
        ex = excerpt(path, lines, min(left - 200, 40000))
        parts.append(f"----- {path} -----\n{ex}\n")
        left -= len(ex) + 40
    return "\n".join(parts)


PROMPT = """You repair a failed GitHub Actions run of a content-automation repo (Python tools for a YouTube/Threads/
Instagram channel "Cosmos in Numbers"). Read the failed log and the files, find the root cause and propose the
SMALLEST code change that fixes it.

Rules:
- kind: "code" only if a change to the repository files below fixes it. Use "transient" (HTTP 429/5xx, timeouts,
  network, busy model), "credentials" (401/403, expired or missing token/secret), "quota", "external" (an API changed
  or is down, nothing to change here) or "config" (a repository variable/secret must be set by the owner).
- Never edit files under .github/ (they cannot be pushed from Actions), never add secrets, never delete content,
  never disable a check or a test, never remove the idempotency checks (logs) of the publishers.
- Each edit: "old" is text copied EXACTLY from the file (whitespace included) that occurs ONCE in it; "new" replaces
  it. Keep edits few and short.
- "diagnosis": 1-3 sentences IN ITALIAN for the owner (what broke and why); "todo": IN ITALIAN, what the owner must do
  if it cannot be fixed in code (empty otherwise).
Answer with JSON only:
{"kind": "code|transient|credentials|quota|external|config", "diagnosis": "", "todo": "",
 "edits": [{"path": "tools/x.py", "old": "", "new": ""}], "confidence": 0.0}
"""


def gemini(prompt: str):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    models = [m for m in os.environ.get("AUTOFIX_GEMINI_MODELS", "").split(",") if m]
    if not models:
        try:
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                             params={"key": key, "pageSize": 200}, timeout=30)
            names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", [])]
        except Exception as e:  # noqa: BLE001
            print("  Gemini model list failed:", type(e).__name__)
            names = []
        names = [n for n in names if re.search(r"pro|flash", n) and not re.search(
            r"image|tts|audio|live|embed|lite|exp|vision", n)]
        ver = lambda n: [float(x) for x in re.findall(r"\d+(?:\.\d+)?", n)[:1]] or [0.0]  # noqa: E731
        names.sort(key=lambda n: (ver(n), "pro" in n, "preview" not in n), reverse=True)
        models = names[:4] or ["gemini-2.5-pro", "gemini-2.5-flash"]
    for i, m in enumerate(models * 2):
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                              params={"key": key}, timeout=180,
                              json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                    "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}})
        except requests.RequestException as e:
            print(f"  Gemini {m}: {type(e).__name__}")
            continue
        if r.status_code == 200:
            try:
                return f"gemini:{m}", "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError, ValueError):
                continue
        print(f"  Gemini {m} HTTP {r.status_code}")
        if r.status_code in (429, 500, 503):
            time.sleep(10 + 10 * i)
    return None


def openai_compat(name, base, key, models, prompt):
    if not key:
        return None
    if not models:
        try:
            r = requests.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
            ids = [m["id"] for m in r.json().get("data", [])
                   if not re.search(r"whisper|tts|guard|vision|image|embed|audio|speech|prompt|compound", m["id"])]
            size = lambda i: max([float(x) for x in re.findall(r"(\d+(?:\.\d+)?)b\b", i)] or [0])  # noqa: E731
            ids.sort(key=lambda i: ("versatile" in i or "coder" in i, size(i)), reverse=True)
            models = ids[:3]
        except Exception as e:  # noqa: BLE001
            print(f"  {name}: model list failed ({type(e).__name__})")
    for m in models:
        try:
            r = requests.post(f"{base}/chat/completions", timeout=180, headers={"Authorization": f"Bearer {key}"},
                              json={"model": m, "temperature": 0.1, "response_format": {"type": "json_object"},
                                    "messages": [{"role": "user", "content": prompt}]})
        except requests.RequestException as e:
            print(f"  {name} {m}: {type(e).__name__}")
            continue
        if r.status_code == 200:
            try:
                return f"{name}:{m}", r.json()["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, ValueError, TypeError):
                continue
        print(f"  {name} {m} HTTP {r.status_code}: {r.text[:150]}")
    return None


def providers():
    """(name, context budget in chars, call) in order: free providers first."""
    groq = os.environ.get("GROK_API_KEY") or os.environ.get("GROQ_API_KEY") or ""
    glm_base = os.environ.get("GLM_BASE_URL") or "https://api.z.ai/api/paas/v4"
    glm_models = [m for m in (os.environ.get("GLM_MODEL") or "glm-5.3,glm-4.6").split(",") if m]
    gh_tok = os.environ.get("GH_TOKEN") or ""
    return [
        ("gemini", 110000, lambda p: gemini(p)),
        ("groq", 22000, lambda p: openai_compat("groq", "https://api.groq.com/openai/v1", groq if groq.startswith(
            "gsk_") else "", [], p)),
        ("glm", 60000, lambda p: openai_compat("glm", glm_base, os.environ.get("GLM_API_KEY", ""), glm_models, p)),
        ("github-models", 30000, lambda p: openai_compat("github-models", "https://models.github.ai/inference", gh_tok,
                                                         ["openai/gpt-4.1", "openai/gpt-4.1-mini"], p)),
    ]


def parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group())
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def forbidden(path: str) -> str:
    p = path.replace("\\", "/").lstrip("./")
    if ".." in p.split("/") or p.startswith((".github/", "secrets/")) or not (ROOT / p).is_file():
        return f"{path}: not an editable file of the repo"
    return ""


def apply_edits(edits) -> str:
    """Apply all edits or none; '' when applied, else the reason."""
    if not edits:
        return "no edits"
    new_text = {}
    for e in edits:
        path, old, new = e.get("path", ""), e.get("old", ""), e.get("new", "")
        why = forbidden(path)
        if why:
            return why
        cur = new_text.get(path) or (ROOT / path).read_text("utf-8")
        if not old or cur.count(old) != 1:
            return f"{path}: 'old' text found {cur.count(old) if old else 0} times (must be exactly once)"
        new_text[path] = cur.replace(old, new, 1)
    for path, text in new_text.items():
        (ROOT / path).write_text(text, "utf-8")
    return ""


def changed_files() -> list[str]:
    out = sh("git", "status", "--porcelain", check=False).stdout
    return [ln[3:].strip().strip('"') for ln in out.splitlines() if ln.strip()]


def test_failures() -> set[str]:
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "tests"],
                           cwd=ROOT, text=True, capture_output=True, timeout=900)
    except subprocess.TimeoutExpired:
        return {"<pytest timeout>"}
    fails = set(re.findall(r"^(?:FAILED|ERROR) (\S+)", r.stdout, re.M))
    if r.returncode not in (0, 1, 5):
        fails.add(f"<pytest exit {r.returncode}>")
    return fails


def check_tree(baseline: set[str]) -> tuple[str, bool]:
    """('' if ok else reason, verified) for the working-tree changes: compile/parse each file, no new test failures.
    verified=False when a changed file cannot be checked here (e.g. TypeScript)."""
    import yaml
    verified = True
    for f in changed_files():
        p = ROOT / f
        if not p.exists():
            return f"{f} deleted", False
        try:
            if f.endswith(".py"):
                py_compile.compile(str(p), doraise=True)
            elif f.endswith(".json"):
                json.loads(p.read_text("utf-8"))
            elif f.endswith((".yml", ".yaml")):
                yaml.safe_load(p.read_text("utf-8"))
            else:
                verified = False
        except Exception as e:  # noqa: BLE001
            return f"{f}: {type(e).__name__}: {str(e)[:200]}", False
    new = test_failures() - baseline
    if new:
        return "tests that now fail: " + ", ".join(sorted(new)[:5]), False
    return "", verified


def revert():
    sh("git", "checkout", "--", ".", check=False)
    sh("git", "clean", "-fdq", "--", "tools", "video", "motion", "tests", "config", check=False)


def save_state(**kv):
    st = json.loads(STATE.read_text("utf-8")) if STATE.exists() else {}
    st.update(kv)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), "utf-8")
    return st


def cmd_diagnose():
    TMP.mkdir(parents=True, exist_ok=True)
    info = run_info()
    where, log = failed_logs()
    known = next((k for k in CFG.get("known", [])
                  if k["kind"] == json.loads(STATE.read_text("utf-8") if STATE.exists() else "{}").get("known")), None)
    save_state(wf_path=info.get("path", ""), where=where, log=log, diagnosis="", todo="", kind="", provider="",
               head_sha=info.get("head_sha", ""))
    if known and not known.get("code_fix"):  # quota, network, upload: nothing to change in the code
        save_state(kind=known["issue_kind"], diagnosis=f"{known['label']}: ancora così dopo "
                   f"{len(known.get('waits_s', []))} tentativi automatici con attese.", todo=known.get("todo", ""))
        output(status="skip")
        return
    if not wf_cfg().get("autofix") or os.environ.get("AUTOFIX_ENABLED", "true") == "false":
        save_state(kind="off", diagnosis="Autofix spento per questo workflow.")
        output(status="skip")
        return
    lim = over_limit()
    if lim:
        save_state(kind="limit", diagnosis=f"Autofix non tentato: {lim} (per evitare loop e costi).")
        output(status="skip")
        return
    baseline = test_failures()
    save_state(baseline=sorted(baseline))
    (TMP / "context.md").write_text(build_context(110000), "utf-8")
    calls = 0
    for name, budget, call in providers():
        feedback = ""
        for _round in range(2):
            if calls >= 5:
                break
            prompt = PROMPT + "\n" + build_context(budget) + feedback
            res = call(prompt)
            if not res:
                break
            calls += 1
            who, text = res
            d = parse(text)
            if not d:
                print(f"  {who}: answer is not JSON")
                feedback = "\n\nYour previous answer was not valid JSON. Answer with the JSON object only."
                continue
            kind = str(d.get("kind", "")).lower()
            save_state(kind=kind, diagnosis=str(d.get("diagnosis", ""))[:1200], todo=str(d.get("todo", ""))[:800],
                       provider=who)
            print(f"  {who}: kind={kind}; {str(d.get('diagnosis', ''))[:300]}")
            if kind != "code":
                output(status="nofix", kind=kind)  # a model that sees no code fix: Claude is not asked either
                return
            why = apply_edits(d.get("edits") or [])
            if not why:
                why, _ = check_tree(baseline)
                if why:
                    revert()
            if not why:
                print(f"  fix by {who}: {', '.join(changed_files())}")
                output(status="fixed", kind="code")
                return
            print(f"  {who}: fix rejected ({why})")
            feedback = (f"\n\nYour previous edits were rejected: {why}. Copy 'old' exactly from the files above "
                        "and keep the change minimal.")
    output(status="nofix", kind=json.loads(STATE.read_text("utf-8")).get("kind") or "unknown")


# ---------------------------------------------------------------- 3. finish
def risky(diff: str, files: list[str]) -> str:
    a = CFG["autofix"]
    for f in files:
        if any(f == r or (r.endswith("/") and f.startswith(r)) for r in a["risky_paths"]):
            return f"tocca {f} (pubblicazione, token, code, log o workflow)"
    added = "\n".join(ln[1:] for ln in diff.splitlines() if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---")))
    m = re.search(a["risky_words"], added, re.I)
    if m:
        return f"la modifica contiene '{m.group()}'"
    n = len(added.splitlines())
    if n > a["max_changed_lines"]:
        return f"modifica troppo grande ({n} righe)"
    return ""


def git_identity():
    sh("git", "config", "user.name", BOT[0])
    sh("git", "config", "user.email", BOT[1])


def push_main_log(entry: dict):
    """Append the autofix log on main (limits across runs)."""
    git_identity()
    sh("git", "checkout", "-q", "-f", "main", check=False)
    for _ in range(4):
        sh("git", "pull", "-q", "--rebase", "--autostash", "origin", "main", check=False)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        sh("git", "add", str(LOG))
        sh("git", "commit", "-q", "-m", f"log: autofix {WF}", check=False)
        if sh("git", "push", "-q", "origin", "HEAD:main", check=False).returncode == 0:
            return
        sh("git", "reset", "-q", "--hard", "origin/main", check=False)
        time.sleep(5)
    print("could not push the autofix log")


def issue(title: str, body: str):
    body += f"\n\nRun: {RUN_URL}\n\n_Aperta da self-heal.yml (tools/self_heal.py)._"
    found = gh_api("GET", "/issues", params={"state": "open", "labels": "alert", "per_page": 50}).json()
    for i in found if isinstance(found, list) else []:
        if i.get("title") == title:
            gh_api("POST", f"/issues/{i['number']}/comments", json={"body": body})
            print(f"issue #{i['number']} updated")
            return
    gh_api("POST", "/labels", json={"name": "alert", "color": "B60205", "description": "Automazione fallita"})
    r = gh_api("POST", "/issues", json={"title": title, "body": body, "labels": ["alert"], "assignees": [OWNER]})
    if r.status_code >= 300:
        r = gh_api("POST", "/issues", json={"title": title, "body": body, "labels": ["alert"]})
    print(f"issue: HTTP {r.status_code} {r.json().get('html_url', '')}")


KIND_IT = {"transient": "errore temporaneo (servizio occupato o rete)", "credentials": "credenziali o token",
           "quota": "quota esaurita", "external": "servizio esterno", "config": "configurazione da sistemare",
           "code": "bug nel codice", "limit": "limite autofix", "off": "autofix spento"}


def cmd_finish():
    st = json.loads(STATE.read_text("utf-8")) if STATE.exists() else {}
    claude_note = TMP / "claude-diagnosis.txt"
    if claude_note.exists() and claude_note.read_text("utf-8").strip():
        st = save_state(diagnosis=claude_note.read_text("utf-8").strip()[:1200], provider="claude",
                        kind="code" if changed_files() else st.get("kind", ""))
    files = [f for f in changed_files() if not f.startswith(("logs/", ".github/"))]
    revert_others = [f for f in changed_files() if f not in files]
    if revert_others:
        sh("git", "checkout", "--", *revert_others, check=False)
    diag = st.get("diagnosis") or "nessuna diagnosi disponibile"
    kind = st.get("kind") or "unknown"
    title = f"Autofix: {WF} non riparato"
    entry = {"wf": WF, "run": RUN_ID, "at": int(time.time()), "kind": kind, "by": st.get("provider", ""),
             "day": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
    if not files:
        if kind not in ("limit", "off"):
            push_main_log({**entry, "result": "no-fix"})
        todo = st.get("todo") or "Apri il log del run per i dettagli."
        issue(title, f"**{WF}** è fallito anche dopo i tentativi automatici e l'autofix non ha trovato una correzione "
                     f"nel codice.\n\n**Causa probabile** ({KIND_IT.get(kind, kind)}): {diag}\n\n**Cosa fare:** {todo}")
        output(result="notified")
        return
    why, verified = check_tree(set(st.get("baseline", [])))
    if why:
        revert()
        push_main_log({**entry, "result": "rejected"})
        issue(title, f"L'autofix ha proposto una correzione per **{WF}** ma non passa i controlli ({why}).\n\n"
                     f"**Causa probabile:** {diag}")
        output(result="notified")
        return
    git_identity()
    diff = sh("git", "diff").stdout
    danger = risky(diff, files) or ("" if verified else "file non verificabile automaticamente (es. TypeScript)")
    branch = f"autofix/{WF}-{RUN_ID}"
    sh("git", "checkout", "-q", "-B", branch)
    sh("git", "add", "--", *files)
    sh("git", "commit", "-q", "-m", f"autofix {WF}: {diag[:60]}",
       "-m", f"Run fallito: {RUN_URL}\nDiagnosi ({st.get('provider', '?')}): {diag}")
    push = sh("git", "push", "-q", "-f", "origin", branch, check=False)
    if push.returncode != 0:
        push_main_log({**entry, "result": "push-failed"})
        issue(title, f"Correzione trovata per **{WF}** ma non è stato possibile caricarla ({push.stderr[-200:]}).\n\n"
                     f"**Causa probabile:** {diag}\n\n```diff\n{diff[:3000]}\n```")
        output(result="notified")
        return
    body = (f"Correzione automatica del run fallito {RUN_URL}\n\n**Diagnosi** ({st.get('provider', '?')}): {diag}\n\n"
            f"Controlli: compilazione dei file e test senza nuovi errori.\n"
            + (f"\n**Non unita in automatico:** {danger}. Va controllata a mano.\n" if danger else
               "\nSicura (nessun publisher, token, cancellazione o workflow): unita in automatico.\n"))
    r = gh_api("POST", "/pulls", json={"title": f"autofix {WF}: {diag[:70]}", "head": branch, "base": "main",
                                       "body": body})
    pr = r.json() if r.status_code < 300 else {}
    pr_url = pr.get("html_url", f"https://github.com/{REPO}/compare/main...{branch}")
    merged = False
    if not danger:
        if pr.get("number"):
            m = gh_api("PUT", f"/pulls/{pr['number']}/merge", json={"merge_method": "squash"})
            merged = m.status_code < 300
            if not merged:
                print(f"merge refused: HTTP {m.status_code} {m.text[:200]}")
        else:  # Actions may not be allowed to open PRs (repo setting): the safe fix goes straight to main
            print(f"PR not created (HTTP {r.status_code}): pushing the safe fix to main")
            sh("git", "pull", "-q", "--rebase", "--autostash", "origin", "main", check=False)
            merged = sh("git", "push", "-q", "origin", f"{branch}:main", check=False).returncode == 0
        if merged:
            gh_api("DELETE", f"/git/refs/heads/{branch}")
    if not merged:
        push_main_log({**entry, "result": "pr-open", "pr": pr_url})
        issue(f"Autofix: {WF} da controllare", f"L'autofix ha preparato una correzione per **{WF}** ma non l'ha unita: "
                                               f"{danger or 'merge non riuscito'}.\n\nPR: {pr_url}\n\n**Diagnosi:** {diag}")
        output(result="pr-open")
        return
    print(f"fix merged: {pr_url}")
    verify = ""
    if int(wf_cfg().get("retries", 0)) > 0:  # re-run the failed jobs: they check out main, so the fix is included
        verify = rerun_and_wait()
        print(f"verification re-run: {verify or 'no result'}")
    if verify == "success":
        after_recovery()
    push_main_log({**entry, "result": "merged", "pr": pr_url, "verify": verify})
    if pr.get("number"):
        note = {"success": "Verifica: il run rilanciato dopo la correzione è riuscito.",
                "": "Verifica: nessun rilancio (si vedrà al prossimo run programmato)."}.get(
            verify, f"Verifica: il run rilanciato è ancora fallito ({verify}).")
        gh_api("POST", f"/issues/{pr['number']}/comments", json={"body": note})
    if verify and verify != "success":
        issue(title, f"Correzione unita ({pr_url}) ma il run di **{WF}** fallisce ancora.\n\n**Diagnosi:** {diag}")
        output(result="notified")
        return
    output(result="merged")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"retry": cmd_retry, "diagnose": cmd_diagnose, "finish": cmd_finish}.get(cmd, lambda: sys.exit(__doc__))()
