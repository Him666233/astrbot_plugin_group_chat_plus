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
        Plain=_Plain,
    )
    message_components = _module(
        "astrbot.api.message_components",
        Plain=_Plain,
        At=_At,
        AtAll=_AtAll,
        Image=_Image,
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

    return types.SimpleNamespace(
        reply_chain=reply_chain,
        message_cleaner=message_cleaner,
        platform_ltm=platform_ltm,
        private_cleaner=private_cleaner,
        private_image=private_image,
        Plain=_Plain,
        Image=_Image,
        Reply=_Reply,
        At=_At,
        Video=_Video,
    )


def _quoted_image_reply(Reply, Image, Plain=None, *, image_name="quoted.png"):
    """被引用消息是一张纯图片（message_str 为空，这正是丢失的场景）。"""
    chain = [] if Plain is None else [Plain("被引用的文字")]
    chain.append(Image(image_name))
    return Reply(
        chain,
        sender_nickname="Alice",
        sender_id="42",
        message_str="",  # 平台对纯图片消息给出的就是空字符串
    )


def _event(*components):
    return types.SimpleNamespace(
        message_obj=types.SimpleNamespace(message=list(components))
    )


# ---------------------------------------------------------------------------
# 共享工具
# ---------------------------------------------------------------------------


def test_resolve_reply_content_reads_chain_when_message_str_is_empty(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)

    assert plugin.reply_chain.resolve_reply_content(reply) == "[图片]"


def test_resolve_reply_content_keeps_chain_text(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image, plugin.Plain)

    assert plugin.reply_chain.resolve_reply_content(reply) == "被引用的文字[图片]"


def test_resolve_reply_content_falls_back_to_legacy_text(plugin):
    reply = plugin.Reply(None, message_str="旧版引用文本")

    assert plugin.reply_chain.resolve_reply_content(reply) == "旧版引用文本"


def test_resolve_reply_content_returns_none_when_nothing_is_known(plugin):
    reply = plugin.Reply(None, message_str="", message=None)

    assert plugin.reply_chain.resolve_reply_content(reply) is None


def test_format_reply_component_marks_bot_sender(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)

    formatted = plugin.reply_chain.format_reply_component(reply, self_id="42")

    assert formatted == "[引用 >>> Alice(你)(ID:42): [图片]]"


def test_analyze_chain_finds_quoted_image_and_treats_reply_as_text(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)
    quoted_image = reply.chain[-1]

    has_image, has_text, images = plugin.reply_chain.analyze_chain([reply])

    assert has_image is True
    assert has_text is True
    assert images == [quoted_image]


def test_render_chain_text_assigns_descriptions_by_expanded_order(plugin):
    """引用图片必须拿到它自己的描述，而不是顶层图片的描述。"""
    quoted = _quoted_image_reply(plugin.Reply, plugin.Image, image_name="quoted.png")
    top_level_image = plugin.Image("outer.png")
    chain = [quoted, top_level_image]

    rendered = plugin.reply_chain.render_chain_text(
        chain,
        image_descriptions={0: "引用图", 1: "外层图"},
    )

    assert rendered == (
        "[引用 >>> Alice(ID:42): [图片内容: 引用图]][图片内容: 外层图]"
    )


# ---------------------------------------------------------------------------
# 群聊：message_cleaner
# ---------------------------------------------------------------------------


def test_group_cleaner_keeps_quoted_image_placeholder(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)

    formatted = plugin.message_cleaner.MessageCleaner._format_reply_component(
        reply, self_id=None
    )

    assert formatted == "[引用 >>> Alice(ID:42): [图片]]\n"


def test_group_cleaner_reports_unavailable_only_when_content_is_unknown(plugin):
    reply = plugin.Reply(
        None, sender_nickname="Alice", sender_id="42", message_str=""
    )

    formatted = plugin.message_cleaner.MessageCleaner._format_reply_component(
        reply, self_id=None
    )

    assert formatted == "[引用 >>> Alice(ID:42): (无法获取引用内容)]\n"


def test_group_cleaner_prefers_chain_text_over_empty_message_str(plugin):
    reply = plugin.Reply(
        [plugin.Plain("普通引用")],
        sender_nickname="Alice",
        sender_id="42",
        message_str="",
    )

    formatted = plugin.message_cleaner.MessageCleaner._format_reply_component(
        reply, self_id=None
    )

    assert formatted == "[引用 >>> Alice(ID:42): 普通引用]\n"


# ---------------------------------------------------------------------------
# 群聊：platform_ltm_helper 图片检测
# ---------------------------------------------------------------------------


def test_platform_ltm_detects_image_inside_quoted_message(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)

    assert plugin.platform_ltm.PlatformLTMHelper.has_image_in_message(
        _event(reply, plugin.At("123"))
    )


def test_platform_ltm_detects_top_level_image(plugin):
    assert plugin.platform_ltm.PlatformLTMHelper.has_image_in_message(
        _event(plugin.Image("direct.png"))
    )


def test_platform_ltm_ignores_image_free_message(plugin):
    assert not plugin.platform_ltm.PlatformLTMHelper.has_image_in_message(
        _event(plugin.Plain("只是文字"))
    )


def test_platform_ltm_quoted_image_message_is_not_pure_image(plugin):
    """「引用图片 + @机器人」不应被判成纯图片消息。"""
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)

    event = _event(reply, plugin.At("123"))

    assert not plugin.platform_ltm.PlatformLTMHelper.is_pure_image_message(event)


def test_platform_ltm_pure_image_message_still_detected(plugin):
    event = _event(plugin.Image("only.png"))

    assert plugin.platform_ltm.PlatformLTMHelper.is_pure_image_message(event)


# ---------------------------------------------------------------------------
# 私信
# ---------------------------------------------------------------------------


def test_private_cleaner_keeps_quoted_image_placeholder(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)

    formatted = (
        plugin.private_cleaner.MessageCleaner._format_reply_component(
            reply, self_id=None
        )
    )

    assert formatted == "[引用 >>> Alice(ID:42): [图片]]"


def test_private_cleaner_reports_unavailable_only_when_content_is_unknown(plugin):
    reply = plugin.Reply(
        None, sender_nickname="Alice", sender_id="42", message_str=""
    )

    formatted = (
        plugin.private_cleaner.MessageCleaner._format_reply_component(
            reply, self_id=None
        )
    )

    assert formatted == "[引用 >>> Alice(ID:42): (无法获取引用内容)]"


def test_private_cleaner_matches_group_format(plugin):
    """私信与群聊的引用格式保持一致（`>>>` 分隔符）。"""
    reply = plugin.Reply(
        [plugin.Plain("普通引用")],
        sender_nickname="Alice",
        sender_id="42",
        message_str="",
    )

    group_format = plugin.message_cleaner.MessageCleaner._format_reply_component(
        reply, self_id=None
    ).strip()
    private_format = (
        plugin.private_cleaner.MessageCleaner._format_reply_component(
            reply, self_id=None
        )
    )

    assert private_format == group_format


def test_private_image_handler_uses_shared_reply_format(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)

    formatted = plugin.private_image.ImageHandler._format_special_component(
        reply, self_id=None
    )

    assert formatted == "[引用 >>> Alice(ID:42): [图片]]"


def test_private_image_handler_finds_quoted_image(plugin):
    reply = _quoted_image_reply(plugin.Reply, plugin.Image)
    quoted_image = reply.chain[-1]

    has_image, has_text, images = plugin.private_image.ImageHandler._analyze_message(
        [reply]
    )

    assert has_image is True
    assert has_text is True
    assert images == [quoted_image]


def test_private_image_handler_counts_images_in_expanded_order(plugin):
    quoted = _quoted_image_reply(plugin.Reply, plugin.Image, image_name="quoted.png")
    top_level_image = plugin.Image("outer.png")

    _, _, images = plugin.private_image.ImageHandler._analyze_message(
        [quoted, top_level_image]
    )

    assert [image.name for image in images] == ["quoted.png", "outer.png"]


def test_private_image_handler_keeps_media_out_of_text_flag(plugin):
    """私信链路原语义：视频/语音/文件不计入 has_text。"""
    has_image, has_text, _ = plugin.private_image.ImageHandler._analyze_message(
        [plugin.Image("a.png"), plugin.Video()]
    )

    assert has_image is True
    assert has_text is False


def test_private_image_handler_applies_image_limit_after_recursive_walk(plugin):
    quoted = _quoted_image_reply(plugin.Reply, plugin.Image, image_name="quoted.png")
    top_level_image = plugin.Image("outer.png")

    _, _, images = plugin.private_image.ImageHandler._analyze_message(
        [quoted, top_level_image], max_images=1
    )

    assert [image.name for image in images] == ["quoted.png"]
