"""Regression tests for quoted-image handling.

The plugin normally runs inside AstrBot.  These tests provide a small set of
message-component doubles so the pure message-chain logic can be tested
without installing the whole AstrBot runtime.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest


class _Logger:
    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class _BaseMessageComponent:
    pass


class _Plain(_BaseMessageComponent):
    def __init__(self, text):
        self.text = text


class _Image(_BaseMessageComponent):
    def __init__(self, name):
        self.name = name

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
    pass


class _At(_BaseMessageComponent):
    pass


class _AtAll(_BaseMessageComponent):
    pass


@pytest.fixture
def image_handler(monkeypatch):
    """Load image_handler with lightweight AstrBot module stubs."""

    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api_all = types.ModuleType("astrbot.api.all")
    message_components = types.ModuleType("astrbot.api.message_components")
    core = types.ModuleType("astrbot.core")
    core_message = types.ModuleType("astrbot.core.message")
    core_components = types.ModuleType("astrbot.core.message.components")

    api_all.AstrMessageEvent = object
    api_all.Context = object
    api_all.BaseMessageComponent = _BaseMessageComponent
    api_all.Image = _Image
    api_all.Plain = _Plain
    api_all.logger = _Logger()

    message_components.Face = _Face
    message_components.At = _At
    message_components.AtAll = _AtAll
    message_components.Reply = _Reply

    class _Video(_BaseMessageComponent):
        pass

    class _Record(_BaseMessageComponent):
        pass

    class _File(_BaseMessageComponent):
        pass

    core_components.Video = _Video
    core_components.Record = _Record
    core_components.File = _File

    modules = {
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.all": api_all,
        "astrbot.api.message_components": message_components,
        "astrbot.core": core,
        "astrbot.core.message": core_message,
        "astrbot.core.message.components": core_components,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    package_name = "group_chat_plus_test_package"
    package = types.ModuleType(package_name)
    package.__path__ = [str(Path(__file__).parents[1])]
    utils_package = types.ModuleType(f"{package_name}.utils")
    utils_package.__path__ = [str(Path(__file__).parents[1] / "utils")]
    cache_module = types.ModuleType(f"{package_name}.utils.image_description_cache")
    cache_module.ImageDescriptionCache = object
    formatter_module = types.ModuleType(f"{package_name}.utils.ai_error_formatter")
    formatter_module.format_ai_error = lambda error, label: f"{label}: {error}"

    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, f"{package_name}.utils", utils_package)
    monkeypatch.setitem(
        sys.modules,
        f"{package_name}.utils.image_description_cache",
        cache_module,
    )
    monkeypatch.setitem(
        sys.modules,
        f"{package_name}.utils.ai_error_formatter",
        formatter_module,
    )

    module_name = f"{package_name}.utils.image_handler"
    spec = importlib.util.spec_from_file_location(
        module_name,
        Path(__file__).parents[1] / "utils" / "image_handler.py",
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module, _Plain, _Image, _Reply


def test_analyze_message_finds_images_inside_reply_chain(image_handler):
    handler, Plain, Image, Reply = image_handler
    quoted_image = Image("quoted.png")
    message = [
        Plain("请看看"),
        Reply(
            [Plain("被引用的文字"), quoted_image],
            sender_nickname="Alice",
            sender_id="42",
        ),
    ]

    has_image, has_text, images = handler.ImageHandler._analyze_message(message)

    assert has_image is True
    assert has_text is True
    assert images == [quoted_image]


def test_analyze_message_applies_image_limit_after_recursive_walk(image_handler):
    handler, Plain, Image, Reply = image_handler
    first = Image("first.png")
    quoted = Image("quoted.png")
    last = Image("last.png")
    message = [first, Reply([Plain("引用"), quoted]), last]

    _, _, images = handler.ImageHandler._analyze_message(message, max_images=2)

    assert images == [first, quoted]


def test_reply_nesting_depth_is_bounded(image_handler):
    handler, Plain, Image, Reply = image_handler
    nested = Image("too-deep.png")
    for _ in range(handler._MAX_REPLY_NESTING_DEPTH + 1):
        nested = Reply([nested])

    has_image, has_text, images = handler.ImageHandler._analyze_message([nested])

    assert has_image is False
    assert has_text is True
    assert images == []


def test_render_keeps_image_description_order_across_reply_chain(image_handler):
    handler, Plain, Image, Reply = image_handler
    message = [
        Plain("前"),
        Image("outer.png"),
        Reply(
            [Plain("引用"), Image("quoted.png")],
            sender_nickname="Alice",
            sender_id="42",
        ),
        Image("after.png"),
    ]

    rendered = handler.ImageHandler._render_message_chain(
        message,
        image_descriptions={0: "外图", 1: "引用图", 2: "后图"},
    )

    assert rendered == (
        "前[图片内容: 外图]"
        "[引用 >>> Alice(ID:42): 引用[图片内容: 引用图]]\n"
        "[图片内容: 后图]"
    )


def test_extract_text_only_removes_nested_images_but_keeps_quote_text(image_handler):
    handler, Plain, Image, Reply = image_handler
    message = [
        Plain("当前消息"),
        Reply(
            [Plain("引用消息"), Image("quoted.png")],
            sender_nickname="Alice",
            sender_id="42",
        ),
    ]

    text = handler.ImageHandler._extract_text_only(message)

    assert text == "当前消息[引用 >>> Alice(ID:42): 引用消息]"


def test_format_reply_uses_message_fallback_and_marks_bot_sender(image_handler):
    handler, _, _, Reply = image_handler
    reply = Reply(
        chain=None,
        sender_nickname="水原千鹤",
        sender_id="3683026476",
        message_str="旧版引用文本",
    )

    formatted = handler.ImageHandler._format_reply_component(
        reply,
        self_id="3683026476",
    )

    assert formatted == "[引用 >>> 水原千鹤(你)(ID:3683026476): 旧版引用文本]\n"
