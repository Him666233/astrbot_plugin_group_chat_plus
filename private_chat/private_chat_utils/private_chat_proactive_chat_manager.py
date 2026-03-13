"""
主动对话管理器 - Proactive Chat Manager

负责管理AI主动发起对话的功能，包括：
1. 沉默时长检测
2. 概率触发机制
3. 临时概率提升（模拟真人"等待回应"状态）
4. 时间段控制和平滑过渡
5. 用户活跃度检测
6. 失败处理和冷却机制

作者: Him666233
版本: v1.2.1

v1.2.0 更新：
- 支持其他插件的 on_llm_request 钩子注入（如 emotionai）
- 通过创建虚拟 event 对象并手动触发钩子实现兼容
"""

import time
import asyncio
import random
import threading
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from pathlib import Path
import json

from astrbot import logger
from astrbot.core.platform import AstrMessageEvent
from astrbot.core.star import Context
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.message.components import Plain, At, BaseMessageComponent
from astrbot.core.provider.entities import ProviderRequest
from astrbot.api.all import AstrBotMessage, MessageType, MessageMember

# 🆕 v1.2.0: 导入钩子调用相关模块
from astrbot.core.star.star_handler import EventType

# 🆕 v1.2.0: 标记键名（与 reply_handler.py 保持一致）
PLUGIN_REQUEST_MARKER = "_group_chat_plus_request"
PLUGIN_CUSTOM_CONTEXTS = "_group_chat_plus_contexts"
PLUGIN_CUSTOM_SYSTEM_PROMPT = "_group_chat_plus_system_prompt"
PLUGIN_CUSTOM_PROMPT = "_group_chat_plus_prompt"
PLUGIN_IMAGE_URLS = "_group_chat_plus_image_urls"


class ProactiveChatManager:
    """
    主动对话管理器

    核心功能：
    1. 维护每个群聊的沉默计时器和状态
    2. 定期检查是否应该触发主动对话
    3. 处理时间段禁用和平滑过渡
    4. 管理临时概率提升机制（AI发言后等待回应）
    5. 处理连续失败和冷却
    """

    # ========== 类变量 - 全局状态管理 ==========

    # 线程锁（用于保护共享状态）
    _lock = threading.Lock()

    # 每个群聊的状态
    # 格式: {chat_key: {...}}
    _chat_states: Dict[str, dict] = {}

    # 后台检查任务
    _background_task: Optional[asyncio.Task] = None
    _is_running: bool = False

    # 状态持久化路径
    _data_dir: Optional[str] = None
    # 调试日志开关（与 main.py 同款）
    _debug_mode: bool = False
    # 模块级全局开关（由 main.py 统一赋值：utils.proactive_chat_manager.DEBUG_MODE = True/False）
    try:
        from . import DEBUG_MODE as DEBUG_MODE  # type: ignore
    except Exception:
        DEBUG_MODE = False

    # 🆕 临时概率提升状态
    # 格式: {chat_key: {"boost_value": 0.5, "boost_until": timestamp, "triggered_by_proactive": True}}
    _temp_probability_boost: Dict[str, dict] = {}

    # ========== 🔧 配置参数集中提取（避免运行时多次读取） ==========
    # 吐槽系统配置
    _enable_complaint_system: bool = True
    _complaint_trigger_threshold: int = 2
    _complaint_level_light: int = 2
    _complaint_level_medium: int = 3
    _complaint_level_strong: int = 4
    _complaint_probability_light: float = 0.3
    _complaint_probability_medium: float = 0.6
    _complaint_probability_strong: float = 0.8
    _complaint_max_accumulation: int = 15
    _complaint_decay_on_success: int = 2
    _complaint_decay_check_interval: int = 6 * 3600
    _complaint_decay_no_failure_threshold: int = 12 * 3600
    _complaint_decay_amount: int = 1
    # 自适应主动对话配置
    _enable_adaptive_proactive: bool = True
    _interaction_score_min: int = 10
    _interaction_score_max: int = 100
    _score_increase_on_success: int = 15
    _score_decrease_on_fail: int = 8
    _score_quick_reply_bonus: int = 5
    _score_multi_user_bonus: int = 10
    _score_streak_bonus: int = 5
    _score_revival_bonus: int = 20
    _interaction_score_decay_rate: int = 2
    # 主动对话基础配置
    _proactive_enabled_groups: list = []
    _proactive_silence_threshold: int = 600
    _proactive_cooldown_duration: int = 1800
    _proactive_max_consecutive_failures: int = 2
    _proactive_failure_threshold_perturbation: float = 0.0
    _proactive_failure_sequence_probability: float = -1.0
    _proactive_require_user_activity: bool = True
    _proactive_min_user_messages: int = 3
    _proactive_probability: float = 0.3
    _proactive_user_activity_window: int = 300
    # 时间段控制配置
    _proactive_enable_quiet_time: bool = False
    _proactive_quiet_start: str = "23:00"
    _proactive_quiet_end: str = "07:00"
    _proactive_transition_minutes: int = 30
    _enable_dynamic_proactive_probability: bool = False
    _proactive_time_periods: str = "[]"
    _proactive_time_transition_minutes: int = 45
    _proactive_time_min_factor: float = 0.0
    _proactive_time_max_factor: float = 2.0
    _proactive_time_use_smooth_curve: bool = True
    _proactive_check_interval: int = 60
    _proactive_temp_boost_probability: float = 0.5
    _proactive_temp_boost_duration: int = 120
    # 主动对话提示词配置
    _proactive_prompt: str = ""
    _proactive_retry_prompt: str = ""
    # 注意力感知主动对话配置
    _enable_attention_mechanism: bool = False
    _proactive_use_attention: bool = True
    _proactive_attention_reference_probability: float = 0.7
    _proactive_attention_rank_weights: str = "1:55,2:25,3:12,4:8"
    _proactive_attention_max_selected_users: int = 2
    _proactive_focus_last_user_probability: float = 0.6
    # 上下文和消息格式配置
    _max_context_messages: int = 20
    _include_timestamp: bool = True
    _include_sender_info: bool = True
    # 记忆注入配置
    _enable_memory_injection: bool = False
    _memory_plugin_mode: str = "legacy"
    _livingmemory_top_k: int = 5
    _livingmemory_version: str = "v1"
    # 工具提醒配置
    _enable_tools_reminder: bool = False
    _tools_reminder_persona_filter: bool = False
    # 超时警告配置
    _proactive_generation_timeout_warning: int = 15
    # 📦 消息缓存配置（用于读取缓存时过滤过期消息）
    _pending_cache_max_count: int = 10  # 缓存最大条数
    _pending_cache_ttl_seconds: int = 1800  # 缓存过期时间（秒）
    # 系统保护上限（与 main.py 保持一致）
    _CACHE_MAX_COUNT_LIMIT: int = 50  # 缓存条数硬上限
    # 🔄 AI重复消息拦截配置（由 main.py 传入）
    _enable_duplicate_filter: bool = True  # 启用AI重复消息拦截
    _duplicate_filter_check_count: int = 5  # 重复检测参考消息条数
    _enable_duplicate_time_limit: bool = True  # 启用重复检测时效性判断
    _duplicate_filter_time_limit: int = 1800  # 重复检测时效(秒)
    # 🔒 重复检测硬上限常量（与 main.py 保持一致，防止内存泄漏）
    _DUPLICATE_CHECK_COUNT_LIMIT: int = 50  # 检查条数硬上限
    _DUPLICATE_CACHE_SIZE_LIMIT: int = 100  # 缓存大小硬上限
    _DUPLICATE_TIME_LIMIT_MAX: int = 7200  # 时效硬上限（2小时）
    # 🆕 主动对话@转换配置
    _enable_proactive_at_conversion: bool = False
    # 🔄 共享的AI回复缓存引用（由 main.py 传入，用于重复检测）
    # 格式: {chat_id: [{"content": "回复内容", "timestamp": 时间戳}]}
    # 注意：主动对话和普通对话共享同一个缓存，确保跨模式也能检测重复
    _shared_replies_cache: Optional[Dict[str, list]] = None
    _CACHE_TTL_LIMIT: int = 7200  # 缓存过期时间硬上限（2小时）

    # ========== 初始化和生命周期 ==========

    @classmethod
    def initialize(cls, data_dir: str):
        """
        初始化管理器

        Args:
            data_dir: 数据存储目录
        """
        cls._data_dir = data_dir
        cls._load_states_from_disk()
        if getattr(cls, "_debug_mode", False) or getattr(cls, "DEBUG_MODE", False):
            logger.info("[主动对话管理器] 已初始化")

    @classmethod
    async def start_background_task(
        cls, context: Context, config: dict, plugin_instance
    ):
        """
        启动后台检查任务

        Args:
            context: AstrBot Context对象
            config: 插件配置
            plugin_instance: 插件实例
        """
        if cls._is_running:
            logger.warning("[主动对话管理器] 后台任务已在运行")
            return

        # 同步调试开关
        try:
            cls._debug_mode = bool(getattr(plugin_instance, "debug_mode", False))
        except Exception:
            cls._debug_mode = False

        # ========== 🔧 直接使用传入的配置值 ==========
        # 说明：配置由 main.py 统一提取后传入，此处直接使用传入的值，
        # 不再提供默认值（避免 AstrBot 平台多次读取配置的问题）
        # 吐槽系统配置
        cls._enable_complaint_system = config["enable_complaint_system"]
        cls._complaint_trigger_threshold = config["complaint_trigger_threshold"]
        cls._complaint_level_light = config["complaint_level_light"]
        cls._complaint_level_medium = config["complaint_level_medium"]
        cls._complaint_level_strong = config["complaint_level_strong"]
        cls._complaint_probability_light = config["complaint_probability_light"]
        cls._complaint_probability_medium = config["complaint_probability_medium"]
        cls._complaint_probability_strong = config["complaint_probability_strong"]
        cls._complaint_max_accumulation = config["complaint_max_accumulation"]
        cls._complaint_decay_on_success = config["complaint_decay_on_success"]
        cls._complaint_decay_check_interval = config["complaint_decay_check_interval"]
        cls._complaint_decay_no_failure_threshold = config[
            "complaint_decay_no_failure_threshold"
        ]
        cls._complaint_decay_amount = config["complaint_decay_amount"]
        # 自适应主动对话配置
        cls._enable_adaptive_proactive = config["enable_adaptive_proactive"]
        cls._interaction_score_min = config["interaction_score_min"]
        cls._interaction_score_max = config["interaction_score_max"]
        cls._score_increase_on_success = config["score_increase_on_success"]
        cls._score_decrease_on_fail = config["score_decrease_on_fail"]
        cls._score_quick_reply_bonus = config["score_quick_reply_bonus"]
        cls._score_multi_user_bonus = config["score_multi_user_bonus"]
        cls._score_streak_bonus = config["score_streak_bonus"]
        cls._score_revival_bonus = config["score_revival_bonus"]
        cls._interaction_score_decay_rate = config["interaction_score_decay_rate"]
        # 主动对话基础配置
        cls._proactive_enabled_groups = config["proactive_enabled_groups"]
        cls._proactive_silence_threshold = config["proactive_silence_threshold"]
        cls._proactive_cooldown_duration = config["proactive_cooldown_duration"]
        cls._proactive_max_consecutive_failures = config[
            "proactive_max_consecutive_failures"
        ]
        cls._proactive_failure_threshold_perturbation = config[
            "proactive_failure_threshold_perturbation"
        ]
        cls._proactive_failure_sequence_probability = config[
            "proactive_failure_sequence_probability"
        ]
        cls._proactive_require_user_activity = config["proactive_require_user_activity"]
        cls._proactive_min_user_messages = config["proactive_min_user_messages"]
        cls._proactive_probability = config["proactive_probability"]
        cls._proactive_user_activity_window = config["proactive_user_activity_window"]
        # 时间段控制配置
        cls._proactive_enable_quiet_time = config["proactive_enable_quiet_time"]
        cls._proactive_quiet_start = config["proactive_quiet_start"]
        cls._proactive_quiet_end = config["proactive_quiet_end"]
        cls._proactive_transition_minutes = config["proactive_transition_minutes"]
        cls._enable_dynamic_proactive_probability = config[
            "enable_dynamic_proactive_probability"
        ]
        cls._proactive_time_periods = config["proactive_time_periods"]
        cls._proactive_time_transition_minutes = config[
            "proactive_time_transition_minutes"
        ]
        cls._proactive_time_min_factor = config["proactive_time_min_factor"]
        cls._proactive_time_max_factor = config["proactive_time_max_factor"]
        cls._proactive_time_use_smooth_curve = config["proactive_time_use_smooth_curve"]
        cls._proactive_check_interval = config["proactive_check_interval"]
        cls._proactive_temp_boost_probability = config[
            "proactive_temp_boost_probability"
        ]
        cls._proactive_temp_boost_duration = config["proactive_temp_boost_duration"]
        # 主动对话提示词配置
        cls._proactive_prompt = config["proactive_prompt"]
        cls._proactive_retry_prompt = config["proactive_retry_prompt"]
        # 注意力感知主动对话配置
        cls._enable_attention_mechanism = config["enable_attention_mechanism"]
        cls._proactive_use_attention = config["proactive_use_attention"]
        cls._proactive_attention_reference_probability = config[
            "proactive_attention_reference_probability"
        ]
        cls._proactive_attention_rank_weights = config[
            "proactive_attention_rank_weights"
        ]
        cls._proactive_attention_max_selected_users = config[
            "proactive_attention_max_selected_users"
        ]
        cls._proactive_focus_last_user_probability = config[
            "proactive_focus_last_user_probability"
        ]
        # 上下文和消息格式配置
        cls._max_context_messages = config["max_context_messages"]
        cls._include_timestamp = config["include_timestamp"]
        cls._include_sender_info = config["include_sender_info"]
        # 记忆注入配置
        cls._enable_memory_injection = config["enable_memory_injection"]
        cls._memory_plugin_mode = config["memory_plugin_mode"]
        cls._livingmemory_top_k = config["livingmemory_top_k"]
        cls._livingmemory_version = config.get("livingmemory_version", "v1")
        # 工具提醒配置
        cls._enable_tools_reminder = config["enable_tools_reminder"]
        cls._tools_reminder_persona_filter = config.get(
            "tools_reminder_persona_filter", False
        )
        # 超时警告配置
        cls._proactive_generation_timeout_warning = config[
            "proactive_generation_timeout_warning"
        ]
        # 📦 消息缓存配置（用于读取缓存时过滤过期消息）
        # 直接从 main.py 传递的配置字典中获取（已在 main.py 中完成验证和硬上限保护）
        cls._pending_cache_max_count = config["pending_cache_max_count"]
        cls._pending_cache_ttl_seconds = config["pending_cache_ttl_seconds"]
        if cls._debug_mode:
            logger.info(
                f"[主动对话管理器] 📦 缓存配置: 最大条数={cls._pending_cache_max_count}, "
                f"过期时间={cls._pending_cache_ttl_seconds}秒"
            )

        # 🔄 AI重复消息拦截配置（直接使用 main.py 传入的已处理值，硬上限已在 main.py 中应用）
        cls._enable_duplicate_filter = config["enable_duplicate_filter"]
        cls._duplicate_filter_check_count = config["duplicate_filter_check_count"]
        cls._enable_duplicate_time_limit = config["enable_duplicate_time_limit"]
        cls._duplicate_filter_time_limit = config["duplicate_filter_time_limit"]
        # 🆕 主动对话@转换配置
        cls._enable_proactive_at_conversion = config["enable_proactive_at_conversion"]
        # 🔄 获取共享的AI回复缓存引用（与普通对话共享，用于跨模式重复检测）
        if hasattr(plugin_instance, "recent_replies_cache"):
            cls._shared_replies_cache = plugin_instance.recent_replies_cache
        else:
            cls._shared_replies_cache = {}
            logger.warning("[主动对话管理器] ⚠️ 未找到共享回复缓存，将使用独立缓存")
        if cls._debug_mode:
            logger.info(
                f"[主动对话管理器] 🔄 重复消息拦截配置: 启用={cls._enable_duplicate_filter}, "
                f"检查条数={cls._duplicate_filter_check_count}, "
                f"时效性={cls._enable_duplicate_time_limit}, "
                f"时效={cls._duplicate_filter_time_limit}秒, "
                f"共享缓存={'已连接' if cls._shared_replies_cache is not None else '独立'}"
            )

        # 🆕 v1.2.0: AI回复内容过滤配置（与普通回复流程共享相同配置）
        cls._enable_output_content_filter = config["enable_output_content_filter"]
        cls._output_content_filter_rules = config["output_content_filter_rules"]
        cls._enable_save_content_filter = config["enable_save_content_filter"]
        cls._save_content_filter_rules = config["save_content_filter_rules"]
        # 获取共享的 content_filter 实例（与普通对话共享，确保过滤逻辑一致）
        if hasattr(plugin_instance, "content_filter"):
            cls._content_filter = plugin_instance.content_filter
        else:
            # 如果没有共享实例，创建独立的过滤器（冗余设计，确保功能可用）
            from .content_filter import ContentFilterManager

            cls._content_filter = ContentFilterManager(
                enable_output_filter=cls._enable_output_content_filter,
                output_filter_rules=cls._output_content_filter_rules,
                enable_save_filter=cls._enable_save_content_filter,
                save_filter_rules=cls._save_content_filter_rules,
                debug_mode=cls._debug_mode,
            )
            logger.warning("[主动对话管理器] ⚠️ 未找到共享内容过滤器，已创建独立实例")
        if cls._debug_mode:
            logger.info(
                f"[主动对话管理器] 🧹 内容过滤配置: "
                f"输出过滤={'启用' if cls._enable_output_content_filter else '禁用'}({len(cls._output_content_filter_rules)}条规则), "
                f"保存过滤={'启用' if cls._enable_save_content_filter else '禁用'}({len(cls._save_content_filter_rules)}条规则), "
                f"过滤器={'共享' if hasattr(plugin_instance, 'content_filter') else '独立'}"
            )

        # 🆕 配置合理性检查：吐槽系统配置（使用已提取的类变量）
        cls._validate_complaint_config_internal()

        cls._is_running = True
        cls._background_task = asyncio.create_task(
            cls._background_check_loop(context, config, plugin_instance)
        )
        if cls._debug_mode or getattr(cls, "DEBUG_MODE", False):
            logger.info("✅ [主动对话管理器] 后台检查任务已启动")

    @classmethod
    async def stop_background_task(cls):
        """停止后台检查任务"""
        cls._is_running = False
        if cls._background_task:
            cls._background_task.cancel()
            try:
                await cls._background_task
            except asyncio.CancelledError:
                pass
        cls._save_states_to_disk()
        if cls._debug_mode or getattr(cls, "DEBUG_MODE", False):
            logger.info("⏹️ [主动对话管理器] 后台检查任务已停止")

    @classmethod
    def _validate_complaint_config(cls, config):
        """
        🔧 修复：验证吐槽系统配置的合理性

        检查规则：
        1. 吐槽系统基于累积失败次数 (total_proactive_failures) 触发，不受冷却影响
        2. 连续失败次数 (consecutive_failures) 用于判断是否进入冷却，与吐槽系统分离
        3. 配置检查：吐槽等级应该 <= max_failures * 2，否则可能很难触发

        说明：
        - 旧版本中吐槽系统依赖 consecutive_failures，导致冷却后吐槽系统被重置
        - 新版本中吐槽系统使用独立的 total_proactive_failures，持续累积
        - 只有成功互动时才会重置 total_proactive_failures

        Args:
            config: 插件配置字典 或 插件实例（会自动提取config属性）
        """
        # 🆕 智能处理：如果传入的是插件实例，提取其 config 属性
        if hasattr(config, "config"):
            config = config.config

        # 🔧 使用字典键访问替代 config.get()，避免 astrBot 平台多次读取配置的问题
        # 检查是否启用了吐槽系统
        enable_complaint = (
            config["enable_complaint_system"]
            if "enable_complaint_system" in config
            else True
        )
        if not enable_complaint:
            return

        max_failures = (
            config["proactive_max_consecutive_failures"]
            if "proactive_max_consecutive_failures" in config
            else 3
        )
        complaint_trigger = (
            config["complaint_trigger_threshold"]
            if "complaint_trigger_threshold" in config
            else 2
        )
        complaint_light = (
            config["complaint_level_light"] if "complaint_level_light" in config else 2
        )
        complaint_medium = (
            config["complaint_level_medium"]
            if "complaint_level_medium" in config
            else 3
        )
        complaint_strong = (
            config["complaint_level_strong"]
            if "complaint_level_strong" in config
            else 4
        )

        warnings = []
        infos = []

        # 🔧 修复后的说明：吐槽系统基于累积失败次数，可以 >= max_failures
        infos.append(
            f" 吐槽系统基于累积失败次数 (total_proactive_failures)，"
            f"不受冷却影响，可以持续累积"
        )
        infos.append(
            f"  - 连续失败次数 (consecutive_failures): 用于冷却判断，达到 {max_failures} 次进入冷却"
        )
        infos.append(
            f"  - 累积失败次数 (total_proactive_failures): 用于吐槽系统，只在成功互动时重置"
        )

        # 合理性建议（不是强制要求）
        max_complaint = max(complaint_light, complaint_medium, complaint_strong)
        if max_complaint > max_failures * 3:
            warnings.append(
                f"⚠️ 最高吐槽等级 ({max_complaint}) 过高（> {max_failures * 3}），"
                f"可能需要很长时间才能触发。建议设置在 {max_failures} ~ {max_failures * 2} 之间"
            )

        # 输出信息
        if infos or warnings:
            logger.info("📢 ========== 主动对话吐槽系统配置说明 ==========")
            for info in infos:
                logger.info(info)
            if warnings:
                logger.warning("\n⚠️ 配置建议")
                for idx, warning in enumerate(warnings, 1):
                    logger.warning(f"  {idx}. {warning}")
            logger.info(
                f"\n💡 当前配置："
                f"\n  - 最大连续失败次数（冷却阈值）: {max_failures}"
                f"\n  - 吐槽触发阈值: {complaint_trigger}"
                f"\n  - 轻度吐槽阈值: {complaint_light}"
                f"\n  - 明显吐槽阈值: {complaint_medium}"
                f"\n  - 强烈吐槽阈值: {complaint_strong}"
            )
            logger.info("====================================================")

    @classmethod
    def _validate_complaint_config_internal(cls):
        """
        🔧 内部验证方法：使用已提取的类变量验证吐槽系统配置的合理性

        此方法在 start_background_task 中配置提取完成后调用
        """
        # 检查是否启用了吐槽系统
        if not cls._enable_complaint_system:
            return

        max_failures = cls._proactive_max_consecutive_failures
        complaint_trigger = cls._complaint_trigger_threshold
        complaint_light = cls._complaint_level_light
        complaint_medium = cls._complaint_level_medium
        complaint_strong = cls._complaint_level_strong

        warnings = []
        infos = []

        # 🔧 修复后的说明：吐槽系统基于累积失败次数，可以 >= max_failures
        infos.append(
            f" 吐槽系统基于累积失败次数 (total_proactive_failures)，"
            f"不受冷却影响，可以持续累积"
        )
        infos.append(
            f"  - 连续失败次数 (consecutive_failures): 用于冷却判断，达到 {max_failures} 次进入冷却"
        )
        infos.append(
            f"  - 累积失败次数 (total_proactive_failures): 用于吐槽系统，只在成功互动时重置"
        )

        # 合理性建议（不是强制要求）
        max_complaint = max(complaint_light, complaint_medium, complaint_strong)
        if max_complaint > max_failures * 3:
            warnings.append(
                f"⚠️ 最高吐槽等级 ({max_complaint}) 过高（> {max_failures * 3}），"
                f"可能需要很长时间才能触发。建议设置在 {max_failures} ~ {max_failures * 2} 之间"
            )

        # 输出信息
        if infos or warnings:
            logger.info("📢 ========== 主动对话吐槽系统配置说明 ==========")
            for info in infos:
                logger.info(info)
            if warnings:
                logger.warning("\n⚠️ 配置建议：")
                for idx, warning in enumerate(warnings, 1):
                    logger.warning(f"  {idx}. {warning}")
            logger.info(
                f"\n💡 当前配置："
                f"\n  - 最大连续失败次数（冷却阈值）: {max_failures}"
                f"\n  - 吐槽触发阈值: {complaint_trigger}"
                f"\n  - 轻度吐槽阈值: {complaint_light}"
                f"\n  - 明显吐槽阈值: {complaint_medium}"
                f"\n  - 强烈吐槽阈值: {complaint_strong}"
            )
            logger.info("====================================================")

    # ========== 工具方法 ==========

    @staticmethod
    def parse_rank_weights(weight_str: str) -> list:
        """
        解析排名权重配置字符串

        Args:
            weight_str: 权重配置字符串，格式：'1:55,2:25,3:12,4:8'

        Returns:
            权重列表，例如 [0.55, 0.25, 0.12, 0.08]
            如果解析失败，返回默认权重 [0.55, 0.25, 0.12, 0.08]

        Examples:
            >>> parse_rank_weights('1:55,2:25,3:12,4:8')
            [0.55, 0.25, 0.12, 0.08]
            >>> parse_rank_weights('1:70,2:30')
            [0.7, 0.3]
            >>> parse_rank_weights('1:0.4,2:0.3,3:0.2,4:0.1')
            [0.4, 0.3, 0.2, 0.1]
        """
        default_weights = [0.55, 0.25, 0.12, 0.08]

        try:
            if not weight_str or not isinstance(weight_str, str):
                logger.warning(
                    f"[权重解析] 配置为空或类型错误: {weight_str}，使用默认权重"
                )
                return default_weights

            # 去除空格
            weight_str = weight_str.strip()

            # 按逗号分割各个排名配置
            parts = weight_str.split(",")
            if not parts:
                logger.warning("[权重解析] 配置格式错误（无内容），使用默认权重")
                return default_weights

            # 解析每个 "排名:权重" 对
            rank_weight_dict = {}
            for part in parts:
                part = part.strip()
                if ":" not in part:
                    logger.warning(
                        f"[权重解析] 跳过格式错误的配置项: {part}（缺少冒号）"
                    )
                    continue

                try:
                    rank_str, weight_str_part = part.split(":", 1)
                    rank = int(rank_str.strip())
                    weight = float(weight_str_part.strip())

                    if rank < 1:
                        logger.warning(
                            f"[权重解析] 跳过无效排名: {rank}（排名必须>=1）"
                        )
                        continue

                    if weight < 0:
                        logger.warning(
                            f"[权重解析] 跳过负数权重: {weight}（权重必须>=0）"
                        )
                        continue

                    rank_weight_dict[rank] = weight

                except ValueError as e:
                    logger.warning(
                        f"[权重解析] 跳过无法解析的配置项: {part}，错误: {e}"
                    )
                    continue

            if not rank_weight_dict:
                logger.warning("[权重解析] 没有有效的权重配置，使用默认权重")
                return default_weights

            # 检查排名是否从1开始连续递增
            sorted_ranks = sorted(rank_weight_dict.keys())
            if sorted_ranks[0] != 1:
                logger.warning(
                    f"[权重解析] 排名必须从1开始，当前最小排名: {sorted_ranks[0]}，使用默认权重"
                )
                return default_weights

            for i, rank in enumerate(sorted_ranks, start=1):
                if rank != i:
                    logger.warning(
                        f"[权重解析] 排名必须连续递增，发现断层: {sorted_ranks}，使用默认权重"
                    )
                    return default_weights

            # 构造权重列表（按排名顺序）
            weights = [rank_weight_dict[rank] for rank in sorted_ranks]

            # 归一化权重（使总和为1）
            total_weight = sum(weights)
            if total_weight <= 0:
                logger.warning(
                    f"[权重解析] 权重总和必须>0，当前: {total_weight}，使用默认权重"
                )
                return default_weights

            normalized_weights = [w / total_weight for w in weights]

            logger.info(
                f"[权重解析] 成功解析 {len(normalized_weights)} 个排名权重: "
                f"{', '.join([f'第{i + 1}名={w:.2%}' for i, w in enumerate(normalized_weights)])}"
            )

            return normalized_weights

        except Exception as e:
            logger.warning(f"[权重解析] 解析失败: {e}，使用默认权重", exc_info=True)
            return default_weights

    @classmethod
    def filter_expired_cached_messages(cls, cached_messages_raw: list) -> list:
        """
        📦 过滤过期的缓存消息

        在读取缓存消息时调用，确保只返回未过期且在数量限制内的消息。
        这解决了主动对话触发时，缓存中可能存在已过期但未被清理的消息的问题。

        Args:
            cached_messages_raw: 原始缓存消息列表

        Returns:
            过滤后的缓存消息列表（已移除过期消息，并限制数量）
        """
        if not cached_messages_raw:
            return []

        current_time = time.time()

        # 直接使用类变量（已在 start_background_task 中从 main.py 同步）
        # 类变量已经过 main.py 的硬上限保护，这里再加一层保护以防万一
        cache_ttl = min(
            max(60, int(cls._pending_cache_ttl_seconds)), cls._CACHE_TTL_LIMIT
        )
        cache_max_count = min(
            max(1, int(cls._pending_cache_max_count)), cls._CACHE_MAX_COUNT_LIMIT
        )

        # 过滤过期消息
        filtered_messages = []
        expired_count = 0
        for msg in cached_messages_raw:
            if isinstance(msg, dict):
                # 获取消息时间戳（兼容不同的字段名）
                msg_timestamp = msg.get("message_timestamp") or msg.get("timestamp", 0)
                if current_time - msg_timestamp < cache_ttl:
                    filtered_messages.append(msg)
                else:
                    expired_count += 1
            else:
                # 非字典类型的消息直接保留（兼容 AstrBotMessage 对象）
                filtered_messages.append(msg)

        # 🔧 修复：在限制数量前先按 message_timestamp 排序，确保保留最新的消息
        # 避免并发写入导致的顺序问题
        if len(filtered_messages) > 1:
            filtered_messages.sort(
                key=lambda m: (
                    (m.get("message_timestamp") or m.get("timestamp", 0))
                    if isinstance(m, dict)
                    else (getattr(m, "timestamp", 0) or 0)
                )
            )

        # 限制数量（保留最新的消息）
        if len(filtered_messages) > cache_max_count:
            removed_count = len(filtered_messages) - cache_max_count
            filtered_messages = filtered_messages[-cache_max_count:]
            if cls._debug_mode:
                logger.info(
                    f"[主动对话-缓存过滤] 数量超限，移除最旧的 {removed_count} 条消息"
                )

        # 输出过滤日志
        if expired_count > 0 and cls._debug_mode:
            logger.info(
                f"[主动对话-缓存过滤] 已过滤 {expired_count} 条过期消息（超过{cache_ttl}秒）"
            )

        return filtered_messages

    @classmethod
    def check_duplicate_message(cls, chat_key: str, content: str) -> bool:
        """
        🔄 检查主动对话内容是否与最近发送的消息重复

        使用与普通对话共享的缓存，确保跨模式也能检测重复。

        Args:
            chat_key: 群聊唯一标识（格式: platform:type:chat_id）
            content: 要检查的消息内容

        Returns:
            True 表示是重复消息，应该拦截；False 表示不是重复消息
        """
        # 检查是否启用重复消息拦截
        if not cls._enable_duplicate_filter:
            return False

        if not content or not content.strip():
            return False

        # 检查共享缓存是否可用
        if cls._shared_replies_cache is None:
            if cls._debug_mode:
                logger.warning("[主动对话-重复检测] 共享缓存不可用，跳过重复检测")
            return False

        content_clean = content.strip()
        current_time = time.time()

        # 从 chat_key 中提取 chat_id（格式: platform:type:chat_id）
        # 共享缓存使用 chat_id 作为 key，与普通对话保持一致
        try:
            chat_id = chat_key.split(":")[-1] if ":" in chat_key else chat_key
        except Exception:
            chat_id = chat_key

        # 获取该会话的回复缓存
        if chat_id not in cls._shared_replies_cache:
            cls._shared_replies_cache[chat_id] = []

        # 根据配置决定是否启用时效性过滤
        if cls._enable_duplicate_time_limit:
            time_limit = max(60, cls._duplicate_filter_time_limit)
            # 清理过期的回复记录
            cls._shared_replies_cache[chat_id] = [
                reply
                for reply in cls._shared_replies_cache[chat_id]
                if current_time - reply.get("timestamp", 0) < time_limit
            ]

        # 检查是否与最近N条回复重复
        check_count = max(1, cls._duplicate_filter_check_count)
        for recent_reply in cls._shared_replies_cache[chat_id][-check_count:]:
            recent_content = recent_reply.get("content", "")
            recent_timestamp = recent_reply.get("timestamp", 0)

            # 如果启用时效性判断，检查消息是否在时效内
            if cls._enable_duplicate_time_limit:
                time_limit = max(60, cls._duplicate_filter_time_limit)
                if current_time - recent_timestamp >= time_limit:
                    continue  # 超过时效，跳过此条

            if recent_content and content_clean == recent_content.strip():
                if cls._debug_mode:
                    logger.warning(
                        f"🚫 [主动对话-重复检测] 检测到与最近回复重复，将拦截发送\n"
                        f"  最近回复: {recent_content[:100]}...\n"
                        f"  当前内容: {content_clean[:100]}..."
                    )
                return True

        return False

    @classmethod
    def convert_at_tags_to_components(
        cls,
        content: str,
        platform_id: str,
        debug_mode: bool = False,
        platform_name: str = "",
    ) -> Tuple[bool, MessageChain]:
        """
        🆕 v1.2.0: 将 AI 生成内容中的 [at:QQ号] 标签转换为真实的 At 组件

        仅在 aiocqhttp 平台下生效，其他平台直接返回原始文本消息链。

        Args:
            content: AI 生成的消息内容
            platform_id: 平台ID（适配器实例ID）
            debug_mode: 是否开启调试模式
            platform_name: 平台类型名称（如 "aiocqhttp"），用于辅助平台检测

        Returns:
            Tuple[bool, MessageChain]: (是否成功转换, 消息链)
            - 如果转换成功，返回 (True, 包含At组件的消息链)
            - 如果转换失败或不需要转换，返回 (False, 纯文本消息链)
        """
        # 匹配合法的 [at:数字] 标签（大小写不敏感，因为AI可能生成 [At:ID] 格式）
        valid_at_pattern = re.compile(r"\[at:(\d+)\]", re.IGNORECASE)

        # 检查是否包含有效的 @ 标签
        if not valid_at_pattern.search(content):
            if debug_mode:
                logger.info(
                    "[主动对话-@转换] 消息中不包含有效的 [at:QQ号] 标签，跳过转换"
                )
            return False, MessageChain().message(content)

        # 检查平台是否为 aiocqhttp
        # 同时检查 platform_id（实例ID）和 platform_name（平台类型名），兼容自定义实例ID
        is_aiocqhttp = (
            "aiocqhttp" in platform_id.lower()
            or "cqhttp" in platform_id.lower()
            or "aiocqhttp" in platform_name.lower()
            or "cqhttp" in platform_name.lower()
        )

        if not is_aiocqhttp:
            if debug_mode:
                logger.info(
                    f"[主动对话-@转换] 当前平台 ({platform_id}) 不是 aiocqhttp，跳过 @ 转换"
                )
            return False, MessageChain().message(content)

        try:
            # 构建包含 At 组件的消息链
            chain: List[BaseMessageComponent] = []
            last_idx = 0

            for match in valid_at_pattern.finditer(content):
                start, end = match.span()

                # 处理标签前的文本
                if start > last_idx:
                    text_before = content[last_idx:start]
                    if text_before:
                        chain.append(Plain(text_before))

                # 获取 QQ 号并创建 At 组件
                target_id = match.group(1)
                chain.append(At(qq=target_id))
                # 在 @ 后添加一个空格，避免与后续内容粘连
                chain.append(Plain(" "))

                last_idx = end

            # 处理最后一个标签后的剩余文本
            if last_idx < len(content):
                remaining_text = content[last_idx:]
                if remaining_text:
                    chain.append(Plain(remaining_text))

            # 如果成功构建了消息链
            if chain:
                message_chain = MessageChain(chain)
                if debug_mode:
                    at_count = len(valid_at_pattern.findall(content))
                    logger.info(
                        f"[主动对话-@转换] ✅ 成功转换 {at_count} 个 @ 标签为真实 At 组件"
                    )
                return True, message_chain
            else:
                # 如果消息链为空，返回原始内容
                return False, MessageChain().message(content)

        except Exception as e:
            # 转换失败时，记录错误并返回原始文本消息链
            logger.warning(f"[主动对话-@转换] ⚠️ 转换失败，将发送原始文本消息: {e}")
            return False, MessageChain().message(content)

    @classmethod
    def record_proactive_reply(cls, chat_key: str, content: str):
        """
        🔄 记录主动对话发送的消息到共享缓存（用于后续重复检测）

        使用与普通对话共享的缓存，确保跨模式也能检测重复。

        Args:
            chat_key: 群聊唯一标识（格式: platform:type:chat_id）
            content: 发送的消息内容
        """
        if not content or not content.strip():
            return

        # 检查共享缓存是否可用
        if cls._shared_replies_cache is None:
            if cls._debug_mode:
                logger.warning("[主动对话-重复检测] 共享缓存不可用，跳过记录")
            return

        # 从 chat_key 中提取 chat_id（格式: platform:type:chat_id）
        # 共享缓存使用 chat_id 作为 key，与普通对话保持一致
        try:
            chat_id = chat_key.split(":")[-1] if ":" in chat_key else chat_key
        except Exception:
            chat_id = chat_key

        if chat_id not in cls._shared_replies_cache:
            cls._shared_replies_cache[chat_id] = []

        # 添加到共享缓存
        cls._shared_replies_cache[chat_id].append(
            {"content": content.strip(), "timestamp": time.time()}
        )

        # 🔒 限制缓存大小（保留配置条数的2倍，最少10条，但不超过硬上限）
        max_cache_size = min(
            max(10, cls._duplicate_filter_check_count * 2),
            cls._DUPLICATE_CACHE_SIZE_LIMIT,
        )
        if len(cls._shared_replies_cache[chat_id]) > max_cache_size:
            # 丢弃最旧的消息，保留最新的
            cls._shared_replies_cache[chat_id] = cls._shared_replies_cache[chat_id][
                -max_cache_size:
            ]

        if cls._debug_mode:
            logger.info(
                f"[主动对话-重复检测] 已记录回复到共享缓存，当前缓存数: {len(cls._shared_replies_cache[chat_id])}"
            )

    # ========== 状态管理 ==========

    @classmethod
    def _get_default_state(cls) -> dict:
        """
        获取默认状态字典（包含所有字段）

        Returns:
            包含所有字段的默认状态字典
        """
        return {
            # 原有字段
            "last_bot_reply_time": 0,  # 上次AI回复时间
            "last_user_message_time": 0,  # 上次用户发言时间
            "consecutive_failures": 0,  # 连续主动对话失败次数（用于判断是否进入冷却）
            "total_proactive_failures": 0,  # 🆕 累积的主动对话失败次数（用于吐槽系统，不会在冷却时重置）
            "is_in_cooldown": False,  # 是否在冷却期
            "cooldown_until": 0,  # 冷却结束时间
            "user_message_count": 0,  # 距离上次AI回复后的用户消息数
            "last_proactive_time": 0,  # 上次主动对话时间
            "user_message_timestamps": [],  # 用户消息时间戳列表（用于活跃度检测）
            "silent_failures": 0,  # 连续沉默失败次数
            "proactive_attempts_count": 0,  # 主动对话连续尝试计数
            "last_proactive_content": None,  # 🆕 上一次主动对话的内容（用于重试时提醒AI）
            # 🆕 v1.2.0 防误判核心字段
            "proactive_active": False,  # 主动对话是否处于活跃待判定状态（只有成功发送后才为True）
            "proactive_outcome_recorded": False,  # 当前主动对话是否已记录结果（防止重复判定）
            # 🆕 v1.2.0 互动评分系统字段
            "interaction_score": 50,  # 互动评分(0-100)，初始50分
            "successful_interactions": 0,  # 成功互动总次数
            "failed_interactions": 0,  # 失败互动总次数
            "last_success_time": 0,  # 上次成功互动时间
            "consecutive_successes": 0,  # 连续成功次数
            "last_score_decay_time": time.time(),  # 上次评分衰减时间
            "quick_reply_count": 0,  # 快速回复次数(30秒内)
            "multi_user_reply_count": 0,  # 多人回复次数
            # 🆕 注意力用户追踪字段
            "last_attention_user_id": None,  # 上一次主动对话时的最高注意力用户ID
            "last_attention_user_name": None,  # 上一次主动对话时的最高注意力用户名称
            # 🆕 累积失败次数相关字段
            "last_proactive_success_time": 0,  # 上次主动对话成功时间（用于时间衰减）
            "last_complaint_decay_time": time.time(),  # 上次吐槽衰减检查时间
            # 🆕 扰动因子相关字段（在开始新一轮连续尝试时计算一次）
            "current_effective_max_failures": -1,  # 当前轮次的有效最大失败阈值（-1表示未设置，使用配置值）
        }

    @classmethod
    def get_chat_state(cls, chat_key: str) -> dict:
        """
        获取群聊状态（确保包含所有字段，兼容旧数据）

        Args:
            chat_key: 群聊唯一标识

        Returns:
            群聊状态字典
        """
        if chat_key not in cls._chat_states:
            cls._chat_states[chat_key] = cls._get_default_state()
        else:
            # 兼容性处理：为旧数据补充缺失字段
            state = cls._chat_states[chat_key]
            default_state = cls._get_default_state()
            for key, value in default_state.items():
                if key not in state:
                    state[key] = value
        return cls._chat_states[chat_key]

    @classmethod
    def _initialize_chat_state(cls, chat_key: str):
        """
        初始化群聊状态（内部方法，在锁保护下调用）

        Args:
            chat_key: 群聊唯一标识
        """
        if chat_key not in cls._chat_states:
            cls._chat_states[chat_key] = cls._get_default_state()

    @classmethod
    def record_user_message(cls, chat_key: str):
        """
        记录用户消息（用于沉默计时器和活跃度检测）

        Args:
            chat_key: 群聊唯一标识 (格式: "aiocqhttp:group:879646332")
        """
        with cls._lock:
            if chat_key not in cls._chat_states:
                cls._initialize_chat_state(chat_key)
            current_time = time.time()
            state = cls._chat_states[chat_key]
            state["last_user_message_time"] = current_time
            state["silent_failures"] = 0  # 重置连续失败计数
            # 更新用户消息计数和时间戳（用于活跃度检测）
            state["user_message_count"] += 1
            state["user_message_timestamps"].append(current_time)
            # 清理过期的时间戳（保留最近24小时内的）
            activity_window = 24 * 3600  # 24小时
            state["user_message_timestamps"] = [
                ts
                for ts in state["user_message_timestamps"]
                if current_time - ts <= activity_window
            ]
            # 同步消息计数与时间戳数量，避免数据不一致
            state["user_message_count"] = len(state["user_message_timestamps"])

    @classmethod
    def record_bot_reply(cls, chat_key: str, is_proactive: bool = True):
        """
        记录AI回复

        Args:
            chat_key: 群聊唯一标识 (格式: "aiocqhttp:group:879646332")
            is_proactive: 是否为主动对话
        """
        with cls._lock:
            if chat_key not in cls._chat_states:
                cls._initialize_chat_state(chat_key)
            current_time = time.time()
            state = cls._chat_states[chat_key]
            state["last_bot_reply_time"] = current_time
            if is_proactive:
                state["last_proactive_time"] = current_time
                # 🆕 v1.2.0: 激活主动对话检测（表示主动对话已成功发送，等待判定）
                state["proactive_active"] = True
                # 🆕 v1.2.0: 重置结果记录标记（表示这次主动对话还未判定结果）
                state["proactive_outcome_recorded"] = False
                # 记录一次主动对话尝试
                try:
                    state["proactive_attempts_count"] = (
                        int(state.get("proactive_attempts_count", 0)) + 1
                    )
                except Exception:
                    state["proactive_attempts_count"] = 1

                if cls._debug_mode:
                    logger.info(f"🎯 [主动对话激活] 群{chat_key} - 已发送，等待判定")
            else:
                # v1.2.0: 普通回复时，如果有活跃的主动对话，需要关闭它（双重保险）
                # 这防止了在其他流程中遗漏关闭主动对话状态的情况
                if state.get("proactive_active", False):
                    if cls._debug_mode:
                        logger.info(
                            f"🔒 [主动对话关闭] 群{chat_key} - 普通回复时关闭活跃的主动对话"
                        )
                    state["proactive_active"] = False
                    # 注意：不设置 outcome_recorded，因为这不是一个判定，只是关闭

            state["silent_failures"] = 0  # 重置连续失败计数
            # 重置用户消息计数（这是"距离上次AI回复后的用户消息数"）
            state["user_message_count"] = 0
            # 清空用户消息时间戳列表（确保活跃度检测正确）
            # 注意：这里不清空所有时间戳，只清空"距离上次AI回复后"的时间戳
            # 但为了确保活跃度检测正确，我们需要清空所有时间戳
            # 因为活跃度检测应该基于"距离上次AI回复后"的用户消息
            state["user_message_timestamps"] = []

    @classmethod
    def record_proactive_failure(
        cls,
        chat_key: str,
        max_failures: int,
        cooldown_duration: int,
        config: dict = None,
    ):
        """
        记录主动对话失败（仅在未记录过时执行）

        Args:
            chat_key: 群聊唯一标识
            max_failures: 最大连续失败次数
            cooldown_duration: 冷却持续时间(秒)
            config: 插件配置（可选，用于评分系统）
        """
        state = cls.get_chat_state(chat_key)

        # 🆕 v1.2.0: 防止重复记录失败
        if state.get("proactive_outcome_recorded", False):
            if cls._debug_mode:
                logger.info(
                    f"[主动对话失败] 群{chat_key} - 本次主动对话已记录过结果，跳过"
                )
            return

        # 🆕 v1.2.0: 关闭主动对话检测（已判定失败）
        state["proactive_active"] = False
        # 标记为已记录
        state["proactive_outcome_recorded"] = True

        # 🔧 修复：同时累积两个失败计数器（加入概率门控）

        failure_prob = cls._proactive_failure_sequence_probability

        increment_consecutive = True
        if failure_prob == 0:
            # 0 = 永远不进入连续失败尝试（仅累积总失败次数，用于吐槽系统）
            increment_consecutive = False
        elif failure_prob == -1:
            # -1 = 不进行概率检测，行为与旧版本一致
            increment_consecutive = True
        elif 0 < failure_prob <= 1:
            roll = random.random()
            increment_consecutive = roll < failure_prob
            if cls._debug_mode:
                logger.info(
                    f"[主动对话失败-概率] 群{chat_key} - 配置={failure_prob:.2f}, 掷骰={roll:.2f}, "
                    f"计入连续失败={'是' if increment_consecutive else '否'}"
                )
        else:
            # 异常取值时退回旧逻辑
            increment_consecutive = True

        # 🆕 累积失败次数（带上限保护）

        max_complaint_accumulation = cls._complaint_max_accumulation
        old_total = state.get("total_proactive_failures", 0)
        state["total_proactive_failures"] = min(
            old_total + 1, max_complaint_accumulation
        )

        # 🆕 v1.2.0 更新互动评分
        cls.record_proactive_failure_for_score_internal(chat_key)

        # 重置用户消息计数和时间戳列表
        state["user_message_count"] = 0
        state["user_message_timestamps"] = []

        if not increment_consecutive:
            # 本次失败不参与连续失败计数，直接返回（仅影响吐槽系统等累积逻辑）
            if cls._debug_mode:
                logger.info(
                    f"[主动对话失败-计数] 群{chat_key} - 仅累积失败次数，"
                    f"连续失败未增加，当前连续失败={state.get('consecutive_failures', 0)}, "
                    f"累积失败={old_total}→{state['total_proactive_failures']}"
                )
            return

        # 计入连续失败计数并进行冷却判断
        state["consecutive_failures"] += 1  # 用于冷却判断

        if cls._debug_mode:
            logger.info(
                f"[主动对话失败-计数] 群{chat_key} - "
                f"连续失败={state['consecutive_failures']} / 阈值={max_failures}, "
                f"累积失败={old_total}→{state['total_proactive_failures']}, "
                f"冷却时长={cooldown_duration}秒"
            )

        if state["consecutive_failures"] >= max_failures:
            # 达到最大失败次数，进入冷却
            failure_count = state[
                "consecutive_failures"
            ]  # 保存失败次数，避免被重置后无法正确记录
            cls.enter_cooldown(chat_key, cooldown_duration)
            # 🔧 修复：日志中显示本轮有效阈值
            effective_threshold = state.get(
                "current_effective_max_failures", max_failures
            )
            logger.info(
                f"⚠️ [主动对话失败] 群{chat_key} - "
                f"连续失败{failure_count}次(本轮阈值={effective_threshold})，进入冷却期{cooldown_duration}秒"
            )

    @classmethod
    def enter_cooldown(cls, chat_key: str, duration: int):
        """
        进入冷却期

        Args:
            chat_key: 群聊唯一标识
            duration: 冷却持续时间(秒)
        """
        state = cls.get_chat_state(chat_key)
        state["is_in_cooldown"] = True
        state["cooldown_until"] = time.time() + duration
        state["consecutive_failures"] = 0  # 🔧 重置连续失败次数（用于下一轮冷却判断）
        state[
            "current_effective_max_failures"
        ] = -1  # 🔧 重置扰动阈值（下一轮重新计算）
        # 🔧 注意：不重置 total_proactive_failures，它会持续累积用于吐槽系统
        # 只有成功互动时才会重置 total_proactive_failures
        # 进入冷却时，取消临时概率提升并重置连续尝试
        try:
            cls.deactivate_temp_probability_boost(chat_key, "进入冷却期")
        except Exception:
            pass
        state["proactive_attempts_count"] = 0
        state["last_proactive_content"] = None  # 🆕 清空上一次主动对话内容

    @classmethod
    def is_in_cooldown(cls, chat_key: str) -> bool:
        """
        检查是否在冷却期

        Args:
            chat_key: 群聊唯一标识

        Returns:
            是否在冷却期
        """
        state = cls.get_chat_state(chat_key)

        if not state["is_in_cooldown"]:
            return False

        # 检查冷却是否已结束
        if time.time() >= state["cooldown_until"]:
            state["is_in_cooldown"] = False
            state["cooldown_until"] = 0
            logger.info(f"✅ [冷却结束] 群{chat_key} - 可以再次尝试主动对话")
            return False

        return True

    # ========== 🆕 临时概率提升机制 ==========

    @classmethod
    def activate_temp_probability_boost(
        cls, chat_key: str, boost_value: float, duration: int
    ):
        """
        激活临时概率提升（AI主动发言后）

        模拟真人发完消息后会留意群里的反应

        Args:
            chat_key: 群聊唯一标识
            boost_value: 提升的概率值
            duration: 持续时间(秒)
        """
        cls._temp_probability_boost[chat_key] = {
            "boost_value": boost_value,
            "boost_until": time.time() + duration,
            "triggered_by_proactive": True,
        }
        logger.info(
            f"✨ [临时概率提升] 群{chat_key} - "
            f"激活临时提升(+{boost_value:.2f})，持续{duration}秒"
        )

    @classmethod
    def deactivate_temp_probability_boost(cls, chat_key: str, reason: str = "回复检测"):
        """
        取消临时概率提升

        Args:
            chat_key: 群聊唯一标识
            reason: 取消原因
        """
        if chat_key in cls._temp_probability_boost:
            del cls._temp_probability_boost[chat_key]
            logger.info(f"🔻 [临时概率提升] 群{chat_key} - 已取消（原因: {reason}）")

    @classmethod
    def get_temp_probability_boost(cls, chat_key: str) -> float:
        """
        获取当前的临时概率提升值

        Args:
            chat_key: 群聊唯一标识

        Returns:
            提升的概率值，如果没有提升则返回0
        """
        if chat_key not in cls._temp_probability_boost:
            return 0.0

        boost_info = cls._temp_probability_boost[chat_key]
        current_time = time.time()

        # 检查是否已过期
        if current_time >= boost_info["boost_until"]:
            cls.deactivate_temp_probability_boost(chat_key, "超时自动取消")
            return 0.0

        return boost_info["boost_value"]

    @classmethod
    def check_and_handle_reply_after_proactive(
        cls, chat_key: str, config: dict, force: bool = False
    ):
        """
        处理“AI决定回复用户消息”这一时机下的临时概率提升清理

        新逻辑：只有当外部在“概率筛选通过 + 决策AI判断应回复”之后显式调用时才取消临时提升。
        早期的“任意用户消息到来就取消”逻辑已废弃。

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置（用于获取衰减配置）
            force: 是否强制执行取消（默认False；为True时无条件取消临时提升并重置计数）
        """
        if not force:
            return

        # 无条件取消并复位相关状态（由上层在正确时机调用）
        if chat_key in cls._temp_probability_boost:
            cls.deactivate_temp_probability_boost(chat_key, "AI决定回复，取消临时提升")

        state = cls.get_chat_state(chat_key)

        # 🆕 v1.2.0: 只有当确实有主动对话活跃或连续尝试状态时才处理
        # 检查关键状态：活跃标记 或 连续尝试计数
        has_active_proactive = state.get("proactive_active", False)
        has_attempts = state.get("proactive_attempts_count", 0) > 0

        if not has_active_proactive and not has_attempts:
            # 没有活跃的主动对话，也没有连续尝试，说明是纯普通对话模式
            # 不做任何处理，直接返回
            if cls._debug_mode:
                logger.info(f"[主动对话] 群{chat_key} - 普通对话模式，跳过主动对话处理")
            return

        # 有主动对话相关状态，需要处理
        if has_active_proactive and not state.get("proactive_outcome_recorded", False):
            # 场景1: 有活跃的主动对话等待判定 → 判定为间接成功
            state["proactive_active"] = False
            state["proactive_outcome_recorded"] = True
            state["consecutive_failures"] = 0

            # 🆕 渐进式衰减：间接成功时也减少累积失败次数

            old_total_failures = state.get("total_proactive_failures", 0)
            decay_amount = cls._complaint_decay_on_success
            state["total_proactive_failures"] = max(
                0, old_total_failures - decay_amount
            )

            # 调试模式：总是输出衰减信息
            if cls._debug_mode and old_total_failures > 0:
                logger.info(
                    f"📉 [累积失败衰减-间接] 群{chat_key} - "
                    f"间接成功，累积失败次数: {old_total_failures} → {state['total_proactive_failures']} (衰减-{decay_amount})"
                )
            # 非调试模式：只在累积失败较多时输出（>=5次）
            elif not cls._debug_mode and old_total_failures >= 5:
                logger.info(
                    f"📉 [累积失败衰减-间接] 群{chat_key} - "
                    f"间接成功，累积失败: {old_total_failures} → {state['total_proactive_failures']}"
                )

            state["consecutive_successes"] = state.get("consecutive_successes", 0) + 1
            state["proactive_attempts_count"] = 0
            state["last_proactive_content"] = None  # 🆕 清空上一次主动对话内容
            state["last_proactive_success_time"] = time.time()
            logger.info(
                f"✅ [主动对话成功-间接] 群{chat_key} - 主动对话激活互动，AI决定回复"
            )
        elif has_attempts:
            # 场景2: 有连续尝试计数（说明之前有主动对话失败），AI决定回复，重置连续尝试
            state["consecutive_failures"] = 0

            # 🆕 渐进式衰减：AI决定回复时也减少累积失败次数

            old_total_failures = state.get("total_proactive_failures", 0)
            decay_amount = cls._complaint_decay_on_success
            state["total_proactive_failures"] = max(
                0, old_total_failures - decay_amount
            )

            # 调试模式：总是输出衰减信息
            if cls._debug_mode and old_total_failures > 0:
                logger.info(
                    f"📉 [累积失败衰减-决定回复] 群{chat_key} - "
                    f"AI决定回复，累积失败次数: {old_total_failures} → {state['total_proactive_failures']} (衰减-{decay_amount})"
                )
            # 非调试模式：只在累积失败较多时输出（>=5次）
            elif not cls._debug_mode and old_total_failures >= 5:
                logger.info(
                    f"📉 [累积失败衰减-决定回复] 群{chat_key} - "
                    f"AI决定回复，累积失败: {old_total_failures} → {state['total_proactive_failures']}"
                )

            state["proactive_attempts_count"] = 0
            state["last_proactive_content"] = None  # 🆕 清空上一次主动对话内容
            state["last_proactive_success_time"] = time.time()
            if cls._debug_mode:
                logger.info(f"[主动对话] 群{chat_key} - AI决定回复，重置连续尝试计数")

    # ========== 🆕 v1.2.0 互动评分系统 ==========

    @classmethod
    def update_interaction_score(
        cls, chat_key: str, delta: int, reason: str, config: dict = None
    ):
        """
        更新互动评分

        Args:
            chat_key: 群聊唯一标识
            delta: 评分变化量（正数加分，负数扣分）
            reason: 变化原因
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）
        """

        if not cls._enable_adaptive_proactive:
            return

        state = cls.get_chat_state(chat_key)
        old_score = state.get("interaction_score", 50)

        # 计算新评分（限制在10-100范围内）

        min_score = cls._interaction_score_min
        max_score = cls._interaction_score_max
        new_score = max(min_score, min(max_score, old_score + delta))

        state["interaction_score"] = new_score

        # 记录评分变化
        # 调试模式：输出所有变化
        if cls._debug_mode:
            logger.info(
                f"📊 [互动评分] 群{chat_key} - {reason}: {old_score}分 → {new_score}分 (变化{delta:+d})"
            )
        # 非调试模式：只输出关键变化
        else:
            # 1. 跨越重要阈值（30分、50分、70分）
            thresholds = [30, 50, 70]
            crossed_threshold = False
            for threshold in thresholds:
                if (old_score < threshold <= new_score) or (
                    old_score > threshold >= new_score
                ):
                    crossed_threshold = True
                    break

            # 2. 极端分数（<=20 或 >=90）
            is_extreme = new_score <= 20 or new_score >= 90

            # 3. 大幅变化（±15分以上）
            is_large_change = abs(delta) >= 15

            # 满足任一条件就输出
            if crossed_threshold or is_extreme or is_large_change:
                logger.info(
                    f"📊 [互动评分] 群{chat_key} - {reason}: {old_score}分 → {new_score}分 (变化{delta:+d})"
                )

        # 重要变化立即保存
        if abs(delta) >= 10:
            cls._save_states_to_disk()

    @classmethod
    def record_proactive_success(
        cls,
        chat_key: str,
        config: dict,
        is_quick: bool = False,
        is_multi_user: bool = False,
    ):
        """
        记录主动对话成功（有人回复）（仅在未记录过时执行）

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置
            is_quick: 是否为快速回复（30秒内）
            is_multi_user: 是否为多人回复
        """

        if not cls._enable_adaptive_proactive:
            return

        state = cls.get_chat_state(chat_key)

        # 🆕 v1.2.0: 防止重复记录成功
        if state.get("proactive_outcome_recorded", False):
            if cls._debug_mode:
                logger.info(
                    f"[主动对话成功] 群{chat_key} - 本次主动对话已记录过结果，跳过"
                )
            return

        # 🆕 v1.2.0: 关闭主动对话检测（已判定成功）
        state["proactive_active"] = False
        # 标记为已记录
        state["proactive_outcome_recorded"] = True

        current_time = time.time()

        # 🔧 修复：重置失败相关计数（成功后处理）
        state["consecutive_failures"] = 0  # 重置连续失败次数
        state[
            "current_effective_max_failures"
        ] = -1  # 🔧 重置扰动阈值（下一轮重新计算）

        # 🆕 渐进式衰减：成功时减少累积失败次数，而不是完全清零
        # 这样更拟人化：偶尔的失败不会因为历史累积而触发过度的吐槽

        old_total_failures = state.get("total_proactive_failures", 0)
        decay_amount = cls._complaint_decay_on_success
        state["total_proactive_failures"] = max(0, old_total_failures - decay_amount)

        # 调试模式：总是输出衰减信息
        if cls._debug_mode and old_total_failures > 0:
            logger.info(
                f"📉 [累积失败衰减] 群{chat_key} - "
                f"成功互动，累积失败次数: {old_total_failures} → {state['total_proactive_failures']} (衰减-{decay_amount})"
            )
        # 非调试模式：只在累积失败较多时输出（>=5次）
        elif not cls._debug_mode and old_total_failures >= 5:
            logger.info(
                f"📉 [累积失败衰减] 群{chat_key} - "
                f"成功互动，累积失败: {old_total_failures} → {state['total_proactive_failures']}"
            )

        state["consecutive_successes"] = state.get("consecutive_successes", 0) + 1
        state["last_proactive_success_time"] = current_time  # 记录上次成功时间

        # 更新成功统计
        state["successful_interactions"] = state.get("successful_interactions", 0) + 1
        state["last_success_time"] = current_time

        # 基础加分

        base_increase = cls._score_increase_on_success
        total_increase = base_increase

        reason_parts = ["有人回复"]

        # 快速回复额外加分
        if is_quick:
            quick_bonus = cls._score_quick_reply_bonus
            total_increase += quick_bonus
            state["quick_reply_count"] = state.get("quick_reply_count", 0) + 1
            reason_parts.append("快速回复+{0}".format(quick_bonus))

        # 多人回复额外加分
        if is_multi_user:
            multi_bonus = cls._score_multi_user_bonus
            total_increase += multi_bonus
            state["multi_user_reply_count"] = state.get("multi_user_reply_count", 0) + 1
            reason_parts.append("多人接话+{0}".format(multi_bonus))

        # 连续成功加速奖励
        if state["consecutive_successes"] >= 3:
            streak_bonus = cls._score_streak_bonus
            total_increase += streak_bonus
            reason_parts.append("连续成功+{0}".format(streak_bonus))

        # 从低分复苏奖励
        current_score = state.get("interaction_score", 50)
        if current_score < 30:
            revival_bonus = cls._score_revival_bonus
            total_increase += revival_bonus
            reason_parts.append("低分复苏+{0}".format(revival_bonus))

        reason = "，".join(reason_parts)
        cls.update_interaction_score(chat_key, total_increase, reason)

    @classmethod
    def record_proactive_failure_for_score(cls, chat_key: str, config: dict = None):
        """
        记录主动对话失败（无人回复）- 仅用于评分系统

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）
        """

        if not cls._enable_adaptive_proactive:
            return

        state = cls.get_chat_state(chat_key)

        # 更新失败统计
        state["failed_interactions"] = state.get("failed_interactions", 0) + 1
        state["consecutive_successes"] = 0  # 重置连续成功

        # 获取当前评分（用于判断是否需要警告）
        current_score = state.get("interaction_score", 50)

        # 扣分

        decrease = cls._score_decrease_on_fail
        cls.update_interaction_score(chat_key, -decrease, "无人回复")

        # 非调试模式：在评分较低时给出警告
        if not cls._debug_mode and current_score <= 30:
            logger.warning(
                f"⚠️ [主动对话] 群{chat_key} - 互动评分较低({current_score}分)，主动对话响应不佳"
            )

    @classmethod
    def record_proactive_failure_for_score_internal(cls, chat_key: str):
        """
        🔧 内部版本：记录主动对话失败（无人回复）- 仅用于评分系统
        使用类变量，不需要传入 config 参数
        """
        cls.record_proactive_failure_for_score(chat_key)

    @classmethod
    def apply_score_decay(cls, config: dict = None):
        """
        应用评分衰减（每24小时执行一次）

        Args:
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）
        """

        if not cls._enable_adaptive_proactive:
            return

        current_time = time.time()
        decay_interval = 24 * 3600  # 24小时
        decay_rate = cls._interaction_score_decay_rate

        # 统计衰减情况（非调试模式用于汇总）
        decay_count = 0

        for chat_key, state in cls._chat_states.items():
            last_decay = state.get("last_score_decay_time", 0)

            # 检查是否需要衰减
            if current_time - last_decay >= decay_interval:
                # 检查是否有新互动
                last_success = state.get("last_success_time", 0)
                last_user_msg = state.get("last_user_message_time", 0)

                # 如果24小时内没有任何互动，进行衰减
                if current_time - max(last_success, last_user_msg) >= decay_interval:
                    cls.update_interaction_score(
                        chat_key, -decay_rate, "24小时无互动自然衰减"
                    )
                    decay_count += 1

                # 更新衰减时间
                state["last_score_decay_time"] = current_time

        # 非调试模式：输出汇总信息（只在有衰减时）
        if not cls._debug_mode and decay_count > 0:
            logger.info(f"📉 [评分衰减] 已对 {decay_count} 个群聊执行24小时无互动衰减")

    @classmethod
    def apply_complaint_decay(cls, config: dict = None):
        """
        🆕 应用累积失败次数的时间自然衰减

        改进逻辑：
        1. 长时间没有新的失败，失败次数会逐渐减少
        2. 防止历史累积的失败次数影响当前的吐槽判断
        3. 更拟人化：偶尔的失败不会因为历史原因触发过度吐槽

        Args:
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）
        """

        if not cls._enable_complaint_system:
            return

        current_time = time.time()
        # 每隔一段时间检查一次（默认6小时）
        check_interval = cls._complaint_decay_check_interval
        # 多久没有新失败就开始衰减（默认12小时）
        no_failure_threshold = cls._complaint_decay_no_failure_threshold
        # 每次衰减的数量（默认1次）
        decay_amount = cls._complaint_decay_amount

        for chat_key, state in cls._chat_states.items():
            try:
                last_check = state.get("last_complaint_decay_time", 0)

                # 检查是否需要衰减
                if current_time - last_check >= check_interval:
                    total_failures = state.get("total_proactive_failures", 0)

                    # 只有累积失败次数 > 0 才需要检查衰减
                    if total_failures > 0:
                        # 获取上次失败时间（通过 last_proactive_time 判断）
                        last_proactive_time = state.get("last_proactive_time", 0)
                        last_success_time = state.get("last_proactive_success_time", 0)

                        # 如果距离上次主动对话失败已经很久了（通过判断是否有新的成功）
                        # 或者长时间没有任何主动对话活动
                        time_since_last_activity = current_time - max(
                            last_proactive_time, last_success_time
                        )

                        if time_since_last_activity >= no_failure_threshold:
                            # 执行衰减
                            old_failures = total_failures
                            new_failures = max(0, total_failures - decay_amount)
                            state["total_proactive_failures"] = new_failures

                            if cls._debug_mode and new_failures != old_failures:
                                logger.info(
                                    f"🕐 [时间自然衰减] 群{chat_key} - "
                                    f"{time_since_last_activity / 3600:.1f}小时无主动对话活动，"
                                    f"累积失败次数: {old_failures} → {new_failures} (衰减-{decay_amount})"
                                )

                    # 更新检查时间
                    state["last_complaint_decay_time"] = current_time

            except Exception as e:
                logger.error(
                    f"[时间自然衰减] 处理群{chat_key}时出错: {e}", exc_info=True
                )

    @classmethod
    def get_score_level(cls, score: int) -> str:
        """
        根据评分获取等级描述

        Args:
            score: 互动评分

        Returns:
            等级描述
        """
        if score >= 80:
            return "热情群🔥"
        elif score >= 60:
            return "友好群😊"
        elif score >= 40:
            return "冷淡群😐"
        elif score >= 20:
            return "冰冷群🥶"
        else:
            return "死群💀"

    @classmethod
    def calculate_adaptive_parameters(cls, chat_key: str, config: dict = None) -> dict:
        """
        根据互动评分计算自适应参数

        ⚠️ 重要：此方法返回的是调整系数，不是最终值
        最终概率计算顺序：基础概率 → 时间段调整 → 自适应系数

        🔧 修复：扰动因子不再在此方法中应用，而是通过 get_effective_max_failures 方法
        在开始新一轮连续尝试时计算一次并保存到状态中

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）

        Returns:
            包含调整参数和系数的字典
        """

        if not cls._enable_adaptive_proactive:
            # 未启用自适应，返回原始参数（系数为1.0，不调整）
            base_max_failures = int(cls._proactive_max_consecutive_failures)
            if base_max_failures < 0:
                base_max_failures = 0

            # 🔧 修复：获取当前轮次的有效阈值（扰动因子在此处理）
            effective_max_failures = cls.get_effective_max_failures(
                chat_key, base_max_failures
            )

            return {
                "prob_multiplier": 1.0,  # 概率系数
                "silence_threshold": cls._proactive_silence_threshold,
                "cooldown_duration": cls._proactive_cooldown_duration,
                "max_failures": effective_max_failures,
                "score": 50,
                "level": "友好群😊",
            }

        state = cls.get_chat_state(chat_key)
        score = state.get("interaction_score", 50)

        # 基础参数（非概率参数直接计算）

        base_silence = cls._proactive_silence_threshold
        base_cooldown = cls._proactive_cooldown_duration
        base_max_failures = int(cls._proactive_max_consecutive_failures)

        # 根据评分等级计算调整系数
        if score >= 80:  # 🔥 热情群
            prob_multiplier = 1.8
            silence_multiplier = 0.5
            cooldown_multiplier = 0.33
            max_failures = min(3, base_max_failures + 1)
        elif score >= 60:  # 😊 友好群
            prob_multiplier = 1.0
            silence_multiplier = 1.0
            cooldown_multiplier = 1.0
            max_failures = base_max_failures
        elif score >= 40:  # 😐 冷淡群
            prob_multiplier = 0.5
            silence_multiplier = 1.5
            cooldown_multiplier = 1.5
            max_failures = max(1, base_max_failures - 1)
        elif score >= 20:  # 🥶 冰冷群
            prob_multiplier = 0.25
            silence_multiplier = 3.0
            cooldown_multiplier = 2.0
            max_failures = 1
        else:  # 💀 死群
            prob_multiplier = 0.1
            silence_multiplier = 6.0
            cooldown_multiplier = 4.0
            max_failures = 1

        # ⚠️ 冷却阈值不允许超过用户配置的最大连续失败次数
        max_failures = max(0, min(max_failures, base_max_failures))

        # 🔧 修复：获取当前轮次的有效阈值（扰动因子在此处理）
        effective_max_failures = cls.get_effective_max_failures(chat_key, max_failures)

        return {
            "prob_multiplier": prob_multiplier,  # ⚠️ 返回系数，不是最终值
            "silence_threshold": int(base_silence * silence_multiplier),
            "cooldown_duration": int(base_cooldown * cooldown_multiplier),
            "max_failures": effective_max_failures,
            "score": score,
            "level": cls.get_score_level(score),
        }

    @classmethod
    def get_effective_max_failures(cls, chat_key: str, base_max_failures: int) -> int:
        """
        获取当前轮次的有效最大失败阈值

        🔧 修复：扰动因子只在开始新一轮连续尝试时（consecutive_failures == 0）计算一次，
        并保存到状态中，直到进入冷却或成功时重置。

        Args:
            chat_key: 群聊唯一标识
            base_max_failures: 基础最大失败次数（已经过自适应调整）

        Returns:
            当前轮次的有效最大失败阈值
        """
        state = cls.get_chat_state(chat_key)
        consecutive_failures = state.get("consecutive_failures", 0)
        current_effective = state.get("current_effective_max_failures", -1)

        # 获取扰动因子配置
        perturb = cls._proactive_failure_threshold_perturbation
        perturb = max(0.0, min(1.0, perturb))

        # 如果扰动因子为0，直接返回基础值（不启用扰动功能）
        if perturb <= 0.0:
            return base_max_failures

        # 如果当前没有连续失败（新一轮开始），计算并保存新的有效阈值
        if consecutive_failures == 0 or current_effective < 0:
            # 使用 Beta 分布实现扰动：perturb 越大，越偏向小值
            # Beta(1, 1+k) 其中 k = perturb * 5，k越大分布越偏向0
            if base_max_failures > 0:
                # 计算 Beta 分布参数，perturb 越大，beta 参数越大，分布越偏向小值
                alpha = 1.0
                beta_param = 1.0 + perturb * 5.0  # perturb=1 时 beta=6，强烈偏向小值

                # 生成 0-1 之间的随机数，偏向小值
                random_ratio = random.betavariate(alpha, beta_param)

                # 映射到 1 ~ base_max_failures 的整数（最小为1，确保至少有一次尝试机会）
                effective = round(random_ratio * base_max_failures)
                effective = max(1, min(effective, base_max_failures))
            else:
                effective = base_max_failures

            state["current_effective_max_failures"] = effective

            if cls._debug_mode:
                logger.info(
                    f"[扰动因子] 群{chat_key} - 新一轮开始，"
                    f"基础阈值={base_max_failures}, 扰动因子={perturb:.2f}, "
                    f"本轮有效阈值={effective}"
                )

            return effective

        # 已有连续失败，返回之前计算的有效阈值
        # 但如果之前保存的值大于当前基础值，使用当前基础值（防止配置变更后阈值过高）
        return min(current_effective, base_max_failures)

    @classmethod
    def generate_complaint_prompt(cls, chat_key: str, config: dict) -> dict:
        """
        🔧 修复：生成吐槽提示词（根据累积失败次数和评分）

        改进：
        1. 使用 total_proactive_failures（累积失败次数）而不是 consecutive_failures
        2. 返回字典结构，包含是否触发、吐槽等级、提示词等信息
        3. 如果触发吐槽，应该优先发送吐槽信息，而不是普通主动对话+吐槽提示词

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置

        Returns:
            字典结构：
            {
                "triggered": bool,  # 是否触发吐槽
                "level": str,  # 吐槽等级（"light"/"medium"/"strong"）
                "prompt": str,  # 吐槽提示词
                "priority": bool,  # 是否优先发送吐槽（True=只发吐槽，False=普通对话+吐槽提示）
                "failure_count": int  # 当前累积失败次数
            }
        """
        # 默认返回值（未触发）
        default_result = {
            "triggered": False,
            "level": "none",
            "prompt": "",
            "priority": False,
            "failure_count": 0,
        }

        if not cls._enable_complaint_system:
            return default_result

        state = cls.get_chat_state(chat_key)
        # 🔧 修复：使用累积失败次数而不是连续失败次数
        total_failures = state.get("total_proactive_failures", 0)
        score = state.get("interaction_score", 50)

        # 根据配置的阈值决定是否触发吐槽

        complaint_threshold = cls._complaint_trigger_threshold
        if total_failures < complaint_threshold:
            default_result["failure_count"] = total_failures
            return default_result

        # 获取各等级吐槽的触发次数和概率

        light_threshold = cls._complaint_level_light
        medium_threshold = cls._complaint_level_medium
        strong_threshold = cls._complaint_level_strong

        # 按从高到低的顺序检查（优先匹配更严重的等级）
        if total_failures >= strong_threshold:
            # 强烈吐槽
            complaint_prob = cls._complaint_probability_strong
            roll = random.random()
            if (
                roll > complaint_prob
            ):  # 🔧 修复：roll > prob 表示不触发，roll <= prob 表示触发
                default_result["failure_count"] = total_failures
                return default_result
            return {
                "triggered": True,
                "level": "strong",
                "prompt": (
                    "\n\n【情绪提示】你已经连续主动说了{0}次话都没人回复，感觉有些受伤。"
                    "你可以用比较明显的方式表达委屈或无奈，"
                    "比如说要安静一段时间、反思自己、或者干脆潜水。"
                    "保持你的性格特点，可以幽默自嘲，也可以稍微委屈，但不要过于消极。"
                ).format(total_failures),
                "priority": True,  # 🔧 修复：强烈吐槽优先发送
                "failure_count": total_failures,
            }
        elif total_failures >= medium_threshold:
            # 明显吐槽
            complaint_prob = cls._complaint_probability_medium
            roll = random.random()
            if (
                roll > complaint_prob
            ):  # 🔧 修复：roll > prob 表示不触发，roll <= prob 表示触发
                default_result["failure_count"] = total_failures
                return default_result
            return {
                "triggered": True,
                "level": "medium",
                "prompt": (
                    "\n\n【情绪提示】你已经连续主动说了{0}次话都没人理会。"
                    "你可以用稍微明显一点的方式表达出被忽视的感觉，"
                    "但仍然保持幽默感，不要太过严肃或负面。"
                    "可以用玩笑的方式吐槽一下，或者假装不在意地换个新话题。"
                ).format(total_failures),
                "priority": True,  # 🔧 修复：明显吐槽优先发送
                "failure_count": total_failures,
            }
        elif total_failures >= light_threshold:
            # 轻度吐槽
            complaint_prob = cls._complaint_probability_light
            roll = random.random()
            if (
                roll > complaint_prob
            ):  # 🔧 修复：roll > prob 表示不触发，roll <= prob 表示触发
                default_result["failure_count"] = total_failures
                return default_result
            return {
                "triggered": True,
                "level": "light",
                "prompt": (
                    "\n\n【情绪提示】你刚才主动说了一句话，但似乎没什么人回应。"
                    "你可以用轻松幽默的语气稍微提一下这件事，或者自然地换个话题。"
                    "不要过度戏剧化，保持轻松自然的感觉。"
                ),
                "priority": True,  # 🔧 修复：轻度吐槽也优先发送
                "failure_count": total_failures,
            }
        else:
            # 未达到任何吐槽等级的阈值
            default_result["failure_count"] = total_failures
            return default_result

    # ========== 检查逻辑 ==========

    @classmethod
    def is_group_enabled(cls, chat_key: str, config: dict = None) -> bool:
        """
        🆕 检查当前群聊是否在白名单中

        Args:
            chat_key: 群聊唯一标识 (格式: "platform_name:group/private:chat_id" 或 "platform_name_group_chat_id")
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）

        Returns:
            True=允许主动对话, False=不允许
        """
        try:
            # 获取白名单配置

            enabled_groups = cls._proactive_enabled_groups

            # 白名单为空 = 所有群聊都启用
            if not enabled_groups or len(enabled_groups) == 0:
                if cls._debug_mode:
                    logger.info(
                        f"[主动对话-白名单检查] chat_key={chat_key}, 白名单为空，允许所有群聊"
                    )
                return True

            # 从 chat_key 解析出 chat_id
            # 支持两种格式：
            # 1. 冒号格式: "platform_name:group/private:chat_id"
            # 2. 下划线格式: "platform_name_group_chat_id" 或 "platform_name_private_chat_id"
            chat_id = None
            if ":" in chat_key:
                # 冒号格式
                parts = chat_key.split(":")
                if len(parts) >= 3:
                    chat_id = parts[2]
                    if cls._debug_mode:
                        logger.info(
                            f"[主动对话-白名单检查] 冒号格式解析: chat_key={chat_key}, chat_id={chat_id}"
                        )
            elif "_" in chat_key:
                # 下划线格式: "platform_name_group_chat_id" 或 "platform_name_private_chat_id"
                # 格式固定为: {platform_name}_{group|private}_{chat_id}
                # 所以最后一部分就是 chat_id
                parts = chat_key.split("_")
                if len(parts) >= 3:
                    # 确保至少有 platform_name, group/private, chat_id 三部分
                    chat_id = parts[-1]  # 最后一部分是 chat_id
                    if cls._debug_mode:
                        logger.info(
                            f"[主动对话-白名单检查] 下划线格式解析: chat_key={chat_key}, parts={parts}, chat_id={chat_id}"
                        )
                elif len(parts) >= 2:
                    # 兼容旧格式（虽然不应该出现）
                    chat_id = parts[-1]
                    logger.warning(
                        f"[主动对话-白名单检查] 下划线格式解析异常: chat_key={chat_key}, parts={parts}, 使用最后一部分作为chat_id: {chat_id}"
                    )

            if chat_id:
                # 检查是否在白名单中
                # 支持字符串和数字类型的ID
                # 先尝试直接匹配
                if chat_id in enabled_groups:
                    if cls._debug_mode:
                        logger.info(
                            f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（直接匹配）"
                        )
                    return True

                # 尝试字符串匹配
                if str(chat_id) in enabled_groups:
                    if cls._debug_mode:
                        logger.info(
                            f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（字符串匹配）"
                        )
                    return True

                # 尝试数字匹配（如果chat_id是数字）
                if chat_id.isdigit():
                    try:
                        if int(chat_id) in enabled_groups:
                            if cls._debug_mode:
                                logger.info(
                                    f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（数字匹配）"
                                )
                            return True
                    except (ValueError, TypeError):
                        pass

                # 都不匹配，检查白名单中的每个元素
                # 处理白名单中可能是字符串或数字的情况
                for group_id in enabled_groups:
                    if str(group_id) == str(chat_id):
                        if cls._debug_mode:
                            logger.info(
                                f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（遍历匹配，group_id={group_id}）"
                            )
                        return True
                    try:
                        if int(group_id) == int(chat_id):
                            if cls._debug_mode:
                                logger.info(
                                    f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（遍历数字匹配，group_id={group_id}）"
                                )
                            return True
                    except (ValueError, TypeError):
                        continue

                if cls._debug_mode:
                    logger.info(
                        f"[主动对话-白名单检查] ❌ chat_id={chat_id} 不在白名单中，白名单={enabled_groups}"
                    )
                return False

            # 无法解析 chat_key，默认不启用
            logger.warning(
                f"[主动对话-白名单检查] ⚠️ 无法解析 chat_key={chat_key}，默认不启用"
            )
            return False

        except Exception as e:
            logger.error(
                f"[主动对话-白名单检查] 发生错误: {e}, chat_key={chat_key}",
                exc_info=True,
            )
            # 出错时默认启用（保守策略）
            return True

    @classmethod
    def should_trigger_proactive_chat(
        cls, chat_key: str, config: dict
    ) -> Tuple[bool, str]:
        """
        判断是否应该触发主动对话

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置

        Returns:
            (是否应该触发, 原因说明)
        """
        state = cls.get_chat_state(chat_key)
        current_time = time.time()

        # 0. 🆕 检查群聊白名单
        if not cls.is_group_enabled(chat_key):
            return False, "当前群聊不在白名单中"

        # 1. 检查是否在冷却期
        if cls.is_in_cooldown(chat_key):
            remaining = int(state["cooldown_until"] - current_time)
            return False, f"在冷却期（剩余{remaining}秒）"

        # 🆕 v1.2.0 获取自适应参数（根据互动评分调整）
        adaptive_params = cls.calculate_adaptive_parameters(chat_key)
        silence_threshold = adaptive_params["silence_threshold"]
        prob_multiplier = adaptive_params["prob_multiplier"]

        # 2. 检查沉默时长（使用自适应阈值）
        silence_duration = int(current_time - state["last_bot_reply_time"])

        if silence_duration < silence_threshold:
            return False, f"沉默时长不足（{silence_duration}/{silence_threshold}秒）"

        # 3. 检查用户活跃度

        require_user_activity = cls._proactive_require_user_activity
        if require_user_activity:
            if not cls.check_user_activity(chat_key):
                state = cls.get_chat_state(chat_key)
                min_messages = cls._proactive_min_user_messages
                if cls._debug_mode:
                    logger.info(
                        f"[主动对话检查] 群{chat_key} - 用户活跃度不足 "
                        f"(消息数={state['user_message_count']}, 最小要求={min_messages})"
                    )
                return False, "用户活跃度不足"
        else:
            if cls._debug_mode:
                logger.info(
                    f"[主动对话检查] 群{chat_key} - 已禁用用户活跃度检查，允许无用户消息时触发"
                )

        # 4. 计算有效概率（正确的顺序）
        # 步骤1: 获取用户配置的基础概率

        base_prob = cls._proactive_probability

        # 步骤2: 应用时间段调整（包括禁用时段检查，最高优先级）
        time_adjusted_prob = cls.calculate_effective_probability(base_prob, config)

        # 如果禁用时段返回0，直接返回
        if time_adjusted_prob <= 0:
            return False, "当前时段已禁用"

        # 步骤3: 应用自适应系数
        final_prob = time_adjusted_prob * prob_multiplier

        # 限制在合理范围内（最高90%）
        final_prob = min(0.9, max(0.0, final_prob))

        # 记录调试信息

        if cls._debug_mode and cls._enable_adaptive_proactive:
            logger.info(
                f"📊 [自适应参数] 群{chat_key} - {adaptive_params['level']} "
                f"评分={adaptive_params['score']}, "
                f"基础概率={base_prob:.2f} → 时间调整={time_adjusted_prob:.2f} → "
                f"自适应系数×{prob_multiplier:.2f} → 最终概率={final_prob:.2f}, "
                f"沉默阈值={silence_threshold}秒, 最大尝试={adaptive_params['max_failures']}次"
            )

        # 5. 概率判断
        roll = random.random()
        if roll >= final_prob:
            return False, f"概率判断失败（{roll:.2f} >= {final_prob:.2f}）"

        return True, f"触发成功（{roll:.2f} < {final_prob:.2f}）"

    @classmethod
    def check_user_activity(cls, chat_key: str, config: dict = None) -> bool:
        """
        检查用户活跃度

        注意：此方法仅在 proactive_require_user_activity 为 True 时被调用。
        当该配置为 False 时，should_trigger_proactive_chat 会直接跳过此检查，
        允许在没有用户消息时也触发主动对话。

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）

        Returns:
            是否满足活跃度要求
        """
        state = cls.get_chat_state(chat_key)
        current_time = time.time()

        # 如果开启了用户活跃度检测，必须要求有用户消息
        # 如果没有用户消息记录，不满足活跃度要求
        if state["user_message_count"] == 0:
            if cls._debug_mode:
                logger.info(
                    f"[用户活跃度检查] 群{chat_key} - 用户消息数为0，不满足活跃度要求"
                )
            return False

        # 检查是否满足最小消息数要求

        min_messages = cls._proactive_min_user_messages
        if state["user_message_count"] < min_messages:
            if cls._debug_mode:
                logger.info(
                    f"[用户活跃度检查] 群{chat_key} - 用户消息数({state['user_message_count']})"
                    f"小于最小要求({min_messages})，不满足活跃度要求"
                )
            return False

        # 检查活跃时间窗口

        activity_window = cls._proactive_user_activity_window
        recent_messages = [
            ts
            for ts in state["user_message_timestamps"]
            if current_time - ts <= activity_window
        ]

        # 确保时间戳列表和消息计数一致（双重检查）
        if len(recent_messages) < min_messages:
            if cls._debug_mode:
                logger.info(
                    f"[用户活跃度检查] 群{chat_key} - 时间窗口内消息数({len(recent_messages)})"
                    f"小于最小要求({min_messages})，不满足活跃度要求"
                )
            return False

        # 确保 user_message_count 和 user_message_timestamps 一致
        # 如果时间戳数量少于消息计数，说明可能有数据不一致，以时间戳为准
        if len(state["user_message_timestamps"]) < state["user_message_count"]:
            logger.warning(
                f"[用户活跃度检查] 群{chat_key} - 数据不一致："
                f"消息计数({state['user_message_count']}) > 时间戳数量({len(state['user_message_timestamps'])})，"
                f"以时间戳为准"
            )
            if len(recent_messages) < min_messages:
                return False

        logger.info(
            f"[用户活跃度检查] 群{chat_key} - ✅ 满足活跃度要求 "
            f"(消息数={state['user_message_count']}, 时间窗口内={len(recent_messages)})"
        )
        return True

    # ========== 时间段控制 ==========

    @classmethod
    def calculate_effective_probability(
        cls, base_prob: float, config: dict = None
    ) -> float:
        """
        计算有效概率（考虑时间段和过渡）

        🆕 v1.1.0: 支持动态时间段调整

        优先级规则：
        1. 原有禁用时段（proactive_enable_quiet_time）- 最高优先级，完全禁用
        2. 动态时间段调整（enable_dynamic_proactive_probability）- 调整概率系数
        3. 基础概率

        Args:
            base_prob: 基础概率
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）

        Returns:
            有效概率 (0.0 - 1.0)
        """
        current_time = datetime.now()

        # ========== 第一优先级：原有禁用时段（向后兼容） ==========

        if cls._proactive_enable_quiet_time:
            try:
                transition_factor = cls.get_transition_factor(current_time)

                if transition_factor < 1e-9:
                    # 在禁用时段内，直接返回0（完全禁用）
                    if cls._debug_mode:
                        logger.info(
                            "[主动对话-时间控制] 在禁用时段内，概率=0（禁用时段优先级最高）"
                        )
                    return 0.0
                elif transition_factor < 1.0:
                    # 在过渡期，先应用过渡系数
                    original_prob = base_prob
                    base_prob = base_prob * transition_factor
                    if cls._debug_mode:
                        logger.info(
                            f"[主动对话-时间控制] 在禁用时段过渡期，"
                            f"原始概率={original_prob:.2f}, 过渡系数={transition_factor:.2f}, "
                            f"调整后概率={base_prob:.2f}"
                        )
            except Exception as e:
                logger.error(f"[时间段计算-禁用时段] 发生错误: {e}", exc_info=True)

        # ========== 第二优先级：动态时间段调整 ==========

        if cls._enable_dynamic_proactive_probability:
            try:
                # 动态导入以避免循环依赖
                from .time_period_manager import TimePeriodManager

                # 解析时间段配置（使用静默模式，避免重复输出日志）
                periods_json = cls._proactive_time_periods
                periods = TimePeriodManager.parse_time_periods(
                    periods_json, silent=True
                )

                if periods:
                    # 计算时间系数
                    time_factor = TimePeriodManager.calculate_time_factor(
                        current_time=current_time,
                        periods_config=periods,
                        transition_minutes=cls._proactive_time_transition_minutes,
                        min_factor=cls._proactive_time_min_factor,
                        max_factor=cls._proactive_time_max_factor,
                        use_smooth_curve=cls._proactive_time_use_smooth_curve,
                    )

                    # 应用时间系数
                    original_prob = base_prob
                    base_prob = base_prob * time_factor

                    # 确保在0-1范围内
                    base_prob = max(0.0, min(1.0, base_prob))

                    if abs(time_factor - 1.0) > 1e-9 and cls._debug_mode:
                        logger.info(
                            f"[主动对话-动态时间调整] "
                            f"原始概率={original_prob:.2f}, 时间系数={time_factor:.2f}, "
                            f"最终概率={base_prob:.2f}"
                        )
            except ImportError:
                logger.warning(
                    "[主动对话-动态时间调整] TimePeriodManager未导入，跳过时间调整"
                )
            except Exception as e:
                logger.error(f"[主动对话-动态时间调整] 发生错误: {e}", exc_info=True)

        return base_prob

    @classmethod
    def get_transition_factor(
        cls, current_time: datetime, config: dict = None
    ) -> float:
        """
        获取过渡系数

        Args:
            current_time: 当前时间
            config: 插件配置（已废弃，保留参数兼容性，实际使用类变量）

        Returns:
            过渡系数 (0.0 - 1.0)
        """
        # 解析配置的时间

        quiet_start = cls.parse_time_config(cls._proactive_quiet_start)
        quiet_end = cls.parse_time_config(cls._proactive_quiet_end)
        transition_minutes = cls._proactive_transition_minutes

        # 转换为分钟数
        current_minutes = current_time.hour * 60 + current_time.minute
        quiet_start_minutes = quiet_start[0] * 60 + quiet_start[1]
        quiet_end_minutes = quiet_end[0] * 60 + quiet_end[1]

        # 处理跨天情况（例如 23:00 - 07:00）
        is_cross_day = quiet_start_minutes > quiet_end_minutes

        if is_cross_day:
            # 跨天情况
            in_quiet_period = (
                current_minutes >= quiet_start_minutes
                or current_minutes < quiet_end_minutes
            )
        else:
            # 不跨天情况
            in_quiet_period = quiet_start_minutes <= current_minutes < quiet_end_minutes

        # 如果在禁用时段内
        if in_quiet_period:
            return 0.0

        # 计算过渡期
        transition_start = quiet_start_minutes - transition_minutes
        transition_end = (
            quiet_end_minutes + transition_minutes
        ) % 1440  # 1440 = 24 * 60

        # 进入禁用时段的过渡期（概率从1降到0）
        if is_cross_day:
            # 跨天情况的过渡期判断
            in_transition_in = (
                transition_start >= 0
                and transition_start <= current_minutes < quiet_start_minutes
            ) or (
                transition_start < 0
                and (
                    current_minutes >= (1440 + transition_start)
                    or current_minutes < quiet_start_minutes
                )
            )
        else:
            in_transition_in = transition_start <= current_minutes < quiet_start_minutes

        if in_transition_in:
            # 计算过渡进度
            if transition_start < 0:
                dist_from_start = (
                    (current_minutes - (1440 + transition_start))
                    if current_minutes < quiet_start_minutes
                    else (current_minutes - transition_start)
                )
            else:
                dist_from_start = current_minutes - transition_start
            progress = dist_from_start / transition_minutes
            return 1.0 - progress  # 从1降到0

        # 离开禁用时段的过渡期（概率从0升到1）
        if is_cross_day:
            in_transition_out = quiet_end_minutes <= current_minutes < transition_end
        else:
            in_transition_out = quiet_end_minutes <= current_minutes < transition_end

        if in_transition_out:
            # 计算过渡进度
            dist_from_end = current_minutes - quiet_end_minutes
            progress = dist_from_end / transition_minutes
            return progress  # 从0升到1

        # 正常时段
        return 1.0

    @classmethod
    def parse_time_config(cls, time_str: str) -> Tuple[int, int]:
        """
        解析时间配置字符串

        Args:
            time_str: 时间字符串，格式为 "HH:MM"

        Returns:
            (小时, 分钟)
        """
        try:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return (hour, minute)
        except Exception as e:
            logger.error(f"[时间解析] 无法解析时间字符串 '{time_str}': {e}")
            return (0, 0)

    # ========== 🆕 v1.2.0 虚拟事件创建 ==========

    @classmethod
    async def _create_virtual_event(
        cls,
        context: Context,
        platform_id: str,
        chat_id: str,
        is_private: bool,
        unified_msg_origin: str,
    ) -> Optional[AstrMessageEvent]:
        """
        创建虚拟的 AstrMessageEvent 对象，用于触发 on_llm_request 钩子

        Args:
            context: Context 对象
            platform_id: 平台 ID
            chat_id: 群聊/私聊 ID
            is_private: 是否私聊
            unified_msg_origin: 统一消息来源标识

        Returns:
            虚拟的 AstrMessageEvent 对象，如果创建失败则返回 None
        """
        try:
            # 尝试获取平台适配器
            platforms = (
                context.platform_manager.get_insts()
                if hasattr(context, "platform_manager")
                else []
            )

            # 查找匹配的平台适配器
            target_adapter = None
            for platform in platforms:
                if hasattr(platform, "meta") and platform.meta().id == platform_id:
                    target_adapter = platform
                    break
                elif (
                    hasattr(platform, "metadata")
                    and platform.metadata.id == platform_id
                ):
                    target_adapter = platform
                    break

            if not target_adapter:
                logger.debug(f"[虚拟事件] 未找到平台适配器: {platform_id}")
                return None

            # 尝试导入 aiocqhttp 相关类
            try:
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
                    AiocqhttpMessageEvent,
                )
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_platform_adapter import (
                    AiocqhttpAdapter,
                )

                # 检查是否是 aiocqhttp 适配器
                if isinstance(target_adapter, AiocqhttpAdapter):
                    # 创建虚拟消息对象
                    message_obj = AstrBotMessage()
                    message_obj.type = (
                        MessageType.FRIEND_MESSAGE
                        if is_private
                        else MessageType.GROUP_MESSAGE
                    )
                    message_obj.group_id = chat_id if not is_private else ""
                    message_obj.sender = MessageMember(
                        user_id="system", nickname="system"
                    )
                    message_obj.message = []
                    message_obj.message_str = ""
                    message_obj.raw_message = {}
                    message_obj.session_id = chat_id

                    # 创建虚拟事件
                    virtual_event = AiocqhttpMessageEvent(
                        message_str="",
                        message_obj=message_obj,
                        platform_meta=target_adapter.metadata,
                        session_id=chat_id,
                        bot=target_adapter.get_client()
                        if hasattr(target_adapter, "get_client")
                        else None,
                    )

                    # 设置 unified_msg_origin
                    virtual_event.unified_msg_origin = unified_msg_origin
                    virtual_event.is_wake = True

                    return virtual_event

            except ImportError:
                pass

            # 如果不是 aiocqhttp，尝试创建通用的虚拟事件
            # 这里我们创建一个简单的包装类
            class VirtualMessageEvent:
                """虚拟消息事件（用于非 aiocqhttp 平台）"""

                def __init__(self):
                    self.unified_msg_origin = unified_msg_origin
                    self.session_id = chat_id
                    self.is_wake = True
                    self._extras = {}
                    self._stopped = False
                    self.plugins_name = None

                def set_extra(self, key: str, value):
                    self._extras[key] = value

                def get_extra(self, key: str, default=None):
                    return self._extras.get(key, default)

                def is_stopped(self) -> bool:
                    return self._stopped

                def stop_event(self):
                    self._stopped = True

            return VirtualMessageEvent()

        except Exception as e:
            logger.debug(f"[虚拟事件] 创建失败: {e}")
            return None

    # ========== 后台任务 ==========

    @classmethod
    async def _background_check_loop(
        cls, context: Context, config_getter, plugin_instance
    ):
        """
        后台检查循环（主逻辑）

        Args:
            context: AstrBot Context对象
            config_getter: 配置获取器（插件实例或配置字典）
            plugin_instance: 插件实例
        """
        if cls._debug_mode:
            logger.info("🔄 [主动对话后台任务] 已启动")

        # 🆕 v1.2.0 定期保存和衰减计时器
        last_save_time = time.time()
        last_decay_time = time.time()
        save_interval = 300  # 每5分钟保存一次
        decay_interval = 3600  # 每小时检查一次衰减

        while cls._is_running:
            try:
                # 获取当前配置
                if hasattr(config_getter, "config"):
                    config = config_getter.config
                else:
                    config = config_getter

                # 获取检查间隔

                check_interval = cls._proactive_check_interval

                # 等待下次检查
                await asyncio.sleep(check_interval)

                # 🆕 v1.2.0 定期保存状态（防止崩溃丢失数据）
                current_time = time.time()
                if current_time - last_save_time >= save_interval:
                    cls._save_states_to_disk()
                    last_save_time = current_time
                    if cls._debug_mode:
                        logger.info("💾 [自动保存] 主动对话状态已保存")

                # 🆕 v1.2.0 定期执行评分衰减
                if current_time - last_decay_time >= decay_interval:
                    cls.apply_score_decay()
                    cls.apply_complaint_decay()  # 🆕 同时执行累积失败次数的时间衰减
                    last_decay_time = current_time

                # 遍历所有群聊状态
                for chat_key in list(cls._chat_states.keys()):
                    try:
                        current_time = time.time()

                        # 🆕 v1.2.0 获取自适应参数（根据互动评分调整）
                        adaptive_params = cls.calculate_adaptive_parameters(chat_key)
                        max_failures = adaptive_params["max_failures"]
                        cooldown_duration = adaptive_params["cooldown_duration"]

                        # 固定参数

                        boost_duration = cls._proactive_temp_boost_duration

                        # ========== 连续尝试机制：检测维持期是否结束且未触发AI回复 ==========
                        state = cls.get_chat_state(chat_key)

                        in_retry_sequence = (
                            int(state.get("proactive_attempts_count", 0)) > 0
                        )

                        # 判断临时提升是否仍然有效
                        boost_info = cls._temp_probability_boost.get(chat_key)
                        boost_active = False
                        if boost_info and isinstance(boost_info, dict):
                            boost_active = current_time < float(
                                boost_info.get("boost_until", 0)
                            )

                        # 如果处于连续尝试序列中且临时提升仍然有效，则在维持期内不再触发新的主动对话
                        if in_retry_sequence and boost_active:
                            if cls._debug_mode:
                                logger.info(
                                    f"[连续尝试] 群{chat_key} 处于维持期内，跳过本轮should_trigger检查"
                                )
                            continue

                        # 如果处于连续尝试序列中，但临时提升已过期（且未被上层在AI决定回复时清理）
                        if in_retry_sequence and not boost_active:
                            # 结合 last_proactive_time + 配置的维持时长，双重判断避免错判
                            last_pt = float(state.get("last_proactive_time", 0))
                            if last_pt > 0 and current_time >= last_pt + boost_duration:
                                # 视为一次失败尝试
                                cls.record_proactive_failure(
                                    chat_key, max_failures, cooldown_duration, config
                                )

                                # 若进入冷却，跳过本轮
                                if cls.is_in_cooldown(chat_key):
                                    # 确保临时提升关闭、连续尝试清零
                                    try:
                                        cls.deactivate_temp_probability_boost(
                                            chat_key, "失败达到上限，进入冷却"
                                        )
                                    except Exception:
                                        pass
                                    state["proactive_attempts_count"] = 0
                                    continue

                                # 未达上限：立即进行下一次连续尝试（不再依赖沉默阈值）
                                try:
                                    # 连续尝试也需尊重白名单与禁用时段（有效概率>0）
                                    if not cls.is_group_enabled(chat_key):
                                        if cls._debug_mode:
                                            logger.info(
                                                f"[连续尝试] 群{chat_key} 不在白名单，跳过连续尝试"
                                            )
                                        continue

                                    base_prob = cls._proactive_probability
                                    eff_prob = cls.calculate_effective_probability(
                                        base_prob
                                    )
                                    if eff_prob <= 0:
                                        logger.info(
                                            f"[连续尝试] 群{chat_key} 处于禁用/极低时段，跳过本次连续尝试"
                                        )
                                        continue

                                    await cls.trigger_proactive_chat(
                                        context, config, plugin_instance, chat_key
                                    )
                                    # 进入下一轮后，继续处理下一个群
                                    continue
                                except Exception as e:
                                    logger.error(
                                        f"[连续尝试] 触发下一次主动对话失败: {e}",
                                        exc_info=True,
                                    )

                        # 检查是否应该触发主动对话
                        should_trigger, reason = cls.should_trigger_proactive_chat(
                            chat_key, config
                        )

                        if should_trigger:
                            # 触发主动对话
                            await cls.trigger_proactive_chat(
                                context, config, plugin_instance, chat_key
                            )
                        else:
                            # 如果概率判断失败，重置计时器
                            if "概率判断失败" in reason:
                                state = cls.get_chat_state(chat_key)
                                state["last_bot_reply_time"] = time.time()
                                if cls._debug_mode:
                                    logger.info(
                                        f"[主动对话检查] 群{chat_key} - {reason}，重置计时器"
                                    )

                    except Exception as e:
                        logger.error(
                            f"[主动对话检查] 群{chat_key} 检查失败: {e}",
                            exc_info=True,
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[主动对话后台任务] 发生错误: {e}", exc_info=True)

        if cls._debug_mode:
            logger.info("🛑 [主动对话后台任务] 已停止")

    @classmethod
    async def trigger_proactive_chat(
        cls,
        context: Context,
        config: dict,
        plugin_instance,
        chat_key: str,
    ):
        """
        触发主动对话（从后台任务调用）

        Args:
            context: AstrBot Context对象
            config: 插件配置
            plugin_instance: 插件实例（ChatPlus实例）
            chat_key: 群聊唯一标识
        """
        try:
            logger.info(f"✨ [主动对话触发] 群{chat_key} - 开始生成主动话题")

            # 从 chat_key 解析出基本信息
            # 注意：chat_key中存储的是platform_name（平台类型），但我们需要platform_id（适配器实例ID）
            is_private = False
            chat_id = None
            platform_name_from_key = None  # 从chat_key解析出的平台名称（可能是类型名）

            if ":" in chat_key:
                parts = chat_key.split(":")
                if len(parts) < 3:
                    logger.error(
                        f"[主动对话触发] 无效的 chat_key (冒号格式): {chat_key}"
                    )
                    return
                platform_name_from_key = parts[0]
                is_private = parts[1] == "private"
                chat_id = parts[2]
            elif "_" in chat_key:
                parts = chat_key.split("_")
                if len(parts) < 3:
                    logger.error(
                        f"[主动对话触发] 无效的 chat_key (下划线格式): {chat_key}"
                    )
                    return
                # chat_key 格式: {platform_name}_{chat_type}_{chat_id}
                # 例如: aiocqhttp_group_879646332
                platform_name_from_key = parts[0]  # 提取平台名称（类型）
                chat_type = parts[-2]
                chat_id = parts[-1]
                is_private = chat_type == "private"
            else:
                logger.error(f"[主动对话触发] 无法识别的 chat_key 格式: {chat_key}")
                return

            # ⚠️ 关键修复：获取正确的platform_id用于构造unified_msg_origin
            # unified_msg_origin需要使用platform_id（适配器实例ID），而不是platform_name（平台类型）
            platform_id = None

            # 方法1：尝试从context的platform_manager中查找匹配的platform_id
            try:
                if hasattr(context, "platform_manager") and hasattr(
                    context.platform_manager, "platform_insts"
                ):
                    # 优先尝试找到与platform_name_from_key匹配的平台实例
                    for platform_inst in context.platform_manager.platform_insts:
                        try:
                            meta = platform_inst.meta()
                            # 检查平台类型名称是否匹配
                            if meta.name == platform_name_from_key:
                                platform_id = meta.id
                                if cls._debug_mode:
                                    logger.info(
                                        f"[主动对话触发] 找到匹配的platform_id: {platform_id} (name: {meta.name})"
                                    )
                                break
                        except Exception:
                            continue

                    # 如果没找到匹配的，使用第一个平台实例
                    if not platform_id and context.platform_manager.platform_insts:
                        platform_id = (
                            context.platform_manager.platform_insts[0].meta().id
                        )
                        logger.warning(
                            f"[主动对话触发] 未找到匹配的平台，使用第一个: {platform_id}"
                        )
            except Exception as e:
                logger.warning(f"[主动对话触发] 从context获取platform_id失败: {e}")

            # 方法2：如果context方法失败，尝试从历史消息中获取
            if not platform_id:
                try:
                    from .context_manager import ContextManager

                    # 如果platform_name_from_key为空，说明chat_key格式有问题，跳过此群
                    if not platform_name_from_key:
                        logger.error(
                            f"[主动对话触发] chat_key解析失败，无法获取平台名称: {chat_key}"
                        )
                        return

                    # 使用platform_name_from_key尝试获取历史消息
                    temp_history = ContextManager.get_history_messages_by_params(
                        platform_name=platform_name_from_key,
                        is_private=is_private,
                        chat_id=chat_id,
                        max_messages=1,
                    )
                    if temp_history and len(temp_history) > 0:
                        msg = temp_history[0]
                        if (
                            isinstance(msg, AstrBotMessage)
                            and hasattr(msg, "platform_name")
                            and msg.platform_name
                        ):
                            platform_id = msg.platform_name
                            if cls._debug_mode:
                                logger.info(
                                    f"[主动对话触发] 从历史消息中获取platform_id: {platform_id}"
                                )
                except Exception as e:
                    logger.warning(f"[主动对话触发] 从历史消息获取platform_id失败: {e}")

            # 兜底：如果还是获取不到，使用从chat_key解析的值
            if not platform_id:
                if not platform_name_from_key:
                    logger.error(
                        f"[主动对话触发] 无法获取platform_id，跳过群 {chat_key}"
                    )
                    return
                platform_id = platform_name_from_key
                logger.warning(
                    f"[主动对话触发] 使用从chat_key解析的platform_id: {platform_id} (可能需要验证准确性)"
                )

            # 复用主流程的逻辑，但简化版本
            await cls._process_proactive_chat_simplified(
                context=context,
                config=config,
                plugin_instance=plugin_instance,
                platform_id=platform_id,  # 🔧 修复：传递platform_id而不是platform_name
                is_private=is_private,
                chat_id=chat_id,
                chat_key=chat_key,
            )

        except Exception as e:
            logger.error(f"[主动对话触发] 群{chat_key} 发生错误: {e}", exc_info=True)

    @classmethod
    async def _process_proactive_chat_simplified(
        cls,
        context: Context,
        config: dict,
        plugin_instance,
        platform_id: str,  # 🔧 修复：使用platform_id而不是platform_name
        is_private: bool,
        chat_id: str,
        chat_key: str,
    ):
        """
        处理主动对话（简化版，复用主流程逻辑）

        流程：
        1. 构造系统提示词（作为"用户消息"）
        2. 提取历史上下文（复用 ContextManager）
        3. 格式化上下文（复用 ContextManager.format_context_for_ai）
        4. 注入记忆、工具、情绪（复用相关逻辑）
        5. 调用AI生成回复（复用 ReplyHandler 逻辑）
        6. 发送回复
        7. 保存历史（保存系统提示词和AI回复）
        """
        try:
            # 动态导入
            from .context_manager import ContextManager
            from .reply_handler import ReplyHandler
            from .message_processor import MessageProcessor
            from .message_cleaner import MessageCleaner
            from .memory_injector import MemoryInjector
            from .tools_reminder import (
                ToolsReminder,
            )  # 保留导入以备其他地方调用，主动对话流程中不注入工具信息（避免浪费token）

            debug_mode = cls._debug_mode

            # ========== 🆕 并发保护：检查普通对话是否正在处理此会话（使用循环等待+锁机制）==========
            # 如果有普通对话正在处理，循环等待直到完成或超时
            # 🔒 使用锁保护检查-标记流程，避免与普通消息处理产生竞态条件
            if hasattr(plugin_instance, "processing_sessions") and hasattr(
                plugin_instance, "concurrent_lock"
            ):
                # 使用与普通消息并发保护相同的配置
                max_wait_loops = getattr(
                    plugin_instance, "concurrent_wait_max_loops", 10
                )
                wait_interval = getattr(
                    plugin_instance, "concurrent_wait_interval", 1.0
                )

                for loop_count in range(max_wait_loops):
                    # 🔒 获取锁进行原子性检查和标记
                    async with plugin_instance.concurrent_lock:
                        # 检查是否有普通对话正在处理此会话
                        processing_in_chat = [
                            msg_id
                            for msg_id, cid in plugin_instance.processing_sessions.items()
                            if cid == chat_id
                        ]

                        if not processing_in_chat:
                            # 没有普通对话在处理，立即标记主动对话并退出
                            if hasattr(
                                plugin_instance, "proactive_processing_sessions"
                            ):
                                plugin_instance.proactive_processing_sessions[
                                    chat_id
                                ] = time.time()
                                if debug_mode:
                                    logger.info(
                                        f"🔒 [主动对话-并发保护] 已标记会话 {chat_id} 为主动对话处理中"
                                    )
                            break

                    # 🔓 释放锁后再进行等待（避免阻塞其他消息）
                    if loop_count == 0:
                        logger.info(
                            f"🔒 [主动对话-并发保护] 会话 {chat_id} 有 {len(processing_in_chat)} 条普通消息正在处理中，"
                            f"开始等待（最多 {max_wait_loops} 次，每次 {wait_interval} 秒）..."
                        )

                    await asyncio.sleep(wait_interval)

                    if debug_mode:
                        logger.info(
                            f"  [主动对话-并发等待] 第 {loop_count + 1}/{max_wait_loops} 次检测..."
                        )
                else:
                    # 循环结束仍有消息在处理，跳过本次主动对话
                    async with plugin_instance.concurrent_lock:
                        still_processing = [
                            msg_id
                            for msg_id, cid in plugin_instance.processing_sessions.items()
                            if cid == chat_id
                        ]
                    if still_processing:
                        logger.warning(
                            f"⚠️ [主动对话-并发保护] 等待 {max_wait_loops * wait_interval:.1f} 秒后仍有 "
                            f"{len(still_processing)} 条普通消息在处理，跳过本次主动对话触发"
                        )
                        return
            elif hasattr(plugin_instance, "proactive_processing_sessions"):
                # 兜底：如果没有 concurrent_lock（旧版本），直接标记（不安全但保持兼容）
                plugin_instance.proactive_processing_sessions[chat_id] = time.time()
                if debug_mode:
                    logger.info(
                        f"⚠️ [主动对话-并发保护] concurrent_lock 不存在，使用兜底标记（不安全）"
                    )

            # ========== 步骤1: 构造系统提示词 ==========
            if cls._debug_mode:
                logger.info("[主动对话-步骤1] 构造系统提示词")

            # 构造详细的主动对话提示词（参考 reply_handler.py 的风格）
            default_proactive_prompt = """
你已经有一段时间没有说话了。现在你可以主动发起一个新话题，或者针对之前的对话内容做一些自然的延伸。

🔍 **【上下文说明】** 🔍：
- 历史上下文已按时间顺序排列，包括你回复过的、以及其他人之间的对话
- 标有 **【📦近期未回复】** 的条目是用户发送但你当时未予回复的消息，可作为了解近期话题的参考
- 如果有近期未回复消息，你可以选择自然地回应这些话题，或发起全新话题，取决于你的判断
- **真正读懂上下文，不要走马观花**：
  * 认真看清楚每条消息是谁说的、在聊什么、有没有未解答的问题或值得接的话头
  * 感受一下群里整体的氛围和情绪，再决定说什么
  * 不要只瞄一眼最后几条就随便凑一句话——先摸清楚背景再开口
- **主动话题的来源**（优先级从高到低）：
  * ✅ **最佳选择**：基于近期未回复消息延伸话题（如果有有价值的内容）
  * ✅ **次选**：基于更早的历史对话延伸话题
  * ✅ **可选**：发起完全新的话题（但最好与群氛围相关）

核心要求：
1. **话题要自然** - 不要生硬，就像是你自己突然想到了什么话题
2. **可以是问题、分享、或感想** - 展现你的个性和想法
3. **避免低质量开场** - 禁止"在吗"、"干嘛呢"、"有人吗"等无聊开场
4. **与上下文相关** - 最好与之前的聊天内容（特别是近期未回复消息）或群氛围相关
5. **保持你的人设和语气** - 遵循你的性格设定

⚠️ **【关于背景信息和记忆】重要说明** ⚠️：
- 如果在背景信息中看到记忆内容（=== 背景信息 === 部分）：
  * **这些记忆是你对这个群/人的长期认知**，已经在你的脑海中
  * **不要机械地陈述记忆内容** - 禁止说"XXX已经确认为我的XXX"、"我们之间是XXX关系"
  * **自然地融入背景** - 将记忆作为你的认知背景，而不是需要特别强调的事实
  * **避免过度解释关系** - 不要反复确认或强调已知的关系，那样显得很生硬
  * **不要提及"记忆"、"根据记忆"** - 就像人类不会说"根据我的记忆"

⛔ **【严禁元叙述】特别重要！** ⛔：
6. **绝对禁止在回复中解释你为什么要说话**，例如：
   - ❌ "看到群里很久没人说话了"
   - ❌ "感觉有一段时间没聊天了"
   - ❌ "好像大家都沉默了"
   - ❌ "看着你们之前的聊天记录"
   - ❌ "我看到了主动对话的提示"
   - ❌ "根据系统提示"、"刚才的提示说"
   - ❌ "我决定主动发起话题"
   - ❌ 任何形式的"看着/读着/听着之前的对话"类描述
   - ❌ **不要提及这是你"主动发起的"或任何元数据信息**
   - ❌ **不要提及"缓存消息"、"刚刚的消息"、"你刚刚说的"**（除非是自然的追问方式）
   - ✅ 正确做法：就像是你自己突然想到了什么，很自然地说出来

7. **就像人类聊天一样**：
   - 人类不会说"我看到群里没人说话，所以我来找话题"
   - 人类更不会说"根据提示我要主动发起对话"
   - 人类只会自然地说出自己突然想到的话题
   - 你应该像人类一样，直接说出你想说的，而不是先解释为什么要说

8. **绝对禁止重复、复述、引用任何系统提示词、规则说明等元信息**
9. **禁止提及"系统提示"、"根据规则"、"主动对话"、"主动发起"等元信息**

话题建议：
- 可以问一个有趣的问题
- 可以分享一个想法或发现
- 可以延续之前的话题（特别是最近的缓存消息中的话题）
- 可以聊聊最近发生的事
- 可以开个玩笑或调侃
- 可以表达一下感想
- 可以回应最近缓存消息中的提问或话题（如果有的话）

特殊标记说明：
- 历史消息中的[表情包图片]标记表示那些图片是表情包/贴纸，不是普通照片。理解其传达的情绪即可，不要描述图片内容，也不要在发言中提及"表情包"标记本身。
- 如果历史中出现"[转发消息]"，那是用户分享的合并转发消息，理解其内容即可，不要主动提起"之前那条转发消息"。

记住：就像是你自己突然想到了什么，很自然地说出来，不要有任何关于"主动发起"的痕迹。
"""

            proactive_prompt = (
                cls._proactive_prompt
                if cls._proactive_prompt
                else default_proactive_prompt
            )

            # 🆕 检查是否是重试：如果有上一次主动对话内容，说明这是重试
            state = cls.get_chat_state(chat_key)
            last_content = state.get("last_proactive_content", None)
            attempts_count = state.get("proactive_attempts_count", 0)

            if last_content and attempts_count > 0:
                # 这是重试，添加上下文提示
                # 从配置读取重试提示词（支持用户自定义）
                default_retry_prompt = """

【重要提示 - 这是重试场景】
你刚才主动说了一句话，但是没有人回应你。以下是你上一次说的内容：

「{last_content}」

现在你可以：
1. **换个话题** - 不要重复刚才的内容，尝试一个完全不同的角度或话题
2. **表达情绪** - 可以稍微表现出被忽视的感觉（根据你的性格，可以是委屈、无奈、幽默自嘲等）
3. **调整策略** - 如果刚才的话题太严肃/太轻松，可以调整一下
4. **保持自然** - 不要说"刚才我说了XXX"，要像人类一样自然地转换话题

⚠️ 重要：虽然你知道上次没人理你，但**不要在回复中明确提及"刚才"、"上次"、"之前我说的"**等，
要表现得像是你自己自然地想到了新话题，或者用更委婉的方式表达（比如"算了"、"好吧"、"那换个话题"等）。
"""

                retry_prompt_template = (
                    cls._proactive_retry_prompt
                    if cls._proactive_retry_prompt
                    else default_retry_prompt
                )

                # 替换 {last_content} 占位符为实际内容
                retry_context = retry_prompt_template.format(last_content=last_content)

                proactive_prompt = retry_context + "\n" + proactive_prompt

                if debug_mode:
                    logger.info(
                        f"🔄 [主动对话-重试] 群{chat_key} - "
                        f"检测到重试（尝试{attempts_count}次），已注入上次内容提示"
                    )

            # 🔧 修复：检查吐槽系统（如果满足条件）
            complaint_info = cls.generate_complaint_prompt(chat_key, config)
            is_complaint_triggered = complaint_info.get("triggered", False)
            complaint_priority = complaint_info.get("priority", False)
            complaint_prompt_text = complaint_info.get("prompt", "")
            complaint_level = complaint_info.get("level", "none")

            # 🔧 修复：根据吐槽优先级决定提示词
            if is_complaint_triggered and complaint_priority:
                # 吐槽优先：只使用吐槽提示词，不使用普通主动对话提示词
                proactive_prompt = complaint_prompt_text
                logger.info(
                    f"🤐 [主动对话-吐槽触发] 群{chat_key} - "
                    f"累积失败{complaint_info.get('failure_count', 0)}次，"
                    f"触发{complaint_level}级吐槽，优先发送吐槽信息"
                )
            elif is_complaint_triggered and complaint_prompt_text:
                # 普通模式：附加吐槽提示词到主动对话提示词
                proactive_prompt += complaint_prompt_text
                logger.info(
                    f"💬 [主动对话-吐槽附加] 群{chat_key} - "
                    f"累积失败{complaint_info.get('failure_count', 0)}次，"
                    f"触发{complaint_level}级吐槽，附加到主动对话"
                )

            # 🔧 优化：根据是否是重试场景，使用不同的标记
            if last_content and attempts_count > 0:
                # 重试场景：使用"再次尝试"标记而不是"主动发起新话题"
                proactive_system_prompt = f"[🔄再次尝试对话]\n{proactive_prompt}"
            else:
                # 首次主动对话：使用原有的"主动发起新话题"标记
                proactive_system_prompt = f"[🎯主动发起新话题]\n{proactive_prompt}"

            proactive_system_prompt = MessageCleaner.mark_proactive_chat_message(
                proactive_system_prompt
            )

            # 🆕 v1.2.x: 如果开启了时间戳功能，在提示词最前面添加当前时间

            if cls._include_timestamp:
                try:
                    dt = datetime.now()
                    weekday_names = [
                        "周一",
                        "周二",
                        "周三",
                        "周四",
                        "周五",
                        "周六",
                        "周日",
                    ]
                    weekday = weekday_names[dt.weekday()]
                    current_time_str = dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")
                    proactive_system_prompt = (
                        f"[{current_time_str}] {proactive_system_prompt}"
                    )
                except Exception as e:
                    if debug_mode:
                        logger.warning(f"[主动对话] 生成时间戳失败: {e}")

            # ========== 步骤1.5: 🆕 注入注意力用户信息（如果启用）==========

            if cls._enable_attention_mechanism and cls._proactive_use_attention:
                if debug_mode:
                    logger.info("[主动对话-步骤1.5] 注入注意力用户信息")

                try:
                    # 🆕 步骤1.5.1: 概率判断是否参考注意力排行榜

                    reference_probability = (
                        cls._proactive_attention_reference_probability
                    )
                    should_reference = random.random() < reference_probability

                    if debug_mode or cls._debug_mode:
                        logger.info(
                            f"[主动对话-注意力] 参考排行榜概率: {reference_probability:.2f}, "
                            f"本次{'参考' if should_reference else '不参考'}排行榜"
                        )

                    if not should_reference:
                        # 不参考排行榜，跳过注意力用户注入
                        if debug_mode or cls._debug_mode:
                            logger.info(
                                "[主动对话-注意力] 本次主动对话不参考注意力排行榜，"
                                "将进行随机话题"
                            )
                    else:
                        # 导入注意力管理器
                        from .attention_manager import AttentionManager

                        # 🆕 步骤1.5.2: 解析权重配置并获取候选用户
                        # 解析权重字符串配置

                        weight_str = cls._proactive_attention_rank_weights
                        rank_weights = cls.parse_rank_weights(weight_str)

                        # 根据权重配置数量决定候选池大小
                        # 例如配置了6个权重，就获取前6名用户
                        candidate_pool_size = len(rank_weights)

                        # 获取高注意力用户列表（数量由权重配置决定）
                        attention_platform_name = platform_id
                        top_users = await AttentionManager.get_top_attention_users(
                            platform_name=attention_platform_name,
                            is_private=is_private,
                            chat_id=chat_id,
                            limit=candidate_pool_size,
                        )

                    if should_reference and top_users and len(top_users) > 0:
                        # 🆕 步骤1.5.3: 智能选择要关注的用户（基于权重）
                        state = cls.get_chat_state(chat_key)

                        # 获取最多选择数量

                        max_selected = cls._proactive_attention_max_selected_users

                        # 准备候选用户列表（取实际用户数和权重配置数的较小值）
                        candidates = top_users[: min(len(rank_weights), len(top_users))]

                        # 如果实际候选数小于权重配置数，只使用对应数量的权重
                        effective_weights = rank_weights[: len(candidates)]

                        if debug_mode or cls._debug_mode:
                            logger.info(
                                f"[主动对话-注意力] 候选池: {len(candidates)}个用户, "
                                f"权重分布: {', '.join([f'第{i + 1}名={w:.1%}' for i, w in enumerate(effective_weights)])}"
                            )

                        # 使用加权随机选择用户
                        selected_users = []
                        available_indices = list(range(len(candidates)))

                        # 根据权重进行加权随机选择
                        for _ in range(min(max_selected, len(candidates))):
                            if not available_indices:
                                break

                            # 获取当前可用候选的权重
                            current_weights = [
                                effective_weights[i] for i in available_indices
                            ]

                            # 加权随机选择（random.choices内部会自动归一化）
                            selected_idx = random.choices(
                                available_indices, weights=current_weights, k=1
                            )[0]

                            selected_users.append(
                                {
                                    "user": candidates[selected_idx],
                                    "rank": selected_idx + 1,
                                }
                            )

                            # 从可用列表中移除已选择的
                            available_indices.remove(selected_idx)

                        # 按排名排序选中的用户（第1名在前）
                        selected_users.sort(key=lambda x: x["rank"])

                        if debug_mode or cls._debug_mode:
                            selected_names = [
                                f"{s['user'].get('user_name', '未知')}(第{s['rank']}名)"
                                for s in selected_users
                            ]
                            logger.info(
                                f"[主动对话-注意力] 智能选择了 {len(selected_users)} 个用户: "
                                f"{', '.join(selected_names)}"
                            )

                        # 检查是否有上一次互动的用户记录
                        last_attention_user = state.get("last_attention_user_id", None)
                        last_attention_user_name = state.get(
                            "last_attention_user_name", None
                        )

                        # 判断是否要特别关注上一次的用户（概率控制）
                        focus_last_user = False

                        focus_probability = cls._proactive_focus_last_user_probability
                        if (
                            last_attention_user
                            and last_attention_user_name
                            and random.random() < focus_probability
                        ):
                            # 检查上次用户是否在本次选中的用户中
                            if any(
                                s["user"].get("user_id") == last_attention_user
                                for s in selected_users
                            ):
                                focus_last_user = True
                                if debug_mode or cls._debug_mode:
                                    logger.info(
                                        f"[主动对话-注意力] 概率命中({focus_probability:.2f})，"
                                        f"将特别关注上一次的用户: {last_attention_user_name}"
                                    )

                        # 记录当前最高注意力用户（用于下次参考）
                        # 注意：这里记录的是实际选中的最高排名用户
                        if selected_users and selected_users[0]["user"].get("user_id"):
                            state["last_attention_user_id"] = selected_users[0][
                                "user"
                            ].get("user_id")
                            state["last_attention_user_name"] = selected_users[0][
                                "user"
                            ].get("user_name", "未知")

                        # 🆕 步骤1.5.4: 构造智能化的注意力用户提示词
                        attention_info = "\n\n=== 💡 当前对话焦点 ===\n"
                        if len(selected_users) == 1:
                            attention_info += "你可以适当关注以下用户：\n\n"
                        else:
                            attention_info += (
                                "你可以适当关注以下用户（按注意力从高到低）：\n\n"
                            )

                        # 🔧 检查是否启用@转换，决定是否在提示词中展示用户ID
                        enable_at_conversion = cls._enable_proactive_at_conversion

                        # 构造选中用户的信息列表
                        for idx, selected in enumerate(selected_users, 1):
                            user = selected["user"]
                            rank = selected["rank"]
                            user_name = user.get("user_name", "未知用户")
                            user_id = user.get("user_id", "")
                            attention_score = user.get("attention_score", 0.0)
                            emotion = user.get("emotion", 0.0)

                            # 判断是否是上一次关注的用户
                            is_last_user = (
                                focus_last_user and user_id == last_attention_user
                            )

                            # 构造情绪描述
                            if emotion > 0.6:
                                emotion_desc = "（情绪：非常积极✨）"
                            elif emotion > 0.3:
                                emotion_desc = "（情绪：较为积极😊）"
                            elif emotion > -0.3:
                                emotion_desc = "（情绪：中性😐）"
                            elif emotion > -0.6:
                                emotion_desc = "（情绪：有些消极😔）"
                            else:
                                emotion_desc = "（情绪：较为消极😞）"

                            # 构造用户ID显示（仅在启用@转换时展示）
                            id_display = (
                                f" (ID: {user_id})"
                                if enable_at_conversion and user_id
                                else ""
                            )

                            # 添加用户信息
                            prefix = f"{idx}. "
                            if is_last_user:
                                prefix = f"{idx}. ⭐ "
                                attention_info += (
                                    f"{prefix}**{user_name}**{id_display} "
                                    f"[注意力: {attention_score:.2f}] {emotion_desc}\n"
                                )
                                attention_info += (
                                    f"   💬 提示：这是你上一次主要互动的对象，"
                                    f"可以考虑延续之前的话题或关心ta的近况\n\n"
                                )
                            else:
                                attention_info += (
                                    f"{prefix}{user_name}{id_display} "
                                    f"[注意力: {attention_score:.2f}] {emotion_desc}\n"
                                )

                        attention_info += (
                            "\n💡 **使用建议**：\n"
                            "- 你可以根据上述用户的注意力和情绪，选择合适的话题方向\n"
                            "- 但这只是参考，不一定非要提到他们，也可以聊其他话题\n"
                            "- 如果选择关注这些用户，请自然地融入话题，不要显得刻意\n"
                            '- ⚠️ 重要：不要在回复中提及"注意力"、"情绪"、"排行榜"等元信息\n'
                        )

                        # 🆕 当启用@转换时，告诉AI可以使用[at:ID]格式
                        if enable_at_conversion:
                            attention_info += (
                                "- 💬 如果你想@某个用户，请使用 [at:用户ID] 格式"
                                "（如 [at:123456]），系统会自动转换为真实的@消息\n"
                            )

                        # 将注意力信息添加到提示词中
                        proactive_system_prompt += attention_info

                        if debug_mode or cls._debug_mode:
                            logger.info(
                                f"[主动对话-注意力] 已智能选择并注入 {len(selected_users)} 个用户信息"
                            )
                            if focus_last_user:
                                logger.info(
                                    f"[主动对话-注意力] 特别标记了上一次互动用户: {last_attention_user_name}"
                                )
                    else:
                        if debug_mode or cls._debug_mode:
                            logger.info("[主动对话-注意力] 没有找到高注意力用户")

                except Exception as e:
                    logger.warning(
                        f"[主动对话-注意力] 注入注意力用户信息失败: {e}",
                        exc_info=True,
                    )

            # ========== 步骤2: 提取历史上下文（从官方对话系统提取，与主动回复逻辑一致）==========
            if debug_mode:
                logger.info("[主动对话-步骤2] 提取历史上下文（从官方对话系统）")

            max_context = cls._max_context_messages

            # 🔧 配置矫正：处理类型和异常值
            # 1. 首先确保是整数类型（配置文件可能传入字符串）
            if not isinstance(max_context, int):
                try:
                    max_context = int(max_context)
                    if debug_mode:
                        logger.info(
                            f"[主动对话-配置矫正] max_context_messages 从 {type(cls._max_context_messages).__name__} 转换为 int: {max_context}"
                        )
                except (ValueError, TypeError):
                    logger.warning(
                        f"⚠️ [主动对话-配置矫正] max_context_messages 配置值 '{cls._max_context_messages}' 无法转换为整数，已矫正为 -1（不限制）"
                    )
                    max_context = -1

            # 2. 处理异常值（小于 -1 的情况）
            if isinstance(max_context, int) and max_context < -1:
                logger.warning(
                    f"⚠️ [主动对话-配置矫正] max_context_messages 配置值 {max_context} 小于 -1，已矫正为 -1（不限制）"
                )
                max_context = -1

            if debug_mode:
                context_limit_desc = (
                    "不限制"
                    if max_context == -1
                    else "不获取历史"
                    if max_context == 0
                    else f"限制为 {max_context} 条"
                )
                logger.info(
                    f"[主动对话] 上下文限制: {max_context} ({context_limit_desc})"
                )

            history_messages = []

            # 🔧 修复：使用platform_id构造unified_msg_origin，与普通流程保持一致
            # unified_msg_origin格式：{platform_id}:{MessageType}:{chat_id}
            # 这与AstrBot框架中event.unified_msg_origin的格式完全一致
            message_type_str = "FriendMessage" if is_private else "GroupMessage"
            unified_msg_origin = f"{platform_id}:{message_type_str}:{chat_id}"

            # 关键日志：显示构造的 unified_msg_origin，用于排查记忆获取问题
            logger.info(
                f"[主动对话] 构造会话标识:\n"
                f"  unified_msg_origin: {unified_msg_origin}\n"
                f"  platform_id: {platform_id}\n"
                f"  chat_id: {chat_id}\n"
                f"  is_private: {is_private}"
            )

            # 尝试从官方对话系统提取历史（与主动回复逻辑一致）
            try:
                cm = context.conversation_manager
                if cm:
                    # 获取当前对话ID
                    curr_cid = await cm.get_curr_conversation_id(unified_msg_origin)
                    if curr_cid:
                        # 获取对话对象
                        conversation = await cm.get_conversation(
                            unified_msg_origin=unified_msg_origin,
                            conversation_id=curr_cid,
                        )
                        if conversation and conversation.history:
                            # 解析官方对话系统的历史记录
                            try:
                                official_history = json.loads(conversation.history)
                                if debug_mode:
                                    logger.info(
                                        f"[主动对话] 从官方对话系统获取到 {len(official_history)} 条历史记录"
                                    )

                                # 🔧 修复：过滤掉人设预设对话（begin_dialogs）
                                # conversation.history 存储了完整的 LLM 对话记录，
                                # 开头部分包含人设的预设对话示例（begin_dialogs）。
                                # 如果不过滤，这些预设对话会被当作真实历史消息，
                                # 经过 format_context_for_ai() 后添加时间戳和发送者前缀，
                                # 导致 AI 看到类似 "[时间] 用户(ID:user): <预设内容>" 的假历史。
                                try:
                                    persona_for_filter = await context.persona_manager.get_default_persona_v3(
                                        unified_msg_origin
                                    )
                                    begin_dialogs_to_filter = persona_for_filter.get(
                                        "_begin_dialogs_processed", []
                                    )
                                    if begin_dialogs_to_filter and len(
                                        official_history
                                    ) >= len(begin_dialogs_to_filter):
                                        # 检查历史记录开头是否与 begin_dialogs 匹配
                                        match = True
                                        for i, bd in enumerate(begin_dialogs_to_filter):
                                            hist_entry = official_history[i]
                                            if (
                                                not isinstance(hist_entry, dict)
                                                or hist_entry.get("role")
                                                != bd.get("role")
                                                or hist_entry.get("content")
                                                != bd.get("content")
                                            ):
                                                match = False
                                                break
                                        if match:
                                            skip_count = len(begin_dialogs_to_filter)
                                            official_history = official_history[
                                                skip_count:
                                            ]
                                            logger.info(
                                                f"[主动对话] 已过滤 {skip_count} 条人设预设对话（begin_dialogs）"
                                            )
                                except Exception as e:
                                    if debug_mode:
                                        logger.warning(
                                            f"[主动对话] 过滤 begin_dialogs 失败: {e}，继续使用原始历史"
                                        )

                                # 🆕 优化：在转换前先截断，防止内存溢出
                                # 硬上限保护：即使配置为-1，也限制最大500条
                                HARD_LIMIT = 500
                                if max_context == -1:
                                    effective_limit = HARD_LIMIT
                                elif max_context == 0:
                                    effective_limit = 0
                                else:
                                    # 预留一些空间给缓存消息合并
                                    effective_limit = min(max_context + 50, HARD_LIMIT)

                                if len(official_history) > effective_limit:
                                    original_count = len(official_history)
                                    official_history = official_history[
                                        -effective_limit:
                                    ]
                                    if debug_mode:
                                        logger.info(
                                            f"[主动对话] 官方历史在转换前截断: {original_count} -> {len(official_history)} 条"
                                        )

                                # 🔧 修复：提前获取真实的bot ID，用于正确标记AI的历史回复
                                # 这样在格式化上下文时才能识别出哪些是bot的回复，添加"禁止重复"标记
                                real_bot_id = ""
                                try:
                                    if hasattr(context, "get_self_id"):
                                        real_bot_id = context.get_self_id()
                                except:
                                    pass
                                # 如果无法获取真实ID，使用"bot"作为后备方案
                                if not real_bot_id:
                                    real_bot_id = "bot"

                                # 将官方历史转换为AstrBotMessage格式（用于格式化上下文）
                                # 只提取用户消息和AI回复，转换为AstrBotMessage对象
                                for idx, msg in enumerate(official_history):
                                    if (
                                        isinstance(msg, dict)
                                        and "role" in msg
                                        and "content" in msg
                                    ):
                                        msg_obj = AstrBotMessage()
                                        msg_obj.message_str = msg["content"]
                                        msg_obj.platform_name = (
                                            platform_id  # 🔧 修复：使用platform_id
                                        )
                                        # 🔧 修复：尝试从消息中获取真实时间戳，如果没有则使用索引模拟时间顺序
                                        # 这样可以保证消息的时间顺序，避免所有消息都是当前时间
                                        if "timestamp" in msg and msg["timestamp"]:
                                            msg_obj.timestamp = msg["timestamp"]
                                        else:
                                            # 使用当前时间减去索引，确保时间递增
                                            msg_obj.timestamp = (
                                                int(time.time())
                                                - (len(official_history) - idx) * 60
                                            )

                                        msg_obj.type = (
                                            MessageType.GROUP_MESSAGE
                                            if not is_private
                                            else MessageType.FRIEND_MESSAGE
                                        )
                                        if not is_private:
                                            msg_obj.group_id = chat_id
                                        msg_obj.session_id = chat_id

                                        # 根据role设置发送者信息
                                        if msg["role"] == "assistant":
                                            # AI的回复
                                            # 🔧 修复：使用真实的bot ID，而不是硬编码"bot"
                                            # 这样在format_context_for_ai中才能正确识别bot的回复，添加"禁止重复"标记
                                            msg_obj.sender = MessageMember(
                                                user_id=real_bot_id, nickname="AI"
                                            )
                                            # 同时设置self_id，确保能被正确识别
                                            msg_obj.self_id = real_bot_id
                                        else:
                                            # 用户消息
                                            msg_obj.sender = MessageMember(
                                                user_id="user", nickname="用户"
                                            )

                                        history_messages.append(msg_obj)

                                # 🔧 修复：按历史截止时间戳过滤，丢弃插件重置之前的旧消息
                                try:
                                    from ...utils.context_manager import (
                                        ContextManager as _GroupCM,
                                    )

                                    _cutoff_ts = _GroupCM.get_history_cutoff(chat_id)
                                    if _cutoff_ts > 0 and history_messages:
                                        _before = len(history_messages)
                                        history_messages = [
                                            _m
                                            for _m in history_messages
                                            if (getattr(_m, "timestamp", 0) or 0)
                                            >= _cutoff_ts
                                        ]
                                        _filtered = _before - len(history_messages)
                                        if _filtered > 0:
                                            logger.info(
                                                f"[主动对话-私信] 历史截止过滤: 丢弃 {_filtered} 条旧消息 "
                                                f"(cutoff={_cutoff_ts}, chat_id={chat_id})"
                                            )
                                except Exception:
                                    pass

                                if debug_mode:
                                    logger.info(
                                        f"[主动对话] 已转换 {len(history_messages)} 条历史消息为AstrBotMessage格式"
                                    )

                            except (json.JSONDecodeError, TypeError) as parse_err:
                                logger.warning(
                                    f"[主动对话] 解析官方历史记录失败: {parse_err}"
                                )
                    else:
                        if debug_mode:
                            logger.info(
                                f"[主动对话] 官方对话系统没有对话记录（对话ID: {curr_cid}）"
                            )
            except Exception as e:
                logger.warning(f"[主动对话] 从官方对话系统提取历史失败: {e}")
                if debug_mode:
                    logger.info(f"[主动对话] 错误详情: {e}", exc_info=True)

            # 如果从官方对话系统获取不到历史，尝试从自定义存储获取（作为fallback）
            # 但如果配置为0，则不获取任何历史
            if not history_messages and not (
                isinstance(max_context, int) and max_context == 0
            ):
                if debug_mode:
                    logger.info("[主动对话] 官方对话系统无历史，尝试从自定义存储获取")

                # 🆕 v1.2.0: 使用新的统一方法获取历史消息（优先官方存储，回退自定义存储）
                # 先准备缓存消息
                cached_astrbot_messages_for_fallback = []
                if (
                    hasattr(plugin_instance, "pending_messages_cache")
                    and chat_id in plugin_instance.pending_messages_cache
                    and len(plugin_instance.pending_messages_cache[chat_id]) > 0
                ):
                    # 🔧 修复：过滤过期的缓存消息，避免使用已过期但未清理的消息
                    cached_messages_raw = cls.filter_expired_cached_messages(
                        plugin_instance.pending_messages_cache[chat_id]
                    )
                    for cached_msg in cached_messages_raw:
                        if isinstance(cached_msg, dict):
                            try:
                                msg_obj = AstrBotMessage()
                                msg_obj.message_str = cached_msg.get("content", "")
                                msg_obj.platform_name = platform_name
                                msg_obj.timestamp = cached_msg.get(
                                    "message_timestamp"
                                ) or cached_msg.get("timestamp", time.time())
                                msg_obj.type = (
                                    MessageType.FRIEND_MESSAGE
                                    if is_private
                                    else MessageType.GROUP_MESSAGE
                                )
                                if not is_private:
                                    msg_obj.group_id = chat_id
                                msg_obj.self_id = self_id
                                msg_obj.session_id = chat_id
                                msg_obj.message_id = (
                                    f"cached_{cached_msg.get('timestamp', time.time())}"
                                )
                                sender_id = cached_msg.get("sender_id", "")
                                sender_name = cached_msg.get("sender_name", "未知用户")
                                if sender_id:
                                    msg_obj.sender = MessageMember(
                                        user_id=sender_id, nickname=sender_name
                                    )
                                cached_astrbot_messages_for_fallback.append(msg_obj)
                            except Exception as e:
                                if debug_mode:
                                    logger.warning(f"[主动对话] 转换缓存消息失败: {e}")
                        elif isinstance(cached_msg, AstrBotMessage):
                            cached_astrbot_messages_for_fallback.append(cached_msg)

                # 使用新的统一方法获取历史消息
                history_messages = await ContextManager.get_history_messages_by_params_with_fallback(
                    platform_name=platform_id,  # 🔧 修复：使用platform_id作为platform_name
                    platform_id=platform_id,
                    is_private=is_private,
                    chat_id=chat_id,
                    bot_id=self_id,
                    max_messages=max_context,
                    context=context,
                    cached_messages=cached_astrbot_messages_for_fallback,
                )

                if debug_mode:
                    logger.info(
                        f"[主动对话] 使用统一方法获取到 {len(history_messages)} 条历史消息"
                    )

                # 如果获取不到历史消息，尝试从所有可用平台中查找（兼容性代码）
                if not history_messages or len(history_messages) == 0:
                    if debug_mode:
                        logger.info(
                            f"[主动对话] 使用platform_id={platform_id}未获取到历史消息，尝试从所有平台查找"
                        )

                    # 获取所有可用平台
                    available_platforms = []
                    try:
                        if hasattr(context, "platform_manager") and hasattr(
                            context.platform_manager, "platform_insts"
                        ):
                            for platform in context.platform_manager.platform_insts:
                                platform_inst_id = (
                                    platform.meta().id
                                    if hasattr(platform, "meta")
                                    else "unknown"
                                )
                                available_platforms.append(platform_inst_id)
                    except Exception as e:
                        logger.warning(f"[主动对话] 获取可用平台列表失败: {e}")

                    # 尝试每个平台获取历史消息
                    for test_platform in available_platforms:
                        if test_platform == platform_id:
                            continue  # 已经试过了
                        try:
                            test_history = await ContextManager.get_history_messages_by_params_with_fallback(
                                platform_name=test_platform,
                                platform_id=test_platform,
                                is_private=is_private,
                                chat_id=chat_id,
                                bot_id=self_id,
                                max_messages=max_context,
                                context=context,
                                cached_messages=cached_astrbot_messages_for_fallback,
                            )
                            if test_history and len(test_history) > 0:
                                # 找到了历史消息，更新platform_name
                                platform_name = test_platform
                                history_messages = test_history
                                if cls._debug_mode:
                                    logger.info(
                                        f"[主动对话] 从平台 {test_platform} 获取到历史消息，更新platform_name"
                                    )
                                break
                        except Exception as e:
                            if debug_mode:
                                logger.info(
                                    f"[主动对话] 尝试平台 {test_platform} 获取历史消息失败: {e}"
                                )
                            continue

            # 🆕 v1.2.0: 缓存消息已在 get_history_messages_by_params_with_fallback 中处理
            # 以下代码保留用于兼容性，但实际上缓存已经在上面合并
            cached_messages_to_merge = []
            if debug_mode:
                logger.info(f"[主动对话] 缓存消息已在统一方法中合并，跳过重复合并")

            # 以下为兼容性占位代码
            if False:  # 保留原有逻辑结构，但不执行
                history_contents = set()
                if history_messages:
                    for msg in history_messages:
                        if isinstance(msg, AstrBotMessage) and hasattr(
                            msg, "message_str"
                        ):
                            content = msg.message_str
                            history_contents.add(content)
                            if ":" in content and len(content) > 20:
                                parts = content.split(":", 2)
                                if len(parts) >= 3:
                                    raw_content = parts[2].strip()
                                    if raw_content:
                                        history_contents.add(raw_content)
                        elif isinstance(msg, dict) and "content" in msg:
                            history_contents.add(msg["content"])

                    # 检查缓存消息是否已在历史中（去重
                    for cached_msg in cached_messages:
                        if isinstance(cached_msg, dict) and "content" in cached_msg:
                            cached_content = cached_msg.get("content", "").strip()
                            if cached_content:
                                # 检查是否重复
                                if cached_content not in history_contents:
                                    cached_messages_to_merge.append(cached_msg)
                                elif debug_mode:
                                    logger.info(
                                        f"[主动对话] 跳过重复的缓存消息: {cached_content[:50]}..."
                                    )
                elif cached_messages:
                    # 如果没有历史消息，所有缓存消息都需要合并
                    cached_messages_to_merge = cached_messages

                if debug_mode and cached_messages_to_merge:
                    logger.info(
                        f"[主动对话] 将合并 {len(cached_messages_to_merge)} 条缓存消息到历史上下文"
                    )

            # 转换缓存消息为 AstrBotMessage 对象
            if cached_messages_to_merge:
                if history_messages is None:
                    history_messages = []

                # 获取 self_id
                self_id = None
                if history_messages:
                    for msg in history_messages:
                        if (
                            isinstance(msg, AstrBotMessage)
                            and hasattr(msg, "self_id")
                            and msg.self_id
                        ):
                            self_id = msg.self_id
                            break

                for cached_msg in cached_messages_to_merge:
                    if isinstance(cached_msg, dict):
                        try:
                            msg_obj = AstrBotMessage()
                            msg_obj.message_str = cached_msg.get("content", "")
                            msg_obj.platform_name = (
                                platform_id  # 🔧 修复：使用platform_id
                            )
                            msg_obj.timestamp = cached_msg.get("timestamp", time.time())
                            msg_obj.type = (
                                MessageType.GROUP_MESSAGE
                                if not is_private
                                else MessageType.FRIEND_MESSAGE
                            )
                            if not is_private:
                                msg_obj.group_id = chat_id
                            msg_obj.self_id = self_id or ""
                            msg_obj.session_id = chat_id
                            msg_obj.message_id = (
                                f"cached_{cached_msg.get('timestamp', time.time())}"
                            )

                            sender_id = cached_msg.get("sender_id", "")
                            sender_name = cached_msg.get("sender_name", "未知用户")
                            if sender_id:
                                msg_obj.sender = MessageMember(
                                    user_id=sender_id, nickname=sender_name
                                )

                            history_messages.append(msg_obj)
                        except Exception as e:
                            logger.warning(
                                f"[主动对话] 转换缓存消息失败: {e}，跳过该消息"
                            )

                if debug_mode:
                    logger.info(
                        f"[主动对话] ✅ 已合并 {len(cached_messages_to_merge)} 条缓存消息到历史上下文"
                    )
                elif cls._debug_mode:
                    logger.info(
                        f"[主动对话] 已合并 {len(cached_messages_to_merge)} 条缓存消息（来自主动回复模式）"
                    )

            # 🆕 优化：合并后按时间戳排序（确保时间线连续）
            # 这样可以形成完整的时间线，避免上下文跳跃
            if history_messages and len(history_messages) > 0:
                # 按时间戳排序
                history_messages.sort(
                    key=lambda msg: (
                        msg.timestamp
                        if hasattr(msg, "timestamp") and msg.timestamp
                        else 0
                    )
                )
                if debug_mode:
                    logger.info(
                        f"[主动对话] 已按时间戳排序，形成完整上下文时间线（共 {len(history_messages)} 条）"
                    )

            # 🆕 优化：应用上下文限制 - 智能截断策略
            # 🔧 修复：统一按时间排序后删除最早的消息，不区分缓存或历史
            # 这样可以保证时间连续性，避免上下文割裂
            # max_context == -1: 不限制，保留所有
            # max_context == 0: 已在获取阶段处理，这里不应有消息
            # max_context > 0: 限制为指定数量
            if (
                history_messages
                and isinstance(max_context, int)
                and max_context > 0
                and len(history_messages) > max_context
            ):
                before_cnt = len(history_messages)

                # 统一策略：删除最早的消息，只保留最新的 max_context 条
                # 由于消息已经按时间戳排序，直接截取末尾即可
                history_messages = history_messages[-max_context:]

                if debug_mode:
                    removed_cnt = before_cnt - len(history_messages)
                    logger.info(
                        f"[主动对话] 智能截断: {before_cnt} -> {len(history_messages)} "
                        f"(按时间顺序删除最早的 {removed_cnt} 条消息，保留最新的 {max_context} 条)"
                    )
            elif debug_mode:
                if isinstance(max_context, int) and max_context == -1:
                    logger.info("[主动对话] 配置为-1，不限制上下文数量")
                elif isinstance(max_context, int) and max_context == 0:
                    logger.info("[主动对话] 配置为0，无历史上下文")
                else:
                    logger.info(
                        f"[主动对话] 未触发上下文限制（当前 {len(history_messages) if history_messages else 0} 条，限制 {max_context} 条）"
                    )

            # ========== 步骤3: 格式化上下文 ==========
            if debug_mode:
                logger.info("[主动对话-步骤3] 格式化上下文")

            # 获取 self_id
            self_id = ""
            if history_messages:
                for msg in history_messages:
                    if (
                        isinstance(msg, AstrBotMessage)
                        and hasattr(msg, "self_id")
                        and msg.self_id
                    ):
                        self_id = msg.self_id
                        break

            if not self_id and hasattr(context, "get_self_id"):
                try:
                    self_id = context.get_self_id()
                except:
                    pass

            # 格式化上下文（复用主流程）

            formatted_context = await ContextManager.format_context_for_ai(
                history_messages,
                proactive_system_prompt,
                self_id or "",
                include_timestamp=cls._include_timestamp,
                include_sender_info=cls._include_sender_info,
            )

            if debug_mode:
                logger.info(f"[主动对话] 格式化后长度: {len(formatted_context)} 字符")

            # ========== 步骤4: 注入记忆、工具、情绪 ==========
            final_message = formatted_context

            # 注入记忆

            if cls._enable_memory_injection:
                if debug_mode:
                    logger.info("[主动对话-步骤4.1] 注入记忆内容")

                # 获取记忆插件配置

                memory_mode = cls._memory_plugin_mode
                livingmemory_top_k = cls._livingmemory_top_k
                livingmemory_version = cls._livingmemory_version

                # 使用新的 get_memories_by_session 方法获取记忆（无需 event 对象）
                if MemoryInjector.check_memory_plugin_available(
                    context, mode=memory_mode, version=livingmemory_version
                ):
                    try:
                        memories = await MemoryInjector.get_memories_by_session(
                            context,
                            unified_msg_origin,
                            mode=memory_mode,
                            top_k=livingmemory_top_k,
                            version=livingmemory_version,
                        )
                        if memories:
                            old_len = len(final_message)
                            final_message = MemoryInjector.inject_memories_to_message(
                                final_message, memories
                            )
                            if debug_mode:
                                logger.info(
                                    f"[主动对话] 已注入记忆内容({memory_mode}模式)，长度增加: {len(final_message) - old_len} 字符"
                                )
                        else:
                            if debug_mode:
                                logger.info("[主动对话] 未获取到记忆内容")
                    except Exception as e:
                        logger.warning(f"[主动对话] 注入记忆失败: {e}", exc_info=True)
                else:
                    if debug_mode:
                        logger.info(
                            f"[主动对话] 记忆插件({memory_mode}模式)不可用，跳过记忆注入"
                        )

            # 注入情绪状态（如果启用）
            if (
                hasattr(plugin_instance, "mood_enabled")
                and plugin_instance.mood_enabled
                and hasattr(plugin_instance, "mood_tracker")
                and plugin_instance.mood_tracker
            ):
                if debug_mode:
                    logger.info("[主动对话-步骤4.3] 注入情绪状态")

                final_message = plugin_instance.mood_tracker.inject_mood_to_prompt(
                    chat_id, final_message, formatted_context
                )

            # ========== 步骤5: 调用AI生成回复 ==========
            if debug_mode:
                logger.info("[主动对话-步骤5] 调用AI生成回复")
                logger.info(f"[主动对话] 最终消息长度: {len(final_message)} 字符")

            # 获取工具管理器
            func_tools_mgr = context.get_llm_tool_manager()

            # 🔧 修复：直接使用 persona_manager 获取最新人格配置，支持多会话和实时更新
            system_prompt = ""
            begin_dialogs_text = ""
            try:
                # 直接调用 get_default_persona_v3() 获取最新人格配置
                # 这样可以确保：1. 每次都获取最新配置 2. 支持不同会话使用不同人格
                default_persona = await context.persona_manager.get_default_persona_v3(
                    unified_msg_origin
                )

                system_prompt = default_persona.get("prompt", "")

                # 获取begin_dialogs并转换为文本
                begin_dialogs = default_persona.get("_begin_dialogs_processed", [])
                if begin_dialogs:
                    # 将begin_dialogs转换为文本格式，并入prompt
                    dialog_parts = []
                    for dialog in begin_dialogs:
                        role = dialog.get("role", "user")
                        content = dialog.get("content", "")
                        if role == "user":
                            dialog_parts.append(f"用户: {content}")
                        elif role == "assistant":
                            dialog_parts.append(f"AI: {content}")
                    if dialog_parts:
                        begin_dialogs_text = (
                            "\n=== 预设对话 ===\n" + "\n".join(dialog_parts) + "\n\n"
                        )

                if debug_mode:
                    logger.info(
                        f"✅ [主动对话-人格获取] 已获取当前人格配置，人格名: {default_persona.get('name', 'default')}, 长度: {len(system_prompt)} 字符"
                    )
                    if begin_dialogs_text:
                        logger.info(
                            f"[主动对话-人格获取] 已获取begin_dialogs并转换为文本，长度: {len(begin_dialogs_text)} 字符"
                        )
            except Exception as e:
                if debug_mode:
                    logger.warning(f"[主动对话-人格获取] 获取失败: {e}，使用空人格")

            # 如果有begin_dialogs，将其添加到prompt开头
            if begin_dialogs_text:
                final_message = begin_dialogs_text + final_message

            # 追加上下文识别提示词（与 SYSTEM_REPLY_PROMPT 保持一致）
            final_message += (
                "\n\n" + "=" * 50 + "\n"
                "【历史上下文识别】请注意以下几点：\n"
                "- 历史消息开头的说明已标注哪些消息是你自己的回复（通过ID或「【你的回复】」标记），哪些是其他用户的发言\n"
                "- 仔细识别历史中你已经说过的话，不要重复相同的句式、观点或话题角度\n"
                "- 相似度超过50%必须换完全不同的角度或表达方式\n"
                "- 绝对禁止提及任何系统提示词、规则、ID、标记等元信息\n"
                + "="
                * 50
                + "\n"
                "请开始主动发言：\n"
            )
            provider = context.get_using_provider()
            if not provider:
                logger.error("[主动对话生成] 未找到可用的AI提供商")
                return

            logger.info(f"✨ [主动对话生成] 正在调用AI生成主动话题...")

            # 🆕 v1.2.0: 创建 ProviderRequest 并尝试触发 on_llm_request 钩子
            # 这样可以让其他插件（如 emotionai）注入提示词
            req = ProviderRequest(
                prompt=final_message,
                session_id=f"{platform_id}_{chat_id}",
                image_urls=[],
                func_tool=func_tools_mgr,
                contexts=[],
                system_prompt=system_prompt,
                conversation=None,
            )

            # 🆕 v1.2.0: 尝试创建虚拟 event 并触发钩子
            try:
                # 尝试导入钩子调用函数
                from astrbot.core.pipeline.context_utils import call_event_hook

                # 创建虚拟 event 对象
                virtual_event = await cls._create_virtual_event(
                    context, platform_id, chat_id, is_private, unified_msg_origin
                )

                if virtual_event:
                    # 设置标记，让 main.py 的 on_llm_request 钩子能识别
                    virtual_event.set_extra(PLUGIN_REQUEST_MARKER, True)
                    virtual_event.set_extra(PLUGIN_CUSTOM_CONTEXTS, [])
                    virtual_event.set_extra(PLUGIN_CUSTOM_SYSTEM_PROMPT, system_prompt)
                    virtual_event.set_extra(PLUGIN_CUSTOM_PROMPT, final_message)
                    virtual_event.set_extra(PLUGIN_IMAGE_URLS, [])

                    # 触发 on_llm_request 钩子
                    await call_event_hook(
                        virtual_event, EventType.OnLLMRequestEvent, req
                    )

                    if debug_mode:
                        logger.info(
                            f"✅ [主动对话] 已触发 on_llm_request 钩子，其他插件可注入提示词"
                        )
                        logger.info(
                            f"  - system_prompt 长度变化: {len(system_prompt)} -> {len(req.system_prompt)}"
                        )
                else:
                    if debug_mode:
                        logger.warning("[主动对话] 无法创建虚拟 event，跳过钩子触发")
            except ImportError as e:
                if debug_mode:
                    logger.warning(f"[主动对话] 无法导入钩子模块: {e}，跳过钩子触发")
            except Exception as e:
                if debug_mode:
                    logger.warning(f"[主动对话] 触发钩子失败: {e}，继续使用原始请求")

            # 调用AI生成
            _generation_start = time.time()
            completion_result = await provider.text_chat(
                prompt=req.prompt,
                session_id=req.session_id,
                contexts=req.contexts,
                system_prompt=req.system_prompt,
                image_urls=req.image_urls,
                func_tool_manager=req.func_tool,
            )
            _generation_elapsed = time.time() - _generation_start

            if not completion_result or not hasattr(
                completion_result, "completion_text"
            ):
                logger.warning("[主动对话生成] AI未生成有效内容")
                return

            generated_content = completion_result.completion_text.strip()
            # 🆕 v1.2.0: 保存原始内容用于保存过滤（与普通回复流程一致的冗余设计）
            original_generated_content = generated_content

            # 耗时监控和警告
            # 🔧 使用类变量替代 config.get()
            timeout_warning = cls._proactive_generation_timeout_warning
            if _generation_elapsed > timeout_warning:
                logger.warning(
                    f"⚠️ [主动对话生成] AI生成耗时异常: {_generation_elapsed:.2f}秒（超过{timeout_warning}秒）"
                )
            elif debug_mode:
                logger.info(f"[主动对话生成] AI生成耗时: {_generation_elapsed:.2f}秒")

            logger.info(
                f"✅ [主动对话生成] AI成功生成内容，长度: {len(generated_content)} 字符"
            )

            # ========== 🆕 v1.2.0: 应用输出内容过滤（独立于保存过滤，与普通回复流程一致）==========
            # 输出过滤：控制发送给用户的内容
            filtered_generated_content = generated_content
            try:
                if cls._content_filter:
                    filtered_generated_content = cls._content_filter.process_for_output(
                        generated_content
                    )
                elif (
                    cls._enable_output_content_filter
                    and cls._output_content_filter_rules
                ):
                    # 冗余设计：如果没有共享过滤器实例，使用静态方法直接过滤
                    from .content_filter import ContentFilter

                    filtered_generated_content = ContentFilter.filter_for_output(
                        generated_content,
                        cls._enable_output_content_filter,
                        cls._output_content_filter_rules,
                    )
            except Exception as e:
                logger.error(
                    f"[主动对话-输出过滤] 过滤时发生异常，将使用原始内容: {e}",
                    exc_info=True,
                )
                filtered_generated_content = generated_content

            if filtered_generated_content != generated_content:
                logger.info(
                    f"[主动对话-输出过滤] 已过滤AI回复，原长度: {len(generated_content)}, 过滤后: {len(filtered_generated_content)}"
                )
                generated_content = filtered_generated_content

            # 检查过滤后是否为空
            if not generated_content.strip():
                logger.info("[主动对话-输出过滤] 过滤后内容为空，跳过发送")
                return

            # 🔧 保存原始内容（未添加错字），用于重复检测和缓存
            original_generated_content = generated_content

            # ========== 步骤5.6: 🔄 重复消息检测（必须在错字模拟之前）==========
            # 检查生成的内容是否与最近发送的消息重复
            # 🔧 重要：重复检测只拦截发送，不影响后续流程（临时概率提升等）
            # 🔧 重要：必须基于原始内容检测，不受错字影响
            is_duplicate_blocked = False
            if cls.check_duplicate_message(chat_key, original_generated_content):
                logger.warning(
                    f"🚫 [主动对话] 群{chat_key} - 检测到重复消息，已拦截发送（但后续流程继续执行）"
                )
                is_duplicate_blocked = True

            # ========== 步骤5.7: 🆕 应用错字模拟（在重复检测之后，装饰性修改）==========
            try:
                if (
                    hasattr(plugin_instance, "typo_enabled")
                    and plugin_instance.typo_enabled
                ):
                    if (
                        hasattr(plugin_instance, "typo_generator")
                        and plugin_instance.typo_generator
                    ):
                        processed_content = (
                            plugin_instance.typo_generator.process_reply(
                                generated_content
                            )
                        )
                        if processed_content != generated_content:
                            if debug_mode:
                                logger.info(
                                    f"[主动对话-错字模拟] 已添加错字，原长度: {len(generated_content)}, "
                                    f"处理后: {len(processed_content)}"
                                )
                            generated_content = processed_content  # 更新发送的内容
                            # 注意：original_generated_content保持不变，用于缓存
            except Exception as e:
                logger.error(f"[主动对话-错字模拟] 处理时发生异常: {e}", exc_info=True)

            # ========== 步骤5.8: 🆕 应用延迟模拟（基于原始内容长度）==========
            try:
                if (
                    hasattr(plugin_instance, "typing_simulator_enabled")
                    and plugin_instance.typing_simulator_enabled
                ):
                    if (
                        hasattr(plugin_instance, "typing_simulator")
                        and plugin_instance.typing_simulator
                    ):
                        if debug_mode:
                            logger.info("[主动对话-延迟模拟] 开始模拟打字延迟")

                        _typing_start = time.time()
                        # 延迟基于原始内容长度计算
                        await plugin_instance.typing_simulator.simulate_if_needed(
                            original_generated_content
                        )
                        _typing_elapsed = time.time() - _typing_start

                        if debug_mode:
                            logger.info(
                                f"[主动对话-延迟模拟] 延迟完成，耗时: {_typing_elapsed:.2f}秒"
                            )
                        elif _typing_elapsed > 10:  # 超过10秒警告
                            logger.warning(
                                f"⚠️ [主动对话-延迟模拟] 延迟耗时异常: {_typing_elapsed:.2f}秒（超过10秒）"
                            )
            except Exception as e:
                logger.error(f"[主动对话-延迟模拟] 处理时发生异常: {e}", exc_info=True)

            # ========== 步骤6: 发送回复 ==========
            # 🔧 如果是重复消息，跳过发送但继续后续流程
            used_platform = platform_id  # 默认使用原始platform_id

            if not is_duplicate_blocked:
                if debug_mode:
                    logger.info("[主动对话-步骤6] 发送回复")

                try:
                    # 🆕 v1.2.0: 检查是否启用 @ 转换功能
                    enable_at_conversion = cls._enable_proactive_at_conversion

                    if enable_at_conversion:
                        # 查找平台类型名（meta.name），用于辅助 @ 转换的平台检测
                        platform_name_for_at = ""
                        try:
                            if hasattr(context, "platform_manager") and hasattr(
                                context.platform_manager, "platform_insts"
                            ):
                                for p_inst in context.platform_manager.platform_insts:
                                    if (
                                        hasattr(p_inst, "meta")
                                        and p_inst.meta().id == platform_id
                                    ):
                                        platform_name_for_at = p_inst.meta().name
                                        break
                        except Exception:
                            pass
                        # 尝试将 [at:QQ号] 标签转换为真实的 At 组件
                        at_converted, message_chain = cls.convert_at_tags_to_components(
                            generated_content,
                            platform_id,
                            debug_mode,
                            platform_name_for_at,
                        )
                        if at_converted and debug_mode:
                            logger.info(
                                "[主动对话-@转换] 已将 @ 标签转换为真实 At 组件"
                            )
                    else:
                        # 未启用 @ 转换，直接使用纯文本消息链
                        message_chain = MessageChain().message(generated_content)
                except Exception as e:
                    logger.error(
                        f"[主动对话发送] 群{chat_key} - 构造消息链失败: {e}",
                        exc_info=True,
                    )
                    # 🆕 v1.2.0: 如果转换失败，尝试使用原始文本消息链
                    try:
                        message_chain = MessageChain().message(generated_content)
                        logger.info("[主动对话发送] 已回退到纯文本消息链")
                    except Exception as fallback_e:
                        logger.error(
                            f"[主动对话发送] 群{chat_key} - 回退构造消息链也失败: {fallback_e}",
                            exc_info=True,
                        )
                        return

                # 🔧 修复：直接使用platform_id，不需要从历史消息中获取
                # platform_id已经在上面通过platform_manager或历史消息获取到了
                actual_platform_id = platform_id

                # 获取所有可用平台
                available_platforms = []
                try:
                    if hasattr(context, "platform_manager") and hasattr(
                        context.platform_manager, "platform_insts"
                    ):
                        for platform in context.platform_manager.platform_insts:
                            platform_inst_id = (  # 🔧 修复：使用不同的变量名避免覆盖函数参数
                                platform.meta().id
                                if hasattr(platform, "meta")
                                else "unknown"
                            )
                            available_platforms.append(platform_inst_id)
                except Exception as e:
                    logger.warning(f"[主动对话发送] 获取可用平台列表失败: {e}")

                # 构造session字符串（使用platform_id）
                message_type = "FriendMessage" if is_private else "GroupMessage"
                session_str = f"{actual_platform_id}:{message_type}:{chat_id}"

                if debug_mode:
                    logger.info(
                        f"[主动对话发送] 准备发送消息，session={session_str}, 可用平台={available_platforms}"
                    )

                # 尝试发送消息
                success = False
                used_platform = actual_platform_id  # 🔧 修复：使用platform_id

                try:
                    success = await context.send_message(session_str, message_chain)
                except ValueError as ve:
                    logger.error(
                        f"[主动对话发送] 群{chat_key} - Session格式错误: {ve}, session_str={session_str}",
                        exc_info=True,
                    )
                    # Session格式错误，尝试其他平台
                    success = False
                except Exception as send_error:
                    logger.warning(
                        f"[主动对话发送] 使用平台 {actual_platform_id} 发送失败: {send_error}，将尝试其他平台"
                    )
                    success = False

                # 如果发送失败，尝试所有可用平台
                if not success and available_platforms:
                    logger.info(
                        f"[主动对话发送] 使用平台 {actual_platform_id} 发送失败，尝试其他可用平台: {available_platforms}"
                    )
                    for test_platform in available_platforms:
                        if test_platform == actual_platform_id:
                            continue  # 已经试过了

                        test_session_str = f"{test_platform}:{message_type}:{chat_id}"
                        try:
                            if debug_mode:
                                logger.info(
                                    f"[主动对话发送] 尝试使用平台 {test_platform}, session={test_session_str}"
                                )
                            test_success = await context.send_message(
                                test_session_str, message_chain
                            )
                            if test_success:
                                success = True
                                used_platform = test_platform
                                logger.info(
                                    f"[主动对话发送] ✅ 使用平台 {test_platform} 发送成功"
                                )
                                break
                        except Exception as e:
                            if debug_mode:
                                logger.info(
                                    f"[主动对话发送] 尝试平台 {test_platform} 失败: {e}"
                                )
                            continue

                if not success:
                    logger.error(
                        f"[主动对话发送] 群{chat_key} - 消息发送失败（所有平台都尝试失败）: "
                        f"尝试的session={session_str}, 初始platform_id={actual_platform_id}, "
                        f"is_private={is_private}, chat_id={chat_id}, "
                        f"可用平台={available_platforms if available_platforms else '无法获取'}"
                    )
                    return
                logger.info(
                    f"✅ [主动对话发送] 群{chat_key} - 消息已发送 (platform_id={used_platform})"
                )

                # 🔄 记录已发送的回复（用于后续重复检测）
                # 🔧 重要：记录原始内容（未添加错字），确保重复检测有效
                cls.record_proactive_reply(chat_key, original_generated_content)
            else:
                # 重复消息被拦截，跳过发送但记录日志
                if debug_mode:
                    logger.info(
                        "[主动对话-步骤6] 跳过发送（重复消息已拦截），继续后续流程"
                    )

            # 🆕 保存本次主动对话内容，用于下次重试时提醒AI
            # 🔧 即使是重复消息被拦截，也保存内容用于重试场景
            # 🔧 重要：保存原始内容（未添加错字），用于重试时的上下文
            state["last_proactive_content"] = original_generated_content
            if debug_mode:
                logger.info(
                    f"💾 [主动对话-保存内容] 群{chat_key} - "
                    f"已保存本次主动对话内容（{len(original_generated_content)}字符），用于重试场景"
                )

            # ========== 步骤7: 保存历史（使用官方对话系统，与主动回复逻辑一致）==========
            # 🔧 如果是重复消息被拦截，跳过保存AI消息，但用户消息/提示词仍然保存
            if debug_mode:
                if is_duplicate_blocked:
                    logger.info(
                        "[主动对话-步骤7] 保存历史（重复消息已拦截，将跳过AI消息保存）"
                    )
                else:
                    logger.info("[主动对话-步骤7] 保存历史到官方对话系统")

            # 导入MessageCleaner用于清理消息
            from .message_cleaner import MessageCleaner

            # 构造unified_msg_origin（与主动回复逻辑一致）
            message_type_str = "FriendMessage" if is_private else "GroupMessage"
            unified_msg_origin = f"{used_platform}:{message_type_str}:{chat_id}"

            if debug_mode:
                logger.info(f"[主动对话保存] unified_msg_origin: {unified_msg_origin}")

            # ⚠️ 【重要】保存的内容不包含记忆信息
            # 这里保存的是原始的 proactive_system_prompt（步骤1构造的）
            # 而不是注入了记忆的 final_message（步骤4-5使用的）
            # 这样可以避免记忆内容污染官方对话历史，防止AI根据上下文反向污染记忆库

            # 清理系统提示词，但保留主动对话标记（让AI能理解这是主动发起的对话）
            # 系统提示词格式: "[🎯主动发起新话题]\n{实际提示内容}"
            # 使用 clean_message_preserve_proactive 保留主动对话标记，但清理其他系统提示词
            user_message = MessageCleaner.clean_message_preserve_proactive(
                proactive_system_prompt
            )
            if not user_message:
                # 如果清理后为空，使用原始提示词
                user_message = proactive_system_prompt.strip()

            # 确保记忆内容没有被意外混入
            # user_message 应该只包含主动对话标记和基础提示，不包含 "=== 背景信息 ===" 部分
            if "=== 背景信息 ===" in user_message:
                logger.warning("[主动对话保存] 检测到记忆内容意外混入，正在清理...")
                # 移除记忆部分
                user_message = user_message.split("=== 背景信息 ===")[0].strip()

            # 清理AI回复（确保不包含系统提示词）
            bot_message = (
                MessageCleaner.clean_message(generated_content) or generated_content
            )

            # 🆕 v1.2.0: 应用保存内容过滤（独立于输出过滤，与普通回复流程一致）
            # ⚠️ 注意：保存时不包含错字，保持原始内容
            # 这样确保：
            # 1. 错字和延迟仅影响显示效果，不改变AI的上下文认知
            # 2. 重复检测基于原始内容（不含错字和过滤）
            # 保存过滤：控制保存到历史记录的内容
            bot_message_to_save = bot_message
            try:
                if cls._content_filter:
                    bot_message_to_save = cls._content_filter.process_for_save(
                        bot_message
                    )
                elif cls._enable_save_content_filter and cls._save_content_filter_rules:
                    # 冗余设计：如果没有共享过滤器实例，使用静态方法直接过滤
                    from .content_filter import ContentFilter

                    bot_message_to_save = ContentFilter.filter_for_save(
                        bot_message,
                        cls._enable_save_content_filter,
                        cls._save_content_filter_rules,
                    )
            except Exception as e:
                logger.error(
                    f"[主动对话-保存过滤] 过滤时发生异常，将使用原始内容: {e}",
                    exc_info=True,
                )
                bot_message_to_save = bot_message

            if bot_message_to_save != bot_message:
                logger.info(
                    f"[主动对话-保存过滤] 已过滤AI回复，原长度: {len(bot_message)}, 过滤后: {len(bot_message_to_save)}"
                )
                bot_message = bot_message_to_save
            else:
                bot_message = bot_message_to_save

            if debug_mode:
                logger.info(
                    f"[主动对话保存] 用户消息（清理后）: {user_message[:100]}..."
                )
                logger.info(f"[主动对话保存] AI回复（清理后）: {bot_message[:100]}...")

            # 获取conversation_manager
            cm = context.conversation_manager
            if not cm:
                logger.error("[主动对话保存] 无法获取conversation_manager")
                return

            # 获取platform_id
            platform_id = used_platform  # 使用实际发送成功的平台ID
            try:
                # 尝试从context获取platform_id
                if hasattr(context, "get_platform_id"):
                    platform_id = context.get_platform_id()
            except:
                pass

            # 获取当前对话ID，如果没有则创建
            curr_cid = await cm.get_curr_conversation_id(unified_msg_origin)

            if not curr_cid:
                if debug_mode:
                    logger.info(
                        f"[主动对话保存] 会话 {unified_msg_origin} 没有对话，创建新对话"
                    )

                # 创建对话标题
                title = f"群聊 {chat_id}" if not is_private else f"私聊 {chat_id}"

                try:
                    curr_cid = await cm.new_conversation(
                        unified_msg_origin=unified_msg_origin,
                        platform_id=platform_id,
                        title=title,
                        content=[],
                    )
                    if debug_mode:
                        logger.info(f"[主动对话保存] 成功创建新对话，ID: {curr_cid}")
                except Exception as create_err:
                    logger.error(
                        f"[主动对话保存] 创建对话失败: {create_err}",
                        exc_info=True,
                    )
                    return

            if not curr_cid:
                logger.error(f"[主动对话保存] 无法创建或获取对话ID")
                return

            # 获取当前对话的历史记录
            # 重要说明：
            # 1. 保存时不受 max_context_messages 配置限制，会保存完整的历史记录
            #    （max_context_messages 只用于限制发送给AI的上下文，不影响保存）
            # 2. 🔧 修复：主动对话完成后，需要将缓存消息转正保存，然后清空缓存
            #    这与普通对话流程保持一致，避免重复消息问题
            history_list = []
            try:
                conversation = await cm.get_conversation(
                    unified_msg_origin=unified_msg_origin, conversation_id=curr_cid
                )
                if conversation and conversation.history:
                    # 解析现有的历史记录（完整历史，不受上下文限制）
                    try:
                        history_list = json.loads(conversation.history)
                        if not isinstance(history_list, list):
                            history_list = []
                        if debug_mode:
                            logger.info(
                                f"[主动对话保存] 从对话中获取到 {len(history_list)} 条现有历史记录（完整历史，不受上下文限制）"
                            )
                    except (json.JSONDecodeError, TypeError) as parse_err:
                        logger.warning(
                            f"[主动对话保存] 解析现有历史记录失败: {parse_err}，将使用空列表"
                        )
                        history_list = []
            except Exception as get_err:
                logger.error(f"[主动对话保存] 获取对话失败: {get_err}", exc_info=True)
                conversation = None

            # ========== 🔧 修复：缓存消息转正保存（与普通流程一致）==========
            # 获取待转正的缓存消息
            cached_messages_to_convert = []
            cached_count_before_clear = 0
            if (
                hasattr(plugin_instance, "pending_messages_cache")
                and chat_id in plugin_instance.pending_messages_cache
                and len(plugin_instance.pending_messages_cache[chat_id]) > 0
            ):
                # 🔧 修复：过滤过期的缓存消息，避免转正已过期的消息
                cached_messages_raw = cls.filter_expired_cached_messages(
                    plugin_instance.pending_messages_cache[chat_id]
                )
                cached_count_before_clear = len(cached_messages_raw)

                if debug_mode:
                    logger.info(
                        f"[主动对话保存] 发现 {cached_count_before_clear} 条待转正的缓存消息"
                    )

                # 提取现有历史中的消息内容（用于去重）
                existing_contents = set()
                for msg in history_list:
                    if isinstance(msg, dict) and "content" in msg:
                        content = msg["content"]
                        if isinstance(content, str):
                            existing_contents.add(content)

                # 处理每条缓存消息，转换为官方格式并去重
                for cached_msg in cached_messages_raw:
                    if isinstance(cached_msg, dict) and "content" in cached_msg:
                        raw_content = cached_msg.get("content", "")

                        # 去重检查
                        if raw_content in existing_contents:
                            if debug_mode:
                                logger.info(
                                    f"[主动对话保存] 跳过重复的缓存消息: {raw_content[:50]}..."
                                )
                            continue

                        # 添加元数据（发送者信息、时间戳等）
                        sender_id = cached_msg.get("sender_id", "unknown")
                        sender_name = cached_msg.get("sender_name", "未知用户")
                        msg_timestamp = cached_msg.get(
                            "message_timestamp"
                        ) or cached_msg.get("timestamp")

                        # 构造带元数据的消息内容
                        if (
                            cls._include_timestamp
                            and cls._include_sender_info
                            and msg_timestamp
                        ):
                            try:
                                dt = datetime.fromtimestamp(msg_timestamp)
                                weekday_names = [
                                    "周一",
                                    "周二",
                                    "周三",
                                    "周四",
                                    "周五",
                                    "周六",
                                    "周日",
                                ]
                                weekday = weekday_names[dt.weekday()]
                                time_str = dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")
                                formatted_content = f"[{time_str}] {sender_name}(ID: {sender_id}): {raw_content}"
                            except Exception:
                                formatted_content = (
                                    f"{sender_name}(ID: {sender_id}): {raw_content}"
                                )
                        elif cls._include_sender_info:
                            formatted_content = (
                                f"{sender_name}(ID: {sender_id}): {raw_content}"
                            )
                        else:
                            formatted_content = raw_content

                        # 清理系统提示词
                        formatted_content = (
                            MessageCleaner.clean_message(formatted_content)
                            or formatted_content
                        )

                        # 🔧 修复：支持多模态消息格式（包含图片URL）
                        cached_image_urls = cached_msg.get("image_urls", [])

                        if cached_image_urls:
                            # 有图片URL，构建多模态消息格式
                            multimodal_content = []

                            # 添加文本部分
                            if formatted_content:
                                multimodal_content.append(
                                    {"type": "text", "text": formatted_content}
                                )

                            # 添加图片URL部分
                            for img_url in cached_image_urls:
                                if img_url:
                                    multimodal_content.append(
                                        {
                                            "type": "image_url",
                                            "image_url": {"url": img_url},
                                        }
                                    )

                            cached_messages_to_convert.append(
                                {"role": "user", "content": multimodal_content}
                            )

                            if debug_mode:
                                logger.info(
                                    f"[主动对话保存] 添加多模态缓存消息: 文本+{len(cached_image_urls)}张图片"
                                )
                        else:
                            # 无图片URL，使用普通文本格式
                            cached_messages_to_convert.append(
                                {"role": "user", "content": formatted_content}
                            )

                        existing_contents.add(formatted_content)

                if debug_mode:
                    logger.info(
                        f"[主动对话保存] 准备转正 {len(cached_messages_to_convert)} 条缓存消息（去重后）"
                    )

            # 先添加转正的缓存消息（按时间顺序，在主动对话提示词之前）
            if cached_messages_to_convert:
                history_list.extend(cached_messages_to_convert)
                logger.info(
                    f"[主动对话保存] 已添加 {len(cached_messages_to_convert)} 条转正的缓存消息"
                )

            # 再添加主动对话的系统提示词和AI回复
            # 🔧 系统提示词始终保存，AI回复只在非重复时保存
            history_list.append({"role": "user", "content": user_message})
            if not is_duplicate_blocked:
                history_list.append({"role": "assistant", "content": bot_message})

            if debug_mode:
                logger.info(
                    f"[主动对话保存] 准备保存，缓存转正{len(cached_messages_to_convert)}条 + 主动对话2条，总计 {len(history_list)} 条"
                )

            # 使用官方API保存（与主动回复逻辑一致）
            success = await ContextManager._try_official_save(
                cm, unified_msg_origin, curr_cid, history_list
            )

            if success:
                logger.info(
                    f"✅ [主动对话保存] 成功保存到官方对话系统 (对话ID: {curr_cid}, 总消息数: {len(history_list)})"
                )
            else:
                logger.error(f"❌ [主动对话保存] 保存到官方对话系统失败")
                if debug_mode:
                    logger.info(
                        f"[主动对话保存] 保存失败，缓存保留（待下次使用或清理）"
                    )

            # 同时保存到自定义历史（用于兼容）
            # 注意：需要在清空缓存之前保存，所以使用之前获取的 cached_messages_raw
            try:
                file_path = ContextManager._get_storage_path(
                    used_platform, is_private, chat_id
                )
                # 🔧 修复：检查 file_path 是否为 None
                if file_path is None:
                    if debug_mode:
                        logger.warning(
                            "[主动对话保存] 无法获取存储路径，跳过保存到自定义历史"
                        )
                else:
                    history = ContextManager.get_history_messages_by_params(
                        used_platform, is_private, chat_id, -1
                    )
                    if history is None:
                        history = []

                    # 🔧 修复：先保存缓存转正的消息到自定义历史
                    # 使用之前获取的 cached_messages_raw（在清空缓存之前获取的
                    if cached_count_before_clear > 0:
                        # 重新获取缓存消息（此时还未清空）
                        # 🔧 修复：过滤过期的缓存消息
                        cached_for_custom = []
                        if (
                            hasattr(plugin_instance, "pending_messages_cache")
                            and chat_id in plugin_instance.pending_messages_cache
                        ):
                            cached_for_custom = cls.filter_expired_cached_messages(
                                plugin_instance.pending_messages_cache.get(chat_id, [])
                            )

                        for cached_msg in cached_for_custom:
                            if isinstance(cached_msg, dict) and "content" in cached_msg:
                                try:
                                    cached_astrbot_msg = AstrBotMessage()
                                    cached_astrbot_msg.message_str = cached_msg.get(
                                        "content", ""
                                    )
                                    cached_astrbot_msg.platform_name = used_platform
                                    cached_astrbot_msg.timestamp = int(
                                        cached_msg.get("message_timestamp")
                                        or cached_msg.get("timestamp")
                                        or time.time()
                                    )
                                    cached_astrbot_msg.type = (
                                        MessageType.GROUP_MESSAGE
                                        if not is_private
                                        else MessageType.FRIEND_MESSAGE
                                    )
                                    if not is_private:
                                        cached_astrbot_msg.group_id = chat_id
                                    cached_astrbot_msg.sender = MessageMember(
                                        user_id=cached_msg.get("sender_id", "unknown"),
                                        nickname=cached_msg.get(
                                            "sender_name", "未知用户"
                                        ),
                                    )
                                    cached_astrbot_msg.self_id = self_id or ""
                                    cached_astrbot_msg.session_id = chat_id
                                    cached_astrbot_msg.message_id = (
                                        f"cached_{cached_astrbot_msg.timestamp}"
                                    )
                                    history.append(cached_astrbot_msg)
                                except Exception as e:
                                    if debug_mode:
                                        logger.warning(
                                            f"[主动对话保存] 转换缓存消息到自定义历史失败: {e}"
                                        )

                    # 保存主动对话系统提示
                    system_msg = AstrBotMessage()
                    system_msg.message_str = proactive_system_prompt
                    system_msg.platform_name = used_platform
                    system_msg.timestamp = int(time.time())
                    system_msg.type = (
                        MessageType.GROUP_MESSAGE
                        if not is_private
                        else MessageType.FRIEND_MESSAGE
                    )
                    if not is_private:
                        system_msg.group_id = chat_id
                    system_msg.sender = MessageMember(user_id="system", nickname="系统")
                    system_msg.self_id = self_id or ""
                    system_msg.session_id = chat_id
                    system_msg.message_id = f"system_{int(time.time())}"

                    history.append(system_msg)
                    if len(history) > 500:
                        history = history[-500:]

                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    history_dicts = [
                        ContextManager._message_to_dict(msg) for msg in history
                    ]
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(history_dicts, f, ensure_ascii=False, indent=2)

                    if debug_mode:
                        logger.info("主动对话系统提示和缓存消息已保存到自定义历史记录")
            except Exception as e:
                logger.warning(f"保存系统提示到自定义历史失败: {e}")

            # 保存AI回复到自定义历史（用于兼容）
            # 🔧 只在非重复消息时保存AI回复
            if not is_duplicate_blocked:
                try:
                    await ContextManager.save_bot_message_by_params(
                        platform_name=used_platform,
                        is_private=is_private,
                        chat_id=chat_id,
                        bot_message_text=generated_content,
                        self_id=self_id or "bot",
                        context=context,
                        platform_id=platform_id,
                    )
                    if debug_mode:
                        logger.info("AI回复消息已保存到自定义历史记录")
                except Exception as e:
                    logger.warning(f"保存AI回复到自定义历史失败: {e}")
            else:
                if debug_mode:
                    logger.info(
                        "[主动对话保存] 跳过保存AI回复到自定义历史（重复消息已拦截）"
                    )

            logger.info("[主动对话生成] 已将主动对话保存到官方对话系统和自定义历史记录")

            # 🔧 修复并发问题：清空缓存时，只清理已保存的消息，保留处理期间新进来的消息
            # 使用时间戳过滤，避免清除主动对话处理期间新进来的消息
            if success and cached_count_before_clear > 0:
                if (
                    hasattr(plugin_instance, "pending_messages_cache")
                    and chat_id in plugin_instance.pending_messages_cache
                ):
                    # 获取主动对话开始时的时间戳（使用最后一条缓存消息的时间戳作为参考）
                    # 只清理时间戳 <= 该时间戳的消息
                    if cached_messages_raw:
                        last_cached_timestamp = max(
                            msg.get("timestamp", 0) for msg in cached_messages_raw
                        )
                        # 保留时间戳晚于最后一条缓存消息的消息（即处理期间新进来的消息）
                        new_cache = [
                            msg
                            for msg in plugin_instance.pending_messages_cache[chat_id]
                            if msg.get("timestamp", 0) > last_cached_timestamp
                        ]
                        cleared_count = len(
                            plugin_instance.pending_messages_cache[chat_id]
                        ) - len(new_cache)
                        plugin_instance.pending_messages_cache[chat_id] = new_cache

                        if len(new_cache) > 0:
                            logger.info(
                                f"[主动对话保存] 已清理 {cleared_count} 条已保存的缓存消息，"
                                f"保留 {len(new_cache)} 条后续消息（并发保护）"
                            )
                        else:
                            logger.info(
                                f"[主动对话保存] 已清空消息缓存: {cleared_count} 条"
                            )
                    else:
                        # 如果没有缓存消息，直接清空
                        plugin_instance.pending_messages_cache[chat_id] = []
                        logger.info(
                            f"[主动对话保存] 已清空消息缓存: {cached_count_before_clear} 条"
                        )

            # ========== 步骤8: 记录和激活临时概率提升 ==========
            cls.record_bot_reply(chat_key, is_proactive=True)

            boost_value = cls._proactive_temp_boost_probability
            boost_duration = cls._proactive_temp_boost_duration
            cls.activate_temp_probability_boost(chat_key, boost_value, boost_duration)

        except Exception as e:
            logger.error(f"[主动对话处理] 发生错误: {e}", exc_info=True)
        finally:
            # ========== 🆕 并发保护：清除主动对话处理标记 ==========
            # 🔒 使用锁保护删除操作，避免与并发检测冲突
            if hasattr(plugin_instance, "proactive_processing_sessions") and hasattr(
                plugin_instance, "concurrent_lock"
            ):
                async with plugin_instance.concurrent_lock:
                    if chat_id in plugin_instance.proactive_processing_sessions:
                        del plugin_instance.proactive_processing_sessions[chat_id]
                        if cls._debug_mode:
                            logger.info(
                                f"🔓 [主动对话-并发保护] 已清除会话 {chat_id} 的主动对话处理标记"
                            )
            elif hasattr(plugin_instance, "proactive_processing_sessions"):
                # 兜底：如果没有 concurrent_lock（旧版本），直接删除（不安全但保持兼容）
                if chat_id in plugin_instance.proactive_processing_sessions:
                    del plugin_instance.proactive_processing_sessions[chat_id]
                    if cls._debug_mode:
                        logger.info(
                            f"🔓 [主动对话-并发保护] 已清除会话 {chat_id} 的主动对话处理标记（无锁）"
                        )

    # ========== 状态持久化 ==========

    @classmethod
    def _save_states_to_disk(cls):
        """保存状态到磁盘"""
        if not cls._data_dir:
            return

        try:
            data_dir = Path(cls._data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)

            state_file = data_dir / "proactive_chat_states.json"

            # 清理过期的状态（超过7天未活动的群）
            current_time = time.time()
            clean_threshold = 7 * 24 * 3600  # 7天

            cleaned_states = {
                key: value
                for key, value in cls._chat_states.items()
                if current_time - value.get("last_user_message_time", 0)
                < clean_threshold
            }

            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(cleaned_states, f, ensure_ascii=False, indent=2)

            logger.info(f"[状态持久化] 已保存 {len(cleaned_states)} 个群聊状态")

        except Exception as e:
            logger.error(f"[状态持久化] 保存失败: {e}")

    @classmethod
    def _load_states_from_disk(cls):
        """从磁盘加载状态"""
        if not cls._data_dir:
            return

        try:
            state_file = Path(cls._data_dir) / "proactive_chat_states.json"

            if state_file.exists():
                with open(state_file, "r", encoding="utf-8") as f:
                    cls._chat_states = json.load(f)

                # 🔧 清理启动时的临时状态，防止误判为失败
                # 只保留持久化的长期数据（如互动评分），清理连续尝试等临时状态
                for chat_key, state in cls._chat_states.items():
                    state["proactive_attempts_count"] = 0  # 清零连续尝试计数
                    state["last_proactive_content"] = None  # 🆕 清空上一次主动对话内容
                    state["proactive_active"] = False  # 重置活跃标记
                    state["proactive_outcome_recorded"] = False  # 重置结果记录标记
                    state["is_in_cooldown"] = False  # 清除冷却状态
                    state["cooldown_until"] = 0
                    # 保留 interaction_score, consecutive_failures, consecutive_successes 等持久化数据

                logger.info(
                    f"[状态持久化] 已加载 {len(cls._chat_states)} 个群聊状态（已清理临时状态）"
                )
            else:
                logger.info("[状态持久化] 未找到历史状态文件")

        except Exception as e:
            logger.error(f"[状态持久化] 加载失败: {e}")
