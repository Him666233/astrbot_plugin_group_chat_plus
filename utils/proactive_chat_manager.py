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
版本: v1.1.0
"""

import time
import asyncio
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from pathlib import Path
import json

from astrbot import logger
from astrbot.core.platform import AstrMessageEvent
from astrbot.core.star import Context
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.message.components import Plain
from astrbot.core.provider.entities import ProviderRequest
from astrbot.api.all import AstrBotMessage, MessageType, MessageMember


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

    # ========== 状态管理 ==========

    @classmethod
    def get_chat_state(cls, chat_key: str) -> dict:
        """
        获取群聊状态

        Args:
            chat_key: 群聊唯一标识

        Returns:
            群聊状态字典
        """
        if chat_key not in cls._chat_states:
            cls._chat_states[chat_key] = {
                "last_bot_reply_time": 0,  # 上次AI回复时间
                "last_user_message_time": 0,  # 上次用户发言时间
                "consecutive_failures": 0,  # 连续主动对话失败次数
                "is_in_cooldown": False,  # 是否在冷却期
                "cooldown_until": 0,  # 冷却结束时间
                "user_message_count": 0,  # 距离上次AI回复后的用户消息数
                "last_proactive_time": 0,  # 上次主动对话时间
                "user_message_timestamps": [],  # 用户消息时间戳列表（用于活跃度检测）
                "silent_failures": 0,  # 连续沉默失败次数
            }
        return cls._chat_states[chat_key]

    @classmethod
    def _initialize_chat_state(cls, chat_key: str):
        """
        初始化群聊状态（内部方法，在锁保护下调用）

        Args:
            chat_key: 群聊唯一标识
        """
        if chat_key not in cls._chat_states:
            cls._chat_states[chat_key] = {
                "last_bot_reply_time": 0,  # 上次AI回复时间
                "last_user_message_time": 0,  # 上次用户发言时间
                "consecutive_failures": 0,  # 连续主动对话失败次数
                "is_in_cooldown": False,  # 是否在冷却期
                "cooldown_until": 0,  # 冷却结束时间
                "user_message_count": 0,  # 距离上次AI回复后的用户消息数
                "last_proactive_time": 0,  # 上次主动对话时间
                "user_message_timestamps": [],  # 用户消息时间戳列表（用于活跃度检测）
                "silent_failures": 0,  # 连续沉默失败次数
            }

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
        cls, chat_key: str, max_failures: int, cooldown_duration: int
    ):
        """
        记录主动对话失败

        Args:
            chat_key: 群聊唯一标识
            max_failures: 最大连续失败次数
            cooldown_duration: 冷却持续时间(秒)
        """
        state = cls.get_chat_state(chat_key)
        state["consecutive_failures"] += 1

        # 重置用户消息计数和时间戳列表
        state["user_message_count"] = 0
        state["user_message_timestamps"] = []

        if state["consecutive_failures"] >= max_failures:
            # 达到最大失败次数，进入冷却
            cls.enter_cooldown(chat_key, cooldown_duration)
            logger.info(
                f"⚠️ [主动对话失败] 群{chat_key[-8:]} - "
                f"连续失败{state['consecutive_failures']}次，进入冷却期{cooldown_duration}秒"
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
        state["consecutive_failures"] = 0

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
            logger.info(f"✅ [冷却结束] 群{chat_key[-8:]} - 可以再次尝试主动对话")
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
            f"✨ [临时概率提升] 群{chat_key[-8:]} - "
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
            logger.info(
                f"🔻 [临时概率提升] 群{chat_key[-8:]} - 已取消（原因: {reason}）"
            )

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
    def check_and_handle_reply_after_proactive(cls, chat_key: str):
        """
        检查并处理主动对话后的用户回复

        如果检测到用户回复，取消临时概率提升

        Args:
            chat_key: 群聊唯一标识
        """
        if chat_key not in cls._temp_probability_boost:
            return

        state = cls.get_chat_state(chat_key)

        # 检查是否有新的用户消息
        if state["user_message_count"] > 0:
            # 有人回复了，取消临时提升
            cls.deactivate_temp_probability_boost(chat_key, "检测到用户回复")
            # 重置失败计数
            state["consecutive_failures"] = 0
            logger.info(
                f"✅ [主动对话成功] 群{chat_key[-8:]} - 有用户回复，重置失败计数"
            )

    # ========== 检查逻辑 ==========

    @classmethod
    def is_group_enabled(cls, chat_key: str, config: dict) -> bool:
        """
        🆕 检查当前群聊是否在白名单中

        Args:
            chat_key: 群聊唯一标识 (格式: "platform_name:group/private:chat_id" 或 "platform_name_group_chat_id")
            config: 插件配置

        Returns:
            True=允许主动对话, False=不允许
        """
        try:
            # 获取白名单配置
            enabled_groups = config.get("proactive_enabled_groups", [])

            # 白名单为空 = 所有群聊都启用
            if not enabled_groups or len(enabled_groups) == 0:
                logger.debug(
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
                    logger.debug(
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
                    logger.debug(
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
                    logger.debug(
                        f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（直接匹配）"
                    )
                    return True

                # 尝试字符串匹配
                if str(chat_id) in enabled_groups:
                    logger.debug(
                        f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（字符串匹配）"
                    )
                    return True

                # 尝试数字匹配（如果chat_id是数字）
                if chat_id.isdigit():
                    try:
                        if int(chat_id) in enabled_groups:
                            logger.debug(
                                f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（数字匹配）"
                            )
                            return True
                    except (ValueError, TypeError):
                        pass

                # 都不匹配，检查白名单中的每个元素
                # 处理白名单中可能是字符串或数字的情况
                for group_id in enabled_groups:
                    if str(group_id) == str(chat_id):
                        logger.debug(
                            f"[主动对话-白名单检查] ✅ chat_id={chat_id} 在白名单中（遍历匹配，group_id={group_id}）"
                        )
                        return True
                    try:
                        if int(group_id) == int(chat_id):
                            if cls._debug_mode:
                                logger.debug(
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
        if not cls.is_group_enabled(chat_key, config):
            return False, "当前群聊不在白名单中"

        # 1. 检查是否在冷却期
        if cls.is_in_cooldown(chat_key):
            remaining = int(state["cooldown_until"] - current_time)
            return False, f"在冷却期（剩余{remaining}秒）"

        # 2. 检查沉默时长
        silence_threshold = config.get("proactive_silence_threshold", 600)
        silence_duration = int(current_time - state["last_bot_reply_time"])

        if silence_duration < silence_threshold:
            return False, f"沉默时长不足（{silence_duration}/{silence_threshold}秒）"

        # 3. 检查用户活跃度
        require_user_activity = config.get("proactive_require_user_activity", True)
        if require_user_activity:
            if not cls.check_user_activity(chat_key, config):
                state = cls.get_chat_state(chat_key)
                min_messages = config.get("proactive_min_user_messages", 3)
                logger.debug(
                    f"[主动对话检查] 群{chat_key[-8:]} - 用户活跃度不足 "
                    f"(消息数={state['user_message_count']}, 最小要求={min_messages})"
                )
                return False, "用户活跃度不足"
        else:
            logger.debug(
                f"[主动对话检查] 群{chat_key[-8:]} - 已禁用用户活跃度检查，允许无用户消息时触发"
            )

        # 4. 计算有效概率（考虑时间段）
        base_prob = config.get("proactive_probability", 0.3)
        effective_prob = cls.calculate_effective_probability(base_prob, config)

        if effective_prob <= 0:
            return False, "当前时段已禁用"

        # 5. 概率判断
        roll = random.random()
        if roll >= effective_prob:
            return False, f"概率判断失败（{roll:.2f} >= {effective_prob:.2f}）"

        return True, f"触发成功（{roll:.2f} < {effective_prob:.2f}）"

    @classmethod
    def check_user_activity(cls, chat_key: str, config: dict) -> bool:
        """
        检查用户活跃度

        注意：此方法仅在 proactive_require_user_activity 为 True 时被调用。
        当该配置为 False 时，should_trigger_proactive_chat 会直接跳过此检查，
        允许在没有用户消息时也触发主动对话。

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置

        Returns:
            是否满足活跃度要求
        """
        state = cls.get_chat_state(chat_key)
        current_time = time.time()

        # 如果开启了用户活跃度检测，必须要求有用户消息
        # 如果没有用户消息记录，不满足活跃度要求
        if state["user_message_count"] == 0:
            logger.debug(
                f"[用户活跃度检查] 群{chat_key[-8:]} - 用户消息数为0，不满足活跃度要求"
            )
            return False

        # 检查是否满足最小消息数要求
        min_messages = config.get("proactive_min_user_messages", 3)
        if state["user_message_count"] < min_messages:
            logger.debug(
                f"[用户活跃度检查] 群{chat_key[-8:]} - 用户消息数({state['user_message_count']})"
                f"小于最小要求({min_messages})，不满足活跃度要求"
            )
            return False

        # 检查活跃时间窗口
        activity_window = config.get("proactive_user_activity_window", 300)
        recent_messages = [
            ts
            for ts in state["user_message_timestamps"]
            if current_time - ts <= activity_window
        ]

        # 确保时间戳列表和消息计数一致（双重检查）
        if len(recent_messages) < min_messages:
            logger.debug(
                f"[用户活跃度检查] 群{chat_key[-8:]} - 时间窗口内消息数({len(recent_messages)})"
                f"小于最小要求({min_messages})，不满足活跃度要求"
            )
            return False

        # 确保 user_message_count 和 user_message_timestamps 一致
        # 如果时间戳数量少于消息计数，说明可能有数据不一致，以时间戳为准
        if len(state["user_message_timestamps"]) < state["user_message_count"]:
            logger.warning(
                f"[用户活跃度检查] 群{chat_key[-8:]} - 数据不一致："
                f"消息计数({state['user_message_count']}) > 时间戳数量({len(state['user_message_timestamps'])})，"
                f"以时间戳为准"
            )
            if len(recent_messages) < min_messages:
                return False

        logger.debug(
            f"[用户活跃度检查] 群{chat_key[-8:]} - ✅ 满足活跃度要求 "
            f"(消息数={state['user_message_count']}, 时间窗口内={len(recent_messages)})"
        )
        return True

    # ========== 时间段控制 ==========

    @classmethod
    def calculate_effective_probability(cls, base_prob: float, config: dict) -> float:
        """
        计算有效概率（考虑时间段和过渡）

        🆕 v1.1.0: 支持动态时间段调整

        优先级规则：
        1. 原有禁用时段（proactive_enable_quiet_time）- 最高优先级，完全禁用
        2. 动态时间段调整（enable_dynamic_proactive_probability）- 调整概率系数
        3. 基础概率

        Args:
            base_prob: 基础概率
            config: 插件配置

        Returns:
            有效概率 (0.0 - 1.0)
        """
        current_time = datetime.now()

        # ========== 第一优先级：原有禁用时段（向后兼容） ==========
        if config.get("proactive_enable_quiet_time", False):
            try:
                transition_factor = cls.get_transition_factor(current_time, config)

                if transition_factor == 0.0:
                    # 在禁用时段内，直接返回0（完全禁用）
                    logger.info(
                        "[主动对话-时间控制] 在禁用时段内，概率=0（禁用时段优先级最高）"
                    )
                    return 0.0
                elif transition_factor < 1.0:
                    # 在过渡期，先应用过渡系数
                    original_prob = base_prob
                    base_prob = base_prob * transition_factor
                    logger.info(
                        f"[主动对话-时间控制] 在禁用时段过渡期，"
                        f"原始概率={original_prob:.2f}, 过渡系数={transition_factor:.2f}, "
                        f"调整后概率={base_prob:.2f}"
                    )
            except Exception as e:
                logger.error(f"[时间段计算-禁用时段] 发生错误: {e}", exc_info=True)

        # ========== 第二优先级：动态时间段调整 ==========
        if config.get("enable_dynamic_proactive_probability", False):
            try:
                # 动态导入以避免循环依赖
                from .time_period_manager import TimePeriodManager

                # 解析时间段配置（使用静默模式，避免重复输出日志）
                periods_json = config.get("proactive_time_periods", "[]")
                periods = TimePeriodManager.parse_time_periods(
                    periods_json, silent=True
                )

                if periods:
                    # 计算时间系数
                    time_factor = TimePeriodManager.calculate_time_factor(
                        current_time=current_time,
                        periods_config=periods,
                        transition_minutes=config.get(
                            "proactive_time_transition_minutes", 45
                        ),
                        min_factor=config.get("proactive_time_min_factor", 0.0),
                        max_factor=config.get("proactive_time_max_factor", 2.0),
                        use_smooth_curve=config.get(
                            "proactive_time_use_smooth_curve", True
                        ),
                    )

                    # 应用时间系数
                    original_prob = base_prob
                    base_prob = base_prob * time_factor

                    # 确保在0-1范围内
                    base_prob = max(0.0, min(1.0, base_prob))

                    if time_factor != 1.0:
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
    def get_transition_factor(cls, current_time: datetime, config: dict) -> float:
        """
        获取过渡系数

        Args:
            current_time: 当前时间
            config: 插件配置

        Returns:
            过渡系数 (0.0 - 1.0)
        """
        # 解析配置的时间
        quiet_start = cls.parse_time_config(
            config.get("proactive_quiet_start", "23:00")
        )
        quiet_end = cls.parse_time_config(config.get("proactive_quiet_end", "07:00"))
        transition_minutes = config.get("proactive_transition_minutes", 30)

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

        while cls._is_running:
            try:
                # 获取当前配置
                if hasattr(config_getter, "config"):
                    config = config_getter.config
                else:
                    config = config_getter

                # 获取检查间隔
                check_interval = config.get("proactive_check_interval", 60)

                # 等待下次检查
                await asyncio.sleep(check_interval)

                # 遍历所有群聊状态
                for chat_key in list(cls._chat_states.keys()):
                    try:
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
                                logger.info(
                                    f"[主动对话检查] 群{chat_key[-8:]} - {reason}，重置计时器"
                                )

                    except Exception as e:
                        logger.error(
                            f"[主动对话检查] 群{chat_key[-8:]} 检查失败: {e}",
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
            logger.info(f"✨ [主动对话触发] 群{chat_key[-8:]} - 开始生成主动话题")

            # 从 chat_key 解析出 platform_name、chat_id 和聊天类型
            is_private = False
            chat_id = None
            platform_name = None

            if ":" in chat_key:
                parts = chat_key.split(":")
                if len(parts) < 3:
                    logger.error(
                        f"[主动对话触发] 无效的 chat_key (冒号格式): {chat_key}"
                    )
                    return
                platform_name = parts[0]
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
                platform_name = parts[0]  # 提取平台名称
                chat_type = parts[-2]
                chat_id = parts[-1]
                is_private = chat_type == "private"
            else:
                logger.error(f"[主动对话触发] 无法识别的 chat_key 格式: {chat_key}")
                return

            # 如果无法从chat_key中提取platform_name，尝试从历史消息中获取
            if not platform_name:
                try:
                    from .context_manager import ContextManager

                    # 尝试获取历史消息来提取platform_name
                    temp_history = ContextManager.get_history_messages_by_params(
                        platform_name="aiocqhttp",  # 临时使用默认值
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
                            platform_name = msg.platform_name
                            if cls._debug_mode:
                                logger.info(
                                    f"[主动对话触发] 从历史消息中获取platform_name: {platform_name}"
                                )
                except Exception as e:
                    logger.warning(
                        f"[主动对话触发] 从历史消息获取platform_name失败: {e}"
                    )

            # 如果仍然没有platform_name，尝试从context中获取
            if not platform_name:
                try:
                    # 尝试从context的platform_manager中获取第一个平台
                    if hasattr(context, "platform_manager") and hasattr(
                        context.platform_manager, "platform_insts"
                    ):
                        if context.platform_manager.platform_insts:
                            platform_name = (
                                context.platform_manager.platform_insts[0].meta().id
                            )
                            if cls._debug_mode:
                                logger.info(
                                    f"[主动对话触发] 从context获取platform_name: {platform_name}"
                                )
                except Exception as e:
                    logger.warning(
                        f"[主动对话触发] 从context获取platform_name失败: {e}"
                    )

            # 如果还是没有platform_name，使用默认值
            if not platform_name:
                platform_name = "aiocqhttp"
                logger.warning(
                    f"[主动对话触发] 无法确定platform_name，使用默认值: {platform_name}"
                )

            # 复用主流程的逻辑，但简化版本
            await cls._process_proactive_chat_simplified(
                context=context,
                config=config,
                plugin_instance=plugin_instance,
                platform_name=platform_name,  # 使用提取的platform_name
                is_private=is_private,
                chat_id=chat_id,
                chat_key=chat_key,
            )

        except Exception as e:
            logger.error(
                f"[主动对话触发] 群{chat_key[-8:]} 发生错误: {e}", exc_info=True
            )

    @classmethod
    async def _process_proactive_chat_simplified(
        cls,
        context: Context,
        config: dict,
        plugin_instance,
        platform_name: str,
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
            from .tools_reminder import ToolsReminder

            debug_mode = config.get("debug_mode", False)

            # ========== 步骤1: 构造系统提示词 ==========
            if debug_mode:
                logger.info("[主动对话-步骤1] 构造系统提示词")

            proactive_prompt = config.get(
                "proactive_prompt",
                "你已经有一段时间没有说话了。现在你可以主动发起一个新话题，或者针对之前的对话内容做一些自然的延伸。"
                "要求：\n"
                "1. 话题要自然，不要生硬\n"
                "2. 可以是问题、分享、或感想\n"
                '3. 避免"在吗"、"干嘛呢"等低质量开场\n'
                "4. 最好与之前的聊天内容或群氛围相关\n"
                "5. 保持你的人设和语气\n"
                '6. 不要提及这是你"主动发起的"或任何元数据信息\n'
                '7. 不要说"根据提示"、"刚才的提示"等元叙述内容\n'
                "8. 就像是你自己突然想到了什么话题，很自然地说出来",
            )

            proactive_system_prompt = f"[🎯主动发起新话题]\n{proactive_prompt}"
            proactive_system_prompt = MessageCleaner.mark_proactive_chat_message(
                proactive_system_prompt
            )

            # ========== 步骤2: 提取历史上下文（从官方对话系统提取，与主动回复逻辑一致）==========
            if debug_mode:
                logger.info("[主动对话-步骤2] 提取历史上下文（从官方对话系统）")

            max_context = config.get("max_context_messages", 20)
            history_messages = []

            # 构造unified_msg_origin（用于从官方对话系统提取历史）
            message_type_str = "FriendMessage" if is_private else "GroupMessage"
            unified_msg_origin = f"{platform_name}:{message_type_str}:{chat_id}"

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

                                # 将官方历史转换为AstrBotMessage格式（用于格式化上下文）
                                # 只提取用户消息和AI回复，转换为AstrBotMessage对象
                                for msg in official_history:
                                    if (
                                        isinstance(msg, dict)
                                        and "role" in msg
                                        and "content" in msg
                                    ):
                                        msg_obj = AstrBotMessage()
                                        msg_obj.message_str = msg["content"]
                                        msg_obj.platform_name = platform_name
                                        msg_obj.timestamp = int(
                                            time.time()
                                        )  # 使用当前时间
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
                                            msg_obj.sender = MessageMember(
                                                user_id="bot", nickname="AI"
                                            )
                                        else:
                                            # 用户消息
                                            msg_obj.sender = MessageMember(
                                                user_id="user", nickname="用户"
                                            )

                                        history_messages.append(msg_obj)

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
                    logger.debug(f"[主动对话] 错误详情: {e}", exc_info=True)

            # 如果从官方对话系统获取不到历史，尝试从自定义存储获取（作为fallback）
            if not history_messages:
                if debug_mode:
                    logger.info("[主动对话] 官方对话系统无历史，尝试从自定义存储获取")

                # 先尝试使用传入的platform_name获取历史消息
                history_messages = ContextManager.get_history_messages_by_params(
                    platform_name=platform_name,
                    is_private=is_private,
                    chat_id=chat_id,
                    max_messages=max_context,
                )

                # 如果获取不到历史消息，尝试从所有可用平台中查找
                if not history_messages or len(history_messages) == 0:
                    if debug_mode:
                        logger.info(
                            f"[主动对话] 使用platform_name={platform_name}未获取到历史消息，尝试从所有平台查找"
                        )

                    # 获取所有可用平台
                    available_platforms = []
                    try:
                        if hasattr(context, "platform_manager") and hasattr(
                            context.platform_manager, "platform_insts"
                        ):
                            for platform in context.platform_manager.platform_insts:
                                platform_id = (
                                    platform.meta().id
                                    if hasattr(platform, "meta")
                                    else "unknown"
                                )
                                available_platforms.append(platform_id)
                    except Exception as e:
                        logger.warning(f"[主动对话] 获取可用平台列表失败: {e}")

                    # 尝试每个平台获取历史消息
                    for test_platform in available_platforms:
                        if test_platform == platform_name:
                            continue  # 已经试过了
                        try:
                            test_history = (
                                ContextManager.get_history_messages_by_params(
                                    platform_name=test_platform,
                                    is_private=is_private,
                                    chat_id=chat_id,
                                    max_messages=max_context,
                                )
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
                                logger.debug(
                                    f"[主动对话] 尝试平台 {test_platform} 获取历史消息失败: {e}"
                                )
                            continue

            # 合并缓存消息（主动回复模式缓存的上下文）
            # 缓存消息是还未保存到官方系统的消息，需要合并到历史上下文中
            # 注意：这里只是读取缓存，不会修改或清空 pending_messages_cache
            #      缓存的转正和清空由普通对话流程负责
            cached_messages_to_merge = []
            if (
                hasattr(plugin_instance, "pending_messages_cache")
                and chat_id in plugin_instance.pending_messages_cache
                and len(plugin_instance.pending_messages_cache[chat_id]) > 0
            ):
                cached_messages = plugin_instance.pending_messages_cache[chat_id]
                if debug_mode:
                    logger.info(
                        f"[主动对话] 发现 {len(cached_messages)} 条缓存消息（来自主动回复模式）"
                    )

                if cached_messages and history_messages:
                    # 构建历史消息内容集合（用于去重）
                    # 注意：官方历史中的消息可能包含元数据，缓存消息是原始内容，需要智能去重
                    history_contents = set()
                    for msg in history_messages:
                        if isinstance(msg, AstrBotMessage) and hasattr(
                            msg, "message_str"
                        ):
                            content = msg.message_str
                            # 添加到集合（用于精确匹配）
                            history_contents.add(content)
                            # 如果内容包含元数据标记，也提取原始内容进行匹配
                            # 例如："[2024-01-01 12:00:00] 用户: 消息内容" -> "消息内容"
                            if ":" in content and len(content) > 20:
                                # 尝试提取原始内容（去掉时间戳和发送者信息）
                                parts = content.split(":", 2)
                                if len(parts) >= 3:
                                    raw_content = parts[2].strip()
                                    if raw_content:
                                        history_contents.add(raw_content)
                        elif isinstance(msg, dict) and "content" in msg:
                            history_contents.add(msg["content"])

                    # 检查缓存消息是否已在历史中（去重）
                    for cached_msg in cached_messages:
                        if isinstance(cached_msg, dict) and "content" in cached_msg:
                            cached_content = cached_msg.get("content", "").strip()
                            if cached_content:
                                # 检查是否重复
                                if cached_content not in history_contents:
                                    cached_messages_to_merge.append(cached_msg)
                                elif debug_mode:
                                    logger.debug(
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
                            msg_obj.platform_name = platform_name
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

            # 应用上下文限制
            if (
                history_messages
                and max_context > 0
                and len(history_messages) > max_context
            ):
                history_messages = history_messages[-max_context:]

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
                history_messages, proactive_system_prompt, self_id or ""
            )

            if debug_mode:
                logger.info(f"[主动对话] 格式化后长度: {len(formatted_context)} 字符")

            # ========== 步骤4: 注入记忆、工具、情绪 ==========
            final_message = formatted_context

            # 注入记忆
            if config.get("enable_memory_injection", False):
                if debug_mode:
                    logger.info("[主动对话-步骤4.1] 注入记忆内容")

                # 注意：主动对话没有 event，需要构造一个模拟的 event 或直接调用
                # 这里我们直接调用 MemoryInjector，但需要 event 对象
                # 暂时跳过记忆注入（主动对话场景下记忆可能不太重要）
                if debug_mode:
                    logger.info("[主动对话] 跳过记忆注入（主动对话场景）")

            # 注入工具信息
            if config.get("enable_tools_reminder", False):
                if debug_mode:
                    logger.info("[主动对话-步骤4.2] 注入工具信息")

                old_len = len(final_message)
                final_message = ToolsReminder.inject_tools_to_message(
                    final_message, context
                )
                if debug_mode:
                    logger.info(
                        f"[主动对话] 已注入工具信息,长度增加: {len(final_message) - old_len} 字符"
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

            # 获取人格的 system_prompt（复用 ReplyHandler 的逻辑）
            system_prompt = ""
            contexts = []
            try:
                if hasattr(context, "provider_manager") and hasattr(
                    context.provider_manager, "personas"
                ):
                    default_persona = None
                    if hasattr(context.provider_manager, "selected_default_persona"):
                        default_persona = (
                            context.provider_manager.selected_default_persona
                        )

                    if default_persona:
                        system_prompt = default_persona.get("prompt", "")
                        begin_dialogs = default_persona.get(
                            "_begin_dialogs_processed", []
                        )
                        if begin_dialogs:
                            contexts.extend(begin_dialogs)
                        if debug_mode:
                            logger.info(
                                f"[主动对话-人格获取] 已获取人格提示词，长度: {len(system_prompt)} 字符"
                            )
            except Exception as e:
                if debug_mode:
                    logger.warning(f"[主动对话-人格获取] 获取失败: {e}")

            # 获取 provider
            provider = context.get_using_provider()
            if not provider:
                logger.error("[主动对话生成] 未找到可用的AI提供商")
                return

            logger.info(f"✨ [主动对话生成] 正在调用AI生成主动话题...")

            # 调用AI生成（复用 provider 的接口）
            completion_result = await provider.text_chat(
                prompt=final_message,
                session_id=f"{platform_name}_{chat_id}",
                contexts=contexts,
                system_prompt=system_prompt,
                image_urls=None,
                func_tool_manager=func_tools_mgr,
            )

            if not completion_result or not hasattr(
                completion_result, "completion_text"
            ):
                logger.warning("[主动对话生成] AI未生成有效内容")
                return

            generated_content = completion_result.completion_text.strip()
            logger.info(
                f"✅ [主动对话生成] AI成功生成内容，长度: {len(generated_content)} 字符"
            )

            # ========== 步骤6: 发送回复 ==========
            if debug_mode:
                logger.info("[主动对话-步骤6] 发送回复")

            try:
                message_chain = MessageChain().message(generated_content)
            except Exception as e:
                logger.error(
                    f"[主动对话发送] 群{chat_key[-8:]} - 构造消息链失败: {e}",
                    exc_info=True,
                )
                return

            # 尝试从历史消息中获取正确的platform_name（如果之前获取的不对）
            actual_platform_name = platform_name
            if history_messages:
                for msg in history_messages:
                    if (
                        isinstance(msg, AstrBotMessage)
                        and hasattr(msg, "platform_name")
                        and msg.platform_name
                    ):
                        actual_platform_name = msg.platform_name
                        if debug_mode:
                            logger.info(
                                f"[主动对话发送] 从历史消息中获取platform_name: {actual_platform_name}"
                            )
                        break

            # 获取所有可用平台
            available_platforms = []
            try:
                if hasattr(context, "platform_manager") and hasattr(
                    context.platform_manager, "platform_insts"
                ):
                    for platform in context.platform_manager.platform_insts:
                        platform_id = (
                            platform.meta().id
                            if hasattr(platform, "meta")
                            else "unknown"
                        )
                        available_platforms.append(platform_id)
            except Exception as e:
                logger.warning(f"[主动对话发送] 获取可用平台列表失败: {e}")

            # 构造session字符串
            message_type = "FriendMessage" if is_private else "GroupMessage"
            session_str = f"{actual_platform_name}:{message_type}:{chat_id}"

            if debug_mode:
                logger.info(
                    f"[主动对话发送] 准备发送消息，session={session_str}, 可用平台={available_platforms}"
                )

            # 尝试发送消息
            success = False
            used_platform = actual_platform_name

            try:
                success = await context.send_message(session_str, message_chain)
            except ValueError as ve:
                logger.error(
                    f"[主动对话发送] 群{chat_key[-8:]} - Session格式错误: {ve}, session_str={session_str}",
                    exc_info=True,
                )
                # Session格式错误，尝试其他平台
                success = False
            except Exception as send_error:
                logger.warning(
                    f"[主动对话发送] 使用平台 {actual_platform_name} 发送失败: {send_error}，将尝试其他平台"
                )
                success = False

            # 如果发送失败，尝试所有可用平台
            if not success and available_platforms:
                logger.info(
                    f"[主动对话发送] 使用平台 {actual_platform_name} 发送失败，尝试其他可用平台: {available_platforms}"
                )
                for test_platform in available_platforms:
                    if test_platform == actual_platform_name:
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
                            logger.debug(
                                f"[主动对话发送] 尝试平台 {test_platform} 失败: {e}"
                            )
                        continue

            if not success:
                logger.error(
                    f"[主动对话发送] 群{chat_key[-8:]} - 消息发送失败（所有平台都尝试失败）: "
                    f"尝试的session={session_str}, 初始platform={actual_platform_name}, "
                    f"is_private={is_private}, chat_id={chat_id}, "
                    f"可用平台={available_platforms if available_platforms else '无法获取'}"
                )
                return
            logger.info(
                f"✅ [主动对话发送] 群{chat_key[-8:]} - 消息已发送 (platform={used_platform})"
            )

            # ========== 步骤7: 保存历史（使用官方对话系统，与主动回复逻辑一致）==========
            if debug_mode:
                logger.info("[主动对话-步骤7] 保存历史到官方对话系统")

            # 导入MessageCleaner用于清理消息
            from .message_cleaner import MessageCleaner

            # 构造unified_msg_origin（与主动回复逻辑一致）
            message_type_str = "FriendMessage" if is_private else "GroupMessage"
            unified_msg_origin = f"{used_platform}:{message_type_str}:{chat_id}"

            if debug_mode:
                logger.info(f"[主动对话保存] unified_msg_origin: {unified_msg_origin}")

            # 清理系统提示词，但保留主动对话标记（让AI能理解这是主动发起的对话）
            # 系统提示词格式: "[🎯主动发起新话题]\n{实际提示内容}"
            # 使用 clean_message_preserve_proactive 保留主动对话标记，但清理其他系统提示词
            user_message = MessageCleaner.clean_message_preserve_proactive(
                proactive_system_prompt
            )
            if not user_message:
                # 如果清理后为空，使用原始提示词
                user_message = proactive_system_prompt.strip()

            # 清理AI回复（确保不包含系统提示词）
            bot_message = (
                MessageCleaner.clean_message(generated_content) or generated_content
            )

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
            # 2. 不会影响 pending_messages_cache（普通对话流程的缓存），
            #    主动对话只读取缓存用于生成回复，不会修改或清空缓存
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

            # 追加新的消息到历史记录（保留之前的完整上下文）
            # 添加用户消息（主动对话的系统提示词，已清理）
            history_list.append({"role": "user", "content": user_message})

            # 添加AI回复
            history_list.append({"role": "assistant", "content": bot_message})

            if debug_mode:
                logger.info(
                    f"[主动对话保存] 准备保存，新增2条消息，总计 {len(history_list)} 条（保留历史上下文）"
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

            # 同时保存到自定义历史（用于兼容）
            try:
                file_path = ContextManager._get_storage_path(
                    used_platform, is_private, chat_id
                )
                history = ContextManager.get_history_messages_by_params(
                    used_platform, is_private, chat_id, -1
                )
                if history is None:
                    history = []

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
                if len(history) > 200:
                    history = history[-200:]

                file_path.parent.mkdir(parents=True, exist_ok=True)
                history_dicts = [
                    ContextManager._message_to_dict(msg) for msg in history
                ]
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(history_dicts, f, ensure_ascii=False, indent=2)

                if debug_mode:
                    logger.info("主动对话系统提示已保存到自定义历史记录")
            except Exception as e:
                logger.warning(f"保存系统提示到自定义历史失败: {e}")

            # 保存AI回复到自定义历史（用于兼容）
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

            logger.info("[主动对话生成] 已将主动对话保存到官方对话系统和自定义历史记录")

            # ========== 步骤8: 记录和激活临时概率提升 ==========
            cls.record_bot_reply(chat_key, is_proactive=True)

            boost_value = config.get("proactive_temp_boost_probability", 0.5)
            boost_duration = config.get("proactive_temp_boost_duration", 120)
            cls.activate_temp_probability_boost(chat_key, boost_value, boost_duration)

        except Exception as e:
            logger.error(f"[主动对话处理] 发生错误: {e}", exc_info=True)

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

                logger.info(f"[状态持久化] 已加载 {len(cls._chat_states)} 个群聊状态")
            else:
                logger.info("[状态持久化] 未找到历史状态文件")

        except Exception as e:
            logger.error(f"[状态持久化] 加载失败: {e}")
