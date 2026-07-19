"""AstrBot 内部增强 API 的可选加载器。

本文件只放高风险内部能力的延迟加载函数。调用方必须接受返回 None
并执行降级逻辑，避免内部 API 变动时影响插件基础功能加载。
"""

from __future__ import annotations

from typing import Any, Callable, NamedTuple

from .public_api import logger


class InternalHookApis(NamedTuple):
    event_type: Any
    registry: Any
    star_map: Any


def load_internal_hook_apis() -> InternalHookApis | None:
    """加载增强提示词追踪需要的内部 handler 注册表 API。"""
    try:
        from astrbot.core.star.star import star_map
        from astrbot.core.star.star_handler import EventType, star_handlers_registry

        return InternalHookApis(EventType, star_handlers_registry, star_map)
    except Exception as e:
        logger.warning(
            "[兼容层] 无法加载 AstrBot 内部 handler 注册表，增强提示词追踪将不可用: %s",
            e,
        )
        return None


def load_call_event_hook() -> Callable[..., Any] | None:
    """加载内部事件 hook 调度器，仅供兼容链路使用。"""
    try:
        from astrbot.core.pipeline.context_utils import call_event_hook

        return call_event_hook
    except Exception as e:
        logger.warning(
            "[兼容层] 无法加载 AstrBot 内部 call_event_hook，虚拟事件兼容链将不可用: %s",
            e,
        )
        return None


def load_aiocqhttp_classes() -> tuple[Any | None, Any | None]:
    """在平台级回退需要时加载 aiocqhttp 专用类型。"""
    try:
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
            AiocqhttpMessageEvent,
        )
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_platform_adapter import (
            AiocqhttpAdapter,
        )

        return AiocqhttpMessageEvent, AiocqhttpAdapter
    except Exception as e:
        logger.warning(
            "[兼容层] 无法加载 aiocqhttp 内部类型，相关平台增强能力将降级: %s",
            e,
        )
        return None, None


def load_skill_prompt_helpers() -> tuple[Any | None, Any | None, Any | None]:
    """加载内部 Skills 提示词辅助，用于增强工具/技能提示保留。"""
    try:
        from astrbot.core.astr_main_agent import _filter_skills_for_current_config
        from astrbot.core.skills.skill_manager import SkillManager, build_skills_prompt

        return SkillManager, build_skills_prompt, _filter_skills_for_current_config
    except Exception as e:
        logger.warning(
            "[兼容层] 无法加载 Skills 内部提示词辅助，Skills 注入增强将降级: %s",
            e,
        )
        return None, None, None


def load_tool_call_prompts() -> tuple[str, str | None]:
    """在当前 AstrBot 暴露相关模板时加载内部工具调用提示词。"""
    try:
        from astrbot.core.astr_main_agent_resources import (
            TOOL_CALL_PROMPT,
            TOOL_CALL_PROMPT_SKILLS_LIKE_MODE,
        )

        return TOOL_CALL_PROMPT, TOOL_CALL_PROMPT_SKILLS_LIKE_MODE
    except Exception:
        try:
            from astrbot.core.astr_main_agent_resources import TOOL_CALL_PROMPT

            return TOOL_CALL_PROMPT, None
        except Exception as e:
            logger.warning(
                "[兼容层] 无法加载工具调用提示模板，工具提示补偿将降级: %s",
                e,
            )
            return "", None


__all__ = [
    "InternalHookApis",
    "load_aiocqhttp_classes",
    "load_call_event_hook",
    "load_internal_hook_apis",
    "load_skill_prompt_helpers",
    "load_tool_call_prompts",
]
