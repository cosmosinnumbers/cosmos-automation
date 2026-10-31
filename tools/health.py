"""Weekly health check (owner 30/10/2026): one GitHub issue every Monday with what the automation did and what is due.

  python tools/health.py [--dry-run]

Sections: runs of every workflow in the last 7 days (gh run list), posts published per platform (the logs of the
repo), Short releases, future items per queue, Short reserve, deadlines (Threads token age, Meta data access,
COSMOS9 end). Never prints a secret: only ages, days and counts. --dry-run prints the issue instead of opening it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "cosmosinnumbers/cosmos-automation")
DAYS = 7
COSMOS9_END = date(2026, 11, 30)
THREADS_TOKEN_DAYS = 60


def gh(*a) -> str:
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def runs(since: datetime) -> tuple[list[str], list[str]]:
    out = ["Solo run automatiche (pianificate o a catena); le prove lanciate a mano non contano.", "",
           "| Workflow | Riuscite | Fallite | Altre | Ultima |", "|---|---|---|---|---|"]
    bad = []
    wfs = json.loads(gh("api", f"repos/{REPO}/actions/workflows", "--jq", ".workflows"))
    for wf in sorted(wfs, key=lambda w: w["name"]):
        if wf["state"] != "active":
            out.append(f"| {wf['name']} | | | | disattivato |")
            continue
        rs = json.loads(gh("run", "list", "--repo", REPO, "--workflow", str(wf["id"]), "--limit", "200",
                           "--created", f">={since:%Y-%m-%d}", "--json", "conclusion,status,createdAt,url,event"))
        rs = [r for r in rs if r["event"] != "workflow_dispatch"]  # only the automatic runs: manual tests are not failures
        c = Counter(r["conclusion"] or r["status"] for r in rs)
        last = rs[0] if rs else None
        last_txt = f"[{last['conclusion'] or last['status']}]({last['url']}) {last['createdAt'][:10]}" if last else "nessuna"
        other = sum(v for k, v in c.items() if k not in ("success", "failure"))
        out.append(f"| {wf['name']} | {c['success']} | {c['failure']} | {other} | {last_txt} |")
        if last and last["conclusion"] == "failure":  # failures already fixed by a later success are only counted
            bad.append(f"{wf['name']}: ultima run fallita ({last['url']})")
    return out, bad


def published(since: int) -> list[str]:
    out = []
    for log, label in (("meta-publish-log.jsonl", "Meta"), ("threads-publish-log.jsonl", "Threads"),
                       ("youtube-publish-log.jsonl", "YouTube"), ("x-publish-log.jsonl", "X"),
                       ("tiktok-publish-log.jsonl", "TikTok")):
        ev = [e for e in creds.events(log) if int(e.get("at", 0)) >= since]
        if label == "Threads":
            ev = [e for e in ev if e.get("k") != "reply"]
        c = Counter(f"{e.get('p', '')} {e.get('k', '')}".strip() or "post" for e in ev)
        detail = ", ".join(f"{k}: {v}" for k, v in sorted(c.items())) or "nessuno"
        out.append(f"- {label}: {len(ev)} ({detail})")
    missed = [e for e in creds.events("missed-log.jsonl") if int(e.get("at", 0)) >= since]
    out.append(f"- Elementi saltati perché la run è partita tardi: {len(missed)}"
               + (f" ({', '.join(e['ref'] for e in missed)})" if missed else ""))
    return out


def queues(now: str) -> list[str]:
    out = []
    for f in sorted(creds.QUEUES.glob("*-queue.json")):
        q = json.loads(f.read_text("utf-8"))
        fut = sorted(i["at"] for i in q if i.get("at", "") > now)
        kinds = Counter(i.get("action", "post") for i in q if i.get("at", "") > now)
        detail = f" ({', '.join(f'{k}: {v}' for k, v in sorted(kinds.items()))})" if len(kinds) > 1 else ""
        out.append(f"- {f.stem.replace('-queue', '')}: {len(fut)} in coda{detail}"
                   + (f", ultimo {fut[-1]}" if fut else " ⚠️ coda vuota"))
    return out


def shorts(since: datetime) -> list[str]:
    rels = json.loads(gh("api", f"repos/{REPO}/releases?per_page=30"))
    days = {(since + timedelta(days=i)).strftime("%m%d") for i in range(1, DAYS + 1)}
    got = sorted({r["tag_name"][1:5] for r in rels if r["tag_name"][:1] == "a" and r["tag_name"][1:5] in days})
    missing = sorted(days - set(got))
    reserve = [p.name for p in (creds.REPO / "reserve").iterdir() if p.is_dir()] if (creds.REPO / "reserve").exists() else []
    return [f"- Short del giorno (release a<MMDD>): {len(got)}/{DAYS}"
            + (f", mancano {', '.join(m[2:] + '/' + m[:2] for m in missing)}" if missing else ""),
            f"- Short di riserva pronti in reserve/: {len(reserve)}" + (" ⚠️ riserva vuota" if not reserve else "")]


def deadlines(today: date) -> list[str]:
    out = []
    try:
        th = creds.load("threads")
        age = (time.time() - th.get("token_at", 0)) / 86400
        out.append(f"- Token Threads: {age:.0f} giorni (scade a {THREADS_TOKEN_DAYS}; tokens.yml lo rinnova il lunedì)"
                   + (" ⚠️ rinnovo non riuscito" if age > 14 else ""))
    except SystemExit:
        out.append("- Token Threads: segreto THREADS_JSON non disponibile qui")
    try:
        import meta_api
        c = meta_api.cfg()
        d = meta_api.call("GET", "debug_token", params={"input_token": c["page_token"],
                                                        "access_token": f"{c['app_id']}|{c['app_secret']}"})["data"]
        left = (d.get("data_access_expires_at", 0) - time.time()) / 86400
        out.append(f"- Meta: token valido {d.get('is_valid')}, accesso ai dati per altri {left:.0f} giorni"
                   + (" ⚠️ Simone deve rigenerarlo (SOP 15.7)" if left < 21 else ""))
    except (SystemExit, Exception) as e:  # noqa: BLE001
        out.append(f"- Meta: controllo non riuscito ({type(e).__name__})")
    left = (COSMOS9_END - today).days
    out.append(f"- COSMOS9: {'finisce fra ' + str(left) + ' giorni (30/11/2026)' if left >= 0 else 'finito il 30/11/2026'}")
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    now = creds.now_local()
    since = now - timedelta(days=DAYS)
    body = [f"Controllo automatico del {now:%d/%m/%Y %H:%M} (ora italiana), periodo {since:%d/%m}–{now:%d/%m}.", ""]
    try:
        table, bad = runs(since)
    except RuntimeError as e:
        table, bad = [f"Elenco delle run non disponibile: {e}"], []
    body += ["## Da guardare", *(f"- ⚠️ {b}" for b in bad), "" if bad else "- Nessun workflow con l'ultima run fallita.", ""]
    body += ["## Workflow (ultimi 7 giorni)", *table, ""]
    body += ["## Pubblicato (dai log del repo)", *published(int(since.timestamp())), ""]
    try:
        body += ["## Short", *shorts(since), ""]
    except RuntimeError as e:
        body += ["## Short", f"Release non leggibili: {e}", ""]
    body += ["## Code (elementi futuri)", *queues(f"{now:%Y-%m-%d %H:%M}"), ""]
    body += ["## Scadenze", *deadlines(now.date()), ""]
    body.append("Nessun segreto in questo testo: solo conteggi, età e giorni.")
    text = "\n".join(body)
    title = f"Salute settimanale {now:%d/%m/%Y}" + (f": {len(bad)} workflow da guardare" if bad else ": tutto in ordine")
    print(title, "\n", text, sep="")
    if "--dry-run" in sys.argv:
        return
    print(gh("issue", "create", "--repo", REPO, "--title", title, "--body", text))


if __name__ == "__main__":
    main()
