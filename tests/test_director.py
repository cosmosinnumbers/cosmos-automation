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


def test_long_shots_are_cut_and_numbers_become_kinetic():
    import render
    assert render.beat_text("It will make forty-nine science-dedicated flybys.")[0] == "49 science-dedicated flybys"
    assert render.beat_text("It arrives in April twenty-thirty and enters orbit.") is None
    assert render.beat_text("The December twenty twenty-six Earth assist.") is None
    assert render.beat_text("But the number forty-nine is a plan.") is None
    img, chart = {"type": "image", "src": "a"}, {"type": "chart", "src": "b"}
    script = {"segments": [{"id": "s1", "chapter": "Intro", "narration": "x", "visuals": [img, chart]}]}
    sents = [{"text": "Hello there.", "start": 0.0, "end": 9.0},
             {"text": "It carries nine science instruments.", "start": 10.0, "end": 14.0}]
    shots = render.build_shots(script, {"duration": 200.0, "segments": [{"id": "s1", "start": 0.0, "sentences": sents}]})
    assert max(s["end"] - s["start"] for s in shots) <= render.MAX_SHOT_LONG + 0.5
    assert [s for s in shots if s["chapter"]] == shots[:1]
    kin = [s["visual"]["text"] for s in shots if s["visual"]["type"] == "kinetic"]
    assert kin == ["9 science instruments"]
    short = render.build_shots(script, {"duration": 50.0, "segments": [{"id": "s1", "start": 0.0, "sentences": sents}]})
    assert len(short) == 2   # Shorts keep their own cuts


def test_long_without_chapters_has_spot_and_ask():
    import director
    shots = []
    t = 0.0
    for i in range(60):
        v = {"type": "image", "src": f"img_{i}"}
        if i == 28:
            v = {"type": "kinetic", "text": "LOOK UP · link in the description", "spot": True}
        if i in (10, 58):
            v["ask"] = "Closer to 10 or to 100?"
        shots.append({"start": t, "end": t + 6, "visual": v, "segment": f"c{i // 8 + 1}", "chapter": None,
                      "act": f"Act {i // 8}" if i % 8 == 0 else None})
        t += 6
    script = {"chapters": False, "sources": [], "segments": [{"id": f"c{k}", "narration": "look up"} for k in range(1, 9)]}
    p = director.plan_long(script, shots, {"duration": t})
    eff = {i: f["effect"] for i, f in p["fx"].items()}
    assert eff[28] == "phonescreens"
    assert eff[10] == "typewriter" and p["fx"][10]["props"]["lines"][0] == "> your turn"
    assert not any(f["effect"] == "typewriter" and "chapter" in f["props"]["lines"][0] for f in p["fx"].values())
    assert p["transitions"] and any(k == "riser" for _, k in p["events"])   # acts still pace the video
    assert eff[59] == "phonescreens" and eff[58] == "typewriter"


def test_long_script_check_engagement():
    import longform_auto as lf
    def beat(say, kind="image", q="europa ice", **kw):
        return {"say": say, "show": {"type": kind, "query": q} if kind in ("image", "footage") else {"type": kind, "text": "x"}, **kw}
    spec = {"title": "Why NASA Will Fly Past Europa 49 Times", "chapters": [
        {"title": "a", "beats": [beat("Chapter one begins here, so what do you think?")]}]}
    probs = " | ".join(lf.script_check(spec))
    assert "never announce chapters" in probs
    assert "'ask' beats" in probs and "'spot' beat" in probs
    spec["title"] = "The Shocking Secret of Europa"
    assert "vague word" in " | ".join(lf.script_check(spec))


def test_long_stickmen_added_and_length_hint():
    import longform_auto as lf
    segs = [{"visuals": [{"type": "image", "src": f"i{k}{j}"} for j in range(3)]} for k in range(4)]
    assert lf.add_stickmen(segs) == 6
    spec = {"title": "x", "chapters": [{"title": "a", "beats": [{"say": "word " * 100, "show": {"type": "image"}}]}]}
    msg = next(m for m in lf.script_check(spec) if m.startswith("narration has"))
    assert "ADD about" in msg and "act 1 100 words" in msg


def test_katana_kit_in_shorts():
    """Owner 06/11/2026: the Katana look. Shock numbers hit as an Impact Frame, the short line slams as Katana Type,
    cuts rotate whip / zoom-through / dither, and every new sound has a level."""
    txt = ["NASA will fly past Europa 49 times.", "Each flyby lasts only minutes.", "The ice hides an ocean.",
           "Scientists have waited decades for this moment to arrive.",
           "It is the largest planetary probe NASA ever built, 6000 kilograms.", "Scientists want to taste it.",
           "Nobody has been this close.", "Each pass maps a new strip of ice.", "It arrives at Jupiter in 2030 after a long cruise."]
    tm = timings(txt)
    d = tm["duration"]
    p = director.plan_short({"sources_full": []}, tm, cut_times=[k * 1.3 for k in range(1, int(d / 1.3))])
    effects = [i["effect"] for i in p["inserts"]]
    assert "impactframe" in effects and "vertigo" not in effects
    assert "katanatype" in effects and "papercut" not in effects
    assert {e for _, e in p["transitions"]} <= {"whip", "zoomthrough", "dither", "glitch"}
    assert p["transitions"] and p["transitions"][0][1] == "whip"
    assert all(k in sfx.LEVEL for _, k in p["events"])
    for a, b in zip(p["inserts"], p["inserts"][1:]):
        assert a["t1"] <= b["t0"]


def test_katana_kit_sounds_and_transitions():
    from PIL import Image
    import motion
    for eff, props in [("katanatype", {"words": [{"text": "49", "at": 0.2}, {"text": "flybys", "at": 0.5}]}),
                       ("impactframe", {}), ("lightsweep", {}), ("flashcuts", {}), ("whip", {}), ("dither", {})]:
        ev = director.effect_sounds(eff, 2.4, props)
        assert ev and all(k in sfx.LEVEL for _, k in ev), eff
    assert director.effect_sounds("katanatype", 2, {"words": [{"text": "49", "at": 0.2}]})[1][1] == "impact"
    im = Image.new("RGB", (320, 180), (200, 120, 40))
    for fr in (motion.whip_out(im, 0.7), motion.whip_in(im, 0.3), motion.dither(im, 4, 8)):
        assert fr.size == im.size and fr.mode == "RGB"
    assert set(director.CUT_CYCLE) <= set(director.TRANS_LEAD)
    assert {"katanatype", "impactframe", "lightsweep", "flashcuts"} <= set(motion.DEFAULT_FRAMES)


def test_katana_kit_in_long_videos():
    shots, t = [], 0.0
    vis = [{"type": "counter", "value": 49, "label": "flybys"}, {"type": "kinetic", "text": "The ice hides an ocean"},
           {"type": "kinetic", "text": "It is the largest moon ocean, 2 times Earth's water"}]
    for k in range(18):
        shots.append({"start": t, "end": t + 6.0, "segment": "s1", "visual": vis[k % 3] if k else {"type": "image", "src": "i"},
                      "chapter": None})
        t += 6.0
    p = director.plan_long({"segments": [{"id": "s1", "narration": "x"}], "sources": []}, shots, {"duration": t})
    effects = [f["effect"] for f in p["fx"].values()]
    assert "lightsweep" in effects and "charts" in effects
    assert "katanatype" in effects and "impactframe" in effects
