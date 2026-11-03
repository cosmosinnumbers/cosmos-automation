"""Weekly learning loop of the viral plan (phase F): what worked in the last videos -> weights the writer reads.

  python tools/learn_weekly.py [--dry-run]

Facts only, no LLM: latest reading of every public YouTube video in 07-analytics/metrics/youtube.jsonl (plus the
retention summary r5/r25/r50/r75 when metrics.py has it). Each Short/long video gets a score = 0.5 * views / median
views + 0.5 * avg_view_pct / median avg_view_pct (same kind). Features of the title and the length are compared:
mean score with the feature against without, needing at least 3 videos on each side. The result goes to
config/viral-weights.json (read by video/ytf/auto_short.py: "what worked / what did not" block in the writer prompt)
and to reports/apprendimento-<date>.md with the reasons, the decision and the numbers behind it. A feature needs a lift
of at least 20% to become a rule; otherwise it stays "no evidence yet". Rules are replaced every week, never piled up.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "07-analytics" / "metrics" / "youtube.jsonl"
WEIGHTS = ROOT / "config" / "viral-weights.json"
REPORT_ONLY = ("under_35s",)   # reported, never fed to the writer: length is fixed by the 85-110 word rule and confounded by topic
FEATURES = {
    "number_in_title": (lambda t, d: bool(re.search(r"\d", t)),
                        "put a concrete number in the title", "avoid a bare number in the title"),
    "scale_comparison": (lambda t, d: bool(re.search(r"\b(fit|fits|than|times|bigger|larger|smaller|vs|versus|longer|faster|hotter|colder)\b", t, re.I)),
                         "use a scale comparison (X fits inside Y, N times bigger than Z)", "do not lean on comparison words"),
    "short_title": (lambda t, d: len(re.sub(r"#\w+", "", t).strip()) <= 55,
                    "keep the title at 55 characters or fewer", "longer titles did better: allow up to 70 characters"),
    "question_title": (lambda t, d: "?" in t, "phrase the title as a question", "avoid question titles"),
    "under_35s": (lambda t, d: d is not None and d <= 35, "keep the Short at 35 seconds or fewer", "longer Shorts held viewers better"),
}


def latest():
    best = {}
    for ln in METRICS.read_text("utf-8").splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("level") == "video" and r.get("metrics", {}).get("avg_view_pct") is not None:
            if r["id"] not in best or r["read_at"] > best[r["id"]]["read_at"]:
                best[r["id"]] = r
    return list(best.values())


def duration(r):
    m = r["metrics"]
    if m.get("avg_view_duration_s") and m.get("avg_view_pct"):
        return m["avg_view_duration_s"] / (m["avg_view_pct"] / 100.0)
    return None


def analyse(rows):
    out = {"features": {}, "winners": [], "losers": [], "n": {}}
    for kind in ("short", "long"):
        vs = [r for r in rows if r["kind"] == kind]
        out["n"][kind] = len(vs)
        if len(vs) < 6:
            continue
        mv = statistics.median(r["metrics"]["views"] for r in vs) or 1
        mp = statistics.median(r["metrics"]["avg_view_pct"] for r in vs) or 1
        for r in vs:
            r["score"] = round(0.5 * r["metrics"]["views"] / mv + 0.5 * r["metrics"]["avg_view_pct"] / mp, 2)
        vs.sort(key=lambda r: -r["score"])
        out["winners"] += [{"title": re.sub(r"#\w+", "", r["title"]).strip(), "kind": kind, "score": r["score"],
                            "views": r["metrics"]["views"], "view_pct": r["metrics"]["avg_view_pct"]} for r in vs[:3]]
        out["losers"] += [{"title": re.sub(r"#\w+", "", r["title"]).strip(), "kind": kind, "score": r["score"],
                           "views": r["metrics"]["views"], "view_pct": r["metrics"]["avg_view_pct"]} for r in vs[-2:]]
        for name, (fn, do, dont) in FEATURES.items():
            if name == "under_35s" and kind != "short":
                continue
            yes = [r["score"] for r in vs if fn(r["title"], duration(r))]
            no = [r["score"] for r in vs if not fn(r["title"], duration(r))]
            if len(yes) < 3 or len(no) < 3:
                continue
            ym, nm = statistics.mean(yes), statistics.mean(no)
            lift = (ym - nm) / nm if nm else 0
            out["features"][f"{kind}:{name}"] = {"kind": kind, "with": round(ym, 2), "without": round(nm, 2), "n_with": len(yes),
                                                 "n_without": len(no), "lift": round(lift, 2),
                                                 "rule": do if lift >= 0.2 else (dont if lift <= -0.2 else None)}
    return out


def report(res, today):
    L = [f"# Apprendimento settimanale ({today})", "",
         f"Video letti: {res['n'].get('short', 0)} Short, {res['n'].get('long', 0)} lunghi (servono almeno 6 per tipo).", ""]
    L += ["## Cosa ha funzionato (punteggio = metà views sulla mediana, metà percentuale vista sulla mediana)"]
    L += [f"- {w['title']} ({w['kind']}): punteggio {w['score']}, {w['views']} views, {w['view_pct']}% visto" for w in res["winners"]] or ["- dati insufficienti"]
    L += ["", "## Cosa no"]
    L += [f"- {w['title']} ({w['kind']}): punteggio {w['score']}, {w['views']} views, {w['view_pct']}% visto" for w in res["losers"]] or ["- dati insufficienti"]
    L += ["", "## Regole dai dati (lift almeno 20%, minimo 3 video per lato)"]
    rules = [(k, v) for k, v in res["features"].items() if v["rule"]]
    L += [f"- {v['kind']}: {v['rule']} (con: {v['with']} su {v['n_with']} video, senza: {v['without']} su {v['n_without']}; lift {v['lift']:+.0%})"
          for k, v in rules] or ["- nessun effetto abbastanza chiaro: il modello resta com'è e si raccolgono altri dati"]
    L += ["", "## Tutti i confronti"]
    L += [f"- {k}: lift {v['lift']:+.0%} (n {v['n_with']}/{v['n_without']})" for k, v in res["features"].items()] or ["- nessuno"]
    L += ["", "Decisione: le regole sopra entrano nel prompt dello scrittore dal prossimo Short; vengono sostituite, non accumulate, ogni lunedì."]
    return "\n".join(L) + "\n"


def main():
    dry = "--dry-run" in sys.argv
    today = date.today().isoformat()
    rows = latest() if METRICS.exists() else []
    res = analyse(rows)
    md = report(res, today)
    print(md)
    weights = {"updated": today, "winners": res["winners"], "losers": res["losers"],
               "rules": [v["rule"] for k, v in res["features"].items() if v["rule"] and not k.endswith(REPORT_ONLY)], "features": res["features"]}
    if dry:
        return
    WEIGHTS.parent.mkdir(exist_ok=True)
    WEIGHTS.write_text(json.dumps(weights, indent=1, ensure_ascii=False), "utf-8")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"apprendimento-{today}.md").write_text(md, "utf-8")


if __name__ == "__main__":
    main()
