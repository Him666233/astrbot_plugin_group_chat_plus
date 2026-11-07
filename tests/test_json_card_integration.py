"""Regression tests for quoted-message (``Reply.chain``) handling.

AstrBot's ``Reply`` component exposes two content sources:

``Reply.chain``
    the original segments of the quoted message (``[Plain, Image, ...]``)
``Reply.message_str``
    the plain-text rendering of the quoted message

For a quoted *pure image* message ``message_str`` is an empty string, so any
code path that only reads it silently loses the quoted content and renders
``(无法获取引用内容)``.

These tests pin the behaviour of every path that used to be affected:

* ``utils/reply_chain_utils.py`` — the shared helper
* ``utils/message_cleaner.py`` — group chat message text extraction
* ``utils/platform_ltm_helper.py`` — group chat image detection
* ``private_chat/`` — private chat message cleaner and image handler

The plugin normally runs inside AstrBot, so a small set of message-component
doubles is provided to exercise the pure message-chain logic without
installing the whole AstrBot runtime.
"""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
PACKAGE_NAME = "group_chat_plus_test_package"


class _Logger:
    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass

    def debug(self, *_args, **_kwargs):
        pass


class _BaseMessageComponent:
    pass


class _Plain(_BaseMessageComponent):
    def __init__(self, text):
        self.text = text


class _Image(_BaseMessageComponent):
    def __init__(self, name=None, file=None, url=None):
        self.name = name or file or url
        self.file = file or name
        self.url = url

    async def convert_to_file_path(self):
        return self.name


class _Reply(_BaseMessageComponent):
    def __init__(
        self,
        chain=None,
        *,
        sender_nickname=None,
        sender_id=None,
        message_str=None,
        message=None,
    ):
        self.chain = chain
        self.sender_nickname = sender_nickname
        self.sender_id = sender_id
        self.message_str = message_str
        self.message = message


class _Face(_BaseMessageComponent):
    def __init__(self, id=0):
        self.id = id


class _At(_BaseMessageComponent):
    def __init__(self, qq=""):
        self.qq = qq


class _AtAll(_BaseMessageComponent):
    pass


class _Video(_BaseMessageComponent):
    pass


class _Record(_BaseMessageComponent):
    pass


class _File(_BaseMessageComponent):
    def __init__(self, name=""):
        self.name = name


class _Forward(_BaseMessageComponent):
    pass


class Json(_BaseMessageComponent):
    def __init__(self, data):
        self.data = data


_Json = Json


def _module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _make_package(name, path):
    package = types.ModuleType(name)
    package.__path__ = [str(path)]
    return package


def _load(monkeypatch, full_name, relative_path, path):
    """Load a real plugin module under ``full_name`` with stubs in place."""
    spec = importlib.util.spec_from_file_location(full_name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, full_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plugin(monkeypatch):
    """Load the plugin modules with lightweight AstrBot module stubs."""

    astrbot = _module("astrbot")
    api = _module("astrbot.api", logger=_Logger())
    api_all = _module(
        "astrbot.api.all",
        logger=_Logger(),
        AstrMessageEvent=object,
        Context=object,
        BaseMessageComponent=_BaseMessageComponent,
        Image=_Image,
        Json=_Json,
        Plain=_Plain,
    )
    message_components = _module(
        "astrbot.api.message_components",
        Plain=_Plain,
        At=_At,
        AtAll=_AtAll,
        Image=_Image,
        Json=_Json,
        Face=_Face,
        Reply=_Reply,
        Video=_Video,
        Record=_Record,
        File=_File,
    )
    api_event = _module("astrbot.api.event", AstrMessageEvent=object)
    core = _module("astrbot.core")
    core_message = _module("astrbot.core.message")
    core_components = _module(
        "astrbot.core.message.components",
        Video=_Video,
        Record=_Record,
        File=_File,
        Forward=_Forward,
    )

    for module in (
        astrbot,
        api,
        api_all,
        message_components,
        api_event,
        core,
        core_message,
        core_components,
    ):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    # ---- fake plugin package tree -------------------------------------
    package = _make_package(PACKAGE_NAME, REPO_ROOT)
    utils_package = _make_package(f"{PACKAGE_NAME}.utils", REPO_ROOT / "utils")
    private_package = _make_package(
        f"{PACKAGE_NAME}.private_chat", REPO_ROOT / "private_chat"
    )
    private_utils_package = _make_package(
        f"{PACKAGE_NAME}.private_chat.private_chat_utils",
        REPO_ROOT / "private_chat" / "private_chat_utils",
    )
    for module in (
        package,
        utils_package,
        private_package,
        private_utils_package,
    ):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    # ---- stub the heavy sibling dependencies --------------------------
    class _StubGroupImageHandler:
        @staticmethod
        def _coerce_plain_text(value):
            if value is None:
                return ""
            return value if isinstance(value, str) else str(value)

    monkeypatch.setitem(
        sys.modules,
        f"{PACKAGE_NAME}.utils.image_handler",
        _module(
            f"{PACKAGE_NAME}.utils.image_handler",
            ImageHandler=_StubGroupImageHandler,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        f"{PACKAGE_NAME}.utils.ai_error_formatter",
        _module(
            f"{PACKAGE_NAME}.utils.ai_error_formatter",
            format_ai_error=lambda error, label: f"{label}: {error}",
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        f"{PACKAGE_NAME}.private_chat.private_chat_utils."
        "private_chat_image_description_cache",
        _module(
            f"{PACKAGE_NAME}.private_chat.private_chat_utils."
            "private_chat_image_description_cache",
            ImageDescriptionCache=object,
        ),
    )

    # ---- load the modules under test ---------------------------------
    _load(
        monkeypatch,
        f"{PACKAGE_NAME}.utils.json_card_utils",
        "utils/json_card_utils.py",
        REPO_ROOT / "utils" / "json_card_utils.py",
    )
    reply_chain = _load(
        monkeypatch,
        f"{PACKAGE_NAME}.utils.reply_chain_utils",
        "utils/reply_chain_utils.py",
        REPO_ROOT / "utils" / "reply_chain_utils.py",
    )
    message_cleaner = _load(
        monkeypatch,
        f"{PACKAGE_NAME}.utils.message_cleaner",
        "utils/message_cleaner.py",
        REPO_ROOT / "utils" / "message_cleaner.py",
    )
    platform_ltm = _load(
        monkeypatch,
        f"{PACKAGE_NAME}.utils.platform_ltm_helper",
        "utils/platform_ltm_helper.py",
        REPO_ROOT / "utils" / "platform_ltm_helper.py",
    )
    private_cleaner = _load(
        monkeypatch,
        f"{PACKAGE_NAME}.private_chat.private_chat_utils."
        "private_chat_message_cleaner",
        "private_chat/private_chat_utils/private_chat_message_cleaner.py",
        REPO_ROOT
        / "private_chat"
        / "private_chat_utils"
        / "private_chat_message_cleaner.py",
    )
    private_image = _load(
        monkeypatch,
        f"{PACKAGE_NAME}.private_chat.private_chat_utils."
        "private_chat_image_handler",
        "private_chat/private_chat_utils/private_chat_image_handler.py",
        REPO_ROOT
        / "private_chat"
        / "private_chat_utils"
        / "private_chat_image_handler.py",
    )
    monkeypatch.setitem(sys.modules, f"{PACKAGE_NAME}.utils.image_description_cache", _module(f"{PACKAGE_NAME}.utils.image_description_cache", ImageDescriptionCache=object))
    image_handler = _load(monkeypatch, f"{PACKAGE_NAME}.utils.image_handler_real", "utils/image_handler.py", REPO_ROOT / "utils" / "image_handler.py")

    return types.SimpleNamespace(
        reply_chain=reply_chain,
        message_cleaner=message_cleaner,
        platform_ltm=platform_ltm,
        private_cleaner=private_cleaner,
        private_image=private_image,
        image_handler=image_handler,
        Plain=_Plain,
        Image=_Image,
        Reply=_Reply,
        At=_At,
        Video=_Video,
    )



def _event(*components):
    return types.SimpleNamespace(
        message_obj=types.SimpleNamespace(message=list(components))
    )

def test_json_card_is_rendered_by_group_and_private_paths(plugin):
    card = _Json({"prompt": "Share", "meta": {"detail_1": {"title": "Title", "desc": "Summary"}}})
    shared = plugin.reply_chain.render_chain_text([card, plugin.Image("outer")])
    group = plugin.image_handler.ImageHandler._render_message_chain([card, plugin.Image("outer")])
    private = plugin.private_image.ImageHandler._format_special_component(card)
    assert all("Title" in text and "Summary" in text for text in (shared, group, private)), (shared, group, private)
    assert "[图片]" in shared and "[图片]" in group
    assert plugin.image_handler.ImageHandler._analyze_message([card, plugin.Image("outer")])[1] is True
    assert plugin.private_image.ImageHandler._analyze_message([card, plugin.Image("outer")])[1] is True
    event = _event(card, plugin.Image("outer"))
    group_text = plugin.message_cleaner.MessageCleaner.extract_raw_message_from_event(event)
    private_text = plugin.private_cleaner.MessageCleaner.extract_raw_message_from_event(event)
    assert "Title" in group_text and "Title" in private_text

    nested_card = _Json({"meta": {"music": {"title": "Quoted song", "url": "https://music.163.com/song?id=123&token=secret"}}})
    quoted = plugin.Reply([plugin.Plain("before"), nested_card], sender_nickname="Alice", sender_id="42")
    chain = [quoted, _Json({"meta": {"video": {"title": "Direct video", "url": "https://youtube.com/watch?v=Abcdef_1234&si=secret"}}})]
    for rendered in (
        plugin.reply_chain.render_chain_text(chain),
        plugin.image_handler.ImageHandler._render_message_chain(chain),
    ):
        assert "Quoted song" in rendered and "Direct video" in rendered
        assert "token" not in rendered and "secret" not in rendered
    private_rendered = plugin.private_image.ImageHandler._format_special_component(chain[-1])
    assert "Direct video" in private_rendered and "secret" not in private_rendered
    assert "Quoted song" in plugin.message_cleaner.MessageCleaner.extract_raw_message_from_event(_event(quoted))
    assert "Quoted song" in plugin.private_cleaner.MessageCleaner.extract_raw_message_from_event(_event(quoted))


def test_json_component_subclasses_keep_component_detection(plugin):
    class ExtendedJson(_Json):
        pass

    card = ExtendedJson({"prompt": "Subclass card"})
    assert "Subclass card" in plugin.reply_chain.render_chain_text([card])

