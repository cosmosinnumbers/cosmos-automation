"""Weekly running order (owner 03/11/2026: "devo avere ogni settimana la scaletta di cosa pubblichiamo").

  python tools/scaletta.py [--start YYYY-MM-DD] [--dry-run]

For the 7 days from --start (default: next Monday) writes reports/scaletta-<YYYY-Www>.md with, day by day:
- what is already in the queues at its exact minute (queues/meta-, threads-, tiktok-, x-, youtube-queue.json);
- the fixed daily slots: YouTube Short 2 (hot news, 15:00, only if a story of the last 48 h passes the fact check),
  YouTube Short 1 (21:00), Threads 12:00 news / 16:00 quiz / 21:00 video post, the Saturday long video;
- the FORECAST of the format of Short 1 (sky event, follow-up of a hit, otherwise the format the variant tests
  favour now), from the same rules as tools/experiments.py plan. The real choice is made on the day, with fresh data.
The workflow scaletta.yml runs it on Sunday evening and opens a GitHub issue assigned to the owner (phone notification).
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiments as ex  # noqa: E402
import trend_scout as ts  # noqa: E402

ROOT = ex.ROOT
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
QUEUES = {"meta": "Instagram/Facebook", "threads": "Threads", "tiktok": "TikTok", "x": "X", "youtube": "YouTube"}
ACTION = {"ig-reel": "Reel Instagram", "fb-reel": "Reel Facebook", "ig-story": "Storia Instagram", "fb-story": "Storia Facebook",
          "ig-carousel": "Carosello Instagram"}


def queued(day: date) -> list[tuple[str, str]]:
    out = []
    for q, name in QUEUES.items():
        items = ex.jload(ROOT / "queues" / f"{q}-queue.json", [])
        for it in items if isinstance(items, list) else []:
            at = str(it.get("at", ""))
            if not at.startswith(day.isoformat()) or it.get("published") or it.get("done"):
                continue
            what = ACTION.get(it.get("action"), name)
            text = (it.get("caption") or it.get("text") or "").split("\n")[0][:70]
            if not text:   # stories have no caption: the slug of the Short (si-a1102-mars-elongated-cloud)
                text = "del Short \"" + " ".join(str(it.get("ref", "")).split("-")[2:]).capitalize() + "\""
            out.append((at[11:16], f"{what}: {text}"))
    return sorted(set(out))


def forecast(days: list[date], seed: str) -> dict:
    """Format of Short 1 for each day, with the plan rules (sky -> follow-up -> bandit), simulated in order."""
    lib = ts.load_formats()
    rng = random.Random(seed)
    state, trends = ex.jload(ex.STATE, {}), ex.latest_trends()
    ideas = [i for i in ex.jload(ex.IDEAS, []) if not i.get("used")]
    ideas.sort(key=lambda i: (-i.get("priority", 0), i.get("created", "")))
    fstate = state.get("formats", {})
    losers = {k for k, v in fstate.items() if v.get("decision") == "perde"}
    bonus = ex.trend_bonus(trends, "formats")
    sky_done, used, out = set(), [], {}
    for d in days:
        recent = used[-6:]
        allowed = [k for k in lib["formats"] if recent.count(k) < ex.MAX_PER_WEEK and k != "audience_question"]
        sky = [e for e in ts.sky_events(d, 2) if e["name"] not in sky_done]
        if sky and "sky_tonight" in allowed:
            sky_done.add(sky[0]["name"])
            f, why = "sky_tonight", f"evento del cielo: {sky[0]['name']} ({sky[0]['date']})"
        elif ideas and ideas[0]["format"] in allowed:
            i = ideas.pop(0)
            f, why = i["format"], f"seguito di \"{i['from']}\" ({i['score_from']}x la mediana)"
        else:
            f, _ = ex.thompson(allowed, fstate, bonus, rng, losers)
            why = "test di variante (scelto dai dati del giorno)"
        used.append(f)
        out[d] = (lib["formats"].get(f, {}).get("label", f), why)
    return out


def build(start: date) -> str:
    days = [start + timedelta(days=i) for i in range(7)]
    fc = forecast(days, str(start))
    week = f"{start:%G-W%V}"
    L = [f"# Scaletta della settimana {start:%d/%m} - {days[-1]:%d/%m/%Y}", "",
         "Tutto esce da GitHub Actions, senza PC. Gli orari sono ora italiana. Il formato degli Short è una previsione: "
         "la scelta vera si fa la mattina stessa con i dati freschi (trend, metriche, notizie).", ""]
    sky = [e for e in json.loads((ts.SKY).read_text("utf-8")).get("events", []) if days[0].isoformat() <= e["date"] <= days[-1].isoformat()] if ts.SKY.exists() else []
    if sky:
        L += ["**Cielo della settimana:** " + "; ".join(f"{e['name']} ({date.fromisoformat(e['date']):%d/%m})" for e in sky), ""]
    for d in days:
        g = GIORNI[d.weekday()]
        label, why = fc[d]
        L += [f"## {g} {d:%d/%m}", ""]
        rows = [("12:00", "Threads: notizia del giorno (fonte NASA/ESA/ESO)"),
                ("15:00", "YouTube Short 2: notizia calda delle ultime 48 ore (esce solo se ce n'è una che passa il fact check)"),
                ("16:00", "Threads: quiz con sondaggio (risposta il giorno dopo)"),
                ("21:00", f"YouTube Short 1: formato previsto **{label}** ({why})"),
                ("21:00", "Threads: post del video del giorno")]
        if d.weekday() == 5:
            rows.append(("09:00", "Video lungo della settimana: costruito e controllato in automatico, pronto come release"))
        q = queued(d)
        busy = {(t, w.split(":")[0]) for t, w in q}
        rows = [(t, w) for t, w in rows if (t, w.split(":")[0]) not in busy]   # the queued post replaces the generic slot
        rows += q
        seen = set()
        for t, what in sorted(rows):
            if (t, what) in seen:
                continue
            seen.add((t, what))
            L.append(f"- {t} · {what}")
        L.append("")
    L += ["## Sempre", "",
          "- I Reel e le storie Instagram/Facebook di ogni Short vanno in coda da soli, con il ritmo anti-blocco di Meta: gli orari esatti compaiono sopra quando sono già in coda.",
          "- TikTok resta spento finché TikTok non approva l'app.",
          "- Link LOOK UP in descrizione, nel commento del canale e in bio; mai codice sconto a schermo.",
          f"- Il report dei test (cosa ha vinto) è in reports/esperimenti-{week}.md il lunedì successivo.", ""]
    return "\n".join(L)


def main():
    a = sys.argv[1:]
    today = date.today()
    start = date.fromisoformat(a[a.index("--start") + 1]) if "--start" in a else today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    md = build(start)
    print(md)
    if "--dry-run" not in a:
        out = ROOT / "reports" / f"scaletta-{start:%G-W%V}.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(md, "utf-8")
        print("written", out)


if __name__ == "__main__":
    main()
