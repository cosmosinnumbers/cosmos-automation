"""A clip never opens on a list label ("Step three: Mars.") or mid-sentence (owner 06/11/2026)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import clip  # noqa: E402

CAPS = [(10.0, 11.0, "Step three: Mars."), (11.3, 14.0, "Its distance from us changes all the time,"),
        (14.0, 16.0, "because both planets move."), (16.2, 40.0, "NASA gives a minimum of 54.6 million km.")]


def test_weak():
    assert clip.weak("Step two: the Sun.")
    assert clip.weak("First, the ruler.")
    assert clip.weak("has kept it warm for billions of years.")
    assert not clip.weak("Our Sun will never go supernova.")
    assert not clip.weak("Here is the twist most people miss.")


def test_hook_start_skips_label():
    assert clip.hook_start(CAPS, 10.0, 45.0) == 11.25


def test_hook_start_skips_mid_sentence():
    assert clip.hook_start(CAPS, 14.0, 45.0) == 16.15


def test_hook_start_keeps_good_opener_and_short_clips():
    assert clip.hook_start(CAPS, 16.2, 45.0) == 16.2
    assert clip.hook_start(CAPS, 10.0, 20.0) == 10.0
