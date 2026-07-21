import asyncio
import os
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PACKAGE = "astrbot_plugin_group_chat_plus"

plugin_package = ModuleType(PLUGIN_PACKAGE)
plugin_package.__path__ = [str(REPOSITORY_ROOT)]
sys.modules.setdefault(PLUGIN_PACKAGE, plugin_package)

utils_package = ModuleType(f"{PLUGIN_PACKAGE}.utils")
utils_package.__path__ = [str(REPOSITORY_ROOT / "utils")]
sys.modules.setdefault(f"{PLUGIN_PACKAGE}.utils", utils_package)

test_runtime = tempfile.TemporaryDirectory()
original_working_directory = Path.cwd()
os.chdir(test_runtime.name)
try:
    from astrbot.api.message_components import Image, Plain, Reply

    from astrbot_plugin_group_chat_plus.utils.image_handler import ImageHandler
finally:
    os.chdir(original_working_directory)


class StubImage(Image):
    async def convert_to_file_path(self) -> str:
        return self.file or ""


class StubProvider:
    def __init__(self) -> None:
        self.image_paths = []

    async def text_chat(self, *, image_urls, **_):
        image_path = image_urls[0]
        self.image_paths.append(image_path)
        return SimpleNamespace(completion_text=f"description:{image_path}")


class StubContext:
    def __init__(self, provider: StubProvider) -> None:
        self.provider = provider

    def get_provider_by_id(self, _provider_id):
        return self.provider

    def get_using_provider(self):
        return self.provider


class StubEvent:
    def __init__(self, message_chain) -> None:
        self.message_obj = SimpleNamespace(message=message_chain)
        self.session_id = "test-session"

    def get_message_outline(self) -> str:
        return "outline"


def make_reply(chain):
    return Reply(
        id="quoted-message",
        chain=chain,
        sender_id="10001",
        sender_nickname="Alice",
        message_str="",
    )


def process_images(message_chain, *, provider_id="vision", max_images=10):
    provider = StubProvider()
    result = asyncio.run(
        ImageHandler.process_message_images(
            StubEvent(message_chain),
            StubContext(provider),
            enable_image_processing=True,
            image_to_text_scope="all",
            image_to_text_provider_id=provider_id,
            image_to_text_prompt="Describe this image.",
            is_at_message=True,
            has_trigger_keyword=False,
            max_images_per_message=max_images,
            self_id="bot",
        )
    )
    return result, provider


def test_analyze_message_collects_images_from_nested_reply_chains():
    first = StubImage(file="quoted-first.png")
    nested = StubImage(file="quoted-nested.png")
    direct = StubImage(file="direct.png")
    chain = [
        make_reply(
            [
                Plain("quoted"),
                first,
                make_reply([nested]),
            ]
        ),
        Plain("question"),
        direct,
    ]

    has_image, has_text, images = ImageHandler._analyze_message(chain)

    assert has_image is True
    assert has_text is True
    assert [image.file for image in images] == [
        "quoted-first.png",
        "quoted-nested.png",
        "direct.png",
    ]


def test_quoted_image_uses_existing_image_to_text_pipeline():
    quoted_image = StubImage(file="quoted.png")

    result, provider = process_images(
        [make_reply([Plain("quoted text "), quoted_image]), Plain("is this true?")]
    )

    should_continue, processed, image_urls, image_retained = result
    assert should_continue is True
    assert image_urls == []
    assert image_retained is True
    assert provider.image_paths == ["quoted.png"]
    assert "[引用 >>> Alice(ID:10001): quoted text " in processed
    assert "[图片内容: description:quoted.png]" in processed
    assert "is this true?" in processed


def test_image_to_text_limit_applies_across_quoted_and_direct_images():
    quoted_first = StubImage(file="quoted-first.png")
    quoted_second = StubImage(file="quoted-second.png")
    direct = StubImage(file="direct.png")

    result, provider = process_images(
        [
            make_reply([quoted_first, quoted_second]),
            Plain("question"),
            direct,
        ],
        max_images=2,
    )

    _, processed, _, _ = result
    assert provider.image_paths == ["quoted-first.png", "quoted-second.png"]
    assert "[图片内容: description:quoted-first.png]" in processed
    assert "[图片内容: description:quoted-second.png]" in processed
    assert processed.count(ImageHandler._image_failure_placeholder()) == 1


def test_multimodal_mode_passes_quoted_images_and_preserves_quote_context():
    quoted_image = StubImage(file="quoted.png")
    direct_image = StubImage(file="direct.png")

    result, provider = process_images(
        [
            make_reply([Plain("quoted text "), quoted_image]),
            Plain("question"),
            direct_image,
        ],
        provider_id="",
    )

    should_continue, processed, image_urls, image_retained = result
    assert should_continue is True
    assert image_retained is True
    assert provider.image_paths == []
    assert image_urls == ["quoted.png", "direct.png"]
    assert "[引用 >>> Alice(ID:10001): quoted text [图片: quoted.png]]" in processed
    assert "question[图片: direct.png]" in processed


def test_disabled_image_processing_strips_images_inside_quotes():
    quoted_image = StubImage(file="quoted-secret-path.png")
    event = StubEvent(
        [make_reply([Plain("quoted text "), quoted_image]), Plain("question")]
    )

    result = asyncio.run(
        ImageHandler.process_message_images(
            event,
            StubContext(StubProvider()),
            enable_image_processing=False,
            image_to_text_scope="all",
            image_to_text_provider_id="vision",
            image_to_text_prompt="Describe this image.",
            is_at_message=True,
            has_trigger_keyword=False,
            self_id="bot",
        )
    )

    should_continue, processed, image_urls, image_retained = result
    assert should_continue is True
    assert image_urls == []
    assert image_retained is False
    assert "quoted text" in processed
    assert "question" in processed
    assert "quoted-secret-path.png" not in processed


def test_empty_reply_chain_falls_back_to_message_string():
    reply = Reply(
        id="quoted-message",
        chain=[],
        sender_id="10001",
        sender_nickname="Alice",
        message_str="fallback quoted text",
    )

    processed = ImageHandler._extract_text_only([reply, Plain("question")])

    assert "[引用 >>> Alice(ID:10001): fallback quoted text]" in processed
    assert "question" in processed
