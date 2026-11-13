"""Sky calculator and product links: known sky facts, stable texts, tracked links (python tests/test_sky.py)."""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import links  # noqa: E402
import sky  # noqa: E402


def test_shower_peaks_match_the_known_nights():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    peak = {n: sky.shower_peak(lon, start).date() for n, lon, _, _ in sky.SHOWERS}
    assert peak["Perseids"] in (date(2026, 8, 12), date(2026, 8, 13))
    assert peak["Geminids"] == date(2026, 12, 14)
    assert peak["Leonids"] in (date(2026, 11, 17), date(2026, 11, 18))


def test_window_of_november_2026():
    w = sky.window(date(2026, 11, 14), 30)
    names = [e["name"] for e in w["events"]]
    assert "Full Moon (supermoon)" in names and "New Moon" in names and "Leonids meteor shower peak" in names
    full = next(e for e in w["events"] if e["name"].startswith("Full Moon"))
    assert full["date"] == "2026-11-24" and 356_000 < full["distance_km"] < 362_000
    p = {x["name"]: x for x in w["planets"]}
    assert p["Venus"]["when"] == "before dawn" and p["Venus"]["mag"] < -4   # morning star after the October conjunction
    assert p["Saturn"]["when"] == "evening"
    assert [e["at"] for e in w["events"]] == sorted(e["at"] for e in w["events"])
    for e in w["events"]:
        assert sky.event_text(e).endswith(".") and "None" not in sky.event_text(e)


def test_total_eclipse_day_is_a_new_moon():
    w = sky.window(date(2027, 7, 20), 30)
    assert any(e["name"] == "New Moon" and e["date"] == "2027-08-02" for e in w["events"])


def test_links_fall_back_to_the_plain_url():
    assert links.link("no-such-product", "threads", "reply") == links.BASE + "no-such-product"
    assert links.link(links.LOOK_UP, "threads", "reply").startswith(("https://gum.co/u/", links.BASE))
    assert links.is_product_link("x https://cosmosinnumbers.gumroad.com/l/look-up") and not links.is_product_link("nasa.gov")


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
