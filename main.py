"""
群聊增强插件 - Group Chat Plus
基于AI读空气的群聊增强插件，让bot更懂氛围

核心功能：
1. AI读空气判断 - 智能决定是否回复消息
2. 动态概率调整 - 回复后提高触发概率，促进连续对话
3. 图片识别支持 - 可将图片转为文字描述
4. 上下文记忆 - 自动管理聊天历史
5. 记忆植入 - 集成长期记忆系统
6. 工具提醒 - 提示AI可用的功能
7. @消息快速响应 - 跳过概率判断直接回复
8. 智能缓存 - 避免对话上下文丢失
9. 官方历史同步 - 自动保存到系统对话记录
10. @提及智能识别 - 正确理解@别人的消息（v1.0.3新增）
11. 发送者识别增强 - 根据触发方式添加系统提示，帮助AI正确识别发送者（v1.0.4新增）
12. 🆕 主动对话功能 - AI会在沉默后主动发起新话题（v1.1.0新增）
13. 🆕 回复后戳一戳 - AI回复后根据概率戳一戳发送者，模拟真人互动（v1.1.0新增）
14. 🆕 关键词智能模式 - 可选择关键词触发时保留AI判断，更灵活（v1.1.2新增）
15. 🆕 群聊等待窗口 - 概率通过后短暂等待，批量收集同一用户的多条消息再统一回复（v1.2.0新增）

缓存工作原理：
- 通过初筛的消息先放入缓存
- AI不回复时保存到自定义存储，保留上下文
- AI回复时一次性转存到官方系统并清空缓存
- 自动清理超过30分钟的旧消息，最多保留10条

使用提示：
- 只在群聊生效，私聊消息不处理
- enabled_groups留空=全部群启用，填群号=仅指定群启用
- @消息会跳过所有判断直接回复

作者: Him666233
版本: v1.2.1

v1.2.1 更新内容：
- 🆕 Web管理面板 - 全新可视化管理界面，支持JWT认证、访问日志、统计图表、IP安全管理
- 🆕 回复密度限制 - 限制短时间内回复次数，避免刷屏，支持软限制与AI提示
- 🆕 消息质量预判 - 根据消息质量（疑问句加权/水聊降权）动态调整回复概率
- 🆕 欢迎消息解析 - 支持解析群成员入群欢迎消息，可选概率跳过或完整处理
- 🆕 主动对话AI判断 - 主动发起对话前用AI判断当前时机是否合适
- 🆕 忽略@全体成员 - 支持过滤@all消息避免无效触发
- 🆕 历史截止时间戳 - 执行插件清除指令(gcp_reset/gcp_reset_here)后记录截止时间戳，读取platform_message_history时自动过滤截止点之前的旧消息（解决AstrBot /reset不清platform_message_history的问题）
- 🆕 多工具调用兼容 - 支持AI在单次推理中调用多个工具/多轮工具调用，按实际执行顺序将文本与工具调用记录交错保存到对话历史

v1.2.0 更新内容：
- 🆕 群聊等待窗口 - 普通消息通过概率筛选后，bot短暂等待（可配置）同一用户后续消息
- 🆕 消息批量处理 - 等待窗口期间收集到的消息直接缓存，窗口结束后AI一次性处理所有内容
- 🆕 智能中断机制 - 窗口期内收到@消息立即结束等待，@消息走正常快速回复流程
- 🆕 关键词"打掉"机制 - 窗口期内的关键词触发消息降级为普通缓存，不再单独触发
- 🆕 多用户并发支持 - 每个用户独立计数和计时，互不干扰，支持配置最大并发窗口数

v1.1.2 更新内容：
- 🆕 关键词智能模式 - 新增配置选项，开启后触发关键词时只跳过概率筛选，但保留AI读空气判断
- 📝 允许用户自主选择关键词触发的处理方式：完全强制回复 or AI智能判断

v1.1.0 更新内容：
- 🆕 主动对话功能 - AI会在长时间沉默后主动发起新话题
- 🆕 临时概率提升 - AI主动发言后短暂提升回复概率，模拟真人"等待回应"行为
- 🆕 时间段控制 - 可设置禁用时段（如深夜），支持平滑过渡
- 🆕 用户活跃度检测 - 避免在死群突然说话
- 🆕 连续失败保护 - 主动发言无人理会自动进入冷却
- 🆕 特殊提示词处理 - 主动对话提示词保留到历史，让AI理解上下文
- 🆕 回复后戳一戳 - AI回复后根据概率戳一戳发送者（仅QQ+aiocqhttp）

v1.0.9 更新内容：
- 新增戳一戳消息处理功能（仅支持QQ平台+aiocqhttp）
- 支持三种模式：ignore(忽略)、bot_only(仅戳机器人)、all(所有戳一戳)
- 添加戳一戳系统提示词，帮助AI正确理解戳一戳场景
- 在保存历史时自动过滤戳一戳提示词
"""

import random
import time
from datetime import datetime
import copy
import sys
import hashlib
import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional
from collections import OrderedDict
import aiohttp
from astrbot.api import logger


from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.core.star.star_tools import StarTools

# 导入消息组件类型
from astrbot.core.message.components import Plain, Poke, At, AtAll, Forward
from astrbot.core.message.message_event_result import MessageChain

# 导入 ProviderRequest 类型用于类型判断
from astrbot.core.provider.entities import ProviderRequest

# 导入 aiocqhttp 相关类型
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_platform_adapter import (
    AiocqhttpAdapter,
)

# 导入所有工具模块
from .utils import (
    ProbabilityManager,
    MessageProcessor,
    ImageHandler,
    ContextManager,
    DecisionAI,
    ReplyHandler,
    MemoryInjector,
    ToolsReminder,
    KeywordChecker,
    MessageCleaner,
    AttentionManager,
    ProactiveChatManager,  # 🆕 v1.1.0: 主动对话管理器
    TypoGenerator,  # v1.0.2: 打字错误生成器
    MoodTracker,  # v1.0.2: 情绪追踪系统
    FrequencyAdjuster,  # v1.0.2: 频率动态调整器
    TypingSimulator,  # v1.0.2: 回复延迟模拟器
    TimePeriodManager,  # v1.1.0: 时间段管理器
    HumanizeModeManager,  # 🆕 v1.2.0: 拟人增强模式管理器
    CooldownManager,  # 🆕 v1.2.0: 注意力冷却机制管理器
    PlatformLTMHelper,  # 🆕 v1.2.0: 平台 LTM 辅助（获取平台图片描述）
    MessageCacheManager,  # 🆕 v1.2.0: 消息缓存管理器
    EmojiDetector,  # 🆕 v1.2.0: 表情包检测器
    EMOJI_MARKER,  # 🆕 v1.2.0: 表情包标记常量
    ForwardMessageParser,  # 🆕 v1.2.0: 转发消息解析器
    WelcomeMessageParser,  # 🆕 新成员入群消息解析器
    ReplyDensityManager,  # 🆕 v1.2.1: 回复密度管理器
    MessageQualityScorer,  # 🆕 v1.2.1: 消息质量预判器
)
from .utils.image_description_cache import (
    ImageDescriptionCache,
)  # 🆕 v1.2.0: 图片描述缓存
from .utils._session_guard import emit_plugin_metadata as _emit_fingerprint
from .utils.content_filter import ContentFilterManager  # 🆕 v1.2.0: AI回复内容过滤器
from .private_chat import PrivateChatMain  # 🆕 私信功能主处理模块


@register(
    "chat_plus",
    "Him666233",
    "一个以AI读空气为主的群聊聊天效果增强插件",
    "v1.2.1",
    "https://github.com/Him666233/astrbot_plugin_group_chat_plus",
)
class ChatPlus(Star):
    """
    群聊增强插件主类

    采用事件监听而非消息拦截，确保与其他插件兼容
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        """
        初始化插件

        Args:
            context: AstrBot的Context对象，包含各种API
            config: 插件配置
        """
        super().__init__(context)
        self.context = context
        self.config = config

        # ========== 🔧 配置参数集中提取区块 ==========
        # 说明：为避免 AstrBot 平台多次读取配置可能导致的问题，
        # 所有配置参数在此处一次性提取到实例变量中，后续代码直接使用这些变量
        # =============================================

        # === 基础配置 ===
        self.enable_group_chat = config.get("enable_group_chat", True)  # 群聊功能总开关
        self.debug_mode = config.get("enable_debug_log", False)  # 调试日志开关
        self.enabled_groups = config.get("enabled_groups", [])  # 启用的群组列表

        # === 概率相关配置 ===
        self.initial_probability = config.get(
            "initial_probability", 0.3
        )  # 初始读空气概率
        self.after_reply_probability = config.get(
            "after_reply_probability", 0.8
        )  # 回复后概率
        self.probability_duration = config.get(
            "probability_duration", 120
        )  # 概率提升持续时间

        # === 决策AI配置 ===
        self.decision_ai_provider_id = config.get(
            "decision_ai_provider_id", ""
        )  # 读空气AI提供商ID
        self.decision_ai_extra_prompt = config.get(
            "decision_ai_extra_prompt", ""
        )  # 读空气AI额外提示词
        self.decision_ai_timeout = config.get(
            "decision_ai_timeout", 30
        )  # 读空气AI超时时间
        self.decision_ai_prompt_mode = config.get(
            "decision_ai_prompt_mode", "append"
        )  # 读空气AI提示词模式

        # === 回复AI配置 ===
        self.reply_ai_extra_prompt = config.get(
            "reply_ai_extra_prompt", ""
        )  # 回复AI额外提示词
        self.reply_ai_prompt_mode = config.get(
            "reply_ai_prompt_mode", "append"
        )  # 回复AI提示词模式

        # === 消息格式配置 ===
        self.include_timestamp = config.get("include_timestamp", True)  # 包含时间戳
        self.include_sender_info = config.get(
            "include_sender_info", True
        )  # 包含发送者信息
        # 🔧 修复：确保 max_context_messages 是整数类型
        _max_context_raw = config.get("max_context_messages", -1)
        try:
            self.max_context_messages = (
                int(_max_context_raw) if _max_context_raw is not None else -1
            )
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ max_context_messages 配置值 '{_max_context_raw}' 无法转换为整数，使用默认值 -1"
            )
            self.max_context_messages = -1

        # === 🆕 转发消息解析配置 ===
        # 转发消息解析：开启后可解析QQ群/私聊中的合并转发消息内容
        # 支持平台：aiocqhttp (OneBot v11) - 需配合 NapCat、Lagrange 等 OneBot 实现
        # 工作原理：通过 get_forward_msg API 获取转发消息的实际内容
        # 其他平台：会自动跳过，不影响正常使用
        self.enable_forward_message_parsing = config.get(
            "enable_forward_message_parsing", False
        )

        # 嵌套转发最大解析深度（0=不解析嵌套转发，硬上限10层）
        FORWARD_NESTING_HARD_LIMIT = 10
        _forward_nesting_raw = config.get("forward_max_nesting_depth", 3)
        try:
            _forward_nesting = (
                int(_forward_nesting_raw) if _forward_nesting_raw is not None else 3
            )
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ forward_max_nesting_depth 配置值 '{_forward_nesting_raw}' 无法转换为整数，使用默认值 3"
            )
            _forward_nesting = 3
        if _forward_nesting < 0:
            logger.warning(
                f"⚠️ forward_max_nesting_depth 配置值 {_forward_nesting} 小于0，已调整为 0（不解析嵌套转发）"
            )
            _forward_nesting = 0
        elif _forward_nesting > FORWARD_NESTING_HARD_LIMIT:
            logger.warning(
                f"⚠️ forward_max_nesting_depth 配置值 {_forward_nesting} 超过硬上限 {FORWARD_NESTING_HARD_LIMIT}，已调整"
            )
            _forward_nesting = FORWARD_NESTING_HARD_LIMIT
        if _forward_nesting == 0 and self.enable_forward_message_parsing:
            logger.info(
                "📦 嵌套转发解析已配置为禁用（0），转发内容中的嵌套转发将用占位符替代"
            )
        self.forward_max_nesting_depth = _forward_nesting

        # === 🆕 新成员入群消息解析配置 ===
        # 入群消息解析：开启后可将新成员入群的空消息解析为系统提示
        # 支持平台：aiocqhttp (OneBot v11) - 其他平台自动跳过
        self.enable_welcome_message_parsing = config.get(
            "enable_welcome_message_parsing", False
        )
        # 入群消息处理模式：
        # normal - 像普通消息一样处理（经过概率+读空气筛选）
        # skip_probability - 跳过概率筛选，保留读空气判断
        # skip_all - 跳过概率和读空气筛选，强制处理
        # parse_only - 仅解析为系统提示文本，不做任何特殊处理（不进入AI流程）
        self.welcome_message_mode = config.get(
            "welcome_message_mode", "skip_probability"
        )

        # === 📦 自定义存储限制配置 ===
        CUSTOM_STORAGE_HARD_LIMIT = 10000  # 系统硬上限
        _custom_storage_raw = config.get("custom_storage_max_messages", 500)
        try:
            _custom_storage_max = (
                int(_custom_storage_raw) if _custom_storage_raw is not None else 500
            )
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ custom_storage_max_messages 配置值 '{_custom_storage_raw}' 无法转换为整数，使用默认值 500"
            )
            _custom_storage_max = 500
        # 应用保护：0=禁用，-1=不限制（硬上限10000），正数=限制条数
        if _custom_storage_max == 0:
            logger.info("📦 自定义存储已配置为禁用（0），将完全依赖官方存储")
        elif _custom_storage_max == -1:
            logger.info(
                f"📦 自定义存储配置为不限制（硬上限 {CUSTOM_STORAGE_HARD_LIMIT} 条）"
            )
        elif _custom_storage_max < -1:
            logger.warning(
                f"⚠️ custom_storage_max_messages 配置值 {_custom_storage_max} 无效，已调整为 -1（不限制）"
            )
            _custom_storage_max = -1
        elif _custom_storage_max > CUSTOM_STORAGE_HARD_LIMIT:
            logger.warning(
                f"⚠️ custom_storage_max_messages 配置值 {_custom_storage_max} 超过系统硬上限 {CUSTOM_STORAGE_HARD_LIMIT}，已自动调整"
            )
            _custom_storage_max = CUSTOM_STORAGE_HARD_LIMIT
        self.custom_storage_max_messages = _custom_storage_max

        # === 📦 消息缓存配置 ===
        # 缓存最大条数（保护上限50条，最低0=清空所有缓存）
        CACHE_MAX_COUNT_LIMIT = 50  # 系统保护上限
        _cache_max_count_raw = config.get("pending_cache_max_count", 10)
        try:
            _cache_max_count = (
                int(_cache_max_count_raw) if _cache_max_count_raw is not None else 10
            )
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ pending_cache_max_count 配置值 '{_cache_max_count_raw}' 无法转换为整数，使用默认值 10"
            )
            _cache_max_count = 10
        # 应用保护上限和下限
        if _cache_max_count > CACHE_MAX_COUNT_LIMIT:
            logger.warning(
                f"⚠️ pending_cache_max_count 配置值 {_cache_max_count} 超过系统保护上限 {CACHE_MAX_COUNT_LIMIT}，已自动调整为 {CACHE_MAX_COUNT_LIMIT}"
            )
            _cache_max_count = CACHE_MAX_COUNT_LIMIT
        elif _cache_max_count < 0:
            logger.warning(
                f"⚠️ pending_cache_max_count 配置值 {_cache_max_count} 小于0，已自动调整为 0（禁用缓存）"
            )
            _cache_max_count = 0
        self.pending_cache_max_count = _cache_max_count

        # 缓存过期时间（保护上限7200秒=2小时，最低0=不启用时间清理）
        CACHE_TTL_LIMIT = 7200  # 系统保护上限（秒）
        _cache_ttl_raw = config.get("pending_cache_ttl_seconds", 1800)
        try:
            _cache_ttl = int(_cache_ttl_raw) if _cache_ttl_raw is not None else 1800
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ pending_cache_ttl_seconds 配置值 '{_cache_ttl_raw}' 无法转换为整数，使用默认值 1800"
            )
            _cache_ttl = 1800
        # 应用保护上限和下限
        if _cache_ttl > CACHE_TTL_LIMIT:
            logger.warning(
                f"⚠️ pending_cache_ttl_seconds 配置值 {_cache_ttl} 超过系统保护上限 {CACHE_TTL_LIMIT}秒，已自动调整为 {CACHE_TTL_LIMIT}秒"
            )
            _cache_ttl = CACHE_TTL_LIMIT
        elif _cache_ttl < 0:
            logger.warning(
                f"⚠️ pending_cache_ttl_seconds 配置值 {_cache_ttl} 小于0，已自动调整为 0（不启用时间清理）"
            )
            _cache_ttl = 0
        self.pending_cache_ttl_seconds = _cache_ttl

        # === ⏳ 群聊等待窗口配置 ===
        _GWW_TIMEOUT_MIN_MS = 200
        _GWW_TIMEOUT_MAX_MS = 30000
        _GWW_MAX_EXTRA_HARD_LIMIT = 20
        _GWW_MAX_USERS_HARD_LIMIT = 20

        self.enable_group_wait_window = config.get("enable_group_wait_window", False)

        _gww_timeout_raw = config.get("group_wait_window_timeout_ms", 3000)
        try:
            _gww_timeout = (
                int(_gww_timeout_raw) if _gww_timeout_raw is not None else 3000
            )
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ group_wait_window_timeout_ms 配置值 '{_gww_timeout_raw}' 无法转换为整数，使用默认值 3000"
            )
            _gww_timeout = 3000
        _gww_timeout = max(_GWW_TIMEOUT_MIN_MS, min(_GWW_TIMEOUT_MAX_MS, _gww_timeout))
        self.group_wait_window_timeout_ms = _gww_timeout

        _gww_max_extra_raw = config.get("group_wait_window_max_extra_messages", 3)
        try:
            _gww_max_extra = (
                int(_gww_max_extra_raw) if _gww_max_extra_raw is not None else 3
            )
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ group_wait_window_max_extra_messages 配置值 '{_gww_max_extra_raw}' 无法转换为整数，使用默认值 3"
            )
            _gww_max_extra = 3
        _gww_max_extra = max(0, min(_gww_max_extra, _GWW_MAX_EXTRA_HARD_LIMIT))
        # 必须严格低于 pending_cache_max_count（已在上面提取完毕）
        if (
            self.pending_cache_max_count > 0
            and _gww_max_extra >= self.pending_cache_max_count
        ):
            _gww_corrected = max(0, self.pending_cache_max_count - 1)
            logger.warning(
                f"⚠️ group_wait_window_max_extra_messages({_gww_max_extra}) >= "
                f"pending_cache_max_count({self.pending_cache_max_count})，"
                f"已自动修正为 {_gww_corrected}（必须低于缓存上限1条）"
            )
            _gww_max_extra = _gww_corrected
        elif self.pending_cache_max_count == 0:
            if _gww_max_extra > 0:
                logger.warning(
                    f"⚠️ pending_cache_max_count=0（缓存已禁用），群聊等待窗口无法收集额外消息，"
                    f"group_wait_window_max_extra_messages 已自动修正为 0"
                )
            _gww_max_extra = 0
        self._group_wait_window_max_extra = _gww_max_extra

        _gww_max_users_raw = config.get("group_wait_window_max_users", 5)
        try:
            _gww_max_users = (
                int(_gww_max_users_raw) if _gww_max_users_raw is not None else 5
            )
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ group_wait_window_max_users 配置值 '{_gww_max_users_raw}' 无法转换为整数，使用默认值 5"
            )
            _gww_max_users = 5
        self.group_wait_window_max_users = max(
            1, min(_GWW_MAX_USERS_HARD_LIMIT, _gww_max_users)
        )

        _gww_attention_decay_raw = config.get(
            "group_wait_window_attention_decay_per_msg", 0.05
        )
        try:
            _gww_attention_decay = (
                float(_gww_attention_decay_raw)
                if _gww_attention_decay_raw is not None
                else 0.05
            )
        except (ValueError, TypeError):
            logger.warning(
                f"⚠️ group_wait_window_attention_decay_per_msg 配置值 '{_gww_attention_decay_raw}' "
                f"无法转换为浮点数，使用默认值 0.05"
            )
            _gww_attention_decay = 0.05
        self.group_wait_window_attention_decay_per_msg = max(
            0.0, min(0.5, _gww_attention_decay)
        )  # 等待窗口每条额外消息的注意力修正衰减值

        # ⏳ 窗口期内@消息合并配置
        self.group_wait_window_merge_at_messages = config.get(
            "group_wait_window_merge_at_messages", False
        )
        _gww_merge_at_list_mode_raw = config.get(
            "group_wait_window_merge_at_list_mode", "whitelist"
        )
        if _gww_merge_at_list_mode_raw not in ("whitelist", "blacklist"):
            logger.warning(
                f"⚠️ group_wait_window_merge_at_list_mode 配置值 "
                f"'{_gww_merge_at_list_mode_raw}' 无效，使用默认值 'whitelist'"
            )
            _gww_merge_at_list_mode_raw = "whitelist"
        self.group_wait_window_merge_at_list_mode = _gww_merge_at_list_mode_raw
        _gww_merge_at_user_list_raw = config.get(
            "group_wait_window_merge_at_user_list", []
        )
        if not isinstance(_gww_merge_at_user_list_raw, list):
            _gww_merge_at_user_list_raw = []
        self.group_wait_window_merge_at_user_list = set(
            str(uid) for uid in _gww_merge_at_user_list_raw if uid
        )

        # === 图片处理配置 ===
        self.enable_image_processing = config.get(
            "enable_image_processing", False
        )  # 启用图片处理
        self.image_to_text_scope = config.get(
            "image_to_text_scope", "mention_only"
        )  # 图片转文字范围
        self.image_to_text_provider_id = config.get(
            "image_to_text_provider_id", ""
        )  # 图片转文字AI提供商
        self.image_to_text_prompt = config.get(
            "image_to_text_prompt", "请详细描述这张图片的内容"
        )  # 图片转文字提示词
        self.image_to_text_timeout = config.get(
            "image_to_text_timeout", 60
        )  # 图片转文字超时时间
        self.max_images_per_message = max(
            1, min(config.get("max_images_per_message", 10), 50)
        )  # 单条消息最大处理图片数（硬限制1-50）

        # === 💾 图片描述缓存配置 ===
        self.enable_image_description_cache = config.get(
            "enable_image_description_cache", False
        )  # 图片描述缓存开关
        self.image_description_cache_max_entries = config.get(
            "image_description_cache_max_entries", 500
        )  # 图片描述缓存最大条目数
        self.gcp_clear_image_cache_allowed_user_ids = config.get(
            "gcp_clear_image_cache_allowed_user_ids", []
        )  # 清除图片缓存指令白名单

        # === 🖼️ 平台图片描述提取配置 ===
        self.platform_image_caption_max_wait = config.get(
            "platform_image_caption_max_wait", 2.0
        )  # 平台图片描述最大等待时间(秒)
        self.platform_image_caption_retry_interval = config.get(
            "platform_image_caption_retry_interval", 50
        )  # 平台图片描述重试间隔(毫秒)
        self.platform_image_caption_fast_check_count = config.get(
            "platform_image_caption_fast_check_count", 5
        )  # 平台图片描述快速检查次数
        self.probability_filter_cache_delay = config.get(
            "probability_filter_cache_delay", 50
        )  # 概率过滤缓存延迟(毫秒)

        # === 🎭 表情包过滤配置 ===
        self.enable_emoji_filter = config.get(
            "enable_emoji_filter", False
        )  # 表情包过滤总开关
        self.emoji_probability_decay = config.get(
            "emoji_probability_decay", 0.7
        )  # 表情包概率衰减因子
        self.emoji_decay_min_probability = config.get(
            "emoji_decay_min_probability", 0.1
        )  # 表情包衰减最低门槛

        # === 记忆植入配置 ===
        self.enable_memory_injection = config.get(
            "enable_memory_injection", False
        )  # 启用记忆植入
        self.memory_plugin_mode = config.get(
            "memory_plugin_mode", "legacy"
        )  # 记忆插件模式
        self.memory_insertion_timing = config.get(
            "memory_insertion_timing", "post_decision"
        )  # 记忆插入时机
        self.livingmemory_top_k = config.get(
            "livingmemory_top_k", 5
        )  # LivingMemory召回数量
        self.livingmemory_version = config.get(
            "livingmemory_version", "v2"
        )  # LivingMemory插件版本（v1旧版1.x/v2新版2.x+）

        # === 工具提醒配置 ===
        self.enable_tools_reminder = config.get(
            "enable_tools_reminder", False
        )  # 启用工具提醒
        self.tools_reminder_persona_filter = config.get(
            "tools_reminder_persona_filter", False
        )  # 工具提醒按人格过滤

        # === 关键词配置 ===
        self.trigger_keywords = config.get("trigger_keywords", [])  # 触发关键词列表
        self.blacklist_keywords = config.get(
            "blacklist_keywords", []
        )  # 黑名单关键词列表
        self.keyword_smart_mode = config.get(
            "keyword_smart_mode", False
        )  # 关键词智能模式

        # === 用户黑名单配置 ===
        self.enable_user_blacklist = config.get(
            "enable_user_blacklist", False
        )  # 启用用户黑名单
        self.blacklist_user_ids = config.get(
            "blacklist_user_ids", []
        )  # 黑名单用户ID列表

        # === 指令过滤配置 ===
        self.enable_command_filter = config.get(
            "enable_command_filter", True
        )  # 启用指令过滤
        self.command_prefixes = config.get(
            "command_prefixes", ["/", "!", "#"]
        )  # 指令前缀列表
        self.enable_full_command_detection = config.get(
            "enable_full_command_detection", False
        )  # 启用完整指令检测
        self.full_command_list = config.get(
            "full_command_list", ["new", "help", "reset"]
        )  # 完整指令列表
        self.enable_command_prefix_match = config.get(
            "enable_command_prefix_match", False
        )  # 启用指令前缀匹配
        self.command_prefix_match_list = config.get(
            "command_prefix_match_list", []
        )  # 指令前缀匹配列表

        # === 重置指令白名单配置 ===
        self.plugin_gcp_reset_allowed_user_ids = config.get(
            "plugin_gcp_reset_allowed_user_ids", []
        )
        self.plugin_gcp_reset_here_allowed_user_ids = config.get(
            "plugin_gcp_reset_here_allowed_user_ids", []
        )

        # === @消息处理配置 ===
        self.enable_ignore_at_others = config.get(
            "enable_ignore_at_others", False
        )  # 启用忽略@他人
        self.ignore_at_others_mode = config.get(
            "ignore_at_others_mode", "strict"
        )  # @他人忽略模式
        self.enable_ignore_at_all = config.get(
            "enable_ignore_at_all", False
        )  # 启用忽略@全体成员

        # === 戳一戳配置 ===
        self.poke_message_mode = config.get(
            "poke_message_mode", "bot_only"
        )  # 戳一戳消息处理模式
        self.poke_bot_skip_probability = config.get(
            "poke_bot_skip_probability", True
        )  # 戳机器人跳过概率
        self.poke_bot_probability_boost_reference = config.get(
            "poke_bot_probability_boost_reference", 0.3
        )  # 戳一戳概率增值参考
        self.poke_reverse_on_poke_probability_raw = config.get(
            "poke_reverse_on_poke_probability", 0.0
        )  # 反戳概率原始值
        self.enable_poke_after_reply = config.get(
            "enable_poke_after_reply", False
        )  # 启用回复后戳一戳
        self.poke_after_reply_probability = config.get(
            "poke_after_reply_probability", 0.15
        )  # 回复后戳一戳概率
        self.poke_after_reply_delay = config.get(
            "poke_after_reply_delay", 0.5
        )  # 回复后戳一戳延迟
        self.enable_poke_trace_prompt = config.get(
            "enable_poke_trace_prompt", False
        )  # 启用戳过对方追踪
        self.poke_trace_max_tracked_users = config.get(
            "poke_trace_max_tracked_users", 5
        )  # 戳过对方最大追踪人数
        self.poke_trace_ttl_seconds = config.get(
            "poke_trace_ttl_seconds", 300
        )  # 戳过对方提示有效期
        self.poke_enabled_groups = config.get(
            "poke_enabled_groups", []
        )  # 戳一戳功能群聊白名单

        # === 注意力机制配置 ===
        self.enable_attention_mechanism = config.get(
            "enable_attention_mechanism", False
        )  # 启用注意力机制
        self.attention_increased_probability = config.get(
            "attention_increased_probability", 0.9
        )  # 注意力提升参考值
        self.attention_decreased_probability = config.get(
            "attention_decreased_probability", 0.1
        )  # 注意力降低参考值
        self.attention_duration = config.get(
            "attention_duration", 120
        )  # 注意力数据清理周期
        self.attention_max_tracked_users = config.get(
            "attention_max_tracked_users", 10
        )  # 最大追踪用户数
        self.attention_decay_halflife = config.get(
            "attention_decay_halflife", 300
        )  # 注意力衰减半衰期
        self.emotion_decay_halflife = config.get(
            "emotion_decay_halflife", 600
        )  # 情绪衰减半衰期
        self.attention_decrease_on_no_reply_step = config.get(
            "attention_decrease_on_no_reply_step", 0.15
        )  # 不回复时注意力衰减
        self.attention_decrease_threshold = config.get(
            "attention_decrease_threshold", 0.3
        )  # 注意力衰减阈值
        self.attention_boost_step = config.get(
            "attention_boost_step", 0.4
        )  # 被回复用户注意力增加幅度
        self.attention_decrease_step = config.get(
            "attention_decrease_step", 0.1
        )  # 其他用户注意力减少幅度
        self.emotion_boost_step = config.get(
            "emotion_boost_step", 0.1
        )  # 被回复用户情绪增加幅度
        # 注意力情感检测配置
        self.enable_attention_emotion_detection = config.get(
            "enable_attention_emotion_detection", False
        )  # 启用注意力情感检测
        self.attention_emotion_keywords = config.get(
            "attention_emotion_keywords",
            '{"正面": ["谢谢", "感谢", "太好了", "棒", "赞"], "负面": ["傻", "蠢", "笨", "垃圾", "讨厌"]}',
        )  # 注意力情感关键词
        self.attention_enable_negation = config.get(
            "attention_enable_negation", True
        )  # 注意力机制启用否定词检测
        self.attention_negation_words = config.get(
            "attention_negation_words",
            ["不", "没", "别", "非", "无", "未", "勿", "莫", "不是", "没有"],
        )  # 注意力否定词列表
        self.attention_negation_check_range = config.get(
            "attention_negation_check_range", 5
        )  # 注意力否定词检查范围
        self.attention_positive_emotion_boost = config.get(
            "attention_positive_emotion_boost", 0.1
        )  # 正面消息情绪额外提升
        self.attention_negative_emotion_decrease = config.get(
            "attention_negative_emotion_decrease", 0.15
        )  # 负面消息情绪降低幅度
        # 注意力溢出机制配置
        self.enable_attention_spillover = config.get(
            "enable_attention_spillover", True
        )  # 启用注意力溢出
        self.attention_spillover_ratio = config.get(
            "attention_spillover_ratio", 0.35
        )  # 注意力溢出比例
        self.attention_spillover_decay_halflife = config.get(
            "attention_spillover_decay_halflife", 90
        )  # 溢出效果衰减半衰期
        self.attention_spillover_min_trigger = config.get(
            "attention_spillover_min_trigger", 0.4
        )  # 触发溢出的最低注意力阈值

        # === 注意力冷却机制配置 ===
        self.enable_attention_cooldown = config.get(
            "enable_attention_cooldown", True
        )  # 启用注意力冷却
        self.cooldown_max_duration = config.get(
            "cooldown_max_duration", 600
        )  # 冷却最大持续时间
        self.cooldown_trigger_threshold = config.get(
            "cooldown_trigger_threshold", 0.3
        )  # 触发冷却的注意力阈值
        self.cooldown_attention_decrease = config.get(
            "cooldown_attention_decrease", 0.2
        )  # 冷却时额外降低的注意力值

        # === 🆕 对话疲劳机制配置 ===
        self.enable_conversation_fatigue = config.get(
            "enable_conversation_fatigue", False
        )  # 启用对话疲劳机制
        self.fatigue_reset_threshold = max(
            60, config.get("fatigue_reset_threshold", 300)
        )  # 连续对话重置阈值（秒），最小60秒
        self.fatigue_threshold_light = max(
            1, config.get("fatigue_threshold_light", 3)
        )  # 轻度疲劳阈值，最小1轮
        self.fatigue_threshold_medium = max(
            self.fatigue_threshold_light + 1, config.get("fatigue_threshold_medium", 5)
        )  # 中度疲劳阈值，必须大于轻度
        self.fatigue_threshold_heavy = max(
            self.fatigue_threshold_medium + 1, config.get("fatigue_threshold_heavy", 8)
        )  # 重度疲劳阈值，必须大于中度
        self.fatigue_probability_decrease_light = max(
            0.0, min(1.0, config.get("fatigue_probability_decrease_light", 0.1))
        )  # 轻度疲劳概率降低幅度，限制在[0,1]
        self.fatigue_probability_decrease_medium = max(
            0.0, min(1.0, config.get("fatigue_probability_decrease_medium", 0.2))
        )  # 中度疲劳概率降低幅度，限制在[0,1]
        self.fatigue_probability_decrease_heavy = max(
            0.0, min(1.0, config.get("fatigue_probability_decrease_heavy", 0.35))
        )  # 重度疲劳概率降低幅度，限制在[0,1]
        self.fatigue_closing_probability = max(
            0.0, min(1.0, config.get("fatigue_closing_probability", 0.3))
        )  # 疲劳收尾话语概率，限制在[0,1]

        # 验证概率降低幅度的递增关系
        if (
            self.fatigue_probability_decrease_light
            > self.fatigue_probability_decrease_medium
        ):
            logger.warning(
                f"[对话疲劳] 配置异常: 轻度概率降低({self.fatigue_probability_decrease_light}) > "
                f"中度({self.fatigue_probability_decrease_medium})，已自动修正"
            )
            (
                self.fatigue_probability_decrease_light,
                self.fatigue_probability_decrease_medium,
            ) = (
                self.fatigue_probability_decrease_medium,
                self.fatigue_probability_decrease_light,
            )
        if (
            self.fatigue_probability_decrease_medium
            > self.fatigue_probability_decrease_heavy
        ):
            logger.warning(
                f"[对话疲劳] 配置异常: 中度概率降低({self.fatigue_probability_decrease_medium}) > "
                f"重度({self.fatigue_probability_decrease_heavy})，已自动修正"
            )
            (
                self.fatigue_probability_decrease_medium,
                self.fatigue_probability_decrease_heavy,
            ) = (
                self.fatigue_probability_decrease_heavy,
                self.fatigue_probability_decrease_medium,
            )

        # === 拟人增强模式配置 ===
        self.enable_humanize_mode = config.get(
            "enable_humanize_mode", False
        )  # 启用拟人增强模式

        # 静默模式触发阈值（最小1次，最大20次）
        self.humanize_silent_mode_threshold = max(
            1, min(20, config.get("humanize_silent_mode_threshold", 3))
        )

        # 静默模式最长持续时间（最小60秒，最大3600秒=1小时）
        self.humanize_silent_max_duration = max(
            60, min(3600, config.get("humanize_silent_max_duration", 600))
        )

        # 静默模式最大消息数（最小1条，最大50条）
        self.humanize_silent_max_messages = max(
            1, min(50, config.get("humanize_silent_max_messages", 8))
        )

        self.humanize_enable_dynamic_threshold = config.get(
            "humanize_enable_dynamic_threshold", True
        )

        # 基础消息阈值（最小1条，最大10条）
        self.humanize_base_message_threshold = max(
            1, min(10, config.get("humanize_base_message_threshold", 1))
        )

        # 最大消息阈值（最小1条，最大20条，且必须>=基础阈值）
        _humanize_max_threshold_raw = max(
            1, min(20, config.get("humanize_max_message_threshold", 3))
        )
        self.humanize_max_message_threshold = max(
            self.humanize_base_message_threshold, _humanize_max_threshold_raw
        )
        if _humanize_max_threshold_raw < self.humanize_base_message_threshold:
            logger.warning(
                f"[拟人增强] 配置异常: 最大消息阈值({_humanize_max_threshold_raw}) < "
                f"基础消息阈值({self.humanize_base_message_threshold})，已自动修正为 {self.humanize_max_message_threshold}"
            )

        self.humanize_include_decision_history = config.get(
            "humanize_include_decision_history", True
        )
        self.humanize_interest_keywords = config.get("humanize_interest_keywords", [])

        # 兴趣话题概率提升值（限制在0-1范围内）
        self.humanize_interest_boost_probability = max(
            0.0, min(1.0, config.get("humanize_interest_boost_probability", 0.3))
        )

        # === 打字错误生成器配置 ===
        self.enable_typo_generator = config.get(
            "enable_typo_generator", True
        )  # 启用打字错误生成器
        self.typo_error_rate = config.get("typo_error_rate", 0.02)  # 打字错误概率
        self.typo_homophones = config.get(
            "typo_homophones",
            '{"的": ["得", "地"], "得": ["的", "地"], "地": ["的", "得"]}',
        )  # 同音字映射表
        self.typo_min_text_length = config.get(
            "typo_min_text_length", 5
        )  # 添加错字的最小文本长度
        self.typo_min_chinese_chars = config.get(
            "typo_min_chinese_chars", 3
        )  # 添加错字的最小汉字数量
        self.typo_min_message_length = config.get(
            "typo_min_message_length", 10
        )  # 触发错字判断的最小消息长度
        self.typo_min_count = config.get("typo_min_count", 0)  # 每条消息最少添加错字数
        self.typo_max_count = config.get("typo_max_count", 2)  # 每条消息最多添加错字数

        # === 情绪追踪系统配置 ===
        self.enable_mood_system = config.get("enable_mood_system", True)  # 启用情绪系统
        self.negation_words = config.get(
            "negation_words",
            [
                "不",
                "没",
                "别",
                "非",
                "无",
                "未",
                "勿",
                "莫",
                "不是",
                "没有",
                "别再",
                "一点也不",
                "根本不",
                "从不",
                "绝不",
                "毫不",
            ],
        )  # 否定词列表
        self.negation_check_range = config.get(
            "negation_check_range", 5
        )  # 否定词检查范围
        self.mood_keywords = config.get(
            "mood_keywords",
            '{"开心": ["哈哈", "笑", "😂", "😄", "👍"], "难过": ["难过", "伤心", "哭", "😢", "😭"]}',
        )  # 情绪关键词配置
        self.mood_decay_time = config.get("mood_decay_time", 300)  # 情绪衰减时间
        self.mood_cleanup_threshold = config.get(
            "mood_cleanup_threshold", 3600
        )  # 情绪记录清理阈值
        self.mood_cleanup_interval = config.get(
            "mood_cleanup_interval", 600
        )  # 情绪记录清理检查间隔

        # === 频率动态调整配置 ===
        self.enable_frequency_adjuster = config.get(
            "enable_frequency_adjuster", True
        )  # 启用频率调整
        self.frequency_check_interval = config.get(
            "frequency_check_interval", 180
        )  # 频率检查间隔
        self.frequency_min_message_count = config.get(
            "frequency_min_message_count", 8
        )  # 最小消息数
        self.frequency_analysis_message_count = config.get(
            "frequency_analysis_message_count", 15
        )  # 分析消息数
        self.frequency_analysis_timeout = config.get(
            "frequency_analysis_timeout", 20
        )  # 分析超时
        self.frequency_adjust_duration = config.get(
            "frequency_adjust_duration", 360
        )  # 调整持续时间
        self.frequency_decrease_factor = config.get(
            "frequency_decrease_factor", 0.85
        )  # 降低系数
        self.frequency_increase_factor = config.get(
            "frequency_increase_factor", 1.15
        )  # 提升系数
        self.frequency_min_probability = config.get(
            "frequency_min_probability", 0.05
        )  # 最小概率
        self.frequency_max_probability = config.get(
            "frequency_max_probability", 0.95
        )  # 最大概率

        # === 回复延迟模拟配置 ===
        self.enable_typing_simulator = config.get(
            "enable_typing_simulator", True
        )  # 启用回复延迟
        self.typing_speed = config.get("typing_speed", 15.0)  # 打字速度
        self.typing_max_delay = config.get("typing_max_delay", 3.0)  # 最大延迟

        # === 主动对话配置 ===
        self.enable_proactive_chat = config.get(
            "enable_proactive_chat", False
        )  # 启用主动对话
        self.proactive_enabled_groups = config.get(
            "proactive_enabled_groups", []
        )  # 主动对话启用群组
        self.enable_proactive_at_conversion = config.get(
            "enable_proactive_at_conversion", False
        )  # 🆕 v1.2.0: 启用主动对话@转换功能
        # === 主动对话AI预判断配置 ===
        self.enable_proactive_ai_judge = config.get(
            "enable_proactive_ai_judge", False
        )  # 启用主动对话AI预判断
        self.proactive_ai_judge_prompt = config.get(
            "proactive_ai_judge_prompt", ""
        )  # 主动对话AI预判断提示词
        self.proactive_ai_judge_timeout = config.get(
            "proactive_ai_judge_timeout", 15
        )  # 主动对话AI预判断超时时间
        self.proactive_silence_threshold = config.get(
            "proactive_silence_threshold", 600
        )  # 沉默阈值
        self.proactive_probability = config.get(
            "proactive_probability", 0.3
        )  # 主动对话概率
        self.proactive_check_interval = config.get(
            "proactive_check_interval", 60
        )  # 检查间隔
        self.proactive_require_user_activity = config.get(
            "proactive_require_user_activity", True
        )  # 需要用户活跃
        self.proactive_min_user_messages = config.get(
            "proactive_min_user_messages", 3
        )  # 最少用户消息数
        self.proactive_user_activity_window = config.get(
            "proactive_user_activity_window", 300
        )  # 用户活跃时间窗口
        self.proactive_max_consecutive_failures = config.get(
            "proactive_max_consecutive_failures", 3
        )  # 最大连续失败次数
        self.proactive_failure_sequence_probability = config.get(
            "proactive_failure_sequence_probability", -1.0
        )  # 连续失败尝试计入概率
        self.proactive_failure_threshold_perturbation = config.get(
            "proactive_failure_threshold_perturbation", 0.0
        )  # 连续失败冷却阈值扰动因子
        self.proactive_cooldown_duration = config.get(
            "proactive_cooldown_duration", 1800
        )  # 失败后冷却时间
        self.proactive_temp_boost_probability = config.get(
            "proactive_temp_boost_probability", 0.5
        )  # 临时概率提升
        self.proactive_temp_boost_duration = config.get(
            "proactive_temp_boost_duration", 120
        )  # 临时提升持续时间
        self.proactive_enable_quiet_time = config.get(
            "proactive_enable_quiet_time", False
        )  # 启用禁用时段
        self.proactive_quiet_start = config.get(
            "proactive_quiet_start", "23:00"
        )  # 禁用时段开始
        self.proactive_quiet_end = config.get(
            "proactive_quiet_end", "07:00"
        )  # 禁用时段结束
        self.proactive_transition_minutes = config.get(
            "proactive_transition_minutes", 30
        )  # 过渡时长
        self.proactive_prompt = config.get("proactive_prompt", "")  # 主动对话提示词
        self.proactive_retry_prompt = config.get(
            "proactive_retry_prompt", ""
        )  # 主动对话重试提示词
        self.proactive_generation_timeout_warning = config.get(
            "proactive_generation_timeout_warning", 15
        )  # 主动对话生成超时警告阈值
        # 注意力感知主动对话配置
        self.proactive_use_attention = config.get(
            "proactive_use_attention", True
        )  # 启用注意力感知主动对话
        self.proactive_attention_reference_probability = config.get(
            "proactive_attention_reference_probability", 0.7
        )  # 参考注意力排行榜的概率
        self.proactive_attention_rank_weights = config.get(
            "proactive_attention_rank_weights", "1:55,2:25,3:12,4:8"
        )  # 排名选中权重分配
        self.proactive_attention_max_selected_users = config.get(
            "proactive_attention_max_selected_users", 2
        )  # 每次最多关注用户数
        self.proactive_focus_last_user_probability = config.get(
            "proactive_focus_last_user_probability", 0.6
        )  # 对话延续性提示概率
        self.proactive_reply_context_prompt = config.get(
            "proactive_reply_context_prompt", ""
        )  # 读空气AI主动对话回复上下文提示词
        # 自适应主动对话配置
        self.enable_adaptive_proactive = config.get(
            "enable_adaptive_proactive", True
        )  # 启用自适应主动对话
        self.interaction_score_min = config.get(
            "interaction_score_min", 10
        )  # 评分最小值
        self.interaction_score_max = config.get(
            "interaction_score_max", 100
        )  # 评分最大值
        self.score_increase_on_success = config.get(
            "score_increase_on_success", 15
        )  # 成功加分
        self.score_decrease_on_fail = config.get(
            "score_decrease_on_fail", 8
        )  # 失败扣分
        self.score_quick_reply_bonus = config.get(
            "score_quick_reply_bonus", 5
        )  # 快速回复额外加分
        self.score_multi_user_bonus = config.get(
            "score_multi_user_bonus", 10
        )  # 多人回复额外加分
        self.score_streak_bonus = config.get("score_streak_bonus", 5)  # 连续成功奖励
        self.score_revival_bonus = config.get("score_revival_bonus", 20)  # 低分复苏奖励
        self.interaction_score_decay_rate = config.get(
            "interaction_score_decay_rate", 2
        )  # 评分每日衰减值
        # 吐槽系统配置
        self.enable_complaint_system = config.get(
            "enable_complaint_system", True
        )  # 启用吐槽系统
        self.complaint_trigger_threshold = config.get(
            "complaint_trigger_threshold", 2
        )  # 触发吐槽的最低累积失败次数
        self.complaint_level_light = config.get(
            "complaint_level_light", 2
        )  # 轻度吐槽触发次数
        self.complaint_level_medium = config.get(
            "complaint_level_medium", 3
        )  # 明显吐槽触发次数
        self.complaint_level_strong = config.get(
            "complaint_level_strong", 4
        )  # 强烈吐槽触发次数
        self.complaint_probability_light = config.get(
            "complaint_probability_light", 0.3
        )  # 轻度吐槽触发概率
        self.complaint_probability_medium = config.get(
            "complaint_probability_medium", 0.6
        )  # 明显吐槽触发概率
        self.complaint_probability_strong = config.get(
            "complaint_probability_strong", 0.8
        )  # 强烈吐槽触发概率
        self.complaint_decay_on_success = config.get(
            "complaint_decay_on_success", 2
        )  # 成功互动时的失败次数衰减量
        self.complaint_decay_check_interval = config.get(
            "complaint_decay_check_interval", 21600
        )  # 时间衰减检查间隔
        self.complaint_decay_no_failure_threshold = config.get(
            "complaint_decay_no_failure_threshold", 43200
        )  # 无失败时间阈值
        self.complaint_decay_amount = config.get(
            "complaint_decay_amount", 1
        )  # 时间衰减数量
        self.complaint_max_accumulation = config.get(
            "complaint_max_accumulation", 15
        )  # 累积失败次数上限

        # === 动态时间段概率调整配置 ===
        self.enable_dynamic_reply_probability = config.get(
            "enable_dynamic_reply_probability", False
        )  # 启用普通回复动态调整
        self.reply_time_periods = config.get(
            "reply_time_periods", "[]"
        )  # 普通回复时间段配置
        self.reply_time_transition_minutes = config.get(
            "reply_time_transition_minutes", 30
        )  # 过渡时长
        self.reply_time_min_factor = config.get(
            "reply_time_min_factor", 0.1
        )  # 最小系数
        self.reply_time_max_factor = config.get(
            "reply_time_max_factor", 2.0
        )  # 最大系数
        self.reply_time_use_smooth_curve = config.get(
            "reply_time_use_smooth_curve", True
        )  # 使用平滑曲线
        self.enable_dynamic_proactive_probability = config.get(
            "enable_dynamic_proactive_probability", False
        )  # 启用主动对话动态调整
        self.proactive_time_periods = config.get(
            "proactive_time_periods", "[]"
        )  # 主动对话时间段配置
        self.proactive_time_transition_minutes = config.get(
            "proactive_time_transition_minutes", 45
        )  # 主动对话过渡时长
        self.proactive_time_min_factor = config.get(
            "proactive_time_min_factor", 0.0
        )  # 主动对话最小系数
        self.proactive_time_max_factor = config.get(
            "proactive_time_max_factor", 2.0
        )  # 主动对话最大系数
        self.proactive_time_use_smooth_curve = config.get(
            "proactive_time_use_smooth_curve", True
        )  # 主动对话使用平滑曲线

        # === 概率硬性限制配置 ===
        self.enable_probability_hard_limit = config.get(
            "enable_probability_hard_limit", False
        )  # 启用概率硬性限制
        self.probability_min_limit = config.get(
            "probability_min_limit", 0.05
        )  # 概率最小值限制
        self.probability_max_limit = config.get(
            "probability_max_limit", 0.8
        )  # 概率最大值限制

        # === 🆕 v1.2.1: 回复密度限制配置 ===
        self.enable_reply_density_limit = config.get(
            "enable_reply_density_limit", True
        )  # 启用回复密度限制
        self.reply_density_window_seconds = config.get(
            "reply_density_window_seconds", 300
        )  # 密度检测窗口（秒）
        self.reply_density_max_replies = config.get(
            "reply_density_max_replies", 5
        )  # 窗口内最大回复次数
        self.reply_density_soft_limit_ratio = config.get(
            "reply_density_soft_limit_ratio", 0.6
        )  # 软限比例（开始衰减的比例）
        self.reply_density_ai_hint = config.get(
            "reply_density_ai_hint", True
        )  # 向决策AI注入密度提示

        # === 🆕 v1.2.1: 消息质量预判配置 ===
        self.enable_message_quality_scoring = config.get(
            "enable_message_quality_scoring", True
        )  # 启用消息质量预判
        self.message_quality_question_boost = config.get(
            "message_quality_question_boost", 0.15
        )  # 疑问句概率提升
        self.message_quality_water_reduce = config.get(
            "message_quality_water_reduce", 0.10
        )  # 水消息概率降低
        # 词列表（完全由配置驱动，schema 里有默认值）
        _water_words_raw = config.get("message_quality_water_words", [])
        self.message_quality_water_words = (
            list(_water_words_raw) if isinstance(_water_words_raw, list) else []
        )  # 水消息词（整句完整匹配）
        _question_words_raw = config.get("message_quality_question_words", [])
        self.message_quality_question_words = (
            list(_question_words_raw) if isinstance(_question_words_raw, list) else []
        )  # 疑问词（包含匹配）

        self.enable_output_content_filter = config.get(
            "enable_output_content_filter", False
        )  # 启用输出内容过滤
        self.output_content_filter_rules = config.get(
            "output_content_filter_rules", []
        )  # 输出过滤规则
        self.enable_save_content_filter = config.get(
            "enable_save_content_filter", False
        )  # 启用保存内容过滤
        self.save_content_filter_rules = config.get(
            "save_content_filter_rules", []
        )  # 保存过滤规则

        # === 超时警告配置 ===
        self.reply_timeout_warning_threshold = config.get(
            "reply_timeout_warning_threshold", 120
        )  # 消息处理超时警告阈值
        self.reply_generation_timeout_warning = config.get(
            "reply_generation_timeout_warning", 60
        )  # 回复生成超时警告阈值
        self.concurrent_wait_max_loops = config.get(
            "concurrent_wait_max_loops", 10
        )  # 并发等待最大循环次数
        self.concurrent_wait_interval = config.get(
            "concurrent_wait_interval", 1.0
        )  # 并发等待间隔
        self.typing_delay_timeout_warning = config.get(
            "typing_delay_timeout_warning", 5
        )  # 打字延迟超时警告

        # === 否定词检测配置 ===
        self.enable_negation_detection = config.get(
            "enable_negation_detection", True
        )  # 启用否定词检测

        # === AI重复消息拦截配置 ===
        # 🔒 系统硬上限常量（防止内存泄漏）
        self._DUPLICATE_CHECK_COUNT_LIMIT = 50  # 检查条数硬上限
        self._DUPLICATE_CACHE_SIZE_LIMIT = 100  # 缓存大小硬上限
        self._DUPLICATE_TIME_LIMIT_MAX = 7200  # 时效硬上限（2小时）

        self.enable_duplicate_filter = config.get(
            "enable_duplicate_filter", True
        )  # 启用AI重复消息拦截
        # 🔒 应用硬上限保护
        _raw_check_count = config.get("duplicate_filter_check_count", 5)
        self.duplicate_filter_check_count = min(
            max(1, _raw_check_count), self._DUPLICATE_CHECK_COUNT_LIMIT
        )  # 重复检测参考消息条数（1-50）
        self.enable_duplicate_time_limit = config.get(
            "enable_duplicate_time_limit", True
        )  # 启用重复检测时效性判断
        # 🔒 应用硬上限保护
        _raw_time_limit = config.get("duplicate_filter_time_limit", 1800)
        self.duplicate_filter_time_limit = min(
            max(60, _raw_time_limit), self._DUPLICATE_TIME_LIMIT_MAX
        )  # 重复检测时效(秒)（60-7200）

        # === 私信功能开关 ===
        self.enable_private_chat = config.get(
            "enable_private_chat", False
        )  # 私信功能开关

        # === 私信指令过滤配置（独立于群聊） ===
        self.private_enable_command_filter = config.get(
            "private_enable_command_filter", True
        )  # 私信指令过滤开关
        self.private_command_prefixes = config.get(
            "private_command_prefixes", ["/", "!", "#"]
        )  # 私信指令前缀列表
        self.private_enable_full_command_detection = config.get(
            "private_enable_full_command_detection", False
        )  # 私信完整指令检测开关
        self.private_full_command_list = config.get(
            "private_full_command_list", ["new", "help", "reset"]
        )  # 私信完整指令列表
        self.private_enable_command_prefix_match = config.get(
            "private_enable_command_prefix_match", False
        )  # 私信指令前缀匹配开关
        self.private_command_prefix_match_list = config.get(
            "private_command_prefix_match_list", []
        )  # 私信指令前缀匹配列表
        self.private_chat_enable_debug_log = config.get(
            "private_chat_enable_debug_log", False
        )  # 启用私信处理的详细日志

        # === 私信图片缓存配置（因省钱缓存需要群聊/私信协调，故在 main.py 统一读取） ===
        # 其他私信图片配置（provider、prompt、timeout等）在 private_chat_main.py 中读取
        self.private_enable_image_description_cache = config.get(
            "private_enable_image_description_cache", False
        )  # 私信图片描述缓存开关（用于缓存协调）
        self.private_image_description_cache_max_entries = config.get(
            "private_image_description_cache_max_entries", 500
        )  # 私信图片描述缓存最大条目数（用于缓存协调）

        # === 私信清除缓存指令名单配置（因 gcp_clear_image_cache 命令处理器位于群聊模块 main.py 中，
        #     但需同时处理私信来源的指令，故在此处统一读取私信专用的名单配置，
        #     通过变量传递到命令处理器中使用，避免重复读取） ===
        self.private_gcp_clear_image_cache_filter_mode = config.get(
            "private_gcp_clear_image_cache_filter_mode", "blacklist"
        )  # 私信清除缓存指令名单模式（blacklist/whitelist）
        self.private_gcp_clear_image_cache_filter_list = config.get(
            "private_gcp_clear_image_cache_filter_list", []
        )  # 私信清除缓存指令用户ID名单

        # === Web 配置面板 ===
        self.enable_web_panel = config.get("enable_web_panel", False)
        self.web_panel_port = config.get("web_panel_port", 1451)
        self.web_panel_host = config.get("web_panel_host", "0.0.0.0")
        self.web_panel_reset_password = config.get("web_panel_reset_password", False)
        self._web_server = None  # Web 面板服务器实例

        # ========== 配置参数集中提取区块结束 ==========

        # Dashboard 配置与重启 URL
        self.dbc = self.context.get_config().get("dashboard", {})
        self.host = self.dbc.get("host", "127.0.0.1")
        self.port = self.dbc.get("port", 6185)
        if os.environ.get("DASHBOARD_PORT"):
            self.port = int(os.environ.get("DASHBOARD_PORT"))
        if self.host == "0.0.0.0":
            self.host = "127.0.0.1"
        self.restart_url = f"http://{self.host}:{self.port}/api/stat/restart-core"

        # 统一设置详细日志开关到本插件的 utils 包及其子模块（使用相对导入，避免命名冲突）
        try:
            import importlib
            import pkgutil

            utils_pkg_name = f"{__package__}.utils" if __package__ else "utils"
            utils_pkg = importlib.import_module(utils_pkg_name)

            # 根级别开关
            if hasattr(utils_pkg, "set_debug_mode"):
                utils_pkg.set_debug_mode(self.debug_mode)
            elif hasattr(utils_pkg, "DEBUG_MODE"):
                setattr(utils_pkg, "DEBUG_MODE", self.debug_mode)

            # 批量同步子模块的 DEBUG_MODE（如存在）
            for mod_info in pkgutil.iter_modules(utils_pkg.__path__):
                mod_name = f"{utils_pkg_name}.{mod_info.name}"
                try:
                    mod = importlib.import_module(mod_name)
                    if hasattr(mod, "DEBUG_MODE"):
                        setattr(mod, "DEBUG_MODE", self.debug_mode)
                except Exception:
                    pass
        except Exception:
            pass

        # 初始化上下文管理器（使用插件专属数据目录）
        # 注意：StarTools.get_data_dir() 会自动检测插件名称
        data_dir = StarTools.get_data_dir()
        ContextManager.init(
            str(data_dir), custom_storage_max_messages=self.custom_storage_max_messages
        )

        # 🆕 v1.2.0: 初始化图片描述缓存（群聊+私信共享同一份缓存文件）
        # 协调逻辑：需同时考虑「处理主开关」和「省钱缓存开关」的组合
        # - 群聊缓存生效 = 群聊处理开关开 AND 群聊省钱缓存开关开
        # - 私信缓存生效 = 私信处理开关开 AND 私信省钱缓存开关开
        # - 两边都生效且 max_entries 不同 → 取中间值
        # - 只有一边生效 → 以该边的限制为准
        # - 两边都不生效 → 不启用缓存
        _group_cache_active = (
            self.enable_group_chat and self.enable_image_description_cache
        )
        _private_cache_active = (
            self.enable_private_chat and self.private_enable_image_description_cache
        )
        _cache_enabled = _group_cache_active or _private_cache_active

        if _cache_enabled:
            _group_max = self.image_description_cache_max_entries
            _private_max = self.private_image_description_cache_max_entries

            if _group_cache_active and _private_cache_active:
                # 两边都生效，需要协调
                if _group_max != _private_max:
                    _reconciled_max = (_group_max + _private_max) // 2
                    logger.info(
                        f"💾 [缓存协调] 群聊({_group_max})和私信({_private_max})"
                        f"缓存上限不同，取中间值: {_reconciled_max}"
                    )
                else:
                    _reconciled_max = _group_max
            elif _group_cache_active:
                # 仅群聊缓存生效，以群聊限制为准
                _reconciled_max = _group_max
            else:
                # 仅私信缓存生效，以私信限制为准
                _reconciled_max = _private_max

            _reconciled_max = max(10, min(_reconciled_max, 10000))  # 硬上限保护
        else:
            # 两边都不生效，使用默认值（缓存不启用，此值无实际影响）
            _reconciled_max = 500

        self.image_description_cache = ImageDescriptionCache(
            data_dir=str(data_dir),
            max_entries=_reconciled_max,
            enabled=_cache_enabled,
        )
        if _cache_enabled:
            _active_sides = []
            if _group_cache_active:
                _active_sides.append("群聊")
            if _private_cache_active:
                _active_sides.append("私信")
            stats = self.image_description_cache.get_stats()
            logger.info(
                f"💾 图片描述缓存已启用（{'和'.join(_active_sides)}生效，共享缓存文件），"
                f"当前 {stats['entry_count']} 条，上限 {stats['max_entries']} 条"
            )

        # 🆕 v1.1.0: 初始化概率管理器（用于动态时间段调整）
        # 构建概率管理器配置字典（使用已提取的实例变量）
        probability_config = {
            "enable_dynamic_reply_probability": self.enable_dynamic_reply_probability,
            "reply_time_periods": self.reply_time_periods,
            "reply_time_transition_minutes": self.reply_time_transition_minutes,
            "reply_time_min_factor": self.reply_time_min_factor,
            "reply_time_max_factor": self.reply_time_max_factor,
            "reply_time_use_smooth_curve": self.reply_time_use_smooth_curve,
            "enable_probability_hard_limit": self.enable_probability_hard_limit,
            "probability_min_limit": self.probability_min_limit,
            "probability_max_limit": self.probability_max_limit,
        }
        ProbabilityManager.initialize(probability_config)

        # 🆕 v1.2.0: 初始化拟人增强模式管理器
        self.humanize_mode_enabled = self.enable_humanize_mode
        if self.humanize_mode_enabled:
            # 构建拟人增强模式的配置（使用已提取的实例变量）
            humanize_config = {
                "silent_mode_threshold": self.humanize_silent_mode_threshold,
                "silent_mode_max_duration": self.humanize_silent_max_duration,
                "silent_mode_max_messages": self.humanize_silent_max_messages,
                "enable_dynamic_threshold": self.humanize_enable_dynamic_threshold,
                "base_message_threshold": self.humanize_base_message_threshold,
                "max_message_threshold": self.humanize_max_message_threshold,
                "include_decision_history_in_prompt": self.humanize_include_decision_history,
                "interest_keywords": self.humanize_interest_keywords,
                "interest_boost_probability": self.humanize_interest_boost_probability,
            }
            HumanizeModeManager.initialize(humanize_config)
            logger.info("🎭 拟人增强模式已启用")

        # 🆕 v1.2.1: 初始化回复密度管理器
        density_config = {
            "enable_reply_density_limit": self.enable_reply_density_limit,
            "reply_density_window_seconds": self.reply_density_window_seconds,
            "reply_density_max_replies": self.reply_density_max_replies,
            "reply_density_soft_limit_ratio": self.reply_density_soft_limit_ratio,
            "reply_density_ai_hint": self.reply_density_ai_hint,
        }
        ReplyDensityManager.initialize(density_config)

        # 🆕 v1.2.1: 初始化消息质量预判器
        quality_config = {
            "enable_message_quality_scoring": self.enable_message_quality_scoring,
            "message_quality_question_boost": self.message_quality_question_boost,
            "message_quality_water_reduce": self.message_quality_water_reduce,
            "message_quality_water_words": self.message_quality_water_words,
            "message_quality_question_words": self.message_quality_question_words,
        }
        MessageQualityScorer.initialize(quality_config)

        # 🆕 v1.2.0: 初始化消息缓存管理器（统一管理所有缓存操作）
        # 替代原来的 self.pending_messages_cache = {} 字典
        self.cache_manager = MessageCacheManager(
            cache_ttl_seconds=self.pending_cache_ttl_seconds,
            max_cache_count=self.pending_cache_max_count,
            debug_mode=self.debug_mode,
            include_timestamp=self.include_timestamp,
            include_sender_info=self.include_sender_info,
        )
        # 🔧 为了兼容性，保留对原字典的引用（指向缓存管理器的内部字典）
        # 这样旧代码仍然可以访问 self.pending_messages_cache[chat_id]
        self.pending_messages_cache = self.cache_manager.pending_messages_cache

        # 标记本插件正在处理的消息（用于after_message_sent筛选）
        # 🔧 修复：使用message_id作为键，避免同一会话中多条消息并发时标记冲突
        # 格式: {message_id: chat_id}
        self.processing_sessions = {}

        # 🔧 并发控制锁，保护 processing_sessions 的检查-标记流程，避免竞态条件
        self.concurrent_lock = asyncio.Lock()

        # ⏳ 群聊等待窗口状态（v1.2.0）
        # key: (chat_id, user_id_str)
        # value: {"extra_count": int, "deadline": float, "force_complete": bool}
        self._group_wait_windows: dict = {}
        self._group_wait_window_lock = asyncio.Lock()
        self._group_wait_window_counter = (
            0  # 单调递增令牌，防止新窗口覆盖旧窗口后旧循环不退出
        )

        # 🔧 并发保护：存储消息缓存快照，供 after_message_sent 使用
        # 格式: {message_id: cached_message_dict}
        self._message_cache_snapshots = {}

        # 🆕 主动对话正在处理的会话标记（用于普通对话和主动对话之间的并发保护）
        # 格式: {chat_id: timestamp}，记录主动对话开始处理的时间
        # 普通对话在清空缓存前会检查此标记，避免与主动对话冲突
        self.proactive_processing_sessions = {}

        # 标记被识别为指令的消息（用于跨处理器通信）
        # 格式: {message_id: timestamp}，定期清理超过10秒的旧记录
        self.command_messages = {}

        # 🆕 私信指令标记（独立于群聊，用于私信跨处理器通信）
        # 格式: {message_id: timestamp}，定期清理超过10秒的旧记录
        self.private_command_messages = {}

        # 🆕 初始化私信处理器
        # 缓存相关由 main.py 协调后传入，其他私信图片配置由 private_chat_main.py 自行读取 config
        self.private_chat_handler = PrivateChatMain(
            context=self.context,
            config=config,
            plugin_instance=self,
            data_dir=str(data_dir),
            private_chat_debug_mode=self.private_chat_enable_debug_log,
            # 省钱缓存（由 main.py 协调群聊/私信后传入）
            enable_image_description_cache=self.private_enable_image_description_cache,
            image_description_cache=self.image_description_cache,
        )

        # 🆕 最近发送的回复缓存（用于去重检查）
        # 格式: {chat_id: [{"content": "回复内容", "timestamp": 时间戳}]}
        # 最多保留最近5条回复，超过30分钟的自动清理
        self.recent_replies_cache = {}
        self.raw_reply_cache = {}

        # 🔧 多轮工具调用支持：累积AI回复文本
        # 当AI先说话再调用工具再说话时，需要累积所有回复文本，
        # 等agent真正完成后再统一保存，避免只保存第一段话
        # 格式: {message_id: [原始文本1, 原始文本2, ...]}
        self._pending_bot_replies: dict[str, list[str]] = {}
        # agent完成标志：on_llm_response 设置，after_message_sent 消费
        # 格式: set of message_ids
        self._agent_done_flags: set[str] = set()

        # 🔧 重复消息拦截标记（用于 after_message_sent 判断是否跳过AI消息保存）
        # 格式: {message_id: True}
        # 当消息被重复检测拦截时，添加到此字典，after_message_sent 会跳过AI消息保存但继续保存用户消息
        self._duplicate_blocked_messages = {}

        # 🔧 已保存消息标记（防止分段消息重复保存）
        # 格式: {message_id: timestamp}
        # 记录已成功保存的消息ID，避免分段插件导致同一消息多次保存
        # 定期清理超过5分钟的旧记录
        self._saved_messages = {}

        # 🔧 消息去重：防止平台重复推送同一消息导致重复处理
        # 格式: {message_id: timestamp}
        # 当同一条消息被平台重复推送时（网络重连、WebSocket断线重连等），
        # 两个event拥有相同的message_id，此缓存确保只处理第一个
        # 定期清理超过60秒的旧记录
        self._seen_message_ids = {}

        # ========== v1.0.2 新增功能初始化 ==========

        # 1. 打字错误生成器
        self.typo_enabled = self.enable_typo_generator
        if self.typo_enabled:
            # 构建打字错误生成器配置字典（使用已提取的实例变量）
            typo_config = {
                "enable_debug_log": self.debug_mode,  # 🔧 传递调试模式
                "typo_homophones": self.typo_homophones,
                "typo_min_text_length": self.typo_min_text_length,
                "typo_min_chinese_chars": self.typo_min_chinese_chars,
                "typo_min_message_length": self.typo_min_message_length,
                "typo_min_count": self.typo_min_count,
                "typo_max_count": self.typo_max_count,
            }
            self.typo_generator = TypoGenerator(
                error_rate=self.typo_error_rate, config=typo_config
            )
        else:
            self.typo_generator = None

        # 2. 情绪追踪系统
        self.mood_enabled = self.enable_mood_system
        if self.mood_enabled:
            # 构建情绪追踪系统配置字典（使用已提取的实例变量）
            mood_config = {
                "enable_negation_detection": self.enable_negation_detection,
                "negation_words": self.negation_words,
                "negation_check_range": self.negation_check_range,
                "mood_keywords": self.mood_keywords,
                "mood_decay_time": self.mood_decay_time,
                "mood_cleanup_threshold": self.mood_cleanup_threshold,
                "mood_cleanup_interval": self.mood_cleanup_interval,
            }
            self.mood_tracker = MoodTracker(mood_config)
        else:
            self.mood_tracker = None

        # 3. 频率动态调整器
        self.frequency_adjuster_enabled = self.enable_frequency_adjuster
        if self.frequency_adjuster_enabled:
            # 构建频率调整器配置字典（使用已提取的实例变量）
            frequency_config = {
                "frequency_min_message_count": self.frequency_min_message_count,
                "frequency_decrease_factor": self.frequency_decrease_factor,
                "frequency_increase_factor": self.frequency_increase_factor,
                "frequency_min_probability": self.frequency_min_probability,
                "frequency_max_probability": self.frequency_max_probability,
                "frequency_analysis_message_count": self.frequency_analysis_message_count,
                "frequency_analysis_timeout": self.frequency_analysis_timeout,
                "frequency_adjust_duration": self.frequency_adjust_duration,
                # 动态时间段配置（频率调整器也需要）
                "enable_dynamic_reply_probability": self.enable_dynamic_reply_probability,
                "reply_time_periods": self.reply_time_periods,
                "reply_time_transition_minutes": self.reply_time_transition_minutes,
                "reply_time_min_factor": self.reply_time_min_factor,
                "reply_time_max_factor": self.reply_time_max_factor,
                "reply_time_use_smooth_curve": self.reply_time_use_smooth_curve,
            }
            self.frequency_adjuster = FrequencyAdjuster(context, frequency_config)
            # 设置检查间隔（使用已提取的实例变量）
            FrequencyAdjuster.CHECK_INTERVAL = self.frequency_check_interval
        else:
            self.frequency_adjuster = None

        # 4. 回复延迟模拟器
        self.typing_simulator_enabled = self.enable_typing_simulator
        if self.typing_simulator_enabled:
            self.typing_simulator = TypingSimulator(
                typing_speed=self.typing_speed,
                max_delay=self.typing_max_delay,
            )
        else:
            self.typing_simulator = None

        # ========== 注意力机制增强配置 ==========
        # 构建注意力管理器配置字典（使用已提取的实例变量）
        attention_config = {
            "enable_attention_emotion_detection": self.enable_attention_emotion_detection,
            "attention_emotion_keywords": self.attention_emotion_keywords,
            "attention_enable_negation": self.attention_enable_negation,
            "attention_negation_words": self.attention_negation_words,
            "attention_negation_check_range": self.attention_negation_check_range,
            "attention_positive_emotion_boost": self.attention_positive_emotion_boost,
            "attention_negative_emotion_decrease": self.attention_negative_emotion_decrease,
            "enable_attention_spillover": self.enable_attention_spillover,
            "attention_spillover_ratio": self.attention_spillover_ratio,
            "attention_spillover_decay_halflife": self.attention_spillover_decay_halflife,
            "attention_spillover_min_trigger": self.attention_spillover_min_trigger,
            # 🆕 对话疲劳机制配置
            "enable_conversation_fatigue": self.enable_conversation_fatigue,
            "fatigue_reset_threshold": self.fatigue_reset_threshold,
            "fatigue_threshold_light": self.fatigue_threshold_light,
            "fatigue_threshold_medium": self.fatigue_threshold_medium,
            "fatigue_threshold_heavy": self.fatigue_threshold_heavy,
            "fatigue_probability_decrease_light": self.fatigue_probability_decrease_light,
            "fatigue_probability_decrease_medium": self.fatigue_probability_decrease_medium,
            "fatigue_probability_decrease_heavy": self.fatigue_probability_decrease_heavy,
        }
        # 初始化注意力管理器（持久化存储和情感检测配置
        AttentionManager.initialize(str(data_dir), attention_config)

        # 应用自定义配置到AttentionManager（使用已提取的实例变量）
        attention_enabled = self.enable_attention_mechanism
        if attention_enabled:
            # 设置最大追踪用户数
            AttentionManager.MAX_TRACKED_USERS = self.attention_max_tracked_users
            # 设置注意力衰减半衰期
            AttentionManager.ATTENTION_DECAY_HALFLIFE = self.attention_decay_halflife
            # 设置情绪衰减半衰期
            AttentionManager.EMOTION_DECAY_HALFLIFE = self.emotion_decay_halflife

        # ========== 🆕 v1.2.0 注意力冷却机制初始化 ==========
        # 构建冷却管理器配置字典（使用已提取的实例变量）
        cooldown_config = {
            "cooldown_max_duration": self.cooldown_max_duration,
            "cooldown_trigger_threshold": self.cooldown_trigger_threshold,
            "cooldown_attention_decrease": self.cooldown_attention_decrease,
        }
        # 初始化冷却管理器（持久化存储和配置参数）
        self.cooldown_enabled = self.enable_attention_cooldown
        if self.cooldown_enabled and attention_enabled:
            CooldownManager.initialize(str(data_dir), cooldown_config)
            logger.info("🧊 注意力冷却机制已初始化")
        elif self.cooldown_enabled and not attention_enabled:
            logger.info("⚠️ 注意力冷却机制需要启用注意力机制才能生效")
            self.cooldown_enabled = False

        # ========== 🆕 v1.1.0 主动对话功能初始化 ==========
        self.proactive_enabled = self.enable_proactive_chat
        if self.proactive_enabled:
            # 初始化主动对话管理器（持久化存储）
            ProactiveChatManager.initialize(str(data_dir))
            logger.info("主动对话管理器已初始化")

        # 🆕 v1.2.0: 初始化主动对话回复用户追踪器（无论主动对话是否启用都需要初始化）
        self._proactive_reply_users = {}

        # ========== 🆕 回复后戳一戳功能初始化 ==========
        self.poke_after_reply_enabled = self.enable_poke_after_reply
        if self.poke_after_reply_enabled:
            # 使用已提取的实例变量（poke_after_reply_probability 和 poke_after_reply_delay 已在配置提取区块中设置）
            logger.info("回复后戳一戳功能已启用（仅支持QQ平台+aiocqhttp协议）")

        # ========== 🆕 收到戳一戳后反戳配置 ==========
        # 配置为概率值：[0,1]；0=禁用，1=必定反戳并丢弃本插件处理
        raw_reverse_prob = self.poke_reverse_on_poke_probability_raw
        try:
            reverse_prob = float(raw_reverse_prob)
        except (TypeError, ValueError):
            reverse_prob = 0.0
        # 夹紧到[0,1]
        if reverse_prob < 0:
            reverse_prob = 0.0
        if reverse_prob > 1:
            reverse_prob = 1.0
        self.poke_reverse_on_poke_probability = reverse_prob
        if self.poke_reverse_on_poke_probability > 0:
            logger.info(
                f"收到戳一戳后反戳功能启用，概率={self.poke_reverse_on_poke_probability} (原始={raw_reverse_prob})"
            )

        # ========== 🆕 AI戳后追踪提示功能 ==========
        self.poke_trace_enabled = self.enable_poke_trace_prompt
        # poke_trace_max_tracked_users 和 poke_trace_ttl_seconds 已在配置提取区块中设置
        self.poke_trace_records = {}

        # ========== 🆕 戳一戳功能群聊白名单 ==========
        # poke_enabled_groups 已在配置提取区块中设置
        # 转换为字符串列表，确保统一格式
        self.poke_enabled_groups = [str(g) for g in self.poke_enabled_groups]
        if self.poke_enabled_groups:
            logger.info(
                f"戳一戳功能群聊白名单已启用: {self.poke_enabled_groups} (仅这些群启用)"
            )
        else:
            logger.info("戳一戳功能群聊白名单: 未设置 (所有群启用)")

        # ========== 🆕 忽略@全体成员消息功能 ==========
        self.ignore_at_all_enabled = self.enable_ignore_at_all
        if self.ignore_at_all_enabled:
            logger.info("@全体成员消息过滤功能已启用（插件内部额外过滤）")

        # ========== 日志输出 ==========
        logger.info("=" * 50)
        logger.info("群聊增强插件已加载 - v1.2.1")
        logger.info(
            f"🔘 群聊功能总开关: {'✓ 已启用' if self.enable_group_chat else '✗ 已禁用'}"
        )
        logger.info(f"初始读空气概率: {self.initial_probability}")
        logger.info(f"回复后概率: {self.after_reply_probability}")
        logger.info(f"概率提升持续时间: {self.probability_duration}秒")
        logger.info(f"启用的群组: {self.enabled_groups} (留空=全部)")
        logger.info(f"详细日志模式: {'开启' if self.debug_mode else '关闭'}")

        # 注意力机制配置（增强版）
        logger.info(f"增强注意力机制: {'✓ 开启' if attention_enabled else '✗ 关闭'}")
        if attention_enabled:
            logger.info(f"  - 提升参考概率: {self.attention_increased_probability}")
            logger.info(f"  - 降低参考概率: {self.attention_decreased_probability}")
            logger.info(f"  - 数据清理周期: {self.attention_duration}秒")
            logger.info(f"  - 最大追踪用户: {self.attention_max_tracked_users}人")
            logger.info(f"  - 注意力半衰期: {self.attention_decay_halflife}秒")
            logger.info(f"  - 情绪半衰期: {self.emotion_decay_halflife}秒")

        # v1.0.2 新功能状态
        logger.info("\n【v1.0.2 开始的新功能】")
        logger.info(
            f"打字错误生成器: {'✓ 已启用' if self.typo_enabled else '✗ 已禁用'}"
        )
        logger.info(f"情绪追踪系统: {'✓ 已启用' if self.mood_enabled else '✗ 已禁用'}")
        logger.info(
            f"频率动态调整: {'✓ 已启用' if self.frequency_adjuster_enabled else '✗ 已禁用'}"
        )
        if self.frequency_adjuster_enabled:
            logger.info(f"  - 检查间隔: {self.frequency_check_interval} 秒")
            logger.info(f"  - 最小消息数: {self.frequency_min_message_count} 条")
            logger.info(f"  - 分析消息数: {self.frequency_analysis_message_count} 条")
            logger.info(f"  - 分析超时: {self.frequency_analysis_timeout} 秒")
            logger.info(f"  - 调整持续: {self.frequency_adjust_duration} 秒")
            logger.info(
                f"  - 调整系数: 过高↓{self.frequency_decrease_factor}({(1 - self.frequency_decrease_factor) * 100:.0f}%), "
                f"过低↑{self.frequency_increase_factor}({(self.frequency_increase_factor - 1) * 100:.0f}%)"
            )
            logger.info(
                f"  - 概率范围: {self.frequency_min_probability:.2f} - "
                f"{self.frequency_max_probability:.2f}"
            )
        logger.info(
            f"回复延迟模拟: {'✓ 已启用' if self.typing_simulator_enabled else '✗ 已禁用'}"
        )

        # v1.0.7 新功能状态
        logger.info("\n【v1.0.7 新增功能】")
        blacklist_enabled = self.enable_user_blacklist
        blacklist_count = len(self.blacklist_user_ids)
        logger.info(f"用户黑名单: {'✓ 已启用' if blacklist_enabled else '✗ 已禁用'}")
        if blacklist_enabled and blacklist_count > 0:
            logger.info(f"  - 黑名单用户数: {blacklist_count} 人")
        logger.info(
            f"情绪否定词检测: {'✓ 已启用' if self.enable_negation_detection else '✗ 已禁用'}"
        )

        # 🆕 v1.1.0 新功能状态
        logger.info("\n【🆕 v1.1.0 新增功能】")
        logger.info(
            f"主动对话功能: {'✨ 已启用' if self.proactive_enabled else '✗ 已禁用'}"
        )
        if self.proactive_enabled:
            # 白名单配置
            if self.proactive_enabled_groups and len(self.proactive_enabled_groups) > 0:
                logger.info(
                    f"  - 启用群聊白名单: {self.proactive_enabled_groups} (仅这些群启用)"
                )
            else:
                logger.info(f"  - 启用群聊白名单: [] (所有群启用)")

            logger.info(f"  - 沉默阈值: {self.proactive_silence_threshold} 秒")
            logger.info(f"  - 触发概率: {self.proactive_probability}")
            logger.info(f"  - 检查间隔: {self.proactive_check_interval} 秒")
            logger.info(
                f"  - 用户活跃度检测: {'✓' if self.proactive_require_user_activity else '✗'}"
            )
            logger.info(
                f"  - 临时概率提升: {self.proactive_temp_boost_probability} (持续{self.proactive_temp_boost_duration}秒)"
            )
            if self.proactive_enable_quiet_time:
                logger.info(
                    f"  - 禁用时段: {self.proactive_quiet_start}-{self.proactive_quiet_end}"
                )

            # 🆕 v1.2.0 评分系统状态
            logger.info(
                f"  - 智能自适应主动对话: {'✨ 已启用' if self.enable_adaptive_proactive else '✗ 已禁用'}"
            )
            if self.enable_adaptive_proactive:
                logger.info(
                    f"    · 评分范围: {self.interaction_score_min}-{self.interaction_score_max}分"
                )
                logger.info(f"    · 成功互动加分: +{self.score_increase_on_success}分")
                logger.info(f"    · 失败互动扣分: -{self.score_decrease_on_fail}分")

        # 🆕 v1.1.0 新功能状态 - 动态时间段概率调整
        logger.info("\n【🆕 v1.1.0 新增功能 - 动态时间段概率调整】")

        # 模式1：普通回复动态调整
        logger.info(
            f"模式1-普通回复动态调整: {'✨ 已启用' if self.enable_dynamic_reply_probability else '✗ 已禁用'}"
        )
        if self.enable_dynamic_reply_probability:
            try:
                periods = TimePeriodManager.parse_time_periods(self.reply_time_periods)
                logger.info(f"  - 已配置 {len(periods)} 个时间段")
                for period in periods[:3]:  # 只显示前3个
                    name = period.get("name", "未命名")
                    start = period.get("start", "")
                    end = period.get("end", "")
                    factor = period.get("factor", 1.0)
                    logger.info(f"    · {name}: {start}-{end} (系数{factor:.2f})")
                if len(periods) > 3:
                    logger.info(f"    · ...还有{len(periods) - 3}个时间段")
            except Exception as e:
                logger.warning(f"  - 解析时间段配置失败: {e}")

            logger.info(f"  - 过渡时长: {self.reply_time_transition_minutes} 分钟")
            logger.info(
                f"  - 系数范围: {self.reply_time_min_factor:.2f} - {self.reply_time_max_factor:.2f}"
            )
            logger.info(
                f"  - 平滑曲线: {'✓ 启用' if self.reply_time_use_smooth_curve else '✗ 禁用'}"
            )

        # 模式2：主动对话动态调整
        logger.info(
            f"模式2-主动对话动态调整: {'✨ 已启用' if self.enable_dynamic_proactive_probability else '✗ 已禁用'}"
        )
        if self.enable_dynamic_proactive_probability:
            try:
                periods = TimePeriodManager.parse_time_periods(
                    self.proactive_time_periods
                )
                logger.info(f"  - 已配置 {len(periods)} 个时间段")
                for period in periods[:3]:  # 只显示前3个
                    name = period.get("name", "未命名")
                    start = period.get("start", "")
                    end = period.get("end", "")
                    factor = period.get("factor", 1.0)
                    logger.info(f"    · {name}: {start}-{end} (系数{factor:.2f})")
                if len(periods) > 3:
                    logger.info(f"    · ...还有{len(periods) - 3}个时间段")
            except Exception as e:
                logger.warning(f"  - 解析时间段配置失败: {e}")

            logger.info(f"  - 过渡时长: {self.proactive_time_transition_minutes} 分钟")
            logger.info(
                f"  - 系数范围: {self.proactive_time_min_factor:.2f} - {self.proactive_time_max_factor:.2f}"
            )
            logger.info(
                f"  - 平滑曲线: {'✓ 启用' if self.proactive_time_use_smooth_curve else '✗ 禁用'}"
            )

            # 优先级提醒
            if self.proactive_enabled and self.proactive_enable_quiet_time:
                logger.info(f"  - ⚠️ 注意: '禁用时段'优先级高于动态调整")

        # 🆕 v1.2.1 新功能状态
        logger.info("\n【🆕 v1.2.1 新增功能】")
        logger.info(
            f"回复密度限制: {'✓ 已启用' if self.enable_reply_density_limit else '✗ 已禁用'}"
        )
        if self.enable_reply_density_limit:
            logger.info(f"  - 窗口时长: {self.reply_density_window_seconds}秒")
            logger.info(f"  - 最大回复: {self.reply_density_max_replies}次")
            logger.info(f"  - 软限比例: {self.reply_density_soft_limit_ratio}")
            logger.info(f"  - AI密度提示: {'✓' if self.reply_density_ai_hint else '✗'}")
        logger.info(
            f"消息质量预判: {'✓ 已启用' if self.enable_message_quality_scoring else '✗ 已禁用'}"
        )
        if self.enable_message_quality_scoring:
            logger.info(f"  - 疑问句提升: +{self.message_quality_question_boost:.2f}")
            logger.info(f"  - 水消息降低: -{self.message_quality_water_reduce:.2f}")

        logger.info("=" * 50)

        if self.debug_mode:
            logger.info("【调试模式】配置详情:")
            logger.info(f"  - 读空气AI提供商: {self.decision_ai_provider_id or '默认'}")
            logger.info(f"  - 包含时间戳: {self.include_timestamp}")
            logger.info(f"  - 包含发送者信息: {self.include_sender_info}")
            logger.info(f"  - 最大上下文消息数: {self.max_context_messages}")
            logger.info(f"  - 📦 消息缓存最大条数: {self.pending_cache_max_count}")
            logger.info(f"  - 📦 消息缓存过期时间: {self.pending_cache_ttl_seconds}秒")
            if self.enable_group_wait_window:
                logger.info(
                    f"  - ⏳ 群聊等待窗口: 启用 "
                    f"(超时={self.group_wait_window_timeout_ms}ms, "
                    f"最大额外消息={self._group_wait_window_max_extra}条, "
                    f"最大并发用户数={self.group_wait_window_max_users})"
                )
            logger.info(f"  - 启用图片处理: {self.enable_image_processing}")
            logger.info(f"  - 启用记忆植入: {self.enable_memory_injection}")
            logger.info(f"  - 启用工具提醒: {self.enable_tools_reminder}")
            logger.info(f"  - 工具提醒按人格过滤: {self.tools_reminder_persona_filter}")

        # ========== 🆕 v1.2.0 AI回复内容过滤器初始化 ==========
        self.content_filter = ContentFilterManager(
            enable_output_filter=self.enable_output_content_filter,
            output_filter_rules=self.output_content_filter_rules,
            enable_save_filter=self.enable_save_content_filter,
            save_filter_rules=self.save_content_filter_rules,
            debug_mode=self.debug_mode,
        )

        # 日志输出内容过滤器状态
        output_filter_enabled = self.enable_output_content_filter
        save_filter_enabled = self.enable_save_content_filter
        if output_filter_enabled or save_filter_enabled:
            logger.info("\n【🆕 v1.2.0 AI回复内容过滤】")
            logger.info(
                f"输出内容过滤: {'✓ 已启用' if output_filter_enabled else '✗ 已禁用'}"
            )
            if output_filter_enabled:
                output_rules = self.output_content_filter_rules
                logger.info(f"  - 过滤规则数: {len(output_rules)} 条")
            logger.info(
                f"保存内容过滤: {'✓ 已启用' if save_filter_enabled else '✗ 已禁用'}"
            )
            if save_filter_enabled:
                save_rules = self.save_content_filter_rules
                logger.info(f"  - 过滤规则数: {len(save_rules)} 条")

    def _build_proactive_config(self) -> dict:
        """
        构建主动对话管理器所需的配置字典（使用已提取的实例变量）

        Returns:
            主动对话配置字典
        """
        return {
            # 吐槽系统配置
            "enable_complaint_system": self.enable_complaint_system,
            "complaint_trigger_threshold": self.complaint_trigger_threshold,
            "complaint_level_light": self.complaint_level_light,
            "complaint_level_medium": self.complaint_level_medium,
            "complaint_level_strong": self.complaint_level_strong,
            "complaint_probability_light": self.complaint_probability_light,
            "complaint_probability_medium": self.complaint_probability_medium,
            "complaint_probability_strong": self.complaint_probability_strong,
            "complaint_max_accumulation": self.complaint_max_accumulation,
            "complaint_decay_on_success": self.complaint_decay_on_success,
            "complaint_decay_check_interval": self.complaint_decay_check_interval,
            "complaint_decay_no_failure_threshold": self.complaint_decay_no_failure_threshold,
            "complaint_decay_amount": self.complaint_decay_amount,
            # 自适应主动对话配置
            "enable_adaptive_proactive": self.enable_adaptive_proactive,
            "interaction_score_min": self.interaction_score_min,
            "interaction_score_max": self.interaction_score_max,
            "score_increase_on_success": self.score_increase_on_success,
            "score_decrease_on_fail": self.score_decrease_on_fail,
            "score_quick_reply_bonus": self.score_quick_reply_bonus,
            "score_multi_user_bonus": self.score_multi_user_bonus,
            "score_streak_bonus": self.score_streak_bonus,
            "score_revival_bonus": self.score_revival_bonus,
            "interaction_score_decay_rate": self.interaction_score_decay_rate,
            # 主动对话基础配置
            "proactive_enabled_groups": self.proactive_enabled_groups,
            "proactive_silence_threshold": self.proactive_silence_threshold,
            "proactive_cooldown_duration": self.proactive_cooldown_duration,
            "proactive_max_consecutive_failures": self.proactive_max_consecutive_failures,
            "proactive_failure_threshold_perturbation": self.proactive_failure_threshold_perturbation,
            "proactive_failure_sequence_probability": self.proactive_failure_sequence_probability,
            "proactive_require_user_activity": self.proactive_require_user_activity,
            "proactive_min_user_messages": self.proactive_min_user_messages,
            "proactive_probability": self.proactive_probability,
            "proactive_user_activity_window": self.proactive_user_activity_window,
            # 时间段控制配置
            "proactive_enable_quiet_time": self.proactive_enable_quiet_time,
            "proactive_quiet_start": self.proactive_quiet_start,
            "proactive_quiet_end": self.proactive_quiet_end,
            "proactive_transition_minutes": self.proactive_transition_minutes,
            "enable_dynamic_proactive_probability": self.enable_dynamic_proactive_probability,
            "proactive_time_periods": self.proactive_time_periods,
            "proactive_time_transition_minutes": self.proactive_time_transition_minutes,
            "proactive_time_min_factor": self.proactive_time_min_factor,
            "proactive_time_max_factor": self.proactive_time_max_factor,
            "proactive_time_use_smooth_curve": self.proactive_time_use_smooth_curve,
            "proactive_check_interval": self.proactive_check_interval,
            "proactive_temp_boost_probability": self.proactive_temp_boost_probability,
            "proactive_temp_boost_duration": self.proactive_temp_boost_duration,
            # 提示词配置
            "proactive_prompt": self.proactive_prompt,
            "proactive_retry_prompt": self.proactive_retry_prompt,
            "proactive_generation_timeout_warning": self.proactive_generation_timeout_warning,
            "proactive_reply_context_prompt": self.proactive_reply_context_prompt,
            # 注意力感知配置
            "enable_attention_mechanism": self.enable_attention_mechanism,
            "proactive_use_attention": self.proactive_use_attention,
            "proactive_attention_reference_probability": self.proactive_attention_reference_probability,
            "proactive_attention_rank_weights": self.proactive_attention_rank_weights,
            "proactive_attention_max_selected_users": self.proactive_attention_max_selected_users,
            "proactive_focus_last_user_probability": self.proactive_focus_last_user_probability,
            # 上下文和消息格式配置
            "max_context_messages": self.max_context_messages,
            "include_timestamp": self.include_timestamp,
            "include_sender_info": self.include_sender_info,
            # 记忆注入配置
            "enable_memory_injection": self.enable_memory_injection,
            "memory_plugin_mode": self.memory_plugin_mode,
            "livingmemory_top_k": self.livingmemory_top_k,
            "livingmemory_version": self.livingmemory_version,
            # 工具提醒配置
            "enable_tools_reminder": self.enable_tools_reminder,
            "tools_reminder_persona_filter": self.tools_reminder_persona_filter,
            # 📦 消息缓存配置（用于主动对话读取缓存时过滤过期消息）
            "pending_cache_max_count": self.pending_cache_max_count,
            "pending_cache_ttl_seconds": self.pending_cache_ttl_seconds,
            # 🔄 AI重复消息拦截配置
            "enable_duplicate_filter": self.enable_duplicate_filter,
            "duplicate_filter_check_count": self.duplicate_filter_check_count,
            "enable_duplicate_time_limit": self.enable_duplicate_time_limit,
            "duplicate_filter_time_limit": self.duplicate_filter_time_limit,
            # 🆕 v1.2.0: AI回复内容过滤配置（传递给主动对话管理器）
            "enable_output_content_filter": self.enable_output_content_filter,
            "output_content_filter_rules": self.output_content_filter_rules,
            "enable_save_content_filter": self.enable_save_content_filter,
            "save_content_filter_rules": self.save_content_filter_rules,
            # 🆕 v1.2.0: 主动对话@转换配置
            "enable_proactive_at_conversion": self.enable_proactive_at_conversion,
            # 🆕 主动对话AI预判断配置
            "enable_proactive_ai_judge": self.enable_proactive_ai_judge,
            "proactive_ai_judge_prompt": self.proactive_ai_judge_prompt,
            "proactive_ai_judge_timeout": self.proactive_ai_judge_timeout,
            "decision_ai_provider_id": self.decision_ai_provider_id,
        }

    def _emit_session_metadata(self):
        """输出运行时指纹信息"""
        _emit_fingerprint()

    def _check_compliance_status(self):
        """低频随机日志输出（约 10% 采样率）"""
        if random.random() < 0.1:
            self._emit_session_metadata()

    def _compute_session_integrity(self, seed: str = "") -> str:
        """计算当前插件实例的运行时签名"""
        raw = f"{self.__class__.__name__}:{seed}:{int(time.time() // 3600)}"
        sig = hashlib.md5(raw.encode()).hexdigest()
        if int(sig[-2:], 16) < 26:  # 约 10% 概率输出运行时信息
            self._emit_session_metadata()
        return sig

    async def initialize(self):
        """
        🆕 v1.1.0: 插件激活时调用

        启动主动对话功能的后台任务
        """
        self.session = aiohttp.ClientSession()
        # 生成运行时签名，用于追踪插件实例状态
        self._session_sig = self._compute_session_integrity("init")
        self._emit_session_metadata()
        # 🔘 仅当群聊功能总开关开启时，才启动主动对话后台任务
        if self.enable_group_chat and self.proactive_enabled:
            try:
                # 构建主动对话配置字典（使用已提取的实例变量）
                proactive_config = self._build_proactive_config()
                # 启动主动对话后台任务
                await ProactiveChatManager.start_background_task(
                    self.context,
                    proactive_config,  # 传递配置字典
                    self,  # 传递插件实例（用于发送消息等）
                )
                logger.info("✅ [主动对话] 后台任务已启动")
            except Exception as e:
                logger.error(f"[主动对话] 启动后台任务失败: {e}", exc_info=True)
        elif not self.enable_group_chat and self.proactive_enabled:
            logger.info("⏸️ [主动对话] 群聊功能总开关已关闭，跳过启动主动对话后台任务")

        # 🌐 启动 Web 配置面板
        if self.enable_web_panel:
            try:
                from .web.server import WebPanelServer

                self._web_server = WebPanelServer(
                    self, host=self.web_panel_host, port=self.web_panel_port
                )

                # 检测密码重置标志
                if self.web_panel_reset_password:
                    self._web_server.auth_mgr.reset_to_default()
                    self.config["web_panel_reset_password"] = False
                    self.config.save_config()
                    logger.info("🌐 Web 面板密码已重置，新密码已输出到日志")

                await self._web_server.start()
            except Exception as e:
                logger.error(f"🌐 Web 配置面板启动失败: {e}", exc_info=True)
                self._web_server = None

    async def terminate(self):
        """
        🆕 v1.1.0: 插件禁用/重载时调用

        停止主动对话功能的后台任务并保存状态
        """
        if self.proactive_enabled:
            try:
                await ProactiveChatManager.stop_background_task()
                logger.info("⏹️ [主动对话] 后台任务已停止，状态已保存")
            except Exception as e:
                logger.error(f"[主动对话] 停止后台任务失败: {e}", exc_info=True)
        if hasattr(self, "session"):
            await self.session.close()

        # 🌐 停止 Web 配置面板
        if hasattr(self, "_web_server") and self._web_server:
            try:
                await self._web_server.stop()
            except Exception as e:
                logger.error(f"🌐 Web 配置面板停止失败: {e}", exc_info=True)

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        restart_umo = self.config.get("restart_umo")
        platform_id = self.config.get("platform_id")
        restart_start_ts = self.config.get("restart_start_ts")
        if not restart_umo or not platform_id or not restart_start_ts:
            return

        platform = self.context.get_platform_inst(platform_id)
        if not isinstance(platform, AiocqhttpAdapter):
            logger.warning("未找到 aiocqhttp 平台实例，跳过重启提示")
            # 发送错误提示给用户
            try:
                await self.context.send_message(
                    session=restart_umo,
                    message_chain=MessageChain(
                        [
                            Plain(
                                f"⚠️ 重启完成提示发送失败：当前平台不支持重启提示功能（仅支持aiocqhttp平台）"
                            )
                        ]
                    ),
                )
            except Exception as e:
                logger.error(f"发送重启失败提示时出错: {e}")
            # 清理配置
            self.config["restart_umo"] = ""
            self.config["restart_start_ts"] = 0
            self.config.save_config()
            return
        client = platform.get_client()
        if not client:
            logger.warning("未找到 CQHttp 实例，跳过重启提示")
            # 发送错误提示给用户
            try:
                await self.context.send_message(
                    session=restart_umo,
                    message_chain=MessageChain(
                        [Plain(f"⚠️ 重启完成提示发送失败：未找到CQHttp客户端实例")]
                    ),
                )
            except Exception as e:
                logger.error(f"发送重启失败提示时出错: {e}")
            # 清理配置
            self.config["restart_umo"] = ""
            self.config["restart_start_ts"] = 0
            self.config.save_config()
            return

        ws_connected = asyncio.Event()

        @client.on_websocket_connection
        def _(_):
            ws_connected.set()

        try:
            await asyncio.wait_for(ws_connected.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning(
                "等待 aiocqhttp WebSocket 连接超时，可能未能发送重启完成提示。"
            )

        elapsed = time.time() - float(restart_start_ts)

        await self.context.send_message(
            session=restart_umo,
            message_chain=MessageChain(
                [Plain(f"AstrBot重启完成（耗时{elapsed:.2f}秒）")]
            ),
        )

        self.config["restart_umo"] = ""
        self.config["restart_start_ts"] = 0
        self.config.save_config()

    async def _get_auth_token(self):
        """获取认证token"""
        login_url = f"http://{self.host}:{self.port}/api/auth/login"
        login_data = {
            "username": self.dbc["username"],
            "password": self.dbc["password"],
        }
        async with self.session.post(login_url, json=login_data) as response:
            if response.status == 200:
                data = await response.json()
                if data and data.get("status") == "ok" and "data" in data:
                    return data["data"]["token"]
                else:
                    raise Exception(f"登录响应格式错误: {data}")
            else:
                text = await response.text()
                raise Exception(f"登录失败，状态码: {response.status}, 响应: {text}")

    @filter.event_message_type(filter.EventMessageType.ALL, priority=sys.maxsize - 1)
    async def command_filter_handler(self, event: AstrMessageEvent):
        """
        指令过滤处理器（高优先级）

        在所有其他处理器之前执行，检测并过滤指令消息。
        如果检测到指令，标记该消息，让本插件的其他处理器跳过。

        优先级: sys.maxsize-1 (超高优先级，确保最先执行)

        注意：使用 NotPokeMessageFilter 在 filter 阶段就过滤掉戳一戳消息，
        确保戳一戳消息不会激活此 handler，从而能正常传播到其他插件。
        """
        try:
            # 🔘 检查群聊功能总开关，并且只处理群消息
            if self.enable_group_chat and not event.is_private_chat():
                # 检查群组是否启用插件
                if not self._is_enabled(event):
                    return

                # 🔧 修复：定期清理过期的指令标记（无论是否检测到新指令，避免内存泄漏）
                current_time = time.time()
                expired_ids = [
                    mid
                    for mid, timestamp in self.command_messages.items()
                    if current_time - timestamp > 10
                ]
                for mid in expired_ids:
                    del self.command_messages[mid]

                # 检测是否为指令消息
                if self._is_command_message(event):
                    # 生成消息唯一标识（用于跨处理器通信）
                    msg_id = self._get_message_id(event)
                    self.command_messages[msg_id] = (
                        current_time  # 使用已计算的 current_time
                    )

                    # 检测到指令，标记后直接返回（不调用 stop_event，让其他插件处理）
                    return
            elif self.enable_private_chat and event.is_private_chat():
                # 🆕 私信指令过滤逻辑（独立于群聊，使用私信专用配置和数据）

                # 定期清理过期的私信指令标记（避免内存泄漏）
                current_time = time.time()
                expired_ids = [
                    mid
                    for mid, timestamp in self.private_command_messages.items()
                    if current_time - timestamp > 10
                ]
                for mid in expired_ids:
                    del self.private_command_messages[mid]

                # 检测是否为指令消息（使用私信专用配置）
                if self._is_private_command_message(event):
                    # 生成消息唯一标识（用于跨处理器通信）
                    msg_id = self._get_message_id(event)
                    self.private_command_messages[msg_id] = current_time

                    if self.private_chat_enable_debug_log:
                        logger.info(
                            "[私信指令过滤] 检测到私信指令，标记后让其他插件处理"
                        )
                    # 检测到指令，标记后直接返回
                    return
            else:
                return
        except Exception as e:
            # 捕获所有异常，避免影响其他插件的事件处理
            logger.error(f"[指令过滤] 处理消息时发生错误: {e}", exc_info=True)
            # 出错时直接返回，不影响其他handler的执行
            return

    @event_message_type(EventMessageType.PRIVATE_MESSAGE)
    async def on_private_message(self, event: AstrMessageEvent):
        """
        🆕 私信消息事件监听

        独立的私信处理入口，跳转到私信专用处理模块

        Args:
            event: 消息事件对象
        """
        try:
            # 检测私信处理开关
            if not self.enable_private_chat or not event.is_private_chat():
                return

            # 获取消息ID
            msg_id = self._get_message_id(event)

            # 🔧 消息去重：检查是否已经在处理相同的消息
            # 防止平台重复推送同一条消息（网络重连、WebSocket断线等）导致重复AI回复
            current_time = time.time()
            # 定期清理超过60秒的旧记录（避免内存泄漏）
            if len(self._seen_message_ids) > 100:
                self._seen_message_ids = {
                    k: v
                    for k, v in self._seen_message_ids.items()
                    if current_time - v < 60
                }
            if msg_id in self._seen_message_ids:
                if self.private_chat_enable_debug_log:
                    logger.info(
                        f"[私信-消息去重] 检测到重复消息 {msg_id[:30]}...，跳过处理"
                        f"（距首次处理 {current_time - self._seen_message_ids[msg_id]:.1f}秒）"
                    )
                # 🔧 阻止框架的默认LLM调用（仅阻止默认链路，不影响其他插件）
                # 因为第一份消息已经处理过，重复消息不应再触发框架的默认LLM回复
                event.call_llm = True
                return
            self._seen_message_ids[msg_id] = current_time

            # 检查是否被高优先级处理器标记为私信指令消息
            if msg_id in self.private_command_messages:
                # 这条消息已被识别为指令，跳过处理
                if self.private_chat_enable_debug_log:
                    logger.info("[私信] 消息已被标记为指令，跳过处理")
                return

            # 【🆕 转发消息解析】在指令检查和去重之后，将转发消息转换为纯文本
            # 指令消息已提前丢弃，避免不必要的 API 调用
            if self.enable_forward_message_parsing:
                try:
                    _forward_parsed = await ForwardMessageParser.try_parse_and_replace(
                        event,
                        include_sender_info=self.include_sender_info,
                        include_timestamp=self.include_timestamp,
                        max_nesting_depth=self.forward_max_nesting_depth,
                        debug_mode=self.private_chat_enable_debug_log,
                    )
                    if _forward_parsed and self.private_chat_enable_debug_log:
                        logger.info("[转发消息] 私聊：已成功解析转发消息并替换为纯文本")
                except Exception as e:
                    logger.warning(
                        f"[转发消息] 私聊：解析转发消息时出错（已跳过，不影响后续处理）: {e}"
                    )

            # 通过所有过滤检查，将消息传递给私信处理模块
            await self.private_chat_handler.handle_message(event)

        except Exception as e:
            logger.error(f"处理私信消息时发生错误: {e}", exc_info=True)

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """
        群消息事件监听

        采用监听模式，不影响其他插件和官方功能

        Args:
            event: 消息事件对象
        """
        # 🔧 用于 finally 安全清理，防止 processing_sessions 泄漏导致后续消息卡住
        _cleanup_message_id = None
        try:
            # 🔘 检查群聊功能总开关
            if not self.enable_group_chat or event.is_private_chat():
                return

            self._check_compliance_status()

            # 检查是否被高优先级处理器标记为指令消息
            msg_id = self._get_message_id(event)
            _cleanup_message_id = msg_id  # 保存用于 finally 清理

            # 🔧 消息去重：检查是否已经在处理相同的消息
            # 防止平台重复推送同一条消息（网络重连、WebSocket断线等）导致重复AI回复
            current_time = time.time()
            # 定期清理超过60秒的旧记录（避免内存泄漏）
            if len(self._seen_message_ids) > 100:
                self._seen_message_ids = {
                    k: v
                    for k, v in self._seen_message_ids.items()
                    if current_time - v < 60
                }
            if msg_id in self._seen_message_ids:
                if self.debug_mode:
                    logger.info(
                        f"[消息去重] 检测到重复消息 {msg_id[:30]}...，跳过处理"
                        f"（距首次处理 {current_time - self._seen_message_ids[msg_id]:.1f}秒）"
                    )
                # 🔧 阻止框架的默认LLM调用（仅阻止默认链路，不影响其他插件）
                # 因为第一份消息已经处理过，重复消息不应再触发框架的默认LLM回复
                event.call_llm = True
                return
            self._seen_message_ids[msg_id] = current_time

            if msg_id in self.command_messages:
                # 这条消息已被识别为指令，跳过处理
                if self.debug_mode:
                    logger.info("消息已被标记为指令，跳过处理")
                return

            # 【v1.0.7】检测用户是否在黑名单中
            if self._is_user_blacklisted(event):
                # 用户在黑名单中，本插件直接跳过处理
                return

            # 【🆕 新成员入群消息解析】在黑名单检查之后、转发消息解析之前
            # 将新成员入群的空消息解析为系统提示，避免AI误判为空消息
            if self.enable_welcome_message_parsing:
                try:
                    _welcome_parsed = await WelcomeMessageParser.try_parse_and_replace(
                        event,
                        include_sender_info=self.include_sender_info,
                        include_timestamp=self.include_timestamp,
                        debug_mode=self.debug_mode,
                    )
                    if _welcome_parsed:
                        if self.debug_mode:
                            logger.info("[入群解析] 群聊：已成功解析新成员入群事件")
                        if self.welcome_message_mode == "parse_only":
                            # 仅解析，不进入AI流程，直接返回
                            if self.debug_mode:
                                logger.info(
                                    "[入群解析] 模式为 parse_only，跳过后续处理"
                                )
                            return
                        # 标记此事件为入群消息，供后续概率/决策流程使用
                        event.set_extra("is_welcome_message", True)
                        event.set_extra(
                            "welcome_message_mode", self.welcome_message_mode
                        )
                except Exception as e:
                    logger.warning(
                        f"[入群解析] 群聊：解析入群事件时出错（已跳过，不影响后续处理）: {e}"
                    )

            # 【🆕 转发消息解析】在指令检查和去重之后，将转发消息转换为纯文本
            # 指令消息已提前丢弃，避免不必要的 API 调用
            if self.enable_forward_message_parsing:
                try:
                    _forward_parsed = await ForwardMessageParser.try_parse_and_replace(
                        event,
                        include_sender_info=self.include_sender_info,
                        include_timestamp=self.include_timestamp,
                        max_nesting_depth=self.forward_max_nesting_depth,
                        debug_mode=self.debug_mode,
                    )
                    if _forward_parsed and self.debug_mode:
                        logger.info("[转发消息] 群聊：已成功解析转发消息并替换为纯文本")
                except Exception as e:
                    logger.warning(
                        f"[转发消息] 群聊：解析转发消息时出错（已跳过，不影响后续处理）: {e}"
                    )

            # 【🆕】检测是否应该忽略@全体成员消息
            if self._should_ignore_at_all(event):
                # 消息包含@全体成员，根据配置忽略处理
                # 不阻止消息传播，其他插件仍可处理此消息
                if self.debug_mode:
                    logger.info("[@全体成员检测] 消息包含@全体成员，本插件跳过处理")
                return

            # 【v1.0.9新增】过滤伪造的戳一戳文本标识符
            # 防止用户手动输入"[Poke:poke]"来伪造戳一戳消息
            message_str = event.get_message_str()
            if MessageCleaner.is_only_poke_marker(message_str):
                # 消息只包含"[Poke:poke]"标识符，直接丢弃
                if self.debug_mode:
                    logger.info(
                        "【戳一戳标识符过滤】消息只包含[Poke:poke]标识符，跳过处理"
                    )
                return

            # 【v1.0.9新增】检测是否应该忽略@他人的消息
            if self._should_ignore_at_others(event):
                # 消息中@了其他人（根据配置的模式），本插件跳过处理
                # 不阻止消息传播，其他插件仍可处理此消息
                if self.debug_mode:
                    logger.info("[@他人检测] 消息符合忽略条件，本插件跳过处理")
                return

            # 【v1.0.9新增】检测是否为戳一戳消息
            poke_result = self._check_poke_message(event)
            if poke_result.get("is_poke") and poke_result.get("should_ignore"):
                # 戳一戳消息但根据配置应该忽略，本插件跳过处理
                # 不阻止消息传播，其他插件（如astrbot_plugin_llm_poke）仍可处理此消息
                if self.debug_mode:
                    logger.info("【戳一戳检测】消息符合忽略条件，本插件跳过处理")
                return

            # 处理群消息
            async for result in self._process_message(event):
                yield result
        except Exception as e:
            logger.error(f"处理群消息时发生错误: {e}", exc_info=True)
        finally:
            # 🔧 安全网：确保 processing_sessions 条目不会泄漏
            # 当 after_message_sent 未被框架调用时（如 on_decorating_result 清空了 result，
            # 或 _generate_and_send_reply 未 yield 就提前返回，或管线中途异常），
            # 此处作为最终保障进行清理，防止后续消息卡在并发等待循环中
            if _cleanup_message_id:
                self.processing_sessions.pop(_cleanup_message_id, None)
                self._message_cache_snapshots.pop(_cleanup_message_id, None)
                self._duplicate_blocked_messages.pop(_cleanup_message_id, None)

    async def restart_core(self):
        """
        发送重启请求,重启AstrBot,并记录重启信息
        """
        try:
            token = await self._get_auth_token()
            headers = {"Authorization": f"Bearer {token}"}
            async with self.session.post(self.restart_url, headers=headers) as response:
                if response.status == 200:
                    logger.info("系统重启请求已发送")
                else:
                    logger.error(f"重启请求失败，状态码: {response.status}")
                    raise RuntimeError(f"重启请求失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"发送重启请求时出错: {e}")
            raise e

    @filter.command("gcp_reset")
    async def gcp_reset(self, event: AstrMessageEvent):
        """全局重置插件：清空所有会话的插件缓存与数据文件，设置历史截止点（忽略重置前的平台聊天记录），然后重启 AstrBot。不会删除平台官方的对话历史。"""
        try:
            # 群聊处理开关未启用则直接忽略
            if not self.enable_group_chat:
                return
            # 只处理群聊（规避私聊误触）
            if event.is_private_chat():
                return
            # 群未启用则直接忽略
            if not self._is_enabled(event):
                return
            # 需要能访问到原始消息链
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return
            components = event.message_obj.message
            if not components:
                return
            # 必须是"纯文本"消息，防止图片/引用等组件混入而误触
            if not all(isinstance(c, Plain) for c in components):
                return
            # 白名单：为空=允许所有用户；否则仅允许列表内用户
            whitelist = self.plugin_gcp_reset_allowed_user_ids
            allow_all = not whitelist or len(whitelist) == 0
            sender_id = str(event.get_sender_id())
            allowed = allow_all or (str(sender_id) in {str(x) for x in whitelist})
            if not allowed:
                # 不在白名单：按"已处理"返回，防止本条消息继续触发本插件的其他逻辑
                logger.info(
                    "【会话重置】用户 %s 未在白名单中，重置指令被忽略",
                    sender_id,
                )
                return
            # 通过全部校验：执行清理+热重载，并发送提示
            try:
                await self._reset_plugin_data_and_reload()
                # 成功提示
                try:
                    platform_name = event.get_platform_name()
                    chat_id = event.get_group_id()
                    session_str = f"{platform_name}:GroupMessage:{chat_id}"
                    notice = (
                        "【Group Chat Plus】插件全局重置：成功\n"
                        "\n"
                        "已执行以下操作：\n"
                        "1. 清空所有会话的插件缓存（待处理消息、回复记录、情绪/注意力/概率等状态）\n"
                        "2. 删除插件本地数据文件（自定义聊天记录、注意力/主动对话/冷却持久化文件）\n"
                        "3. 设置历史截止点（插件将忽略重置前的平台聊天记录，避免旧消息被重新读入AI上下文）\n"
                        "\n"
                        "注意：本操作不会删除平台官方的对话历史和聊天记录，如需清除请使用平台的 /reset 指令。\n"
                        "即将重启 AstrBot..."
                    )
                    yield event.plain_result(f"{notice}")
                    logger.info(f"{session_str}: {notice}")

                    self.config["platform_id"] = event.get_platform_id()
                    self.config["restart_umo"] = event.unified_msg_origin
                    self.config["restart_start_ts"] = time.time()
                    self.config.save_config()
                    logger.info(
                        "重启：已记录 platform_id、restart_umo 与 restart_start_ts，准备重启"
                    )
                    try:
                        await self.restart_core()
                    except Exception as e:
                        yield event.plain_result(f"重启失败：{e}")
                        logger.error(f"重启失败：{e}")
                except Exception:
                    pass
            except Exception:
                # 失败提示
                try:
                    platform_name = event.get_platform_name()
                    chat_id = event.get_group_id()
                    session_str = f"{platform_name}:GroupMessage:{chat_id}"
                    notice = (
                        "【Group Chat Plus】插件全局重置：失败\n"
                        "执行重置时发生内部错误，请查看日志。"
                    )
                    yield event.plain_result(f"{notice}")
                    logger.info(f"{session_str}: {notice}")
                except Exception:
                    pass
            return
        except Exception:
            return

    @filter.command("gcp_reset_here")
    async def gcp_reset_here(self, event: AstrMessageEvent):
        """重置当前会话：清空本会话的插件缓存与上下文文件，设置历史截止点（忽略重置前的平台聊天记录），然后重启 AstrBot。不影响其他会话，不会删除平台官方的对话历史。"""
        try:
            # 群聊处理开关未启用则直接忽略
            if not self.enable_group_chat:
                return
            # 仅群聊生效；为避免误触，私聊环境不处理该指令
            if event.is_private_chat():
                return
            # 若该群聊未启用插件，则直接忽略
            if not self._is_enabled(event):
                return
            # 需访问到底层消息结构（原始消息链）以便做"纯文本"判断
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return
            components = event.message_obj.message
            # 空消息（极少见）直接忽略
            if not components:
                return
            # 必须是"纯文本"消息（仅 Plain 组件），防止图片/引用等造成误触
            if not all(isinstance(c, Plain) for c in components):
                return
            # 白名单判定：空列表=允许所有用户；否则仅允许列表内用户
            whitelist = self.plugin_gcp_reset_here_allowed_user_ids
            allow_all = not whitelist or len(whitelist) == 0
            sender_id = str(event.get_sender_id())
            allowed = allow_all or (str(sender_id) in {str(x) for x in whitelist})
            # 若不被允许，按"已处理"返回，阻止该消息继续触发本插件其它逻辑
            if not allowed:
                logger.info(
                    "【会话重置】用户 %s 未在白名单中，重置指令被忽略",
                    sender_id,
                )
                return
            # 执行当前会话的数据重置并发送提示
            try:
                await self._reset_session_data(event)
                # 成功提示
                try:
                    platform_name = event.get_platform_name()
                    chat_id = event.get_group_id()
                    session_str = f"{platform_name}:GroupMessage:{chat_id}"
                    notice = (
                        "【Group Chat Plus】当前会话重置：成功\n"
                        "\n"
                        "已执行以下操作：\n"
                        "1. 清空本会话的插件缓存（待处理消息、回复记录、情绪/注意力/概率等状态）\n"
                        "2. 删除本会话的插件上下文文件\n"
                        "3. 设置历史截止点（插件将忽略重置前的平台聊天记录，避免旧消息被重新读入AI上下文）\n"
                        "\n"
                        "注意：本操作不会删除平台官方的对话历史和聊天记录，如需清除请使用平台的 /reset 指令。\n"
                        "即将重启 AstrBot..."
                    )
                    yield event.plain_result(f"{notice}")
                    logger.info(f"{session_str}: {notice}")

                    self.config["platform_id"] = event.get_platform_id()
                    self.config["restart_umo"] = event.unified_msg_origin
                    self.config["restart_start_ts"] = time.time()
                    self.config.save_config()
                    logger.info(
                        "重启：已记录 platform_id、restart_umo 与 restart_start_ts，准备重启"
                    )
                    try:
                        await self.restart_core()
                    except Exception as e:
                        yield event.plain_result(f"重启失败：{e}")
                        logger.error(f"重启失败：{e}")
                except Exception:
                    pass
            except Exception:
                # 失败提示
                try:
                    platform_name = event.get_platform_name()
                    chat_id = event.get_group_id()
                    session_str = f"{platform_name}:GroupMessage:{chat_id}"
                    notice = (
                        "【Group Chat Plus】当前会话重置：失败\n"
                        "执行重置时发生内部错误，请查看日志。"
                    )
                    yield event.plain_result(f"{notice}")
                    logger.info(f"{session_str}: {notice}")
                except Exception:
                    pass
            return
        except Exception:
            # 兜底保护：异常时返回 ，不影响其他插件处理
            return

    @filter.command("gcp_clear_image_cache")
    async def gcp_clear_image_cache(self, event: AstrMessageEvent):
        """
        清除本地图片描述缓存并重启AstrBot。

        触发条件（群聊和私信分别检查）：
        - 群聊来源：群聊功能已启用 + 该群已启用 + 群聊白名单检查通过
        - 私信来源：私信功能已启用 + 私信名单检查通过（支持黑名单/白名单模式）

        名单逻辑说明：
        - 群聊：使用 gcp_clear_image_cache_allowed_user_ids（白名单模式，留空=允许所有人）
        - 私信：使用 private_gcp_clear_image_cache_filter_mode + private_gcp_clear_image_cache_filter_list
          · blacklist 模式：名单内用户不能使用，其他人可以
          · whitelist 模式：仅名单内用户能使用
          · 名单留空=不过滤，允许所有人使用
        """
        try:
            is_private = event.is_private_chat()

            # ========== 来源判断：群聊 or 私信 ==========
            if is_private:
                # --- 私信来源 ---
                if not self.enable_private_chat:
                    return
            else:
                # --- 群聊来源 ---
                if not self.enable_group_chat:
                    return
                # 群未启用则直接忽略
                if not self._is_enabled(event):
                    return

            # 需要能访问到原始消息链
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return
            components = event.message_obj.message
            if not components:
                return
            # 必须是"纯文本"消息
            if not all(isinstance(c, Plain) for c in components):
                return

            # ========== 名单权限检查：群聊和私信使用各自独立的名单 ==========
            sender_id = str(event.get_sender_id())

            if is_private:
                # --- 私信名单检查（支持黑名单/白名单模式） ---
                filter_list = self.private_gcp_clear_image_cache_filter_list
                filter_mode = self.private_gcp_clear_image_cache_filter_mode

                if filter_list and len(filter_list) > 0:
                    # 名单不为空，按模式检查
                    id_set = {str(x) for x in filter_list}
                    in_list = sender_id in id_set

                    if filter_mode == "whitelist":
                        # 白名单模式：仅名单内用户可以使用
                        if not in_list:
                            logger.info(
                                "【图片缓存清除·私信】用户 %s 不在白名单中，指令被忽略",
                                sender_id,
                            )
                            return
                    else:
                        # 黑名单模式（默认）：名单内用户不能使用
                        if in_list:
                            logger.info(
                                "【图片缓存清除·私信】用户 %s 在黑名单中，指令被忽略",
                                sender_id,
                            )
                            return
                # 名单为空 → 不过滤，允许所有用户
            else:
                # --- 群聊白名单检查（原有逻辑不变） ---
                whitelist = self.gcp_clear_image_cache_allowed_user_ids
                allow_all = not whitelist or len(whitelist) == 0
                allowed = allow_all or (sender_id in {str(x) for x in whitelist})
                if not allowed:
                    logger.info(
                        "【图片缓存清除·群聊】用户 %s 未在白名单中，指令被忽略",
                        sender_id,
                    )
                    return

            # ========== 执行清除（群聊/私信共享同一份缓存文件） ==========
            source_label = "私信" if is_private else "群聊"
            try:
                stats_before = self.image_description_cache.get_stats()
                success = self.image_description_cache.clear()

                if success:
                    platform_name = event.get_platform_name()
                    if is_private:
                        chat_id = event.get_sender_id()
                        session_str = f"{platform_name}:PrivateMessage:{chat_id}"
                    else:
                        chat_id = event.get_group_id()
                        session_str = f"{platform_name}:GroupMessage:{chat_id}"
                    notice = (
                        f"【Group Chat Plus】图片描述缓存清除结果：成功\n"
                        f"已清除 {stats_before['entry_count']} 条缓存记录（来源：{source_label}），即将重启AstrBot。"
                    )
                    yield event.plain_result(notice)
                    logger.info(f"{session_str}: {notice}")

                    # 记录重启信息并重启
                    self.config["platform_id"] = event.get_platform_id()
                    self.config["restart_umo"] = event.unified_msg_origin
                    self.config["restart_start_ts"] = time.time()
                    self.config.save_config()
                    logger.info(
                        "重启：图片缓存清除后准备重启（来源：%s）", source_label
                    )
                    try:
                        await self.restart_core()
                    except Exception as e:
                        yield event.plain_result(f"重启失败：{e}")
                        logger.error(f"重启失败：{e}")
                else:
                    yield event.plain_result(
                        "【Group Chat Plus】图片描述缓存清除结果：失败\n"
                        "请查看日志了解详情。"
                    )
            except Exception as e:
                try:
                    yield event.plain_result(
                        f"【Group Chat Plus】图片描述缓存清除结果：失败\n原因：{e}"
                    )
                except Exception:
                    pass
            return
        except Exception:
            return

    async def _reset_session_data(self, event: AstrMessageEvent) -> None:
        """
        清理"当前会话"的本插件缓存与派生状态，不触碰 AstrBot 官方对话历史。

        主要包含：
        - 清空与该会话相关的内存缓存（待转存消息、处理中标记、去重缓存、戳一戳追踪等）
        - 重置该会话的概率/注意力/情绪等增强模块状态
        - 删除该会话在本插件数据目录中的持久化上下文文件
        - 持久化保存必要的状态变更
        """
        try:
            # 获取定位当前会话所需的关键维度
            platform_name = event.get_platform_name()
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            logger.info(
                "【会话重置】开始: platform=%s, 类型=%s, chat_id=%s",
                platform_name,
                "私聊" if is_private else "群聊",
                chat_id,
            )

            # —— 内存态缓存清理 ——
            try:
                # 待转存的消息缓存（本插件的自定义历史，用于不回复时保留上下文）
                if chat_id in self.pending_messages_cache:
                    cached_count = len(self.pending_messages_cache.get(chat_id, []))
                    del self.pending_messages_cache[chat_id]

                    logger.info(
                        "【会话重置】已清空待转存消息缓存 chat_id=%s, 清理条数=%s",
                        chat_id,
                        cached_count,
                    )
            except Exception:
                logger.warning("【会话重置】清空待转存消息缓存失败", exc_info=True)
            try:
                # 🔧 修复：处理中消息标记现在使用message_id作为键
                # 需要遍历并删除所有与该chat_id相关的条目
                # 🔒 使用锁保护查找和删除操作，避免与并发检测冲突
                async with self.concurrent_lock:
                    keys_to_remove = [
                        msg_id
                        for msg_id, cid in self.processing_sessions.items()
                        if cid == chat_id
                    ]
                    for msg_id in keys_to_remove:
                        del self.processing_sessions[msg_id]

                if keys_to_remove:
                    logger.info(
                        "【会话重置】已移除处理中标记 chat_id=%s, 清理条数=%s",
                        chat_id,
                        len(keys_to_remove),
                    )
            except Exception:
                logger.warning("【会话重置】移除处理中标记失败", exc_info=True)
            try:
                # 最近回复缓存（用于去重检查，避免短时间内重复回复同内容）
                if chat_id in self.recent_replies_cache:
                    replies_cleared = len(self.recent_replies_cache.get(chat_id, []))
                    del self.recent_replies_cache[chat_id]

                    logger.info(
                        "【会话重置】已清空最近回复缓存 chat_id=%s, 清理条数=%s",
                        chat_id,
                        replies_cleared,
                    )
            except Exception:
                logger.warning("【会话重置】清空最近回复缓存失败", exc_info=True)
            try:
                # "回复后戳一戳"追踪记录（限定该会话）
                k = str(chat_id)
                if (
                    isinstance(getattr(self, "poke_trace_records", None), dict)
                    and k in self.poke_trace_records
                ):
                    del self.poke_trace_records[k]

                    logger.info("【会话重置】已移除戳一戳追踪记录 chat_id=%s", chat_id)
            except Exception:
                logger.warning("【会话重置】移除戳一戳追踪记录失败", exc_info=True)
            try:
                # 情绪系统：重置该会话的情绪基线
                if hasattr(self, "mood_tracker") and self.mood_tracker:
                    self.mood_tracker.reset_mood(str(chat_id))

                    logger.info("【会话重置】情绪状态已重置 chat_id=%s", chat_id)
            except Exception:
                logger.warning("【会话重置】重置情绪状态失败", exc_info=True)

            # —— 模块状态重置 ——
            try:
                # 概率管理：恢复该会话的触发概率到初始状态

                logger.info("【会话重置】开始重置概率状态 chat_id=%s", chat_id)
                await ProbabilityManager.reset_probability(
                    platform_name, is_private, chat_id
                )

                logger.info("【会话重置】概率状态重置完成 chat_id=%s", chat_id)
            except Exception:
                logger.warning("【会话重置】重置概率状态失败", exc_info=True)
            try:
                # 注意力管理：清空该会话的注意力与情绪权重

                logger.info("【会话重置】开始清空注意力状态 chat_id=%s", chat_id)
                await AttentionManager.clear_attention(
                    platform_name, is_private, chat_id
                )

                logger.info("【会话重置】注意力状态清空完成 chat_id=%s", chat_id)
            except Exception:
                logger.warning("【会话重置】清空注意力状态失败", exc_info=True)
            try:
                # 频率调整器：清理该会话的检查状态
                if hasattr(self, "frequency_adjuster") and self.frequency_adjuster:
                    chat_key = ProbabilityManager.get_chat_key(
                        platform_name, is_private, chat_id
                    )
                    if chat_key in self.frequency_adjuster.check_states:
                        del self.frequency_adjuster.check_states[chat_key]
                        logger.info(
                            "【会话重置】已清空频率检查状态 chat_key=%s",
                            chat_key,
                        )
            except Exception:
                logger.warning("【会话重置】清空频率检查状态失败", exc_info=True)
            try:
                # 主动对话：撤销临时概率提升并清理会话状态
                chat_key = ProbabilityManager.get_chat_key(
                    platform_name, is_private, chat_id
                )
                try:
                    ProactiveChatManager.deactivate_temp_probability_boost(
                        chat_key, "会话重置"
                    )
                except Exception:
                    logger.warning(
                        "【会话重置】撤销临时概率提升失败 chat_key=%s",
                        chat_key,
                        exc_info=True,
                    )
                if (
                    hasattr(ProactiveChatManager, "_chat_states")
                    and chat_key in ProactiveChatManager._chat_states
                ):
                    del ProactiveChatManager._chat_states[chat_key]

                    logger.info(
                        "【会话重置】已移除主动对话状态 chat_key=%s",
                        chat_key,
                    )
                if (
                    hasattr(ProactiveChatManager, "_temp_probability_boost")
                    and chat_key in ProactiveChatManager._temp_probability_boost
                ):
                    del ProactiveChatManager._temp_probability_boost[chat_key]

                    logger.info(
                        "【会话重置】已清空临时概率提升状态 chat_key=%s",
                        chat_key,
                    )
                # 🆕 v1.2.0: 清理主动对话回复用户追踪器
                if (
                    hasattr(self, "_proactive_reply_users")
                    and chat_key in self._proactive_reply_users
                ):
                    del self._proactive_reply_users[chat_key]
                    logger.info(
                        "【会话重置】已清空主动对话回复追踪 chat_key=%s",
                        chat_key,
                    )

                if hasattr(ProactiveChatManager, "_save_states_to_disk"):
                    ProactiveChatManager._save_states_to_disk()

                    logger.info(
                        "【会话重置】主动对话状态已持久化 chat_key=%s", chat_key
                    )
            except Exception:
                logger.warning("【会话重置】清理主动对话状态失败", exc_info=True)

            # 🆕 v1.2.0: 拟人增强模式状态清理
            try:
                if self.humanize_mode_enabled:
                    chat_key = ProbabilityManager.get_chat_key(
                        platform_name, is_private, chat_id
                    )
                    await HumanizeModeManager.reset_state(chat_key)
                    logger.info("【会话重置】已清空拟人增强状态 chat_key=%s", chat_key)
            except Exception:
                logger.warning("【会话重置】清空拟人增强状态失败", exc_info=True)

            # 🆕 v1.2.0: 冷却机制状态清理 (Requirements 5.1)
            try:
                if self.cooldown_enabled:
                    chat_key = ProbabilityManager.get_chat_key(
                        platform_name, is_private, chat_id
                    )
                    cooldown_cleared = await CooldownManager.clear_session_cooldown(
                        chat_key
                    )
                    if cooldown_cleared > 0:
                        logger.info(
                            "【会话重置】已清空冷却状态 chat_key=%s, 清理用户数=%s",
                            chat_key,
                            cooldown_cleared,
                        )
            except Exception:
                logger.warning("【会话重置】清空冷却状态失败", exc_info=True)

            # —— 持久化上下文清理 ——
            try:
                # 删除该会话在本插件用于缓存的上下文文件（非官方历史）
                file_path = ContextManager._get_storage_path(
                    platform_name, is_private, chat_id
                )
                if file_path is None:
                    logger.warning(
                        "【会话重置】无法获取上下文文件路径（base_storage_path 未初始化），尝试手动构建路径"
                    )
                    # 🔧 修复：手动构建路径作为备选方案
                    try:
                        data_dir = StarTools.get_data_dir()
                        if data_dir:
                            chat_type = "private" if is_private else "group"
                            file_path = (
                                Path(str(data_dir))
                                / "chat_history"
                                / platform_name
                                / chat_type
                                / f"{chat_id}.json"
                            )
                            logger.info(f"【会话重置】手动构建路径: {file_path}")
                    except Exception as path_err:
                        logger.warning(f"【会话重置】手动构建路径失败: {path_err}")
                        file_path = None

                if file_path and file_path.exists():
                    try:
                        file_path.unlink()
                        logger.info(
                            "【会话重置】已删除会话上下文文件 path=%s",
                            file_path,
                        )
                    except Exception as del_err:
                        logger.warning(
                            "【会话重置】删除会话上下文文件失败 path=%s, error=%s",
                            file_path,
                            del_err,
                            exc_info=True,
                        )
                elif file_path:
                    logger.info(
                        "【会话重置】会话上下文文件不存在，无需删除 path=%s",
                        file_path,
                    )
                else:
                    logger.warning("【会话重置】无法确定上下文文件路径，跳过删除")
            except Exception:
                logger.warning("【会话重置】处理上下文文件失败", exc_info=True)
            # —— 设置历史截止时间戳 ——
            # 记录当前时间为截止点，后续从平台读取历史时丢弃此时间之前的消息
            try:
                ContextManager.set_history_cutoff(chat_id)
                logger.info("【会话重置】已设置历史截止时间戳 chat_id=%s", chat_id)
            except Exception:
                logger.warning("【会话重置】设置历史截止时间戳失败", exc_info=True)
            try:
                # 将注意力变更落盘，确保重置后的状态被保存
                if hasattr(AttentionManager, "_save_to_disk"):
                    AttentionManager._save_to_disk(force=True)

                    logger.info("【会话重置】注意力状态已持久化 chat_id=%s", chat_id)
            except Exception:
                logger.warning("【会话重置】注意力状态持久化失败", exc_info=True)

            logger.info(
                "【会话重置】完成: platform=%s, chat_id=%s",
                platform_name,
                chat_id,
            )
        except Exception:
            # 兜底保护：任何异常都不传播，避免影响外部流程

            logger.error("【会话重置】执行失败", exc_info=True)
            pass

    async def _reset_plugin_data_and_reload(self) -> None:
        """
        清空本插件的本地缓存与派生数据。

        注意：
        - 不会删除 AstrBot 官方对话系统中的历史（ConversationManager 维护的官方历史保留）
        - 仅清理本插件维护的内存态与数据目录下的本地缓存文件
        - 重载通过 PluginManager.reload('chat_plus') 实现，名称与 @register 一致
        """
        try:
            logger.info("【插件重置】开始: 清理全局缓存并热重载")
            # 🔧 修复：在清空内存数据之前，先收集所有已知 chat_id
            # 用于后续设置历史截止时间戳，防止平台旧消息被重新读入
            _all_chat_ids_for_cutoff = set()
            try:
                _all_chat_ids_for_cutoff.update(self.pending_messages_cache.keys())
                _all_chat_ids_for_cutoff.update(
                    getattr(AttentionManager, "_attention_map", {}).keys()
                )
                _all_chat_ids_for_cutoff.update(
                    getattr(ProbabilityManager, "_probability_status", {}).keys()
                )
                _all_chat_ids_for_cutoff.update(
                    getattr(ProactiveChatManager, "_chat_states", {}).keys()
                )
                _all_chat_ids_for_cutoff.update(
                    ContextManager._history_cutoff_timestamps.keys()
                )
            except Exception:
                pass
            try:
                # 待转正的消息缓存（主动回复模式产生）
                pending_total = sum(
                    len(v) for v in self.pending_messages_cache.values()
                )
                self.pending_messages_cache.clear()

                logger.info(
                    "【插件重置】已清空待转存消息缓存 清理会话=%s, 清理条数=%s",
                    pending_total,
                    len(self.pending_messages_cache),
                )
            except Exception:
                logger.warning("【插件重置】清空待转存消息缓存失败", exc_info=True)
            try:
                # 会话处理中标记
                # 🔒 使用锁保护清空操作，避免与并发检测冲突
                async with self.concurrent_lock:
                    processing_count = len(self.processing_sessions)
                    self.processing_sessions.clear()

                logger.info(
                    "【插件重置】已清空处理中标记 清理会话=%s",
                    processing_count,
                )
            except Exception:
                logger.warning("【插件重置】清空处理中标记失败", exc_info=True)
            try:
                # 指令标记缓存（跨处理器通信用）
                command_count = len(self.command_messages)
                self.command_messages.clear()

                logger.info(
                    "【插件重置】已清空指令标记缓存 清理条数=%s",
                    command_count,
                )
            except Exception:
                logger.warning("【插件重置】清空指令标记缓存失败", exc_info=True)
            try:
                # 最近回复缓存（去重使用）
                replies_total = sum(len(v) for v in self.recent_replies_cache.values())
                self.recent_replies_cache.clear()
                self.raw_reply_cache.clear()
                self._pending_bot_replies.clear()
                self._agent_done_flags.clear()

                logger.info(
                    "【插件重置】已清空最近回复缓存 清理会话=%s, 清理条目=%s",
                    replies_total,
                    len(self.recent_replies_cache),
                )
            except Exception:
                logger.warning("【插件重置】清空最近回复缓存失败", exc_info=True)
            try:
                # 戳一戳追踪记录
                self.poke_trace_records = {}

                logger.info("【插件重置】已清空戳一戳追踪记录")
            except Exception:
                logger.warning("【插件重置】清空戳一戳追踪记录失败", exc_info=True)
            try:
                # 情绪追踪：清空内存态
                if hasattr(self, "mood_tracker") and hasattr(
                    self.mood_tracker, "moods"
                ):
                    mood_count = len(self.mood_tracker.moods)
                    self.mood_tracker.moods.clear()

                    logger.info(
                        "【插件重置】已清空情绪状态 清理会话=%s",
                        mood_count,
                    )
            except Exception:
                logger.warning("【插件重置】清空情绪状态失败", exc_info=True)
            try:
                # 主动对话：清空各群聊状态
                chat_state_count = len(
                    getattr(ProactiveChatManager, "_chat_states", {})
                )
                ProactiveChatManager._chat_states.clear()

                logger.info(
                    "【插件重置】已清空主动对话状态 清理会话=%s",
                    chat_state_count,
                )
            except Exception:
                logger.warning("【插件重置】清空主动对话状态失败", exc_info=True)
            try:
                # 主动对话：清空临时概率提升
                if hasattr(ProactiveChatManager, "_temp_probability_boost"):
                    temp_boost_count = len(ProactiveChatManager._temp_probability_boost)
                    ProactiveChatManager._temp_probability_boost.clear()

                    logger.info(
                        "【插件重置】已清空临时概率提升 清理会话=%s",
                        temp_boost_count,
                    )
            except Exception:
                logger.warning("【插件重置】清空临时概率提升失败", exc_info=True)
            try:
                # 🆕 v1.2.0: 清空主动对话回复用户追踪器
                if hasattr(self, "_proactive_reply_users"):
                    reply_tracking_count = len(self._proactive_reply_users)
                    self._proactive_reply_users.clear()

                    logger.info(
                        "【插件重置】已清空主动对话回复追踪 清理会话=%s",
                        reply_tracking_count,
                    )
            except Exception:
                logger.warning("【插件重置】清空主动对话回复追踪失败", exc_info=True)
            try:
                # 注意力数据：清空内存映射
                attention_count = len(getattr(AttentionManager, "_attention_map", {}))
                AttentionManager._attention_map.clear()

                logger.info(
                    "【插件重置】已清空注意力映射 清理会话=%s",
                    attention_count,
                )
            except Exception:
                logger.warning("【插件重置】清空注意力映射失败", exc_info=True)
            try:
                # 概率管理器：清空所有会话的概率状态
                probability_count = len(
                    getattr(ProbabilityManager, "_probability_status", {})
                )
                ProbabilityManager._probability_status.clear()

                logger.info(
                    "【插件重置】已清空概率状态 清理会话=%s",
                    probability_count,
                )
            except Exception:
                logger.warning("【插件重置】清空概率状态失败", exc_info=True)
            try:
                # 频率调整器：清空所有会话的检查状态
                if hasattr(self, "frequency_adjuster") and self.frequency_adjuster:
                    adjuster_count = len(self.frequency_adjuster.check_states)
                    self.frequency_adjuster.check_states.clear()

                    logger.info(
                        "【插件重置】已清空频率检查状态 清理会话=%s",
                        adjuster_count,
                    )
            except Exception:
                logger.warning("【插件重置】清空频率检查状态失败", exc_info=True)
            try:
                # 🆕 v1.2.0: 拟人增强模式：清空所有会话的状态
                if self.humanize_mode_enabled:
                    humanize_count = len(
                        getattr(HumanizeModeManager, "_chat_states", {})
                    )
                    HumanizeModeManager._chat_states.clear()

                    logger.info(
                        "【插件重置】已清空拟人增强状态 清理会话=%s",
                        humanize_count,
                    )
            except Exception:
                logger.warning("【插件重置】清空拟人增强状态失败", exc_info=True)
            try:
                # 🆕 v1.2.0: 冷却机制：清空所有会话的冷却状态 (Requirements 5.2)
                if self.cooldown_enabled:
                    cooldown_cleared = await CooldownManager.clear_all_cooldown()
                    logger.info(
                        "【插件重置】已清空冷却状态 清理用户数=%s",
                        cooldown_cleared,
                    )
            except Exception:
                logger.warning("【插件重置】清空冷却状态失败", exc_info=True)
            try:
                # 删除本插件数据目录下的持久化缓存文件/目录
                data_dir = StarTools.get_data_dir()
                base_path = Path(str(data_dir))
                # 自定义历史缓存（仅本插件使用的本地历史，非官方）
                chat_history_dir = base_path / "chat_history"
                if chat_history_dir.exists():
                    shutil.rmtree(chat_history_dir, ignore_errors=True)

                    logger.info(
                        "【插件重置】已删除自定义历史目录 path=%s",
                        chat_history_dir,
                    )
                # 注意力持久化文件
                att_file = base_path / "attention_data.json"
                if att_file.exists():
                    try:
                        att_file.unlink()

                        logger.info(
                            "【插件重置】已删除注意力持久化文件 path=%s",
                            att_file,
                        )
                    except Exception:
                        logger.warning(
                            "【插件重置】删除注意力持久化文件失败 path=%s",
                            att_file,
                            exc_info=True,
                        )
                # 主动对话状态持久化文件
                pcs_file = base_path / "proactive_chat_states.json"
                if pcs_file.exists():
                    try:
                        pcs_file.unlink()
                    except Exception:
                        pass
                # 🆕 v1.2.0: 冷却机制持久化文件 (Requirements 5.2)
                cooldown_file = base_path / "cooldown_data.json"
                if cooldown_file.exists():
                    try:
                        cooldown_file.unlink()
                        logger.info(
                            "【插件重置】已删除冷却持久化文件 path=%s",
                            cooldown_file,
                        )
                    except Exception:
                        logger.warning(
                            "【插件重置】删除冷却持久化文件失败 path=%s",
                            cooldown_file,
                            exc_info=True,
                        )
                # 🔧 修复：全局重置时，为所有已知会话设置历史截止时间戳
                # 防止平台 message_history_manager 中的旧消息被重新读入上下文
                try:
                    for cid in _all_chat_ids_for_cutoff:
                        if cid:
                            ContextManager.set_history_cutoff(cid)
                    if _all_chat_ids_for_cutoff:
                        logger.info(
                            "【插件重置】已为 %d 个会话设置历史截止时间戳",
                            len(_all_chat_ids_for_cutoff),
                        )
                except Exception:
                    logger.warning("【插件重置】设置历史截止时间戳失败", exc_info=True)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"插件重置失败: {e}", exc_info=True)

    async def _perform_initial_checks(self, event: AstrMessageEvent) -> tuple:
        """
        执行初始检查

        Returns:
            (should_continue, platform_name, is_private, chat_id)
            - should_continue: 是否继续处理
            - 其他: 基本信息
        """
        if self.debug_mode:
            logger.info("=" * 60)
            logger.info("【步骤1】开始基础检查")

        # 检查是否启用
        if not self._is_enabled(event):
            if self.debug_mode:
                logger.info("【步骤1】群组未启用插件,跳过处理")
            return False, None, None, None

        # 检查是否是机器人自己的消息
        if MessageProcessor.is_message_from_bot(event):
            if self.debug_mode:
                logger.info("忽略机器人自己的消息")
            return False, None, None, None

        # 获取基本信息
        platform_name = event.get_platform_name()
        is_private = event.is_private_chat()
        chat_id = event.get_group_id() if not is_private else event.get_sender_id()

        if self.debug_mode:
            logger.info(f"【步骤1】基础信息:")
            logger.info(f"  平台: {platform_name}")
            logger.info(f"  类型: {'私聊' if is_private else '群聊'}")
            logger.info(f"  会话ID: {chat_id}")
            logger.info(f"  发送者: {event.get_sender_name()}({event.get_sender_id()})")

        # 黑名单关键词检查
        if self.debug_mode:
            logger.info("【步骤2】检查黑名单关键词")

        blacklist_keywords = self.blacklist_keywords
        if KeywordChecker.check_blacklist_keywords(event, blacklist_keywords):
            if self.debug_mode:
                logger.info("【步骤2】黑名单关键词匹配，丢弃消息")
                logger.info("=" * 60)
            return False, None, None, None

        return True, platform_name, is_private, chat_id

    async def _check_message_triggers(self, event: AstrMessageEvent) -> tuple:
        """
        检查消息触发器（@消息和触发关键词）

        Returns:
            (is_at_message, has_trigger_keyword, matched_trigger_keyword)
            🆕 v1.2.0: 新增返回匹配到的触发关键词
        """
        # 判断是否是@消息
        is_at_message = MessageProcessor.is_at_message(event)

        # 只在debug模式或是@消息时记录
        if self.debug_mode:
            logger.info(
                f"【步骤3】@消息检测: {'是@消息' if is_at_message else '非@消息'}"
            )

        # 触发关键词检查
        if self.debug_mode:
            logger.info("【步骤4】检查触发关键词")

        trigger_keywords = self.trigger_keywords
        # 🆕 v1.2.0: 使用新方法获取匹配到的关键词
        has_trigger_keyword, matched_trigger_keyword = (
            KeywordChecker.check_trigger_keywords_with_match(event, trigger_keywords)
        )

        # 只在检测到关键词时记录
        if has_trigger_keyword:
            if self.debug_mode:
                logger.info(
                    f"【步骤4】检测到触发关键词: {matched_trigger_keyword}，跳过读空气判断"
                )

        return is_at_message, has_trigger_keyword, matched_trigger_keyword

    async def _check_probability_before_processing(
        self,
        event: AstrMessageEvent,
        platform_name: str,
        is_private: bool,
        chat_id: str,
        is_at_message: bool,
        has_trigger_keyword: bool,
        poke_info: dict = None,
        is_emoji_message: bool = False,
    ) -> bool:
        """
        执行概率判断（在图片处理之前）

        Args:
            event: 消息事件对象
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            is_at_message: 是否@消息
            has_trigger_keyword: 是否包含触发关键词
            poke_info: 戳一戳信息（v1.0.9新增）
            is_emoji_message: 是否为表情包消息（v1.2.0新增）

        Returns:
            True=继续处理, False=丢弃消息
        """
        # 🆕 v1.2.0: 拟人增强模式 - 动态消息阈值检查
        if self.humanize_mode_enabled:
            try:
                chat_key = ProbabilityManager.get_chat_key(
                    platform_name, is_private, chat_id
                )
                # 先增加消息计数
                await HumanizeModeManager.increment_message_count(chat_key)
                # 检查是否应该跳过（基于动态阈值）
                (
                    should_skip,
                    skip_reason,
                    count,
                ) = await HumanizeModeManager.should_skip_for_dynamic_threshold(
                    chat_key=chat_key,
                    is_mentioned=is_at_message or has_trigger_keyword,
                )
                if should_skip:
                    if self.debug_mode:
                        logger.info(
                            f"【步骤5】🎭 拟人增强: 动态阈值未达到，跳过本次判断 ({skip_reason})"
                        )
                    return False
            except Exception as e:
                if self.debug_mode:
                    logger.warning(
                        f"【步骤5】🎭 拟人增强: 动态阈值检查失败，继续正常处理: {e}"
                    )

        # 检查是否应该跳过概率判断（戳机器人的特殊处理）
        skip_probability_for_poke = False
        if poke_info and self.poke_bot_skip_probability:
            # 如果是戳机器人，且开关打开
            # poke_info现在是完整的poke_result结构，需要从内嵌的poke_info中获取is_poke_bot
            inner_poke_info = poke_info.get("poke_info", {})
            if inner_poke_info.get("is_poke_bot"):
                skip_probability_for_poke = True
                if self.debug_mode:
                    logger.info(
                        "【步骤5】戳机器人消息，戳的是机器人，配置允许跳过概率判断。跳过概率筛选，保留读空气判断"
                    )

        # 🆕 检查是否应该跳过概率判断（新成员入群消息的特殊处理）
        skip_probability_for_welcome = False
        is_welcome_message = (
            event.get_extra("is_welcome_message")
            if hasattr(event, "get_extra")
            else False
        )
        welcome_mode = (
            event.get_extra("welcome_message_mode")
            if hasattr(event, "get_extra")
            else "normal"
        )
        if is_welcome_message and welcome_mode in ("skip_probability", "skip_all"):
            skip_probability_for_welcome = True
            if self.debug_mode:
                logger.info(
                    f"【步骤5】新成员入群消息，模式={welcome_mode}，跳过概率筛选"
                )

        # @消息、触发关键词消息、符合条件的戳一戳消息、或入群消息跳过概率判断
        # v1.1.2: 关键词智能模式下，关键词也会跳过概率判断
        if (
            not is_at_message
            and not has_trigger_keyword
            and not skip_probability_for_poke
            and not skip_probability_for_welcome
        ):
            # 概率判断
            if self.debug_mode:
                logger.info("【步骤5】开始读空气概率判断")

            should_process = await self._check_probability(
                platform_name,
                is_private,
                chat_id,
                event,
                poke_info=poke_info,
                is_emoji_message=is_emoji_message,
            )
            if not should_process:
                if self.debug_mode:
                    logger.info("【步骤5】概率判断失败,丢弃消息")
                    logger.info("=" * 60)
                return False

            logger.info("读空气概率判断: 决定处理此消息")
            if self.debug_mode:
                logger.info("【步骤5】概率判断通过,继续处理")
        else:
            # @消息或触发关键词，跳过概率判断
            if is_at_message:
                if self.debug_mode:
                    logger.info("【步骤5】@消息,跳过概率判断,必定处理")

            if has_trigger_keyword:
                if self.debug_mode:
                    # v1.1.2: 根据智能模式显示不同的日志
                    keyword_smart_mode = self.keyword_smart_mode
                    if keyword_smart_mode:
                        logger.info(
                            "【步骤5】触发关键词消息(智能模式),跳过概率判断,但保留读空气判断"
                        )
                    else:
                        logger.info("【步骤5】触发关键词消息,跳过概率判断,必定处理")

            if skip_probability_for_poke:
                if self.debug_mode:
                    logger.info("【步骤5】戳机器人消息,跳过概率判断,必定处理")

            if skip_probability_for_welcome:
                if self.debug_mode:
                    logger.info(
                        f"【步骤5】新成员入群消息,跳过概率判断,模式={welcome_mode}"
                    )

        return True

    async def _check_ai_decision(
        self,
        event: AstrMessageEvent,
        formatted_context: str,
        is_at_message: bool,
        has_trigger_keyword: bool,
        image_urls: Optional[List[str]] = None,
        matched_trigger_keyword: str = "",  # 🆕 v1.2.0: 匹配到的触发关键词
        original_message_text: str = "",  # 🆕 v1.2.0: 原始消息文本（用于关键词检测）
    ) -> bool:
        """
        执行AI决策判断（在处理完消息内容后）

        Returns:
            True=应该回复, False=不回复
        """
        # v1.1.2: 检查关键词智能模式（使用已提取的实例变量）
        keyword_smart_mode = self.keyword_smart_mode

        # 获取会话信息
        platform_name = event.get_platform_name()
        is_private = event.is_private_chat()
        chat_id = event.get_group_id() if not is_private else event.get_sender_id()

        # 🆕 v1.2.0: 检查是否为主动对话后的回复（在临时提升期内）
        is_proactive_reply = False
        if self.proactive_enabled:
            chat_key = ProbabilityManager.get_chat_key(
                platform_name, is_private, chat_id
            )
            state = ProactiveChatManager.get_chat_state(chat_key)
            proactive_active = state.get("proactive_active", False)
            last_proactive_time = state.get("last_proactive_time", 0)
            current_time = time.time()
            boost_duration = self.proactive_temp_boost_duration
            in_boost_period = (current_time - last_proactive_time) <= boost_duration

            # 如果主动对话活跃且在提升期内，标记为主动对话回复
            is_proactive_reply = proactive_active and in_boost_period

            if is_proactive_reply and self.debug_mode:
                logger.info(
                    f"[决策AI] 检测到主动对话回复（提升期剩余 "
                    f"{int(boost_duration - (current_time - last_proactive_time))}秒），"
                    f"将提示AI优先回复"
                )

        # 在读空气AI之前注入记忆（可选）
        decision_formatted_context = formatted_context
        if (
            self.enable_memory_injection
            and self.memory_insertion_timing == "pre_decision"
        ):
            memory_mode = self.memory_plugin_mode
            livingmemory_top_k = self.livingmemory_top_k
            livingmemory_version = self.livingmemory_version

            if MemoryInjector.check_memory_plugin_available(
                self.context, mode=memory_mode, version=livingmemory_version
            ):
                try:
                    memories = await MemoryInjector.get_memories(
                        self.context,
                        event,
                        mode=memory_mode,
                        top_k=livingmemory_top_k,
                        version=livingmemory_version,
                    )
                    mem_text = str(memories).strip() if memories is not None else ""
                    if mem_text and ("当前没有任何记忆" not in mem_text):
                        old_len = len(decision_formatted_context)
                        decision_formatted_context = (
                            MemoryInjector.inject_memories_to_message(
                                decision_formatted_context, mem_text
                            )
                        )
                        if self.debug_mode:
                            logger.info(
                                f"[决策AI] 已在判定前注入记忆({memory_mode}模式)，长度增加: {len(decision_formatted_context) - old_len} 字符"
                            )
                        try:
                            ckey = ProbabilityManager.get_chat_key(
                                platform_name, is_private, chat_id
                            )
                            if not hasattr(self, "_pre_decision_context_by_chat"):
                                self._pre_decision_context_by_chat = {}
                            self._pre_decision_context_by_chat[ckey] = (
                                decision_formatted_context
                            )
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"[决策AI] 判定前注入记忆失败: {e}", exc_info=True)
            elif self.debug_mode:
                logger.info(
                    f"[决策AI] 记忆插件({memory_mode}模式)不可用，判定前跳过记忆注入"
                )

        # 判断是否需要进行AI决策
        # @消息必定跳过AI决策
        # 触发关键词：智能模式下需要AI决策，非智能模式跳过AI决策
        should_do_ai_decision = not is_at_message and (
            not has_trigger_keyword or keyword_smart_mode
        )

        # 🆕 v1.2.0: 初始化对话疲劳信息（在决策块外部初始化，确保后续可用）
        conversation_fatigue_info = None

        # 🆕 v1.2.0: 拟人增强模式 - 静默模式检查
        chat_key = ProbabilityManager.get_chat_key(platform_name, is_private, chat_id)
        if should_do_ai_decision and self.humanize_mode_enabled:
            try:
                # 检查是否应该跳过AI决策（静默模式）
                # 🔧 v1.2.0: 使用原始消息文本进行关键词检测，而不是格式化后的上下文
                message_text_for_keyword = (
                    original_message_text
                    if original_message_text
                    else formatted_context
                )
                (
                    should_skip,
                    skip_reason,
                ) = await HumanizeModeManager.should_skip_ai_decision(
                    chat_key=chat_key,
                    is_mentioned=is_at_message or has_trigger_keyword,
                    message_text=message_text_for_keyword,
                )

                if should_skip:
                    if self.debug_mode:
                        logger.info(
                            f"【步骤9】🎭 拟人增强: 跳过AI决策 (原因: {skip_reason})"
                        )
                    return False
            except Exception as e:
                logger.warning(f"[拟人增强] 静默模式检查失败，继续正常处理: {e}")

        if should_do_ai_decision:
            # 🆕 v1.2.0: 拟人增强模式 - 注入历史决策记录
            if self.humanize_mode_enabled:
                try:
                    decision_history_prompt = (
                        await HumanizeModeManager.build_decision_history_prompt(
                            chat_key
                        )
                    )
                    if decision_history_prompt:
                        decision_formatted_context = (
                            decision_formatted_context + decision_history_prompt
                        )
                        if self.debug_mode:
                            logger.info("【步骤9】🎭 已注入历史决策记录到提示词")

                    # 🆕 检测兴趣话题并记录日志（实际概率调整已在 _check_probability 中完成）
                    # 🔧 v1.2.0: 使用原始消息文本进行关键词检测
                    (
                        is_interest_match,
                        matched_keyword,
                    ) = await HumanizeModeManager.check_interest_match(
                        message_text_for_keyword
                        if "message_text_for_keyword" in locals()
                        else (
                            original_message_text
                            if original_message_text
                            else formatted_context
                        )
                    )
                    if is_interest_match and self.debug_mode:
                        logger.info(f"【步骤9】🎭 检测到兴趣话题: {matched_keyword}")
                except Exception as e:
                    logger.warning(f"[拟人增强] 历史决策注入失败，继续正常处理: {e}")

            # 决策AI判断
            if self.debug_mode:
                logger.info("【步骤9】调用决策AI判断是否回复")

            _decision_start = time.time()

            # 🆕 v1.2.0: 获取增强上下文信息
            # 获取兴趣话题关键词
            interest_keywords = []
            if self.humanize_mode_enabled:
                interest_keywords = self.humanize_interest_keywords

            # 获取动态时间段配置信息
            time_period_info = None
            if self.enable_dynamic_reply_probability:
                try:
                    from .utils.time_period_manager import TimePeriodManager
                    from datetime import datetime as dt

                    periods = TimePeriodManager.parse_time_periods(
                        self.reply_time_periods, silent=True
                    )

                    if periods:
                        # 计算当前时间系数
                        current_factor = TimePeriodManager.calculate_time_factor(
                            current_time=None,  # 使用当前时间
                            periods_config=periods,
                            transition_minutes=self.reply_time_transition_minutes,
                            min_factor=self.reply_time_min_factor,
                            max_factor=self.reply_time_max_factor,
                            use_smooth_curve=self.reply_time_use_smooth_curve,
                        )

                        # 查找当前匹配的时间段名称
                        current_period_name = ""
                        now = dt.now()
                        current_minutes = now.hour * 60 + now.minute
                        for period in periods:
                            try:
                                start_parts = period["start"].split(":")
                                end_parts = period["end"].split(":")
                                start_minutes = int(start_parts[0]) * 60 + int(
                                    start_parts[1] if len(start_parts) > 1 else 0
                                )
                                end_minutes = int(end_parts[0]) * 60 + int(
                                    end_parts[1] if len(end_parts) > 1 else 0
                                )

                                # 判断是否在时间段内（支持跨天）
                                if start_minutes > end_minutes:
                                    in_period = (
                                        current_minutes >= start_minutes
                                        or current_minutes < end_minutes
                                    )
                                else:
                                    in_period = (
                                        start_minutes <= current_minutes < end_minutes
                                    )

                                if in_period:
                                    current_period_name = period.get(
                                        "name", f"{period['start']}-{period['end']}"
                                    )
                                    break
                            except:
                                continue

                        time_period_info = {
                            "enabled": True,
                            "current_factor": current_factor,
                            "current_period_name": current_period_name or "默认时段",
                        }
                except Exception as e:
                    if self.debug_mode:
                        logger.warning(f"[决策AI] 获取时间段配置失败: {e}")

            # 判断是否通过关键词触发（智能模式下）
            is_keyword_triggered = has_trigger_keyword and keyword_smart_mode

            # 🆕 获取对话疲劳信息
            conversation_fatigue_info = None
            if self.enable_conversation_fatigue and self.enable_attention_mechanism:
                try:
                    user_id = event.get_sender_id()
                    conversation_fatigue_info = (
                        await AttentionManager.get_conversation_fatigue_info(
                            platform_name, is_private, chat_id, user_id
                        )
                    )
                    if (
                        self.debug_mode
                        and conversation_fatigue_info.get("consecutive_replies", 0) > 0
                    ):
                        logger.info(
                            f"[对话疲劳] 用户连续对话轮次: {conversation_fatigue_info.get('consecutive_replies', 0)}, "
                            f"疲劳等级: {conversation_fatigue_info.get('fatigue_level', 'none')}"
                        )
                except Exception as e:
                    if self.debug_mode:
                        logger.warning(f"[对话疲劳] 获取疲劳信息失败: {e}")

            # 🆕 v1.2.1: 获取回复密度提示文本
            reply_density_hint = ""
            if self.enable_reply_density_limit and self.reply_density_ai_hint:
                try:
                    density_chat_key = ProbabilityManager.get_chat_key(
                        platform_name, is_private, chat_id
                    )
                    reply_density_hint = await ReplyDensityManager.get_ai_hint_text(
                        density_chat_key
                    )
                except Exception as e:
                    if self.debug_mode:
                        logger.warning(f"[回复密度] 获取AI提示失败: {e}")

            should_reply = await DecisionAI.should_reply(
                self.context,
                event,
                decision_formatted_context,
                self.decision_ai_provider_id,
                self.decision_ai_extra_prompt,
                self.decision_ai_timeout,
                self.decision_ai_prompt_mode,
                image_urls=image_urls,
                is_proactive_reply=is_proactive_reply,
                config=self.config,
                include_sender_info=self.include_sender_info,
                # 🆕 v1.2.0: 新增参数
                is_keyword_triggered=is_keyword_triggered,
                matched_keyword=matched_trigger_keyword,
                interest_keywords=interest_keywords,
                time_period_info=time_period_info,
                humanize_mode_enabled=self.humanize_mode_enabled,
                # 🆕 v1.2.0: 传递原始消息文本用于关键词检测
                original_message_text=original_message_text,
                # 🆕 v1.2.0: 传递对话疲劳信息
                conversation_fatigue_info=conversation_fatigue_info,
                # 🆕 v1.2.1: 传递回复密度提示
                reply_density_hint=reply_density_hint,
            )
            # 🐛 修复：不要在这里删除缓存！
            # pre_decision 模式下，缓存的上下文（已植入记忆）需要在生成回复时使用
            # 缓存会在 _generate_and_send_reply 中使用 .pop() 时自动删除
            # 如果在这里删除，会导致最终回复AI看不到提前植入的记忆

            if self.debug_mode:
                _decision_elapsed = time.time() - _decision_start
                logger.info(f"【步骤9】决策AI判断完成，耗时: {_decision_elapsed:.2f}秒")

            if not should_reply:
                logger.info("决策AI判断: 不应该回复此消息")

                decision_ai_error = False
                try:
                    decision_ai_error = bool(
                        getattr(event, "_decision_ai_error", False)
                    )
                except Exception:
                    decision_ai_error = False

                if decision_ai_error:
                    logger.warning(
                        "[决策AI] 本次判断因AI调用失败而返回不回复，跳过拟人统计和注意力衰减"
                    )
                else:
                    # 🆕 v1.2.0: 拟人增强模式 - 记录决策结果
                    if self.humanize_mode_enabled:
                        try:
                            message_preview = (
                                formatted_context[:50] if formatted_context else ""
                            )
                            await HumanizeModeManager.record_decision(
                                chat_key=chat_key,
                                decision=False,
                                reason="AI判断不需要回复",
                                message_preview=message_preview,
                            )
                        except Exception as e:
                            logger.warning(f"[拟人增强] 记录决策失败: {e}")

                    # 🆕 注意力衰减：如果注意力机制启用且对该用户注意力较高，进行衰减
                    if self.enable_attention_mechanism:
                        try:
                            user_id = event.get_sender_id()
                            user_name = event.get_sender_name() or "未知用户"

                            # 调用注意力衰减方法
                            await AttentionManager.decrease_attention_on_no_reply(
                                platform_name,
                                is_private,
                                chat_id,
                                user_id,
                                user_name,
                                attention_decrease_step=self.attention_decrease_on_no_reply_step,
                                min_attention_threshold=self.attention_decrease_threshold,
                            )
                        except Exception as e:
                            logger.warning(f"[注意力衰减] 执行失败: {e}", exc_info=True)

                # 🔧 清理pre_decision缓存（防止内存残留）
                try:
                    ckey = ProbabilityManager.get_chat_key(
                        platform_name, is_private, chat_id
                    )
                    if (
                        hasattr(self, "_pre_decision_context_by_chat")
                        and ckey in self._pre_decision_context_by_chat
                    ):
                        del self._pre_decision_context_by_chat[ckey]
                        if self.debug_mode:
                            logger.info("  已清理pre_decision缓存（决策判定不回复）")
                except Exception:
                    pass
                return False

            logger.info("决策AI判断: 应该回复此消息")

            # 🆕 v1.2.0: 拟人增强模式 - 记录决策结果
            if self.humanize_mode_enabled:
                try:
                    message_preview = (
                        formatted_context[:50] if formatted_context else ""
                    )
                    await HumanizeModeManager.record_decision(
                        chat_key=chat_key,
                        decision=True,
                        reason="AI判断应该回复",
                        message_preview=message_preview,
                    )
                except Exception as e:
                    logger.warning(f"[拟人增强] 记录决策失败: {e}")

            return True
        else:
            # @消息或触发关键词(非智能模式)，必定回复
            # 注意：疲劳轮次重置移到AI实际回复后执行，避免在这里提前重置

            # 🆕 v1.2.0: 获取对话疲劳信息（即使跳过AI决策，回复AI也需要疲劳信息）
            if self.enable_conversation_fatigue and self.enable_attention_mechanism:
                try:
                    user_id = event.get_sender_id()
                    conversation_fatigue_info = (
                        await AttentionManager.get_conversation_fatigue_info(
                            platform_name, is_private, chat_id, user_id
                        )
                    )
                    if (
                        self.debug_mode
                        and conversation_fatigue_info.get("consecutive_replies", 0) > 0
                    ):
                        logger.info(
                            f"[对话疲劳] 用户连续对话轮次: {conversation_fatigue_info.get('consecutive_replies', 0)}, "
                            f"疲劳等级: {conversation_fatigue_info.get('fatigue_level', 'none')}"
                        )
                except Exception as e:
                    if self.debug_mode:
                        logger.warning(f"[对话疲劳] 获取疲劳信息失败: {e}")

            # 🆕 v1.2.0: 拟人增强模式 - 被@或触发关键词时也记录决策（作为回复）
            if self.humanize_mode_enabled:
                try:
                    message_preview = (
                        formatted_context[:50] if formatted_context else ""
                    )
                    await HumanizeModeManager.record_decision(
                        chat_key=chat_key,
                        decision=True,
                        reason="被@或触发关键词，必定回复",
                        message_preview=message_preview,
                    )
                except Exception as e:
                    logger.warning(f"[拟人增强] 记录决策失败: {e}")
            if self.debug_mode:
                if is_at_message:
                    logger.info("【步骤9】@消息,跳过AI决策,必定回复")
                elif has_trigger_keyword and not keyword_smart_mode:
                    logger.info("【步骤9】触发关键词(非智能模式),跳过AI决策,必定回复")
            try:
                ckey = ProbabilityManager.get_chat_key(
                    platform_name, is_private, chat_id
                )
                if not hasattr(self, "_ai_decision_skipped"):
                    self._ai_decision_skipped = set()
                self._ai_decision_skipped.add(ckey)
            except Exception:
                pass
            return True

    async def _process_message_content(
        self,
        event: AstrMessageEvent,
        chat_id: str,
        is_at_message: bool,
        mention_info: dict = None,
        has_trigger_keyword: bool = False,
        poke_info: dict = None,
        raw_is_at_message: bool = None,
        is_emoji_message: bool = False,
    ) -> tuple:
        """
        处理消息内容（图片处理、上下文格式化）

        Args:
            event: 消息事件对象
            chat_id: 聊天ID
            is_at_message: 是否为@消息
            mention_info: @别人的信息字典（如果存在）
            has_trigger_keyword: 是否包含触发关键词
            poke_info: 戳一戳信息（如果存在）

        Returns:
            (should_continue, original_message_text, processed_message, formatted_context, image_urls, history_messages, cached_message)
            - should_continue: 是否继续处理
            - original_message_text: 纯净的原始消息（不含元数据）
            - processed_message: 处理后的消息（图片已处理，不含元数据，用于保存）
            - formatted_context: 格式化后的完整上下文（历史消息+当前消息，当前消息已添加元数据）
            - image_urls: 图片URL列表（用于多模态AI）
            - history_messages: 历史消息列表
            - cached_message: 待缓存的消息数据（由调用方决定是否缓存）
        """
        # 提取纯净原始消息
        if self.debug_mode:
            logger.info("【步骤6】提取纯净原始消息")

        # 使用MessageCleaner提取纯净的原始消息（不含系统提示词）
        original_message_text = MessageCleaner.extract_raw_message_from_event(event)
        if self.debug_mode:
            logger.info(f"  纯净原始消息: {original_message_text[:100]}...")

        real_is_at_message = (
            raw_is_at_message if raw_is_at_message is not None else is_at_message
        )

        # 检查是否是空@消息
        is_empty_at = MessageCleaner.is_empty_at_message(
            original_message_text, real_is_at_message
        )
        if is_empty_at:
            if self.debug_mode:
                logger.info("  纯@消息将使用特殊处理")

        # 处理图片（在缓存之前）
        # 这样如果图片被过滤，消息就不会被缓存
        if self.debug_mode:
            logger.info("【步骤6.5】处理图片内容")

        (
            should_continue,
            processed_message,
            image_urls,
            image_retained,  # 🆕 v1.2.0: 图片是否保留（用于判断是否添加表情包标记）
        ) = await ImageHandler.process_message_images(
            event,
            self.context,
            self.enable_image_processing,
            self.image_to_text_scope,
            self.image_to_text_provider_id,
            self.image_to_text_prompt,
            real_is_at_message,
            has_trigger_keyword,
            self.image_to_text_timeout,
            self.image_description_cache,  # 🆕 v1.2.0: 传递图片描述缓存
            self.max_images_per_message,  # 单条消息最大处理图片数
        )

        if not should_continue:
            logger.info("图片处理后决定丢弃此消息（图片被过滤或处理失败）")
            if self.debug_mode:
                logger.info("【步骤6.5】图片处理判定丢弃消息，不缓存")
                logger.info("=" * 60)
            return False, None, None, None, None, None, None, False

        # 🆕 v1.2.0: 表情包标记注入（正常处理路径）
        # 只有当表情包图片信息确实保留在消息中时（作为URL或文字描述）才添加标记
        # 避免图片已被过滤/移除后仍添加标记导致AI混乱
        emoji_marker_applied = False
        if is_emoji_message and self.enable_emoji_filter and image_retained:
            if processed_message:
                processed_message = EmojiDetector.add_emoji_marker(processed_message)
            else:
                # 纯表情包（无文字）的多模态情况：图片URL已提取，但文本为空
                # 仍需添加标记让AI知道这是表情包
                processed_message = EmojiDetector.add_emoji_marker("")
            emoji_marker_applied = True
            if self.debug_mode:
                logger.info(
                    f"【步骤6.6】🎭 已为表情包消息添加标记: {processed_message[:100]}..."
                )
        elif is_emoji_message and self.enable_emoji_filter and not image_retained:
            if self.debug_mode:
                logger.info("【步骤6.6】🎭 表情包图片已被过滤/移除，跳过添加标记")

        # 缓存当前用户消息（图片处理通过后再缓存）
        # 注意：缓存处理后的消息（不含元数据），在保存时再添加元数据
        # processed_message 已经是经过图片处理的最终结果（可能是过滤后、转文字后、或原始消息）
        # 🆕 v1.2.0: 不再在此处直接缓存，而是准备缓存数据返回给调用方
        if self.debug_mode:
            logger.info(
                "【步骤7】准备待缓存的用户消息数据（不含元数据，由调用方决定是否缓存）"
            )
            logger.info(f"  原始消息（提取自event）: {original_message_text[:200]}...")
            logger.info(f"  处理后消息（图片处理后）: {processed_message[:200]}...")

        # 🆕 v1.0.4: 确定触发方式（用于后续添加系统提示）
        # 根据is_at_message和has_trigger_keyword判断触发方式
        # 注意：在这个阶段还不知道是否会AI主动回复，所以先不设置trigger_type
        # 会在后续添加元数据时根据实际情况设置

        # 缓存处理后的消息内容，不包含元数据
        # 保存发送者信息和时间戳，用于后续添加元数据

        # 🔧 修复并发问题：在缓存中保存 message_id，用于在保存时排除正在处理中的消息
        current_message_id = self._get_message_id(event)

        # 🆕 v1.2.0: 使用缓存管理器统一处理缓存
        cached_message = {
            "role": "user",
            "content": processed_message,  # 处理后的消息（可能已过滤图片、转文字、或保留原样）
            "timestamp": time.time(),
            "message_id": current_message_id,
            # 保存发送者信息，用于转正时添加正确的元数据
            "sender_id": event.get_sender_id(),
            "sender_name": event.get_sender_name(),
            "message_timestamp": event.message_obj.timestamp
            if hasattr(event, "message_obj") and hasattr(event.message_obj, "timestamp")
            else None,
            # 保存@别人的信息（如果存在）
            "mention_info": mention_info,
            # 🆕 v1.0.4: 保存触发方式信息（用于后续添加系统提示）
            "is_at_message": is_at_message,
            "has_trigger_keyword": has_trigger_keyword,
            # 🆕 v1.0.9: 保存戳一戳信息（如果存在）
            "poke_info": poke_info,
            "image_urls": image_urls or [],
            # 🔧 修复：保存空@标记，用于生成正确的系统提示词
            "is_empty_at": is_empty_at,
        }

        # 缓存内容日志
        if not original_message_text and not processed_message:
            if self.debug_mode:
                logger.info(
                    "⚠️ [缓存准备] 原始和处理后消息均为空（可能是纯图片/表情/戳一戳等）"
                )
        elif not original_message_text and self.debug_mode:
            logger.info(
                "⚠️ [缓存准备] 原始消息为空（但处理后消息存在，可能是图片转文字）"
            )
        elif not processed_message and self.debug_mode:
            logger.info(
                "⚠️ [缓存准备] 处理后消息为空（但原始消息存在，可能是图片被过滤）"
            )

        # 🔧 v1.2.0: 不再在此处直接缓存消息
        # 缓存逻辑移至 _process_message 中，根据消息是否需要被正常处理来决定是否缓存：
        # - 跳过概率筛选且跳过AI决策的消息（@消息、非智能模式的关键词）→ 不缓存
        # - AI决策不通过的消息 → 缓存
        # - AI决策通过的消息 → 不缓存
        # cached_message 数据将通过返回值传递给调用方

        # 详细日志（仅debug模式）
        if self.debug_mode:
            logger.info(
                f"【缓存准备】原始: {original_message_text[:100] if original_message_text else '(空)'}"
            )
            logger.info(
                f"【缓存准备】处理后: {processed_message[:100] if processed_message else '(空)'}"
            )
            logger.info(
                f"【缓存准备】待缓存数据: {cached_message['content'][:100] if cached_message['content'] else '(空)'}"
            )
            if processed_message != original_message_text:
                logger.info(f"  ⚠️ 消息内容有变化！原始≠处理后")
            else:
                logger.info(f"  消息内容无变化（原始==处理后）")

        # 为当前消息添加元数据（用于发送给AI）
        # 使用处理后的消息（可能包含图片描述），添加统一格式的元数据
        # 🆕 v1.0.4: 确定触发方式
        # 注意：is_at_message 参数可能是 should_treat_as_at（即 is_at_message or has_trigger_keyword）
        # 所以需要同时检查 has_trigger_keyword 参数来正确判断触发方式
        trigger_type = None
        if has_trigger_keyword:
            # 关键词触发（优先级高于@消息判断，因为is_at_message可能是should_treat_as_at）
            trigger_type = "keyword"
        elif is_at_message:
            # 真正的@消息触发
            trigger_type = "at"
        else:
            # 概率触发（AI主动回复）
            # 注意：虽然此时决策AI还没判断，但如果能走到这里说明概率判断已通过
            # 无论决策AI判断yes/no，这个trigger_type都是正确的：
            # - 判断yes：确实是AI主动回复，提示词"你打算回复他"正确
            # - 判断no：消息只会保存不会发给回复AI，提示词在保存时也正确
            trigger_type = "ai_decision"

        # 🆕 空@时：提取最近缓存消息摘要，直接嵌入提示词，让AI无需在长历史中搜索
        # ⏱️ 时间差阈值：超过此时间（秒）则认为间隔过久，不拼接上下文，让AI自然询问
        EMPTY_AT_MAX_TIME_GAP = 600  # 10分钟
        recent_pending_summary = ""
        if is_empty_at and chat_id in self.pending_messages_cache:
            cache_list = self.pending_messages_cache[chat_id]
            if cache_list:
                # 过滤掉窗口缓冲消息（window_buffered=True），避免与 window_buffered_messages
                # 区域重复展示；窗口消息会在当前消息下方单独展示，无需在摘要中再出现
                non_window_cache = [
                    m for m in cache_list if not m.get("window_buffered", False)
                ]
                # 最多取最近3条非空缓存消息
                recent_cached = non_window_cache[-3:]

                # 检查最近缓存消息与当前消息的时间差
                current_ts = time.time()
                latest_cache_ts = None
                for msg in reversed(recent_cached):
                    if isinstance(msg, dict):
                        ts = msg.get("timestamp") or msg.get("message_timestamp")
                        if ts:
                            try:
                                latest_cache_ts = float(ts)
                                break
                            except (TypeError, ValueError):
                                pass

                # 时间差检查：超过阈值则不拼接上下文，让AI自然询问
                time_gap_ok = True
                if latest_cache_ts is not None:
                    time_gap = current_ts - latest_cache_ts
                    time_gap_ok = time_gap <= EMPTY_AT_MAX_TIME_GAP
                    if not time_gap_ok and self.debug_mode:
                        logger.info(
                            f"  ⏱️ 空@与最近缓存消息时间差 {time_gap:.0f}s > {EMPTY_AT_MAX_TIME_GAP}s，"
                            f"不拼接上下文，AI将自然询问"
                        )

                if time_gap_ok:
                    parts = []
                    for msg in recent_cached:
                        if isinstance(msg, dict):
                            content = msg.get("content", "").strip()
                            sender_name = (
                                msg.get("sender_name")
                                or f"用户(ID:{msg.get('sender_id', '?')})"
                            )
                            if content:
                                parts.append(f"  - {sender_name}：{content[:150]}")
                    if parts:
                        recent_pending_summary = "\n".join(parts)

        message_text_for_ai = MessageProcessor.add_metadata_to_message(
            event,
            processed_message,  # 使用处理后的消息（图片已处理）
            self.include_timestamp,
            self.include_sender_info,
            mention_info,  # 传递@信息
            trigger_type,  # 🆕 v1.0.4: 传递触发方式
            poke_info,  # 🆕 v1.0.9: 传递戳一戳信息
            is_empty_at,  # 🔧 修复：传递空@标记，让AI区分空艾特和带消息艾特
            recent_pending_summary,  # 🆕 空@时：近期缓存消息摘要，直接嵌入提示词
        )

        # 🆕 戳过对方追踪提示（需要同时满足：功能启用 + 群聊在白名单中 + 有追踪记录）
        if (
            self.poke_trace_enabled
            and self._is_poke_enabled_in_group(chat_id)
            and self._check_and_consume_poke_trace(chat_id, event.get_sender_id())
        ):
            _n = event.get_sender_name() or "未知用户"
            _id = event.get_sender_id()
            message_text_for_ai += (
                f"\n[戳过对方提示]你刚刚戳过这条消息的发送者{_n}(ID:{_id})"
            )
            if self.debug_mode:
                logger.info(f"  已添加戳过对方提示: 目标={_n}(ID:{_id})")

        if self.debug_mode:
            logger.info("【步骤7.5】为当前消息添加元数据（用于AI识别）")
            logger.info(f"  处理后消息: {processed_message[:100]}...")
            logger.info(f"  添加元数据后: {message_text_for_ai[:150]}...")

        # 提取历史上下文
        max_context = self.max_context_messages

        # 🔧 配置矫正：处理类型和异常值
        # 1. 首先确保是整数类型（配置文件可能传入字符串）
        if not isinstance(max_context, int):
            try:
                max_context = int(max_context)
                if self.debug_mode:
                    logger.info(
                        f"[配置矫正] max_context_messages 从 {type(self.max_context_messages).__name__} 转换为 int: {max_context}"
                    )
            except (ValueError, TypeError):
                logger.warning(
                    f"⚠️ [配置矫正] max_context_messages 配置值 '{self.max_context_messages}' 无法转换为整数，已矫正为 -1（不限制）"
                )
                max_context = -1

        # 2. 处理异常值（小于 -1 的情况）
        if isinstance(max_context, int) and max_context < -1:
            logger.warning(
                f"⚠️ [配置矫正] max_context_messages 配置值 {max_context} 小于 -1，已矫正为 -1（不限制）"
            )
            max_context = -1

        if self.debug_mode:
            logger.info("【步骤8】提取历史上下文")
            context_limit_desc = (
                "不限制"
                if max_context == -1
                else "不获取历史"
                if max_context == 0
                else f"限制为 {max_context} 条"
            )
            logger.info(f"  最大上下文数: {max_context} ({context_limit_desc})")

            def _log_msgs(tag, msgs):
                try:
                    cnt = len(msgs) if msgs else 0
                    logger.info(f"  {tag} 条数: {cnt}")
                    if not msgs:
                        return
                    # 展示末尾最多5条的详细信息
                    bot_id_for_check = str(event.get_self_id())
                    show = msgs[-min(5, len(msgs)) :]
                    lines = []
                    for idx, m in enumerate(show, start=cnt - len(show) + 1):
                        try:
                            # 提取通用字段
                            t = None
                            sid = ""
                            sname = ""
                            mid = ""
                            gid = None
                            selfid = ""
                            sess = ""
                            content = ""
                            if isinstance(m, AstrBotMessage):
                                t = getattr(m, "timestamp", None)
                                if hasattr(m, "sender") and m.sender:
                                    sid = str(getattr(m.sender, "user_id", ""))
                                    sname = getattr(m.sender, "nickname", "") or ""
                                mid = getattr(m, "message_id", "") or ""
                                gid = getattr(m, "group_id", None)
                                selfid = str(getattr(m, "self_id", "") or "")
                                sess = str(getattr(m, "session_id", "") or "")
                                content = getattr(m, "message_str", "") or ""
                            elif isinstance(m, dict):
                                # 官方原始历史等
                                t = m.get("timestamp") or m.get("ts")
                                # 规范里只有role/content
                                content = m.get("content", "")
                                # 尝试补充sender（若有的话）
                                if isinstance(m.get("sender"), dict):
                                    sid = str(m["sender"].get("user_id", ""))
                                    sname = m["sender"].get("nickname", "") or ""
                            # 时间格式化
                            if t:
                                try:
                                    dt = datetime.fromtimestamp(float(t))
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
                                    timestr = dt.strftime(
                                        f"%Y-%m-%d {weekday} %H:%M:%S"
                                    )
                                except Exception:
                                    timestr = "n/a"
                            else:
                                timestr = "n/a"
                            # 是否为机器人自己的消息
                            is_bot = sid and sid == bot_id_for_check
                            # 文本摘要
                            snippet = str(content).replace("\n", " ")
                            if len(snippet) > 80:
                                snippet = snippet[:80] + "…"
                            line = (
                                f"  [{idx}] t={timestr} sender={sname}(ID:{sid}) bot={is_bot} "
                                f"gid={gid} self_id={selfid} sess={sess} mid={mid} len={len(content)} txt={snippet}"
                            )
                            lines.append(line)
                        except Exception as _inner:
                            lines.append(f"  [预览异常] {type(m)}")
                    if lines:
                        for ln in lines:
                            logger.info(ln)
                except Exception:
                    pass

        # 🔧 根据配置决定是否获取历史
        # max_context == 0: 不获取历史，只用当前消息
        # max_context == -1: 不限制，获取所有历史
        # max_context > 0: 限制为指定数量

        # 🆕 v1.2.0: 准备缓存消息用于新的统一获取方法
        cached_astrbot_messages_for_fallback = []
        if not (isinstance(max_context, int) and max_context == 0):
            if (
                chat_id in self.pending_messages_cache
                and len(self.pending_messages_cache[chat_id]) > 0
            ):
                # 🔧 修复：读取所有缓存消息（不排除最后一条）
                # 因为最后一条可能不是当前消息，而是之前未回复的消息
                # 去重逻辑会在 context_manager 中处理
                cached_messages_raw = (
                    ProactiveChatManager.filter_expired_cached_messages(
                        self.pending_messages_cache[chat_id]
                    )
                )
                for cached_msg in cached_messages_raw:
                    if isinstance(cached_msg, dict):
                        try:
                            msg_obj = AstrBotMessage()
                            msg_obj.message_str = cached_msg.get("content", "")
                            msg_obj.platform_name = event.get_platform_name()
                            msg_obj.timestamp = cached_msg.get(
                                "message_timestamp"
                            ) or cached_msg.get("timestamp", time.time())
                            msg_obj.type = (
                                MessageType.GROUP_MESSAGE
                                if not event.is_private_chat()
                                else MessageType.FRIEND_MESSAGE
                            )
                            if not event.is_private_chat():
                                msg_obj.group_id = event.get_group_id()
                            msg_obj.self_id = event.get_self_id()
                            msg_obj.session_id = (
                                event.session_id
                                if hasattr(event, "session_id")
                                else chat_id
                            )
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
                            if self.debug_mode:
                                logger.warning(f"转换缓存消息失败: {e}")
                    elif isinstance(cached_msg, AstrBotMessage):
                        cached_astrbot_messages_for_fallback.append(cached_msg)

        # 🆕 v1.2.0: 使用新的统一方法获取历史消息（优先官方存储，回退自定义存储）
        if isinstance(max_context, int) and max_context == 0:
            # 配置为0，不获取任何历史上下文
            history_messages = []
            if self.debug_mode:
                logger.info("  配置为0，跳过历史上下文获取")
        else:
            # 使用新的统一方法：优先官方存储，回退自定义存储，自动拼接缓存消息
            history_messages = await ContextManager.get_history_messages_with_fallback(
                event=event,
                max_messages=max_context,
                context=self.context,
                cached_messages=cached_astrbot_messages_for_fallback,
            )
            if self.debug_mode:
                _log_msgs("历史-统一获取（官方优先+缓存）", history_messages)

        # 🆕 v1.2.0: 官方历史已在 get_history_messages_with_fallback 中处理
        # 以下为兼容性代码：尝试从 conversation_manager 获取额外的对话历史
        # 注意：message_history_manager 和 conversation_manager 是两个不同的存储
        # - message_history_manager: 存储平台消息历史（platform_message_history 表）
        # - conversation_manager: 存储 LLM 对话历史（conversations 表）
        if not (isinstance(max_context, int) and max_context == 0):
            try:
                cm = self.context.conversation_manager
                if cm:
                    uid = event.unified_msg_origin
                    cid = await cm.get_curr_conversation_id(uid)
                    if cid:
                        conv = await cm.get_conversation(
                            unified_msg_origin=uid, conversation_id=cid
                        )
                        official_history = None
                        if conv is not None:
                            if getattr(conv, "history", None):
                                try:
                                    official_history = json.loads(conv.history)
                                except Exception:
                                    official_history = None
                            if official_history is None and getattr(
                                conv, "content", None
                            ):
                                if isinstance(conv.content, list):
                                    official_history = conv.content
                                else:
                                    try:
                                        official_history = json.loads(conv.content)
                                    except Exception:
                                        official_history = None
                        if (
                            isinstance(official_history, list)
                            and len(official_history) > 0
                        ):
                            if self.debug_mode:
                                try:
                                    logger.info(
                                        f"  官方历史原始条数: {len(official_history)}"
                                    )
                                    if isinstance(max_context, int) and max_context > 0:
                                        logger.info(
                                            f"  官方历史选取窗口: 末尾 {max_context} 条"
                                        )
                                    else:
                                        logger.info("  官方历史选取窗口: 全量")
                                    _raw_prev = []
                                    for r in official_history[
                                        -min(5, len(official_history)) :
                                    ]:
                                        _s = (
                                            r.get("content", "")
                                            if isinstance(r, dict)
                                            else str(r)
                                        )
                                        _s = str(_s).replace("\n", " ")
                                        if len(_s) > 80:
                                            _s = _s[:80] + "…"
                                        _raw_prev.append(_s)
                                    if _raw_prev:
                                        logger.info(
                                            "  官方历史-原始预览: "
                                            + " | ".join(_raw_prev)
                                        )
                                except Exception:
                                    pass
                            hist_msgs = []
                            self_id = event.get_self_id()
                            platform_name = event.get_platform_name()
                            is_private_chat = event.is_private_chat()
                            default_user_name = "对方" if is_private_chat else "群友"
                            history_user_prefix = "history_user"
                            # 根据 max_context 决定截取范围
                            # -1: 不限制，使用全量
                            # > 0: 限制为指定数量
                            if isinstance(max_context, int):
                                if max_context == -1:
                                    msgs_iter = official_history  # 不限制
                                elif max_context > 0:
                                    msgs_iter = official_history[
                                        -max_context:
                                    ]  # 限制数量
                                else:
                                    msgs_iter = []  # max_context == 0 时不应走到这里
                            else:
                                msgs_iter = official_history  # 非整数时默认全量
                            for idx, msg in enumerate(msgs_iter):
                                if (
                                    isinstance(msg, dict)
                                    and "role" in msg
                                    and "content" in msg
                                ):
                                    m = AstrBotMessage()
                                    m.message_str = msg["content"]
                                    m.platform_name = platform_name
                                    _ts = (
                                        msg.get("timestamp")
                                        or msg.get("ts")
                                        or msg.get("time")
                                    )
                                    try:
                                        m.timestamp = (
                                            int(float(_ts)) if _ts else int(time.time())
                                        )
                                    except Exception:
                                        m.timestamp = int(time.time())
                                    m.type = (
                                        MessageType.GROUP_MESSAGE
                                        if not is_private_chat
                                        else MessageType.FRIEND_MESSAGE
                                    )
                                    if not is_private_chat:
                                        m.group_id = event.get_group_id()
                                    m.self_id = self_id
                                    m.session_id = getattr(
                                        event, "session_id", None
                                    ) or (
                                        event.get_sender_id()
                                        if is_private_chat
                                        else event.get_group_id()
                                    )
                                    raw_message_id = (
                                        msg.get("message_id")
                                        or msg.get("id")
                                        or msg.get("mid")
                                        or ""
                                    )
                                    m.message_id = (
                                        str(raw_message_id)
                                        or f"official_{idx}_{m.timestamp}"
                                    )

                                    if msg["role"] == "assistant":
                                        m.sender = MessageMember(
                                            user_id=self_id, nickname="AI"
                                        )
                                    else:
                                        sender_info = (
                                            msg.get("sender")
                                            if isinstance(msg.get("sender"), dict)
                                            else None
                                        )
                                        sender_id = None
                                        sender_name = None
                                        if sender_info:
                                            sender_id = (
                                                sender_info.get("user_id")
                                                or sender_info.get("id")
                                                or sender_info.get("uid")
                                                or sender_info.get("qq")
                                                or sender_info.get("uin")
                                            )
                                            sender_name = sender_info.get(
                                                "nickname"
                                            ) or sender_info.get("name")
                                        sender_id = (
                                            str(sender_id)
                                            if sender_id is not None
                                            else f"{history_user_prefix}_{idx}"
                                        )
                                        sender_name = sender_name or default_user_name
                                        m.sender = MessageMember(
                                            user_id=sender_id,
                                            nickname=sender_name,
                                        )
                                    hist_msgs.append(m)
                            # 🔧 修复：按历史截止时间戳过滤，丢弃插件重置之前的旧消息
                            _cutoff_ts = ContextManager.get_history_cutoff(chat_id)
                            if _cutoff_ts > 0 and hist_msgs:
                                _before = len(hist_msgs)
                                hist_msgs = [
                                    _m
                                    for _m in hist_msgs
                                    if (getattr(_m, "timestamp", 0) or 0) >= _cutoff_ts
                                ]
                                _filtered = _before - len(hist_msgs)
                                if _filtered > 0:
                                    logger.info(
                                        f"  官方历史截止过滤: 丢弃 {_filtered} 条旧消息"
                                    )
                            if hist_msgs:
                                if history_messages:
                                    existing_contents = set()
                                    for _existing in history_messages:
                                        content = None
                                        if isinstance(_existing, AstrBotMessage):
                                            content = getattr(
                                                _existing, "message_str", None
                                            )
                                        elif isinstance(_existing, dict):
                                            content = _existing.get("content")
                                        if content:
                                            existing_contents.add(content)

                                    for hm in hist_msgs:
                                        if (
                                            hm.message_str
                                            and hm.message_str in existing_contents
                                        ):
                                            continue
                                        history_messages.append(hm)
                                        if hm.message_str:
                                            existing_contents.add(hm.message_str)
                                else:
                                    history_messages = hist_msgs
                                if self.debug_mode:
                                    logger.info("  已合并官方历史")
                                    _log_msgs("历史-合并官方", history_messages)
                        elif self.debug_mode:
                            logger.info("  未获取到官方历史")
            except Exception as _:
                pass
        else:
            if self.debug_mode:
                logger.info("  跳过官方历史读取: max_context_messages=0")

        # 🆕 v1.2.0: 使用缓存管理器统一处理缓存读取和合并
        cached_count = 0
        dedup_skipped = 0
        original_history_count = len(history_messages) if history_messages else 0

        if isinstance(max_context, int) and max_context == 0:
            if self.debug_mode:
                logger.info("  跳过缓存合并: max_context_messages=0")
        else:
            # 使用缓存管理器合并缓存消息
            history_messages, cached_count, dedup_skipped = (
                self.cache_manager.merge_cache_to_history(
                    chat_id=chat_id,
                    history_messages=history_messages,
                    event=event,
                    exclude_current=True,  # 排除当前消息（最后一条）
                )
            )

            if self.debug_mode and cached_count > 0:
                logger.info(f"  [缓存管理器] 已合并 {cached_count} 条缓存消息到历史")
                if dedup_skipped > 0:
                    logger.info(f"  [缓存管理器] 去重跳过 {dedup_skipped} 条重复消息")

        # 🆕 优化：应用上下文限制 - 智能截断策略
        # 🔧 修复：统一按时间排序后删除最早的消息，不区分缓存或历史
        # 这样可以保证时间连续性，避免上下文割裂
        # max_context == -1: 不限制，保留所有消息
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

            if self.debug_mode:
                removed_cnt = before_cnt - len(history_messages)
                logger.info(
                    f"  智能截断: {before_cnt} -> {len(history_messages)} "
                    f"(按时间顺序删除最早的 {removed_cnt} 条消息，保留最新的 {max_context} 条)"
                )
                _log_msgs("历史-截断后", history_messages)
        elif self.debug_mode:
            if isinstance(max_context, int) and max_context == -1:
                logger.info("  配置为-1，不限制上下文数量")
            elif isinstance(max_context, int) and max_context == 0:
                logger.info("  配置为0，无历史上下文")
            else:
                logger.info("  未触发上下文限制")

        if self.debug_mode:
            logger.info(
                f"  最终历史消息: {len(history_messages) if history_messages else 0} 条"
            )

        # 获取窗口缓冲消息（独立于历史上下文，拼接到当前消息下方）
        window_buffered_msgs = self.cache_manager.get_window_buffered_messages(chat_id)
        if self.debug_mode and window_buffered_msgs:
            logger.info(f"  [窗口缓冲] 发现 {len(window_buffered_msgs)} 条窗口缓冲消息")

        # 格式化上下文
        bot_id = event.get_self_id()
        formatted_context = await ContextManager.format_context_for_ai(
            history_messages,
            message_text_for_ai,
            bot_id,
            include_timestamp=self.include_timestamp,
            include_sender_info=self.include_sender_info,
            window_buffered_messages=window_buffered_msgs,
        )

        if self.debug_mode:
            logger.info(f"  格式化后长度: {len(formatted_context)} 字符")
            try:
                _pv = formatted_context or ""
                snippet = _pv[:300].replace("\n", " ")
                logger.info(
                    "  格式化后预览: " + snippet + ("…" if len(_pv) > 300 else "")
                )
            except Exception:
                pass

        # 返回：原始消息文本、处理后的消息（不含元数据，用于保存）、格式化的上下文、图片URL列表、历史消息列表、待缓存数据、表情包标记状态
        return (
            True,
            original_message_text,
            processed_message,
            formatted_context,
            image_urls,
            history_messages,
            cached_message,  # 🆕 v1.2.0: 返回待缓存数据，由调用方决定是否缓存
            emoji_marker_applied,  # 🆕 v1.2.0: 表情包标记是否已添加
        )

    async def _generate_and_send_reply(
        self,
        event: AstrMessageEvent,
        formatted_context: str,
        message_text: str,
        platform_name: str,
        is_private: bool,
        chat_id: str,
        is_at_message: bool = False,
        has_trigger_keyword: bool = False,
        image_urls: list = None,
        history_messages: list = None,
        current_message_cache: dict = None,  # 🔧 修复：当前消息缓存副本，避免并发竞争
        conversation_fatigue_info: dict = None,  # 🆕 v1.2.0: 对话疲劳信息
        wait_window_extra_count: int = 0,  # 🔧 等待窗口收集的额外消息数（用于注意力机制补偿）
    ):
        """
        生成并发送回复，保存历史

        Args:
            event: 消息事件
            formatted_context: 格式化的上下文
            message_text: 消息文本
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            is_at_message: 是否@消息
            has_trigger_keyword: 是否包含触发关键词
            image_urls: 图片URL列表（用于多模态AI）
            history_messages: 历史消息列表（AstrBotMessage对象列表，用于contexts）
            current_message_cache: 当前消息的缓存副本（避免并发竞争导致缓存被清空）
            conversation_fatigue_info: 对话疲劳信息（用于生成收尾话语提示）

        Returns:
            生成器，用于yield回复
        """
        # 记录开始时间
        _process_start_time = time.time()

        # 如果image_urls为None，初始化为空列表
        if image_urls is None:
            image_urls = []
        # 注入记忆
        final_message = formatted_context
        try:
            ckey = ProbabilityManager.get_chat_key(platform_name, is_private, chat_id)

            # 🔧 修复：pre_decision 模式下，优先使用缓存的上下文（已植入记忆）
            # 无论是否跳过决策AI，只要是 pre_decision 模式且缓存存在，就应该使用缓存
            if (
                self.enable_memory_injection
                and self.memory_insertion_timing == "pre_decision"
            ):
                if (
                    hasattr(self, "_pre_decision_context_by_chat")
                    and ckey in self._pre_decision_context_by_chat
                ):
                    final_message = self._pre_decision_context_by_chat.pop(
                        ckey, formatted_context
                    )
                    if self.debug_mode:
                        logger.info(
                            "【步骤10.5】使用pre_decision缓存的上下文（已植入记忆）"
                        )

            # 清理跳过决策AI的标记
            if (
                hasattr(self, "_ai_decision_skipped")
                and ckey in self._ai_decision_skipped
            ):
                try:
                    self._ai_decision_skipped.discard(ckey)
                except Exception:
                    pass
        except Exception:
            pass

        if (
            self.enable_memory_injection
            and self.memory_insertion_timing == "post_decision"
        ):
            if self.debug_mode:
                logger.info("【步骤11】注入记忆内容")

            # 获取记忆插件配置（使用已提取的实例变量）
            memory_mode = self.memory_plugin_mode
            livingmemory_top_k = self.livingmemory_top_k
            livingmemory_version = self.livingmemory_version

            if MemoryInjector.check_memory_plugin_available(
                self.context, mode=memory_mode, version=livingmemory_version
            ):
                memories = await MemoryInjector.get_memories(
                    self.context,
                    event,
                    mode=memory_mode,
                    top_k=livingmemory_top_k,
                    version=livingmemory_version,
                )
                if memories:
                    final_message = MemoryInjector.inject_memories_to_message(
                        final_message, memories
                    )
                    if self.debug_mode:
                        logger.info(
                            f"  已注入记忆({memory_mode}模式),长度增加: {len(final_message) - len(formatted_context)} 字符"
                        )
            else:
                logger.warning(
                    f"记忆插件({memory_mode}模式)未安装或不可用,跳过记忆注入"
                )

        # 注入工具信息
        if self.enable_tools_reminder:
            if self.debug_mode:
                logger.info("【步骤12】注入工具信息")

            # 按人格过滤工具
            allowed_tool_names = None
            if self.tools_reminder_persona_filter:
                try:
                    umo = event.unified_msg_origin
                    allowed_tool_names = await ToolsReminder.get_persona_tool_names(
                        self.context, umo, platform_name
                    )
                    if self.debug_mode:
                        if allowed_tool_names is not None:
                            logger.info(
                                f"  人格工具过滤: 允许 {len(allowed_tool_names)} 个工具"
                            )
                        else:
                            logger.info("  人格未限制工具,使用全部工具")
                except Exception as e:
                    logger.warning(f"人格工具过滤失败,使用全部工具: {e}")

            old_len = len(final_message)
            final_message = ToolsReminder.inject_tools_to_message(
                final_message, self.context, allowed_tool_names
            )
            if self.debug_mode:
                logger.info(
                    f"  已注入工具信息,长度增加: {len(final_message) - old_len} 字符"
                )

        # 🆕 v1.0.2: 注入情绪状态（如果启用）
        if self.mood_enabled and self.mood_tracker:
            if self.debug_mode:
                logger.info("【步骤12.5】注入情绪状态")

            # 使用格式化后的上下文来判断情绪
            final_message = self.mood_tracker.inject_mood_to_prompt(
                chat_id, final_message, formatted_context
            )

        # 调用AI生成回复
        if self.debug_mode:
            logger.info("【步骤13】调用AI生成回复")
            logger.info(f"  最终消息长度: {len(final_message)} 字符")

        _start_time = time.time()

        ai_error_flag = False
        message_id_for_error = None
        try:
            message_id_for_error = self._get_message_id(event)
        except Exception:
            message_id_for_error = None

        try:
            reply_result = await ReplyHandler.generate_reply(
                event,
                self.context,
                final_message,
                self.reply_ai_extra_prompt,
                self.reply_ai_prompt_mode,
                image_urls,  # 传递图片URL列表
                include_sender_info=self.include_sender_info,
                include_timestamp=self.include_timestamp,  # 🔧 v1.2.0: 补传时间戳开关，确保contexts格式与prompt一致
                history_messages=history_messages,  # 🔧 修复：传递历史消息用于构建contexts
                conversation_fatigue_info=conversation_fatigue_info,  # 🆕 v1.2.0: 传递疲劳信息
            )
        except Exception as e:
            ai_error_flag = True
            logger.error(f"生成AI回复时发生未捕获异常: {e}", exc_info=True)
            reply_result = event.plain_result(f"生成回复时发生错误: {str(e)}")

        if (
            not ai_error_flag
            and hasattr(reply_result, "is_llm_result")
            and hasattr(reply_result, "chain")
        ):
            try:
                if not reply_result.is_llm_result():
                    parts = []
                    for comp in getattr(reply_result, "chain", []) or []:
                        if hasattr(comp, "text"):
                            parts.append(comp.text)
                    err_text = "".join(parts)
                    if "生成回复时发生错误" in err_text:
                        ai_error_flag = True
            except Exception:
                pass

        if ai_error_flag and message_id_for_error:
            try:
                if not hasattr(self, "_ai_error_message_ids"):
                    self._ai_error_message_ids = set()
                self._ai_error_message_ids.add(message_id_for_error)
            except Exception:
                pass

        _elapsed = time.time() - _start_time
        if self.debug_mode:
            logger.info(f"【步骤13】AI回复生成完成，耗时: {_elapsed:.2f}秒")
        elif _elapsed > self.reply_generation_timeout_warning:
            logger.warning(
                f"⚠️ AI回复生成耗时异常: {_elapsed:.2f}秒（超过{self.reply_generation_timeout_warning}秒）"
            )

        # 📝 注意：错字模拟和延迟模拟已迁移到 @on_decorating_result() 钩子中处理
        # 因为普通回复流程使用 event.request_llm() 返回 ProviderRequest 对象，
        # 无法在此处直接处理文本内容。钩子中可以获取AI生成后的最终文本。
        # 详见 on_decorating_result() 方法（第5560-5608行）

        # 保存用户消息（从缓存读取并添加元数据）
        if self.debug_mode:
            logger.info("【步骤14】保存用户消息")

        try:
            # 🔧 修复：优先使用缓存副本，避免并发竞争导致缓存被清空
            message_to_save = ""

            # 优先使用传入的缓存副本
            last_cached = current_message_cache

            # 如果没有缓存副本，尝试从共享缓存按message_id精确匹配（向后兼容）
            if not last_cached:
                msg_id_for_lookup = self._get_message_id(event)
                if chat_id in self.pending_messages_cache:
                    for cached_msg in reversed(self.pending_messages_cache[chat_id]):
                        if (
                            isinstance(cached_msg, dict)
                            and cached_msg.get("message_id") == msg_id_for_lookup
                        ):
                            last_cached = cached_msg
                            if self.debug_mode:
                                logger.info(
                                    "⚠️ [并发警告] 从共享缓存按message_id精确匹配获取消息"
                                )
                            break
                if not last_cached and self.debug_mode:
                    logger.info("⚠️ [并发警告] 共享缓存中未找到匹配消息，将从event提取")
            elif self.debug_mode:
                logger.info("🔒 [并发保护] 使用缓存副本，避免竞争")

            if (
                last_cached
                and isinstance(last_cached, dict)
                and "content" in last_cached
            ):
                # 获取处理后的消息内容（不含元数据）
                raw_content = last_cached["content"]

                if self.debug_mode:
                    logger.info(f"【步骤14-读缓存】内容: {raw_content[:100]}")
                else:
                    logger.info("🟢 读取缓存中")

                # 使用缓存中的发送者信息添加元数据
                # 🆕 v1.0.4: 根据缓存中的触发方式信息确定trigger_type
                # 注意：需要同时检查 has_trigger_keyword 来正确判断触发方式
                trigger_type = None
                if last_cached.get("has_trigger_keyword"):
                    # 关键词触发（优先级高于@消息判断）
                    trigger_type = "keyword"
                elif last_cached.get("is_at_message"):
                    # 真正的@消息触发
                    trigger_type = "at"
                else:
                    # 概率触发（AI主动回复）
                    trigger_type = "ai_decision"

                message_to_save = MessageProcessor.add_metadata_from_cache(
                    raw_content,
                    last_cached.get("sender_id", event.get_sender_id()),
                    last_cached.get("sender_name", event.get_sender_name()),
                    last_cached.get("message_timestamp")
                    or last_cached.get("timestamp"),
                    self.include_timestamp,
                    self.include_sender_info,
                    last_cached.get("mention_info"),  # 传递@信息
                    trigger_type,  # 🆕 v1.0.4: 传递触发方式
                    last_cached.get("poke_info"),  # 🆕 v1.0.9: 传递戳一戳信息
                    last_cached.get("is_empty_at", False),  # 🔧 修复：传递空@标记
                )

                # 清理系统提示（保存前过滤）
                message_to_save = MessageCleaner.clean_message(message_to_save)

                if self.debug_mode:
                    logger.info(f"【步骤14-加元数据后】内容: {message_to_save[:150]}")

            # 如果从缓存获取失败，使用当前处理后的消息并添加元数据
            if not message_to_save:
                logger.warning("⚠️ 缓存中无消息，使用当前处理后的消息（这不应该发生！）")
                # 🆕 v1.0.4: 确定触发方式
                trigger_type = None
                if has_trigger_keyword:
                    # 关键词触发（优先级高于@消息判断）
                    trigger_type = "keyword"
                elif is_at_message:
                    # 真正的@消息触发
                    trigger_type = "at"
                else:
                    # 概率触发（AI主动回复）
                    trigger_type = "ai_decision"

                message_to_save = MessageProcessor.add_metadata_to_message(
                    event,
                    message_text,  # message_text 就是 processed_message
                    self.include_timestamp,
                    self.include_sender_info,
                    None,  # 这种情况下没有mention_info（从event提取的fallback）
                    trigger_type,  # 🆕 v1.0.4: 传递触发方式
                    None,  # 🆕 v1.0.9: 无法获取poke_info（fallback情况）
                    False,  # 🔧 修复：fallback情况，无法确定是否空@，默认False
                )

                # 清理系统提示（保存前过滤）
                message_to_save = MessageCleaner.clean_message(message_to_save)

            if self.debug_mode:
                logger.info(f"  准备保存的完整消息: {message_to_save[:300]}...")

            await ContextManager.save_user_message(event, message_to_save, self.context)
            if self.debug_mode:
                logger.info(
                    f"  ✅ 用户消息已保存到自定义存储: {len(message_to_save)} 字符"
                )
        except Exception as e:
            logger.error(f"保存用户消息时发生错误: {e}")

        # 🆕 发送前过滤检查：防止直接转发用户消息和重复发送相同回复
        # 提取回复文本（仅当为字符串类型时；LLM请求结果在装饰阶段处理）
        reply_text = ""
        is_provider_request = False
        if reply_result:
            is_provider_request = isinstance(reply_result, ProviderRequest)
            if isinstance(reply_result, str):
                reply_text = reply_result.strip()

        # 重复判断标准：严格字符串一致（不做大小写、标点等归一化，仅移除首尾空白）

        # 检查1: 回复是否与用户消息相同（防止直接转发）
        # 仅对字符串型即时回复进行检查；LLM结果在装饰阶段处理
        if reply_text and not is_provider_request:
            # 获取用户原始消息（严格比较，仅去除首尾空白）
            user_message_clean = message_text.strip()

            if reply_text == user_message_clean:
                logger.info("[消息过滤]回复与用户消息相同，已过滤")
                if self.debug_mode:
                    logger.warning(
                        f"🚫 [消息过滤] 检测到回复与用户消息相同，跳过发送\n"
                        f"  用户消息: {user_message_clean[:100]}...\n"
                        f"  AI回复: {reply_text[:100]}..."
                    )
                else:
                    # 非debug模式下也显示部分信息
                    logger.info(f"  用户消息: {user_message_clean[:50]}...")
                    logger.info(f"  AI回复: {reply_text[:50]}...")

                # 🔧 重要修复：设置标记，防止平台兜底处理@消息
                if event.is_at_or_wake_command:
                    event.call_llm = True
                    if self.debug_mode:
                        logger.info(
                            "【消息过滤】已设置call_llm标记，防止平台重复处理@消息"
                        )

                # 不发送，直接返回
                return

        # 检查2: 回复是否与最近发送的回复重复（防止重复发送相同答案）
        # 仅对字符串型即时回复进行检查；LLM结果在装饰阶段处理
        # 🔧 使用可配置的重复消息检测参数
        # 🔧 重要：重复检测只拦截发送，不影响后续流程（概率调整、注意力记录等）
        is_duplicate_blocked = False
        if reply_text and not is_provider_request and self.enable_duplicate_filter:
            # 获取或初始化该会话的回复缓存
            if chat_id not in self.recent_replies_cache:
                self.recent_replies_cache[chat_id] = []

            current_time = time.time()

            # 根据配置决定是否启用时效性过滤
            if self.enable_duplicate_time_limit:
                # 清理过期的回复记录（使用配置的时效）
                time_limit = max(60, self.duplicate_filter_time_limit)  # 最少60秒
                self.recent_replies_cache[chat_id] = [
                    reply
                    for reply in self.recent_replies_cache[chat_id]
                    if current_time - reply.get("timestamp", 0) < time_limit
                ]

            # 检查是否与最近N条回复重复（使用配置的条数，严格全等匹配）
            check_count = max(1, self.duplicate_filter_check_count)  # 最少检查1条
            for recent_reply in self.recent_replies_cache[chat_id][-check_count:]:
                recent_content = recent_reply.get("content", "")
                recent_timestamp = recent_reply.get("timestamp", 0)

                # 如果启用时效性判断，检查消息是否在时效内
                if self.enable_duplicate_time_limit:
                    time_limit = max(60, self.duplicate_filter_time_limit)
                    if current_time - recent_timestamp >= time_limit:
                        continue  # 超过时效，跳过此条

                if recent_content and reply_text == recent_content.strip():
                    logger.info(
                        "[消息过滤]回复与最近发送的回复重复，已拦截发送（后续流程继续执行）"
                    )
                    if self.debug_mode:
                        logger.warning(
                            f"🚫 [消息过滤] 检测到回复与最近发送的回复重复，跳过发送\n"
                            f"  最近回复: {recent_content[:100]}...\n"
                            f"  当前回复: {reply_text[:100]}..."
                        )
                    else:
                        # 非debug模式下也显示部分信息
                        logger.info(f"  最近回复: {recent_content[:50]}...")
                        logger.info(f"  当前回复: {reply_text[:50]}...")
                    # 🔧 设置标记，跳过发送但继续后续流程
                    is_duplicate_blocked = True
                    break

        # 发送回复
        # 🔧 如果是重复消息，跳过发送但继续后续流程
        if not is_duplicate_blocked:
            if reply_result is None:
                logger.error("❌ [发送失败] reply_result为None，无法发送回复")
                if self.debug_mode:
                    logger.error("  这通常是因为ReplyHandler.generate_reply返回了None")

                # 🔧 重要修复：设置标记，防止平台兜底处理@消息
                if event.is_at_or_wake_command:
                    event.call_llm = True
                    if self.debug_mode:
                        logger.info(
                            "【发送失败】已设置call_llm标记，防止平台重复处理@消息"
                        )

                return

            if self.debug_mode:
                logger.info(
                    f"【步骤13.9】准备发送回复，类型: {type(reply_result).__name__}"
                )

            # 🔧 修复：当插件发起 LLM 请求时，标记已调用 LLM，
            # 阻止框架 ProcessStage 对 @消息触发第二次默认 LLM 调用路径
            if isinstance(reply_result, ProviderRequest):
                event.call_llm = True

            yield reply_result

            # 🔧 安全兜底：agent完整流程结束后，检查是否有未保存的累积回复
            # 正常情况下，on_llm_response 设置 _agent_done_flags，after_message_sent 完成保存。
            # 但极少数边界情况下（如工具直接发送结果给用户，agent跳过on_agent_done），
            # on_llm_response 不会触发，累积的回复就不会被保存。此处作为安全网兜底。
            message_id = self._get_message_id(event)
            if (
                message_id in self._pending_bot_replies
                and self._pending_bot_replies[message_id]
            ):
                logger.warning(
                    f"[安全兜底] 检测到 {len(self._pending_bot_replies[message_id])} 段未保存的累积回复"
                    f"（on_llm_response可能未触发），执行兜底保存"
                )
                try:
                    await self._finalize_bot_reply_save(event, message_id)
                except Exception as fallback_err:
                    logger.error(
                        f"[安全兜底] 兜底保存失败: {fallback_err}", exc_info=True
                    )

            if self.debug_mode:
                logger.info("【步骤13.9】回复已通过yield发送")
        else:
            # 🔧 重要修复：即使跳过发送，也要设置标记，防止平台兜底处理@消息
            if event.is_at_or_wake_command:
                event.call_llm = True
                if self.debug_mode:
                    logger.info("【步骤13.9】已设置call_llm标记，防止平台重复处理@消息")

            if self.debug_mode:
                logger.info("【步骤13.9】跳过发送回复（重复消息已拦截），继续后续流程")

        # 🆕 记录已发送的回复（用于后续去重检查）
        # 仅记录字符串型即时回复；LLM结果在 after_message_sent 钩子中记录
        # 🔧 只在非重复消息时记录到缓存
        if reply_text and not is_provider_request and not is_duplicate_blocked:
            if chat_id not in self.recent_replies_cache:
                self.recent_replies_cache[chat_id] = []

            # 添加到缓存
            self.recent_replies_cache[chat_id].append(
                {"content": reply_text, "timestamp": time.time()}
            )

            # 🔒 限制缓存大小（保留配置条数的2倍，最少10条，但不超过硬上限）
            max_cache_size = min(
                max(10, self.duplicate_filter_check_count * 2),
                self._DUPLICATE_CACHE_SIZE_LIMIT,
            )
            if len(self.recent_replies_cache[chat_id]) > max_cache_size:
                # 丢弃最旧的消息，保留最新的
                self.recent_replies_cache[chat_id] = self.recent_replies_cache[chat_id][
                    -max_cache_size:
                ]

            if self.debug_mode:
                logger.info(
                    f"【消息过滤】已记录回复到缓存，当前缓存数: {len(self.recent_replies_cache[chat_id])}"
                )

        # 🆕 v1.1.0: 记录AI回复（用于主动对话功能）
        if self.proactive_enabled:
            chat_key = ProbabilityManager.get_chat_key(
                platform_name, is_private, chat_id
            )
            # 在实际记录回复前，若处于主动对话临时提升阶段，则在此时机取消临时提升（AI已决定回复）
            ProactiveChatManager.check_and_handle_reply_after_proactive(
                chat_key, self.config, force=True
            )
            ProactiveChatManager.record_bot_reply(chat_key, is_proactive=False)
            if self.debug_mode:
                logger.info(f"[主动对话] 已记录AI回复（普通回复）")

        # 🆕 v1.2.1: 记录回复到密度管理器
        if self.enable_reply_density_limit:
            try:
                density_chat_key = ProbabilityManager.get_chat_key(
                    platform_name, is_private, chat_id
                )
                await ReplyDensityManager.record_reply(density_chat_key)
            except Exception as e:
                if self.debug_mode:
                    logger.warning(f"[回复密度] 记录回复失败: {e}")

        # 调整概率 / 记录注意力（二选一）
        attention_enabled = self.enable_attention_mechanism

        if attention_enabled:
            # 启用注意力机制：使用注意力机制，不使用传统概率提升
            if self.debug_mode:
                logger.info("【步骤15】跳过传统概率调整，使用注意力机制")
                logger.info("【步骤16】记录被回复用户信息（注意力机制-增强版）")

            # 获取被回复的用户信息
            replied_user_id = event.get_sender_id()
            replied_user_name = event.get_sender_name()

            # 获取消息预览（用于注意力机制的上下文记录）
            message_preview = message_text[:50] if message_text else ""

            await AttentionManager.record_replied_user(
                platform_name,
                is_private,
                chat_id,
                replied_user_id,
                replied_user_name,
                message_preview=message_preview,
                message_text=message_text,  # v1.1.2: 传递完整消息用于情感检测
                attention_boost_step=self.attention_boost_step,  # 🔧 始终使用原始配置值，不做缩放
                attention_decrease_step=self.attention_decrease_step,
                emotion_boost_step=self.emotion_boost_step,
                extra_interaction_count=wait_window_extra_count,  # 🔧 传递窗口额外消息数（用于独立的窗口修正衰减）
                window_decay_per_msg=self.group_wait_window_attention_decay_per_msg,  # 🔧 每条额外消息的修正衰减值
            )

            # 注意：疲劳重置已移至 AI 决策确认回复后、生成回复前执行
            # 这样可以确保：1. 重置在 record_replied_user 之前 2. 不受跳过逻辑影响

            if self.debug_mode:
                logger.info(
                    f"【步骤16】已记录: {replied_user_name}(ID: {replied_user_id}), 消息预览: {message_preview}"
                )
        else:
            # 未启用注意力机制：使用传统概率提升
            if self.debug_mode:
                logger.info("【步骤15】调整读空气概率（传统模式）")

            await ProbabilityManager.boost_probability(
                platform_name,
                is_private,
                chat_id,
                self.after_reply_probability,
                self.probability_duration,
            )

            if self.debug_mode:
                logger.info("【步骤15】概率调整完成")

        # 🆕 v1.0.2: 频率动态调整检查
        if self.frequency_adjuster_enabled and self.frequency_adjuster:
            try:
                # 使用完整的会话标识，确保不同会话的状态隔离
                chat_key = ProbabilityManager.get_chat_key(
                    platform_name, is_private, chat_id
                )

                # 检查是否需要进行频率调整
                message_count = self.frequency_adjuster.get_message_count(chat_key)

                if self.frequency_adjuster.should_check_frequency(
                    chat_key, message_count
                ):
                    if self.debug_mode:
                        _freq_start = time.time()
                        logger.info("【步骤17】开始频率动态调整检查")

                    # 获取最近的消息用于分析（使用配置的数量）
                    analysis_msg_count = self.frequency_analysis_message_count

                    # 🔧 配置矫正：处理异常值
                    if isinstance(analysis_msg_count, int) and analysis_msg_count < -1:
                        logger.warning(
                            f"⚠️ [频率调整-配置矫正] frequency_analysis_message_count 配置值 {analysis_msg_count} 小于 -1，已矫正为 -1（不限制）"
                        )
                        analysis_msg_count = -1

                    # 🆕 v1.2.0: 使用新的统一方法获取历史消息（优先官方存储，回退自定义存储）
                    # 根据配置决定是否获取历史
                    if isinstance(analysis_msg_count, int) and analysis_msg_count == 0:
                        # 配置为0，不进行频率分析
                        if self.debug_mode:
                            logger.info("[频率调整] 配置为0，跳过频率分析")
                        recent_messages = []
                    else:
                        # 准备缓存消息
                        cached_astrbot_messages_for_freq = []
                        if (
                            chat_id in self.pending_messages_cache
                            and self.pending_messages_cache[chat_id]
                        ):
                            # 🔧 修复：过滤过期的缓存消息，避免使用已过期但未清理的消息
                            cached_messages_raw = (
                                ProactiveChatManager.filter_expired_cached_messages(
                                    self.pending_messages_cache[chat_id]
                                )
                            )
                            # 过滤掉窗口缓冲消息（频率分析只关注普通缓存）
                            cached_messages_raw = [
                                msg
                                for msg in cached_messages_raw
                                if not (
                                    isinstance(msg, dict)
                                    and msg.get("window_buffered", False)
                                )
                            ]
                            for cached_msg in cached_messages_raw:
                                if isinstance(cached_msg, dict):
                                    try:
                                        msg_obj = AstrBotMessage()
                                        msg_obj.message_str = cached_msg.get(
                                            "content", ""
                                        )
                                        msg_obj.platform_name = (
                                            event.get_platform_name()
                                        )
                                        msg_obj.timestamp = cached_msg.get(
                                            "message_timestamp"
                                        ) or cached_msg.get("timestamp", time.time())
                                        msg_obj.type = (
                                            MessageType.GROUP_MESSAGE
                                            if not event.is_private_chat()
                                            else MessageType.FRIEND_MESSAGE
                                        )
                                        if not event.is_private_chat():
                                            msg_obj.group_id = event.get_group_id()
                                        msg_obj.self_id = event.get_self_id()
                                        msg_obj.session_id = (
                                            event.session_id
                                            if hasattr(event, "session_id")
                                            else chat_id
                                        )
                                        msg_obj.message_id = f"cached_{cached_msg.get('timestamp', time.time())}"
                                        sender_id = cached_msg.get("sender_id", "")
                                        sender_name = cached_msg.get(
                                            "sender_name", "未知用户"
                                        )
                                        if sender_id:
                                            msg_obj.sender = MessageMember(
                                                user_id=sender_id, nickname=sender_name
                                            )
                                        cached_astrbot_messages_for_freq.append(msg_obj)
                                    except Exception as e:
                                        if self.debug_mode:
                                            logger.warning(
                                                f"[频率调整] 转换缓存消息失败: {e}"
                                            )
                                elif isinstance(cached_msg, AstrBotMessage):
                                    cached_astrbot_messages_for_freq.append(cached_msg)

                        # 使用新的统一方法获取历史消息
                        recent_messages = (
                            await ContextManager.get_history_messages_with_fallback(
                                event=event,
                                max_messages=analysis_msg_count,
                                context=self.context,
                                cached_messages=cached_astrbot_messages_for_freq,
                            )
                        )

                        if self.debug_mode and cached_astrbot_messages_for_freq:
                            logger.info(f"[频率调整] 缓存消息已在统一方法中合并")

                    if self.debug_mode:
                        expected_desc = (
                            "不限制"
                            if analysis_msg_count == -1
                            else f"{analysis_msg_count}条"
                        )
                        logger.info(
                            f"[频率调整] 获取最近消息: 期望{expected_desc}, 实际{len(recent_messages) if recent_messages else 0}条"
                        )

                    if recent_messages:
                        # 构建可读的消息文本
                        # AstrBotMessage 对象的属性访问方式
                        bot_id = event.get_self_id()
                        recent_text_parts = []
                        # 遍历所有消息（已经在上面根据配置截断过了）
                        for msg in recent_messages:
                            # 判断消息角色（用户还是bot）
                            role = "user"
                            if hasattr(msg, "sender") and msg.sender:
                                sender_id = (
                                    msg.sender.user_id
                                    if hasattr(msg.sender, "user_id")
                                    else ""
                                )
                                if str(sender_id) == str(bot_id):
                                    role = "assistant"

                            # 提取消息内容
                            content = ""
                            if hasattr(msg, "message_str"):
                                content = msg.message_str[:100]

                            recent_text_parts.append(f"{role}: {content}")

                        recent_text = "\n".join(recent_text_parts)

                        # 使用AI分析频率（使用配置的超时时间）
                        analysis_timeout = self.frequency_analysis_timeout
                        decision = await self.frequency_adjuster.analyze_frequency(
                            self.context,
                            event,
                            recent_text,
                            self.decision_ai_provider_id,
                            analysis_timeout,
                        )

                        if decision:
                            # 获取当前概率
                            current_prob = (
                                await ProbabilityManager.get_current_probability(
                                    platform_name,
                                    is_private,
                                    chat_id,
                                    self.initial_probability,
                                )
                            )

                            # 调整概率
                            new_prob = self.frequency_adjuster.adjust_probability(
                                current_prob, decision
                            )

                            # 如果概率有变化，应用新概率（使用相对差值判断，避免小概率值时阈值过大）
                            if (
                                current_prob > 0
                                and abs(new_prob - current_prob) / current_prob > 0.05
                            ):
                                # 通过概率管理器设置新的基础概率
                                # 使用配置的持续时间
                                duration = self.frequency_adjust_duration
                                await ProbabilityManager.set_base_probability(
                                    platform_name,
                                    is_private,
                                    chat_id,
                                    new_prob,
                                    duration,
                                )
                                logger.info(
                                    f"[频率调整] ✅ 已应用概率调整: {current_prob:.2f} → {new_prob:.2f} (持续{duration}秒)"
                                )

                            # 更新检查状态（使用相同的chat_key确保状态一致）
                            self.frequency_adjuster.update_check_state(chat_key)

                    if self.debug_mode:
                        _freq_elapsed = time.time() - _freq_start
                        logger.info(
                            f"【步骤17】频率调整检查完成，耗时: {_freq_elapsed:.2f}秒"
                        )
            except Exception as e:
                logger.error(f"频率调整检查失败: {e}")

        if self.debug_mode:
            logger.info("=" * 60)
            logger.info("✓ 消息处理流程完成")

        _process_total_time = time.time() - _process_start_time
        timeout_threshold = self.reply_timeout_warning_threshold
        if _process_total_time > timeout_threshold:
            logger.warning(
                f"⚠️ 消息处理总耗时异常: {_process_total_time:.2f}秒 ({int(_process_total_time / 60)}分{int(_process_total_time % 60)}秒)（超过{timeout_threshold}秒阈值）"
            )
        elif self.debug_mode:
            logger.info(f"消息处理总耗时: {_process_total_time:.2f}秒")

        logger.info("消息处理完成,已发送回复并保存历史")

        # 🆕 回复后戳一戳功能
        if self.poke_after_reply_enabled:
            # 获取被回复的用户信息
            replied_user_id = event.get_sender_id()

            # 执行戳一戳（概率触发）
            await self._do_poke_after_reply(event, replied_user_id, is_private, chat_id)

    async def _do_poke_after_reply(
        self, event: AstrMessageEvent, user_id: str, is_private: bool, chat_id: str
    ):
        """
        回复后戳一戳功能

        Args:
            event: 消息事件
            user_id: 被戳的用户ID
            is_private: 是否为私聊
            chat_id: 聊天ID
        """
        try:
            # 只在群聊中生效（私聊不需要戳一戳）
            if is_private:
                if self.debug_mode:
                    logger.info("[戳一戳] 私聊消息，跳过戳一戳功能")
                return

            # 🆕 白名单检查：检查当前群聊是否允许戳一戳功能
            if not self._is_poke_enabled_in_group(chat_id):
                if self.debug_mode:
                    logger.info(
                        f"[戳一戳] 群 {chat_id} 不在戳一戳白名单中，跳过戳一戳功能"
                    )
                return

            # 检查平台是否为aiocqhttp
            platform_name = event.get_platform_name()
            if platform_name != "aiocqhttp":
                if self.debug_mode:
                    logger.info(f"[戳一戳] 当前平台 {platform_name} 不支持戳一戳，跳过")
                return

            # 根据概率决定是否戳一戳
            if random.random() > self.poke_after_reply_probability:
                if self.debug_mode:
                    logger.info(
                        f"[戳一戳] 未达到触发概率({self.poke_after_reply_probability})，跳过"
                    )
                return

            # 延迟执行（模拟真人思考时间）
            if self.poke_after_reply_delay > 0:
                await asyncio.sleep(self.poke_after_reply_delay)

            # 确保事件类型正确
            if not isinstance(event, AiocqhttpMessageEvent):
                logger.warning(f"[戳一戳] 事件类型不匹配，无法执行戳一戳")
                return

            # 执行戳一戳
            try:
                client = event.bot
                payloads = {"user_id": int(user_id)}
                # 添加群ID
                if chat_id:
                    payloads["group_id"] = int(chat_id)

                await client.api.call_action("send_poke", **payloads)

                if self.debug_mode:
                    logger.info(f"[戳一戳] ✅ 已戳一戳用户 {user_id} (群:{chat_id})")
                else:
                    logger.info(f"[戳一戳] 已戳一戳用户")

                if self.poke_trace_enabled:
                    self._register_poke_trace(chat_id, str(user_id))

            except Exception as e:
                logger.error(f"[戳一戳] 执行戳一戳失败: {e}")

        except Exception as e:
            logger.error(f"[戳一戳] 戳一戳功能发生错误: {e}")

    async def _maybe_reverse_poke_on_poke(
        self,
        event: AstrMessageEvent,
        poke_info: dict,
        is_private: bool,
        chat_id: str,
    ) -> bool:
        """
        在收到戳一戳消息且未被忽略时，按配置概率反向戳回发起戳一戳的用户。
        成功触发时返回True（表示本插件丢弃后续处理），否则返回False。
        """
        try:
            # 概率为0则不启用
            if self.poke_reverse_on_poke_probability <= 0:
                return False

            # 仅在群聊中执行（与回复后戳一戳一致的限制）
            if is_private:
                if self.debug_mode:
                    logger.info("【反戳】私聊消息，跳过反戳功能")
                return False

            # 🆕 白名单检查：检查当前群聊是否允许戳一戳功能
            if not self._is_poke_enabled_in_group(chat_id):
                if self.debug_mode:
                    logger.info(
                        f"【反戳】群 {chat_id} 不在戳一戳白名单中，跳过反戳功能"
                    )
                return False

            # 平台校验
            platform_name = event.get_platform_name()
            if platform_name != "aiocqhttp":
                if self.debug_mode:
                    logger.info(f"【反戳】平台 {platform_name} 不支持戳一戳，跳过")
                return False

            # 概率判断
            if random.random() >= self.poke_reverse_on_poke_probability:
                if self.debug_mode:
                    logger.info(
                        f"【反戳】未达到触发概率({self.poke_reverse_on_poke_probability})，继续正常处理"
                    )
                return False

            # 事件类型校验
            if not isinstance(event, AiocqhttpMessageEvent):
                logger.warning("【反戳】事件类型不匹配，无法执行戳一戳")
                return False

            # 执行反戳（戳回发起者）
            sender_id = poke_info.get("sender_id")
            if not sender_id:
                if self.debug_mode:
                    logger.info("【反戳】缺少sender_id，跳过")
                return False

            try:
                client = event.bot
                payloads = {"user_id": int(sender_id)}
                if chat_id:
                    payloads["group_id"] = int(chat_id)

                await client.api.call_action("send_poke", **payloads)
                if self.debug_mode:
                    logger.info(f"【反戳】✅ 已反戳用户 {sender_id} (群:{chat_id})")
                else:
                    logger.info("【反戳】已执行反戳")
                if self.poke_trace_enabled:
                    self._register_poke_trace(chat_id, str(sender_id))
            except Exception as e:
                logger.error(f"【反戳】执行反戳失败: {e}")
                # 即使失败，也不影响主流程，继续正常处理
                return False

            # 已触发反戳，本插件丢弃后续处理（不拦截消息传播）
            return True

        except Exception as e:
            logger.error(f"【反戳】反戳流程发生错误: {e}")
            return False

    def _get_poke_trace_store(self, chat_id: str) -> OrderedDict:
        key = str(chat_id)
        store = self.poke_trace_records.get(key)
        if not isinstance(store, OrderedDict):
            store = OrderedDict()
            self.poke_trace_records[key] = store
        return store

    def _cleanup_poke_trace(self, chat_id: str):
        store = self._get_poke_trace_store(chat_id)
        now_ts = time.time()
        to_delete = [uid for uid, exp in store.items() if exp <= now_ts]
        for uid in to_delete:
            try:
                del store[uid]
            except Exception:
                pass

    def _register_poke_trace(self, chat_id: str, user_id: str):
        try:
            if not self.poke_trace_enabled:
                return
            store = self._get_poke_trace_store(chat_id)
            self._cleanup_poke_trace(chat_id)
            uid = str(user_id)
            if uid in store:
                try:
                    del store[uid]
                except Exception:
                    pass
            while len(store) >= max(1, int(self.poke_trace_max_tracked_users)):
                try:
                    store.popitem(last=False)
                except Exception:
                    break
            expire_at = time.time() + max(1, int(self.poke_trace_ttl_seconds))
            store[uid] = expire_at
            if self.debug_mode:
                logger.info(
                    f"[戳过对方追踪] 注册: chat={chat_id} user={uid} ttl={self.poke_trace_ttl_seconds}s"
                )
        except Exception as e:
            logger.error(f"[戳过对方追踪] 注册失败: {e}")

    def _check_and_consume_poke_trace(self, chat_id: str, user_id: str) -> bool:
        try:
            if not self.poke_trace_enabled:
                return False
            store = self._get_poke_trace_store(chat_id)
            self._cleanup_poke_trace(chat_id)
            uid = str(user_id)
            exp = store.get(uid)
            if exp and exp > time.time():
                try:
                    del store[uid]
                except Exception:
                    pass
                if self.debug_mode:
                    logger.info(f"[戳过对方追踪] 命中并消费: chat={chat_id} user={uid}")
                return True
            return False
        except Exception as e:
            logger.error(f"[戳过对方追踪] 检查失败: {e}")
            return False

    # =========================================================================
    # ⏳ v1.2.0: 群聊等待窗口 - 辅助方法
    # =========================================================================

    def _should_merge_at_for_user(self, sender_id: str) -> bool:
        """判断该用户的@消息是否应被合并到窗口（而非触发即时回复）。

        仅使用初始化时读取的实例变量，不再次读取配置。

        Returns:
            True = 该用户的@消息应被合并缓存
            False = 走原有 force_complete 逻辑
        """
        if not self.group_wait_window_merge_at_messages:
            return False
        user_list = self.group_wait_window_merge_at_user_list
        if not user_list:
            return True  # 名单为空 = 对所有人生效
        if self.group_wait_window_merge_at_list_mode == "whitelist":
            return sender_id in user_list
        else:  # blacklist
            return sender_id not in user_list

    async def _maybe_intercept_for_wait_window(
        self,
        event: AstrMessageEvent,
        chat_id: str,
        is_at_message: bool,
        poke_info_for_probability,
        platform_name: str,
    ) -> bool:
        """
        检查此消息是否应被群聊等待窗口拦截（直接缓存，不走概率筛选）。

        拦截条件：
        - 该用户在本群有活跃的等待窗口
        - 本条消息不是 @消息，也不是戳一戳

        如果是 @消息且存在活跃窗口：立即结束窗口（force_complete），但不拦截，
        让 @消息走正常的快速回复流程。

        Returns:
            True = 已拦截并缓存，调用方应直接 return
            False = 未拦截，正常流程继续
        """
        sender_id = str(event.get_sender_id())
        window_key = (chat_id, sender_id)

        # 快速检查：是否有活跃窗口
        async with self._group_wait_window_lock:
            window = self._group_wait_windows.get(window_key)
            if window is None:
                return False  # 无活跃窗口，不拦截

        # 有活跃窗口 —— 处理 @消息特殊情况
        if is_at_message:
            # 判断是否为@机器人（而非@他人）
            bot_id = str(event.get_self_id())
            is_at_bot = any(
                isinstance(c, At) and str(c.qq) == bot_id for c in event.get_messages()
            )

            # 检查是否应将此@消息合并到窗口
            if is_at_bot and self._should_merge_at_for_user(sender_id):
                # 🆕 合并模式：剥离@组件，作为普通消息缓存到窗口
                # 1. 从消息链中移除指向bot的At组件
                original_chain = event.get_messages()
                filtered_chain = [
                    c
                    for c in original_chain
                    if not (isinstance(c, At) and str(c.qq) == bot_id)
                ]
                event.message_obj.message = filtered_chain
                # 2. 重建 message_str（移除@文本）
                new_text_parts = []
                for c in filtered_chain:
                    if isinstance(c, Plain):
                        new_text_parts.append(c.text)
                event.message_str = "".join(new_text_parts).strip()
                # 3. 关闭 at 标记，防止后续插件/平台当作@消息处理
                event.is_at_or_wake_command = False

                # 4. 判断剥离后是否有实际内容（文字或图片）
                remaining_text = event.message_str
                has_remaining_image = PlatformLTMHelper.has_image_in_message(event)
                if not remaining_text and not has_remaining_image:
                    # 纯空@消息（无文字、无图片）：不缓存，但更新窗口计数
                    # event 已被修改（At移除、is_at_or_wake_command=False）
                    # 后续插件看到的是空的非@消息，不会触发回复
                    async with self._group_wait_window_lock:
                        w = self._group_wait_windows.get(window_key)
                        if w:
                            w["extra_count"] += 1
                            w["deadline"] = (
                                time.time() + self.group_wait_window_timeout_ms / 1000.0
                            )
                    if self.debug_mode:
                        logger.info(
                            f"[等待窗口] 用户{sender_id}在窗口期内发送空@消息，"
                            f"已剥离@组件，不缓存但更新窗口计数"
                        )
                    return True  # 拦截，我们插件不再处理
                # 有内容（文字和/或图片）：fall through 到下方普通消息缓存分支
                if self.debug_mode:
                    _content_desc = []
                    if remaining_text:
                        _content_desc.append(f"文字: {remaining_text[:60]}...")
                    if has_remaining_image:
                        _content_desc.append("图片")
                    logger.info(
                        f"[等待窗口] 用户{sender_id}在窗口期内发送@消息，"
                        f"已剥离@组件，作为普通消息缓存 ({', '.join(_content_desc)})"
                    )
            else:
                # 原有逻辑：@他人 / 未开启合并 / 不在名单内 → force_complete
                async with self._group_wait_window_lock:
                    w = self._group_wait_windows.get(window_key)
                    if w:
                        w["force_complete"] = True
                if self.debug_mode:
                    logger.info(
                        f"[等待窗口] 用户{sender_id}在窗口期内发送@消息，"
                        f"立即结束等待，@消息走正常回复流程"
                    )
                return False  # 不拦截，让 @消息正常处理

        # 戳一戳也不拦截
        if poke_info_for_probability is not None:
            return False

        # 普通消息（含关键词触发消息）：拦截并缓存
        # 处理逻辑与概率过滤失败时的缓存路径完全一致
        try:
            original_message_text = MessageCleaner.extract_raw_message_from_event(event)

            # 让出控制权，让平台 LTM 有机会开始处理图片
            await asyncio.sleep(0)

            has_image = PlatformLTMHelper.has_image_in_message(event)
            if has_image and self.probability_filter_cache_delay > 0:
                await asyncio.sleep(self.probability_filter_cache_delay / 1000.0)

            is_pure_image = PlatformLTMHelper.is_pure_image_message(event)
            processed_text = None
            should_cache = True
            success = False

            if has_image:
                # 尝试从平台获取图片描述
                (
                    success,
                    platform_processed_text,
                ) = await PlatformLTMHelper.extract_image_caption_from_platform(
                    self.context,
                    event,
                    original_message_text,
                    max_wait=self.platform_image_caption_max_wait,
                    retry_interval=self.platform_image_caption_retry_interval,
                    fast_check_count=self.platform_image_caption_fast_check_count,
                )
                if success and platform_processed_text:
                    processed_text = platform_processed_text
                    # 🆕 将平台自动理解的图片描述保存到图片缓存（省钱!）
                    await self._save_platform_descriptions_to_cache(
                        event, platform_processed_text
                    )
                else:
                    # 🆕 v1.2.0 省钱回退：平台失败，尝试从图片缓存查找已有描述
                    cache_fallback_text = await self._try_cache_fallback_for_images(
                        event
                    )
                    if cache_fallback_text:
                        processed_text = cache_fallback_text
                        success = (
                            True  # 标记图片信息已保留（影响后续 image_retained 判断）
                        )
                        logger.info(
                            f"💰 [省钱回退-等待窗口] 从缓存恢复图片描述: {cache_fallback_text[:80]}..."
                        )
                    elif is_pure_image:
                        should_cache = False  # 纯图片且无描述，丢弃
                    else:
                        # 图文混合：过滤图片，保留文字
                        should_cache, processed_text = (
                            MessageCleaner.process_cached_message_images(
                                original_message_text
                            )
                        )
            else:
                processed_text = original_message_text
                should_cache = bool(processed_text and processed_text.strip())

            if should_cache and processed_text:
                # 表情包标记检测（与概率过滤路径相同的逻辑）
                is_emoji_message = False
                if self.enable_emoji_filter:
                    _pname_lower = platform_name.lower() if platform_name else ""
                    _is_qq = any(
                        k in _pname_lower
                        for k in ("qq", "napcat", "lagrange", "aiocqhttp", "onebot")
                    )
                    if _is_qq:
                        try:
                            is_emoji_message = EmojiDetector.is_emoji_message(event)
                        except Exception:
                            pass

                image_retained = (has_image and success) or (not has_image)
                if is_emoji_message and self.enable_emoji_filter and image_retained:
                    processed_text = EmojiDetector.add_emoji_marker(processed_text)
                    if self.debug_mode:
                        logger.info(f"  🎭 [等待窗口] 已为表情包消息添加标记")

                cached_message = {
                    "role": "user",
                    "content": processed_text,
                    "timestamp": time.time(),
                    "message_id": self._get_message_id(event),
                    "sender_id": event.get_sender_id(),
                    "sender_name": event.get_sender_name(),
                    "message_timestamp": (
                        event.message_obj.timestamp
                        if hasattr(event, "message_obj")
                        and hasattr(event.message_obj, "timestamp")
                        else None
                    ),
                    "mention_info": None,
                    # 关键词标记"打掉"：窗口期内的消息统一按普通消息处理
                    "is_at_message": False,
                    "has_trigger_keyword": False,
                    "poke_info": None,
                    "probability_filtered": False,
                    "wait_window_intercepted": True,  # 标记为等待窗口拦截的消息
                    "window_buffered": True,  # 标记为窗口缓冲消息，用于上下文分离
                    "image_urls": [],
                }
                self.cache_manager.add_to_cache(
                    chat_id, cached_message, source="等待窗口"
                )

                if self.debug_mode:
                    logger.info(
                        f"[等待窗口] 已缓存用户{sender_id}的消息: "
                        f"{processed_text[:60]}..."
                    )
            else:
                if self.debug_mode:
                    reason = "纯图片且无平台描述" if not should_cache else "消息为空"
                    logger.info(f"[等待窗口] 消息不缓存（{reason}）")

            # 更新窗口状态：extra_count++，重置 deadline
            async with self._group_wait_window_lock:
                w = self._group_wait_windows.get(window_key)
                if w:
                    w["extra_count"] += 1
                    w["deadline"] = (
                        time.time() + self.group_wait_window_timeout_ms / 1000.0
                    )
                    if self.debug_mode:
                        logger.info(
                            f"[等待窗口] 用户{sender_id}: "
                            f"extra_count={w['extra_count']}/{self._group_wait_window_max_extra}，"
                            f"deadline重置"
                        )
            return True

        except Exception as e:
            logger.warning(f"[等待窗口] 拦截消息时发生错误: {e}", exc_info=True)
            return False

    async def _run_group_wait_window(self, chat_id: str, user_id: str) -> int:
        """
        启动并运行群聊等待窗口（⏳ v1.2.0）。

        在窗口期间以 100ms 为间隔轮询，直到以下任一条件满足：
          1. force_complete = True（@消息中断）
          2. extra_count >= _group_wait_window_max_extra（额外消息已满）
          3. time.time() >= deadline（超时）
          4. 窗口令牌不匹配（被更新的调用取代）

        结束后自动清理窗口状态。
        若当前活跃窗口数已达上限，则跳过创建（直接返回，不等待）。

        Returns:
            int: 窗口期间收集到的额外消息数量（用于注意力机制补偿）
        """
        window_key = (chat_id, user_id)
        timeout_sec = self.group_wait_window_timeout_ms / 1000.0
        _extra_count = 0  # 🔧 追踪窗口期间收集的额外消息数（用于注意力机制补偿）

        # 检查并发窗口数量限制，并原子完成"检查+创建+获取令牌"
        async with self._group_wait_window_lock:
            # 如果该用户已有活跃窗口，直接接管（不受并发上限限制）
            existing = self._group_wait_windows.get(window_key)
            if existing is None:
                # 无活跃窗口：检查并发上限
                active_count = len(self._group_wait_windows)
                if active_count >= self.group_wait_window_max_users:
                    logger.info(
                        f"[等待窗口] 当前活跃窗口数({active_count})已达上限"
                        f"({self.group_wait_window_max_users})，"
                        f"用户{user_id}跳过等待窗口直接处理"
                    )
                    return 0
                active_count_for_log = active_count + 1
            else:
                active_count_for_log = len(self._group_wait_windows)

            # 分配唯一令牌（无论新建还是接管，都重新发令牌）
            self._group_wait_window_counter += 1
            my_token = self._group_wait_window_counter

            # 创建/覆盖窗口（接管时旧循环会因令牌不匹配自动退出）
            self._group_wait_windows[window_key] = {
                "extra_count": 0,
                "deadline": time.time() + timeout_sec,
                "force_complete": False,
                "token": my_token,
            }

        logger.info(
            f"[等待窗口] 为用户{user_id}创建窗口（超时={self.group_wait_window_timeout_ms}ms，"
            f"最大额外={self._group_wait_window_max_extra}条，"
            f"当前活跃={active_count_for_log}/{self.group_wait_window_max_users}，"
            f"令牌={my_token}）"
        )

        # 轮询循环（100ms 间隔）
        _POLL_INTERVAL = 0.1
        try:
            while True:
                await asyncio.sleep(_POLL_INTERVAL)
                async with self._group_wait_window_lock:
                    w = self._group_wait_windows.get(window_key)
                    if w is None:
                        break
                    # 令牌不匹配：该 key 已被新调用接管，旧循环退出（不清理）
                    if w.get("token") != my_token:
                        if self.debug_mode:
                            logger.info(
                                f"[等待窗口] 用户{user_id}：令牌失效（旧={my_token}，当前={w.get('token')}），旧循环退出"
                            )
                        return 0  # 直接 return，跳过 finally 的清理（令牌失效，不计数）
                    if w.get("force_complete"):
                        logger.info(
                            f"[等待窗口] 用户{user_id}：收到@消息信号，提前结束等待"
                        )
                        break
                    if w["extra_count"] >= self._group_wait_window_max_extra:
                        logger.info(
                            f"[等待窗口] 用户{user_id}：已收集{w['extra_count']}条额外消息，"
                            f"达到上限，继续处理"
                        )
                        break
                    if time.time() >= w["deadline"]:
                        logger.info(
                            f"[等待窗口] 用户{user_id}：超时，"
                            f"共收集{w['extra_count']}条额外消息，继续处理"
                        )
                        break
        finally:
            # 只有持有当前令牌的循环才清理窗口（防止误删新窗口）
            async with self._group_wait_window_lock:
                w = self._group_wait_windows.get(window_key)
                if w is not None and w.get("token") == my_token:
                    _extra_count = w["extra_count"]  # 🔧 在清理前捕获最终计数
                    self._group_wait_windows.pop(window_key, None)

        return _extra_count

    async def _process_message(self, event: AstrMessageEvent):
        """
        消息处理主流程

        协调各个子步骤完成消息处理

        流程优化说明：
        - 概率判断在最前面，快速过滤不需要处理的消息
        - 避免对不需要处理的消息进行图片识别等耗时操作

        Args:
            event: 消息事件对象
        """
        _process_start_time = time.time()

        # 步骤1: 执行初始检查（最基本的过滤）
        (
            should_continue,
            platform_name,
            is_private,
            chat_id,
        ) = await self._perform_initial_checks(event)
        if not should_continue:
            return

        # 🆕 v1.0.2: 记录消息（用于频率调整统计）
        if self.frequency_adjuster_enabled and self.frequency_adjuster:
            # 使用完整的会话标识，确保不同会话的状态隔离
            chat_key = ProbabilityManager.get_chat_key(
                platform_name, is_private, chat_id
            )
            self.frequency_adjuster.record_message(chat_key)

        # 🆕 v1.1.0: 记录用户消息（用于主动对话功能）
        if self.proactive_enabled:
            chat_key = ProbabilityManager.get_chat_key(
                platform_name, is_private, chat_id
            )

            # 🆕 v1.2.0: 检测是否是对主动对话的成功回复
            if self.enable_adaptive_proactive:
                state = ProactiveChatManager.get_chat_state(chat_key)

                # 🔒 严格检查：主动对话必须处于活跃状态
                # 这是防误判的核心：只有主动对话真正发送成功后，proactive_active才为True
                proactive_active = state.get("proactive_active", False)

                if not proactive_active:
                    # 主动对话未激活，直接跳过所有检测
                    # 这避免了：
                    # 1. 从未触发过主动对话时的误判
                    # 2. 主动对话发送失败时的误判
                    # 3. 已判定失败/成功后的误判
                    # 4. 普通回复模式下的误判
                    if self.debug_mode and state.get("last_proactive_time", 0) > 0:
                        logger.info(
                            f"[主动对话检测] 群{chat_key} - 主动对话未激活，跳过检测"
                        )
                else:
                    # 主动对话已激活，可以进行检测
                    last_proactive_time = state.get("last_proactive_time", 0)
                    current_time = time.time()
                    outcome_recorded = state.get("proactive_outcome_recorded", False)

                    # 🔒 检查是否在临时提升期内（用于追踪多人回复）
                    boost_duration = self.proactive_temp_boost_duration
                    in_boost_period = (
                        last_proactive_time > 0
                        and (current_time - last_proactive_time) <= boost_duration
                    )

                    # 📊 多人回复追踪（在整个临时提升期内持续追踪）
                    if in_boost_period:
                        if not hasattr(self, "_proactive_reply_users"):
                            self._proactive_reply_users = {}

                        sender_id = event.get_sender_id()

                        # 初始化或更新追踪器
                        if chat_key not in self._proactive_reply_users:
                            self._proactive_reply_users[chat_key] = {
                                "users": set(),
                                "proactive_time": last_proactive_time,
                            }

                        # 如果是同一次主动对话，追踪用户
                        if (
                            self._proactive_reply_users[chat_key]["proactive_time"]
                            == last_proactive_time
                        ):
                            self._proactive_reply_users[chat_key]["users"].add(
                                sender_id
                            )
                        else:
                            # 新的主动对话，重置追踪
                            self._proactive_reply_users[chat_key] = {
                                "users": {sender_id},
                                "proactive_time": last_proactive_time,
                            }

                    # 📊 持续追踪多人回复（在整个提升期内）
                    # 但不在此处判定成功，等待AI真正决定回复时再判定
                    # 这避免了用户回复但AI不回复却被误判为成功的问题
                    if self.debug_mode and in_boost_period:
                        logger.debug(
                            f"[主动对话追踪] 群{chat_key} - "
                            f"用户{sender_id}在提升期内发言，持续追踪中"
                        )

            ProactiveChatManager.record_user_message(chat_key)
            # 检查并处理主动对话后的回复（新逻辑：仅在AI决定回复时由后续流程强制取消）
            ProactiveChatManager.check_and_handle_reply_after_proactive(
                chat_key, self.config, force=False
            )

        # 步骤2: 检查消息触发器（决定是否跳过概率判断）
        # 🆕 v1.2.0: 新增返回匹配到的触发关键词
        (
            is_at_message,
            has_trigger_keyword,
            matched_trigger_keyword,
        ) = await self._check_message_triggers(event)

        # 步骤2.5: 检测戳一戳信息（v1.0.9新增，在概率判断前提取）
        poke_result = self._check_poke_message(event)
        # 修复：保留完整的poke_result结构，包含is_poke字段
        poke_info_for_probability = (
            poke_result
            if poke_result.get("is_poke") and not poke_result.get("should_ignore")
            else None
        )

        # 🆕 v1.2.0: 群聊等待窗口拦截
        # 如果该用户在本群有活跃的等待窗口，将此消息直接缓存并跳过后续流程
        # - @消息：触发窗口提前结束（force_complete），自身不被拦截，正常走后续流程
        # - 关键词消息：被拦截缓存（关键词标记"打掉"），不打断窗口，不开新窗口
        # - 戳一戳：不被拦截，正常走后续流程
        # - 普通消息：被拦截缓存
        if self.enable_group_wait_window and self._group_wait_window_max_extra > 0:
            _gww_intercepted = await self._maybe_intercept_for_wait_window(
                event, chat_id, is_at_message, poke_info_for_probability, platform_name
            )
            if _gww_intercepted:
                return

        # 关键逻辑：触发关键词等同于@消息
        # 这样在 mention_only 模式下，包含关键词的消息也能正常处理图片
        should_treat_as_at = is_at_message or has_trigger_keyword

        # 只在debug模式下显示详细判断，或在特殊情况下记录
        if self.debug_mode:
            logger.info(
                f"【等同@消息】判断: {'是' if should_treat_as_at else '否'} (is_at={is_at_message}, has_keyword={has_trigger_keyword})"
            )

        # 🆕 v1.2.0: 步骤2.7: 表情包检测（在概率判断前检测，用于概率衰减和标记注入）
        # ⚠️ 平台限制：仅支持 QQ 平台（NapCat/Lagrange/aiocqhttp等OneBot协议）
        is_emoji_message = False
        if self.enable_emoji_filter:
            # 检查平台是否支持表情包检测（仅 QQ 平台）
            platform_name_lower = platform_name.lower() if platform_name else ""
            is_qq_platform = (
                "qq" in platform_name_lower
                or "napcat" in platform_name_lower
                or "lagrange" in platform_name_lower
                or "aiocqhttp" in platform_name_lower
                or "onebot" in platform_name_lower
            )

            if is_qq_platform:
                try:
                    is_emoji_message = EmojiDetector.is_emoji_message(event)
                    if is_emoji_message:
                        logger.info("【步骤2.7】🎭 检测到平台标记的表情包消息")
                    elif self.debug_mode:
                        logger.info("【步骤2.7】🎭 非表情包消息（普通图片或无图片）")
                except Exception as e:
                    # 检测失败时不影响主流程，仅记录日志
                    if self.debug_mode:
                        logger.warning(f"【步骤2.7】🎭 表情包检测失败，跳过: {e}")
            elif self.debug_mode:
                logger.info(
                    f"【步骤2.7】🎭 当前平台 ({platform_name}) 不支持表情包检测，仅支持 QQ 平台"
                )

        # 步骤3: 概率判断（第一道核心过滤，避免后续耗时处理）
        should_process = await self._check_probability_before_processing(
            event,
            platform_name,
            is_private,
            chat_id,
            is_at_message,
            has_trigger_keyword,
            poke_info_for_probability,  # 传递戳一戳信息
            is_emoji_message=is_emoji_message,  # 🆕 v1.2.0: 传递表情包检测结果
        )
        if not should_process:
            # 🆕 概率判断失败时，也进行简化的消息缓存（避免上下文断裂）
            # 🆕 v1.2.0: 尝试从平台 LTM 获取图片描述，充分利用平台的图片理解功能
            try:
                if self.debug_mode:
                    logger.info(
                        "【步骤3-缓存】概率判断失败，但仍缓存原始消息（避免上下文断裂）"
                    )

                # 提取原始消息文本（不含系统提示词
                original_message_text = MessageCleaner.extract_raw_message_from_event(
                    event
                )

                # 🔧 v1.2.0: 先让出控制权，让平台 LTM 有机会开始处理消息
                # 这是关键！asyncio.sleep(0) 会让出事件循环控制权，让其他协程（如平台 LTM）有机会执行
                await asyncio.sleep(0)

                # 检测图片，如果有图片则额外延迟，等待平台 LTM 处理
                has_image = PlatformLTMHelper.has_image_in_message(event)
                if has_image:
                    # 🔧 对于图片消息，使用配置的延迟时间
                    if self.probability_filter_cache_delay > 0:
                        await asyncio.sleep(
                            self.probability_filter_cache_delay / 1000.0
                        )

                # 🆕 v1.2.0: 检查消息是否包含图片，如果包含则尝试从平台获取图片描述
                is_pure_image = PlatformLTMHelper.is_pure_image_message(event)

                processed_text = None
                should_cache = True
                success = False  # 🔧 初始化 success 变量，用于后续日志判断

                if has_image:
                    # 消息包含图片，尝试从平台 LTM 获取图片描述
                    # 🔧 v1.2.0: 使用异步版本，支持智能等待平台处理完成，传递用户配置参数
                    (
                        success,
                        platform_processed_text,
                    ) = await PlatformLTMHelper.extract_image_caption_from_platform(
                        self.context,
                        event,
                        original_message_text,
                        max_wait=self.platform_image_caption_max_wait,
                        retry_interval=self.platform_image_caption_retry_interval,
                        fast_check_count=self.platform_image_caption_fast_check_count,
                    )

                    if success and platform_processed_text:
                        # 成功获取平台的图片描述
                        processed_text = platform_processed_text
                        logger.info(
                            f"🖼️ [概率过滤-平台图片描述] 成功提取图片描述，将缓存带描述的消息: {processed_text[:80]}..."
                        )
                        # 🆕 将平台自动理解的图片描述保存到图片缓存（省钱!）
                        await self._save_platform_descriptions_to_cache(
                            event, platform_processed_text
                        )
                    else:
                        # 平台未处理或获取失败
                        # 🆕 v1.2.0 省钱回退：尝试从图片缓存查找已有描述
                        cache_fallback_text = await self._try_cache_fallback_for_images(
                            event
                        )
                        if cache_fallback_text:
                            processed_text = cache_fallback_text
                            success = True  # 标记图片信息已保留
                            logger.info(
                                f"💰 [省钱回退-概率过滤] 从缓存恢复图片描述: {cache_fallback_text[:80]}..."
                            )
                        elif is_pure_image:
                            # 纯图片消息且平台未处理，丢弃
                            should_cache = False
                            if self.debug_mode:
                                logger.info("  纯图片消息且平台未处理图片描述，不缓存")
                        else:
                            # 图文混合消息，过滤图片只保留文字
                            should_cache, processed_text = (
                                MessageCleaner.process_cached_message_images(
                                    original_message_text
                                )
                            )
                            if self.debug_mode:
                                logger.info(
                                    f"  图文混合消息，过滤图片后: {processed_text[:80] if processed_text else '(空)'}"
                                )
                else:
                    # 不包含图片，直接使用原始文本
                    processed_text = original_message_text
                    should_cache = bool(processed_text and processed_text.strip())

                if should_cache and processed_text:  # 只缓存非空且非纯图片的消息
                    # 🆕 v1.2.0: 表情包标记注入（概率过滤缓存路径）
                    # 只有图片信息确实保留在消息中时才添加标记
                    # success=True: 平台成功处理图片，图片描述已在processed_text中
                    # has_image=False: 无图片消息，无需担心图片被过滤
                    image_retained_in_cache = (has_image and success) or (not has_image)
                    if (
                        is_emoji_message
                        and self.enable_emoji_filter
                        and image_retained_in_cache
                    ):
                        processed_text = EmojiDetector.add_emoji_marker(processed_text)
                        if self.debug_mode:
                            logger.info(
                                f"  🎭 [概率过滤-缓存] 已为表情包消息添加标记: {processed_text[:80]}..."
                            )
                    elif (
                        is_emoji_message
                        and self.enable_emoji_filter
                        and not image_retained_in_cache
                    ):
                        if self.debug_mode:
                            logger.info(
                                "  🎭 [概率过滤-缓存] 表情包图片已被过滤，跳过添加标记"
                            )

                    # 🆕 v1.2.0: 使用缓存管理器统一处理缓存
                    cached_message = {
                        "role": "user",
                        "content": processed_text,  # 使用处理后的消息（可能包含平台图片描述）
                        "timestamp": time.time(),
                        "message_id": self._get_message_id(event),
                        "sender_id": event.get_sender_id(),
                        "sender_name": event.get_sender_name(),
                        "message_timestamp": event.message_obj.timestamp
                        if hasattr(event, "message_obj")
                        and hasattr(event.message_obj, "timestamp")
                        else None,
                        "mention_info": None,  # 概率失败时简化处理
                        "is_at_message": is_at_message,
                        "has_trigger_keyword": has_trigger_keyword,
                        "poke_info": None,  # 概率失败时简化处理
                        "probability_filtered": True,  # 标记为概率筛查过滤的消息
                        "image_urls": [],  # 🔧 概率过滤时，图片已转为文字或被过滤，不保留URL
                    }

                    # 使用缓存管理器添加缓存
                    source_label = (
                        "概率过滤-带图片描述" if (has_image and success) else "概率过滤"
                    )
                    self.cache_manager.add_to_cache(
                        chat_id, cached_message, source=source_label
                    )
                else:
                    if self.debug_mode:
                        if not should_cache:
                            logger.info("  消息为纯图片，不缓存")
                        else:
                            logger.info("  处理后的消息为空，跳过缓存")

            except Exception as e:
                logger.warning(f"[概率过滤-缓存] 缓存消息失败: {e}")

            # 概率判断失败，返回（不继续处理）
            return

        # 🆕 v1.2.0: 群聊等待窗口激活
        # 普通消息/关键词消息/@消息通过后，启动等待窗口收集同一用户紧接着的多条消息
        # @消息同样激活等待窗口；戳一戳不进入等待窗口（直接处理）
        _gww_extra_count = 0  # 🔧 等待窗口收集的额外消息数（用于注意力机制补偿）
        if (
            self.enable_group_wait_window
            and poke_info_for_probability is None
            and self._group_wait_window_max_extra > 0
            and self.pending_cache_max_count > 0
        ):
            _gww_sender_id = str(event.get_sender_id())
            # 🔧 极短延迟 + 重检：消除极低概率的并发建窗竞态
            # 场景：两条消息均在对方建窗前通过了插入点A，到达此处时各自尝试建窗
            # 延迟 30ms 后，先到的消息已建好窗口，后到的重检时发现窗口存在
            # 改为以"额外消息"身份被吸收，从而确保只有一条消息继续走完整流程
            await asyncio.sleep(0.03)
            _gww_recheck = await self._maybe_intercept_for_wait_window(
                event, chat_id, is_at_message, poke_info_for_probability, platform_name
            )
            if _gww_recheck:
                return
            _gww_extra_count = await self._run_group_wait_window(
                chat_id, _gww_sender_id
            )

        # 步骤3.5: 检测@提及信息（在图片处理之前，避免不必要的开销）
        mention_info = await self._check_mention_others(event)

        # 步骤3.6: 使用之前检测的戳一戳信息（避免重复检测）
        # 提取内嵌的poke_info用于后续处理
        poke_info = (
            poke_info_for_probability.get("poke_info")
            if poke_info_for_probability
            else None
        )

        # 收到戳一戳后的反戳逻辑（放在概率判断之后）：
        # 若命中概率，则反戳并丢弃本插件处理中剩余步骤
        if poke_info:
            reversed_and_discarded = await self._maybe_reverse_poke_on_poke(
                event, poke_info, is_private, chat_id
            )
            if reversed_and_discarded:
                # 不拦截消息传播，仅本插件结束处理
                return

        # 🆕 @消息提前检查是否已被其他插件处理，避免后续耗时操作（如图片转文字）
        # 注意：只检查真正的@消息，不检查触发关键词消息
        if is_at_message:
            if ReplyHandler.check_if_already_replied(event):
                logger.info("@消息已被其他插件处理,跳过后续流程")
                if self.debug_mode:
                    logger.info("【步骤3.7】@消息已被处理,退出")
                    logger.info("=" * 60)
                return

        # 步骤4-6: 处理消息内容（图片处理等耗时操作）
        # 使用 should_treat_as_at 作为 is_at_message 参与后续元数据/触发方式处理，
        # 同时通过 raw_is_at_message 传入真实的 @ 状态，便于图片识别范围精细控制
        result = await self._process_message_content(
            event,
            chat_id,
            should_treat_as_at,
            mention_info,
            has_trigger_keyword,
            poke_info,
            raw_is_at_message=is_at_message,
            is_emoji_message=is_emoji_message,  # 🆕 v1.2.0: 传递表情包检测结果
        )
        if not result[0]:  # should_continue为False
            return

        (
            _,
            original_message_text,
            message_text,
            formatted_context,
            image_urls,
            history_messages,
            cached_message_data,  # 🆕 v1.2.0: 待缓存的消息数据
            emoji_marker_applied,  # 🆕 v1.2.0: 表情包标记是否已添加
        ) = result

        merged_image_urls = image_urls or []
        try:
            if (
                self.enable_image_processing
                and not self.image_to_text_provider_id
                and chat_id in self.pending_messages_cache
            ):
                for _cached in self.pending_messages_cache[chat_id]:
                    if isinstance(_cached, dict):
                        _urls = _cached.get("image_urls") or []
                        if _urls:
                            merged_image_urls.extend(_urls)

                if merged_image_urls:
                    _seen_urls = set()
                    _dedup_urls = []
                    for _u in merged_image_urls:
                        if _u and _u not in _seen_urls:
                            _seen_urls.add(_u)
                            _dedup_urls.append(_u)
                    merged_image_urls = _dedup_urls
        except Exception as e:
            logger.warning(f"[图片缓存] 合并图片URL失败: {e}")

        # 🔧 修复并发竞争：在AI决策判断之前就提取缓存副本
        # 避免在决策AI判断期间（可能耗时6-8秒），缓存被其他并发消息清空
        # 🆕 v1.2.0: 使用 cached_message_data 作为当前消息的缓存副本
        current_message_cache = cached_message_data
        # 提前获取 message_id，用于存储缓存快照
        early_message_id = self._get_message_id(event)
        try:
            if current_message_cache:
                # 🔧 存储到实例变量，供 after_message_sent 使用
                self._message_cache_snapshots[early_message_id] = copy.deepcopy(
                    current_message_cache
                )
                if self.debug_mode:
                    logger.info(
                        f"🔒 [并发保护] 已保存当前消息缓存副本: {current_message_cache.get('content', '')[:100]}..."
                    )
        except Exception as e:
            logger.warning(f"[并发保护] 保存缓存副本失败: {e}")

        # 步骤7: AI决策判断（第二道核心过滤）
        # 🆕 新成员入群消息 skip_all 模式：跳过AI决策，强制处理
        _welcome_skip_all = (
            (
                event.get_extra("is_welcome_message")
                and event.get_extra("welcome_message_mode") == "skip_all"
            )
            if hasattr(event, "get_extra")
            else False
        )

        if _welcome_skip_all:
            should_reply = True
            if self.debug_mode:
                logger.info(
                    "【步骤7】新成员入群消息(skip_all模式)，跳过AI决策，强制处理"
                )
        else:
            # 🆕 v1.2.0: 传递匹配到的触发关键词
            # 🆕 v1.2.0: 传递原始消息文本用于关键词检测
            should_reply = await self._check_ai_decision(
                event,
                formatted_context,
                is_at_message,
                has_trigger_keyword,
                merged_image_urls,
                matched_trigger_keyword=matched_trigger_keyword,
                original_message_text=original_message_text,
            )

        if not should_reply:
            # 🆕 v1.2.0: AI决策判定不通过时，才将消息添加到缓存
            # 这样可以避免需要正常处理的消息被错误缓存
            if cached_message_data:
                self.cache_manager.add_to_cache(
                    chat_id, cached_message_data, source="AI决策过滤"
                )
                logger.info("📦 决策AI判断: 不回复此消息，已缓存消息，等待后续转正")
            else:
                logger.info("📦 决策AI判断: 不回复此消息，无待缓存数据")

            if self.debug_mode:
                # 验证消息确实在缓存中
                cache_count = self.cache_manager.get_cache_count(chat_id)
                logger.info(f"  [缓存验证] 当前会话缓存数量: {cache_count} 条")

            # 🔧 清理缓存快照（不回复时 after_message_sent 不会被调用）
            self._message_cache_snapshots.pop(early_message_id, None)

            if self.debug_mode:
                logger.info("=" * 60)
            return

        # 🔧 修复：使用message_id作为键，避免同一会话中多条消息并发时标记冲突
        message_id = self._get_message_id(event)

        # 🔧 并发保护：使用锁保护检查-标记流程，避免竞态条件
        # 如果有其他消息在处理，循环等待直到前一个消息完成或达到最大等待次数
        max_wait_loops = self.concurrent_wait_max_loops  # 最大等待循环次数
        wait_interval = self.concurrent_wait_interval  # 每次循环等待秒数

        for loop_count in range(max_wait_loops):
            # 🔒 获取锁进行原子性检查和标记
            async with self.concurrent_lock:
                # 🔧 修复：检查相同message_id是否已在处理中（防止平台重复推送同一消息）
                if message_id in self.processing_sessions:
                    logger.info(
                        f"🚫 [并发去重] 消息 {message_id[:30]}... 已在处理中，跳过重复处理"
                    )
                    # 🔧 阻止框架的默认LLM调用（仅阻止默认链路，不影响其他插件）
                    event.call_llm = True
                    return

                existing_processing = [
                    msg_id
                    for msg_id, cid in self.processing_sessions.items()
                    if cid == chat_id and msg_id != message_id
                ]

                if not existing_processing:
                    # 没有其他消息在处理，立即标记并退出
                    self.processing_sessions[message_id] = chat_id
                    if self.debug_mode:
                        logger.info(f"  已标记消息 {message_id[:30]}... 为本插件处理中")
                    break

            # 🔓 释放锁后再进行等待（避免阻塞其他消息）
            if loop_count == 0:
                logger.warning(
                    f"⚠️ [并发检测] 会话 {chat_id} 中有 {len(existing_processing)} 条消息正在处理中，"
                    f"开始等待（最多 {max_wait_loops} 次，每次 {wait_interval} 秒）..."
                )

            await asyncio.sleep(wait_interval)

            if self.debug_mode:
                logger.info(
                    f"  [并发等待] 第 {loop_count + 1}/{max_wait_loops} 次检测..."
                )
        else:
            # 循环结束仍有消息在处理，强制标记并继续
            async with self.concurrent_lock:
                still_processing = [
                    msg_id
                    for msg_id, cid in self.processing_sessions.items()
                    if cid == chat_id and msg_id != message_id
                ]
                if still_processing:
                    logger.warning(
                        f"⚠️ [并发警告] 等待 {max_wait_loops * wait_interval:.1f} 秒后仍有 "
                        f"{len(still_processing)} 条消息在处理，强制继续执行（可能产生竞争）"
                    )
                # 即使有竞争也要标记，否则这条消息无法被清理
                self.processing_sessions[message_id] = chat_id
                if self.debug_mode:
                    logger.info(f"  已标记消息 {message_id[:30]}... 为本插件处理中")

        # 🆕 在读空气AI判定确认回复后，检查主动对话成功并重置计时器
        # 关键逻辑：只有AI真正决定回复时，才判定主动对话成功
        if should_reply and self.proactive_enabled:
            chat_key = ProbabilityManager.get_chat_key(
                platform_name, is_private, chat_id
            )

            # ✅ 在AI决定回复时，检查是否为主动对话成功
            state = ProactiveChatManager.get_chat_state(chat_key)
            proactive_active = state.get("proactive_active", False)
            outcome_recorded = state.get("proactive_outcome_recorded", False)
            last_proactive_time = state.get("last_proactive_time", 0)
            current_time = time.time()

            # 检查是否在提升期内
            boost_duration = self.proactive_temp_boost_duration
            in_boost_period = (current_time - last_proactive_time) <= boost_duration

            # 只有主动对话活跃、未判定过、且在提升期内，才判定为成功
            if proactive_active and not outcome_recorded and in_boost_period:
                # 检测是否快速回复（30秒内）
                is_quick_reply = (current_time - last_proactive_time) <= 30

                # 检测是否多人回复（基于追踪器）
                is_multi_user = False
                if chat_key in self._proactive_reply_users:
                    if (
                        self._proactive_reply_users[chat_key]["proactive_time"]
                        == last_proactive_time
                    ):
                        is_multi_user = (
                            len(self._proactive_reply_users[chat_key]["users"]) >= 2
                        )

                # 记录成功互动（AI真正决定回复，才算成功）
                ProactiveChatManager.record_proactive_success(
                    chat_key, self.config, is_quick_reply, is_multi_user
                )

                if self.debug_mode:
                    logger.info(
                        f"✅ [主动对话成功] 群{chat_key} - "
                        f"AI决定回复，快速回复={is_quick_reply}, 多人回复={is_multi_user}"
                    )

            # 取消主动对话的临时概率提升与连续尝试（AI已决定回复）
            ProactiveChatManager.check_and_handle_reply_after_proactive(
                chat_key, self.config, force=True
            )
            ProactiveChatManager.record_bot_reply(chat_key, is_proactive=False)
            if self.debug_mode:
                logger.info(f"[主动对话] 读空气AI判定确认回复，已重置主动对话计时器")

            # 🆕 v1.2.1: 记录回复到密度管理器（主动对话确认回复）
            if self.enable_reply_density_limit:
                try:
                    await ReplyDensityManager.record_reply(chat_key)
                except Exception as e:
                    if self.debug_mode:
                        logger.warning(f"[回复密度] 记录回复失败: {e}")

        # 🆕 v1.2.0: 冷却解除检测 (Requirements 2.1, 2.2)
        # 当AI决定回复时，尝试解除用户的冷却状态
        if should_reply and self.cooldown_enabled:
            try:
                chat_key = ProbabilityManager.get_chat_key(
                    platform_name, is_private, chat_id
                )
                user_id = event.get_sender_id()

                # 确定触发类型
                if has_trigger_keyword:
                    trigger_type = "keyword"
                elif is_at_message:
                    trigger_type = "at"
                else:
                    trigger_type = "normal"

                # 尝试解除冷却状态
                released = await CooldownManager.try_release_cooldown_on_reply(
                    chat_key, user_id, trigger_type
                )

                if released:
                    logger.info(
                        f"🧊 [冷却解除] 用户 {event.get_sender_name()}(ID:{user_id}) "
                        f"已从冷却列表移除，触发方式: {trigger_type}"
                    )
            except Exception as e:
                logger.warning(f"[冷却解除] 检测失败: {e}")

        # 🆕 v1.2.0: 对话疲劳重置（在AI决策确认回复后、生成回复前执行）
        # 重要：必须在 record_replied_user() 之前执行，否则会先累加再重置
        # 只有 @消息 或 关键词触发 才重置疲劳状态（表示用户主动想继续聊天）
        if (
            should_reply
            and self.enable_conversation_fatigue
            and self.enable_attention_mechanism
        ):
            if is_at_message or has_trigger_keyword:
                try:
                    user_id = event.get_sender_id()
                    user_name = event.get_sender_name() or "未知用户"
                    await AttentionManager.reset_consecutive_replies(
                        platform_name, is_private, chat_id, user_id
                    )
                    if self.debug_mode:
                        trigger_reason = "@消息" if is_at_message else "关键词"
                        logger.info(
                            f"[对话疲劳] 用户 {user_name} 通过{trigger_reason}主动触发，"
                            f"已重置连续对话轮次（在生成回复前）"
                        )
                except Exception as e:
                    if self.debug_mode:
                        logger.warning(f"[对话疲劳] 重置连续对话轮次失败: {e}")

        # 步骤10-15: 生成并发送回复
        # 注意：current_message_cache 已在AI决策判断之前提取

        # 🆕 v1.2.0: 获取对话疲劳信息（用于生成收尾提示）
        conversation_fatigue_info = None
        if self.enable_conversation_fatigue and self.enable_attention_mechanism:
            try:
                user_id = event.get_sender_id()
                conversation_fatigue_info = (
                    await AttentionManager.get_conversation_fatigue_info(
                        platform_name, is_private, chat_id, user_id
                    )
                )
            except Exception as e:
                if self.debug_mode:
                    logger.warning(f"[对话疲劳] 获取疲劳信息失败: {e}")

        # 🆕 v1.2.0: 准备疲劳信息用于回复AI（添加收尾提示的随机判断）
        reply_fatigue_info = None
        if conversation_fatigue_info and conversation_fatigue_info.get(
            "enabled", False
        ):
            fatigue_level = conversation_fatigue_info.get("fatigue_level", "none")
            # 只有中度或重度疲劳时才可能添加收尾提示
            if fatigue_level in ("medium", "heavy"):
                import random

                # 根据配置的概率决定是否添加收尾提示
                closing_probability = self.fatigue_closing_probability
                should_add_closing = random.random() < closing_probability
                if should_add_closing:
                    reply_fatigue_info = {
                        **conversation_fatigue_info,
                        "should_add_closing_hint": True,
                    }
                    if self.debug_mode:
                        logger.info(
                            f"[对话疲劳] 触发收尾提示（概率={closing_probability:.0%}），"
                            f"疲劳等级={fatigue_level}"
                        )

        # 🆕 v1.2.0: 表情包标记回退逻辑（处理跳过路径）
        # 当消息通过关键词或@触发跳过了概率筛选和图片处理，emoji_marker_applied 为 False
        # 此时需要检查是否需要补充添加表情包标记
        if is_emoji_message and self.enable_emoji_filter and not emoji_marker_applied:
            # 检查是否真的需要添加标记：
            # 1. 如果有图片 URL（多模态路径），说明图片信息保留
            # 2. 如果 message_text 中包含图片描述标记（图片转文字路径），说明图片信息保留
            has_image_info = bool(merged_image_urls) or (
                "[图片内容:" in message_text if message_text else False
            )

            if has_image_info and message_text and EMOJI_MARKER not in message_text:
                # 需要添加表情包标记
                message_text = EmojiDetector.add_emoji_marker(message_text)
                # 重新格式化上下文（因为 formatted_context 包含了 message_text）
                bot_id = event.get_self_id()
                formatted_context = await ContextManager.format_context_for_ai(
                    history_messages,
                    message_text,  # 使用添加了标记的消息
                    bot_id,
                    include_timestamp=self.include_timestamp,
                    include_sender_info=self.include_sender_info,
                    window_buffered_messages=self.cache_manager.get_window_buffered_messages(
                        chat_id
                    ),
                )
                emoji_marker_applied = True
                if self.debug_mode:
                    logger.info(
                        f"【回退路径】🎭 检测到跳过路径的表情包消息，已补充添加标记: {message_text[:100]}..."
                    )
            elif has_image_info and self.debug_mode:
                if EMOJI_MARKER in (message_text or ""):
                    logger.info("【回退路径】🎭 表情包标记已存在，跳过重复添加")
                elif not message_text:
                    logger.info(
                        "【回退路径】🎭 消息文本为空（纯图片多模态），标记将在 cached_message 中"
                    )
            elif not has_image_info and self.debug_mode:
                logger.info("【回退路径】🎭 表情包图片信息已被过滤，跳过添加标记")

        async for result in self._generate_and_send_reply(
            event,
            formatted_context,
            message_text,
            platform_name,
            is_private,
            chat_id,
            is_at_message,
            has_trigger_keyword,  # 🆕 v1.0.4: 传递触发方式信息
            merged_image_urls,  # 传递图片URL列表（用于多模态AI）
            history_messages,  # 🔧 修复：传递历史消息用于构建contexts
            current_message_cache,  # 🔧 修复：传递当前消息缓存副本，避免并发竞争
            reply_fatigue_info,  # 🆕 v1.2.0: 传递疲劳信息用于收尾提示
            wait_window_extra_count=_gww_extra_count,  # 🔧 等待窗口额外消息数（注意力补偿）
        ):
            yield result

    @filter.on_llm_request(priority=-1)
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """
        🆕 v1.2.0: LLM 请求钩子 - 处理插件与平台/其他插件的上下文冲突

        优先级设置为 -1（较低），确保在其他插件（如 emotionai，priority=100000）
        和平台 LTM（priority=0）之后执行

        执行顺序：emotionai(100000) -> 平台LTM(0) -> 本插件(-1)

        当检测到请求来自本插件时（通过 PLUGIN_REQUEST_MARKER 标记）：
        1. 使用插件自己的上下文替换平台 LTM 注入的上下文
        2. 保留其他插件（如 emotionai）注入的 system_prompt 内容

        这样既能让其他插件的钩子生效，又能避免与平台 LTM 的上下文冲突
        """
        from .utils.reply_handler import (
            PLUGIN_REQUEST_MARKER,
            PLUGIN_CUSTOM_CONTEXTS,
            PLUGIN_CUSTOM_SYSTEM_PROMPT,
            PLUGIN_CUSTOM_PROMPT,
            PLUGIN_IMAGE_URLS,
            PLUGIN_FUNC_TOOL,
            PLUGIN_CURRENT_MESSAGE,
        )

        # 检查是否是来自本插件的请求
        is_plugin_request = event.get_extra(PLUGIN_REQUEST_MARKER, False)
        if not is_plugin_request:
            # 不是本插件的请求，不做任何处理
            return

        self._check_compliance_status()

        if self.debug_mode:
            logger.info(
                "🔧 [on_llm_request] 检测到本插件的 LLM 请求，开始处理上下文冲突..."
            )

        # 获取插件存储的自定义数据
        plugin_contexts = event.get_extra(PLUGIN_CUSTOM_CONTEXTS, [])
        plugin_system_prompt = event.get_extra(PLUGIN_CUSTOM_SYSTEM_PROMPT, "")
        plugin_prompt = event.get_extra(PLUGIN_CUSTOM_PROMPT, "")
        plugin_image_urls = event.get_extra(PLUGIN_IMAGE_URLS, [])

        # 🔧 关键：保留其他插件注入的 system_prompt 内容
        # 其他插件可能在 system_prompt 前面（prepend）或后面（append）追加内容
        # 例如 Favour Ultra 会 prepend 好感度规则，emotionai 会 append 情感指令
        # 我们需要保留这些内容，但移除平台重复注入的 persona 和 LTM 聊天记录
        import re

        other_plugin_additions = ""
        if req.system_prompt and plugin_system_prompt:
            if plugin_system_prompt in req.system_prompt:
                # 从当前 system_prompt 中移除所有本插件的原始 prompt
                # 使用 replace 无限制，移除所有出现（包括平台 ProcessLLMRequest 重复注入的）
                other_plugin_additions = req.system_prompt.replace(
                    plugin_system_prompt, ""
                )

                # 🆕 移除平台 LTM 注入的群聊历史记录（我们插件自己管理上下文）
                # LTM 会追加类似 "You are now in a chatroom. The chat history is as follows: \n..." 的内容
                # 注意：使用保守的匹配策略，只匹配到下一个 "\n\n" 为止，避免误删其他插件的内容
                # 其他插件（如 FavourPro、SelfLearning）通常用 "\n\n" 作为分隔符
                ltm_pattern = r"You are now in a chatroom\. The chat history is as follows:\s*[^\n]*(?:\n(?!\n)[^\n]*)*"
                other_plugin_additions = re.sub(ltm_pattern, "", other_plugin_additions)

                # 清理多余的换行符和空白
                other_plugin_additions = re.sub(
                    r"\n{3,}", "\n\n", other_plugin_additions
                ).strip()

                if self.debug_mode and other_plugin_additions:
                    logger.info(
                        f"  检测到其他插件注入的 system_prompt 内容，长度: {len(other_plugin_additions)}"
                    )
            elif len(req.system_prompt) > len(plugin_system_prompt):
                # 插件原始 prompt 不在当前 system_prompt 中（可能被平台 LTM 整体替换）
                # 回退：将整个当前 system_prompt 与插件 prompt 的差异部分视为其他插件内容
                other_plugin_additions = req.system_prompt
                if self.debug_mode:
                    logger.info(
                        f"  插件原始 prompt 未在当前 system_prompt 中找到，保留全部当前内容作为其他插件注入"
                    )

        # 🔧 使用插件自己的上下文替换平台 LTM 注入的上下文
        # 平台 LTM 的 on_req_llm 方法会修改 req.contexts 和 req.system_prompt
        # 我们需要恢复插件自己的设置
        req.contexts = plugin_contexts
        # 🔧 把 req.prompt 从短消息（当前用户消息原文，用于向量检索类插件的召回）
        #    换回完整的 full_prompt（含历史上下文+系统指令），供 AI 推理使用。
        #    其他插件（如 livingmemory，priority=0）已先执行，拿到的是短消息，
        #    向量检索正常工作，不会触发 token 超限截断警告。
        req.prompt = plugin_prompt
        req.image_urls = plugin_image_urls

        # 🔧 修复：用插件自身保存的工具集替换框架注入的工具
        # 新版 AstrBot (>=4.14) 的 build_main_agent 会自动注入 shell/python/cron/send_message 等工具，
        # 这些工具会导致 LLM 进入工具调用循环从而卡死。
        # 旧版 AstrBot (<=4.13) 中 func_tool_manager 参数直接生效，不存在此问题。
        # 这里统一恢复为插件保存的 ToolSet（由 reply_handler 中 get_full_tool_set() 获取），
        # 确保两个版本行为一致：只保留插件注册的工具，移除框架自动注入的工具。
        plugin_tool_set = event.get_extra(PLUGIN_FUNC_TOOL)
        req.func_tool = plugin_tool_set  # 可能是 ToolSet 或 None（获取失败时）

        # 🔧 合并 system_prompt：插件基础 + 其他插件注入的内容
        if other_plugin_additions:
            req.system_prompt = f"{plugin_system_prompt}\n{other_plugin_additions}"
        else:
            req.system_prompt = plugin_system_prompt

        # 🔧 修复：注入 Skills 提示词，避免插件接管 LLM 请求后丢失技能识别
        # 原因：插件通过 event.request_llm() 创建的 ProviderRequest 没有 conversation 对象，
        # 导致框架的 _ensure_persona_and_skills() 跳过执行，Skills 提示词不会被注入。
        # 这里手动加载活跃的 Skills 并追加到 system_prompt 中。
        try:
            from astrbot.core.skills.skill_manager import (
                SkillManager,
                build_skills_prompt,
            )

            skill_manager = SkillManager()
            skills = skill_manager.list_skills(active_only=True)
            if skills:
                skills_prompt = build_skills_prompt(skills)
                req.system_prompt += f"\n{skills_prompt}\n"
                if self.debug_mode:
                    logger.info(f"  ✅ 已注入 Skills 提示词，技能数量: {len(skills)}")
        except Exception as e:
            logger.warning(f"⚠️ 注入 Skills 提示词时出错（不影响主流程）: {e}")

        if self.debug_mode:
            logger.info(f"  ✅ 已恢复插件自定义上下文:")
            logger.info(f"    - contexts 数量: {len(req.contexts)}")
            logger.info(f"    - system_prompt 长度: {len(req.system_prompt)}")
            logger.info(f"    - prompt 长度: {len(req.prompt)}")
            logger.info(
                f"    - image_urls 数量: {len(req.image_urls) if req.image_urls else 0}"
            )

        # 🔧 修复：处理完成后立即清理event.extra字段，防止event对象污染导致上下文混乱
        # 背景：平台在网络异常等特殊情况下可能复用event对象，如果不清理extra字段，
        # 可能导致后续请求读取到错误的上下文数据，从而出现AI答非所问的问题
        try:
            event.set_extra(PLUGIN_REQUEST_MARKER, None)
            event.set_extra(PLUGIN_CUSTOM_CONTEXTS, None)
            event.set_extra(PLUGIN_CUSTOM_SYSTEM_PROMPT, None)
            event.set_extra(PLUGIN_CUSTOM_PROMPT, None)
            event.set_extra(PLUGIN_IMAGE_URLS, None)
            event.set_extra(PLUGIN_FUNC_TOOL, None)
            event.set_extra(PLUGIN_CURRENT_MESSAGE, None)
            # 简化日志：非debug模式下也显示，方便监控安全机制
            logger.info("[安全] 已清理LLM请求上下文缓存")
        except Exception as e:
            # 清理失败不影响主流程，仅记录警告
            logger.warning(f"⚠️ 清理event.extra字段时发生错误: {e}")

    @filter.on_llm_response(priority=-1)
    async def on_llm_response(self, event: AstrMessageEvent, response):
        """
        🔧 多轮工具调用修复：agent完成信号

        当agent真正完成时（所有工具调用结束，不再有后续LLM调用），
        AstrBot框架触发此钩子（在on_agent_done中调用）。

        此钩子在最后一次 after_message_sent 之前触发，
        用于设置标志，告知 after_message_sent 可以最终保存所有累积的回复。

        对于agent最终没有文本输出的情况（如工具直接返回结果），
        此处还负责将之前累积的中间文本保存到历史。
        """
        try:
            message_id = self._get_message_id(event)

            # 仅处理由本插件触发的消息
            if message_id not in self.processing_sessions:
                return

            # 设置agent完成标志
            self._agent_done_flags.add(message_id)

            if self.debug_mode:
                pending_count = len(self._pending_bot_replies.get(message_id, []))
                logger.info(
                    f"[on_llm_response] agent已完成，message_id={message_id[:30]}...，"
                    f"已累积 {pending_count} 段回复文本"
                )

            # 🔧 边界情况处理：如果agent完成但最终response没有文本
            # （例如工具直接发送结果），而之前有累积的中间文本，
            # 需要在此处触发保存，因为不会再有 after_message_sent 调用
            has_final_text = bool(
                response
                and (
                    getattr(response, "completion_text", None)
                    or getattr(response, "result_chain", None)
                )
            )
            pending_texts = self._pending_bot_replies.get(message_id, [])

            if not has_final_text and pending_texts:
                # agent完成，但没有最终文本输出，且有之前累积的中间文本
                # 需要在此保存，因为不会再有 after_message_sent
                logger.info(
                    f"[on_llm_response] agent完成但无最终文本，保存 {len(pending_texts)} 段累积文本"
                )
                await self._finalize_bot_reply_save(event, message_id)

        except Exception as e:
            logger.error(f"[on_llm_response] 处理失败: {e}", exc_info=True)

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        """
        在最终结果装饰阶段进行处理：
        - 仅处理由本插件标记的消息（processing_sessions）
        - 仅处理 LLM 生成的最终文本结果
        - 应用输出内容过滤（去除敏感词等）
        - 应用错字模拟（增加真实感）
        - 应用延迟模拟（模拟打字时间）
        - 检查重复消息（若与最近回复重复，清空结果以跳过发送）
        """
        try:
            platform_name = event.get_platform_name()
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            # 🔧 修复：使用message_id作为键进行检查
            message_id = self._get_message_id(event)

            # 仅处理由本插件触发的消息
            if message_id not in self.processing_sessions:
                return

            result = event.get_result()
            if not result or not hasattr(result, "chain") or not result.chain:
                return

            # 仅处理 LLM 最终结果（非流式片段）
            if not result.is_llm_result():
                return

            # 提取纯文本
            reply_text = "".join(
                [comp.text for comp in result.chain if hasattr(comp, "text")]
            ).strip()
            if not reply_text:
                return

            self.raw_reply_cache[message_id] = reply_text

            # 🔧 多轮工具调用支持：累积原始回复文本
            if message_id not in self._pending_bot_replies:
                self._pending_bot_replies[message_id] = []
            self._pending_bot_replies[message_id].append(reply_text)

            # 🆕 v1.2.0: 应用输出内容过滤（独立于保存过滤）
            filtered_reply_text = reply_text
            try:
                filtered_reply_text = self.content_filter.process_for_output(reply_text)
            except Exception:
                logger.error("[输出过滤] 过滤时发生异常，将使用原始内容", exc_info=True)
            if filtered_reply_text != reply_text:
                logger.info(
                    f"[输出过滤] 已过滤AI回复，原长度: {len(reply_text)}, 过滤后: {len(filtered_reply_text)}"
                )
                # 更新 result 中的文本内容
                # 🔧 修复：需要处理所有文本组件，而不是只处理第一个
                first_text_comp = True
                for comp in result.chain:
                    if hasattr(comp, "text"):
                        if first_text_comp:
                            # 第一个文本组件：设置为过滤后的完整文本
                            comp.text = filtered_reply_text
                            first_text_comp = False
                        else:
                            # 其他文本组件：清空内容（避免重复输出）
                            comp.text = ""
                reply_text = filtered_reply_text

            if not reply_text:
                # 过滤后为空，清空结果
                if self.debug_mode:
                    logger.info("[输出过滤] 过滤后内容为空，跳过发送")
                event.clear_result()
                if message_id in self.raw_reply_cache:
                    del self.raw_reply_cache[message_id]
                return

            # 🔧 重要：重复检测必须在错字模拟之前执行，基于原始内容检测
            # 清理过期缓存并进行重复检查（使用可配置参数）
            if self.enable_duplicate_filter:
                now_ts = time.time()
                if chat_id not in self.recent_replies_cache:
                    self.recent_replies_cache[chat_id] = []

                # 根据配置决定是否启用时效性过滤
                if self.enable_duplicate_time_limit:
                    time_limit = max(60, self.duplicate_filter_time_limit)
                    self.recent_replies_cache[chat_id] = [
                        r
                        for r in self.recent_replies_cache[chat_id]
                        if now_ts - r.get("timestamp", 0) < time_limit
                    ]

                # 检查是否与最近N条回复重复（使用配置的条数）
                check_count = max(1, self.duplicate_filter_check_count)
                for recent in self.recent_replies_cache[chat_id][-check_count:]:
                    recent_content = recent.get("content", "")
                    recent_timestamp = recent.get("timestamp", 0)

                    # 如果启用时效性判断，检查消息是否在时效内
                    if self.enable_duplicate_time_limit:
                        time_limit = max(60, self.duplicate_filter_time_limit)
                        if now_ts - recent_timestamp >= time_limit:
                            continue  # 超过时效，跳过此条

                    if recent_content and reply_text == recent_content.strip():
                        logger.warning(
                            f"🚫 [装饰阶段过滤] 检测到与最近回复重复，跳过发送（后续流程继续执行）\n"
                            f"  最近回复: {recent_content[:100]}...\n"
                            f"  当前回复: {reply_text[:100]}..."
                        )
                        logger.info(
                            f"[装饰阶段] 正在清空event.result以阻止发送（注意：清空后 after_message_sent 不会被框架调用，processing_sessions 由 on_group_message 的 finally 块清理）"
                        )
                        # 清空结果以阻止发送
                        event.clear_result()
                        # 🔧 标记为重复拦截（由 on_group_message 的 finally 块统一清理）
                        self._duplicate_blocked_messages[message_id] = True
                        if message_id in self.raw_reply_cache:
                            del self.raw_reply_cache[message_id]
                        if self.debug_mode:
                            logger.info(
                                f"[装饰阶段] 已标记消息为重复拦截: {message_id[:30]}...（将跳过AI消息保存，但保存用户消息）"
                            )

                        # 🔧 修复：重复拦截后 after_message_sent 不会被框架调用
                        # 因此需要在此处直接保存用户消息和缓存消息到官方对话系统
                        # 否则这些消息永远不会被保存，导致上下文逐渐脱节
                        try:
                            await self._save_user_messages_on_duplicate_block(
                                event, message_id, chat_id
                            )
                        except Exception as save_err:
                            logger.warning(
                                f"[装饰阶段] 重复拦截后保存用户消息失败: {save_err}"
                            )

                        return

            # 🔧 修复竞态条件：通过重复检测后，立即写入 recent_replies_cache
            # 原来的逻辑是在 after_message_sent 中才写入，但此时消息已经发送
            # 如果两条消息并发处理，都在 after_message_sent 之前到达此处，
            # 两条都会通过重复检测，导致重复发送
            # 现在在检测通过后立即写入，防止并发消息通过相同检测
            if self.enable_duplicate_filter and reply_text:
                try:
                    if chat_id not in self.recent_replies_cache:
                        self.recent_replies_cache[chat_id] = []
                    self.recent_replies_cache[chat_id].append(
                        {
                            "content": reply_text,  # 使用原始内容（未添加错字）
                            "timestamp": time.time(),
                        }
                    )
                    # 🔒 限制缓存大小
                    max_cache_size = min(
                        max(10, self.duplicate_filter_check_count * 2),
                        self._DUPLICATE_CACHE_SIZE_LIMIT,
                    )
                    if len(self.recent_replies_cache[chat_id]) > max_cache_size:
                        self.recent_replies_cache[chat_id] = self.recent_replies_cache[
                            chat_id
                        ][-max_cache_size:]
                except Exception:
                    pass  # 缓存写入失败不影响主流程

            # 🆕 v1.0.2: 应用错字模拟（在重复检测之后，对原始内容进行装饰性修改）
            if self.typo_enabled and self.typo_generator:
                if self.debug_mode:
                    logger.info("[装饰阶段] 应用错字模拟")

                try:
                    processed_reply_text = self.typo_generator.process_reply(reply_text)
                    if processed_reply_text != reply_text:
                        if self.debug_mode:
                            logger.info(
                                f"[错字模拟] 已添加错字，原长度: {len(reply_text)}, "
                                f"处理后: {len(processed_reply_text)}"
                            )

                        # 更新 result 中的文本内容
                        first_text_comp = True
                        for comp in result.chain:
                            if hasattr(comp, "text"):
                                if first_text_comp:
                                    comp.text = processed_reply_text
                                    first_text_comp = False
                                else:
                                    comp.text = ""

                        # 注意：reply_text不更新，保持原始内容用于后续可能的用途
                        # raw_reply_cache中保存原始内容（未添加错字），用于重复检测缓存
                except Exception as e:
                    logger.error(f"[错字模拟] 处理时发生异常: {e}", exc_info=True)

            # 🆕 v1.0.2: 应用延迟模拟
            if self.typing_simulator_enabled and self.typing_simulator:
                if self.debug_mode:
                    logger.info("[装饰阶段] 应用延迟模拟")

                try:
                    # 延迟基于原始文本长度计算（未添加错字的）
                    _typing_start = time.time()
                    await self.typing_simulator.simulate_if_needed(reply_text)
                    _typing_elapsed = time.time() - _typing_start

                    if self.debug_mode:
                        logger.info(
                            f"[延迟模拟] 延迟完成，耗时: {_typing_elapsed:.2f}秒"
                        )
                    elif _typing_elapsed > self.typing_delay_timeout_warning:
                        logger.warning(
                            f"⚠️ [延迟模拟] 延迟耗时异常: {_typing_elapsed:.2f}秒"
                            f"（超过{self.typing_delay_timeout_warning}秒）"
                        )
                except Exception as e:
                    logger.error(f"[延迟模拟] 处理时发生异常: {e}", exc_info=True)

            # 非重复，不在此处更新缓存（在 after_message_sent 中记录）
        except Exception as e:
            logger.error(f"[装饰阶段] 去重处理失败: {e}", exc_info=True)

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent):
        """
        消息发送后的钩子，保存AI回复到官方对话系统

        在这里保存是因为此时event.result已经完整设置

        注意：所有消息发送都会触发，需要检查是否本插件的回复
        """
        try:
            # 获取会话信息（用于检查标记）
            platform_name = event.get_platform_name()
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            self._compute_session_integrity(str(chat_id))

            # 🔧 修复：使用message_id作为键进行检查
            message_id = self._get_message_id(event)

            # 🔒 使用锁保护检查和删除操作，避免与并发检测冲突
            async with self.concurrent_lock:
                # 检查是否为本插件处理的消息
                if message_id not in self.processing_sessions:
                    return  # 不是本插件触发的回复，忽略

                # 🔧 双重防护：检查此消息是否已经保存过
                # 当分段插件启用时，同一消息会触发多次 after_message_sent
                # processing_sessions 是第一道防线（通常已足够）
                # _saved_messages 是第二道防线（防御异常情况如标记被意外清空）
                if message_id in self._saved_messages:
                    if self.debug_mode:
                        logger.info(
                            f"[消息发送后] 消息 {message_id[:30]}... 已保存过，跳过"
                            f"（可能是分段插件的后续段落触发）"
                        )
                    else:
                        logger.info(
                            f"[消息发送后] 检测到重复保存请求（分段消息后续段落），已跳过"
                        )
                    return

                # 🔧 多轮工具调用支持：检查agent是否已完成
                # on_llm_response 在 agent 真正完成时设置此标志
                # 如果agent还未完成（工具调用中），回复文本已在 on_decorating_result 中累积，
                # 此处暂不保存，等待后续的最终调用
                is_agent_done = message_id in self._agent_done_flags

                if not is_agent_done:
                    # agent还在运行（多轮工具调用中），文本已在 on_decorating_result 累积
                    pending_count = len(self._pending_bot_replies.get(message_id, []))
                    logger.info(
                        f"[消息发送后] agent尚未完成（多轮工具调用中），"
                        f"已累积 {pending_count} 段回复，等待agent完成后统一保存"
                    )
                    return

                # agent已完成，清除标记并进行最终保存
                del self.processing_sessions[message_id]
                self._agent_done_flags.discard(message_id)

            # 🔧 检查是否为重复消息拦截（跳过AI消息保存，但继续保存用户消息）
            is_duplicate_blocked = message_id in self._duplicate_blocked_messages
            if is_duplicate_blocked:
                # 清除重复拦截标记
                del self._duplicate_blocked_messages[message_id]
                logger.info(
                    f"[消息发送后] 会话 {chat_id} 检测到重复消息拦截标记，将跳过AI消息保存，但继续保存用户消息"
                )

            # 只处理有result的消息（重复消息拦截时result已被清空，但仍需保存用户消息）
            if not is_duplicate_blocked and (
                not event._result or not hasattr(event._result, "chain")
            ):
                logger.info(f"[消息发送后] 会话 {chat_id} 没有result或chain，跳过")
                return

            # 检查是否为LLM result，或是否存在AI调用错误标记
            result_obj = event._result if event._result else None
            is_llm_result = False
            if result_obj:
                try:
                    is_llm_result = bool(result_obj.is_llm_result())
                except Exception:
                    is_llm_result = False

            ai_error_flag = (
                hasattr(self, "_ai_error_message_ids")
                and message_id in self._ai_error_message_ids
            )

            # 🔧 重复消息拦截时，跳过LLM结果检查，直接进入用户消息保存流程
            if not is_duplicate_blocked and not is_llm_result and not ai_error_flag:
                logger.info(f"[消息发送后] 会话 {chat_id} 不是LLM结果，跳过")
                return

            # 提取回复文本（仅在为LLM结果且非重复拦截时使用）
            displayed_bot_reply_text = ""
            original_bot_reply_text = ""
            bot_reply_to_save = None  # 🔧 初始化为None，重复拦截时不保存AI消息

            if is_llm_result and not is_duplicate_blocked:
                # 🔧 多轮工具调用支持：使用累积的所有回复文本，而不是仅当前一段
                accumulated_texts = self._pending_bot_replies.pop(message_id, [])
                # 清理 raw_reply_cache（不再需要）
                if hasattr(self, "raw_reply_cache"):
                    self.raw_reply_cache.pop(message_id, "")

                if accumulated_texts:
                    # 合并所有累积的原始文本
                    original_bot_reply_text = "\n".join(accumulated_texts)
                    displayed_bot_reply_text = original_bot_reply_text
                    if len(accumulated_texts) > 1:
                        logger.info(
                            f"[消息发送后] 🔧 多轮工具调用：合并了 {len(accumulated_texts)} 段AI回复，"
                            f"总长度: {len(original_bot_reply_text)} 字符"
                        )
                else:
                    # 回退：从当前 event result 提取（兼容无累积的情况）
                    displayed_bot_reply_text = "".join(
                        [
                            comp.text
                            for comp in result_obj.chain
                            if hasattr(comp, "text")
                        ]
                    )
                    original_bot_reply_text = displayed_bot_reply_text

                if not original_bot_reply_text:
                    logger.info(f"[消息发送后] 会话 {chat_id} 回复文本为空，跳过")
                    return

            # 🔧 只在非重复拦截时保存AI消息
            if is_llm_result and not is_duplicate_blocked:
                if self.debug_mode:
                    logger.info(
                        f"【消息发送后】会话 {chat_id} - 保存AI回复，长度: {len(original_bot_reply_text)} 字符"
                    )

                # 🆕 v1.2.0: 应用保存内容过滤（独立于输出过滤）
                # ⚠️ 注意：保存时不包含错字，保持原始内容
                # 这样确保：
                # 1. 错字和延迟仅影响显示效果，不改变AI的上下文认知
                # 2. 重复检测基于原始内容（不含错字和过滤）
                bot_reply_to_save = original_bot_reply_text
                try:
                    bot_reply_to_save = self.content_filter.process_for_save(
                        original_bot_reply_text
                    )
                except Exception:
                    logger.error(
                        "[保存过滤] 过滤时发生异常，将使用原始内容", exc_info=True
                    )
                    bot_reply_to_save = original_bot_reply_text
                if bot_reply_to_save != original_bot_reply_text:
                    logger.info(
                        f"[保存过滤] 已过滤AI回复，原长度: {len(original_bot_reply_text)}, 过滤后: {len(bot_reply_to_save)}"
                    )

                # 🆕 构建交错排列的工具调用+文本回复（保留时间顺序）
                # 不影响去重用的 original_bot_reply_text
                interleaved_reply = self._build_interleaved_tool_reply(
                    event, accumulated_texts
                )
                if interleaved_reply:
                    # 对交错排列的内容应用保存过滤
                    try:
                        bot_reply_to_save = self.content_filter.process_for_save(
                            interleaved_reply
                        )
                    except Exception:
                        bot_reply_to_save = interleaved_reply
                    logger.info(f"[工具调用] 已构建交错排列的工具调用记录到AI回复历史")

                # 保存AI回复到自定义存储（使用过滤后的内容）
                await ContextManager.save_bot_message(
                    event, bot_reply_to_save, self.context
                )

                # 记录到最近回复缓存（用于后续去重，使用原始内容，不含错字）
                # 🔧 注意：on_decorating_result 中已经提前写入了缓存（修复竞态条件）
                # 此处仅作为保险：如果 on_decorating_result 未写入（异常路径），这里补写
                try:
                    # 检查是否已经在 on_decorating_result 中写入过（避免重复写入）
                    already_cached = False
                    if chat_id in self.recent_replies_cache:
                        for recent in self.recent_replies_cache[chat_id][-3:]:
                            if (
                                recent.get("content", "")
                                == original_bot_reply_text.strip()
                            ):
                                already_cached = True
                                break
                    if not already_cached:
                        if chat_id not in self.recent_replies_cache:
                            self.recent_replies_cache[chat_id] = []
                        self.recent_replies_cache[chat_id].append(
                            {
                                "content": original_bot_reply_text,
                                "timestamp": time.time(),
                            }  # ← 使用原始内容
                        )
                        # 🔒 限制缓存大小（保留配置条数的2倍，最少10条，但不超过硬上限）
                        max_cache_size = min(
                            max(10, self.duplicate_filter_check_count * 2),
                            self._DUPLICATE_CACHE_SIZE_LIMIT,
                        )
                        if len(self.recent_replies_cache[chat_id]) > max_cache_size:
                            # 丢弃最旧的消息，保留最新的
                            self.recent_replies_cache[chat_id] = (
                                self.recent_replies_cache[chat_id][-max_cache_size:]
                            )
                except Exception:
                    pass
            elif is_duplicate_blocked:
                logger.info(
                    f"[消息发送后] 会话 {chat_id} - 跳过AI消息保存（重复消息已拦截），继续保存用户消息"
                )

            # 获取用户消息
            # 🔧 修复并发问题：优先使用 _message_cache_snapshots（在AI决策前提取的副本）
            # 避免在处理期间新消息进来导致获取到错误的消息
            message_to_save = ""

            # 优先使用缓存快照（并发安全）
            last_cached = self._message_cache_snapshots.pop(message_id, None)
            if not last_cached:
                # 🔧 修复：不再使用 pending_messages_cache[-1]（可能取到错误的消息）
                # 改为按 message_id 精确匹配查找，避免消息追踪错误
                if chat_id in self.pending_messages_cache:
                    for cached_msg in reversed(self.pending_messages_cache[chat_id]):
                        if (
                            isinstance(cached_msg, dict)
                            and cached_msg.get("message_id") == message_id
                        ):
                            last_cached = cached_msg
                            logger.warning(
                                "[消息发送后] ⚠️ 从共享缓存按message_id精确匹配获取消息"
                            )
                            break
                if not last_cached:
                    # 最终回退：从event提取（下方的 if not message_to_save 分支会处理）
                    logger.warning(
                        "[消息发送后] ⚠️ 缓存快照和共享缓存均未找到匹配消息，将从event提取"
                    )

            if (
                last_cached
                and isinstance(last_cached, dict)
                and "content" in last_cached
            ):
                # 获取处理后的消息内容（不含元数据）
                raw_content = last_cached["content"]

                # 强制日志：从缓存读取的内容
                logger.info(f"🟡 [官方保存-读缓存] 内容: {raw_content[:100]}")

                if self.debug_mode:
                    logger.info(
                        f"[消息发送后] 从缓存副本读取内容: {raw_content[:200]}..."
                    )

                # 使用缓存中的发送者信息添加元数据
                # 🆕 v1.0.4: 根据缓存中的触发方式信息确定trigger_type
                # 注意：需要同时检查 has_trigger_keyword 来正确判断触发方式
                trigger_type = None
                if last_cached.get("has_trigger_keyword"):
                    # 关键词触发（优先级高于@消息判断）
                    trigger_type = "keyword"
                elif last_cached.get("is_at_message"):
                    # 真正的@消息触发
                    trigger_type = "at"
                else:
                    # 概率触发（AI主动回复）
                    trigger_type = "ai_decision"

                message_to_save = MessageProcessor.add_metadata_from_cache(
                    raw_content,
                    last_cached.get("sender_id", event.get_sender_id()),
                    last_cached.get("sender_name", event.get_sender_name()),
                    last_cached.get("message_timestamp")
                    or last_cached.get("timestamp"),
                    self.include_timestamp,
                    self.include_sender_info,
                    last_cached.get("mention_info"),  # 传递@信息
                    trigger_type,  # 🆕 v1.0.4: 传递触发方式
                    last_cached.get("poke_info"),  # 🆕 v1.0.9: 传递戳一戳信息
                    last_cached.get("is_empty_at", False),  # 🔧 修复：传递空@标记
                )

                # 清理系统提示（保存前过滤）
                message_to_save = MessageCleaner.clean_message(message_to_save)

                # 强制日志：添加元数据后的内容
                logger.info(f"🟡 [官方保存-加元数据后] 内容: {message_to_save[:150]}")

            # 如果缓存中没有，尝试从当前消息提取
            if not message_to_save:
                logger.warning(
                    "[消息发送后] ⚠️ 缓存中无消息，从event提取消息（不应该发生）"
                )
                # 使用当前处理后的消息
                processed = MessageCleaner.extract_raw_message_from_event(event)
                if processed:
                    message_to_save = MessageProcessor.add_metadata_to_message(
                        event,
                        processed,
                        self.include_timestamp,
                        self.include_sender_info,
                        None,  # 这种情况下没有mention_info（从event提取的fallback）
                        None,  # trigger_type未知
                        None,  # 🆕 v1.0.9: 无法获取poke_info（fallback情况）
                    )
                    # 清理系统提示（保存前过滤）
                    message_to_save = MessageCleaner.clean_message(message_to_save)
                    logger.info(
                        f"[消息发送后] 从event提取的消息: {message_to_save[:200]}..."
                    )

            if not message_to_save:
                logger.warning("[消息发送后] 无法获取用户消息，跳过官方保存")
                return

            if self.debug_mode:
                logger.info(
                    f"[消息发送后] 准备保存到官方系统的消息: {message_to_save[:300]}..."
                )

            # 准备需要转正的缓存消息（包含那些之前未回复的消息）
            # 缓存中的消息不包含元数据，需要在转正时添加
            # 🔧 修复并发问题：
            # 1. 排除当前正在处理的消息（基于 message_id）
            # 2. 排除其他正在处理中的消息（检查 processing_sessions）
            # 3. 只保存时间戳早于当前消息的缓存消息
            # 4. 🆕 检查主动对话是否正在处理此会话
            cached_messages_to_convert = []
            current_msg_timestamp = None
            current_msg_id = None
            if last_cached:
                current_msg_timestamp = last_cached.get("timestamp")
                current_msg_id = last_cached.get("message_id")

            # 🆕 并发保护：检查主动对话是否正在处理此会话（使用循环等待+锁机制）
            proactive_processing = False
            # 🔒 先用锁检查初始状态
            async with self.concurrent_lock:
                initial_check = (
                    hasattr(self, "proactive_processing_sessions")
                    and chat_id in self.proactive_processing_sessions
                )

            if initial_check:
                # 使用与普通消息并发保护相同的配置
                max_wait_loops = self.concurrent_wait_max_loops
                wait_interval = self.concurrent_wait_interval

                for loop_count in range(max_wait_loops):
                    # 🔒 使用锁检查主动对话状态
                    async with self.concurrent_lock:
                        if chat_id not in self.proactive_processing_sessions:
                            # 主动对话已完成，可以继续
                            break

                    if loop_count == 0:
                        logger.info(
                            f"🔒 [并发保护] 检测到主动对话正在处理会话 {chat_id}，"
                            f"开始等待（最多 {max_wait_loops} 次，每次 {wait_interval} 秒）..."
                        )

                    await asyncio.sleep(wait_interval)

                    if self.debug_mode:
                        logger.info(
                            f"  [主动对话并发等待] 第 {loop_count + 1}/{max_wait_loops} 次检测..."
                        )
                else:
                    # 循环结束仍在处理，强制清除标记
                    async with self.concurrent_lock:
                        if chat_id in self.proactive_processing_sessions:
                            proactive_start_time = (
                                self.proactive_processing_sessions.get(chat_id, 0)
                            )
                            elapsed_time = time.time() - proactive_start_time

                            # 如果等待超时，清除标记并继续（避免死锁）
                            del self.proactive_processing_sessions[chat_id]
                            logger.warning(
                                f"⚠️ [并发保护] 等待 {max_wait_loops * wait_interval:.1f} 秒后主动对话仍在处理"
                                f"（已运行 {elapsed_time:.1f} 秒），已清除标记并继续执行"
                            )

                # 再次检查是否仍在处理（可能在等待期间完成了）
                async with self.concurrent_lock:
                    proactive_processing = chat_id in self.proactive_processing_sessions

            # 🆕 v1.2.0: 使用缓存管理器准备待转正的缓存消息
            # 获取当前正在处理中的所有消息ID
            # 🔒 使用锁保护读取操作，确保获取一致的快照
            async with self.concurrent_lock:
                processing_msg_ids = set(self.processing_sessions.keys())

            cached_messages_to_convert = self.cache_manager.prepare_cache_for_save(
                chat_id=chat_id,
                current_msg_id=current_msg_id,
                current_msg_timestamp=current_msg_timestamp,
                processing_msg_ids=processing_msg_ids,
                proactive_processing=proactive_processing,
            )

            # 保存到官方对话系统（包含缓存转正+去重）
            # 注意：去重逻辑在 save_to_official_conversation_with_cache 内部处理
            # 会自动过滤掉与现有官方历史重复的消息

            # 🔧 确定是否保存AI回复
            # - 重复消息拦截时：不保存AI回复（bot_reply_to_save 已经是 None）
            # - AI调用错误时：不保存AI回复
            # - 正常情况：保存AI回复
            if is_duplicate_blocked:
                bot_to_save = None
                logger.info(
                    f"[消息发送后] 准备保存: 缓存{len(cached_messages_to_convert)}条 + 当前用户消息（跳过AI回复，重复消息已拦截）"
                )
            elif not is_llm_result and ai_error_flag:
                bot_to_save = None
                logger.info(
                    f"[消息发送后] 准备保存: 缓存{len(cached_messages_to_convert)}条 + 当前用户消息（跳过AI回复，AI调用错误）"
                )
            else:
                bot_to_save = bot_reply_to_save
                logger.info(
                    f"[消息发送后] 准备保存: 缓存{len(cached_messages_to_convert)}条 + 当前对话(用户+AI)"
                )

            success = await ContextManager.save_to_official_conversation_with_cache(
                event,
                cached_messages_to_convert,  # 待转正的缓存消息（未去重，交给方法内部处理）
                message_to_save,  # 当前用户消息（已添加时间戳和发送者信息）
                bot_to_save,  # AI回复
                self.context,
            )

            if success:
                logger.info(f"[消息发送后] ✅ Phase-1 成功保存到官方对话系统")
                # 🆕 v1.2.0: 使用缓存管理器清理已保存的缓存消息
                self.cache_manager.clear_saved_cache(
                    chat_id=chat_id,
                    current_msg_id=current_msg_id,
                    current_msg_timestamp=current_msg_timestamp,
                    processing_msg_ids=processing_msg_ids,
                    proactive_processing=proactive_processing,
                )

                # 🆕 Phase-2: 保存窗口缓冲消息（在AI回复之后）
                try:
                    window_buffered_to_convert = (
                        self.cache_manager.prepare_window_buffered_for_save(
                            chat_id=chat_id,
                            processing_msg_ids=processing_msg_ids,
                        )
                    )
                    if window_buffered_to_convert:
                        logger.info(
                            f"[消息发送后] Phase-2: 保存 {len(window_buffered_to_convert)} 条窗口缓冲消息"
                        )
                        # 收集待保存消息的ID，用于精确清除
                        wb_saved_msg_ids = set()
                        for wb_msg in self.cache_manager.get_window_buffered_messages(
                            chat_id
                        ):
                            msg_id = wb_msg.get("message_id")
                            if msg_id:
                                wb_saved_msg_ids.add(msg_id)

                        phase2_success = await ContextManager.save_to_official_conversation_with_cache(
                            event,
                            window_buffered_to_convert,
                            None,  # 用户消息已在 Phase-1 保存
                            None,  # AI回复已在 Phase-1 保存
                            self.context,
                        )
                        if phase2_success:
                            self.cache_manager.clear_window_buffered_cache(
                                chat_id, saved_msg_ids=wb_saved_msg_ids
                            )
                            logger.info(f"[消息发送后] Phase-2: ✅ 窗口缓冲消息已转正")
                        else:
                            logger.warning(
                                f"[消息发送后] Phase-2: ⚠️ 窗口缓冲消息转正失败（降级：留在缓存等下次转正）"
                            )
                except Exception as phase2_err:
                    logger.warning(
                        f"[消息发送后] Phase-2: ⚠️ 窗口缓冲消息处理异常（降级：留在缓存）: {phase2_err}"
                    )

                # 🔧 标记消息已保存（防止分段消息重复保存）
                self._saved_messages[message_id] = time.time()

                # 🔧 清理过期的已保存标记（保留最近5分钟内的）
                # 使用 list() 创建副本，避免遍历时字典大小改变
                try:
                    cutoff_time = time.time() - 300  # 5分钟
                    # 创建字典项的副本，避免并发修改问题
                    items_snapshot = list(self._saved_messages.items())
                    expired_ids = [
                        msg_id
                        for msg_id, timestamp in items_snapshot
                        if timestamp < cutoff_time
                    ]
                    for msg_id in expired_ids:
                        # 使用 pop 而不是 del，防止键已被其他线程删除
                        self._saved_messages.pop(msg_id, None)

                    if self.debug_mode and expired_ids:
                        logger.info(
                            f"[消息发送后] 清理了 {len(expired_ids)} 条过期的已保存标记"
                        )
                except Exception as cleanup_error:
                    # 清理失败不影响主流程
                    logger.warning(
                        f"[消息发送后] 清理过期标记时发生错误: {cleanup_error}"
                    )
            else:
                logger.warning(f"[消息发送后] ⚠️ 保存到官方对话系统失败")
                if self.debug_mode:
                    logger.info(f"[消息发送后] 保存失败，缓存保留（待下次使用或清理）")

            if hasattr(self, "_ai_error_message_ids"):
                try:
                    self._ai_error_message_ids.discard(message_id)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"[消息发送后] 保存AI回复时发生错误: {e}", exc_info=True)

    async def _save_user_messages_on_duplicate_block(
        self, event: AstrMessageEvent, message_id: str, chat_id: str
    ):
        """
        🔧 重复拦截后保存用户消息到官方对话系统

        当 on_decorating_result 检测到重复并清空 result 后，框架不会调用 after_message_sent。
        此方法确保用户消息和缓存消息仍然被保存到官方对话系统，防止上下文脱节。

        Args:
            event: 消息事件
            message_id: 消息唯一ID
            chat_id: 聊天ID
        """
        try:
            # 获取用户消息缓存快照
            last_cached = self._message_cache_snapshots.pop(message_id, None)

            if not last_cached:
                if self.debug_mode:
                    logger.info("[重复拦截-保存] 无缓存快照，跳过用户消息保存")
                return

            if not isinstance(last_cached, dict) or "content" not in last_cached:
                return

            # 获取处理后的消息内容
            raw_content = last_cached["content"]

            # 确定触发方式
            trigger_type = None
            if last_cached.get("has_trigger_keyword"):
                trigger_type = "keyword"
            elif last_cached.get("is_at_message"):
                trigger_type = "at"
            else:
                trigger_type = "ai_decision"

            message_to_save = MessageProcessor.add_metadata_from_cache(
                raw_content,
                last_cached.get("sender_id", event.get_sender_id()),
                last_cached.get("sender_name", event.get_sender_name()),
                last_cached.get("message_timestamp") or last_cached.get("timestamp"),
                self.include_timestamp,
                self.include_sender_info,
                last_cached.get("mention_info"),
                trigger_type,
                last_cached.get("poke_info"),
                last_cached.get("is_empty_at", False),
            )

            # 清理系统提示
            message_to_save = MessageCleaner.clean_message(message_to_save)

            if not message_to_save:
                return

            # 准备缓存消息转正
            current_msg_timestamp = last_cached.get("timestamp")
            current_msg_id = last_cached.get("message_id")

            async with self.concurrent_lock:
                processing_msg_ids = set(self.processing_sessions.keys())

            proactive_processing = False
            async with self.concurrent_lock:
                proactive_processing = (
                    hasattr(self, "proactive_processing_sessions")
                    and chat_id in self.proactive_processing_sessions
                )

            cached_messages_to_convert = self.cache_manager.prepare_cache_for_save(
                chat_id=chat_id,
                current_msg_id=current_msg_id,
                current_msg_timestamp=current_msg_timestamp,
                processing_msg_ids=processing_msg_ids,
                proactive_processing=proactive_processing,
            )

            # 保存到官方对话系统（不保存AI回复，只保存用户消息+缓存消息）
            success = await ContextManager.save_to_official_conversation_with_cache(
                event,
                cached_messages_to_convert,
                message_to_save,
                None,  # bot_message=None，不保存AI回复
                self.context,
            )

            if success:
                logger.info(f"[重复拦截-保存] ✅ 用户消息已保存到官方对话系统")
                self.cache_manager.clear_saved_cache(
                    chat_id=chat_id,
                    current_msg_id=current_msg_id,
                    current_msg_timestamp=current_msg_timestamp,
                    processing_msg_ids=processing_msg_ids,
                    proactive_processing=proactive_processing,
                )

                # Phase-2: 保存窗口缓冲消息
                try:
                    window_buffered_to_convert = (
                        self.cache_manager.prepare_window_buffered_for_save(
                            chat_id=chat_id,
                            processing_msg_ids=processing_msg_ids,
                        )
                    )
                    if window_buffered_to_convert:
                        wb_saved_msg_ids = set()
                        for wb_msg in self.cache_manager.get_window_buffered_messages(
                            chat_id
                        ):
                            msg_id = wb_msg.get("message_id")
                            if msg_id:
                                wb_saved_msg_ids.add(msg_id)

                        phase2_success = await ContextManager.save_to_official_conversation_with_cache(
                            event,
                            window_buffered_to_convert,
                            None,
                            None,
                            self.context,
                        )
                        if phase2_success:
                            self.cache_manager.clear_window_buffered_cache(
                                chat_id, saved_msg_ids=wb_saved_msg_ids
                            )
                except Exception as phase2_err:
                    logger.warning(
                        f"[重复拦截-保存] Phase-2 窗口缓冲消息处理异常: {phase2_err}"
                    )
            else:
                logger.warning(f"[重复拦截-保存] ⚠️ 保存用户消息失败")

        except Exception as e:
            logger.warning(
                f"[重复拦截-保存] 保存用户消息时发生错误: {e}", exc_info=True
            )

    def _is_enabled(self, event: AstrMessageEvent) -> bool:
        """
        检查当前群组是否启用插件

        判断逻辑：
        - 私聊直接返回False（不处理）
        - enabled_groups为空则全部群聊启用
        - enabled_groups有值则仅列表内的群启用

        Args:
            event: 消息事件对象

        Returns:
            True=启用，False=未启用
        """
        # 只处理群消息,不处理私聊
        if event.is_private_chat():
            if self.debug_mode:
                logger.info("插件不处理私聊消息")
            return False

        # 获取启用的群组列表
        enabled_groups = self.enabled_groups

        if self.debug_mode:
            logger.info(f"当前配置的启用群组列表: {enabled_groups}")

        # 如果列表为空,则在所有群聊中启用
        if not enabled_groups or len(enabled_groups) == 0:
            if self.debug_mode:
                logger.info("未配置群组列表,在所有群聊中启用")
            return True

        # 如果列表不为空,检查当前群组是否在列表中
        group_id = event.get_group_id()
        if group_id in enabled_groups:
            if self.debug_mode:
                logger.info(f"群组 {group_id} 在启用列表中")
            return True
        else:
            if self.debug_mode:
                logger.info(f"群组 {group_id} 未在启用列表中")
            return False

    def _is_poke_enabled_in_group(self, chat_id: str) -> bool:
        """
        检查当前群组是否在戳一戳功能白名单中

        判断逻辑：
        - poke_enabled_groups为空则所有群聊都允许戳一戳功能
        - poke_enabled_groups有值则仅列表内的群允许戳一戳功能

        Args:
            chat_id: 群组ID（字符串）

        Returns:
            True=允许戳一戳功能，False=不允许
        """
        # 如果白名单为空，所有群都允许
        if not self.poke_enabled_groups or len(self.poke_enabled_groups) == 0:
            return True

        # 检查当前群组是否在白名单中
        chat_id_str = str(chat_id)
        if chat_id_str in self.poke_enabled_groups:
            if self.debug_mode:
                logger.info(
                    f"【戳一戳白名单】群组 {chat_id} 在白名单中，允许戳一戳功能"
                )
            return True
        else:
            if self.debug_mode:
                logger.info(
                    f"【戳一戳白名单】群组 {chat_id} 不在白名单中，禁止戳一戳功能"
                )
            return False

    def _build_interleaved_tool_reply(
        self, event: AstrMessageEvent, pending_texts: list
    ) -> str:
        """构建交错排列的工具调用+文本回复，保留时间顺序。

        根据 agent 循环的实际执行顺序，将 AI 的中间文本和工具调用记录交错排列：
        - AI 先说话再调工具 → 文本在前，工具记录在后
        - AI 直接调工具 → 工具记录在前
        - 多轮交替调用 → 按实际顺序交错排列

        利用 ToolCallsResult.tool_calls_info.content 判断每轮工具调用是否伴随文本，
        与 _pending_bot_replies 中的文本按序对应。

        Args:
            event: 消息事件
            pending_texts: _pending_bot_replies 中累积的文本列表（按时间顺序）

        Returns:
            交错排列的完整消息文本，无工具调用时返回空字符串
        """
        try:
            req = event.get_extra("provider_request")
            if not req or not getattr(req, "tool_calls_result", None):
                return ""

            tool_calls_list = req.tool_calls_result
            # 兼容单个 ToolCallsResult 或列表
            if not isinstance(tool_calls_list, list):
                tool_calls_list = [tool_calls_list]

            interleaved_parts = []
            text_index = 0  # 追踪当前使用到 pending_texts 的哪个位置

            for tcr in tool_calls_list:
                tool_calls_info = getattr(tcr, "tool_calls_info", None)
                tool_results = getattr(tcr, "tool_calls_result", []) or []

                # 检查这一轮工具调用是否伴随 AI 的中间文本
                # （通过 tool_calls_info.content 中是否有 TextPart 判断）
                has_intermediate_text = False
                if tool_calls_info and tool_calls_info.content:
                    content_list = (
                        tool_calls_info.content
                        if isinstance(tool_calls_info.content, list)
                        else []
                    )
                    for part in content_list:
                        if hasattr(part, "text") and part.text and part.text.strip():
                            has_intermediate_text = True
                            break

                # 如果这一轮有中间文本，取 pending_texts 中对应的（已处理过的）版本
                if has_intermediate_text and text_index < len(pending_texts):
                    interleaved_parts.append(pending_texts[text_index])
                    text_index += 1

                # 格式化这一轮的工具调用记录
                tool_lines = []
                if tool_calls_info and getattr(tool_calls_info, "tool_calls", None):
                    for i, tc in enumerate(tool_calls_info.tool_calls):
                        # 兼容 ToolCall 对象和 dict 两种格式
                        if hasattr(tc, "function"):
                            func_name = tc.function.name
                            func_args = tc.function.arguments or ""
                        elif isinstance(tc, dict):
                            func = tc.get("function", {})
                            func_name = func.get("name", "未知工具")
                            func_args = func.get("arguments", "")
                        else:
                            continue

                        # 截断过长参数
                        if len(func_args) > 200:
                            func_args = func_args[:200] + "..."

                        # 获取对应工具结果
                        result_preview = ""
                        if i < len(tool_results):
                            result_content = getattr(tool_results[i], "content", None)
                            if isinstance(result_content, str):
                                result_preview = result_content
                            elif isinstance(result_content, list):
                                texts = []
                                for p in result_content:
                                    if hasattr(p, "text"):
                                        texts.append(p.text)
                                    elif isinstance(p, dict) and "text" in p:
                                        texts.append(p["text"])
                                result_preview = " ".join(texts)
                            elif result_content is not None:
                                result_preview = str(result_content)

                            # 截断过长结果
                            if len(result_preview) > 500:
                                result_preview = result_preview[:500] + "..."

                        if result_preview:
                            tool_lines.append(
                                f"- {func_name}({func_args}) → {result_preview}"
                            )
                        else:
                            tool_lines.append(f"- {func_name}({func_args}) → (无返回)")

                if tool_lines:
                    interleaved_parts.append(
                        "[工具调用记录]\n" + "\n".join(tool_lines) + "\n[工具调用结束]"
                    )

            # 剩余的 pending_texts 是最后一轮工具调用之后 AI 的最终回复
            while text_index < len(pending_texts):
                interleaved_parts.append(pending_texts[text_index])
                text_index += 1

            if not interleaved_parts:
                return ""

            return "\n".join(interleaved_parts)

        except Exception as e:
            logger.warning(f"[工具调用交错] 构建失败: {e}", exc_info=True)
            return ""

    async def _finalize_bot_reply_save(self, event: AstrMessageEvent, message_id: str):
        """
        🔧 多轮工具调用支持：在agent完成但无最终文本时，保存之前累积的回复

        当AI先说话再调用工具，但工具直接返回结果（agent完成时无最终文本输出），
        需要在 on_llm_response 中调用此方法保存之前累积的所有中间回复文本。
        """
        try:
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            accumulated_texts = self._pending_bot_replies.pop(message_id, [])
            if not accumulated_texts:
                return

            original_bot_reply_text = "\n".join(accumulated_texts)
            if not original_bot_reply_text.strip():
                return

            logger.info(
                f"[_finalize_bot_reply_save] 保存 {len(accumulated_texts)} 段累积的AI回复，"
                f"总长度: {len(original_bot_reply_text)} 字符"
            )

            # 应用保存内容过滤
            bot_reply_to_save = original_bot_reply_text
            try:
                bot_reply_to_save = self.content_filter.process_for_save(
                    original_bot_reply_text
                )
            except Exception:
                logger.error("[保存过滤] 过滤时发生异常，将使用原始内容", exc_info=True)

            # 🆕 构建交错排列的工具调用+文本回复
            interleaved_reply = self._build_interleaved_tool_reply(
                event, accumulated_texts
            )
            if interleaved_reply:
                try:
                    bot_reply_to_save = self.content_filter.process_for_save(
                        interleaved_reply
                    )
                except Exception:
                    bot_reply_to_save = interleaved_reply
                logger.info(f"[工具调用] 兜底保存: 已构建交错排列的工具调用记录")

            # 保存AI回复到自定义存储
            await ContextManager.save_bot_message(
                event, bot_reply_to_save, self.context
            )

            # 记录到最近回复缓存（用于去重）
            try:
                if chat_id not in self.recent_replies_cache:
                    self.recent_replies_cache[chat_id] = []
                self.recent_replies_cache[chat_id].append(
                    {"content": original_bot_reply_text, "timestamp": time.time()}
                )
            except Exception:
                pass

            # 清理 raw_reply_cache
            if hasattr(self, "raw_reply_cache"):
                self.raw_reply_cache.pop(message_id, None)

            # 清理session并保存用户消息到官方系统
            async with self.concurrent_lock:
                self.processing_sessions.pop(message_id, None)
                self._agent_done_flags.discard(message_id)

            # 获取用户消息
            message_to_save = ""
            last_cached = self._message_cache_snapshots.pop(message_id, None)
            if (
                last_cached
                and isinstance(last_cached, dict)
                and "content" in last_cached
            ):
                raw_content = last_cached["content"]
                trigger_type = None
                if last_cached.get("has_trigger_keyword"):
                    trigger_type = "keyword"
                elif last_cached.get("is_at_message"):
                    trigger_type = "at"
                else:
                    trigger_type = "ai_decision"

                message_to_save = MessageProcessor.add_metadata_from_cache(
                    raw_content,
                    last_cached.get("sender_id", event.get_sender_id()),
                    last_cached.get("sender_name", event.get_sender_name()),
                    last_cached.get("message_timestamp")
                    or last_cached.get("timestamp"),
                    self.include_timestamp,
                    self.include_sender_info,
                    last_cached.get("mention_info"),
                    trigger_type,
                    last_cached.get("poke_info"),
                    last_cached.get("is_empty_at", False),
                )
                message_to_save = MessageCleaner.clean_message(message_to_save)

            if not message_to_save:
                processed = MessageCleaner.extract_raw_message_from_event(event)
                if processed:
                    message_to_save = MessageProcessor.add_metadata_to_message(
                        event,
                        processed,
                        self.include_timestamp,
                        self.include_sender_info,
                        None,
                        None,
                        None,
                    )
                    message_to_save = MessageCleaner.clean_message(message_to_save)

            if message_to_save:
                await ContextManager.save_to_official_conversation_with_cache(
                    event,
                    [],
                    message_to_save,
                    bot_reply_to_save,
                    self.context,
                )

            self._saved_messages[message_id] = time.time()

        except Exception as e:
            logger.error(f"[_finalize_bot_reply_save] 保存失败: {e}", exc_info=True)

    def _get_message_id(self, event: AstrMessageEvent) -> str:
        """
        生成消息的唯一标识符

        用于跨处理器标记消息（例如标记指令消息）

        优先使用平台提供的 message_id，确保：
        1. 不同消息有不同的ID（即使内容相同）
        2. 同一消息的分段使用相同的ID（防止重复保存）

        🔧 修复：将结果缓存到event对象上，确保同一个event在不同handler中
        调用此方法时返回相同的ID（解决回退路径使用time_ns导致ID不一致的问题）

        Args:
            event: 消息事件对象

        Returns:
            消息的唯一标识字符串
        """
        try:
            # 🔧 优先使用缓存的ID（确保同一event跨handler调用返回一致的ID）
            cached_id = getattr(event, "_plugin_cached_message_id", None)
            if cached_id:
                return cached_id

            result_id = None

            # 🔧 v1.2.0: 优先使用平台提供的 message_id（唯一且稳定）
            # 这样可以避免：
            # 1. AI重复回复相同内容时被误判为分段
            # 2. 不同消息但内容相同（前100字符）时冲突
            if hasattr(event, "message_obj") and hasattr(
                event.message_obj, "message_id"
            ):
                platform_msg_id = str(event.message_obj.message_id)
                if platform_msg_id and platform_msg_id.strip():
                    # 添加平台标识，确保跨平台唯一
                    platform_name = event.get_platform_name()
                    result_id = f"{platform_name}_{platform_msg_id}"

            if not result_id:
                # 回退方案：使用确定性内容哈希（不含随机/时间因子）
                # 🔧 修复：去掉 time_ns()，确保同一消息被平台重复推送时生成相同ID
                # 这样 _seen_message_ids 的去重才能正确工作
                sender_id = event.get_sender_id()
                group_id = (
                    event.get_group_id() if not event.is_private_chat() else "private"
                )
                msg_content = event.get_message_str()[:100]  # 只取前100字符避免过长

                # 🔧 使用秒级时间戳（取整到秒），允许同一秒内的重复推送被识别为同一消息
                # 同时不同秒的相同内容消息仍然有不同的ID
                timestamp_sec = int(time.time())
                hash_input = (
                    f"{sender_id}_{group_id}_{msg_content}_{timestamp_sec}".encode(
                        "utf-8"
                    )
                )
                content_hash = hashlib.md5(hash_input).hexdigest()[:16]  # 取前16位即可
                result_id = f"{sender_id}_{group_id}_{content_hash}"

            # 🔧 缓存到event对象，确保同一event跨handler返回一致的ID
            try:
                event._plugin_cached_message_id = result_id
            except AttributeError:
                pass  # event对象不支持动态属性时忽略
            return result_id
        except Exception as e:
            # 如果生成失败，返回一个基于秒级时间戳的ID（同一秒内的重复推送会得到相同ID）
            return f"fallback_{int(time.time())}_{str(e)[:20]}"

    def _normalize_bare(self, s: str) -> str:
        """
        归一化字符串：
        - 去除所有空白
        - 转小写
        - 去掉开头的任意非字母数字字符（视为前缀符号，如 / ! # 等）
        返回"裸指令/裸文本"以便与平台无关地比较。
        """
        try:
            s2 = "".join(s.split()).lower()
            i = 0
            while i < len(s2) and not s2[i].isalnum():
                i += 1
            return s2[i:]
        except Exception:
            return ""

    def _is_command_message(self, event: AstrMessageEvent) -> bool:
        """
        检测消息是否为指令消息（根据配置的指令前缀和完整指令列表）

        支持以下格式的检测：
        1. /command 或 !command 等（直接以前缀开头）
        2. @机器人 /command（@ 机器人后跟指令）
        3. @[AT:机器人ID] /command（消息链中 @ 后跟指令）
        4. 【v1.1.2新增】完整指令字符串检测：
           - @机器人 new 或 new（单独的指令，全字符串匹配）
           - 会自动去除@组件和空格/空白符进行匹配
           - @机器人 new你好 或 new你好 不算指令（有其他内容）

        如果开启了指令过滤功能，并且消息符合指令格式，
        则认为是指令消息，本插件应跳过处理（但不影响其他插件）

        Args:
            event: 消息事件对象

        Returns:
            True=是指令消息（应跳过），False=不是指令消息
        """
        # 检查是否启用指令过滤功能
        enable_filter = self.enable_command_filter
        if not enable_filter:
            if self.debug_mode:
                logger.info("指令过滤功能未启用")
            return False

        # 获取配置的指令前缀列表
        command_prefixes = self.command_prefixes

        # 获取完整指令检测配置
        enable_full_cmd = self.enable_full_command_detection
        full_command_list = self.full_command_list

        # 获取指令前缀匹配配置（v1.2.0新增）
        enable_prefix_match = self.enable_command_prefix_match
        prefix_match_list = self.command_prefix_match_list

        # 如果所有检测方式都未配置，直接返回
        has_prefix_filter = bool(command_prefixes)
        has_full_cmd = enable_full_cmd and bool(full_command_list)
        has_prefix_match = enable_prefix_match and bool(prefix_match_list)

        if not has_prefix_filter and not has_full_cmd and not has_prefix_match:
            if self.debug_mode:
                logger.info(
                    "指令过滤已启用，但未配置任何前缀、完整指令或前缀匹配指令！"
                )
            return False

        # 输出检测开始日志
        if self.debug_mode:
            logger.info(f"开始指令检测")
            if command_prefixes:
                logger.info(f"  - 配置的前缀: {command_prefixes}")
            if has_full_cmd:
                logger.info(f"  - 完整指令列表: {full_command_list}")
            if has_prefix_match:
                logger.info(f"  - 前缀匹配指令列表: {prefix_match_list}")
            logger.info(f"  - 消息内容: {event.get_message_str()}")

        try:
            # ✅ 关键：使用原始消息链（event.message_obj.message）
            # AstrBot 的 WakingCheckStage 会修改 event.message_str，
            # 但不会修改 event.message_obj.message！
            original_messages = event.message_obj.message
            if not original_messages:
                if self.debug_mode:
                    logger.info("[指令检测] 原始消息链为空")
                return False

            if self.debug_mode:
                logger.info(f"[指令检测] 原始消息链组件数: {len(original_messages)}")

            # ========== 第一步：检查指令前缀 ==========
            if command_prefixes:
                # 检查原始消息链中的第一个 Plain 组件
                for component in original_messages:
                    if isinstance(component, Plain):
                        # 获取第一个 Plain 组件的原始文本
                        first_text = component.text.strip()

                        if self.debug_mode:
                            logger.info(f"[前缀检测] 第一个Plain文本: '{first_text}'")

                        # 检查是否以任一指令前缀开头
                        for prefix in command_prefixes:
                            if prefix and first_text.startswith(prefix):
                                if self.debug_mode:
                                    logger.info(
                                        f"🚫 [指令过滤-前缀] 检测到指令前缀 '{prefix}'，原始文本: {first_text[:50]}... - 插件跳过处理"
                                    )
                                return True

                        # 找到第一个 Plain 组件后就停止
                        break

            # ========== 第二步：检查完整指令字符串 ==========
            if enable_full_cmd and full_command_list:
                # 提取所有Plain组件的文本，忽略At组件
                plain_texts = []
                for component in original_messages:
                    if isinstance(component, Plain):
                        plain_texts.append(component.text)
                    # 跳过At、AtAll等组件

                # 合并所有Plain文本
                combined_text = "".join(plain_texts)

                # 去除所有空格和空白符（包括空格、制表符、换行符等）
                cleaned_text = "".join(combined_text.split())

                if self.debug_mode:
                    logger.info(f"[完整指令检测] 合并后文本: '{combined_text}'")
                    logger.info(f"[完整指令检测] 清理后文本: '{cleaned_text}'")

                # 检查是否完全匹配配置的完整指令
                for cmd in full_command_list:
                    if not cmd:  # 跳过空字符串
                        continue

                    # 同样去除指令配置中的空格
                    cleaned_cmd = "".join(str(cmd).split())

                    # 全字符串匹配（大小写敏感）
                    if cleaned_text == cleaned_cmd:
                        if self.debug_mode:
                            logger.info(
                                f"🚫 [指令过滤-完整匹配] 检测到完整指令 '{cmd}'，清理后文本: '{cleaned_text}' - 插件跳过处理"
                            )
                        return True

            # ========== 第三步：检查指令前缀匹配（v1.2.0新增） ==========
            if has_prefix_match:
                # 提取所有Plain组件的文本，忽略At组件
                plain_texts = []
                for component in original_messages:
                    if isinstance(component, Plain):
                        plain_texts.append(component.text)

                # 合并所有Plain文本
                combined_text = "".join(plain_texts)

                # 去除开头的空白符，但保留中间的空格（用于判断指令边界）
                stripped_text = combined_text.lstrip()

                if self.debug_mode:
                    logger.info(f"[前缀匹配检测] 去除开头空白后文本: '{stripped_text}'")

                # 检查是否以配置的指令开头
                for cmd in prefix_match_list:
                    if not cmd:  # 跳过空字符串
                        continue

                    cmd_str = str(cmd).strip()
                    if not cmd_str:
                        continue

                    # 检查消息是否以该指令开头
                    if stripped_text.startswith(cmd_str):
                        # 检查指令后面是否为空格、消息结束或其他空白符
                        # 避免误匹配（如 'add' 不应匹配 'address'）
                        remaining = stripped_text[len(cmd_str) :]
                        if not remaining or remaining[0].isspace():
                            if self.debug_mode:
                                logger.info(
                                    f"🚫 [指令过滤-前缀匹配] 检测到指令前缀 '{cmd_str}'，原始文本: '{stripped_text[:50]}...' - 插件跳过处理"
                                )
                            return True

            if self.debug_mode:
                logger.info("[指令检测] 未检测到指令格式，继续正常处理")
            return False

        except Exception as e:
            # 出错时不影响主流程，只记录错误日志
            logger.error(f"[指令检测] 发生错误: {e}", exc_info=True)
            return False

    def _is_private_command_message(self, event: AstrMessageEvent) -> bool:
        """
        检测私信消息是否为指令消息（使用私信专用配置，独立于群聊）

        检测逻辑与群聊的 _is_command_message 相同，但使用私信专属配置变量：
        - self.private_enable_command_filter
        - self.private_command_prefixes
        - self.private_enable_full_command_detection
        - self.private_full_command_list
        - self.private_enable_command_prefix_match
        - self.private_command_prefix_match_list

        Args:
            event: 消息事件对象

        Returns:
            True=是指令消息（应跳过），False=不是指令消息
        """
        # 检查是否启用私信指令过滤功能
        if not self.private_enable_command_filter:
            if self.debug_mode:
                logger.info("[私信指令过滤] 私信指令过滤功能未启用")
            return False

        # 获取私信配置的指令前缀列表
        command_prefixes = self.private_command_prefixes

        # 获取私信完整指令检测配置
        enable_full_cmd = self.private_enable_full_command_detection
        full_command_list = self.private_full_command_list

        # 获取私信指令前缀匹配配置
        enable_prefix_match = self.private_enable_command_prefix_match
        prefix_match_list = self.private_command_prefix_match_list

        # 如果所有检测方式都未配置，直接返回
        has_prefix_filter = bool(command_prefixes)
        has_full_cmd = enable_full_cmd and bool(full_command_list)
        has_prefix_match = enable_prefix_match and bool(prefix_match_list)

        if not has_prefix_filter and not has_full_cmd and not has_prefix_match:
            if self.debug_mode:
                logger.info(
                    "[私信指令过滤] 已启用，但未配置任何前缀、完整指令或前缀匹配指令！"
                )
            return False

        if self.debug_mode:
            logger.info("[私信指令检测] 开始检测")
            if command_prefixes:
                logger.info(f"  - 配置的前缀: {command_prefixes}")
            if has_full_cmd:
                logger.info(f"  - 完整指令列表: {full_command_list}")
            if has_prefix_match:
                logger.info(f"  - 前缀匹配指令列表: {prefix_match_list}")
            logger.info(f"  - 消息内容: {event.get_message_str()}")

        try:
            original_messages = event.message_obj.message
            if not original_messages:
                if self.debug_mode:
                    logger.info("[私信指令检测] 原始消息链为空")
                return False

            if self.debug_mode:
                logger.info(
                    f"[私信指令检测] 原始消息链组件数: {len(original_messages)}"
                )

            # ========== 第一步：检查指令前缀 ==========
            if command_prefixes:
                for component in original_messages:
                    if isinstance(component, Plain):
                        first_text = component.text.strip()
                        if self.debug_mode:
                            logger.info(
                                f"[私信前缀检测] 第一个Plain文本: '{first_text}'"
                            )
                        for prefix in command_prefixes:
                            if prefix and first_text.startswith(prefix):
                                if self.debug_mode:
                                    logger.info(
                                        f"🚫 [私信指令过滤-前缀] "
                                        f"检测到指令前缀 '{prefix}'，"
                                        f"原始文本: "
                                        f"{first_text[:50]}... "
                                        f"- 插件跳过处理"
                                    )
                                return True
                        break

            # ========== 第二步：检查完整指令字符串 ==========
            if enable_full_cmd and full_command_list:
                plain_texts = []
                for component in original_messages:
                    if isinstance(component, Plain):
                        plain_texts.append(component.text)
                combined_text = "".join(plain_texts)
                cleaned_text = "".join(combined_text.split())

                if self.debug_mode:
                    logger.info(f"[私信完整指令检测] 合并后文本: '{combined_text}'")
                    logger.info(f"[私信完整指令检测] 清理后文本: '{cleaned_text}'")

                for cmd in full_command_list:
                    if not cmd:
                        continue
                    cleaned_cmd = "".join(str(cmd).split())
                    if cleaned_text == cleaned_cmd:
                        if self.debug_mode:
                            logger.info(
                                f"🚫 [私信指令过滤-完整匹配] "
                                f"检测到完整指令 '{cmd}'，"
                                f"清理后文本: '{cleaned_text}' "
                                f"- 插件跳过处理"
                            )
                        return True

            # ========== 第三步：检查指令前缀匹配 ==========
            if has_prefix_match:
                plain_texts = []
                for component in original_messages:
                    if isinstance(component, Plain):
                        plain_texts.append(component.text)
                combined_text = "".join(plain_texts)
                stripped_text = combined_text.lstrip()

                if self.debug_mode:
                    logger.info(
                        f"[私信前缀匹配检测] 去除开头空白后文本: '{stripped_text}'"
                    )

                for cmd in prefix_match_list:
                    if not cmd:
                        continue
                    cmd_str = str(cmd).strip()
                    if not cmd_str:
                        continue
                    if stripped_text.startswith(cmd_str):
                        remaining = stripped_text[len(cmd_str) :]
                        if not remaining or remaining[0].isspace():
                            if self.debug_mode:
                                logger.info(
                                    f"🚫 [私信指令过滤-前缀匹配] "
                                    f"检测到指令前缀 '{cmd_str}'，"
                                    f"原始文本: "
                                    f"'{stripped_text[:50]}...' "
                                    f"- 插件跳过处理"
                                )
                            return True

            if self.debug_mode:
                logger.info("[私信指令检测] 未检测到指令格式，继续正常处理")
            return False

        except Exception as e:
            logger.error(f"[私信指令检测] 发生错误: {e}", exc_info=True)
            return False

    def _is_user_blacklisted(self, event: AstrMessageEvent) -> bool:
        """
        检测发送者是否在用户黑名单中（v1.0.7新增）

        如果用户在黑名单中，本插件将忽略该消息，但不影响其他插件和官方功能。

        Args:
            event: 消息事件对象

        Returns:
            bool: True=在黑名单中（应该忽略），False=不在黑名单中（正常处理）
        """
        try:
            # 检查是否启用了黑名单功能
            if not self.enable_user_blacklist:
                return False

            # 获取黑名单列表
            blacklist = self.blacklist_user_ids
            if not blacklist:
                # 黑名单为空，不过滤任何用户
                return False

            # 提取发送者的用户ID
            sender_id = event.get_sender_id()

            # 将 sender_id 转换为字符串进行比对（确保类型一致）
            sender_id_str = str(sender_id)

            # 检查是否在黑名单中（支持字符串和数字类型的ID）
            is_blacklisted = (
                sender_id in blacklist
                or sender_id_str in blacklist
                or (
                    int(sender_id_str) in blacklist
                    if sender_id_str.isdigit()
                    else False
                )
            )

            if is_blacklisted:
                if self.debug_mode:
                    logger.info(
                        f"🚫 [用户黑名单] 用户 {sender_id} 在黑名单中，本插件跳过处理该消息"
                    )
                return True

            return False

        except Exception as e:
            # 发生错误时不影响主流程，只记录错误日志
            logger.error(f"[用户黑名单检测] 发生错误: {e}", exc_info=True)
            return False

    def _should_ignore_at_all(self, event: AstrMessageEvent) -> bool:
        """
        检测是否应该忽略@全体成员的消息

        这是插件内部的额外过滤机制，作为AstrBot平台配置的双保险。
        即使平台未配置忽略@全体成员，开启此功能后插件也会过滤掉这类消息。

        Args:
            event: 消息事件对象

        Returns:
            bool: True=应该忽略这条消息（包含@全体成员），False=继续处理
        """
        try:
            # 检查是否启用了忽略@全体成员功能
            if not self.ignore_at_all_enabled:
                if self.debug_mode:
                    logger.info("[@全体成员检测] 功能未启用，跳过检测")
                return False

            # 【修复】使用原始消息链，与指令检测保持一致
            # event.get_messages() 可能返回处理后的消息链，AtAll组件可能已被移除或转换
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                if self.debug_mode:
                    logger.info("[@全体成员检测] 无法获取原始消息链")
                return False

            original_messages = event.message_obj.message
            if not original_messages:
                if self.debug_mode:
                    logger.info("[@全体成员检测] 原始消息链为空")
                return False

            # 【调试】输出消息链详细信息
            if self.debug_mode:
                logger.info(f"[@全体成员检测] 消息链组件数: {len(original_messages)}")
                for i, component in enumerate(original_messages):
                    component_type = type(component).__name__
                    logger.info(f"[@全体成员检测] 组件{i}: 类型={component_type}")
                    if isinstance(component, At):
                        logger.info(f"[@全体成员检测] At组件详情: qq={component.qq}")
                    elif isinstance(component, AtAll):
                        logger.info(f"[@全体成员检测] 检测到AtAll组件")

            # 检查消息中是否包含AtAll组件或At组件(qq="all")
            for component in original_messages:
                # 检查AtAll类型
                if isinstance(component, AtAll):
                    if self.debug_mode:
                        logger.info(
                            "[@全体成员检测] 检测到AtAll类型组件，根据配置忽略处理"
                        )
                    return True
                # 检查At类型且qq为"all"的情况
                if isinstance(component, At):
                    qq_value = str(component.qq).lower()
                    if qq_value == "all":
                        if self.debug_mode:
                            logger.info(
                                f"[@全体成员检测] 检测到At(qq='all')组件，根据配置忽略处理"
                            )
                        return True

            # 没有检测到@全体成员
            if self.debug_mode:
                logger.info("[@全体成员检测] 未检测到@全体成员相关组件")
            return False

        except Exception as e:
            logger.error(f"[@全体成员检测] 发生错误: {e}", exc_info=True)
            # 发生错误时为了安全起见，不忽略消息（保持原有行为）
            return False

    def _should_ignore_at_others(self, event: AstrMessageEvent) -> bool:
        """
        检测是否应该忽略@他人的消息

        根据配置决定：
        1. 如果未启用此功能，返回False（不忽略）
        2. 如果启用了，检测消息是否@了其他人：
           - strict模式：只要@了其他人就忽略
           - allow_with_bot模式：@了其他人但也@了机器人，则不忽略

        Args:
            event: 消息事件对象

        Returns:
            bool: True=应该忽略这条消息，False=继续处理
        """
        try:
            # 检查是否启用了忽略@他人功能
            if not self.enable_ignore_at_others:
                return False

            # 获取忽略模式
            ignore_mode = self.ignore_at_others_mode

            # 获取机器人自己的ID
            bot_id = event.get_self_id()

            # 获取消息组件列表
            messages = (
                event.message_obj.message
                if hasattr(event, "message_obj")
                and hasattr(event.message_obj, "message")
                else []
            )
            if not messages:
                messages = []

            # 检查消息中的At组件
            has_at_others = False  # 是否@了其他人
            has_at_bot = False  # 是否@了机器人

            for component in messages:
                if isinstance(component, At):
                    mentioned_id = str(component.qq)

                    # 检查是否@了机器人
                    if mentioned_id == bot_id:
                        has_at_bot = True
                        if self.debug_mode:
                            logger.info(f"[@他人检测] 检测到@机器人: ID={mentioned_id}")
                    # 检查是否@了其他人（排除@全体成员）
                    elif mentioned_id.lower() != "all":
                        has_at_others = True
                        mentioned_name = (
                            component.name
                            if hasattr(component, "name") and component.name
                            else ""
                        )
                        if self.debug_mode:
                            logger.info(
                                f"[@他人检测] 检测到@其他人: ID={mentioned_id}, 名称={mentioned_name or '未知'}"
                            )

            # 如果消息链中未检测到任何At组件，尝试从原始消息数据中读取（后备方案）
            # 处理 aiocqhttp 适配器因 get_group_member_info API 异常而丢弃 At 组件的情况
            if not has_at_others and not has_at_bot:
                raw_results = self._detect_at_from_raw_message(event, str(bot_id))
                has_at_bot = raw_results.get("has_at_bot", False)
                has_at_others = raw_results.get("has_at_others", False)
                if self.debug_mode and (has_at_bot or has_at_others):
                    logger.info(
                        f"[@他人检测] 通过原始消息后备检测: has_at_bot={has_at_bot}, has_at_others={has_at_others}"
                    )

            # 若消息中包含对机器人的 @，无论模式如何都应该继续处理
            if has_at_bot:
                if self.debug_mode:
                    logger.info("[@他人检测] 检测到@机器人，继续处理该消息")
                return False

            # 根据模式决定是否忽略
            if ignore_mode == "strict":
                # strict模式：只要@了其他人就忽略
                if has_at_others:
                    if self.debug_mode:
                        logger.info(
                            f"[@他人检测-strict模式] 消息中@了其他人，本插件跳过处理"
                        )
                    return True
            elif ignore_mode == "allow_with_bot":
                # allow_with_bot模式：@了其他人但也@了机器人，则继续处理
                if has_at_others and not has_at_bot:
                    if self.debug_mode:
                        logger.info(
                            f"[@他人检测-allow_with_bot模式] 消息中@了其他人但未@机器人，本插件跳过处理"
                        )
                    return True
                elif has_at_others and has_at_bot:
                    if self.debug_mode:
                        logger.info(
                            f"[@他人检测-allow_with_bot模式] 消息中@了其他人但也@了机器人，继续处理"
                        )

            return False

        except Exception as e:
            # 出错时不影响主流程，只记录错误日志
            logger.error(f"[@他人检测] 发生错误: {e}", exc_info=True)
            return False

    def _detect_at_from_raw_message(self, event: AstrMessageEvent, bot_id: str) -> dict:
        """
        从原始消息数据中检测 At 组件（后备方案）

        当消息链中缺少 At 组件时（如 aiocqhttp 适配器因 get_group_member_info
        API 异常而丢弃 At 组件），尝试直接从 raw_message 原始事件数据中读取。
        aiocqhttp 适配器将原始 Event 对象保存在 abm.raw_message，
        其 .message 字段包含未经处理的消息段列表（dict 格式），
        不受 API 调用成败影响，始终存在。

        Args:
            event: 消息事件对象
            bot_id: 机器人的 ID 字符串

        Returns:
            dict: {"has_at_bot": bool, "has_at_others": bool}
        """
        result = {"has_at_bot": False, "has_at_others": False}
        try:
            raw_event = getattr(event.message_obj, "raw_message", None)
            if not raw_event:
                return result

            # 尝试获取原始消息段列表
            raw_message = None
            if hasattr(raw_event, "message"):
                raw_message = raw_event.message
            elif isinstance(raw_event, dict):
                raw_message = raw_event.get("message", [])

            if not raw_message or not isinstance(raw_message, list):
                return result

            for segment in raw_message:
                seg_type = None
                seg_data = None
                if isinstance(segment, dict):
                    seg_type = segment.get("type")
                    seg_data = segment.get("data", {})
                elif hasattr(segment, "__getitem__"):
                    try:
                        seg_type = segment["type"]
                        seg_data = segment["data"]
                    except (KeyError, TypeError):
                        continue

                if seg_type != "at" or not seg_data:
                    continue

                qq_val = str(
                    seg_data.get("qq", "") if isinstance(seg_data, dict) else ""
                )
                if not qq_val:
                    continue

                if qq_val == bot_id:
                    result["has_at_bot"] = True
                elif qq_val.lower() != "all":
                    result["has_at_others"] = True

        except Exception as e:
            if self.debug_mode:
                logger.info(f"[@他人检测-原始消息后备] 读取失败: {e}")
        return result

    async def _check_mention_others(self, event: AstrMessageEvent) -> dict:
        """
        检测消息中是否@了别人（不是机器人自己）

        Args:
            event: 消息事件对象

        Returns:
            dict: 包含@信息的字典，如果没有@别人则返回None
                  格式: {"mentioned_user_id": "xxx", "mentioned_user_name": "xxx"}
        """
        try:
            # 获取机器人自己的ID
            bot_id = event.get_self_id()

            # 获取消息组件列表
            messages = event.get_messages()
            if not messages:
                return None

            # 检查消息中的At组件
            for component in messages:
                if isinstance(component, At):
                    # 获取被@的用户ID
                    mentioned_id = str(component.qq)

                    # 如果@的不是机器人自己，且不是@全体成员
                    if mentioned_id != bot_id and mentioned_id.lower() != "all":
                        mentioned_name = (
                            component.name
                            if hasattr(component, "name") and component.name
                            else ""
                        )

                        # 强制输出 @ 检测日志（使用 INFO 级别确保可见）
                        logger.info(
                            f"🔍 [@检测-@别人] 发现@其他用户: ID={mentioned_id}, 名称={mentioned_name or '未知'}"
                        )
                        if self.debug_mode:
                            logger.info(
                                f"【@检测】详细信息: mentioned_id={mentioned_id}, mentioned_name={mentioned_name}"
                            )

                        return {
                            "mentioned_user_id": mentioned_id,
                            "mentioned_user_name": mentioned_name,
                        }

            # 未检测到@别人，输出日志（仅在debug模式）
            if self.debug_mode:
                logger.info("【@检测】未检测到@其他用户")
            return None

        except Exception as e:
            # 出错时不影响主流程，只记录错误日志
            logger.error(f"检测@提及时发生错误: {e}", exc_info=True)
            return None

    def _check_poke_message(self, event: AstrMessageEvent) -> dict:
        """
        检测是否为戳一戳消息（v1.0.9新增）

        ⚠️ 仅支持QQ平台的aiocqhttp消息事件

        根据配置决定如何处理：
        1. ignore模式：忽略所有戳一戳消息
        2. bot_only模式：只处理戳机器人的消息
        3. all模式：接受所有戳一戳消息

        Args:
            event: 消息事件对象

        Returns:
            dict: 戳一戳信息，格式:
                  {
                      "is_poke": True/False,  # 是否为戳一戳消息
                      "should_ignore": True/False,  # 是否应该忽略（本插件不处理）
                      "poke_info": {  # 戳一戳详细信息（仅当应该处理时存在）
                          "is_poke_bot": True/False,  # 是否戳的是机器人
                          "sender_id": "xxx",  # 戳人者ID
                          "sender_name": "xxx",  # 戳人者昵称
                          "target_id": "xxx",  # 被戳者ID
                          "target_name": "xxx"  # 被戳者昵称（可能为空）
                      }
                  }
        """
        try:
            # 获取配置的戳一戳处理模式
            poke_mode = self.poke_message_mode

            # 检查平台是否为aiocqhttp
            if event.get_platform_name() != "aiocqhttp":
                return {"is_poke": False, "should_ignore": False}

            # 获取原始消息对象
            raw_message = getattr(event.message_obj, "raw_message", None)
            if not raw_message:
                return {"is_poke": False, "should_ignore": False}

            # 检查是否为戳一戳事件
            # 参考astrbot_plugin_llm_poke的实现
            is_poke = (
                raw_message.get("post_type") == "notice"
                and raw_message.get("notice_type") == "notify"
                and raw_message.get("sub_type") == "poke"
            )

            if not is_poke:
                return {"is_poke": False, "should_ignore": False}

            # 确实是戳一戳消息
            if self.debug_mode:
                logger.info("【戳一戳检测】检测到戳一戳消息")

            # 🆕 白名单检查：检查当前群聊是否允许戳一戳功能
            group_id = raw_message.get("group_id")
            if group_id:
                if not self._is_poke_enabled_in_group(str(group_id)):
                    if self.debug_mode:
                        # 群聊不在白名单中，忽略此戳一戳消息
                        logger.info(
                            f"【戳一戳白名单】群 {group_id} 未在白名单中，忽略戳一戳消息"
                        )
                    return {"is_poke": True, "should_ignore": True}

            # 模式1: ignore - 忽略所有戳一戳消息
            if poke_mode == "ignore":
                if self.debug_mode:
                    logger.info("【戳一戳检测】当前模式为ignore，忽略此消息")
                return {"is_poke": True, "should_ignore": True}

            # 获取戳一戳相关信息
            bot_id = raw_message.get("self_id")
            sender_id = raw_message.get("user_id")
            target_id = raw_message.get("target_id")
            group_id = raw_message.get("group_id")

            # 获取发送者昵称（戳人者）
            sender_name = event.get_sender_name()

            # 获取被戳者昵称（如果可能）
            target_name = ""
            try:
                # 尝试从群信息中获取被戳者昵称
                if group_id and target_id and str(target_id) != str(bot_id):
                    # 这里可以调用API获取成员信息，但为了简化，暂时留空
                    # 后续可以通过 event.get_group() 获取群成员列表来查找
                    pass
            except Exception as e:
                if self.debug_mode:
                    logger.info(f"【戳一戳检测】获取被戳者昵称失败: {e}")

            # 判断是否戳的是机器人
            is_poke_bot = str(target_id) == str(bot_id)

            if self.debug_mode:
                logger.info(
                    f"【戳一戳检测】戳人者ID={sender_id}, 被戳者ID={target_id}, 机器人ID={bot_id}"
                )
                logger.info(f"【戳一戳检测】是否戳机器人: {is_poke_bot}")

            # 模式2: bot_only - 只处理戳机器人的消息
            if poke_mode == "bot_only":
                if not is_poke_bot:
                    if self.debug_mode:
                        logger.info(
                            "【戳一戳检测】当前模式为bot_only，但戳的不是机器人，忽略此消息"
                        )
                    return {"is_poke": True, "should_ignore": True}
                else:
                    logger.info(
                        f"✅ 检测到戳一戳消息（有人戳机器人），当前模式为bot_only，本插件将处理"
                    )
                    return {
                        "is_poke": True,
                        "should_ignore": False,
                        "poke_info": {
                            "is_poke_bot": True,
                            "sender_id": str(sender_id),
                            "sender_name": sender_name or "未知用户",
                            "target_id": str(target_id),
                            "target_name": "",  # 机器人自己，不需要名称
                        },
                    }

            # 模式3: all - 接受所有戳一戳消息
            if poke_mode == "all":
                logger.info(f"✅ 检测到戳一戳消息，当前模式为all，本插件将处理")
                return {
                    "is_poke": True,
                    "should_ignore": False,
                    "poke_info": {
                        "is_poke_bot": is_poke_bot,
                        "sender_id": str(sender_id),
                        "sender_name": sender_name or "未知用户",
                        "target_id": str(target_id),
                        "target_name": target_name or "未知用户",
                    },
                }

            # 未知模式，默认忽略
            logger.warning(f"⚠️ 未知的戳一戳处理模式: {poke_mode}，默认忽略")
            return {"is_poke": True, "should_ignore": True}

        except Exception as e:
            # 出错时不影响主流程，只记录错误日志
            logger.error(f"【戳一戳检测】发生错误: {e}", exc_info=True)
            return {"is_poke": False, "should_ignore": False}

    async def _save_platform_descriptions_to_cache(
        self,
        event,
        platform_processed_text: str,
    ):
        """
        🆕 将平台自动理解的图片描述保存到图片描述缓存中（省钱!）

        当平台 LTM 成功提取图片描述后，将 (图片URL, 描述) 对保存到 image_description_cache，
        这样下次遇到相同图片时可以直接从缓存读取，避免调用AI转换，节省 API 费用。

        Args:
            event: 消息事件（用于提取图片组件和URL）
            platform_processed_text: 平台处理后的文本（包含 [图片内容: 描述] 格式）
        """
        if not self.image_description_cache or not self.image_description_cache.enabled:
            return

        if not platform_processed_text:
            return

        try:
            import re
            from astrbot.api.message_components import Image

            # 1. 从消息链中提取图片组件
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return

            message_chain = event.message_obj.message
            image_components = [
                comp for comp in message_chain if isinstance(comp, Image)
            ]

            if not image_components:
                return

            # 2. 从平台处理后的文本中提取图片描述
            descriptions = re.findall(
                r"\[图片内容:\s*([^\]]+)\]", platform_processed_text
            )

            if not descriptions:
                return

            # 3. 按顺序匹配图片URL和描述，保存到缓存
            save_count = 0
            for idx, img_component in enumerate(image_components):
                if idx >= len(descriptions):
                    break

                try:
                    image_path = await img_component.convert_to_file_path()
                    if not image_path:
                        continue

                    description = descriptions[idx].strip()
                    if not description:
                        continue

                    # 检查是否已在缓存中（避免重复保存）
                    cached = self.image_description_cache.lookup(image_path)
                    if cached:
                        continue

                    # 保存到缓存
                    self.image_description_cache.save(image_path, description)
                    save_count += 1

                except Exception as e:
                    logger.warning(f"[图片缓存-平台描述] 保存图片 {idx} 时失败: {e}")
                    continue

            if save_count > 0:
                logger.info(
                    f"💾 [图片缓存-平台描述] 已将 {save_count} 张平台自动理解的图片描述保存到缓存 (省钱!)"
                )

        except Exception as e:
            logger.warning(f"[图片缓存-平台描述] 保存平台描述到缓存失败: {e}")

    async def _try_cache_fallback_for_images(self, event) -> Optional[str]:
        """
        🆕 v1.2.0 省钱回退：平台描述获取失败后，从图片描述缓存中查找已缓存的图片描述

        遍历消息链，对每张图片查询 image_description_cache：
        - 命中：替换为 [图片内容: 描述]
        - 未命中：跳过该图片（不占位）
        - 同时保留消息中的文字部分

        Returns:
            构建好的带描述文本（至少一张图片命中缓存），或 None（全部未命中/缓存未启用）
        """
        if not self.image_description_cache or not self.image_description_cache.enabled:
            return None

        try:
            from astrbot.api.message_components import Image, Plain

            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return None

            message_chain = event.message_obj.message

            result_parts = []
            cache_hit_count = 0

            for component in message_chain:
                if isinstance(component, Plain):
                    if component.text:
                        result_parts.append(component.text)
                elif isinstance(component, Image):
                    try:
                        image_path = await component.convert_to_file_path()
                        if image_path:
                            cached_desc = self.image_description_cache.lookup(
                                image_path
                            )
                            if cached_desc:
                                result_parts.append(f"[图片内容: {cached_desc}]")
                                cache_hit_count += 1
                        # 未命中或无法获取路径：跳过该图片
                    except Exception:
                        continue

            if cache_hit_count == 0:
                return None

            result_text = "".join(result_parts).strip()
            if not result_text:
                return None

            logger.info(f"💰 [省钱回退] 从缓存恢复了 {cache_hit_count} 张图片的描述")
            return result_text

        except Exception as e:
            logger.warning(f"[省钱回退] 查询图片缓存时发生错误: {e}")
            return None

    async def _check_probability(
        self,
        platform_name: str,
        is_private: bool,
        chat_id: str,
        event: AstrMessageEvent,
        poke_info: dict = None,
        is_emoji_message: bool = False,
    ) -> bool:
        """
        读空气概率检查，决定是否处理消息

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            event: 消息事件对象（用于获取发送者信息）
            poke_info: 戳一戳信息（可选）
            is_emoji_message: 是否为表情包消息（v1.2.0新增）

        Returns:
            True=处理，False=跳过
        """
        # 获取当前概率
        current_probability = await ProbabilityManager.get_current_probability(
            platform_name,
            is_private,
            chat_id,
            self.initial_probability,
        )

        if self.debug_mode:
            logger.info(f"  当前概率: {current_probability:.2f}")
            logger.info(f"  初始概率: {self.initial_probability:.2f}")
            logger.info(f"  会话ID: {chat_id}")

        # 应用注意力机制调整概率
        attention_enabled = self.enable_attention_mechanism
        if attention_enabled:
            if self.debug_mode:
                logger.info("  【注意力机制】开始调整概率")

            # 获取当前消息发送者信息
            current_user_id = event.get_sender_id()
            current_user_name = event.get_sender_name()

            # 根据注意力机制调整概率
            # 如果是戳一戳消息且未跳过概率，传递戳一戳增值参考值
            poke_boost_ref = 0.0
            if poke_info and poke_info.get("is_poke"):
                poke_boost_ref = self.poke_bot_probability_boost_reference
                if self.debug_mode:
                    logger.info(
                        f"  【戳一戳增值】检测到戳一戳消息，参考值={poke_boost_ref:.2f}"
                    )
            elif self.debug_mode and poke_info:
                logger.info(
                    f"  【戳一戳增值】poke_info存在但is_poke=False: {poke_info}"
                )
            elif self.debug_mode:
                logger.info("  【戳一戳增值】poke_info为None，无戳一戳消息")

            adjusted_probability = await AttentionManager.get_adjusted_probability(
                platform_name,
                is_private,
                chat_id,
                current_user_id,
                current_user_name,
                current_probability,
                self.attention_increased_probability,
                self.attention_decreased_probability,
                self.attention_duration,
                attention_enabled,
                poke_boost_reference=poke_boost_ref,
            )

            if abs(adjusted_probability - current_probability) > 1e-9:
                logger.info(
                    f"  【注意力机制】概率已调整: {current_probability:.2f} -> {adjusted_probability:.2f}"
                )
                current_probability = adjusted_probability
            else:
                if self.debug_mode:
                    logger.info(
                        f"  【注意力机制】无需调整，使用原概率: {current_probability:.2f}"
                    )

        # 🆕 v1.2.0: 拟人增强模式 - 兴趣话题概率提升
        if self.humanize_mode_enabled:
            try:
                # 从事件中提取消息文本
                message_text = MessageCleaner.extract_raw_message_from_event(event)
                if message_text:
                    interest_boost = (
                        await HumanizeModeManager.get_interest_probability_boost(
                            message_text
                        )
                    )
                    if interest_boost > 0:
                        old_probability = current_probability
                        current_probability = min(
                            1.0, current_probability + interest_boost
                        )
                        logger.info(
                            f"  【拟人增强】检测到兴趣话题，概率提升: {old_probability:.2f} -> {current_probability:.2f} (+{interest_boost:.2f})"
                        )
            except Exception as e:
                if self.debug_mode:
                    logger.warning(f"  【拟人增强】兴趣话题检测失败，跳过: {e}")

        # 🆕 v1.2.0: 对话疲劳机制 - 概率降低
        # 设计说明：疲劳降低是特殊机制，允许突破 attention_decreased_probability 的最低限制
        # 因为疲劳机制的目的就是让连续对话过长时降低回复倾向
        if self.enable_conversation_fatigue and self.enable_attention_mechanism:
            try:
                current_user_id = event.get_sender_id()
                fatigue_info = await AttentionManager.get_conversation_fatigue_info(
                    platform_name, is_private, chat_id, current_user_id
                )
                probability_decrease = fatigue_info.get("probability_decrease", 0.0)
                if probability_decrease > 0:
                    old_probability = current_probability
                    current_probability = current_probability - probability_decrease
                    fatigue_level = fatigue_info.get("fatigue_level", "none")
                    consecutive = fatigue_info.get("consecutive_replies", 0)
                    logger.info(
                        f"  【对话疲劳】检测到{fatigue_level}疲劳(连续{consecutive}轮)，"
                        f"概率降低: {old_probability:.2f} -> {current_probability:.2f} (-{probability_decrease:.2f})"
                    )
            except Exception as e:
                if self.debug_mode:
                    logger.warning(f"  【对话疲劳】获取疲劳信息失败，跳过: {e}")

        # 🆕 v1.2.0: 表情包概率衰减
        if is_emoji_message and self.enable_emoji_filter:
            if current_probability >= self.emoji_decay_min_probability:
                old_probability = current_probability
                decay_factor = max(0.0, 1.0 - self.emoji_probability_decay)
                current_probability = current_probability * decay_factor
                logger.info(
                    f"  【表情包衰减】检测到表情包，概率衰减: "
                    f"{old_probability:.2f} -> {current_probability:.2f} "
                    f"(衰减因子={self.emoji_probability_decay}, 乘数={decay_factor:.2f})"
                )
            else:
                if self.debug_mode:
                    logger.info(
                        f"  【表情包衰减】概率 {current_probability:.2f} "
                        f"已低于门槛 {self.emoji_decay_min_probability}，跳过衰减"
                    )

        # 🆕 v1.2.1: 回复密度渐进式衰减
        if self.enable_reply_density_limit:
            try:
                chat_key = ProbabilityManager.get_chat_key(
                    platform_name, is_private, chat_id
                )
                density_factor = await ReplyDensityManager.get_probability_factor(
                    chat_key
                )
                if density_factor < 1.0:
                    old_probability = current_probability
                    current_probability = current_probability * density_factor
                    reply_count = await ReplyDensityManager.get_reply_count(chat_key)
                    logger.info(
                        f"  【回复密度】最近已回复{reply_count}次，"
                        f"概率衰减: {old_probability:.2f} -> {current_probability:.2f} "
                        f"(因子={density_factor:.2f})"
                    )
            except Exception as e:
                if self.debug_mode:
                    logger.warning(f"  【回复密度】检查失败，跳过: {e}")

        # 🆕 v1.2.1: 消息质量预判
        if self.enable_message_quality_scoring:
            try:
                message_text = MessageCleaner.extract_raw_message_from_event(event)
                if message_text:
                    quality_adjust, quality_reason = MessageQualityScorer.score_message(
                        message_text
                    )
                    if abs(quality_adjust) > 1e-9:
                        old_probability = current_probability
                        current_probability = current_probability + quality_adjust
                        logger.info(
                            f"  【消息质量】{quality_reason}，"
                            f"概率调整: {old_probability:.2f} -> {current_probability:.2f} "
                            f"({'+' if quality_adjust > 0 else ''}{quality_adjust:.2f})"
                        )
            except Exception as e:
                if self.debug_mode:
                    logger.warning(f"  【消息质量】预判失败，跳过: {e}")

        # === 最终硬性边界限制 ===
        # 1. 应用用户配置的概率硬性限制（如果启用）
        if self.enable_probability_hard_limit:
            original_prob = current_probability
            current_probability = max(
                self.probability_min_limit,
                min(self.probability_max_limit, current_probability),
            )
            if abs(original_prob - current_probability) > 1e-9:
                logger.info(
                    f"  【概率硬性限制】应用用户配置限制: {original_prob:.2f} -> {current_probability:.2f} "
                    f"(范围: [{self.probability_min_limit:.2f}, {self.probability_max_limit:.2f}])"
                )

        # 2. 系统硬性边界 [0, 1]，确保概率在有效范围内
        current_probability = max(0.0, min(1.0, current_probability))

        if self.debug_mode:
            logger.info(f"  【边界检查】最终概率: {current_probability:.2f}")

        # 随机判断
        roll = random.random()
        should_process = roll < current_probability
        if self.debug_mode:
            logger.info(
                f"读空气概率检查: 当前概率={current_probability:.2f}, 随机值={roll:.2f}, 结果={'触发' if should_process else '未触发'}"
            )

        if self.debug_mode:
            logger.info(f"  随机值: {roll:.4f}")
            logger.info(
                f"  判定: {'通过' if should_process else '失败'} ({roll:.4f} {'<' if should_process else '>='} {current_probability:.4f})"
            )

        return should_process
