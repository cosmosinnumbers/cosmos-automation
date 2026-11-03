import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import longform_auto as lf  # noqa: E402

SPEC = {"chapters": [{"title": "A", "beats": [{"say": "One."}, {"say": "Two."}]}, {"title": "B", "beats": [{"say": "Three."}]}]}


def run(scores, weak=()):
    lf.claude_cli.available = lambda: False
    lf.glm.available = lambda: False
    lf.a.backup_llm = lambda msgs: ("raw", {"scores": scores, "weak": list(weak)})
    return lf.retention_review(SPEC)


def test_good_scores_pass():
    probs, sc = run({"hook": 8, "pacing": 7, "clarity": 8, "originality": 6, "payoff": 7})
    assert probs == [] and sc["hook"] == 8


def test_low_hook_sends_script_back_with_weak_spots():
    probs, sc = run({"hook": 4, "pacing": 7, "clarity": 8, "originality": 6, "payoff": 7},
                    [{"chapter": 1, "quote": "Hello", "why": "greeting", "fix": "open on the number"}])
    assert any("hook 4/10" in p for p in probs) and any("chapter 1" in p for p in probs)


def test_no_critic_means_no_gate():
    lf.claude_cli.available = lambda: False
    lf.glm.available = lambda: False
    lf.a.backup_llm = lambda msgs: None
    lf.a.gemini = lambda msgs, search=False: ("", None)
    assert lf.retention_review(SPEC) == ([], {})


if __name__ == "__main__":
    test_good_scores_pass(); test_low_hook_sends_script_back_with_weak_spots(); test_no_critic_means_no_gate(); print("ok")
