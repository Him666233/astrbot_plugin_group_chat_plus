"""
注意力机制管理器模块
负责管理AI对特定用户的注意力，实现更精确的对话焦点

核心功能：
1. 记录AI最后回复的目标用户
2. 根据下一条消息的发送者调整读空气概率
3. 提升对刚对话用户的关注度，降低对其他用户的响应

作者: Him666233
版本: v1.0.1
"""

import time
import asyncio
from typing import Dict, Any, Optional
from astrbot.api.all import *


class AttentionManager:
    """
    注意力机制管理器

    主要功能：
    1. 记录AI回复的目标用户信息（ID和名字）
    2. 在概率判断前，根据当前消息发送者调整概率
    3. 同一用户继续对话时提升概率，不同用户时降低概率
    4. 支持时间窗口，超时后不再应用注意力调整
    """

    # 存储每个会话最后回复的目标用户信息
    # 格式: {chat_key: {"user_id": str, "user_name": str, "replied_at": timestamp}}
    _attention_status: Dict[str, Dict[str, Any]] = {}
    _lock = asyncio.Lock()  # 异步锁

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
    async def record_replied_user(
        platform_name: str, is_private: bool, chat_id: str, user_id: str, user_name: str
    ) -> None:
        """
        记录AI回复的目标用户

        在AI发送回复后调用，记录被回复的用户信息

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            user_id: 被回复的用户ID
            user_name: 被回复的用户名字
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        async with AttentionManager._lock:
            AttentionManager._attention_status[chat_key] = {
                "user_id": user_id,
                "user_name": user_name,
                "replied_at": current_time,
            }

        logger.info(
            f"[注意力机制] 会话 {chat_key} - 已记录回复目标: {user_name}(ID: {user_id})"
        )

    @staticmethod
    async def get_adjusted_probability(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        current_user_id: str,
        current_user_name: str,
        current_probability: float,
        attention_increased_probability: float,
        attention_decreased_probability: float,
        attention_duration: int,
        enabled: bool,
    ) -> float:
        """
        根据注意力机制调整概率

        检查当前消息发送者是否是上次回复的目标用户：
        - 如果是同一用户，提升概率（增强注意力）
        - 如果是不同用户，降低概率（分散注意力）
        - 超过时间窗口则不调整

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            current_user_id: 当前消息发送者ID
            current_user_name: 当前消息发送者名字
            current_probability: 当前概率（未调整前）
            attention_increased_probability: 同一用户时提升到的概率
            attention_decreased_probability: 不同用户时降低到的概率
            attention_duration: 注意力持续时间（秒）
            enabled: 是否启用注意力机制

        Returns:
            调整后的概率值
        """
        # 如果未启用注意力机制，直接返回原概率
        if not enabled:
            return current_probability

        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        async with AttentionManager._lock:
            # 如果该聊天没有记录，返回原概率
            if chat_key not in AttentionManager._attention_status:
                logger.debug(f"[注意力机制] 会话 {chat_key} - 无历史记录，使用原概率")
                return current_probability

            status = AttentionManager._attention_status[chat_key]
            replied_at = status.get("replied_at", 0)
            replied_user_id = status.get("user_id", "")
            replied_user_name = status.get("user_name", "")

            # 检查是否在注意力时间窗口内
            time_elapsed = current_time - replied_at
            if time_elapsed > attention_duration:
                # 超时了，清理记录并返回原概率
                del AttentionManager._attention_status[chat_key]
                logger.debug(
                    f"[注意力机制] 会话 {chat_key} - 注意力已超时({time_elapsed:.1f}秒)，使用原概率"
                )
                return current_probability

            # 在时间窗口内，检查是否是同一用户
            is_same_user = current_user_id == replied_user_id

            if is_same_user:
                # 同一用户，使用提升概率（直接替换，因为这是针对性的高关注）
                adjusted_probability = attention_increased_probability
                logger.info(
                    f"[注意力机制] 🎯 会话 {chat_key} - 检测到同一用户继续对话 "
                    f"{current_user_name}(ID: {current_user_id}), "
                    f"概率 {current_probability:.2f} → {adjusted_probability:.2f} "
                    f"(已持续 {time_elapsed:.1f}秒)"
                )
                return adjusted_probability
            else:
                # 不同用户，使用降低概率（直接替换，因为要降低对非目标用户的关注）
                adjusted_probability = attention_decreased_probability
                logger.info(
                    f"[注意力机制] 👥 会话 {chat_key} - 检测到不同用户发言 "
                    f"当前: {current_user_name}(ID: {current_user_id}) vs "
                    f"上次回复: {replied_user_name}(ID: {replied_user_id}), "
                    f"概率 {current_probability:.2f} → {adjusted_probability:.2f} "
                    f"(已持续 {time_elapsed:.1f}秒)"
                )
                return adjusted_probability

    @staticmethod
    async def clear_attention(
        platform_name: str, is_private: bool, chat_id: str
    ) -> None:
        """
        清除注意力状态

        立即清除注意力记录

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)

        async with AttentionManager._lock:
            if chat_key in AttentionManager._attention_status:
                del AttentionManager._attention_status[chat_key]
                logger.debug(f"[注意力机制] 会话 {chat_key} 注意力状态已清除")

    @staticmethod
    async def get_attention_info(
        platform_name: str, is_private: bool, chat_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取当前注意力信息（用于调试）

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID

        Returns:
            注意力信息字典，如果没有记录则返回None
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)

        async with AttentionManager._lock:
            if chat_key in AttentionManager._attention_status:
                return AttentionManager._attention_status[chat_key].copy()
            return None
