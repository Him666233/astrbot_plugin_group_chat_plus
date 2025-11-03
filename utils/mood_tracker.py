"""
情绪追踪系统 - 为AI添加动态情绪状态
让AI的回复更有情感变化，更像真人

核心理念：
- 情绪随对话内容动态变化
- 在prompt中注入当前情绪状态
- 情绪会随时间自动衰减回归平静

作者: Him666233
版本: v1.0.5
参考: MaiBot mood_manager.py (简化实现)
"""

import time
from typing import Optional, Dict
from astrbot.api.all import logger


class MoodTracker:
    """
    简化版情绪追踪器

    核心功能：
    - 维护每个群聊的情绪状态
    - 根据关键词和上下文更新情绪
    - 情绪自动衰减回归平静
    """

    # 预定义的情绪状态和对应的关键词
    MOOD_KEYWORDS = {
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
        ],
        "难过": ["难过", "伤心", "哭", "😢", "😭", "呜呜", "555", "心疼"],
        "生气": ["生气", "气", "烦", "😡", "😠", "恼火", "讨厌"],
        "惊讶": ["哇", "天哪", "😮", "😲", "震惊", "卧槽", "我去"],
        "疑惑": ["？", "疑惑", "🤔", "为什么", "怎么", "什么"],
        "无语": ["无语", "😑", "...", "省略号", "服了", "醉了"],
        "兴奋": ["！！", "激动", "😆", "🎉", "太好了", "yes", "耶"],
    }

    # 默认情绪
    DEFAULT_MOOD = "平静"

    # 情绪衰减时间（秒）
    MOOD_DECAY_TIME = 300  # 5分钟后开始衰减

    def __init__(self):
        """初始化情绪追踪器"""
        # 存储每个群聊的情绪状态
        # 格式: {chat_id: {"mood": "情绪", "intensity": 强度, "last_update": 时间戳}}
        self.moods: Dict[str, Dict] = {}

        logger.info("[情绪追踪系统] 已初始化")

    def _detect_mood_from_text(self, text: str) -> Optional[str]:
        """
        从文本中检测情绪

        Args:
            text: 要分析的文本

        Returns:
            检测到的情绪，如果没有明显情绪则返回None
        """
        if not text:
            return None

        # 统计各种情绪的关键词出现次数
        mood_scores = {}
        for mood, keywords in self.MOOD_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                mood_scores[mood] = score

        if not mood_scores:
            return None

        # 返回得分最高的情绪
        return max(mood_scores, key=mood_scores.get)

    def update_mood_from_context(self, chat_id: str, recent_messages: str) -> str:
        """
        根据最近的对话内容更新情绪

        Args:
            chat_id: 群聊ID
            recent_messages: 最近的消息上下文

        Returns:
            更新后的情绪状态
        """
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

            if time_since_update > self.MOOD_DECAY_TIME:
                # 情绪衰减，逐渐回归平静
                self.moods[chat_id]["mood"] = self.DEFAULT_MOOD
                self.moods[chat_id]["intensity"] = max(
                    0.0, self.moods[chat_id]["intensity"] - 0.2
                )
                logger.debug(f"[情绪追踪] {chat_id} 情绪衰减到: {self.DEFAULT_MOOD}")

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
        if chat_id not in self.moods:
            return self.DEFAULT_MOOD

        # 检查是否需要衰减
        current_time = time.time()
        time_since_update = current_time - self.moods[chat_id]["last_update"]

        if time_since_update > self.MOOD_DECAY_TIME:
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

        logger.debug(f"[情绪追踪] {chat_id} 注入情绪: {current_mood}")

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
