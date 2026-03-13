"""
情绪追踪系统 - 为AI添加动态情绪状态
让AI的回复更有情感变化，更像真人

核心理念：
- 情绪随对话内容动态变化
- 在prompt中注入当前情绪状态
- 情绪会随时间自动衰减回归平静
- v1.0.6更新：支持否定词检测，避免"不难过"被误判为"难过"

作者: Him666233
版本: v1.2.1
参考: MaiBot mood_manager.py (简化实现)
"""

import time
import json
import os
from typing import Optional, Dict, List, Any
from astrbot.api.all import logger

DEBUG_MODE: bool = False


class MoodTracker:
    """
    简化版情绪追踪器

    核心功能：
    - 维护每个群聊的情绪状态
    - 根据关键词和上下文更新情绪
    - 情绪自动衰减回归平静
    - 支持否定词检测，避免误判（v1.0.6新增）
    """

    # 默认情绪
    DEFAULT_MOOD = "平静"

    def _get_default_mood_keywords(self) -> Dict[str, List[str]]:
        """
        获取默认的情绪关键词配置

        Returns:
            默认的情绪关键词字典
        """
        return {
            "开心": [
                "哈哈",
                "笑",
                "😂",
                "😄",
                "👍",
                "棒",
                "赞",
                "好评",
                "厉害",
                "nb",
                "牛",
                "开心",
                "高兴",
                "快乐",
            ],
            "难过": ["难过", "伤心", "哭", "😢", "😭", "呜呜", "555", "心疼", "悲伤"],
            "生气": ["生气", "气", "烦", "😡", "😠", "恼火", "讨厌", "愤怒"],
            "惊讶": ["哇", "天哪", "😮", "😲", "震惊", "卧槽", "我去", "惊讶"],
            "疑惑": ["？", "疑惑", "🤔", "为什么", "怎么", "什么", "不懂"],
            "无语": ["无语", "😑", "...", "省略号", "服了", "醉了", "无言"],
            "兴奋": ["！！", "激动", "😆", "🎉", "太好了", "yes", "耶", "兴奋"],
        }

    def _get_hardcoded_defaults(self) -> dict:
        """
        获取硬编码的默认配置值

        说明：为避免 AstrBot 平台多次读取配置可能导致的问题，
        所有配置参数应由 main.py 一次性提取后传入。
        此方法仅作为最后的兜底，当配置字典中缺少某些键时使用。

        Returns:
            包含默认值的字典
        """
        return {
            "mood_decay_time": 300,
            "mood_cleanup_threshold": 3600,
            "mood_cleanup_interval": 600,
            "enable_negation_detection": True,
            "negation_words": [
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
            "negation_check_range": 5,
            "mood_keywords": "",
        }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化情绪追踪器

        Args:
            config: 插件配置字典，包含否定词列表、情绪关键词等配置
        """
        # 存储每个群聊的情绪状态
        # 格式: {chat_id: {"mood": "情绪", "intensity": 强度, "last_update": 时间戳}}
        self.moods: Dict[str, Dict] = {}

        # 从配置读取参数，如果没有配置则使用默认值
        # 说明：配置应由 main.py 一次性提取后传入，此处仅作兜底
        if config is None:
            config = {}

        # 说明：配置由 main.py 统一提取后传入，此处直接使用传入的值，
        # 不再提供默认值（避免 AstrBot 平台多次读取配置的问题）

        # 情绪衰减时间（秒）
        self.mood_decay_time: int = config["mood_decay_time"]

        # 清理相关配置（防止内存泄漏）
        self._cleanup_threshold: int = config["mood_cleanup_threshold"]
        self._cleanup_interval: int = config["mood_cleanup_interval"]
        self._last_cleanup_time: float = time.time()

        # 是否启用否定词检测
        self.enable_negation: bool = config["enable_negation_detection"]

        # 否定词列表
        self.negation_words: List[str] = config["negation_words"]

        # 否定词检查范围（关键词前N个字符）
        self.negation_check_range: int = config["negation_check_range"]

        # 情绪关键词 - 支持字符串(JSON)或字典格式
        mood_keywords_raw = config["mood_keywords"]

        # 如果是字符串格式，尝试解析为JSON
        if isinstance(mood_keywords_raw, str):
            if mood_keywords_raw.strip():  # 非空字符串，尝试解析
                try:
                    self.mood_keywords: Dict[str, List[str]] = json.loads(
                        mood_keywords_raw
                    )
                    if DEBUG_MODE:
                        logger.info(
                            f"[情绪追踪] 已加载情绪关键词配置，共 {len(self.mood_keywords)} 种情绪类型"
                        )
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"[情绪追踪] mood_keywords JSON解析失败: {e}，使用硬编码默认配置"
                    )
                    self.mood_keywords = self._get_default_mood_keywords()
            else:  # 空字符串，使用硬编码默认配置
                if DEBUG_MODE:
                    logger.info(f"[情绪追踪] mood_keywords 为空，使用硬编码默认配置")
                self.mood_keywords = self._get_default_mood_keywords()
        elif isinstance(mood_keywords_raw, dict):  # 字典格式（向后兼容旧版本配置）
            self.mood_keywords = mood_keywords_raw
            if DEBUG_MODE:
                logger.info(
                    f"[情绪追踪] 已从字典格式加载情绪关键词，共 {len(self.mood_keywords)} 种情绪类型"
                )
        else:
            logger.warning(
                f"[情绪追踪] mood_keywords 配置格式错误(类型: {type(mood_keywords_raw).__name__})，使用硬编码默认配置"
            )
            self.mood_keywords = self._get_default_mood_keywords()

        if DEBUG_MODE:
            logger.info(
                f"[情绪追踪系统] 已初始化 | "
                f"衰减时间: {self.mood_decay_time}秒 | "
                f"否定词检测: {'启用' if self.enable_negation else '禁用'} | "
                f"否定词数量: {len(self.negation_words)} | "
                f"情绪类型: {len(self.mood_keywords)} | "
                f"清理阈值: {self._cleanup_threshold}秒 | "
                f"清理间隔: {self._cleanup_interval}秒"
            )

    def _has_negation_before(self, text: str, keyword_pos: int) -> bool:
        """
        检查关键词前是否有否定词

        Args:
            text: 完整文本
            keyword_pos: 关键词在文本中的位置

        Returns:
            如果检测到否定词返回True
        """
        # 提取关键词前的上下文
        start_pos = max(0, keyword_pos - self.negation_check_range)
        context_before = text[start_pos:keyword_pos]

        # 检查是否包含否定词
        for neg_word in self.negation_words:
            if neg_word in context_before:
                return True

        return False

    def _detect_mood_from_text(self, text: str) -> Optional[str]:
        """
        从文本中检测情绪（v1.0.6增强：支持否定词检测）

        Args:
            text: 要分析的文本

        Returns:
            检测到的情绪，如果没有明显情绪则返回None
        """
        if not text:
            return None

        # 统计各种情绪的关键词出现次数
        mood_scores = {}

        for mood, keywords in self.mood_keywords.items():
            score = 0

            for keyword in keywords:
                # 查找所有该关键词的出现位置
                start = 0
                while True:
                    pos = text.find(keyword, start)
                    if pos == -1:
                        break

                    # 如果启用了否定词检测，检查前面是否有否定词
                    if self.enable_negation and self._has_negation_before(text, pos):
                        # 检测到否定词，跳过这个关键词
                        if DEBUG_MODE:
                            logger.info(
                                f"[情绪检测] 检测到否定词，忽略关键词 '{keyword}' "
                                f"(位置: {pos}, 前文: '{text[max(0, pos - self.negation_check_range) : pos]}')"
                            )
                    else:
                        # 没有否定词，正常计分
                        score += 1

                    start = pos + 1

            if score > 0:
                mood_scores[mood] = score

        if not mood_scores:
            return None

        # 返回得分最高的情绪
        detected_mood = max(mood_scores, key=mood_scores.get)
        logger.info(
            f"[情绪检测] 文本: '{text[:50]}...' | 检测结果: {detected_mood} | 得分: {mood_scores}"
        )

        return detected_mood

    def update_mood_from_context(self, chat_id: str, recent_messages: str) -> str:
        """
        根据最近的对话内容更新情绪

        Args:
            chat_id: 群聊ID
            recent_messages: 最近的消息上下文

        Returns:
            更新后的情绪状态
        """
        # 定期清理长期不活跃的群组（防止内存泄漏）
        self._cleanup_inactive_chats()

        # 检测情绪
        detected_mood = self._detect_mood_from_text(recent_messages)

        current_time = time.time()

        if chat_id not in self.moods:
            # 初始化情绪状态
            self.moods[chat_id] = {
                "mood": detected_mood or self.DEFAULT_MOOD,
                "intensity": 0.5 if detected_mood else 0.0,
                "last_update": current_time,
            }
        else:
            # 检查是否需要衰减
            time_since_update = current_time - self.moods[chat_id]["last_update"]

            if time_since_update > self.mood_decay_time:
                # 情绪衰减，逐渐回归平静
                self.moods[chat_id]["mood"] = self.DEFAULT_MOOD
                self.moods[chat_id]["intensity"] = max(
                    0.0, self.moods[chat_id]["intensity"] - 0.2
                )
                logger.info(f"[情绪追踪] {chat_id} 情绪衰减到: {self.DEFAULT_MOOD}")

            # 如果检测到新情绪，更新
            if detected_mood:
                old_mood = self.moods[chat_id]["mood"]
                self.moods[chat_id]["mood"] = detected_mood
                self.moods[chat_id]["intensity"] = min(
                    1.0, self.moods[chat_id]["intensity"] + 0.3
                )
                self.moods[chat_id]["last_update"] = current_time

                if old_mood != detected_mood:
                    logger.info(
                        f"[情绪追踪] {chat_id} 情绪变化: {old_mood} → {detected_mood}"
                    )

        return self.moods[chat_id]["mood"]

    def get_current_mood(self, chat_id: str) -> str:
        """
        获取当前情绪状态

        Args:
            chat_id: 群聊ID

        Returns:
            当前情绪
        """
        # 定期清理长期不活跃的群组（防止内存泄漏）
        self._cleanup_inactive_chats()

        if chat_id not in self.moods:
            return self.DEFAULT_MOOD

        # 检查是否需要衰减
        current_time = time.time()
        time_since_update = current_time - self.moods[chat_id]["last_update"]

        if time_since_update > self.mood_decay_time:
            self.moods[chat_id]["mood"] = self.DEFAULT_MOOD
            self.moods[chat_id]["intensity"] = 0.0

        return self.moods[chat_id]["mood"]

    def inject_mood_to_prompt(
        self, chat_id: str, original_prompt: str, recent_context: str = ""
    ) -> str:
        """
        将情绪状态注入到prompt中

        Args:
            chat_id: 群聊ID
            original_prompt: 原始prompt
            recent_context: 最近的对话上下文（用于更新情绪）

        Returns:
            注入情绪后的prompt
        """
        # 如果有上下文，先更新情绪
        if recent_context:
            self.update_mood_from_context(chat_id, recent_context)

        current_mood = self.get_current_mood(chat_id)

        # 只有非平静状态才注入情绪
        if current_mood == self.DEFAULT_MOOD:
            return original_prompt

        # 在prompt开头注入情绪提示
        mood_hint = f"[当前情绪状态: 你感到{current_mood}]\n"

        # 如果原prompt已经包含情绪相关内容，不重复添加
        if "情绪" in original_prompt or "心情" in original_prompt:
            return original_prompt

        logger.info(f"[情绪追踪] {chat_id} 注入情绪: {current_mood}")

        return mood_hint + original_prompt

    def reset_mood(self, chat_id: str):
        """
        重置指定群聊的情绪状态

        Args:
            chat_id: 群聊ID
        """
        if chat_id in self.moods:
            self.moods[chat_id] = {
                "mood": self.DEFAULT_MOOD,
                "intensity": 0.0,
                "last_update": time.time(),
            }

            logger.info(f"[情绪追踪] {chat_id} 情绪已重置")

    def get_mood_description(self, chat_id: str) -> str:
        """
        获取情绪的详细描述

        Args:
            chat_id: 群聊ID

        Returns:
            情绪描述文本
        """
        if chat_id not in self.moods:
            return f"情绪: {self.DEFAULT_MOOD}"

        mood_data = self.moods[chat_id]
        intensity_desc = (
            "轻微"
            if mood_data["intensity"] < 0.4
            else "中等"
            if mood_data["intensity"] < 0.7
            else "强烈"
        )

        return f"情绪: {mood_data['mood']} ({intensity_desc})"

    def _cleanup_inactive_chats(self) -> None:
        """
        清理长期不活跃的群组情绪记录（防止内存泄漏）

        当群组超过 _cleanup_threshold 时间未更新时，移除其记录。
        为了避免频繁检查，只在距离上次清理超过 _cleanup_interval 时才执行。

        如果 _cleanup_threshold 设置为0，则禁用自动清理。
        """
        # 如果清理阈值设置为0，则禁用自动清理
        if self._cleanup_threshold <= 0:
            return

        current_time = time.time()

        # 检查是否需要执行清理
        if current_time - self._last_cleanup_time < self._cleanup_interval:
            return

        # 找出需要清理的群组
        inactive_chats = []
        for chat_id, mood_data in self.moods.items():
            last_update = mood_data.get("last_update", 0)
            if current_time - last_update > self._cleanup_threshold:
                inactive_chats.append(chat_id)

        # 执行清理
        if inactive_chats:
            for chat_id in inactive_chats:
                del self.moods[chat_id]

            if DEBUG_MODE:
                logger.info(
                    f"[情绪追踪-内存清理] 已清理 {len(inactive_chats)} 个不活跃群组的情绪记录 "
                    f"(超过 {self._cleanup_threshold / 3600:.1f} 小时未活跃)"
                )

        # 更新上次清理时间
        self._last_cleanup_time = current_time
