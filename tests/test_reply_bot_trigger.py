import importlib.util
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "utils" / "message_processor.py"

test_runtime = tempfile.TemporaryDirectory()
original_working_directory = Path.cwd()
os.chdir(test_runtime.name)
try:
    from astrbot.api.message_components import At, Reply

    spec = importlib.util.spec_from_file_location(
        "gcp_message_processor_test",
        MODULE_PATH,
    )
    message_processor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(message_processor)
finally:
    os.chdir(original_working_directory)

MessageProcessor = message_processor.MessageProcessor


class StubEvent:
    unified_msg_origin = "bot:GroupMessage:test"

    def __init__(self, components, message_text=""):
        self.message_obj = SimpleNamespace(message=components)
        self._message_text = message_text

    def get_self_id(self):
        return "749732852"

    def get_message_str(self):
        return self._message_text


def test_reply_to_bot_triggers_by_default():
    event = StubEvent([Reply(id="1", sender_id="749732852")])

    assert MessageProcessor.is_at_message(event)


def test_reply_to_bot_does_not_trigger_when_switch_is_disabled():
    event = StubEvent([Reply(id="1", sender_id="749732852")])

    assert not MessageProcessor.is_at_message(
        event,
        reply_bot_skip_probability=False,
    )


def test_reply_to_other_user_never_triggers():
    event = StubEvent([Reply(id="1", sender_id="123456")])

    assert not MessageProcessor.is_at_message(
        event,
        reply_bot_skip_probability=True,
    )


def test_at_bot_still_triggers_when_reply_switch_is_disabled():
    event = StubEvent([At(qq="749732852")])

    assert MessageProcessor.is_at_message(
        event,
        reply_bot_skip_probability=False,
    )


def test_reply_switch_is_enabled_and_ordered_before_poke_switch():
    schema = json.loads(
        (REPOSITORY_ROOT / "_conf_schema.json").read_text(encoding="utf-8")
    )
    keys = list(schema)

    assert schema["reply_bot_skip_probability"]["default"] is True
    assert keys.index("reply_bot_skip_probability") < keys.index(
        "poke_bot_skip_probability"
    )
