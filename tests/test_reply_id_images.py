"""Resolve quoted pictures when OneBot only supplies a reply identifier."""

import asyncio
import types

import pytest

from test_image_handler import image_handler  # noqa: F401


def run_process(handler, chain, provider_id="vision", **overrides):
    calls = []

    class Provider:
        async def text_chat(self, **kwargs):
            calls.append(kwargs["image_urls"])
            return types.SimpleNamespace(completion_text="recognized " + kwargs["image_urls"][0])

    event = types.SimpleNamespace(
        message_obj=types.SimpleNamespace(message=chain),
        session_id="test-session",
        get_message_outline=lambda: "reply + mention",
    )
    context = types.SimpleNamespace(get_provider_by_id=lambda _: Provider())
    kwargs = {
        "event": event,
        "context": context,
        "enable_image_processing": True,
        "image_to_text_scope": "mention_only",
        "image_to_text_provider_id": provider_id,
        "image_to_text_prompt": "Describe the picture",
        "is_at_message": True,
        "has_trigger_keyword": False,
        "timeout": 5,
        "max_images_per_message": 3,
    }
    kwargs.update(overrides)
    return asyncio.run(handler.ImageHandler.process_message_images(**kwargs)), calls, event


@pytest.mark.parametrize("provider_id", ["vision", ""])
def test_reply_id_image_uses_caption_and_multimodal_paths(image_handler, monkeypatch, provider_id):
    handler, _, _, Reply = image_handler
    quote = Reply([], sender_nickname="Alice", sender_id="42", message_str="")
    quote.id = "original-message"

    async def extract(event, component):
        assert component is quote
        assert component.id == "original-message"
        return ["downloaded.png"]

    monkeypatch.setattr(handler, "extract_quoted_message_images", extract)
    result, calls, event = run_process(handler, [quote], provider_id)
    assert result[0] is True and result[3] is True
    assert "无法获取引用内容" not in result[1]
    if provider_id:
        assert calls == [["downloaded.png"]]
        assert "recognized downloaded.png" in result[1]
    else:
        assert calls == []
        assert result[2] == ["downloaded.png"]
    assert event.message_obj.message[0] is quote
    assert quote.chain == [] and quote.message_str == ""


def test_embedded_images_keep_the_recursive_path_without_remote_fetch(image_handler, monkeypatch):
    handler, _, Image, Reply = image_handler

    async def extract(*args):
        raise AssertionError("Embedded pictures must not be fetched or captioned twice")

    monkeypatch.setattr(handler, "extract_quoted_message_images", extract)
    result, calls, _ = run_process(handler, [Reply([Image("embedded.png")])])
    assert result[3] is True
    assert calls == [["embedded.png"]]


@pytest.mark.parametrize(
    "options",
    [
        {"enable_image_processing": False},
        {"is_at_message": False},
        {"image_to_text_scope": "keyword_only"},
        {"image_to_text_scope": "at_only", "is_at_message": False, "has_trigger_keyword": True},
    ],
)
def test_disabled_or_out_of_scope_requests_do_not_fetch_quotes(image_handler, monkeypatch, options):
    handler, _, _, Reply = image_handler
    fetched = []

    async def extract(*args):
        fetched.append(True)
        return ["quote.png"]

    monkeypatch.setattr(handler, "extract_quoted_message_images", extract)
    result, calls, _ = run_process(handler, [Reply([])], **options)
    assert not fetched and not calls and not result[2] and not result[3]


def test_fetched_and_direct_images_share_the_existing_limit(image_handler, monkeypatch):
    handler, _, Image, Reply = image_handler

    async def extract(*args):
        return ["quote1.png", "quote1.png", "quote2.png", "quote3.png"]

    monkeypatch.setattr(handler, "extract_quoted_message_images", extract)
    result, calls, _ = run_process(
        handler, [Image("direct.png"), Reply([])], max_images_per_message=2
    )
    assert calls == [["direct.png"], ["quote1.png"]]
    assert "recognized quote1.png" in result[1]


@pytest.mark.parametrize("error", [RuntimeError("Unavailable"), asyncio.TimeoutError()])
def test_failed_quote_fetch_keeps_direct_picture_processing(image_handler, monkeypatch, error):
    handler, _, Image, Reply = image_handler

    async def extract(*args):
        raise error

    monkeypatch.setattr(handler, "extract_quoted_message_images", extract)
    result, calls, _ = run_process(handler, [Reply([]), Image("direct.png")])
    assert result[3] is True
    assert calls == [["direct.png"]]


def test_older_astrbot_without_the_quote_extractor_keeps_embedded_images(image_handler, monkeypatch):
    handler, _, Image, Reply = image_handler
    monkeypatch.setattr(handler, "extract_quoted_message_images", None)
    result, calls, _ = run_process(handler, [Reply([Image("embedded.png")])])
    assert result[3] is True
    assert calls == [["embedded.png"]]
