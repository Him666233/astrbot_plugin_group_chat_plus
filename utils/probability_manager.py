"""
概率管理器模块
负责管理和动态调整读空气概率

v1.1.0 更新：
- 🆕 支持临时概率提升（主动对话后的等待回应状态）
- 🆕 支持动态时间段概率调整（模拟人类作息）
- 🆕 支持概率硬性限制（一键简化功能，强制限制概率范围）
- 临时提升优先级高于常规提升
- 时间调整与其他功能自动配合，不冲突
- 硬性限制在所有调整的最末尾应用

作者: Him666233
版本: V1.2.3.hotfix.2
"""

import time
import asyncio
import copy
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING
from astrbot.api.all import *
from ._session_guard import guard_session

if TYPE_CHECKING:
    pass

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class ProbabilityManager:
    """
    概率管理器

    主要功能：
    1. 管理每个会话的读空气概率
    2. AI回复后临时提升概率
    3. 🆕 v1.1.0: 支持主动对话后的临时概率提升
    4. 🆕 v1.1.0: 支持动态时间段概率调整
    5. 🆕 v1.1.0: 支持概率硬性限制（一键简化功能）
    6. 超时后自动恢复初始概率

    优先级顺序（从高到低）：
    1. 临时概率提升（主动对话后）
    2. 常规概率提升（回复后）
    3. 动态时间段调整
    4. 基础概率（initial_probability）
    5. 概率硬性限制（最末尾强制限制，覆盖所有调整结果）
    """

    # 使用字典保存每个聊天的概率状态
    # 格式:
    # {
    #   chat_key: {
    #       "base_probability": float,
    #       "base_until": timestamp,
    #       "base_source": str,
    #       "reply_boost_probability": float,
    #       "reply_boost_until": timestamp,
    #       "reply_boost_source": str,
    #   }
    # }
    _probability_status: Dict[str, Dict[str, Any]] = {}
    _lock = asyncio.Lock()  # 异步锁

    # 🆕 v1.1.0: 插件配置引用（用于动态时间调整）
    _plugin_config: Optional[dict] = None

    # ========== 🔧 配置参数集中提取（避免运行时多次读取） ==========
    # 动态时间段调整配置
    _enable_dynamic_reply_probability: bool = False
    _reply_time_periods: str = "[]"
    _reply_time_transition_minutes: int = 30
    _reply_time_min_factor: float = 0.1
    _reply_time_max_factor: float = 2.0
    _reply_time_use_smooth_curve: bool = True
    # 概率硬性限制配置
    _enable_probability_hard_limit: bool = False
    _probability_min_limit: float = 0.05
    _probability_max_limit: float = 0.8

    @staticmethod
    def initialize(config: dict):
        """
        🆕 v1.1.0: 初始化概率管理器

        说明：配置由 main.py 统一提取后传入，此处直接使用传入的值，
        不再提供默认值（避免 AstrBot 平台多次读取配置的问题）

        Args:
            config: 插件配置字典（由 main.py 统一提取）
        """
        ProbabilityManager._plugin_config = config

        # ========== 🔧 直接使用传入的配置值 ==========
        # 动态时间段调整配置
        ProbabilityManager._enable_dynamic_reply_probability = config[
            "enable_dynamic_reply_probability"
        ]
        ProbabilityManager._reply_time_periods = config["reply_time_periods"]
        ProbabilityManager._reply_time_transition_minutes = config[
            "reply_time_transition_minutes"
        ]
        ProbabilityManager._reply_time_min_factor = config["reply_time_min_factor"]
        ProbabilityManager._reply_time_max_factor = config["reply_time_max_factor"]
        ProbabilityManager._reply_time_use_smooth_curve = config[
            "reply_time_use_smooth_curve"
        ]
        # 概率硬性限制配置
        ProbabilityManager._enable_probability_hard_limit = config[
            "enable_probability_hard_limit"
        ]
        ProbabilityManager._probability_min_limit = config["probability_min_limit"]
        ProbabilityManager._probability_max_limit = config["probability_max_limit"]

        if DEBUG_MODE:
            logger.info("[概率管理器] 已初始化，动态时间调整功能已就绪")

    @staticmethod
    def get_chat_key(platform_name: str, is_private: bool, chat_id: str) -> str:
        """
        获取聊天的唯一标识

        Args:
            platform_name: 平台名称（如aiocqhttp, gewechat等）
            is_private: 是否私聊
            chat_id: 聊天ID（群号或用户ID）

        Returns:
            唯一标识键
        """
        chat_type = "private" if is_private else "group"
        return f"{platform_name}_{chat_type}_{chat_id}"

    @staticmethod
    def _clamp_probability(value: Any, fallback: float, label: str) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            logger.warning(
                f"[概率管理器] {label} 值 '{value}' 无法转换为浮点数，已回退为 {fallback:.2f}"
            )
            return fallback

        if parsed < 0.0 or parsed > 1.0:
            clamped = max(0.0, min(1.0, parsed))
            logger.warning(
                f"[概率管理器] {label} 值 {parsed} 超出范围[0,1]，已矫正为 {clamped:.2f}"
            )
            return clamped

        return parsed

    @staticmethod
    def _normalize_duration(duration: Any, fallback: int, label: str) -> int:
        try:
            parsed = int(duration)
        except (TypeError, ValueError):
            logger.warning(
                f"[概率管理器] {label} 值 '{duration}' 无法转换为整数，已回退为 {fallback} 秒"
            )
            return fallback

        if parsed <= 0:
            logger.warning(
                f"[概率管理器] {label} 值 {parsed} 小于等于 0，已回退为 {fallback} 秒"
            )
            return fallback

        return parsed

    @staticmethod
    def _migrate_legacy_status(status: Dict[str, Any], chat_key: str) -> Dict[str, Any]:
        migrated = copy.deepcopy(status)
        legacy_probability = migrated.get("probability")
        legacy_until = migrated.get("boosted_until")

        if legacy_probability is not None or legacy_until is not None:
            logger.warning(
                f"[概率管理器] 会话 {chat_key} 检测到旧版概率状态结构，已自动迁移为新结构"
            )
            if "base_probability" not in migrated and legacy_probability is not None:
                migrated["base_probability"] = legacy_probability
            if "base_until" not in migrated and legacy_until is not None:
                migrated["base_until"] = legacy_until
            migrated.setdefault("base_source", "legacy_probability_state")
            migrated.pop("probability", None)
            migrated.pop("boosted_until", None)

        return migrated

    @staticmethod
    def _compact_status(status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        compacted = {
            key: value
            for key, value in status.items()
            if value is not None and value != ""
        }
        return compacted or None

    @staticmethod
    async def get_probability_status_snapshot(chat_key: str) -> Dict[str, Any]:
        async with ProbabilityManager._lock:
            status = ProbabilityManager._probability_status.get(chat_key)
            if not status:
                return {}
            migrated = ProbabilityManager._migrate_legacy_status(status, chat_key)
            if migrated != status:
                ProbabilityManager._probability_status[chat_key] = migrated
            return copy.deepcopy(migrated)

    @staticmethod
    async def get_current_probability(
        platform_name: str, is_private: bool, chat_id: str, initial_probability: float
    ) -> float:
        """
        获取当前聊天的读空气概率

        🆕 v1.1.0: 支持动态时间段概率调整
        🆕 v1.1.0: 支持临时概率提升（主动对话后的等待回应状态）
        🆕 v1.1.0: 支持概率硬性限制（一键简化功能）

        优先级顺序（从高到低）：
        1. 临时概率提升（主动对话后）- 叠加到基础概率上
        2. 常规概率提升（回复后）- 完全覆盖基础概率
        3. 动态时间段调整 - 作为系数应用到基础概率
        4. 基础概率（initial_probability）
        5. 概率硬性限制 - 强制限制最终概率范围（最末尾应用）

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            initial_probability: 初始概率（配置值）

        Returns:
            当前概率值（已应用所有调整和限制）
        """
        chat_key = ProbabilityManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        # 生成本次会话的运行时签名
        guard_session(chat_key, probability=0.05)

        # ========== 第一步：获取基础概率（考虑基础覆盖 + 传统回复后提升） ==========
        base_probability = ProbabilityManager._clamp_probability(
            initial_probability, 0.0, f"会话 {chat_key} 的 initial_probability"
        )
        base_source = "initial_probability"

        async with ProbabilityManager._lock:
            status = ProbabilityManager._probability_status.get(chat_key)
            if status:
                migrated = ProbabilityManager._migrate_legacy_status(status, chat_key)
                if migrated != status:
                    ProbabilityManager._probability_status[chat_key] = migrated
                status = migrated

                base_until = status.get("base_until")
                if base_until is not None:
                    try:
                        base_until = float(base_until)
                    except (TypeError, ValueError):
                        logger.warning(
                            f"[概率管理器] 会话 {chat_key} 的基础概率到期时间无效，已清理该状态"
                        )
                        status.pop("base_probability", None)
                        status.pop("base_until", None)
                        status.pop("base_source", None)
                        base_until = None

                if base_until is not None:
                    if base_until < 0:
                        logger.warning(
                            f"[概率管理器] 会话 {chat_key} 的基础概率到期时间为负值，已清理该状态"
                        )
                        status.pop("base_probability", None)
                        status.pop("base_until", None)
                        status.pop("base_source", None)
                    elif current_time < base_until:
                        base_probability = ProbabilityManager._clamp_probability(
                            status.get("base_probability", base_probability),
                            base_probability,
                            f"会话 {chat_key} 的基础概率状态",
                        )
                        base_source = status.get("base_source", "base_probability")
                        if DEBUG_MODE:
                            logger.info(
                                f"会话 {chat_key} 使用基础概率覆盖: {base_probability:.2f} (来源: {base_source})"
                            )
                    else:
                        status.pop("base_probability", None)
                        status.pop("base_until", None)
                        status.pop("base_source", None)
                        if DEBUG_MODE:
                            logger.info(
                                f"会话 {chat_key} 的基础概率覆盖已超时，恢复为初始概率: {base_probability:.2f}"
                            )

                reply_boost_until = status.get("reply_boost_until")
                if reply_boost_until is not None:
                    try:
                        reply_boost_until = float(reply_boost_until)
                    except (TypeError, ValueError):
                        logger.warning(
                            f"[概率管理器] 会话 {chat_key} 的传统回复后提升到期时间无效，已清理该状态"
                        )
                        status.pop("reply_boost_probability", None)
                        status.pop("reply_boost_until", None)
                        status.pop("reply_boost_source", None)
                        reply_boost_until = None

                if reply_boost_until is not None:
                    if reply_boost_until < 0:
                        logger.warning(
                            f"[概率管理器] 会话 {chat_key} 的传统回复后提升到期时间为负值，已清理该状态"
                        )
                        status.pop("reply_boost_probability", None)
                        status.pop("reply_boost_until", None)
                        status.pop("reply_boost_source", None)
                    elif current_time < reply_boost_until:
                        boosted_probability = ProbabilityManager._clamp_probability(
                            status.get("reply_boost_probability", base_probability),
                            base_probability,
                            f"会话 {chat_key} 的传统回复后提升概率",
                        )
                        base_probability = boosted_probability
                        base_source = status.get(
                            "reply_boost_source", "after_reply_probability"
                        )
                        logger.info(
                            f"[传统回复后提升] 会话 {chat_key} 当前使用临时提升概率: {base_probability:.2f}"
                        )
                    else:
                        status.pop("reply_boost_probability", None)
                        status.pop("reply_boost_until", None)
                        status.pop("reply_boost_source", None)
                        logger.info(
                            f"[传统回复后提升] 会话 {chat_key} 的临时提升已过期，恢复到基础概率层"
                        )

                compacted = ProbabilityManager._compact_status(status)
                if compacted is None:
                    del ProbabilityManager._probability_status[chat_key]
                else:
                    ProbabilityManager._probability_status[chat_key] = compacted

        # ========== 第二步：应用动态时间段调整 ==========
        if ProbabilityManager._enable_dynamic_reply_probability:
            try:
                # 动态导入以避免循环依赖
                from .time_period_manager import TimePeriodManager

                # 解析时间段配置（使用静默模式，避免重复输出日志）
                periods_json = ProbabilityManager._reply_time_periods
                periods = TimePeriodManager.parse_time_periods(
                    periods_json, silent=True
                )

                if periods:
                    # 计算时间系数
                    time_factor = TimePeriodManager.calculate_time_factor(
                        current_time=datetime.now(),
                        periods_config=periods,
                        transition_minutes=ProbabilityManager._reply_time_transition_minutes,
                        min_factor=ProbabilityManager._reply_time_min_factor,
                        max_factor=ProbabilityManager._reply_time_max_factor,
                        use_smooth_curve=ProbabilityManager._reply_time_use_smooth_curve,
                    )

                    # 应用时间系数到基础概率
                    original_base = base_probability
                    adjusted_probability = base_probability * time_factor

                    # 确保在0-1范围内
                    adjusted_probability = max(0.0, min(1.0, adjusted_probability))

                    # 保存调整后的概率（用于日志）
                    time_adjusted_probability = adjusted_probability

                    # 更新基础概率
                    base_probability = adjusted_probability

                    if abs(time_factor - 1.0) > 1e-9:
                        logger.info(
                            f"[动态时间调整-普通回复] 会话 {chat_key} "
                            f"原始概率={original_base:.4f}, 时间系数={time_factor:.2f}, "
                            f"调整后概率={time_adjusted_probability:.4f}"
                        )
            except ImportError:
                logger.warning(
                    "[动态时间调整-普通回复] TimePeriodManager未导入，跳过时间调整"
                )
            except Exception as e:
                logger.error(
                    f"[动态时间调整-普通回复] 应用时间调整时发生错误: {e}",
                    exc_info=True,
                )

        # ========== 第三步：叠加临时概率提升（主动对话后） ==========
        try:
            # 动态导入以避免循环依赖
            from .proactive_chat_manager import ProactiveChatManager

            temp_boost = ProactiveChatManager.get_temp_probability_boost(chat_key)

            if temp_boost > 0:
                # 临时提升：叠加到基础概率上
                original_prob = base_probability
                final_probability = base_probability + temp_boost
                # 确保不超过1.0
                final_probability = min(final_probability, 1.0)
                # 确保不小于0.0（虽然理论上不会小于0）
                final_probability = max(0.0, final_probability)

                if DEBUG_MODE:
                    logger.info(
                        f"[临时概率提升] 会话 {chat_key} "
                        f"基础概率={original_prob:.2f}, 临时提升={temp_boost:.2f}, "
                        f"最终概率={final_probability:.2f}"
                    )

                # 注意：临时提升返回的概率会跳过硬性限制，但已经确保在0-1范围内
                # 如果需要应用硬性限制，需要在这里也检查
                if ProbabilityManager._enable_probability_hard_limit:
                    min_limit = ProbabilityManager._probability_min_limit
                    max_limit = ProbabilityManager._probability_max_limit
                    original_final = final_probability
                    final_probability = max(
                        min_limit, min(max_limit, final_probability)
                    )
                    if abs(original_final - final_probability) > 1e-9:
                        logger.info(
                            f"[临时概率提升+硬性限制] 会话 {chat_key} "
                            f"应用硬性限制: {original_final:.2f} → {final_probability:.2f}"
                        )

                return final_probability
        except ImportError:
            # 如果 ProactiveChatManager 未导入，忽略临时提升
            pass
        except Exception as e:
            logger.error(f"[临时概率提升] 检查临时提升时发生错误: {e}", exc_info=True)

        # ========== 第四步：应用概率硬性限制（一键简化功能） ==========
        if ProbabilityManager._enable_probability_hard_limit:
            min_limit = ProbabilityManager._probability_min_limit
            max_limit = ProbabilityManager._probability_max_limit

            original_prob = base_probability
            # 强制限制在范围内
            base_probability = max(min_limit, min(max_limit, base_probability))

            # 使用更精确的比较（考虑浮点数精度问题）
            # 如果原始概率小于最小值或被限制，记录日志
            if original_prob < min_limit or original_prob > max_limit:
                logger.info(
                    f"[概率硬性限制] 会话 {chat_key} "
                    f"原始概率={original_prob:.4f}, 限制范围=[{min_limit:.2f}, {max_limit:.2f}], "
                    f"最终概率={base_probability:.4f}"
                )
            elif abs(original_prob - base_probability) > 0.001:
                logger.info(
                    f"[概率硬性限制] 会话 {chat_key} "
                    f"原始概率={original_prob:.4f}, 限制范围=[{min_limit:.2f}, {max_limit:.2f}], "
                    f"最终概率={base_probability:.4f}"
                )

        # ========== 最后一步：统一安全限制（确保所有路径都返回0-1范围内的值） ==========
        # 无论前面的计算如何，最终概率必须在0.0-1.0范围内
        base_probability = max(0.0, min(1.0, base_probability))

        # ========== 返回最终概率 ==========
        return base_probability

    @staticmethod
    async def boost_probability(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        boosted_probability: float,
        duration: int,
    ) -> None:
        """
        临时提升读空气概率

        AI回复后调用，提升概率促进连续对话

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            boosted_probability: 提升后的概率
            duration: 持续时间（秒）
        """
        chat_key = ProbabilityManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()
        safe_probability = ProbabilityManager._clamp_probability(
            boosted_probability,
            0.8,
            f"会话 {chat_key} 的传统回复后提升概率",
        )
        safe_duration = ProbabilityManager._normalize_duration(
            duration,
            120,
            f"会话 {chat_key} 的传统回复后提升持续时间",
        )
        boosted_until = current_time + safe_duration

        async with ProbabilityManager._lock:
            status = ProbabilityManager._probability_status.get(chat_key, {})
            status = ProbabilityManager._migrate_legacy_status(status, chat_key)
            status["reply_boost_probability"] = safe_probability
            status["reply_boost_until"] = boosted_until
            status["reply_boost_source"] = "after_reply_probability"
            ProbabilityManager._probability_status[chat_key] = status

        logger.info(
            f"[传统回复后提升] 会话 {chat_key} 已启用临时提升: {safe_probability:.2f}, "
            f"持续 {safe_duration} 秒 (至 {time.strftime('%H:%M:%S', time.localtime(boosted_until))})"
        )

    @staticmethod
    async def reset_probability(
        platform_name: str, is_private: bool, chat_id: str
    ) -> None:
        """
        重置概率状态

        立即清除提升状态，恢复初始概率

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
        """
        chat_key = ProbabilityManager.get_chat_key(platform_name, is_private, chat_id)

        async with ProbabilityManager._lock:
            if chat_key in ProbabilityManager._probability_status:
                del ProbabilityManager._probability_status[chat_key]
                logger.info(f"会话 {chat_key} 概率状态已重置")

    @staticmethod
    async def set_base_probability(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        new_probability: float,
        duration: int = 600,
    ) -> None:
        """
        设置基础概率（用于频率动态调整）

        与 boost_probability 类似，但用于频率调整器修改基础概率
        这个概率会持续较长时间（默认10分钟），直到下次频率检查

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            new_probability: 新的基础概率
            duration: 持续时间（秒），默认600秒（10分钟）
        """
        chat_key = ProbabilityManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()
        safe_probability = ProbabilityManager._clamp_probability(
            new_probability,
            0.0,
            f"会话 {chat_key} 的基础概率覆盖值",
        )
        safe_duration = ProbabilityManager._normalize_duration(
            duration,
            600,
            f"会话 {chat_key} 的基础概率覆盖持续时间",
        )
        boosted_until = current_time + safe_duration

        async with ProbabilityManager._lock:
            status = ProbabilityManager._probability_status.get(chat_key, {})
            status = ProbabilityManager._migrate_legacy_status(status, chat_key)
            status["base_probability"] = safe_probability
            status["base_until"] = boosted_until
            status["base_source"] = "frequency_adjuster"
            ProbabilityManager._probability_status[chat_key] = status

        logger.info(
            f"[频率调整] 会话 {chat_key} 基础概率已调整为 {safe_probability:.2f}, "
            f"持续 {safe_duration} 秒"
        )
