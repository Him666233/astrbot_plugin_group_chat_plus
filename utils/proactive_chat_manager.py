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
版本: v1.1.2
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

        # 🆕 配置合理性检查：吐槽系统配置
        cls._validate_complaint_config(config)

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

        # 检查是否启用了吐槽系统
        if not config.get("enable_complaint_system", True):
            return

        max_failures = config.get("proactive_max_consecutive_failures", 3)
        complaint_trigger = config.get("complaint_trigger_threshold", 2)
        complaint_light = config.get("complaint_level_light", 2)
        complaint_medium = config.get("complaint_level_medium", 3)
        complaint_strong = config.get("complaint_level_strong", 4)

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
                    logger.info(
                        f"🎯 [主动对话激活] 群{chat_key[-8:]} - 已发送，等待判定"
                    )
            else:
                # v1.2.0: 普通回复时，如果有活跃的主动对话，需要关闭它（双重保险）
                # 这防止了在其他流程中遗漏关闭主动对话状态的情况
                if state.get("proactive_active", False):
                    if cls._debug_mode:
                        logger.info(
                            f"🔒 [主动对话关闭] 群{chat_key[-8:]} - 普通回复时关闭活跃的主动对话"
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
                logger.debug(
                    f"[主动对话失败] 群{chat_key[-8:]} - 本次主动对话已记录过结果，跳过"
                )
            return

        # 🆕 v1.2.0: 关闭主动对话检测（已判定失败）
        state["proactive_active"] = False
        # 标记为已记录
        state["proactive_outcome_recorded"] = True

        # 🔧 修复：同时累积两个失败计数器
        state["consecutive_failures"] += 1  # 用于冷却判断

        # 🆕 累积失败次数（带上限保护）
        max_complaint_accumulation = (
            config.get("complaint_max_accumulation", 15) if config else 15
        )
        old_total = state.get("total_proactive_failures", 0)
        state["total_proactive_failures"] = min(
            old_total + 1, max_complaint_accumulation
        )

        # 🆕 v1.2.0 更新互动评分
        if config:
            cls.record_proactive_failure_for_score(chat_key, config)

        # 重置用户消息计数和时间戳列表
        state["user_message_count"] = 0
        state["user_message_timestamps"] = []

        if state["consecutive_failures"] >= max_failures:
            # 达到最大失败次数，进入冷却
            failure_count = state[
                "consecutive_failures"
            ]  # 保存失败次数，避免被重置后无法正确记录
            cls.enter_cooldown(chat_key, cooldown_duration)
            logger.info(
                f"⚠️ [主动对话失败] 群{chat_key[-8:]} - "
                f"连续失败{failure_count}次，进入冷却期{cooldown_duration}秒"
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
                logger.debug(
                    f"[主动对话] 群{chat_key[-8:]} - 普通对话模式，跳过主动对话处理"
                )
            return

        # 有主动对话相关状态，需要处理
        if has_active_proactive and not state.get("proactive_outcome_recorded", False):
            # 场景1: 有活跃的主动对话等待判定 → 判定为间接成功
            state["proactive_active"] = False
            state["proactive_outcome_recorded"] = True
            state["consecutive_failures"] = 0

            # 🆕 渐进式衰减：间接成功时也减少累积失败次数
            old_total_failures = state.get("total_proactive_failures", 0)
            decay_amount = config.get("complaint_decay_on_success", 2)
            state["total_proactive_failures"] = max(
                0, old_total_failures - decay_amount
            )

            # 调试模式：总是输出衰减信息
            if cls._debug_mode and old_total_failures > 0:
                logger.info(
                    f"📉 [累积失败衰减-间接] 群{chat_key[-8:]} - "
                    f"间接成功，累积失败次数: {old_total_failures} → {state['total_proactive_failures']} (衰减-{decay_amount})"
                )
            # 非调试模式：只在累积失败较多时输出（>=5次）
            elif not cls._debug_mode and old_total_failures >= 5:
                logger.info(
                    f"📉 [累积失败衰减-间接] 群{chat_key[-8:]} - "
                    f"间接成功，累积失败: {old_total_failures} → {state['total_proactive_failures']}"
                )

            state["consecutive_successes"] = state.get("consecutive_successes", 0) + 1
            state["proactive_attempts_count"] = 0
            state["last_proactive_content"] = None  # 🆕 清空上一次主动对话内容
            state["last_proactive_success_time"] = time.time()
            logger.info(
                f"✅ [主动对话成功-间接] 群{chat_key[-8:]} - 主动对话激活互动，AI决定回复"
            )
        elif has_attempts:
            # 场景2: 有连续尝试计数（说明之前有主动对话失败），AI决定回复，重置连续尝试
            state["consecutive_failures"] = 0

            # 🆕 渐进式衰减：AI决定回复时也减少累积失败次数
            old_total_failures = state.get("total_proactive_failures", 0)
            decay_amount = config.get("complaint_decay_on_success", 2)
            state["total_proactive_failures"] = max(
                0, old_total_failures - decay_amount
            )

            # 调试模式：总是输出衰减信息
            if cls._debug_mode and old_total_failures > 0:
                logger.info(
                    f"📉 [累积失败衰减-决定回复] 群{chat_key[-8:]} - "
                    f"AI决定回复，累积失败次数: {old_total_failures} → {state['total_proactive_failures']} (衰减-{decay_amount})"
                )
            # 非调试模式：只在累积失败较多时输出（>=5次）
            elif not cls._debug_mode and old_total_failures >= 5:
                logger.info(
                    f"📉 [累积失败衰减-决定回复] 群{chat_key[-8:]} - "
                    f"AI决定回复，累积失败: {old_total_failures} → {state['total_proactive_failures']}"
                )

            state["proactive_attempts_count"] = 0
            state["last_proactive_content"] = None  # 🆕 清空上一次主动对话内容
            state["last_proactive_success_time"] = time.time()
            if cls._debug_mode:
                logger.debug(
                    f"[主动对话] 群{chat_key[-8:]} - AI决定回复，重置连续尝试计数"
                )

    # ========== 🆕 v1.2.0 互动评分系统 ==========

    @classmethod
    def update_interaction_score(
        cls, chat_key: str, delta: int, reason: str, config: dict
    ):
        """
        更新互动评分

        Args:
            chat_key: 群聊唯一标识
            delta: 评分变化量（正数加分，负数扣分）
            reason: 变化原因
            config: 插件配置
        """
        if not config.get("enable_adaptive_proactive", True):
            return

        state = cls.get_chat_state(chat_key)
        old_score = state.get("interaction_score", 50)

        # 计算新评分（限制在10-100范围内）
        min_score = config.get("interaction_score_min", 10)
        max_score = config.get("interaction_score_max", 100)
        new_score = max(min_score, min(max_score, old_score + delta))

        state["interaction_score"] = new_score

        # 记录评分变化
        # 调试模式：输出所有变化
        if cls._debug_mode:
            logger.info(
                f"📊 [互动评分] 群{chat_key[-8:]} - {reason}: {old_score}分 → {new_score}分 (变化{delta:+d})"
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
                    f"📊 [互动评分] 群{chat_key[-8:]} - {reason}: {old_score}分 → {new_score}分 (变化{delta:+d})"
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
        if not config.get("enable_adaptive_proactive", True):
            return

        state = cls.get_chat_state(chat_key)

        # 🆕 v1.2.0: 防止重复记录成功
        if state.get("proactive_outcome_recorded", False):
            if cls._debug_mode:
                logger.debug(
                    f"[主动对话成功] 群{chat_key[-8:]} - 本次主动对话已记录过结果，跳过"
                )
            return

        # 🆕 v1.2.0: 关闭主动对话检测（已判定成功）
        state["proactive_active"] = False
        # 标记为已记录
        state["proactive_outcome_recorded"] = True

        current_time = time.time()

        # 🔧 修复：重置失败相关计数（成功后处理）
        state["consecutive_failures"] = 0  # 重置连续失败次数

        # 🆕 渐进式衰减：成功时减少累积失败次数，而不是完全清零
        # 这样更拟人化：偶尔的失败不会因为历史累积而触发过度的吐槽
        old_total_failures = state.get("total_proactive_failures", 0)
        decay_amount = config.get("complaint_decay_on_success", 2)
        state["total_proactive_failures"] = max(0, old_total_failures - decay_amount)

        # 调试模式：总是输出衰减信息
        if cls._debug_mode and old_total_failures > 0:
            logger.info(
                f"📉 [累积失败衰减] 群{chat_key[-8:]} - "
                f"成功互动，累积失败次数: {old_total_failures} → {state['total_proactive_failures']} (衰减-{decay_amount})"
            )
        # 非调试模式：只在累积失败较多时输出（>=5次）
        elif not cls._debug_mode and old_total_failures >= 5:
            logger.info(
                f"📉 [累积失败衰减] 群{chat_key[-8:]} - "
                f"成功互动，累积失败: {old_total_failures} → {state['total_proactive_failures']}"
            )

        state["consecutive_successes"] = state.get("consecutive_successes", 0) + 1
        state["last_proactive_success_time"] = current_time  # 记录上次成功时间

        # 更新成功统计
        state["successful_interactions"] = state.get("successful_interactions", 0) + 1
        state["last_success_time"] = current_time

        # 基础加分
        base_increase = config.get("score_increase_on_success", 15)
        total_increase = base_increase

        reason_parts = ["有人回复"]

        # 快速回复额外加分
        if is_quick:
            quick_bonus = config.get("score_quick_reply_bonus", 5)
            total_increase += quick_bonus
            state["quick_reply_count"] = state.get("quick_reply_count", 0) + 1
            reason_parts.append("快速回复+{0}".format(quick_bonus))

        # 多人回复额外加分
        if is_multi_user:
            multi_bonus = config.get("score_multi_user_bonus", 10)
            total_increase += multi_bonus
            state["multi_user_reply_count"] = state.get("multi_user_reply_count", 0) + 1
            reason_parts.append("多人接话+{0}".format(multi_bonus))

        # 连续成功加速奖励
        if state["consecutive_successes"] >= 3:
            streak_bonus = config.get("score_streak_bonus", 5)
            total_increase += streak_bonus
            reason_parts.append("连续成功+{0}".format(streak_bonus))

        # 从低分复苏奖励
        current_score = state.get("interaction_score", 50)
        if current_score < 30:
            revival_bonus = config.get("score_revival_bonus", 20)
            total_increase += revival_bonus
            reason_parts.append("低分复苏+{0}".format(revival_bonus))

        reason = "，".join(reason_parts)
        cls.update_interaction_score(chat_key, total_increase, reason, config)

    @classmethod
    def record_proactive_failure_for_score(cls, chat_key: str, config: dict):
        """
        记录主动对话失败（无人回复）- 仅用于评分系统

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置
        """
        if not config.get("enable_adaptive_proactive", True):
            return

        state = cls.get_chat_state(chat_key)

        # 更新失败统计
        state["failed_interactions"] = state.get("failed_interactions", 0) + 1
        state["consecutive_successes"] = 0  # 重置连续成功

        # 获取当前评分（用于判断是否需要警告）
        current_score = state.get("interaction_score", 50)

        # 扣分
        decrease = config.get("score_decrease_on_fail", 8)
        cls.update_interaction_score(chat_key, -decrease, "无人回复", config)

        # 非调试模式：在评分较低时给出警告
        if not cls._debug_mode and current_score <= 30:
            logger.warning(
                f"⚠️ [主动对话] 群{chat_key[-8:]} - 互动评分较低({current_score}分)，主动对话响应不佳"
            )

    @classmethod
    def apply_score_decay(cls, config: dict):
        """
        应用评分衰减（每24小时执行一次）

        Args:
            config: 插件配置
        """
        if not config.get("enable_adaptive_proactive", True):
            return

        current_time = time.time()
        decay_interval = 24 * 3600  # 24小时
        decay_rate = config.get("interaction_score_decay_rate", 2)

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
                        chat_key, -decay_rate, "24小时无互动自然衰减", config
                    )
                    decay_count += 1

                # 更新衰减时间
                state["last_score_decay_time"] = current_time

        # 非调试模式：输出汇总信息（只在有衰减时）
        if not cls._debug_mode and decay_count > 0:
            logger.info(f"📉 [评分衰减] 已对 {decay_count} 个群聊执行24小时无互动衰减")

    @classmethod
    def apply_complaint_decay(cls, config: dict):
        """
        🆕 应用累积失败次数的时间自然衰减

        改进逻辑：
        1. 长时间没有新的失败，失败次数会逐渐减少
        2. 防止历史累积的失败次数影响当前的吐槽判断
        3. 更拟人化：偶尔的失败不会因为历史原因触发过度吐槽

        Args:
            config: 插件配置
        """
        if not config.get("enable_complaint_system", True):
            return

        current_time = time.time()
        # 每隔一段时间检查一次（默认6小时）
        check_interval = config.get("complaint_decay_check_interval", 6 * 3600)
        # 多久没有新失败就开始衰减（默认12小时）
        no_failure_threshold = config.get(
            "complaint_decay_no_failure_threshold", 12 * 3600
        )
        # 每次衰减的数量（默认1次）
        decay_amount = config.get("complaint_decay_amount", 1)

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
                                    f"🕐 [时间自然衰减] 群{chat_key[-8:]} - "
                                    f"{time_since_last_activity / 3600:.1f}小时无主动对话活动，"
                                    f"累积失败次数: {old_failures} → {new_failures} (衰减-{decay_amount})"
                                )

                    # 更新检查时间
                    state["last_complaint_decay_time"] = current_time

            except Exception as e:
                logger.error(
                    f"[时间自然衰减] 处理群{chat_key[-8:]}时出错: {e}", exc_info=True
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
    def calculate_adaptive_parameters(cls, chat_key: str, config: dict) -> dict:
        """
        根据互动评分计算自适应参数

        ⚠️ 重要：此方法返回的是调整系数，不是最终值
        最终概率计算顺序：基础概率 → 时间段调整 → 自适应系数

        Args:
            chat_key: 群聊唯一标识
            config: 插件配置

        Returns:
            包含调整参数和系数的字典
        """
        if not config.get("enable_adaptive_proactive", True):
            # 未启用自适应，返回原始参数（系数为1.0，不调整）
            return {
                "prob_multiplier": 1.0,  # 概率系数
                "silence_threshold": config.get("proactive_silence_threshold", 600),
                "cooldown_duration": config.get("proactive_cooldown_duration", 1800),
                "max_failures": config.get("proactive_max_consecutive_failures", 2),
                "score": 50,
                "level": "友好群😊",
            }

        state = cls.get_chat_state(chat_key)
        score = state.get("interaction_score", 50)

        # 基础参数（非概率参数直接计算）
        base_silence = config.get("proactive_silence_threshold", 600)
        base_cooldown = config.get("proactive_cooldown_duration", 1800)
        base_max_failures = config.get("proactive_max_consecutive_failures", 2)

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

        return {
            "prob_multiplier": prob_multiplier,  # ⚠️ 返回系数，不是最终概率
            "silence_threshold": int(base_silence * silence_multiplier),
            "cooldown_duration": int(base_cooldown * cooldown_multiplier),
            "max_failures": max_failures,
            "score": score,
            "level": cls.get_score_level(score),
        }

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

        if not config.get("enable_complaint_system", True):
            return default_result

        state = cls.get_chat_state(chat_key)
        # 🔧 修复：使用累积失败次数而不是连续失败次数
        total_failures = state.get("total_proactive_failures", 0)
        score = state.get("interaction_score", 50)

        # 根据配置的阈值决定是否触发吐槽
        complaint_threshold = config.get("complaint_trigger_threshold", 2)
        if total_failures < complaint_threshold:
            default_result["failure_count"] = total_failures
            return default_result

        # 获取各等级吐槽的触发次数和概率
        light_threshold = config.get("complaint_level_light", 2)
        medium_threshold = config.get("complaint_level_medium", 3)
        strong_threshold = config.get("complaint_level_strong", 4)

        # 按从高到低的顺序检查（优先匹配更严重的等级）
        if total_failures >= strong_threshold:
            # 强烈吐槽
            complaint_prob = config.get("complaint_probability_strong", 0.8)
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
            complaint_prob = config.get("complaint_probability_medium", 0.6)
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
            complaint_prob = config.get("complaint_probability_light", 0.3)
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

        # 🆕 v1.2.0 获取自适应参数（根据互动评分调整）
        adaptive_params = cls.calculate_adaptive_parameters(chat_key, config)
        silence_threshold = adaptive_params["silence_threshold"]
        prob_multiplier = adaptive_params["prob_multiplier"]

        # 2. 检查沉默时长（使用自适应阈值）
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

        # 4. 计算有效概率（正确的顺序）
        # 步骤1: 获取用户配置的基础概率
        base_prob = config.get("proactive_probability", 0.3)

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
        if cls._debug_mode and config.get("enable_adaptive_proactive", True):
            logger.info(
                f"📊 [自适应参数] 群{chat_key[-8:]} - {adaptive_params['level']} "
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

                    if time_factor != 1.0 and cls._debug_mode:
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
                check_interval = config.get("proactive_check_interval", 60)

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
                    cls.apply_score_decay(config)
                    cls.apply_complaint_decay(
                        config
                    )  # 🆕 同时执行累积失败次数的时间衰减
                    last_decay_time = current_time

                # 遍历所有群聊状态
                for chat_key in list(cls._chat_states.keys()):
                    try:
                        current_time = time.time()

                        # 🆕 v1.2.0 获取自适应参数（根据互动评分调整）
                        adaptive_params = cls.calculate_adaptive_parameters(
                            chat_key, config
                        )
                        max_failures = adaptive_params["max_failures"]
                        cooldown_duration = adaptive_params["cooldown_duration"]

                        # 固定参数
                        boost_duration = config.get(
                            "proactive_temp_boost_duration", 120
                        )

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
                                    f"[连续尝试] 群{chat_key[-8:]} 处于维持期内，跳过本轮should_trigger检查"
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
                                    if not cls.is_group_enabled(chat_key, config):
                                        if cls._debug_mode:
                                            logger.info(
                                                f"[连续尝试] 群{chat_key[-8:]} 不在白名单，跳过连续尝试"
                                            )
                                        continue

                                    base_prob = config.get("proactive_probability", 0.3)
                                    eff_prob = cls.calculate_effective_probability(
                                        base_prob, config
                                    )
                                    if eff_prob <= 0:
                                        logger.info(
                                            f"[连续尝试] 群{chat_key[-8:]} 处于禁用/极低时段，跳过本次连续尝试"
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
            logger.error(
                f"[主动对话触发] 群{chat_key[-8:]} 发生错误: {e}", exc_info=True
            )

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
            from .tools_reminder import ToolsReminder

            debug_mode = config.get("debug_mode", False)

            # ========== 步骤1: 构造系统提示词 ==========
            if debug_mode:
                logger.info("[主动对话-步骤1] 构造系统提示词")

            # 构造详细的主动对话提示词（参考 reply_handler.py 的风格）
            default_proactive_prompt = """
你已经有一段时间没有说话了。现在你可以主动发起一个新话题，或者针对之前的对话内容做一些自然的延伸。

核心要求：
1. **话题要自然** - 不要生硬，就像是你自己突然想到了什么话题
2. **可以是问题、分享、或感想** - 展现你的个性和想法
3. **避免低质量开场** - 禁止"在吗"、"干嘛呢"、"有人吗"等无聊开场
4. **与上下文相关** - 最好与之前的聊天内容或群氛围相关
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
- 可以延续之前的话题
- 可以聊聊最近发生的事
- 可以开个玩笑或调侃
- 可以表达一下感想

记住：就像是你自己突然想到了什么，很自然地说出来，不要有任何关于"主动发起"的痕迹。
"""
            proactive_prompt = config.get("proactive_prompt", default_proactive_prompt)

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
                retry_prompt_template = config.get(
                    "proactive_retry_prompt", default_retry_prompt
                )

                # 替换 {last_content} 占位符为实际内容
                retry_context = retry_prompt_template.format(last_content=last_content)

                proactive_prompt = retry_context + "\n" + proactive_prompt

                if debug_mode:
                    logger.info(
                        f"🔄 [主动对话-重试] 群{chat_key[-8:]} - "
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
                    f"🤐 [主动对话-吐槽触发] 群{chat_key[-8:]} - "
                    f"累积失败{complaint_info.get('failure_count', 0)}次，"
                    f"触发{complaint_level}级吐槽，优先发送吐槽信息"
                )
            elif is_complaint_triggered and complaint_prompt_text:
                # 普通模式：附加吐槽提示词到主动对话提示词
                proactive_prompt += complaint_prompt_text
                logger.info(
                    f"💬 [主动对话-吐槽附加] 群{chat_key[-8:]} - "
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

            # ========== 步骤1.5: 🆕 注入注意力用户信息（如果启用）==========
            if config.get("enable_attention_mechanism", False) and config.get(
                "proactive_use_attention", True
            ):
                if debug_mode:
                    logger.info("[主动对话-步骤1.5] 注入注意力用户信息")

                try:
                    # 🆕 步骤1.5.1: 概率判断是否参考注意力排行榜
                    reference_probability = config.get(
                        "proactive_attention_reference_probability", 0.7
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
                        weight_str = config.get(
                            "proactive_attention_rank_weights", "1:55,2:25,3:12,4:8"
                        )
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
                        max_selected = config.get(
                            "proactive_attention_max_selected_users", 2
                        )

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
                        focus_probability = config.get(
                            "proactive_focus_last_user_probability", 0.6
                        )
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

                            # 添加用户信息
                            prefix = f"{idx}. "
                            if is_last_user:
                                prefix = f"{idx}. ⭐ "
                                attention_info += (
                                    f"{prefix}**{user_name}** "
                                    f"[注意力: {attention_score:.2f}] {emotion_desc}\n"
                                )
                                attention_info += (
                                    f"   💬 提示：这是你上一次主要互动的对象，"
                                    f"可以考虑延续之前的话题或关心ta的近况\n\n"
                                )
                            else:
                                attention_info += (
                                    f"{prefix}{user_name} "
                                    f"[注意力: {attention_score:.2f}] {emotion_desc}\n"
                                )

                        attention_info += (
                            "\n💡 **使用建议**：\n"
                            "- 你可以根据上述用户的注意力和情绪，选择合适的话题方向\n"
                            "- 但这只是参考，不一定非要提到他们，也可以聊其他话题\n"
                            "- 如果选择关注这些用户，请自然地融入话题，不要显得刻意\n"
                            '- ⚠️ 重要：不要在回复中提及"注意力"、"情绪"、"排行榜"等元信息\n'
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

            max_context = config.get("max_context_messages", 20)

            # 🔧 配置矫正：处理异常值
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
            # 但如果配置为0，则不获取任何历史
            if not history_messages and not (
                isinstance(max_context, int) and max_context == 0
            ):
                if debug_mode:
                    logger.info("[主动对话] 官方对话系统无历史，尝试从自定义存储获取")

                # 🔧 修复：使用platform_id获取历史消息
                # 注意：ContextManager存储时使用的是platform_name，但实际可能是platform_id
                # 🔧 修复：先获取所有历史消息（max_messages=-1），稍后统一应用限制
                history_messages = ContextManager.get_history_messages_by_params(
                    platform_name=platform_id,  # 先尝试使用platform_id
                    is_private=is_private,
                    chat_id=chat_id,
                    max_messages=-1,  # 先获取所有历史，稍后统一应用限制
                )

                # 如果获取不到历史消息，尝试从所有可用平台中查找
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
                                platform_inst_id = (  # 🔧 修复：使用不同的变量名避免覆盖函数参数
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
                            test_history = (
                                ContextManager.get_history_messages_by_params(
                                    platform_name=test_platform,
                                    is_private=is_private,
                                    chat_id=chat_id,
                                    max_messages=-1,  # 先获取所有历史，稍后统一应用限制
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
                    key=lambda msg: msg.timestamp
                    if hasattr(msg, "timestamp") and msg.timestamp
                    else 0
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
                include_timestamp=config.get("include_timestamp", True),
                include_sender_info=config.get("include_sender_info", True),
            )

            if debug_mode:
                logger.info(f"[主动对话] 格式化后长度: {len(formatted_context)} 字符")

            # ========== 步骤4: 注入记忆、工具、情绪 ==========
            final_message = formatted_context

            # 注入记忆
            if config.get("enable_memory_injection", False):
                if debug_mode:
                    logger.info("[主动对话-步骤4.1] 注入记忆内容")

                # 获取记忆插件配置
                memory_mode = config.get("memory_plugin_mode", "legacy")
                livingmemory_top_k = config.get("livingmemory_top_k", 5)

                # 使用新的 get_memories_by_session 方法获取记忆（无需 event 对象）
                if MemoryInjector.check_memory_plugin_available(
                    context, mode=memory_mode
                ):
                    try:
                        memories = await MemoryInjector.get_memories_by_session(
                            context,
                            unified_msg_origin,
                            mode=memory_mode,
                            top_k=livingmemory_top_k,
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

            # 获取 provider
            provider = context.get_using_provider()
            if not provider:
                logger.error("[主动对话生成] 未找到可用的AI提供商")
                return

            logger.info(f"✨ [主动对话生成] 正在调用AI生成主动话题...")

            # 调用AI生成（复用 provider 的接口）
            # 【关键修复】不使用contexts参数，避免Agent模式下上下文丢失
            _generation_start = time.time()
            completion_result = await provider.text_chat(
                prompt=final_message,
                session_id=f"{platform_id}_{chat_id}",  # 🔧 修复：使用platform_id
                contexts=[],  # 【修复】不使用contexts，避免Agent模式下冲突
                system_prompt=system_prompt,
                image_urls=None,
                func_tool_manager=func_tools_mgr,
            )
            _generation_elapsed = time.time() - _generation_start

            if not completion_result or not hasattr(
                completion_result, "completion_text"
            ):
                logger.warning("[主动对话生成] AI未生成有效内容")
                return

            generated_content = completion_result.completion_text.strip()

            # 耗时监控和警告
            timeout_warning = config.get("proactive_generation_timeout_warning", 15)
            if _generation_elapsed > timeout_warning:
                logger.warning(
                    f"⚠️ [主动对话生成] AI生成耗时异常: {_generation_elapsed:.2f}秒（超过{timeout_warning}秒）"
                )
            elif debug_mode:
                logger.info(f"[主动对话生成] AI生成耗时: {_generation_elapsed:.2f}秒")

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
                    f"[主动对话发送] 群{chat_key[-8:]} - Session格式错误: {ve}, session_str={session_str}",
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
                            logger.debug(
                                f"[主动对话发送] 尝试平台 {test_platform} 失败: {e}"
                            )
                        continue

            if not success:
                logger.error(
                    f"[主动对话发送] 群{chat_key[-8:]} - 消息发送失败（所有平台都尝试失败）: "
                    f"尝试的session={session_str}, 初始platform_id={actual_platform_id}, "
                    f"is_private={is_private}, chat_id={chat_id}, "
                    f"可用平台={available_platforms if available_platforms else '无法获取'}"
                )
                return
            logger.info(
                f"✅ [主动对话发送] 群{chat_key[-8:]} - 消息已发送 (platform_id={used_platform})"
            )

            # 🆕 保存本次主动对话内容，用于下次重试时提醒AI
            state["last_proactive_content"] = generated_content
            if debug_mode:
                logger.info(
                    f"💾 [主动对话-保存内容] 群{chat_key[-8:]} - "
                    f"已保存本次主动对话内容（{len(generated_content)}字符），用于重试场景"
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
