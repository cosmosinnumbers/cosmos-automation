"""News radar: clustering, heat, sky flag, read side (python tests/test_news_radar.py). No network."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import news_radar as nr  # noqa: E402

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
H = NOW - timedelta(hours=5)


def n(title, outlet, src="news", **kw):
    return {"src": src, "title": title, "url": f"https://{outlet.lower().replace(' ', '')}.example/{abs(hash(title)) % 999}",
            "date": H, "outlet": outlet, **kw}


FETCHED = {
    "news": [n("Euclid telescope releases first major data set with 26 million galaxies", "Space.com"),
             n("Euclid space telescope data release maps 26 million galaxies", "BBC"),
             n("ESA's Euclid drops huge galaxies data release", "Ars Technica"),
             n("Geminid meteor shower 2026: how to watch the best shooting stars of the year", "CNN"),
             n("How to see the Geminid meteor shower this week", "The Guardian"),
             n("NASA budget cuts threaten science missions, senate warned", "Politico"),
             n("Pop star announces world tour", "Variety")],
    "reddit": [n("Euclid space telescope just dropped its first major release of data", "r/space", "reddit", rank=1)],
    "hn": [n("Euclid first major data release: 26M galaxies", "Hacker News", "hn", points=180)],
    "wiki": [{"src": "wiki", "title": "Geminids", "url": "https://en.wikipedia.org/wiki/Geminids", "date": H, "outlet": "Wikipedia",
              "views": 90000, "jump": 3.0},
             {"src": "wiki", "title": "Taylor Swift", "url": "x", "date": H, "outlet": "Wikipedia", "views": 1, "jump": 1}],
    "trends": [n("geminid meteor shower", "Google Trends US", "trends")],
    "agency": [{"src": "agency", "title": "Euclid opens data treasure trove with 26 million galaxies", "date": H,
                "url": "https://www.esa.int/Science_Exploration/Space_Science/Euclid/x", "outlet": "esa.int"}],
}


def test_clusters_heat_and_flags():
    r = nr.build({}, 48, NOW, FETCHED)
    titles = [s["title"] for s in r["stories"]]
    assert not any("budget" in t.lower() or "pop star" in t.lower() for t in titles), titles   # off topic dropped
    assert not any("Taylor" in t for t in titles)
    euclid = next(s for s in r["stories"] if "Euclid" in s["title"])
    gem = next(s for s in r["stories"] if "Geminid" in s["title"])
    assert euclid["outlets"] == 3 and euclid["primary"].startswith("https://www.esa.int") and not euclid["sky"]
    assert {"news", "reddit", "hn", "agency"} <= set(euclid["signals"])
    assert gem["sky"] and gem["outlets"] == 2 and {"wiki", "trends"} <= set(gem["signals"])
    assert len([s for s in r["stories"] if "Euclid" in s["title"] or "galaxies" in s["title"]]) == 1   # one story, not three
    assert r["stories"][0]["heat"] >= r["stories"][-1]["heat"]


def test_old_items_and_failed_sources():
    old = dict(FETCHED, news=[dict(FETCHED["news"][0], date=NOW - timedelta(days=5))], reddit=[], hn=[], wiki=[], trends=[], agency=[])
    assert nr.build({}, 48, NOW, old)["stories"] == []
    r = nr.build({}, 48, NOW, {"news": FETCHED["news"]})   # the other sources are missing: skipped, not fatal
    assert set(r["skipped"]) == {"reddit", "hn", "wiki", "trends", "agency"} and r["stories"]


def test_report_and_keys():
    r = nr.build({}, 48, NOW, FETCHED)
    md = nr.report(r, "cosmos")
    assert "🔭" in md and "📄" in md and "| Calore |" in md
    assert nr.keys("NASA's Webb Finds Water on Distant Planet - Space.com") == {"webb", "find", "water", "distant", "planet"}


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
