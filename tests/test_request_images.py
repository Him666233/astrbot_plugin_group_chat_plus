"""Exercise the real request hook without importing the AstrBot runtime."""

import ast
import asyncio
import logging
import sys
import types
from pathlib import Path

import pytest


class _Event:
    def __init__(self, extras):
        self.extras = extras

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)

    def set_extra(self, key, value):
        self.extras[key] = value


@pytest.fixture
def request_hook(monkeypatch):
    root = Path(__file__).parents[1]
    package = "chat_plus_request_test_package"
    reply = types.ModuleType(f"{package}.utils.reply_handler")
    for node in ast.parse(
        (root / "utils/reply_handler.py").read_text(encoding="utf-8")
    ).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("PLUGIN_"):
                    setattr(reply, target.id, ast.literal_eval(node.value))

    tools = types.ModuleType(f"{package}.utils.tools_reminder")
    tools.ToolsReminder = types.SimpleNamespace(
        _extract_tools_from_container=lambda _: []
    )
    skills = types.ModuleType("astrbot.core.skills.skill_manager")
    skills.SkillManager = lambda: types.SimpleNamespace(list_skills=lambda **_: [])
    skills.build_skills_prompt = lambda _: ""
    for name in (
        package,
        f"{package}.utils",
        "astrbot",
        "astrbot.core",
        "astrbot.core.skills",
    ):
        module = types.ModuleType(name)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)
    for module in (reply, tools, skills):
        monkeypatch.setitem(sys.modules, module.__name__, module)

    tree = ast.parse((root / "main.py").read_text(encoding="utf-8"))
    plugin = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ChatPlus"
    )
    methods = [
        node
        for node in plugin.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in ("_snapshot_request_before_rewrite", "on_llm_request")
    ]
    for method in methods:
        if method.name == "on_llm_request":
            method.decorator_list = []
    isolated = ast.Module(
        body=[
            ast.ImportFrom(
                module="__future__", names=[ast.alias(name="annotations")], level=0
            ),
            ast.ClassDef(
                name="ChatPlus", bases=[], keywords=[], body=methods, decorator_list=[]
            ),
        ],
        type_ignores=[],
    )
    namespace = {
        "__name__": f"{package}.main",
        "__package__": package,
        "logger": logging.getLogger(__name__),
        "SystemPromptRewriter": types.SimpleNamespace(
            rewrite=lambda **_: types.SimpleNamespace(
                confidence="high", merged_system_prompt="system"
            )
        ),
    }
    exec(  # noqa: S102 -- Load only repository-owned hook methods.
        compile(ast.fix_missing_locations(isolated), str(root / "main.py"), "exec"),
        namespace,
    )
    subject = namespace["ChatPlus"]()
    subject.debug_mode = False
    subject._check_compliance_status = lambda: None
    subject._merge_per_plugin_prompt = lambda prompt, _: prompt
    subject._merge_per_plugin_contexts = lambda contexts, _: contexts
    subject._extract_third_party_prompt_additions = lambda *_: []
    subject._extract_third_party_context_additions = lambda *_: []
    return subject, reply


@pytest.mark.parametrize(
    ("plugin_images", "injections", "expected"),
    [
        ([], None, ["quoted.png", "core.png"]),
        ([], {"memory": {"prompt_added": "memory"}}, ["quoted.png", "core.png"]),
        (
            ["direct.png"],
            {"memory": {"contexts_added": [{"role": "system", "content": "memory"}]}},
            ["direct.png", "quoted.png", "core.png"],
        ),
        (
            ["quoted.png"],
            {"memory": {"system_prompt_added": "memory"}},
            ["quoted.png", "core.png"],
        ),
        (
            ["direct.png"],
            {"media": {"image_urls_added": ["added.png", "quoted.png", "direct.png"]}},
            ["direct.png", "added.png", "quoted.png", "core.png"],
        ),
    ],
)
def test_existing_images_survive_request_rewrite(
    request_hook, plugin_images, injections, expected
):
    subject, constants = request_hook
    event = _Event(
        {
            constants.PLUGIN_REQUEST_MARKER: True,
            constants.PLUGIN_CUSTOM_CONTEXTS: [],
            constants.PLUGIN_CUSTOM_SYSTEM_PROMPT: "system",
            constants.PLUGIN_CUSTOM_PROMPT: "full prompt",
            constants.PLUGIN_IMAGE_URLS: plugin_images,
            "_gcp_per_plugin_injections": injections,
        }
    )
    image_part = object()
    req = types.SimpleNamespace(
        prompt="current message",
        contexts=[],
        system_prompt="system",
        image_urls=["quoted.png", "core.png"],
        audio_urls=[],
        extra_user_content_parts=[image_part],
        func_tool=None,
    )

    asyncio.run(subject.on_llm_request(event, req))

    assert req.image_urls == expected
    assert req.extra_user_content_parts == [image_part]
    assert req.prompt == "full prompt"
    assert event.get_extra(constants.PLUGIN_REQUEST_MARKER) is None
