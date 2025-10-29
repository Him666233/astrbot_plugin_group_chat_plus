"""
概率管理器模块
负责管理和动态调整读空气概率

作者: Him666233
版本: v1.0.1
"""

import time
import asyncio
from typing import Dict, Any
from astrbot.api.all import *


class ProbabilityManager:
    """
    概率管理器

    主要功能：
    1. 管理每个会话的读空气概率
    2. AI回复后临时提升概率
    3. 超时后自动恢复初始概率
    """

    # 使用字典保存每个聊天的概率状态
    # 格式: {chat_key: {"probability": float, "boosted_until": timestamp}}
    _probability_status: Dict[str, Dict[str, Any]] = {}
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
    async def get_current_probability(
        platform_name: str, is_private: bool, chat_id: str, initial_probability: float
    ) -> float:
        """
        获取当前聊天的读空气概率

        提升期内返回提升后的概率，否则返回初始概率

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            initial_probability: 初始概率（配置值）

        Returns:
            当前概率值
        """
        chat_key = ProbabilityManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        async with ProbabilityManager._lock:
            # 如果该聊天没有记录,返回初始概率
            if chat_key not in ProbabilityManager._probability_status:
                return initial_probability

            status = ProbabilityManager._probability_status[chat_key]
            boosted_until = status.get("boosted_until", 0)

            # 检查是否还在提升期内
            if current_time < boosted_until:
                probability = status.get("probability", initial_probability)
                logger.debug(f"会话 {chat_key} 当前使用提升后的概率: {probability}")
                return probability
            else:
                # 超时了,返回初始概率并清理记录
                if chat_key in ProbabilityManager._probability_status:
                    del ProbabilityManager._probability_status[chat_key]
                logger.debug(
                    f"会话 {chat_key} 概率提升已超时,恢复为初始概率: {initial_probability}"
                )
                return initial_probability

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
                logger.debug(f"会话 {chat_key} 概率状态已重置")
