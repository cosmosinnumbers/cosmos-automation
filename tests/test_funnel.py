"""Funnel report: the clicks of robots never count as people (funnel review 16/11/2026).  python tests/test_funnel.py"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cta
import funnel_report as fr
import links
import sky_page


def utm(i, camp, src, med, day, n):
    return {"id": i, "campaign": camp, "source": src, "medium": med, "date": day, "metrics": {"unique_clicks": n}}


def write(d, name, rows):
    (Path(d) / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows), "utf-8")


def base_rows(d):
    write(d, "gumroad-utm", [
        utm("c", "look-up", "x", "reply", "2026-11-15", 2),                  # published nowhere: robots
        utm("y", "look-up", "youtube", "description", "2026-11-15", 9),
        utm("t", "look-up", "threads", "reply", "2026-11-15", 76),
        utm("i", "look-up", "instagram", "bio", "2026-11-15", 40),
    ])
    write(d, "instagram", [{"level": "account", "date": "2026-11-15", "metrics": {"acct_reach": 100, "acct_website_clicks": 3}}])


def test_robots_are_not_people():
    with tempfile.TemporaryDirectory() as d:
        fr.M = Path(d)
        base_rows(d)
        f = fr.build(7, date(2026, 11, 15))
        # Threads gave no human count: its 76 stay apart; YouTube loses the 2 of the control link; Instagram is capped
        assert f["clicks"] == {"look-up · youtube description": 7, "look-up · instagram bio": 3}, f["clicks"]
        assert f["unverified_clicks"] == {"look-up · threads reply": 76} and f["human_clicks"] == 10
        assert "il clic" in fr.verdict({**f, "yt_views": 1000, "threads_views": 0})[0]   # under 30 human clicks: never "la pagina"


def test_threads_capped_by_its_own_count():
    with tempfile.TemporaryDirectory() as d:
        fr.M = Path(d)
        base_rows(d)
        write(d, "threads", [{"level": "account", "id": "u", "date": "2026-11-15", "metrics": {"acct_link_clicks_7d": 4}},
                             {"level": "post", "id": "p", "date": "2026-11-15", "metrics": {"views": 500}}])
        f = fr.build(7, date(2026, 11, 15))
        assert f["clicks"]["look-up · threads reply"] == 4 and not f["unverified_clicks"] and f["threads_views"] == 500


def test_amazon_only_when_live():
    assert links.amazon() == "" and not any("Amazon" in t for t in cta.all_texts())   # config/stores.json is empty today
    with tempfile.TemporaryDirectory() as d:
        old, links.STORES = links.STORES, Path(d) / "stores.json"
        links.STORES.write_text(json.dumps({"amazon_kindle": "https://www.amazon.com/dp/B0TEST", "gumroad_seller_id": "1", "site": "https://x.test/"}))
        try:
            texts = cta.all_texts()
            assert any("amazon.com/dp/B0TEST" in t for t in texts) and all(len(t) <= 280 for t in texts)
            assert links.is_product_link("see https://www.amazon.com/dp/B0TEST")
            page = sky_page.build(json.loads((sky_page.OUT / "sky.json").read_text("utf-8")), date(2026, 12, 5))
            assert "amazon.com/dp/B0TEST" in page and "COSMOS9" not in page and "follow_from_embed_form" in page
        finally:
            links.STORES = old


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
