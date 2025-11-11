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
版本: v1.1.0

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
import sys
import hashlib
import asyncio
from typing import List, Optional
from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.core.star.star_tools import StarTools

# 导入消息组件类型
from astrbot.core.message.components import Plain, Poke, At

# 导入 ProviderRequest 类型用于类型判断
from astrbot.core.provider.entities import ProviderRequest

# 导入 aiocqhttp 相关类型
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
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
)


@register(
    "chat_plus",
    "Him666233",
    "一个以AI读空气为主的群聊聊天效果增强插件",
    "v1.1.0",
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

        # 获取调试日志开关
        self.debug_mode = config.get("enable_debug_log", False)

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
        ContextManager.init(str(data_dir))

        # 🆕 v1.1.0: 初始化概率管理器（用于动态时间段调整）
        ProbabilityManager.initialize(config)

        # 初始化消息缓存（用于保存"通过筛选但未回复"的消息）
        # 格式: {chat_id: [{"role": "user", "content": "消息内容", "timestamp": 时间戳}]}
        self.pending_messages_cache = {}

        # 标记本插件正在处理的会话（用于after_message_sent筛选）
        # 格式: {chat_id: True}
        self.processing_sessions = {}

        # 标记被识别为指令的消息（用于跨处理器通信）
        # 格式: {message_id: timestamp}，定期清理超过10秒的旧记录
        self.command_messages = {}

        # 🆕 最近发送的回复缓存（用于去重检查）
        # 格式: {chat_id: [{"content": "回复内容", "timestamp": 时间戳}]}
        # 最多保留最近5条回复，超过30分钟的自动清理
        self.recent_replies_cache = {}

        # ========== v1.0.2 新增功能初始化 ==========

        # 1. 打字错误生成器
        self.typo_enabled = config.get("enable_typo_generator", True)
        if self.typo_enabled:
            self.typo_generator = TypoGenerator(
                error_rate=config.get("typo_error_rate", 0.02)
            )
        else:
            self.typo_generator = None

        # 2. 情绪追踪系统
        self.mood_enabled = config.get("enable_mood_system", True)
        if self.mood_enabled:
            # v1.0.6: 传入配置，支持自定义否定词和情绪关键词
            self.mood_tracker = MoodTracker(config)
        else:
            self.mood_tracker = None

        # 3. 频率动态调整器
        self.frequency_adjuster_enabled = config.get("enable_frequency_adjuster", True)
        if self.frequency_adjuster_enabled:
            self.frequency_adjuster = FrequencyAdjuster(context)
            # 设置检查间隔
            FrequencyAdjuster.CHECK_INTERVAL = config.get(
                "frequency_check_interval", 180
            )
        else:
            self.frequency_adjuster = None

        # 4. 回复延迟模拟器
        self.typing_simulator_enabled = config.get("enable_typing_simulator", True)
        if self.typing_simulator_enabled:
            self.typing_simulator = TypingSimulator(
                typing_speed=config.get("typing_speed", 15.0),
                max_delay=config.get("typing_max_delay", 3.0),
            )
        else:
            self.typing_simulator = None

        # ========== 注意力机制增强配置 ==========
        # 初始化注意力管理器（持久化存储）
        AttentionManager.initialize(str(data_dir))

        # 应用自定义配置到AttentionManager
        attention_enabled = config.get("enable_attention_mechanism", False)
        if attention_enabled:
            # 设置最大追踪用户数
            AttentionManager.MAX_TRACKED_USERS = config.get(
                "attention_max_tracked_users", 10
            )
            # 设置注意力衰减半衰期
            AttentionManager.ATTENTION_DECAY_HALFLIFE = config.get(
                "attention_decay_halflife", 300
            )
            # 设置情绪衰减半衰期
            AttentionManager.EMOTION_DECAY_HALFLIFE = config.get(
                "emotion_decay_halflife", 600
            )

        # ========== 🆕 v1.1.0 主动对话功能初始化 ==========
        self.proactive_enabled = config.get("enable_proactive_chat", False)
        if self.proactive_enabled:
            # 初始化主动对话管理器（持久化存储）
            ProactiveChatManager.initialize(str(data_dir))
            logger.info("主动对话管理器已初始化")

        # ========== 🆕 回复后戳一戳功能初始化 ==========
        self.poke_after_reply_enabled = config.get("enable_poke_after_reply", False)
        if self.poke_after_reply_enabled:
            self.poke_after_reply_probability = config.get(
                "poke_after_reply_probability", 0.15
            )
            self.poke_after_reply_delay = config.get("poke_after_reply_delay", 0.5)
            logger.info("回复后戳一戳功能已启用（仅支持QQ平台+aiocqhttp协议）")

        # ========== 🆕 收到戳一戳后反戳配置 ==========
        # 配置为概率值：[0,1]；0=禁用，1=必定反戳并丢弃本插件处理
        raw_reverse_prob = config.get("poke_reverse_on_poke_probability", 0.0)
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

        # ========== 日志输出 ==========
        logger.info("=" * 50)
        logger.info("群聊增强插件已加载 - v1.1.0")
        logger.info(f"初始读空气概率: {config.get('initial_probability', 0.1)}")
        logger.info(f"回复后概率: {config.get('after_reply_probability', 0.8)}")
        logger.info(f"概率提升持续时间: {config.get('probability_duration', 300)}秒")
        logger.info(f"启用的群组: {config.get('enabled_groups', [])} (留空=全部)")
        logger.info(f"详细日志模式: {'开启' if self.debug_mode else '关闭'}")

        # 注意力机制配置（增强版）
        attention_enabled = config.get("enable_attention_mechanism", False)
        logger.info(f"增强注意力机制: {'✓ 开启' if attention_enabled else '✗ 关闭'}")
        if attention_enabled:
            logger.info(
                f"  - 提升参考概率: {config.get('attention_increased_probability', 0.9)}"
            )
            logger.info(
                f"  - 降低参考概率: {config.get('attention_decreased_probability', 0.1)}"
            )
            logger.info(f"  - 数据清理周期: {config.get('attention_duration', 120)}秒")
            logger.info(
                f"  - 最大追踪用户: {config.get('attention_max_tracked_users', 10)}人"
            )
            logger.info(
                f"  - 注意力半衰期: {config.get('attention_decay_halflife', 300)}秒"
            )
            logger.info(
                f"  - 情绪半衰期: {config.get('emotion_decay_halflife', 600)}秒"
            )
            logger.info(
                f"  - 情绪系统: {'✓ 启用' if config.get('enable_emotion_system', True) else '✗ 禁用'}"
            )

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
            logger.info(
                f"  - 检查间隔: {config.get('frequency_check_interval', 180)} 秒"
            )
            logger.info(
                f"  - 分析消息数: {config.get('frequency_analysis_message_count', 15)} 条"
            )
            logger.info(
                f"  - 分析超时: {config.get('frequency_analysis_timeout', 20)} 秒"
            )
            logger.info(
                f"  - 调整持续: {config.get('frequency_adjust_duration', 360)} 秒"
            )
        logger.info(
            f"回复延迟模拟: {'✓ 已启用' if self.typing_simulator_enabled else '✗ 已禁用'}"
        )

        # v1.0.7 新功能状态
        logger.info("\n【v1.0.7 新增功能】")
        blacklist_enabled = config.get("enable_user_blacklist", False)
        blacklist_count = len(config.get("blacklist_user_ids", []))
        logger.info(f"用户黑名单: {'✓ 已启用' if blacklist_enabled else '✗ 已禁用'}")
        if blacklist_enabled and blacklist_count > 0:
            logger.info(f"  - 黑名单用户数: {blacklist_count} 人")
        logger.info(
            f"情绪否定词检测: {'✓ 已启用' if config.get('enable_negation_detection', True) else '✗ 已禁用'}"
        )

        # 🆕 v1.1.0 新功能状态
        logger.info("\n【🆕 v1.1.0 新增功能】")
        logger.info(
            f"主动对话功能: {'✨ 已启用' if self.proactive_enabled else '✗ 已禁用'}"
        )
        if self.proactive_enabled:
            # 白名单配置
            proactive_groups = config.get("proactive_enabled_groups", [])
            if proactive_groups and len(proactive_groups) > 0:
                logger.info(f"  - 启用群聊白名单: {proactive_groups} (仅这些群启用)")
            else:
                logger.info(f"  - 启用群聊白名单: [] (所有群启用)")

            logger.info(
                f"  - 沉默阈值: {config.get('proactive_silence_threshold', 600)} 秒"
            )
            logger.info(f"  - 触发概率: {config.get('proactive_probability', 0.3)}")
            logger.info(
                f"  - 检查间隔: {config.get('proactive_check_interval', 60)} 秒"
            )
            logger.info(
                f"  - 用户活跃度检测: {'✓' if config.get('proactive_require_user_activity', True) else '✗'}"
            )
            logger.info(
                f"  - 临时概率提升: {config.get('proactive_temp_boost_probability', 0.5)} (持续{config.get('proactive_temp_boost_duration', 120)}秒)"
            )
            if config.get("proactive_enable_quiet_time", False):
                logger.info(
                    f"  - 禁用时段: {config.get('proactive_quiet_start', '23:00')}-{config.get('proactive_quiet_end', '07:00')}"
                )

        # 🆕 v1.1.0 新功能状态 - 动态时间段概率调整
        logger.info("\n【🆕 v1.1.0 新增功能 - 动态时间段概率调整】")

        # 模式1：普通回复动态调整
        reply_time_enabled = config.get("enable_dynamic_reply_probability", False)
        logger.info(
            f"模式1-普通回复动态调整: {'✨ 已启用' if reply_time_enabled else '✗ 已禁用'}"
        )
        if reply_time_enabled:
            try:
                periods_json = config.get("reply_time_periods", "[]")
                periods = TimePeriodManager.parse_time_periods(periods_json)
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

            logger.info(
                f"  - 过渡时长: {config.get('reply_time_transition_minutes', 30)} 分钟"
            )
            logger.info(
                f"  - 系数范围: {config.get('reply_time_min_factor', 0.1):.2f} - {config.get('reply_time_max_factor', 2.0):.2f}"
            )
            logger.info(
                f"  - 平滑曲线: {'✓ 启用' if config.get('reply_time_use_smooth_curve', True) else '✗ 禁用'}"
            )

        # 模式2：主动对话动态调整
        proactive_time_enabled = config.get(
            "enable_dynamic_proactive_probability", False
        )
        logger.info(
            f"模式2-主动对话动态调整: {'✨ 已启用' if proactive_time_enabled else '✗ 已禁用'}"
        )
        if proactive_time_enabled:
            try:
                periods_json = config.get("proactive_time_periods", "[]")
                periods = TimePeriodManager.parse_time_periods(periods_json)
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

            logger.info(
                f"  - 过渡时长: {config.get('proactive_time_transition_minutes', 45)} 分钟"
            )
            logger.info(
                f"  - 系数范围: {config.get('proactive_time_min_factor', 0.0):.2f} - {config.get('proactive_time_max_factor', 2.0):.2f}"
            )
            logger.info(
                f"  - 平滑曲线: {'✓ 启用' if config.get('proactive_time_use_smooth_curve', True) else '✗ 禁用'}"
            )

            # 优先级提醒
            if self.proactive_enabled and config.get(
                "proactive_enable_quiet_time", False
            ):
                logger.info(f"  - ⚠️ 注意: '禁用时段'优先级高于动态调整")

        logger.info("=" * 50)

        if self.debug_mode:
            logger.info("【调试模式】配置详情:")
            logger.info(
                f"  - 读空气AI提供商: {config.get('decision_ai_provider_id', '默认')}"
            )
            logger.info(f"  - 包含时间戳: {config.get('include_timestamp', True)}")
            logger.info(
                f"  - 包含发送者信息: {config.get('include_sender_info', True)}"
            )
            logger.info(
                f"  - 最大上下文消息数: {config.get('max_context_messages', 20)}"
            )
            logger.info(
                f"  - 启用图片处理: {config.get('enable_image_processing', False)}"
            )
            logger.info(
                f"  - 启用记忆植入: {config.get('enable_memory_injection', False)}"
            )
            logger.info(
                f"  - 启用工具提醒: {config.get('enable_tools_reminder', False)}"
            )

    async def initialize(self):
        """
        🆕 v1.1.0: 插件激活时调用

        启动主动对话功能的后台任务
        """
        if self.proactive_enabled:
            try:
                # 启动主动对话后台任务
                await ProactiveChatManager.start_background_task(
                    self.context,
                    self,  # 传递插件实例以获取config
                    self,
                )
                logger.info("✅ [主动对话] 后台任务已启动")
            except Exception as e:
                logger.error(f"[主动对话] 启动后台任务失败: {e}", exc_info=True)

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
            # 只处理群消息
            if event.is_private_chat():
                return

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
        except Exception as e:
            # 捕获所有异常，避免影响其他插件的事件处理
            logger.error(f"[指令过滤] 处理消息时发生错误: {e}", exc_info=True)
            # 出错时直接返回，不影响其他handler的执行
            return

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """
        群消息事件监听

        采用监听模式，不影响其他插件和官方功能

        Args:
            event: 消息事件对象
        """
        try:
            # 检查是否被高优先级处理器标记为指令消息
            msg_id = self._get_message_id(event)
            if msg_id in self.command_messages:
                # 这条消息已被识别为指令，跳过处理
                if self.debug_mode:
                    logger.info("消息已被标记为指令，跳过处理")
                return

            # 【v1.0.7】检测用户是否在黑名单中
            if self._is_user_blacklisted(event):
                # 用户在黑名单中，本插件直接跳过处理
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

        blacklist_keywords = self.config.get("blacklist_keywords", [])
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
            (is_at_message, has_trigger_keyword)
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

        trigger_keywords = self.config.get("trigger_keywords", [])
        has_trigger_keyword = KeywordChecker.check_trigger_keywords(
            event, trigger_keywords
        )

        # 只在检测到关键词时记录
        if has_trigger_keyword:
            if self.debug_mode:
                logger.info("【步骤4】检测到触发关键词，跳过读空气判断")

        return is_at_message, has_trigger_keyword

    async def _check_probability_before_processing(
        self,
        event: AstrMessageEvent,
        platform_name: str,
        is_private: bool,
        chat_id: str,
        is_at_message: bool,
        has_trigger_keyword: bool,
        poke_info: dict = None,
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

        Returns:
            True=继续处理, False=丢弃消息
        """
        # 检查是否应该跳过概率判断（戳机器人的特殊处理）
        skip_probability_for_poke = False
        if poke_info and self.config.get("poke_bot_skip_probability", True):
            # 如果是戳机器人，且开关打开
            if poke_info.get("is_poke_bot"):
                skip_probability_for_poke = True
                if self.debug_mode:
                    logger.info(
                        "【步骤5】戳机器人消息，戳的是机器人，配置允许跳过概率判断。跳过概率筛选，保留读空气判断"
                    )

        # @消息、触发关键词消息、或符合条件的戳一戳消息跳过概率判断
        if (
            not is_at_message
            and not has_trigger_keyword
            and not skip_probability_for_poke
        ):
            # 概率判断
            if self.debug_mode:
                logger.info("【步骤5】开始读空气概率判断")

            should_process = await self._check_probability(
                platform_name, is_private, chat_id, event
            )
            if not should_process:
                logger.info("读空气概率判断: 不处理此消息")
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
                    logger.info("【步骤5】触发关键词消息,跳过概率判断,必定处理")

            if skip_probability_for_poke:
                if self.debug_mode:
                    logger.info("【步骤5】戳机器人消息,跳过概率判断,必定处理")

        return True

    async def _check_ai_decision(
        self,
        event: AstrMessageEvent,
        formatted_context: str,
        is_at_message: bool,
        has_trigger_keyword: bool,
        image_urls: Optional[List[str]] = None,
    ) -> bool:
        """
        执行AI决策判断（在处理完消息内容后）

        Returns:
            True=应该回复, False=不回复
        """
        # @消息或触发关键词消息跳过AI决策判断
        if not is_at_message and not has_trigger_keyword:
            # 决策AI判断
            if self.debug_mode:
                logger.info("【步骤9】调用决策AI判断是否回复")

            should_reply = await DecisionAI.should_reply(
                self.context,
                event,
                formatted_context,
                self.config.get("decision_ai_provider_id", ""),
                self.config.get("decision_ai_extra_prompt", ""),
                self.config.get("decision_ai_timeout", 30),
                self.config.get("decision_ai_prompt_mode", "append"),
                image_urls=image_urls,
            )

            if not should_reply:
                logger.info("决策AI判断: 不应该回复此消息")
                return False

            logger.info("决策AI判断: 应该回复此消息")
            return True
        else:
            # @消息或触发关键词，必定回复
            if self.debug_mode:
                logger.info("【步骤9】@消息或触发关键词,跳过AI决策,必定回复")

            return True

    async def _process_message_content(
        self,
        event: AstrMessageEvent,
        chat_id: str,
        is_at_message: bool,
        mention_info: dict = None,
        has_trigger_keyword: bool = False,
        poke_info: dict = None,
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
            (should_continue, original_message_text, processed_message, formatted_context, image_urls)
            - should_continue: 是否继续处理
            - original_message_text: 纯净的原始消息（不含元数据）
            - processed_message: 处理后的消息（图片已处理，不含元数据，用于保存）
            - formatted_context: 格式化后的完整上下文（历史消息+当前消息，当前消息已添加元数据）
            - image_urls: 图片URL列表（用于多模态AI）
        """
        # 提取纯净原始消息
        if self.debug_mode:
            logger.info("【步骤6】提取纯净原始消息")

        # 使用MessageCleaner提取纯净的原始消息（不含系统提示词）
        original_message_text = MessageCleaner.extract_raw_message_from_event(event)
        if self.debug_mode:
            logger.info(f"  纯净原始消息: {original_message_text[:100]}...")

        # 检查是否是空@消息
        is_empty_at = MessageCleaner.is_empty_at_message(
            original_message_text, is_at_message
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
        ) = await ImageHandler.process_message_images(
            event,
            self.context,
            self.config.get("enable_image_processing", False),
            self.config.get("image_to_text_scope", "all"),
            self.config.get("image_to_text_provider_id", ""),
            self.config.get("image_to_text_prompt", "请详细描述这张图片的内容"),
            is_at_message,
            self.config.get("image_to_text_timeout", 60),
        )

        if not should_continue:
            logger.info("图片处理后决定丢弃此消息（图片被过滤或处理失败）")
            if self.debug_mode:
                logger.info("【步骤6.5】图片处理判定丢弃消息，不缓存")
                logger.info("=" * 60)
            return False, None, None, None, None

        # 缓存当前用户消息（图片处理通过后再缓存）
        # 注意：缓存处理后的消息（不含元数据），在保存时再添加元数据
        # processed_message 已经是经过图片处理的最终结果（可能是过滤后、转文字后、或原始消息）
        if self.debug_mode:
            logger.info("【步骤7】缓存处理后的用户消息（不含元数据，保存时再添加）")
            logger.info(f"  原始消息（提取自event）: {original_message_text[:200]}...")
            logger.info(f"  处理后消息（图片处理后）: {processed_message[:200]}...")

        # 🆕 v1.0.4: 确定触发方式（用于后续添加系统提示）
        # 根据is_at_message和has_trigger_keyword判断触发方式
        # 注意：在这个阶段还不知道是否会AI主动回复，所以先不设置trigger_type
        # 会在后续添加元数据时根据实际情况设置

        # 缓存处理后的消息内容，不包含元数据
        # 保存发送者信息和时间戳，用于后续添加元数据

        cached_message = {
            "role": "user",
            "content": processed_message,  # 处理后的消息（可能已过滤图片、转文字、或保留原样）
            "timestamp": time.time(),
            # 保存发送者信息，用于转正时添加正确的元数据
            "sender_id": event.get_sender_id(),
            "sender_name": event.get_sender_name(),
            "message_timestamp": event.message_obj.timestamp
            if hasattr(event, "message_obj") and hasattr(event.message_obj, "timestamp")
            else None,
            # 保存@别人的信息（如果存在）
            "mention_info": mention_info,
            # 🆕 v1.0.4: 保存触发方式信息（用于后续添加系统提示）
            # 注意：is_at_message 参数可能是 should_treat_as_at，所以需要同时保存 has_trigger_keyword
            # 以便后续能正确判断触发方式
            "is_at_message": is_at_message,
            "has_trigger_keyword": has_trigger_keyword,  # 重新添加，用于正确判断触发方式
            # 🆕 v1.0.9: 保存戳一戳信息（如果存在）
            "poke_info": poke_info,
        }

        # 缓存内容日志
        # 优化：只在debug模式下或确实有问题时才记录警告
        # 空消息可能是正常的（如纯图片、纯表情、戳一戳等）
        if not original_message_text and not processed_message:
            # 只有原始和处理后都为空时才警告（可能是提取问题）
            if self.debug_mode:
                logger.info(
                    "⚠️ [缓存] 原始和处理后消息均为空（可能是纯图片/表情/戳一戳等）"
                )
        elif not original_message_text and self.debug_mode:
            logger.info("⚠️ [缓存] 原始消息为空（但处理后消息存在，可能是图片转文字）")
        elif not processed_message and self.debug_mode:
            logger.info("⚠️ [缓存] 处理后消息为空（但原始消息存在，可能是图片被过滤）")

        # 简化日志：只显示一条缓存成功的消息
        if self.debug_mode:
            logger.info(
                f"【缓存详情】原始: {original_message_text[:100] if original_message_text else '(空)'}"
            )
            logger.info(
                f"【缓存详情】处理后: {processed_message[:100] if processed_message else '(空)'}"
            )
            logger.info(
                f"【缓存详情】已缓存: {cached_message['content'][:100] if cached_message['content'] else '(空)'}"
            )
        else:
            logger.info("🔵 已缓存消息")

        if self.debug_mode:
            logger.info(f"  已缓存内容: {cached_message['content'][:200]}...")
            if processed_message != original_message_text:
                logger.info(f"  ⚠️ 消息内容有变化！原始≠处理后")
            else:
                logger.info(f"  消息内容无变化（原始==处理后）")

        if chat_id not in self.pending_messages_cache:
            self.pending_messages_cache[chat_id] = []

        # 清理旧消息
        current_time = time.time()
        cache_ttl = 1800
        old_count = len(self.pending_messages_cache[chat_id])
        self.pending_messages_cache[chat_id] = [
            msg
            for msg in self.pending_messages_cache[chat_id]
            if current_time - msg.get("timestamp", 0) < cache_ttl
        ]

        if self.debug_mode and old_count > len(self.pending_messages_cache[chat_id]):
            removed = old_count - len(self.pending_messages_cache[chat_id])
            logger.info(f"  已清理过期缓存: {removed} 条（超过30分钟）")

        # 添加到缓存
        self.pending_messages_cache[chat_id].append(cached_message)
        if len(self.pending_messages_cache[chat_id]) > 10:
            removed_msg = self.pending_messages_cache[chat_id].pop(0)
            if self.debug_mode:
                logger.info(f"  缓存已满，移除最旧消息")

        if self.debug_mode:
            logger.info(f"  缓存消息数: {len(self.pending_messages_cache[chat_id])}")

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

        message_text_for_ai = MessageProcessor.add_metadata_to_message(
            event,
            processed_message,  # 使用处理后的消息（图片已处理）
            self.config.get("include_timestamp", True),
            self.config.get("include_sender_info", True),
            mention_info,  # 传递@信息
            trigger_type,  # 🆕 v1.0.4: 传递触发方式
            poke_info,  # 🆕 v1.0.9: 传递戳一戳信息
        )

        if self.debug_mode:
            logger.info("【步骤7.5】为当前消息添加元数据（用于AI识别）")
            logger.info(f"  处理后消息: {processed_message[:100]}...")
            logger.info(f"  添加元数据后: {message_text_for_ai[:150]}...")

        # 提取历史上下文
        max_context = self.config.get("max_context_messages", 20)
        if self.debug_mode:
            logger.info("【步骤8】提取历史上下文")
            logger.info(f"  最大上下文数: {max_context}")

        history_messages = ContextManager.get_history_messages(event, max_context)

        # 合并缓存消息
        cached_messages_to_merge = []
        if (
            chat_id in self.pending_messages_cache
            and len(self.pending_messages_cache[chat_id]) > 1
        ):
            cached_messages = self.pending_messages_cache[chat_id][:-1]
            if cached_messages and history_messages:
                history_contents = set()
                for msg in history_messages:
                    if isinstance(msg, AstrBotMessage) and hasattr(msg, "message_str"):
                        history_contents.add(msg.message_str)
                    elif isinstance(msg, dict) and "content" in msg:
                        history_contents.add(msg["content"])

                for cached_msg in cached_messages:
                    if isinstance(cached_msg, dict) and "content" in cached_msg:
                        if cached_msg["content"] not in history_contents:
                            cached_messages_to_merge.append(cached_msg)
            elif cached_messages:
                cached_messages_to_merge = cached_messages

        if cached_messages_to_merge:
            if history_messages is None:
                history_messages = []
            # 将字典类型的缓存消息转换为 AstrBotMessage 对象
            for cached_msg in cached_messages_to_merge:
                if isinstance(cached_msg, dict):
                    try:
                        # 创建 AstrBotMessage 对象
                        msg_obj = AstrBotMessage()
                        msg_obj.message_str = cached_msg.get("content", "")
                        msg_obj.platform_name = event.get_platform_name()
                        msg_obj.timestamp = cached_msg.get("timestamp", time.time())
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

                        # 设置发送者信息
                        sender_id = cached_msg.get("sender_id", "")
                        sender_name = cached_msg.get("sender_name", "未知用户")
                        if sender_id:
                            msg_obj.sender = MessageMember(
                                user_id=sender_id, nickname=sender_name
                            )

                        history_messages.append(msg_obj)
                    except Exception as e:
                        logger.warning(
                            f"转换缓存消息为 AstrBotMessage 失败: {e}，跳过该消息"
                        )
                else:
                    # 如果已经是 AstrBotMessage 对象，直接添加
                    history_messages.append(cached_msg)
            if self.debug_mode:
                logger.info(f"  合并缓存消息: {len(cached_messages_to_merge)} 条")

        # 应用上下文限制
        if history_messages and max_context > 0 and len(history_messages) > max_context:
            history_messages = history_messages[-max_context:]

        if self.debug_mode:
            logger.info(
                f"  最终历史消息: {len(history_messages) if history_messages else 0} 条"
            )

        # 格式化上下文
        bot_id = event.get_self_id()
        formatted_context = await ContextManager.format_context_for_ai(
            history_messages, message_text_for_ai, bot_id
        )

        if self.debug_mode:
            logger.info(f"  格式化后长度: {len(formatted_context)} 字符")

        # 返回：原始消息文本、处理后的消息（不含元数据，用于保存）、格式化的上下文、图片URL列表
        return (
            True,
            original_message_text,
            processed_message,
            formatted_context,
            image_urls,
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

        Returns:
            生成器，用于yield回复
        """
        # 如果image_urls为None，初始化为空列表
        if image_urls is None:
            image_urls = []
        # 注入记忆
        final_message = formatted_context

        if self.config.get("enable_memory_injection", False):
            if self.debug_mode:
                logger.info("【步骤11】注入记忆内容")

            if MemoryInjector.check_memory_plugin_available(self.context):
                memories = await MemoryInjector.get_memories(self.context, event)
                if memories:
                    final_message = MemoryInjector.inject_memories_to_message(
                        final_message, memories
                    )
                    if self.debug_mode:
                        logger.info(
                            f"  已注入记忆,长度增加: {len(final_message) - len(formatted_context)} 字符"
                        )
            else:
                logger.warning("记忆插件未安装或不可用,跳过记忆注入")

        # 注入工具信息
        if self.config.get("enable_tools_reminder", False):
            if self.debug_mode:
                logger.info("【步骤12】注入工具信息")

            old_len = len(final_message)
            final_message = ToolsReminder.inject_tools_to_message(
                final_message, self.context
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

        reply_result = await ReplyHandler.generate_reply(
            event,
            self.context,
            final_message,
            self.config.get("reply_ai_extra_prompt", ""),
            self.config.get("reply_ai_prompt_mode", "append"),
            image_urls,  # 传递图片URL列表
        )

        if self.debug_mode:
            logger.info("【步骤13】AI回复生成完成")

        # 🆕 v1.0.2: 处理回复文本（添加错别字）
        if self.typo_enabled and self.typo_generator and reply_result:
            if self.debug_mode:
                logger.info("【步骤13.5】处理回复文本（可能添加错别字）")

            # 提取回复文本
            original_reply = str(reply_result)
            processed_reply = self.typo_generator.process_reply(original_reply)

            if processed_reply != original_reply:
                # 回复被修改了，更新reply_result
                reply_result = processed_reply
                if self.debug_mode:
                    logger.info("  已添加错别字")

        # 🆕 v1.0.2: 模拟打字延迟
        if self.typing_simulator_enabled and self.typing_simulator and reply_result:
            if self.debug_mode:
                logger.info("【步骤13.6】模拟打字延迟")

            await self.typing_simulator.simulate_if_needed(str(reply_result))

        # 保存用户消息（从缓存读取并添加元数据）
        if self.debug_mode:
            logger.info("【步骤14】保存用户消息")

        try:
            # 从缓存获取处理后的消息
            message_to_save = ""
            if (
                chat_id in self.pending_messages_cache
                and len(self.pending_messages_cache[chat_id]) > 0
            ):
                last_cached = self.pending_messages_cache[chat_id][-1]
                if isinstance(last_cached, dict) and "content" in last_cached:
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
                        self.config.get("include_timestamp", True),
                        self.config.get("include_sender_info", True),
                        last_cached.get("mention_info"),  # 传递@信息
                        trigger_type,  # 🆕 v1.0.4: 传递触发方式
                        last_cached.get("poke_info"),  # 🆕 v1.0.9: 传递戳一戳信息
                    )

                    # 清理系统提示（保存前过滤）
                    message_to_save = MessageCleaner.clean_message(message_to_save)

                    if self.debug_mode:
                        logger.info(
                            f"【步骤14-加元数据后】内容: {message_to_save[:150]}"
                        )

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
                    self.config.get("include_timestamp", True),
                    self.config.get("include_sender_info", True),
                    None,  # 这种情况下没有mention_info（从event提取的fallback）
                    trigger_type,  # 🆕 v1.0.4: 传递触发方式
                    None,  # 🆕 v1.0.9: 无法获取poke_info（fallback情况）
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
                # 不发送，直接返回
                return

        # 检查2: 回复是否与最近发送的回复重复（防止重复发送相同答案）
        # 仅对字符串型即时回复进行检查；LLM结果在装饰阶段处理
        if reply_text and not is_provider_request:
            # 获取或初始化该会话的回复缓存
            if chat_id not in self.recent_replies_cache:
                self.recent_replies_cache[chat_id] = []

            # 清理过期的回复记录（超过30分钟）
            current_time = time.time()
            self.recent_replies_cache[chat_id] = [
                reply
                for reply in self.recent_replies_cache[chat_id]
                if current_time - reply.get("timestamp", 0) < 1800  # 30分钟
            ]

            # 检查是否与最近5条回复重复（严格全等，仅去除首尾空白后比较）
            for recent_reply in self.recent_replies_cache[chat_id][-5:]:
                recent_content = recent_reply.get("content", "")
                if recent_content and reply_text == recent_content.strip():
                    logger.info("[消息过滤]回复与最近发送的回复重复，已过滤")
                    if self.debug_mode:
                        logger.warning(
                            f"🚫 [消息过滤] 检测到回复与最近发送的回复重复，跳过发送\n"
                            f"  最近回复: {recent_content[:100]}...\n"
                            f"  当前回复: {reply_text[:100]}..."
                        )
                    # 不发送，直接返回
                    return

        # 发送回复
        yield reply_result

        # 🆕 记录已发送的回复（用于后续去重检查）
        # 仅记录字符串型即时回复；LLM结果在 after_message_sent 钩子中记录
        if reply_text and not is_provider_request:
            if chat_id not in self.recent_replies_cache:
                self.recent_replies_cache[chat_id] = []

            # 添加到缓存（最多保留5条）
            self.recent_replies_cache[chat_id].append(
                {"content": reply_text, "timestamp": time.time()}
            )

            # 限制缓存大小
            if len(self.recent_replies_cache[chat_id]) > 5:
                self.recent_replies_cache[chat_id] = self.recent_replies_cache[chat_id][
                    -5:
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
            ProactiveChatManager.record_bot_reply(chat_key, is_proactive=False)
            if self.debug_mode:
                logger.info(f"[主动对话] 已记录AI回复（普通回复）")

        # 调整概率 / 记录注意力（二选一）
        attention_enabled = self.config.get("enable_attention_mechanism", False)

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
                attention_boost_step=self.config.get("attention_boost_step", 0.4),
                attention_decrease_step=self.config.get("attention_decrease_step", 0.1),
                emotion_boost_step=self.config.get("emotion_boost_step", 0.1),
            )

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
                self.config.get("after_reply_probability", 0.8),
                self.config.get("probability_duration", 300),
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
                        logger.info("【步骤17】开始频率动态调整检查")

                    # 获取最近的消息用于分析（使用配置的数量）
                    analysis_msg_count = self.config.get(
                        "frequency_analysis_message_count", 15
                    )
                    recent_messages = ContextManager.get_history_messages(
                        event, analysis_msg_count
                    )

                    if self.debug_mode:
                        logger.info(
                            f"[频率调整] 获取最近消息: 期望{analysis_msg_count}条, 实际{len(recent_messages) if recent_messages else 0}条"
                        )

                    if recent_messages:
                        # 构建可读的消息文本
                        # AstrBotMessage 对象的属性访问方式
                        bot_id = event.get_self_id()
                        recent_text_parts = []
                        for msg in recent_messages[-analysis_msg_count:]:  # 最近N条
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
                        analysis_timeout = self.config.get(
                            "frequency_analysis_timeout", 20
                        )
                        decision = await self.frequency_adjuster.analyze_frequency(
                            self.context,
                            event,
                            recent_text,
                            self.config.get("decision_ai_provider_id", ""),
                            analysis_timeout,
                        )

                        if decision:
                            # 获取当前概率
                            current_prob = (
                                await ProbabilityManager.get_current_probability(
                                    platform_name,
                                    is_private,
                                    chat_id,
                                    self.config.get("initial_probability", 0.1),
                                )
                            )

                            # 调整概率
                            new_prob = self.frequency_adjuster.adjust_probability(
                                current_prob, decision
                            )

                            # 如果概率有变化，应用新概率
                            if abs(new_prob - current_prob) > 0.01:
                                # 通过概率管理器设置新的基础概率
                                # 使用配置的持续时间
                                duration = self.config.get(
                                    "frequency_adjust_duration", 360
                                )
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
                        logger.info("【步骤17】频率调整检查完成")
            except Exception as e:
                logger.error(f"频率调整检查失败: {e}")

        if self.debug_mode:
            logger.info("=" * 60)
            logger.info("✓ 消息处理流程完成")

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
            except Exception as e:
                logger.error(f"【反戳】执行反戳失败: {e}")
                # 即使失败，也不影响主流程，继续正常处理
                return False

            # 已触发反戳，本插件丢弃后续处理（不拦截消息传播）
            return True

        except Exception as e:
            logger.error(f"【反戳】反戳流程发生错误: {e}")
            return False

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
            ProactiveChatManager.record_user_message(chat_key)
            # 检查并处理主动对话后的回复
            ProactiveChatManager.check_and_handle_reply_after_proactive(chat_key)

        # 步骤2: 检查消息触发器（决定是否跳过概率判断）
        is_at_message, has_trigger_keyword = await self._check_message_triggers(event)

        # 步骤2.5: 检测戳一戳信息（v1.0.9新增，在概率判断前提取）
        poke_result = self._check_poke_message(event)
        poke_info_for_probability = (
            poke_result.get("poke_info")
            if poke_result.get("is_poke") and not poke_result.get("should_ignore")
            else None
        )

        # 关键逻辑：触发关键词等同于@消息
        # 这样在 mention_only 模式下，包含关键词的消息也能正常处理图片
        should_treat_as_at = is_at_message or has_trigger_keyword

        # 只在debug模式下显示详细判断，或在特殊情况下记录
        if self.debug_mode:
            logger.info(
                f"【等同@消息】判断: {'是' if should_treat_as_at else '否'} (is_at={is_at_message}, has_keyword={has_trigger_keyword})"
            )
            logger.info("⭐ [等同@消息] 因包含触发关键词，按@消息处理")

        # 步骤3: 概率判断（第一道核心过滤，避免后续耗时处理）
        should_process = await self._check_probability_before_processing(
            event,
            platform_name,
            is_private,
            chat_id,
            is_at_message,
            has_trigger_keyword,
            poke_info_for_probability,  # 传递戳一戳信息
        )
        if not should_process:
            return

        # 步骤3.5: 检测@提及信息（在图片处理之前，避免不必要的开销）
        mention_info = await self._check_mention_others(event)

        # 步骤3.6: 使用之前检测的戳一戳信息（避免重复检测）
        poke_info = poke_info_for_probability

        # 🆕 收到戳一戳后的反戳逻辑（放在概率判断之后）：
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
        # 使用 should_treat_as_at 而不是 is_at_message，这样触发关键词也能触发图片处理
        result = await self._process_message_content(
            event,
            chat_id,
            should_treat_as_at,
            mention_info,
            has_trigger_keyword,
            poke_info,
        )
        if not result[0]:  # should_continue为False
            return

        _, original_message_text, message_text, formatted_context, image_urls = result

        # 步骤7: AI决策判断（第二道核心过滤）
        should_reply = await self._check_ai_decision(
            event, formatted_context, is_at_message, has_trigger_keyword, image_urls
        )

        if not should_reply:
            # 不回复，但保存缓存的用户消息
            if self.debug_mode:
                logger.info("【步骤9】决策AI返回NO,但保存缓存的用户消息")

            try:
                if (
                    chat_id in self.pending_messages_cache
                    and self.pending_messages_cache[chat_id]
                ):
                    last_cached_msg = self.pending_messages_cache[chat_id][-1]

                    # 获取处理后的消息内容（不含元数据）
                    raw_content = last_cached_msg["content"]

                    # 使用缓存中的发送者信息添加元数据
                    # 🆕 v1.0.4: 根据缓存中的触发方式信息确定trigger_type
                    # 注意：需要同时检查 has_trigger_keyword 来正确判断触发方式
                    trigger_type = None
                    if last_cached_msg.get("has_trigger_keyword"):
                        # 关键词触发（优先级高于@消息判断）
                        trigger_type = "keyword"
                    elif last_cached_msg.get("is_at_message"):
                        # 真正的@消息触发
                        trigger_type = "at"
                    else:
                        # 概率触发（AI主动回复）
                        trigger_type = "ai_decision"

                    message_with_metadata = MessageProcessor.add_metadata_from_cache(
                        raw_content,
                        last_cached_msg.get("sender_id", event.get_sender_id()),
                        last_cached_msg.get("sender_name", event.get_sender_name()),
                        last_cached_msg.get("message_timestamp")
                        or last_cached_msg.get("timestamp"),
                        self.config.get("include_timestamp", True),
                        self.config.get("include_sender_info", True),
                        last_cached_msg.get("mention_info"),  # 传递@信息
                        trigger_type,  # 🆕 v1.0.4: 传递触发方式
                        last_cached_msg.get("poke_info"),  # 🆕 v1.0.9: 传递戳一戳信息
                    )

                    # 清理系统提示（保存前过滤）
                    message_with_metadata = MessageCleaner.clean_message(
                        message_with_metadata
                    )

                    await ContextManager.save_user_message(
                        event,
                        message_with_metadata,
                        None,
                    )
                    logger.info(f"已保存未回复的用户消息到自定义历史（已添加元数据）")
            except Exception as e:
                logger.warning(f"保存未回复消息失败: {e}")

            if self.debug_mode:
                logger.info("=" * 60)
            return

        # 标记本插件正在处理此会话
        self.processing_sessions[chat_id] = True
        if self.debug_mode:
            logger.info(f"  已标记会话 {chat_id} 为本插件处理中")

        # 🆕 在读空气AI判定确认回复后，立即重置主动对话计时器
        # 无论是否从主动对话触发，只要AI判定要回复，就重置计时器
        if should_reply and self.proactive_enabled:
            chat_key = ProbabilityManager.get_chat_key(
                platform_name, is_private, chat_id
            )
            ProactiveChatManager.record_bot_reply(chat_key, is_proactive=False)
            if self.debug_mode:
                logger.info(f"[主动对话] 读空气AI判定确认回复，已重置主动对话计时器")

        # 步骤10-15: 生成并发送回复
        async for result in self._generate_and_send_reply(
            event,
            formatted_context,
            message_text,
            platform_name,
            is_private,
            chat_id,
            is_at_message,
            has_trigger_keyword,  # 🆕 v1.0.4: 传递触发方式信息
            image_urls,  # 传递图片URL列表（用于多模态AI）
        ):
            yield result

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        """
        在最终结果装饰阶段进行去重：
        - 仅处理由本插件标记的会话（processing_sessions）
        - 仅处理 LLM 生成的最终文本结果
        - 若与最近 5 条回复内容重复（30 分钟内），清空结果以跳过发送
        """
        try:
            platform_name = event.get_platform_name()
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            # 仅处理由本插件触发的会话
            if chat_id not in self.processing_sessions:
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

            # 清理过期缓存并进行重复检查（严格全等，仅去除首尾空白）
            now_ts = time.time()
            if chat_id not in self.recent_replies_cache:
                self.recent_replies_cache[chat_id] = []
            self.recent_replies_cache[chat_id] = [
                r
                for r in self.recent_replies_cache[chat_id]
                if now_ts - r.get("timestamp", 0) < 1800
            ]

            for recent in self.recent_replies_cache[chat_id][-5:]:
                recent_content = recent.get("content", "")
                if recent_content and reply_text == recent_content.strip():
                    logger.warning(
                        f"🚫 [装饰阶段过滤] 检测到与最近回复重复，跳过发送\n"
                        f"  最近回复: {recent_content[:100]}...\n"
                        f"  当前回复: {reply_text[:100]}..."
                    )
                    # 清空结果以阻止发送
                    event.clear_result()
                    # 清除会话标记，避免残留
                    try:
                        del self.processing_sessions[chat_id]
                    except Exception:
                        pass
                    return

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

            # 检查是否为本插件处理的会话
            if chat_id not in self.processing_sessions:
                return  # 不是本插件触发的回复，忽略

            # 清除标记（无论成功与否，都要清除）
            del self.processing_sessions[chat_id]

            # 只处理有result的消息
            if not event._result or not hasattr(event._result, "chain"):
                logger.info(f"[消息发送后] 会话 {chat_id} 没有result或chain，跳过")
                return

            # 检查是否为LLM result
            if not event._result.is_llm_result():
                logger.info(f"[消息发送后] 会话 {chat_id} 不是LLM结果，跳过")
                return

            # 提取回复文本
            bot_reply_text = "".join(
                [comp.text for comp in event._result.chain if hasattr(comp, "text")]
            )
            if not bot_reply_text:
                logger.info(f"[消息发送后] 会话 {chat_id} 回复文本为空，跳过")
                return

            if self.debug_mode:
                logger.info(
                    f"【消息发送后】会话 {chat_id} - 保存AI回复，长度: {len(bot_reply_text)} 字符"
                )

            # 保存AI回复到自定义存储
            await ContextManager.save_bot_message(event, bot_reply_text, self.context)

            # 记录到最近回复缓存（用于后续去重）
            try:
                if chat_id not in self.recent_replies_cache:
                    self.recent_replies_cache[chat_id] = []
                self.recent_replies_cache[chat_id].append(
                    {"content": bot_reply_text, "timestamp": time.time()}
                )
                if len(self.recent_replies_cache[chat_id]) > 5:
                    self.recent_replies_cache[chat_id] = self.recent_replies_cache[
                        chat_id
                    ][-5:]
            except Exception:
                pass

            # 获取用户消息（从缓存的最后一条消息）
            # 注意：缓存中的消息不包含元数据，需要在这里添加
            message_to_save = ""

            if (
                chat_id in self.pending_messages_cache
                and len(self.pending_messages_cache[chat_id]) > 0
            ):
                last_cached = self.pending_messages_cache[chat_id][-1]
                if isinstance(last_cached, dict) and "content" in last_cached:
                    # 获取处理后的消息内容（不含元数据）
                    raw_content = last_cached["content"]

                    # 强制日志：从缓存读取的内容
                    logger.info(f"🟡 [官方保存-读缓存] 内容: {raw_content[:100]}")

                    if self.debug_mode:
                        logger.info(
                            f"[消息发送后] 从缓存读取内容: {raw_content[:200]}..."
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
                        self.config.get("include_timestamp", True),
                        self.config.get("include_sender_info", True),
                        last_cached.get("mention_info"),  # 传递@信息
                        trigger_type,  # 🆕 v1.0.4: 传递触发方式
                        last_cached.get("poke_info"),  # 🆕 v1.0.9: 传递戳一戳信息
                    )

                    # 清理系统提示（保存前过滤）
                    message_to_save = MessageCleaner.clean_message(message_to_save)

                    # 强制日志：添加元数据后的内容
                    logger.info(
                        f"🟡 [官方保存-加元数据后] 内容: {message_to_save[:150]}"
                    )

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
                        self.config.get("include_timestamp", True),
                        self.config.get("include_sender_info", True),
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
            cached_messages_to_convert = []
            if (
                chat_id in self.pending_messages_cache
                and len(self.pending_messages_cache[chat_id]) > 1
            ):
                # 获取缓存中除了最后一条（当前消息）之外的消息
                raw_cached = self.pending_messages_cache[chat_id][:-1]
                logger.info(f"[消息发送后] 发现 {len(raw_cached)} 条待转正的缓存消息")

                # 处理每条缓存消息，使用缓存中的发送者信息添加元数据
                for cached_msg in raw_cached:
                    if isinstance(cached_msg, dict) and "content" in cached_msg:
                        # 获取处理后的消息内容（不含元数据）
                        raw_content = cached_msg["content"]

                        # 使用缓存中保存的发送者信息添加元数据
                        # 这样每条消息都会有正确的发送者信息
                        # 🆕 v1.0.4: 根据缓存中的触发方式信息确定trigger_type
                        # 注意：需要同时检查 has_trigger_keyword 来正确判断触发方式
                        trigger_type = None
                        if cached_msg.get("has_trigger_keyword"):
                            # 关键词触发（优先级高于@消息判断）
                            trigger_type = "keyword"
                        elif cached_msg.get("is_at_message"):
                            # 真正的@消息触发
                            trigger_type = "at"
                        else:
                            # 概率触发（AI主动回复）
                            trigger_type = "ai_decision"

                        msg_content = MessageProcessor.add_metadata_from_cache(
                            raw_content,
                            cached_msg.get("sender_id", "unknown"),
                            cached_msg.get("sender_name", "未知用户"),
                            cached_msg.get("message_timestamp")
                            or cached_msg.get("timestamp"),
                            self.config.get("include_timestamp", True),
                            self.config.get("include_sender_info", True),
                            cached_msg.get("mention_info"),  # 传递@信息
                            trigger_type,  # 🆕 v1.0.4: 传递触发方式
                            cached_msg.get("poke_info"),  # 🆕 v1.0.9: 传递戳一戳信息
                        )

                        # 清理系统提示（保存前过滤）
                        msg_content = MessageCleaner.clean_message(msg_content)

                        # 添加到转正列表
                        cached_messages_to_convert.append(
                            {
                                "role": cached_msg.get("role", "user"),
                                "content": msg_content,
                            }
                        )

                        if self.debug_mode:
                            sender_info = f"{cached_msg.get('sender_name')}(ID: {cached_msg.get('sender_id')})"
                            logger.info(
                                f"[消息发送后] 转正消息（已添加元数据，发送者: {sender_info}）: {msg_content[:100]}..."
                            )
            else:
                logger.info(f"[消息发送后] 没有待转正的缓存消息")

            # 保存到官方对话系统（包含缓存转正+去重）
            # 注意：去重逻辑在 save_to_official_conversation_with_cache 内部处理
            # 会自动过滤掉与现有官方历史重复的消息
            logger.info(
                f"[消息发送后] 准备保存: 缓存{len(cached_messages_to_convert)}条 + 当前对话(用户+AI)"
            )
            success = await ContextManager.save_to_official_conversation_with_cache(
                event,
                cached_messages_to_convert,  # 待转正的缓存消息（未去重，交给方法内部处理）
                message_to_save,  # 当前用户消息（已添加时间戳和发送者信息）
                bot_reply_text,  # AI回复
                self.context,
            )

            if success:
                logger.info(f"[消息发送后] ✅ 成功保存到官方对话系统")
                # 成功保存后，清空该会话的消息缓存
                if chat_id in self.pending_messages_cache:
                    cleared_count = len(self.pending_messages_cache[chat_id])
                    # 清空整个缓存列表
                    self.pending_messages_cache[chat_id] = []

                    if self.debug_mode:
                        logger.info(
                            f"[消息发送后] 已清空消息缓存: {cleared_count} 条消息"
                        )
                    else:
                        logger.info(f"[消息发送后] 已清空消息缓存: {cleared_count} 条")
            else:
                logger.warning(f"[消息发送后] ⚠️ 保存到官方对话系统失败")
                if self.debug_mode:
                    logger.info(f"[消息发送后] 保存失败，缓存保留（待下次使用或清理）")

        except Exception as e:
            logger.error(f"[消息发送后] 保存AI回复时发生错误: {e}", exc_info=True)

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
        enabled_groups = self.config.get("enabled_groups", [])

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

    def _get_message_id(self, event: AstrMessageEvent) -> str:
        """
        生成消息的唯一标识符

        用于跨处理器标记消息（例如标记指令消息）

        Args:
            event: 消息事件对象

        Returns:
            消息的唯一标识字符串
        """
        try:
            # 使用 发送者ID + 群组ID + 消息内容 的组合作为唯一标识
            sender_id = event.get_sender_id()
            group_id = (
                event.get_group_id() if not event.is_private_chat() else "private"
            )
            msg_content = event.get_message_str()[:100]  # 只取前100字符避免过长

            # 🔧 修复：使用 hashlib.md5 生成稳定的哈希标识（跨进程一致）
            hash_input = f"{sender_id}_{group_id}_{msg_content}".encode("utf-8")
            content_hash = hashlib.md5(hash_input).hexdigest()[:16]  # 取前16位即可
            msg_id = f"{sender_id}_{group_id}_{content_hash}"
            return msg_id
        except Exception as e:
            # 如果生成失败，返回一个基于时间的唯一ID
            return f"fallback_{time.time()}_{random.randint(1000, 9999)}"

    def _is_command_message(self, event: AstrMessageEvent) -> bool:
        """
        检测消息是否为指令消息（根据配置的指令前缀）

        支持以下格式的检测：
        1. /command 或 !command 等（直接以前缀开头）
        2. @机器人 /command（@ 机器人后跟指令）
        3. @[AT:机器人ID] /command（消息链中 @ 后跟指令）

        如果开启了指令过滤功能，并且消息以配置的前缀开头，
        则认为是指令消息，本插件应跳过处理（但不影响其他插件）

        Args:
            event: 消息事件对象

        Returns:
            True=是指令消息（应跳过），False=不是指令消息
        """
        # 检查是否启用指令过滤功能
        enable_filter = self.config.get("enable_command_filter", False)
        if not enable_filter:
            if self.debug_mode:
                logger.info("指令过滤功能未启用")
            return False

        # 获取配置的指令前缀列表
        command_prefixes = self.config.get("command_prefixes", [])
        if not command_prefixes:
            logger.warning("指令过滤已启用，但未配置指令前缀列表！")
            return False

        # 输出检测开始日志（无论是否 debug 模式，便于排查问题）
        if self.debug_mode:
            logger.info(f"开始指令检测，配置的前缀: {command_prefixes}")
            logger.info(f"消息内容: {event.get_message_str()}")

        try:
            # ✅ 关键：使用原始消息链（event.message_obj.message）
            # AstrBot 的 WakingCheckStage 会修改 event.message_str，
            # 但不会修改 event.message_obj.message！
            # 例如：用户发送 "/help"，WakingCheckStage 将 event.message_str 改为 "help"
            # 但 event.message_obj.message 中的 Plain 组件仍然是 "/help"
            original_messages = event.message_obj.message
            if not original_messages:
                if self.debug_mode:
                    logger.info("[指令检测] 原始消息链为空")
                return False

            if self.debug_mode:
                logger.info(f"[指令检测] 配置的前缀: {command_prefixes}")
                logger.info(f"[指令检测] 原始消息链组件数: {len(original_messages)}")

            # 检查原始消息链中的第一个 Plain 组件
            # 这样可以准确检测 "/help" "@mo /help" 等格式
            for component in original_messages:
                if isinstance(component, Plain):
                    # 获取第一个 Plain 组件的原始文本
                    first_text = component.text.strip()

                    if self.debug_mode:
                        logger.info(
                            f"[指令检测] 第一个Plain文本（原始）: '{first_text}'"
                        )

                    # 检查是否以任一指令前缀开头
                    for prefix in command_prefixes:
                        if prefix and first_text.startswith(prefix):
                            if self.debug_mode:
                                logger.info(
                                    f"🚫 [指令过滤] 检测到指令前缀 '{prefix}'，原始文本: {first_text[:50]}... - 插件跳过处理"
                                )
                            return True

                    # 找到第一个 Plain 组件后就停止
                    # （因为指令前缀通常在消息开头）
                    break

            if self.debug_mode:
                logger.info("[指令检测] 未检测到指令格式，继续正常处理")
            return False

        except Exception as e:
            # 出错时不影响主流程，只记录错误日志
            logger.error(f"[指令检测] 发生错误: {e}", exc_info=True)
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
            if not self.config.get("enable_user_blacklist", False):
                return False

            # 获取黑名单列表
            blacklist = self.config.get("blacklist_user_ids", [])
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
            if not self.config.get("enable_ignore_at_others", False):
                return False

            # 获取忽略模式
            ignore_mode = self.config.get("ignore_at_others_mode", "strict")

            # 获取机器人自己的ID
            bot_id = event.get_self_id()

            # 获取消息组件列表
            messages = event.get_messages()
            if not messages:
                return False

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
            poke_mode = self.config.get("poke_message_mode", "ignore")

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

    async def _check_probability(
        self,
        platform_name: str,
        is_private: bool,
        chat_id: str,
        event: AstrMessageEvent,
    ) -> bool:
        """
        读空气概率检查，决定是否处理消息

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            event: 消息事件对象（用于获取发送者信息）

        Returns:
            True=处理，False=跳过
        """
        # 获取当前概率
        current_probability = await ProbabilityManager.get_current_probability(
            platform_name,
            is_private,
            chat_id,
            self.config.get("initial_probability", 0.1),
        )

        if self.debug_mode:
            logger.info(f"  当前概率: {current_probability:.2f}")
            logger.info(
                f"  初始概率: {self.config.get('initial_probability', 0.1):.2f}"
            )
            logger.info(f"  会话ID: {chat_id}")

        # 应用注意力机制调整概率
        attention_enabled = self.config.get("enable_attention_mechanism", False)
        if attention_enabled:
            if self.debug_mode:
                logger.info("  【注意力机制】开始调整概率")

            # 获取当前消息发送者信息
            current_user_id = event.get_sender_id()
            current_user_name = event.get_sender_name()

            # 根据注意力机制调整概率
            adjusted_probability = await AttentionManager.get_adjusted_probability(
                platform_name,
                is_private,
                chat_id,
                current_user_id,
                current_user_name,
                current_probability,
                self.config.get("attention_increased_probability", 0.9),
                self.config.get("attention_decreased_probability", 0.1),
                self.config.get("attention_duration", 120),
                attention_enabled,
            )

            if adjusted_probability != current_probability:
                if self.debug_mode:
                    logger.info(
                        f"  【注意力机制】概率已调整: {current_probability:.2f} -> {adjusted_probability:.2f}"
                    )
                current_probability = adjusted_probability
            else:
                if self.debug_mode:
                    logger.info(
                        f"  【注意力机制】无需调整，使用原概率: {current_probability:.2f}"
                    )

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
