"""
回复密度管理器模块
滑动窗口追踪Bot在每个群的回复密度，实现智能回复频率控制

核心功能：
1. 滑动窗口追踪 - 记录每个群最近N分钟内的Bot回复时间戳
2. 渐进式概率衰减 - 接近上限时逐步降低概率，而非硬性截断
3. 密度信息输出 - 为Decision AI提供回复密度上下文

作者: Him666233
版本: v1.2.1
"""

import time
import asyncio
from typing import Dict, List, Any, Optional
from astrbot.api.all import logger

# 详细日志开关
DEBUG_MODE: bool = False


class ReplyDensityManager:
    """
    回复密度管理器

    使用滑动窗口追踪每个会话的Bot回复频率，
    提供渐进式概率衰减和硬性上限拦截。
    """

    # 每个会话的回复时间戳列表
    # 格式: {chat_key: [timestamp1, timestamp2, ...]}
    _reply_timestamps: Dict[str, List[float]] = {}
    _lock = asyncio.Lock()

    # 配置（由 main.py 初始化）
    _enabled: bool = False
    _window_seconds: int = 300
    _max_replies: int = 5
    _soft_limit_ratio: float = 0.6
    _ai_hint_enabled: bool = True

    @classmethod
    def initialize(cls, config: dict) -> None:
        """初始化，配置由 main.py 统一提取后传入"""
        cls._enabled = config["enable_reply_density_limit"]
        cls._window_seconds = config["reply_density_window_seconds"]
        cls._max_replies = config["reply_density_max_replies"]
        cls._soft_limit_ratio = config["reply_density_soft_limit_ratio"]
        cls._ai_hint_enabled = config["reply_density_ai_hint"]

        if DEBUG_MODE:
            logger.info(
                f"[回复密度] 已初始化: 窗口={cls._window_seconds}秒, "
                f"上限={cls._max_replies}次, 软限比={cls._soft_limit_ratio}"
            )

    @classmethod
    async def record_reply(cls, chat_key: str) -> None:
        """记录一次Bot回复"""
        async with cls._lock:
            if chat_key not in cls._reply_timestamps:
                cls._reply_timestamps[chat_key] = []
            cls._reply_timestamps[chat_key].append(time.time())
            # 清理过期记录
            cls._cleanup_expired(chat_key)

    @classmethod
    def _cleanup_expired(cls, chat_key: str) -> None:
        """清理窗口外的过期记录（需在锁内调用）"""
        if chat_key not in cls._reply_timestamps:
            return
        cutoff = time.time() - cls._window_seconds
        cls._reply_timestamps[chat_key] = [
            t for t in cls._reply_timestamps[chat_key] if t > cutoff
        ]

    @classmethod
    async def get_reply_count(cls, chat_key: str) -> int:
        """获取当前窗口内的回复次数"""
        async with cls._lock:
            cls._cleanup_expired(chat_key)
            return len(cls._reply_timestamps.get(chat_key, []))

    @classmethod
    async def should_block(cls, chat_key: str) -> bool:
        """检查是否应该硬性拦截（达到上限）"""
        if not cls._enabled:
            return False
        count = await cls.get_reply_count(chat_key)
        return count >= cls._max_replies

    @classmethod
    async def get_probability_factor(cls, chat_key: str) -> float:
        """
        获取密度概率衰减因子（0.0 ~ 1.0）

        渐进式衰减：
        - 回复数 < 软限 → 1.0（无衰减）
        - 软限 <= 回复数 < 硬限 → 线性衰减到 0.1
        - 回复数 >= 硬限 → 0.0（完全拦截）
        """
        if not cls._enabled:
            return 1.0

        count = await cls.get_reply_count(chat_key)
        max_replies = cls._max_replies
        soft_limit = int(max_replies * cls._soft_limit_ratio)

        if count < soft_limit:
            return 1.0
        if count >= max_replies:
            return 0.0

        # 线性衰减：从1.0衰减到0.1
        range_size = max_replies - soft_limit
        if range_size <= 0:
            return 0.0
        progress = (count - soft_limit) / range_size
        return max(0.1, 1.0 - progress * 0.9)

    @classmethod
    async def get_density_info(cls, chat_key: str) -> Dict[str, Any]:
        """获取密度信息（用于注入Decision AI）"""
        count = await cls.get_reply_count(chat_key)
        window_min = cls._window_seconds // 60

        return {
            "enabled": cls._enabled,
            "reply_count": count,
            "max_replies": cls._max_replies,
            "window_minutes": window_min,
            "density_ratio": count / max(1, cls._max_replies),
        }

    @classmethod
    async def get_ai_hint_text(cls, chat_key: str) -> str:
        """生成Decision AI的密度提示文本"""
        if not cls._enabled or not cls._ai_hint_enabled:
            return ""

        info = await cls.get_density_info(chat_key)
        count = info["reply_count"]
        max_r = info["max_replies"]
        window_min = info["window_minutes"]
        ratio = info["density_ratio"]

        if ratio >= 0.8:
            suggestion = (
                "你最近回复非常频繁，除非消息非常重要或直接问你，否则应该保持沉默。"
            )
        elif ratio >= 0.5:
            suggestion = "你最近回复较多，适当减少回复频率，只回复重要或有趣的消息。"
        elif count == 0:
            suggestion = "你最近没有发言，如果有值得参与的话题可以适当回复。"
        else:
            suggestion = "你的回复频率正常。"

        return (
            f"\n\n[系统信息-回复密度]\n"
            f"最近{window_min}分钟内你已回复{count}次（上限{max_r}次）\n"
            f"建议: {suggestion}\n"
        )

    @classmethod
    async def clear_session(cls, chat_key: str) -> None:
        """清除指定会话的密度数据"""
        async with cls._lock:
            if chat_key in cls._reply_timestamps:
                del cls._reply_timestamps[chat_key]
