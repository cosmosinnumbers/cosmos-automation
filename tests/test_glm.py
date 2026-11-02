"""GLM provider: model choice, JSON validation, fallback, and the director's creative pass (no network)."""
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video" / "ytf"))
import director  # noqa: E402
import glm  # noqa: E402


class R:
    def __init__(self, code, body):
        self.status_code, self._b, self.text = code, body, str(body)

    def json(self):
        return self._b


def chat_ok(content):
    return R(200, {"choices": [{"message": {"content": content}}]})


def test_no_key_means_none():
    with mock.patch.dict(os.environ, {}, clear=True):
        assert glm.chat([{"role": "user", "parts": [{"text": "x"}]}]) is None


def test_model_order_and_json():
    env = {"GLM_API_KEY": "k"}
    models = R(200, {"data": [{"id": "glm-5.2"}, {"id": "glm-5.3"}, {"id": "glm-5.3-flash"}, {"id": "glm-5v-turbo"},
                              {"id": "glm-4.6"}]})
    calls = []

    def post(url, **kw):
        calls.append(kw["json"]["model"])
        return chat_ok('Here: {"ok": true}')

    with mock.patch.dict(os.environ, env, clear=True), mock.patch("requests.get", return_value=models), \
            mock.patch("requests.post", side_effect=post):
        out = glm.chat([{"role": "user", "parts": [{"text": "x"}]}])
    assert out[1] == {"ok": True} and calls == ["glm-5.3"]


def test_bad_answer_goes_to_next_model():
    env = {"GLM_API_KEY": "k", "GLM_MODELS": "glm-5.3,glm-5.2"}
    answers = iter([chat_ok("no json"), chat_ok('{"ok": true}')])
    with mock.patch.dict(os.environ, env, clear=True), mock.patch("requests.post", side_effect=lambda *a, **k: next(answers)):
        out = glm.chat([{"role": "user", "parts": [{"text": "x"}]}])
    assert out[1] == {"ok": True}


def test_creative_pass_validates():
    plan = {"inserts": [{"effect": "orbit", "props": {"label": "NASA · NEW"}}]}
    env = {"GLM_API_KEY": "k", "GLM_MODELS": "glm-5.3"}
    narr = "NASA's probes fire for 9 minutes."
    good = chat_ok('{"hook_label": "9 MINUTES TO MARS", "accent_words": ["probes"]}')
    with mock.patch.dict(os.environ, env, clear=True), mock.patch("requests.post", return_value=good):
        p = director.creative_pass(narr, {"inserts": [{"effect": "orbit", "props": {"label": "x"}}]})
    assert p["inserts"][0]["props"]["label"] == "9 MINUTES TO MARS"
    bad = chat_ok('{"hook_label": "USE CODE COSMOS9", "accent_words": ["probes"]}')
    with mock.patch.dict(os.environ, env, clear=True), mock.patch("requests.post", return_value=bad):
        p = director.creative_pass(narr, plan)
    assert p["inserts"][0]["props"]["label"] == "NASA · NEW"      # rejected: the deterministic label stays
    invented = chat_ok('{"hook_label": "100 PROBES", "accent_words": []}')
    with mock.patch.dict(os.environ, env, clear=True), mock.patch("requests.post", return_value=invented):
        p = director.creative_pass(narr, plan)
    assert p["inserts"][0]["props"]["label"] == "NASA · NEW"      # a number not in the narration


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(name, "ok")
