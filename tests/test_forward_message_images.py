"""Regression tests for merged-forward image preservation."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest


class _Forward:
    def __init__(self, message_id):
        self.id = message_id


class _Plain:
    def __init__(self, text):
        self.text = text


class _Event:
    def __init__(self, message):
        self.message_obj = types.SimpleNamespace(message=message, timestamp=0)
        self.message_str = ""
        self.extras = {}

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_sender_name(self):
        return "forwarder"

    def get_sender_id(self):
        return "100"


@pytest.fixture
def parser_module(monkeypatch):
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, debug=lambda *a, **k: None)
    core = types.ModuleType("astrbot.core")
    core_message = types.ModuleType("astrbot.core.message")
    components = types.ModuleType("astrbot.core.message.components")
    components.Forward = _Forward
    components.Plain = _Plain
    platform = types.ModuleType("astrbot.core.platform")
    event_module = types.ModuleType("astrbot.core.platform.astr_message_event")
    event_module.AstrMessageEvent = object
    for name, module in {
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.core": core,
        "astrbot.core.message": core_message,
        "astrbot.core.message.components": components,
        "astrbot.core.platform": platform,
        "astrbot.core.platform.astr_message_event": event_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    module_name = "forward_message_parser_test"
    spec = importlib.util.spec_from_file_location(
        module_name,
        Path(__file__).parents[1] / "utils" / "forward_message_parser.py",
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_forward_images_are_exposed_after_forward_is_replaced(parser_module):
    parser = parser_module
    event = _Event([_Forward("forward-1")])

    async def call_action(action, **params):
        assert action == "get_forward_msg"
        return {
            "data": [
                {
                    "sender": {"nickname": "Alice", "user_id": "42"},
                    "message": [
                        {"type": "image", "data": {"url": "https://img/one.jpg"}},
                        {"type": "image", "data": {"file": "https://img/two.jpg"}},
                    ],
                }
            ]
        }

    # The parser's call-action lookup reads event.bot.
    event.bot = types.SimpleNamespace(call_action=call_action)
    parsed = await parser.ForwardMessageParser.try_parse_and_replace(
        event,
        include_sender_info=True,
        include_timestamp=False,
    )

    assert parsed is True
    assert event.extras[parser.FORWARD_IMAGE_URLS_EXTRA] == [
        "https://img/one.jpg",
        "https://img/two.jpg",
    ]
    assert isinstance(event.message_obj.message[0], _Plain)
    assert event.message_obj.message[0].text.count("[图片]") == 2


@pytest.mark.asyncio
async def test_nested_forward_images_are_collected_once(parser_module):
    parser = parser_module
    event = _Event([_Forward("outer")])

    async def call_action(action, **params):
        message_id = str(params.get("message_id") or params.get("id"))
        if message_id == "outer":
            return {
                "data": [
                    {
                        "sender": {"nickname": "Alice", "user_id": "42"},
                        "message": [
                            {"type": "forward", "data": {"id": "inner"}},
                        ],
                    }
                ]
            }
        return {
            "data": [
                {
                    "sender": {"nickname": "Bob", "user_id": "43"},
                    "message": [
                        {"type": "image", "data": {"url": "https://img/nested.jpg"}},
                    ],
                }
            ]
        }

    event.bot = types.SimpleNamespace(call_action=call_action)
    await parser.ForwardMessageParser.try_parse_and_replace(
        event,
        include_sender_info=True,
        include_timestamp=False,
    )

    assert event.extras[parser.FORWARD_IMAGE_URLS_EXTRA] == [
        "https://img/nested.jpg"
    ]
