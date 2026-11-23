"""按群概率覆盖：解析、钳制、群聊命中、私聊回退。"""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]


class _Logger:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message, *_args, **_kwargs):
        self.infos.append(str(message))

    def warning(self, message, *_args, **_kwargs):
        self.warnings.append(str(message))

    def error(self, *_args, **_kwargs):
        pass

    def debug(self, *_args, **_kwargs):
        pass


def _module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _load(monkeypatch, full_name, path):
    spec = importlib.util.spec_from_file_location(full_name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, full_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pm(monkeypatch):
    logger = _Logger()
    for name, module in (
        ("astrbot", _module("astrbot")),
        ("astrbot.api", _module("astrbot.api", logger=logger)),
        ("astrbot.api.all", _module("astrbot.api.all", logger=logger)),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    package = types.ModuleType("gcp_probability_test")
    package.__path__ = [str(REPO_ROOT / "utils")]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    _load(
        monkeypatch,
        f"{package.__name__}._session_guard",
        REPO_ROOT / "utils" / "_session_guard.py",
    )
    proactive = _module(
        f"{package.__name__}.proactive_chat_manager",
        ProactiveChatManager=types.SimpleNamespace(
            get_temp_probability_boost=lambda _chat_key: 0
        ),
    )
    monkeypatch.setitem(sys.modules, proactive.__name__, proactive)
    module = _load(
        monkeypatch,
        f"{package.__name__}.probability_manager",
        REPO_ROOT / "utils" / "probability_manager.py",
    )
    module.ProbabilityManager._probability_status.clear()
    return module


def _config(**overrides):
    config = {
        "enable_dynamic_reply_probability": False,
        "reply_time_periods": "[]",
        "reply_time_transition_minutes": 30,
        "reply_time_min_factor": 0.1,
        "reply_time_max_factor": 2.0,
        "reply_time_use_smooth_curve": True,
        "enable_probability_hard_limit": False,
        "probability_min_limit": 0.05,
        "probability_max_limit": 0.8,
        "group_probability_overrides": "{}",
    }
    config.update(overrides)
    return config


def test_parse_clamps_and_skips_bad_fields(pm):
    parsed = pm.ProbabilityManager._parse_group_probability_overrides(
        {
            "819557069": {
                "initial_probability": 1.4,
                "after_reply_probability": -0.2,
            },
            "100": "not-a-dict",
            "200": {"initial_probability": "nope", "after_reply_probability": 0.2},
        }
    )
    assert parsed["819557069"] == {
        "initial_probability": 1.0,
        "after_reply_probability": 0.0,
    }
    assert "100" not in parsed
    assert parsed["200"] == {"after_reply_probability": 0.2}


def test_initialize_rejects_invalid_json(pm):
    pm.ProbabilityManager.initialize(_config(group_probability_overrides="{"))
    assert pm.ProbabilityManager._group_probability_overrides == {}


def test_initialize_empty_table(pm):
    pm.ProbabilityManager.initialize(_config(group_probability_overrides="{}"))
    assert pm.ProbabilityManager._group_probability_overrides == {}


def test_group_hit_private_fallback_and_empty_table(pm):
    async def scenario():
        pm.ProbabilityManager.initialize(
            _config(
                group_probability_overrides=(
                    '{"819557069": {"initial_probability": 0.03, '
                    '"after_reply_probability": 0.2}}'
                )
            )
        )
        group_probability = await pm.ProbabilityManager.get_current_probability(
            "aiocqhttp", False, "819557069", 0.02
        )
        private_probability = await pm.ProbabilityManager.get_current_probability(
            "aiocqhttp", True, "819557069", 0.02
        )
        other_group = await pm.ProbabilityManager.get_current_probability(
            "aiocqhttp", False, "1", 0.02
        )
        await pm.ProbabilityManager.boost_probability(
            "aiocqhttp", False, "819557069", 0.8, 120
        )
        await pm.ProbabilityManager.boost_probability(
            "aiocqhttp", True, "819557069", 0.8, 120
        )
        group_key = pm.ProbabilityManager.get_chat_key("aiocqhttp", False, "819557069")
        private_key = pm.ProbabilityManager.get_chat_key("aiocqhttp", True, "819557069")
        group_boost = pm.ProbabilityManager._probability_status[group_key][
            "reply_boost_probability"
        ]
        private_boost = pm.ProbabilityManager._probability_status[private_key][
            "reply_boost_probability"
        ]
        pm.ProbabilityManager.initialize(_config(group_probability_overrides="{}"))
        pm.ProbabilityManager._probability_status.clear()
        fallback = await pm.ProbabilityManager.get_current_probability(
            "aiocqhttp", False, "819557069", 0.02
        )
        return (
            group_probability,
            private_probability,
            other_group,
            group_boost,
            private_boost,
            fallback,
        )

    (
        group_probability,
        private_probability,
        other_group,
        group_boost,
        private_boost,
        fallback,
    ) = asyncio.run(scenario())
    assert group_probability == pytest.approx(0.03)
    assert private_probability == pytest.approx(0.02)
    assert other_group == pytest.approx(0.02)
    assert group_boost == pytest.approx(0.2)
    assert private_boost == pytest.approx(0.8)
    assert fallback == pytest.approx(0.02)
