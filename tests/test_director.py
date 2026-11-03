"""The director picks effects from the narration and never puts a discount code on screen (TikTok rule)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import director  # noqa: E402
import sfx  # noqa: E402


def timings(sentences):
    t, out = 0.0, []
    for s in sentences:
        d = len(s.split()) * 0.33
        out.append({"start": t, "end": t + d, "text": s})
        t += d + 0.15
    return {"duration": t, "segments": [{"sentences": out}]}


TXT = ["NASA will fly past Europa 49 times.", "Under the ice there may be twice as much water as on Earth.",
       "The shell could be 15 to 25 kilometers thick.", "But the surface is young, and that is the surprising part.",
       "The whole spacecraft spans 30.5 meters with its solar arrays open.", "Europa Clipper uses solar power.",
       "It arrives at Jupiter in 2030 after a long cruise."]


def test_number_info():
    assert director.number_info("It arrives in 2030.") is None
    assert director.number_info("The X-59 flies.") is None
    r = director.number_info("The shell could be 15 to 25 kilometers thick.")
    assert r["display"] == "15–25 km" and r["value"] == 25 and r["from"] == 15
    assert director.number_info("About 70% of it is water.")["display"] == "70%"


def test_plan_short():
    tm = timings(TXT)
    p = director.plan_short({"sources_full": [{"title": "Europa Clipper", "url": "https://science.nasa.gov/x"}]},
                            tm, cut_times=[tm["duration"] / 2])
    effects = [i["effect"] for i in p["inserts"]]
    assert effects[0] == "orbit" and "charts" in effects
    assert effects[-1] == "typewriter" and p["tail"] > 0
    assert p["inserts"][0]["props"]["label"].startswith("NASA")
    for a, b in zip(p["inserts"], p["inserts"][1:]):
        assert a["t1"] <= b["t0"]                       # never two scenes at once
    shown = str([i["props"] for i in p["inserts"]])
    assert "COSMOS9" not in shown and "code" not in shown.lower()
    assert all(k in sfx.LEVEL for _, k in p["events"])  # every sound event has a level


def test_sfx_track_peaks_on_event():
    import numpy as np
    x = sfx.track(2.0, [(1.0, "impact")])
    env = np.abs(x[:, 0])
    onset = np.argmax(env > 0.2 * env.max()) / sfx.SR   # real samples can peak a little after they start
    assert 0.9 < onset < 1.1 and env[: int(0.9 * sfx.SR)].max() < 0.05 * env.max()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "ok")


def test_long_uses_typewriter_and_risers():
    import director as dr
    shots, t = [], 0.0
    for c in range(6):
        for k in range(4):
            v = {"type": "kinetic", "text": "A huge number appears here"} if k == 1 else {"type": "image", "src": "img"}
            shots.append({"start": t, "end": t + 5.0, "segment": f"s{c}", "visual": v,
                          "chapter": (f"Chapter title {c}" if c else "Intro") if k == 0 else None})
            t += 5.0
    script = {"segments": [{"id": f"s{c}", "narration": "Text."} for c in range(6)], "sources": []}
    p = dr.plan_long(script, shots, {"duration": t})
    effects = [f["effect"] for f in p["fx"].values()]
    assert "typewriter" in effects
    assert sum(1 for _, k in p["events"] if k == "riser") >= 5
