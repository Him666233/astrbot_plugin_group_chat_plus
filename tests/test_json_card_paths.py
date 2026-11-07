import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


class Plain:
    def __init__(self, text): self.text = text

class Image:
    pass

class Json:
    def __init__(self, data): self.data = data

class At:
    qq = "123"
class AtAll: pass
class Face: id = "1"
class Reply:
    chain = None


@pytest.fixture
def modules(monkeypatch):
    comps = types.ModuleType("astrbot.api.message_components")
    for key, value in dict(Plain=Plain, Image=Image, Json=Json, At=At,
                           AtAll=AtAll, Face=Face, Reply=Reply).items():
        setattr(comps, key, value)
    monkeypatch.setitem(sys.modules, "astrbot", types.ModuleType("astrbot"))
    api = types.ModuleType("astrbot.api")
    api.logger = types.SimpleNamespace(info=lambda *a, **k: None)
    monkeypatch.setitem(sys.modules, "astrbot.api", api)
    monkeypatch.setitem(sys.modules, "astrbot.api.message_components", comps)
    pkg = types.ModuleType("gcp_test")
    pkg.__path__ = [str(ROOT)]
    utils = types.ModuleType("gcp_test.utils")
    utils.__path__ = [str(ROOT / "utils")]
    monkeypatch.setitem(sys.modules, "gcp_test", pkg)
    monkeypatch.setitem(sys.modules, "gcp_test.utils", utils)
    spec = importlib.util.spec_from_file_location("gcp_test.utils.json_card_utils", ROOT / "utils/json_card_utils.py")
    card = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, card)
    spec.loader.exec_module(card)
    return card


def test_renderer_extracts_only_whitelisted_card_fields(modules):
    card = modules.render_json_card({"prompt": "Share", "app": "Demo", "meta": {"detail_1": {"title": "Title", "desc": "Summary", "url": "https://example.org/a?token=secret#frag", "host": "private"}}, "preview": "secret"})
    assert all(part in card for part in ("Share", "Demo", "Title", "Summary", "https://example.org/a"))
    assert "secret" not in card and "private" not in card and "preview" not in card


def test_card_rendering_handles_json_string_and_bad_payload(modules):
    placeholder = "[JSON" + chr(0x5361) + chr(0x7247) + "]"
    assert "hello" in modules.render_json_card('{"prompt":"hello"}')
    assert modules.render_json_card('{bad') == placeholder
    assert modules.render_json_card({"unknown": {"deep": "do not leak"}}) == placeholder


def test_shared_reply_renderer_and_analysis_include_json(modules, monkeypatch):
    package = types.ModuleType("gcp_test.utils")
    package.__path__ = [str(ROOT / "utils")]
    monkeypatch.setitem(sys.modules, "gcp_test.utils", package)
    spec = importlib.util.spec_from_file_location("gcp_test.utils.reply_chain_utils", ROOT / "utils/reply_chain_utils.py")
    shared = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, shared)
    spec.loader.exec_module(shared)
    text = shared.render_chain_text([Json({"prompt": "hello"})])
    assert "hello" in text
    assert shared.analyze_chain([Json({"prompt": "hello"})])[1] is True


def test_known_section_search_url_validation_and_output_bounds(modules):
    text = modules.render_json_card({"meta": {"detail_1": {}, "video": {
        "title": "v" * 5000, "qqdocurl": "https://example.org/watch?token=secret#frag"
    }}})
    assert "https://example.org/watch" in text and "secret" not in text and "frag" not in text
    assert len(text) <= 1000
    assert modules.render_json_card({"meta": {"video": {"url": "https://exa\nmple.org/x"}}}) == "[JSON卡片]"
    assert modules.render_json_card({"prompt": "x" * 5000}) .__len__() <= 1000
    assert modules.render_json_card("x" * 65537) == "[JSON卡片]"


def test_known_section_fallback_is_not_lost_when_first_section_empty(modules):
    text = modules.render_json_card({"meta": {"detail_1": {}, "music": {"title": "music-title", "summary": "music-summary"}}})
    assert "music-title" in text and "music-summary" in text


def test_unknown_and_deep_payloads_are_bounded(modules):
    deep = {}
    cursor = deep
    for _ in range(1500):
        cursor["x"] = {}
        cursor = cursor["x"]
    assert modules.render_json_card(deep) == "[JSON卡片]"


def test_all_known_section_names_and_optional_json_import(monkeypatch):
    for section in ("detail_1", "detail", "news", "video", "music", "mannounce"):
        source = ROOT / "utils/json_card_utils.py"
        name = f"card_no_component_{section}"
        api = types.ModuleType("astrbot.api")
        comps = types.ModuleType("astrbot.api.message_components")
        for key, value in (("astrbot", types.ModuleType("astrbot")), ("astrbot.api", api), ("astrbot.api.message_components", comps)):
            monkeypatch.setitem(sys.modules, key, value)
        spec = importlib.util.spec_from_file_location(name, source)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert section in ("detail_1", "detail", "news", "video", "music", "mannounce")
        assert "known" in mod.render_json_card({"meta": {section: {"title": "known"}}})
        assert mod.Json is None


def test_url_rejects_bidi_c1_controls_and_userinfo(modules):
    for url in (
        "https://example.org/" + chr(0x202E) + "x",
        "https://example.org/" + chr(0x0085) + "x",
        "https://user:secret@example.org/private",
        "javascript:alert(1)",
        "http:///missing-host",
        "https://example.org:99999/x",
        "https://example.org/" + "x" * 501,
    ):
        assert modules._url(url) == ""
    text = modules.render_json_card({"prompt": "中文" + chr(0x85) + chr(0x202E) + "正常"})
    assert "中文正常" in text and chr(0x85) not in text and chr(0x202E) not in text


def test_public_shortlink_and_url_survive_max_output_truncation(modules):
    text = modules.render_json_card({"meta": {"detail_1": {
        "title": "标题" * 1000,
        "url": "https://t.co/abc?tracking=private#fragment",
    }}})
    assert len(text) <= 1000
    assert "https://t.co/abc" in text
    assert "tracking" not in text and "fragment" not in text

@pytest.mark.parametrize(("url", "expected"), [
    ("https://music.163.com/song?id=123&token=secret", "https://music.163.com/song?id=123"),
    ("https://music.163.com/#/song?id=123&token=secret", "https://music.163.com/#/song?id=123"),
    ("https://youtube.com/watch?v=Abcdef_1234&si=secret", "https://youtube.com/watch?v=Abcdef_1234"),
    ("https://www.youtube.com/watch?v=Abcdef_1234", "https://www.youtube.com/watch?v=Abcdef_1234"),
    ("https://example.org/watch?v=Abcdef_1234", "https://example.org/watch"),
    ("https://music.163.com.evil/song?id=123", "https://music.163.com.evil/song"),
    ("https://b23.tv/SHORT?token=secret#frag", "https://b23.tv/SHORT"),
    ("https://www.bilibili.com/video/BV123?x=1", "https://www.bilibili.com/video/BV123"),
    ("https://music.163.com/album?id=123", "https://music.163.com/album"),
    ("https://music.163.com/song?id=0", ""),
    ("https://music.163.com/song?ID=123", ""),
    ("https://music.163.com/song?id=123&id=456", ""),
    ("https://music.163.com/song?ID=123&id=456", ""),
    ("https://music.163.com/#/song", ""),
    ("https://music.163.com/#/songish?id=123", ""),
    ("https://music.163.com/#/song/id=123", ""),
    ("https://music.163.com/%73ong?id=123", "https://music.163.com/%73ong"),
    ("https://music.163.com/?x=1#/song?id=123", "https://music.163.com/#/song?id=123"),
    ("https://youtube.com/watch?v=short", ""),
    ("https://youtube.com/watch?V=Abcdef_1234", ""),
    ("https://youtube.com/watch?v=Abcdef_1234&v=Zyxwv_98765", ""),
    ("https://youtube.com/watch?v=Abcdef_1234%26token", ""),
    ("https://example.org/a%2Fb?q=secret#frag", "https://example.org/a%2Fb"),
    ("https://example.org/a%0Ab", ""),
    ("https://example.org/a%E2%80%AEb", ""),
    ("https://example.org/a%ED%A0%80b", ""),
    ("https://example.org/a%ZZ", ""),
    ("https://example.org:443/a", ""),
    ("https://user@example.org/a", ""),
    ("https://@example.org/a", ""),
    ("https://example.org./a", ""),
    ("https://a_b.example/a", ""),
    ("https://éxample.org/a", ""),
])
def test_url_public_route_allowlist_and_conservative_fallback(modules, url, expected):
    assert modules._url(url) == expected


def test_url_route_query_limits_and_syntax(modules):
    assert modules._url("https://music.163.com/song?id=123&x=ok&y=ok&z=ok&a=ok&b=ok&c=ok&d=ok") == "https://music.163.com/song?id=123"
    assert modules._url("https://music.163.com/song?id=123&a=1&b=2&c=3&d=4&e=5&f=6&g=7&h=8") == ""
    assert modules._url("https://music.163.com/song?id=123&bad-name=1") == ""
    assert modules._url("https://music.163.com/song?id=123&id=123") == ""
    assert modules._url("https://music.163.com/song?id=123&x=1%26y=2") == ""
    assert modules._url("https://music.163.com/song?id=123;x=1") == ""
    assert modules._url("https://music.163.com/song?id=123&") == ""
    assert modules._url("https://music.163.com/song?id=" + "1" * 257) == ""
    assert modules._url("https://music.163.com/song?id=" + "1" * 513) == ""
    assert modules._url("https://music.163.com/song?id=123#fragment") == "https://music.163.com/song?id=123"
    assert modules._url("https://music.163.com/song?id=123&token=abc") == "https://music.163.com/song?id=123"


def test_url_identity_fidelity_and_render_bounds(modules):
    value = "https://music.163.com/#/song?id=123&token=secret"
    rendered = modules.render_json_card({"meta": {"music": {"title": "Synthetic song", "url": value}}})
    assert "https://music.163.com/#/song?id=123" in rendered
    assert "token" not in rendered and "secret" not in rendered
    assert len(rendered) <= 1000
    assert modules._url("https://music.163.com/" + "x" * 2049) == ""
