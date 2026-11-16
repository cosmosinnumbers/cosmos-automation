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
CONTROL = {("x", "reply")}   # tracked links that are published nowhere (X is off since 26/10/2026): robots only


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

    th, th_acct = defaultdict(dict), {}
    for r in rows("threads"):
        if r.get("level") == "account":
            if "acct_link_clicks_7d" in r["metrics"] and s < r["date"] <= t:
                th_acct = r["metrics"]   # the last reading inside the window
        else:
            th[r["id"]][r["date"]] = r["metrics"].get("views", 0)
    out["threads_views"] = sum(grow(v, t, s) for v in th.values()) if th else None
    out["threads_link_clicks"] = th_acct.get("acct_link_clicks_7d") if days == 7 else None

    fb = defaultdict(dict)
    for r in rows("facebook"):
        if r.get("level") == "post" and r["metrics"].get("clicks") is not None:
            fb[r["id"]][r["date"]] = r["metrics"]["clicks"]
    out["fb_post_clicks"] = sum(grow(v, t, s) for v in fb.values()) if fb else None

    # Clicks counted by Gumroad on the short links. Robots open them too (funnel review 16/11/2026): every link got 2
    # "clicks" the day it was made, and a link posted on Threads or Facebook gets about 20 more per post from the
    # preview crawlers (164 "clicks" on 8 Threads replies in two days, with zero downloads). So:
    # - CONTROL links are published nowhere: what they count is robots, and it is taken off every link of the product;
    # - a link on a platform that counts human link clicks itself is capped by that number (Instagram link taps,
    #   Threads link clicks, Facebook clicks on the posts); with no such number its clicks are left out and shown
    #   apart as "non verificabili", never added to the human total.
    series, meta = defaultdict(dict), {}
    for r in rows("gumroad-utm"):
        series[r["id"]][r["date"]] = r["metrics"].get("unique_clicks") or 0
        meta[r["id"]] = (r["campaign"], r["source"], r["medium"])
    raw = {meta[i]: grow(v, t, s) for i, v in series.items()}
    base = defaultdict(int)
    for (camp, src, med), d in raw.items():
        if (src, med) in CONTROL:
            base[camp] = max(base[camp], d)
    caps = {("instagram", "bio"): out["ig_link_taps"], ("threads", "reply"): out["threads_link_clicks"],
            ("facebook", "post"): out["fb_post_clicks"]}
    clicks, unverified, robots = {}, {}, 0
    left = dict(caps)   # one human number per platform, shared by the links of all products
    for (camp, src, med), d in sorted(raw.items(), key=lambda kv: -kv[1]):
        if not d or (src, med) in CONTROL:
            robots += d
            continue
        name, human = f"{camp} · {src} {med}", max(0, d - base[camp])
        if (src, med) in caps:
            if left[(src, med)] is None:
                unverified[name] = d
                continue
            human = min(human, left[(src, med)])
            left[(src, med)] -= human
        robots += d - human
        if human:
            clicks[name] = human
    out["clicks"], out["robot_clicks"], out["unverified_clicks"] = clicks, robots, unverified
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
    if views and (hc < 30 or hc * 1000 < views * 3):
        L.append(f"- **Collo di bottiglia: il clic.** Clic veri: {n(hc)} su {n(views)} visualizzazioni "
                 f"({hc / views * 100:.2f}%). Sotto i 30 clic veri a settimana (o lo 0,3%) non si può giudicare né "
                 "prezzo né pagina: servono contenuti da cielo di stasera, video lunghi (link cliccabili), la pagina "
                 "Amazon e link del canale in ordine.")
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
        L.append(f"- {n(f['robot_clicks'])} clic contati da Gumroad sono robot (anteprime dei link, controlli "
                 "automatici): esclusi dai conti. Si riconoscono perché li prendono anche i link mai pubblicati.")
    if f["unverified_clicks"]:
        L.append(f"- {n(sum(f['unverified_clicks'].values()))} clic non verificabili (" +
                 ", ".join(f"{k}: {v}" for k, v in f["unverified_clicks"].items()) +
                 "): la piattaforma non ci ha dato il suo conteggio dei clic di persone, quindi non entrano nel totale.")
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
