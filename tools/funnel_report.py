"""Daily sales funnel in one page: views -> human clicks to Gumroad -> free downloads -> sales (run by metrics.yml).

  python tools/funnel_report.py [--days 7]

Reads the snapshots in 07-analytics/metrics/*.jsonl, writes reports/funnel.md (overwritten every day) and appends one
row to 07-analytics/metrics/funnel.jsonl. No API call, no LLM.
Why (sales review 13/11/2026): with 0 sales nobody could say where people were lost. Two traps found by hand that
this report now shows every day: the Instagram bio link had 187 "clicks" while Instagram itself counted 2 link taps
(link-preview robots), and the links inside posts were not tracked at all.
A number that is not measured is written "non misurato", never estimated.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = ROOT / "07-analytics" / "metrics"
OUT, LOG = ROOT / "reports" / "funnel.md", M / "funnel.jsonl"
FREE = ("free", "20 numbers", "30 nights")   # how the free products are recognised from their title


def rows(name: str) -> list[dict]:
    f = M / f"{name}.jsonl"
    return [json.loads(l) for l in f.read_text("utf-8").splitlines() if l.strip()] if f.exists() else []


def at_or_before(series: dict[str, float], day: str):
    days = [d for d in sorted(series) if d <= day]
    return series[days[-1]] if days else None


def delta(series: dict[str, float], today: str, since: str):
    """Growth of a cumulative counter between `since` and `today` (None if there is no reading old enough)."""
    a, b = at_or_before(series, since), at_or_before(series, today)
    return None if a is None or b is None else b - a


def grow(series: dict[str, float], today: str, since: str) -> float:
    """Same for one post or video: a piece published inside the window counts everything it has."""
    d = delta(series, today, since)
    return (at_or_before(series, today) or 0) if d is None else d


def build(days: int = 7, today: date | None = None) -> dict:
    today = today or date.today()
    t, s = today.isoformat(), (today - timedelta(days=days)).isoformat()
    out = {"date": t, "days": days}

    yt = rows("youtube")
    acc = {r["date"]: r["metrics"] for r in yt if r.get("level") == "account"}
    out["yt_views"] = delta({d: m.get("views", 0) for d, m in acc.items()}, t, s)
    out["yt_subs"] = (at_or_before({d: m.get("subscribers", 0) for d, m in acc.items()}, t))
    longs = defaultdict(dict)
    for r in yt:
        if r.get("kind") == "long":
            longs[r["id"]][r["date"]] = r["metrics"].get("views", 0)
    out["yt_long_views"] = sum(grow(v, t, s) for v in longs.values()) if longs else None

    ig = [r for r in rows("instagram") if r.get("level") == "account" and s < r["date"] <= t]
    out["ig_reach"] = sum(r["metrics"].get("acct_reach") or 0 for r in ig) if ig else None
    out["ig_link_taps"] = sum(r["metrics"].get("acct_website_clicks") or 0 for r in ig) if ig else None

    th = defaultdict(dict)
    for r in rows("threads"):
        th[r["id"]][r["date"]] = r["metrics"].get("views", 0)
    out["threads_views"] = sum(grow(v, t, s) for v in th.values()) if th else None

    clicks, robots = {}, 0
    series = defaultdict(dict)
    meta = {}
    for r in rows("gumroad-utm"):
        series[r["id"]][r["date"]] = r["metrics"].get("unique_clicks") or 0
        meta[r["id"]] = (r["campaign"], r["source"], r["medium"])
    for i, v in series.items():
        d = grow(v, t, s)
        if not d:
            continue
        camp, src, med = meta[i]
        if (src, med) == ("instagram", "bio") and out["ig_link_taps"] is not None and d > out["ig_link_taps"]:
            robots += d - out["ig_link_taps"]   # Instagram counted fewer taps than Gumroad counted clicks: robots
            d = out["ig_link_taps"]
        if d:
            clicks[f"{camp} · {src} {med}"] = d
    out["clicks"], out["robot_clicks"] = clicks, robots
    out["human_clicks"] = sum(clicks.values())

    sales = defaultdict(dict)
    price, title = {}, {}
    for r in rows("gumroad"):
        if "sales" in r.get("metrics", {}):
            sales[r["id"]][r["date"]] = r["metrics"]["sales"]
            price[r["id"]], title[r["id"]] = r["metrics"].get("price_usd", 0), r["title"]
    out["free_downloads"] = sum(delta(v, t, s) or 0 for i, v in sales.items() if not price[i])
    out["paid_sales"] = sum(delta(v, t, s) or 0 for i, v in sales.items() if price[i])
    out["paid_sales_total"] = sum(at_or_before(v, t) or 0 for i, v in sales.items() if price[i])
    out["free_downloads_total"] = sum(at_or_before(v, t) or 0 for i, v in sales.items() if not price[i])
    return out


def n(v) -> str:
    return "non misurato" if v is None else f"{v:,}".replace(",", ".")


def verdict(f: dict) -> list[str]:
    views = sum(v or 0 for v in (f["yt_views"], f["ig_reach"], f["threads_views"]))
    hc, L = f["human_clicks"], []
    if views and hc * 1000 < views * 3:
        L.append(f"- **Collo di bottiglia: il clic.** Clic veri: {n(hc)} su {n(views)} visualizzazioni "
                 f"({hc / views * 100:.2f}%). Finché sono sotto lo 0,3% non serve toccare prezzo o pagina: servono "
                 "contenuti da cielo di stasera, video lunghi (link cliccabili) e link del canale in ordine.")
    elif hc >= 30 and not f["free_downloads"] and not f["paid_sales"]:
        L.append(f"- **Collo di bottiglia: la pagina.** {n(hc)} clic veri e nessun download né vendita: rivedere "
                 "titolo, copertina e prime righe delle pagine Gumroad.")
    elif f["free_downloads"] >= 20 and not f["paid_sales"]:
        L.append("- **Collo di bottiglia: il passaggio da gratis a pagamento.** Rivedere la pagina finale del PDF, la "
                 "ricevuta e le email di Gumroad.")
    else:
        L.append("- Nessun collo di bottiglia netto con questi numeri: continuare e rileggere domani.")
    need = max(0, 50 - hc)
    L.append(f"- Regola pratica: una vendita ogni 50-100 clic veri di persone interessate al cielo. Questa settimana "
             f"ne mancano almeno {need} per aspettarsi la prima.")
    if f["robot_clicks"]:
        L.append(f"- {n(f['robot_clicks'])} clic del link in bio di Instagram sono robot (Instagram ha contato "
                 f"solo {n(f['ig_link_taps'])} tocchi sul link): esclusi dai conti.")
    return L


def main():
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 7
    f = build(days)
    L = [f"# Funnel di vendita, ultimi {days} giorni (al {f['date']})", "",
         "Scritto ogni mattina da `tools/funnel_report.py` dopo le metriche. Un numero non letto è \"non misurato\".", "",
         "| Passo | Numero |", "|---|---|",
         f"| Visualizzazioni YouTube (canale) | {n(f['yt_views'])} |",
         f"| di cui video lunghi (gli unici con link cliccabili) | {n(f['yt_long_views'])} |",
         f"| Copertura Instagram | {n(f['ig_reach'])} |",
         f"| Visualizzazioni Threads | {n(f['threads_views'])} |",
         f"| Iscritti YouTube (totale) | {n(f['yt_subs'])} |",
         f"| **Clic veri verso Gumroad** | **{n(f['human_clicks'])}** |",
         f"| Download del gratuito | {n(f['free_downloads'])} (totale {n(f['free_downloads_total'])}) |",
         f"| **Vendite a pagamento** | **{n(f['paid_sales'])}** (totale {n(f['paid_sales_total'])}) |", "",
         "## Da dove arrivano i clic", ""]
    L += [f"- {k}: {v}" for k, v in sorted(f["clicks"].items(), key=lambda kv: -kv[1])] or ["- Nessun clic misurato."]
    L += ["", "## Lettura", "", *verdict(f), ""]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(L), "utf-8")
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
