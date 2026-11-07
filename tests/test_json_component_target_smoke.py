"""Optional component-level smoke against an externally supplied AstrBot source file."""

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest


@pytest.mark.skipif(not os.environ.get("GCP_TARGET_COMPONENTS"), reason="set GCP_TARGET_COMPONENTS for component-only smoke")
def test_actual_target_json_component_renders_allowlisted_identity(monkeypatch):
    target = Path(os.environ["GCP_TARGET_COMPONENTS"])
    assert target.is_file()

    core = types.ModuleType("astrbot.core")
    core.astrbot_config = {}
    core.file_token_service = types.SimpleNamespace()
    core.logger = types.SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None)
    utils = types.ModuleType("astrbot.core.utils")
    path_module = types.ModuleType("astrbot.core.utils.astrbot_path")
    path_module.get_astrbot_temp_path = lambda *a, **k: ""
    io_module = types.ModuleType("astrbot.core.utils.io")
    io_module.download_file = lambda *a, **k: None
    media_module = types.ModuleType("astrbot.core.utils.media_utils")
    media_module.MediaResolver = type("MediaResolver", (), {})
    media_module.file_uri_to_path = lambda value: value
    media_module.is_file_uri = lambda value: False
    packages = (
        types.ModuleType("astrbot"), core,
        types.ModuleType("astrbot.core.message"), utils, path_module,
        io_module, media_module,
    )
    for module in packages:
        monkeypatch.setitem(sys.modules, module.__name__, module)

    name = "astrbot.core.message.components"
    spec = importlib.util.spec_from_file_location(name, target)
    components = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, components)
    spec.loader.exec_module(components)

    helper_spec = importlib.util.spec_from_file_location(
        "json_card_target_smoke", Path(__file__).parents[1] / "utils" / "json_card_utils.py"
    )
    helper = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper)

    card = components.Json({"meta": {"music": {"title": "Synthetic", "url": "https://music.163.com/#/song?id=123&token=REDACTED"}}})
    assert helper.is_json_component(card)
    rendered = helper.render_json_component(card)
    assert "Synthetic" in rendered and "https://music.163.com/#/song?id=123" in rendered
    assert "REDACTED" not in rendered
