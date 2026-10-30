"""Weekly strategy on GitHub (owner 30/10/2026, replaces the Claude task cosmos-strategy-weekly): scorecard + decisions.

  python tools/strategy_weekly.py [--dry-run] [--no-llm]

1. Facts by code, never by the LLM: 07-analytics/metrics/*.jsonl (cumulative readings of metrics.yml), latest
   reading against the one 7 days earlier, per channel and format: posts, views, views gained in the week, median,
   likes, comments, shares, saves, Instagram watch time; account followers; what is "non misurato" and why.
2. Gemini (backup: Groq, the same writer chain as auto_short.py) reads the facts table and the research of the week
   (research/cosmos/<week>.md and gemini-*.md) and writes in Italian: interpretation, at most 2 decisions as
   hypotheses (variable, expected result, metric, duration, criterion) or none, competitor ideas. Every number of
   its text must be in the facts or the research; the ones that are not are listed as "non verificati".
Output: reports/scorecard-<YYYY-MM-DD>.md and a dated section on top of reports/decisioni-settimanali.md (committed
by strategy.yml); --dry-run prints them. No publishing, no secrets in the text.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video" / "ytf"))
METRICS = ROOT / "07-analytics" / "metrics"
RESEARCH = ROOT / "research" / "cosmos"
OUT = ROOT / "reports"
CHANNELS = ("youtube", "instagram", "facebook", "threads", "tiktok", "gumroad")

PROMPT = """Sei lo stratega dei dati di "Cosmos in Numbers" (canale faceless sullo spazio, in inglese) e del prodotto
LOOK UP (guida all'osservazione del cielo su Gumroad, $14). Scrivi in italiano, frasi semplici.
Regole fisse: usa SOLO numeri presenti nei FATTI o nella RICERCA qui sotto, con le loro date; non stimare ciò che è
"non misurato"; i campioni piccoli vanno dichiarati tali; separa fatti, interpretazioni e ipotesi; confronti solo fra
formati e periodi comparabili, con i valori assoluti; il criterio finale è il business (visite a LOOK UP, vendite);
al massimo 2 decisioni, ognuna come ipotesi da testare con UNA variabile; se le prove non bastano, nessuna decisione
e indica il prossimo test utile. Niente engagement artificiale, nessuna spesa.

FATTI (calcolati dal codice, {period}):
{facts}

RICERCA DELLA SETTIMANA (dati pubblici di altri canali e schede Gemini; i loro numeri non sono fonti primarie):
{research}

Rispondi solo con JSON:
{{"interpretazione": ["3-6 punti: cosa dicono i fatti e cosa resta incerto"],
  "decisioni": [{{"ipotesi": "", "variabile": "", "risultato_atteso": "", "metrica": "", "durata": "", "criterio": ""}}],
  "nessuna_decisione_perche": "vuoto se ci sono decisioni",
  "prossimo_test": "",
  "idee_competitor": ["al massimo 2 idee adattate al nostro formato, senza copiare titoli o montaggi"]}}"""


def readings(ch: str) -> list[dict]:
    f = METRICS / f"{ch}.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text("utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def at_date(rows: list[dict], d: str) -> dict[str, dict]:
    return {r["id"]: r for r in rows if r.get("date") == d}


def fmt(n) -> str:
    if n is None:
        return "–"
    return f"{n:,.0f}".replace(",", ".") if float(n).is_integer() else f"{n:.1f}".replace(".", ",")


def scorecard(today: date) -> tuple[list[str], str]:
    lines, periods = [], []
    lines += ["| Canale | Formato | Post (nuovi 7 gg) | Visualizzazioni cumulate | + nella settimana | Mediana per post |"
              " Like | Commenti | Condivisioni | Salvataggi | Visione media |", "|" + "---|" * 11]
    notes, accounts, missing = [], [], defaultdict(set)
    for ch in CHANNELS:
        rows = readings(ch)
        dates = sorted({r.get("date") for r in rows if r.get("date")})
        if not dates:
            notes.append(f"- {ch}: nessuna lettura (non misurato)")
            continue
        last = dates[-1]
        target = (date.fromisoformat(last) - timedelta(days=7)).isoformat()
        prev = max((d for d in dates if d <= target), default=dates[0])
        periods.append(f"{ch} {prev}→{last}")
        now, before = at_date(rows, last), at_date(rows, prev)
        for r in now.values():
            for k, why in (r.get("missing") or {}).items():
                missing[ch].add(f"{k} ({why})")
        groups = defaultdict(list)
        for r in now.values():
            if r.get("level") == "account":
                m, p = r.get("metrics", {}), before.get(r["id"], {}).get("metrics", {})
                accounts.append(f"- {ch} {r.get('title', '')}: " + ", ".join(
                    f"{k} {fmt(v)}" + (f" (era {fmt(p[k])} il {prev})" if k in p and prev != last else "")
                    for k, v in m.items()))
            elif r.get("level") in ("post", "video") and r.get("metrics"):
                groups[r.get("kind") or "post"].append(r)
        if ch == "gumroad" and not groups:
            notes.append(f"- gumroad {last}: vendite e visite non misurate ({'; '.join(sorted(missing[ch])) or 'nessun dato'})")
        week_start = (date.fromisoformat(last) - timedelta(days=7)).isoformat()
        for kind, rs in sorted(groups.items()):
            views = [r["metrics"].get("views") for r in rs if r["metrics"].get("views") is not None]
            gained = sum((r["metrics"].get("views") or 0) - (before.get(r["id"], {}).get("metrics", {}).get("views") or 0)
                         for r in rs) if prev != last else None
            new = sum(1 for r in rs if (r.get("published") or "")[:10] > week_start)
            tot = lambda k: sum(r["metrics"].get(k) or 0 for r in rs) if any(k in r["metrics"] for r in rs) else None  # noqa: E731
            watch = [r["metrics"]["avg_watch_ms"] / 1000 for r in rs if r["metrics"].get("avg_watch_ms")]
            lines.append(f"| {ch} | {kind} | {len(rs)} ({new}) | {fmt(sum(views)) if views else '–'} | {fmt(gained)} | "
                         f"{fmt(statistics.median(views)) if views else '–'} | {fmt(tot('likes'))} | "
                         f"{fmt(tot('comments') if tot('comments') is not None else tot('replies'))} | "
                         f"{fmt(tot('shares'))} | {fmt(tot('saved'))} | "
                         f"{(fmt(statistics.median(watch)) + ' s mediana') if watch else '–'} |")
    out = ["## Distribuzione, attenzione e coinvolgimento (per canale e formato)", *lines, "",
           "Visualizzazioni come definite da ogni piattaforma (07-analytics/metrics/DEFINIZIONI.md); valori cumulati "
           "all'ultima lettura, \"+ nella settimana\" = differenza con la lettura di 7 giorni prima.", "",
           "## Account", *(accounts or ["- nessuna lettura di account"]), "",
           "## Traffico e risultati di business", *(notes or ["- vedi tabella"]), "",
           "## Non misurato", *(f"- {ch}: {'; '.join(sorted(v))}" for ch, v in sorted(missing.items()) if v)]
    return out, "; ".join(periods)


def research(today: date) -> str:
    if not RESEARCH.exists():
        return "nessuna ricerca"
    week = sorted(RESEARCH.glob("20*-W*.md"))
    parts = [week[-1].read_text("utf-8")[:5000]] if week else []
    for f in sorted(RESEARCH.glob("gemini-*.md")):
        try:
            d = date.fromisoformat(f.stem.replace("gemini-", ""))
        except ValueError:
            continue
        if (today - d).days <= 7:
            parts.append(f.read_text("utf-8")[:2500])
    return "\n\n---\n\n".join(parts)[:14000] or "nessuna ricerca"


def unverified(text: str, sources: str) -> list[str]:
    flat = sources.replace(".", "").replace(",", "")
    out = []
    for n in dict.fromkeys(re.findall(r"\d[\d.,]*", text)):
        n = n.rstrip(".,")
        if len(n.replace(".", "").replace(",", "")) < 2 or n in sources or n.replace(".", "").replace(",", "") in flat:
            continue
        out.append(n)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    today = date.today()
    facts, period = scorecard(today)
    facts_txt = "\n".join(facts)
    res = research(today)
    analysis = ["## Analisi (Gemini, controllata dal codice)", "- Non scritta: --no-llm."]
    if "--no-llm" not in sys.argv:
        import auto_short as a
        msgs = [{"role": "user", "parts": [{"text": PROMPT.format(period=period, facts=facts_txt, research=res)}]}]
        _, j = a.gemini(msgs, search=False)
        body = []
        body += ["### Interpretazione", *(f"- {x}" for x in j.get("interpretazione", []))]
        dec = [d for d in j.get("decisioni", []) if d.get("ipotesi")][:2]
        body += ["", "### Decisioni (ipotesi da testare)"]
        body += [f"- **{d['ipotesi']}** Variabile: {d.get('variabile', '')}. Risultato atteso: {d.get('risultato_atteso', '')}. "
                 f"Metrica: {d.get('metrica', '')}. Durata: {d.get('durata', '')}. Criterio: {d.get('criterio', '')}." for d in dec]
        if not dec:
            body.append(f"- Nessuna decisione: {j.get('nessuna_decisione_perche', '')}")
        body += ["", f"### Prossimo test utile\n- {j.get('prossimo_test', '')}", "",
                 "### Idee dai competitor", *(f"- {x}" for x in j.get("idee_competitor", [])[:2])]
        text = "\n".join(body)
        bad = unverified(text, facts_txt + res)
        analysis = ["## Analisi (Gemini, controllata dal codice)"]
        if bad:
            analysis.append(f"⚠️ Numeri non trovati nei fatti né nella ricerca, da non usare: {', '.join(bad)}")
        analysis.append(text)
    doc = [f"# Scorecard settimanale ({today:%d/%m/%Y})", "",
           f"**Periodo delle letture:** {period}. **Fonti:** `07-analytics/metrics/*.jsonl` (metrics.yml), "
           f"`research/cosmos/`. Fatti calcolati dal codice (`tools/strategy_weekly.py`); l'analisi è un'ipotesi, "
           "non una conclusione. Campioni piccoli: tutto esplorativo.", "", *facts, "", *analysis, ""]
    text = "\n".join(doc)
    if "--dry-run" in sys.argv:
        print(text)
        return
    OUT.mkdir(exist_ok=True)
    (OUT / f"scorecard-{today:%Y-%m-%d}.md").write_text(text, "utf-8")
    dec_file = OUT / "decisioni-settimanali.md"
    old = dec_file.read_text("utf-8") if dec_file.exists() else "# Decisioni settimanali (GitHub Actions)\n"
    head, _, rest = old.partition("\n")
    section = f"\n## {today:%d/%m/%Y}: scorecard `reports/scorecard-{today:%Y-%m-%d}.md`\n" + "\n".join(analysis[1:]) + "\n"
    dec_file.write_text(head + "\n" + section + rest, "utf-8")
    print(text)


if __name__ == "__main__":
    main()
