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
版本: v1.1.2
"""

import time
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from astrbot.api.all import *

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False

# 导入需要使用的其他模块
# 使用 TYPE_CHECKING 避免循环导入
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .time_period_manager import TimePeriodManager
    from .proactive_chat_manager import ProactiveChatManager


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
    # 格式: {chat_key: {"probability": float, "boosted_until": timestamp}}
    _probability_status: Dict[str, Dict[str, Any]] = {}
    _lock = asyncio.Lock()  # 异步锁

    # 🆕 v1.1.0: 插件配置引用（用于动态时间调整）
    _plugin_config: Optional[dict] = None

    @staticmethod
    def initialize(config: dict):
        """
        🆕 v1.1.0: 初始化概率管理器

        Args:
            config: 插件配置字典
        """
        ProbabilityManager._plugin_config = config
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

        # ========== 第一步：获取基础概率（考虑常规提升） ==========
        base_probability = initial_probability

        async with ProbabilityManager._lock:
            if chat_key in ProbabilityManager._probability_status:
                status = ProbabilityManager._probability_status[chat_key]
                boosted_until = status.get("boosted_until", 0)

                # 检查是否还在提升期内
                if current_time < boosted_until:
                    base_probability = status.get("probability", initial_probability)
                    if DEBUG_MODE:
                        logger.info(
                            f"会话 {chat_key} 使用常规提升概率: {base_probability:.2f}"
                        )
                else:
                    # 超时了，清理记录
                    del ProbabilityManager._probability_status[chat_key]
                    if DEBUG_MODE:
                        logger.info(
                            f"会话 {chat_key} 概率提升已超时，恢复为初始概率: {initial_probability:.2f}"
                        )

        # ========== 第二步：应用动态时间段调整 ==========
        if ProbabilityManager._plugin_config and ProbabilityManager._plugin_config.get(
            "enable_dynamic_reply_probability", False
        ):
            try:
                # 动态导入以避免循环依赖
                from .time_period_manager import TimePeriodManager

                # 解析时间段配置（使用静默模式，避免重复输出日志）
                periods_json = ProbabilityManager._plugin_config.get(
                    "reply_time_periods", "[]"
                )
                periods = TimePeriodManager.parse_time_periods(
                    periods_json, silent=True
                )

                if periods:
                    # 计算时间系数
                    time_factor = TimePeriodManager.calculate_time_factor(
                        current_time=datetime.now(),
                        periods_config=periods,
                        transition_minutes=ProbabilityManager._plugin_config.get(
                            "reply_time_transition_minutes", 30
                        ),
                        min_factor=ProbabilityManager._plugin_config.get(
                            "reply_time_min_factor", 0.1
                        ),
                        max_factor=ProbabilityManager._plugin_config.get(
                            "reply_time_max_factor", 2.0
                        ),
                        use_smooth_curve=ProbabilityManager._plugin_config.get(
                            "reply_time_use_smooth_curve", True
                        ),
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

                    if time_factor != 1.0:
                        if DEBUG_MODE:
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
                if (
                    ProbabilityManager._plugin_config
                    and ProbabilityManager._plugin_config.get(
                        "enable_probability_hard_limit", False
                    )
                ):
                    min_limit = ProbabilityManager._plugin_config.get(
                        "probability_min_limit", 0.05
                    )
                    max_limit = ProbabilityManager._plugin_config.get(
                        "probability_max_limit", 0.8
                    )
                    original_final = final_probability
                    final_probability = max(
                        min_limit, min(max_limit, final_probability)
                    )
                    if original_final != final_probability:
                        if DEBUG_MODE:
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
        if ProbabilityManager._plugin_config and ProbabilityManager._plugin_config.get(
            "enable_probability_hard_limit", False
        ):
            min_limit = ProbabilityManager._plugin_config.get(
                "probability_min_limit", 0.05
            )
            max_limit = ProbabilityManager._plugin_config.get(
                "probability_max_limit", 0.8
            )

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
        boosted_until = current_time + duration

        async with ProbabilityManager._lock:
            ProbabilityManager._probability_status[chat_key] = {
                "probability": boosted_probability,
                "boosted_until": boosted_until,
            }

        logger.info(
            f"会话 {chat_key} 概率已提升至 {boosted_probability}, "
            f"持续 {duration} 秒 (至 {time.strftime('%H:%M:%S', time.localtime(boosted_until))})"
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
        boosted_until = current_time + duration

        async with ProbabilityManager._lock:
            ProbabilityManager._probability_status[chat_key] = {
                "probability": new_probability,
                "boosted_until": boosted_until,
            }

        logger.info(
            f"[频率调整] 会话 {chat_key} 基础概率已调整为 {new_probability:.2f}, "
            f"持续 {duration} 秒"
        )
