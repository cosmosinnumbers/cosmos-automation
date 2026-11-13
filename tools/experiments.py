"""Variant tests and automatic replication of what works (viral engine, steps 4, 5 and 7).

  python tools/experiments.py plan [--evergreen | --hot] [--seed S]     choose format + hook (+ topic) of the next Short
  python tools/experiments.py record <result.json>              log the labels of a released Short
  python tools/experiments.py learn [--dry-run]                 metrics -> arm state, hits -> follow-up ideas
  python tools/experiments.py report [--dry-run]                reports/esperimenti-<YYYY-Www>.md

Every Short carries labels (format, hook, theme, topic): logs/experiments.jsonl. `learn` joins them with the YouTube
metrics (07-analytics/metrics/youtube.jsonl, through logs/youtube-publish-log.jsonl ref -> video id), scores each
Short 48 h+ after publication (0.5 * views / median + 0.5 * % viewed / median, as learn_weekly.py) and keeps a
Beta(successes, failures) per format and per hook in config/experiments-state.json (success = score >= 1, older
results weigh 20% less per week). Shorts published before the engine get labels inferred from their title.

`plan` = priorities, then Thompson sampling: a sky event in the next 2 days (config/sky-calendar.json) -> sky_tonight;
then a follow-up idea of queues/ideas.json (written by `learn` when a Short scored >= 2x the median); otherwise 80% of
the time the arm with the best Beta sample x trend bonus (research/<niche>/trends-<date>.json), 20% the least tried
arm (exploration). Max 3 Shorts of the same format in 7 days. Decisions: a format wins after >= 5 Shorts with mean
score >= 1.3, loses under 0.7 after 5 Shorts (then only 5% of exploration). No LLM, no network.
"""
from __future__ import annotations

import json
import os
import random
import re
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import trend_scout as ts  # noqa: E402

LOG = ROOT / "logs" / "experiments.jsonl"
STATE = ROOT / "config" / "experiments-state.json"
IDEAS = ROOT / "queues" / "ideas.json"
METRICS = ROOT / "07-analytics" / "metrics" / "youtube.jsonl"
PUBLOG = ROOT / "logs" / "youtube-publish-log.jsonl"
NICHE = os.environ.get("NICHE", "cosmos")
EXPLORE, MAX_PER_WEEK, HIT, WIN, LOSE, MIN_N = 0.2, 3, 2.0, 1.3, 0.7, 5


def jl(path: Path) -> list[dict]:
    out = []
    if path.exists():
        for ln in path.read_text("utf-8").splitlines():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def jload(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def jsave(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", "utf-8")


def latest_trends() -> dict:
    files = sorted((ROOT / "research" / NICHE).glob("trends-*.json"))
    return jload(files[-1], {}) if files else {}


def recent_formats(log: list[dict], today: date, days: int = 7) -> dict:
    out: dict = {}
    for r in log:
        try:
            d = date.fromisoformat(r["date"][:10])
        except (KeyError, ValueError):
            continue
        if 0 <= (today - d).days < days:
            lb = r.get("labels", {})
            f = lb.get("tried") or lb.get("format")   # a variant that fell back still used its slot
            out[f] = out.get(f, 0) + 1
    return out


def thompson(arms: list[str], state: dict, bonus: dict, rng: random.Random, losers: set) -> tuple[str, str]:
    """(arm, why): 20% exploration on the least tried arm, otherwise the best Beta sample x (1 + 0.5 x trend)."""
    if not arms:
        raise ValueError("no arm available")
    if rng.random() < EXPLORE:
        pool = [a for a in arms if a not in losers] or arms
        n = {a: state.get(a, {}).get("n", 0) for a in pool}
        least = min(n.values())
        return rng.choice([a for a in pool if n[a] == least]), "esplorazione (braccio meno provato)"
    best, why, top = None, "", -1.0
    for a in arms:
        s = state.get(a, {})
        x = rng.betavariate(1 + s.get("wins", 0), 1 + s.get("losses", 0)) * (1 + 0.5 * bonus.get(a, 0))
        if a in losers:
            x *= 0.25
        if x > top:
            best, top = a, x
            why = f"Thompson: Beta({1 + s.get('wins', 0):.1f}, {1 + s.get('losses', 0):.1f}), trend {bonus.get(a, 0):.2f}"
    return best, why


def trend_bonus(trends: dict, key: str) -> dict:
    sc = {k: v["score"] for k, v in (trends.get(key) or {}).items() if k != "other"}
    top = max(sc.values()) if sc else 0
    return {k: v / top for k, v in sc.items()} if top else {}


HOT_FORMATS = ("news_angle", "mission_glitch", "myth_number", "scale_zoom", "survive_x")  # fit any fresh news


def plan(today: date, evergreen: bool = False, seed: str | None = None, hot: bool = False) -> dict:
    lib = ts.load_formats()
    rng = random.Random(seed or f"{today}-{datetime.now():%H}")
    log, state, trends = jl(LOG), jload(STATE, {}), latest_trends()
    used = recent_formats(log, today)
    fstate, hstate = state.get("formats", {}), state.get("hooks", {})
    losers = {k for k, v in fstate.items() if v.get("decision") == "perde"}
    allowed = [k for k, f in lib["formats"].items()
               if used.get(k, 0) < MAX_PER_WEEK and (f.get("evergreen") or not evergreen)]
    if hot:   # second Short of the day: only formats that fit a fresh news story, no sky event, no follow-up
        allowed = [k for k in allowed if k in HOT_FORMATS] or list(HOT_FORMATS)
    questions = [q for q in trends.get("audience_questions", []) if len(q) <= 140]
    if not questions:
        allowed = [k for k in allowed if k != "audience_question"]
    out = {"date": today.isoformat(), "topic": "", "source": "bandit"}

    # 1. a sky event the viewer can see in the next 4 days, not covered in the last 2 days (sales review 13/11/2026:
    #    it was 2 and 3. People search an event in the days before it, and "what to see tonight" is the content that
    #    matches the product, a stargazing guide: each event now gets up to two Shorts instead of one)
    sky = [e for e in ts.sky_events(today, 4)]
    if sky and not evergreen and not hot and "sky_tonight" in allowed and recent_formats(log, today, 2).get("sky_tonight", 0) == 0:
        e = sky[0]
        out.update(format="sky_tonight", topic=e["hint"], source="sky-calendar", why=f"{e['name']} il {e['date']}")
    # 1b. no calendar event, but a sky story is hot in the news today (aurora alert, a new comet, an eclipse): the
    #     news radar (tools/news_radar.py) flags the stories a viewer can go out and see
    if "format" not in out and not evergreen and "sky_tonight" in allowed and recent_formats(log, today, 2).get("sky_tonight", 0) == 0:
        try:
            import news_radar
            hot_sky = news_radar.sky_story("cosmos")
        except Exception:  # noqa: BLE001
            hot_sky = None
        if hot_sky:
            out.update(format="sky_tonight", topic=f"this sky story in the news today: {hot_sky['title']}",
                       source="news-radar", why=f"calore {hot_sky['heat']}, {hot_sky['outlets']} testate")
    # 2. a follow-up of a hit (queues/ideas.json), oldest first
    if "format" not in out and not hot:
        ideas = jload(IDEAS, [])
        todo = [i for i in ideas if not i.get("used") and i.get("format") in allowed]
        if todo:
            i = sorted(todo, key=lambda i: (-i.get("priority", 0), i.get("created", "")))[0]
            out.update(format=i["format"], topic=i.get("hint", ""), source="replica", why=f"seguito di {i.get('from')}", idea=i["id"])
    # 3. Thompson sampling with the trend bonus
    if "format" not in out:
        f, why = thompson(allowed, fstate, trend_bonus(trends, "formats"), rng, losers)
        out.update(format=f, why=why)
        if f == "audience_question":
            out["topic"] = "Answer this real question from viewers: " + rng.choice(questions)
    h, hwhy = thompson(list(lib["hooks"]), hstate, trend_bonus(trends, "hooks"), rng, set())
    out.update(hook=h, hook_why=hwhy)
    return out


def mark_used(idea_id: str) -> None:
    ideas = jload(IDEAS, [])
    for i in ideas:
        if i.get("id") == idea_id:
            i["used"] = date.today().isoformat()
    jsave(IDEAS, ideas)


def record(result_path: Path) -> dict:
    r = jload(result_path, {})
    labels = dict(r.get("labels") or {})
    lib = ts.load_formats()
    c = ts.classify(r.get("title", ""), lib)
    labels.setdefault("format", c["format"])
    labels.setdefault("hook", c["hook"])
    labels["theme"] = c["theme"]
    labels["title_chars"] = len(re.sub(r"#\w+", "", r.get("title", "")).strip())
    labels["seconds"] = r.get("duration")
    row = {"date": date.today().isoformat(), "ref": r.get("id"), "title": r.get("title"), "labels": labels,
           "run": os.environ.get("GITHUB_RUN_ID"), "timing": r.get("timing")}
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if labels.get("idea"):
        mark_used(labels["idea"])
    return row


def latest_metrics() -> dict:
    best: dict = {}
    for r in jl(METRICS):
        if r.get("level") == "video" and r.get("kind") == "short":
            if r["id"] not in best or r["read_at"] > best[r["id"]]["read_at"]:
                best[r["id"]] = r
    return best


def scored_shorts(today: date) -> list[dict]:
    """Our Shorts published 48 h+ ago, with score and labels (logged, or inferred from the title)."""
    mets = latest_metrics()
    lib = ts.load_formats()
    by_ref = {r["ref"]: r for r in jl(LOG) if r.get("ref")}
    vid_ref = {p["id"]: p["ref"] for p in jl(PUBLOG) if p.get("p") == "youtube" and p.get("id")}
    rows = []
    cutoff = datetime.combine(today, datetime.min.time(), timezone.utc) - timedelta(hours=48)
    for vid, m in mets.items():
        try:
            pub = datetime.fromisoformat(m["published"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if pub > cutoff:
            continue
        exp = by_ref.get(vid_ref.get(vid, ""), {})
        labels = exp.get("labels") or {**ts.classify(m["title"], lib), "inferred": True}
        rows.append({"id": vid, "ref": vid_ref.get(vid), "title": re.sub(r"#\w+", "", m["title"]).strip(),
                     "published": pub.date().isoformat(), "views": m["metrics"].get("views") or 0,
                     "pct": m["metrics"].get("avg_view_pct"), "labels": labels})
    if not rows:
        return []
    mv = statistics.median(r["views"] for r in rows) or 1
    pcts = [r["pct"] for r in rows if r["pct"] is not None]
    mp = statistics.median(pcts) if pcts else None
    for r in rows:
        if mp and r["pct"] is not None:
            r["score"] = round(0.5 * r["views"] / mv + 0.5 * r["pct"] / mp, 2)
        else:
            r["score"] = round(r["views"] / mv, 2)
    return rows


def arms(rows: list[dict], key: str, today: date) -> dict:
    out: dict = {}
    for r in rows:
        a = r["labels"].get(key) or "other"
        w = 0.8 ** max(0, (today - date.fromisoformat(r["published"])).days // 7)
        s = out.setdefault(a, {"n": 0, "wins": 0.0, "losses": 0.0, "scores": []})
        s["n"] += 1
        s["scores"].append(r["score"])
        if r["score"] >= 1:
            s["wins"] += w
        else:
            s["losses"] += w
    for s in out.values():
        s["mean"] = round(statistics.mean(s["scores"]), 2)
        s["wins"], s["losses"] = round(s["wins"], 2), round(s["losses"], 2)
        s["decision"] = ("vince" if s["n"] >= MIN_N and s["mean"] >= WIN else
                         "perde" if s["n"] >= MIN_N and s["mean"] < LOSE else "esplora")
        del s["scores"]
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["mean"]))


def follow_ups(rows: list[dict], ideas: list[dict], today: date) -> list[dict]:
    """A Short at >= 2x the median gets 2 follow-ups in the same format (never the same numbers)."""
    done = {i.get("from_id") for i in ideas}
    lib = ts.load_formats()["formats"]
    new = []
    for r in sorted(rows, key=lambda r: -r["score"]):
        if r["score"] < HIT or r["id"] in done:
            continue
        if (today - date.fromisoformat(r["published"])).days > 21:
            continue   # an old hit: the trend has moved on
        f = r["labels"].get("format")
        if f not in lib:   # title not classified: data Shorts are evergreen comparisons, the others news
            f = "scale_zoom" if "nasa data" in r["title"].lower() else "news_angle"
        for n, angle in enumerate(("the next step of the same story or a neighbouring object (a sequel: 'Part 2')",
                                   "the same format and angle on a different object"), 1):
            new.append({"id": f"{r['id']}-{n}", "from": r["title"], "from_id": r["id"], "format": f, "priority": 2 if n == 1 else 1,
                        "created": today.isoformat(), "score_from": r["score"],
                        "hint": f"Our Short '{r['title']}' did {r['score']}x our median. Make {angle}. "
                                "Same format and pace, NEW measured numbers from primary sources, never the same facts."})
    return new


def learn(today: date, dry: bool = False) -> dict:
    rows = scored_shorts(today)
    state = {"updated": today.isoformat(), "n_shorts": len(rows),
             "formats": arms(rows, "format", today), "hooks": arms(rows, "hook", today), "themes": arms(rows, "theme", today),
             "hits": [{k: r[k] for k in ("title", "id", "score", "views", "pct")} for r in sorted(rows, key=lambda r: -r["score"])[:5]]}
    ideas = jload(IDEAS, [])
    new = follow_ups(rows, ideas, today)
    if not dry:
        jsave(STATE, state)
        if new:
            jsave(IDEAS, ideas + new)
    state["new_ideas"] = new
    return state


def report(today: date, dry: bool = False) -> str:
    state, trends, log, ideas = jload(STATE, {}), latest_trends(), jl(LOG), jload(IDEAS, [])
    week = f"{today:%G-W%V}"
    L = [f"# Esperimenti {week}", "",
         f"Short valutati (pubblicati da almeno 48 ore): {state.get('n_shorts', 0)}. Punteggio = metà views sulla mediana, "
         "metà % vista sulla mediana. Successo = punteggio ≥ 1. Decisione dopo almeno 5 Short: vince ≥ 1,3, perde < 0,7.", ""]
    for key, name in (("formats", "Formati"), ("hooks", "Hook"), ("themes", "Temi")):
        L += [f"## {name}", "", "| | Short | Punteggio medio | Successi | Decisione |", "|---|---|---|---|---|"]
        L += [f"| {k} | {v['n']} | {v['mean']} | {v['wins']} | {v['decision']} |" for k, v in (state.get(key) or {}).items()]
        L.append("")
    L += ["## Short migliori", ""] + [f"- {h['title']}: {h['score']}x, {h['views']} views, {h['pct']}% visto" for h in state.get("hits", [])] + [""]
    wk = [r for r in log if r.get("date", "") >= (today - timedelta(days=7)).isoformat()]
    L += ["## Uscite degli ultimi 7 giorni", ""]
    L += [f"- {r['date']} {r.get('ref')}: formato {r['labels'].get('format')}, hook {r['labels'].get('hook')}"
          + (f", da {r['labels'].get('source')}" if r['labels'].get('source') else "") for r in wk] or ["- nessuna uscita etichettata"]
    tt = [r["timing"]["total_s"] for r in wk if (r.get("timing") or {}).get("total_s")]
    if tt:
        L += ["", f"Tempo medio di produzione di uno Short (scrittura + clip + render): {statistics.mean(tt) / 60:.1f} minuti su {len(tt)} Short."]
    ours = recent_formats(log, today)
    hot = [k for k, v in (trends.get("formats") or {}).items() if k != "other" and not ours.get(k)][:3]
    L += ["", "## Trend della nicchia non coperti da noi questa settimana", ""] + [f"- {k}" for k in hot] or ["- nessuno"]
    todo = [i for i in ideas if not i.get("used")]
    L += ["", "## Seguiti in coda (replica automatica)", ""] + [f"- {i['format']}: seguito di '{i['from']}' ({i['score_from']}x)" for i in todo] or ["- nessuno"]
    md = "\n".join(L) + "\n"
    if not dry:
        (ROOT / "reports").mkdir(exist_ok=True)
        (ROOT / "reports" / f"esperimenti-{week}.md").write_text(md, "utf-8")
    return md


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else "plan"
    today = date.today()
    dry = "--dry-run" in a
    if cmd == "plan":
        p = plan(today, "--evergreen" in a, a[a.index("--seed") + 1] if "--seed" in a else None, "--hot" in a)
        print(json.dumps(p, ensure_ascii=False, indent=1))
        gh = os.environ.get("GITHUB_OUTPUT")
        if gh:
            with open(gh, "a", encoding="utf-8") as f:
                f.write(f"format={p['format']}\nhook={p['hook']}\nidea={p.get('idea', '')}\nsource={p['source']}\n")
                f.write("topic<<EOF_TOPIC\n" + p.get("topic", "") + "\nEOF_TOPIC\n")
    elif cmd == "record":
        print(json.dumps(record(Path(a[1])), ensure_ascii=False))
    elif cmd == "learn":
        print(json.dumps(learn(today, dry), ensure_ascii=False, indent=1))
    elif cmd == "report":
        print(report(today, dry))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
