"""
打字错误生成器 - 基于拼音相似性的中文错别字生成
让AI回复显得更像真人，添加少量自然的错别字

核心理念：
- 保持"读空气"为主，错字为辅
- 仅在回复生成后添加，不影响AI判断逻辑
- 低概率、高自然度

作者: Him666233
版本: v1.0.7
参考: MaiBot typo_generator.py (简化实现)
"""

import random
from typing import Optional, Tuple
from pypinyin import Style, pinyin

from astrbot.api.all import logger


class TypoGenerator:
    """
    简化版错别字生成器

    核心功能：
    - 基于拼音相似性替换汉字
    - 优先替换常用字
    - 低概率触发，保持自然
    """

    def __init__(self, error_rate: float = 0.02):
        """
        初始化错别字生成器

        Args:
            error_rate: 错别字生成概率，默认2%（建议0.01-0.05）
        """
        self.error_rate = error_rate

        # 常见同音字映射表（精简版，避免加载大型字典）
        # 格式：{字: [同音字列表]}
        self.common_homophones = self._init_common_homophones()

        logger.info(f"[打字错误生成器] 已初始化，错字率: {error_rate:.1%}")

    def _init_common_homophones(self) -> dict:
        """
        初始化常见同音字映射表

        使用高频易混淆的字对，而非完整字典
        这样可以避免依赖大型数据文件，且效果更自然
        """
        # 精选的高频易混淆字对
        homophones = {
            # 的/得/地
            "的": ["得", "地"],
            "得": ["的", "地"],
            "地": ["的", "得"],
            # 在/再
            "在": ["再"],
            "再": ["在"],
            # 做/作
            "做": ["作"],
            "作": ["做"],
            # 已/以
            "已": ["以"],
            "以": ["已"],
            # 其/起
            "其": ["起"],
            "起": ["其"],
            # 会/回
            "会": ["回"],
            "回": ["会"],
            # 像/象
            "像": ["象"],
            "象": ["像"],
            # 在/再
            "那": ["哪"],
            "哪": ["那"],
            # 它/他/她
            "它": ["他", "她"],
            "他": ["它", "她"],
            "她": ["他", "它"],
            # 您/你
            "您": ["你"],
            "你": ["您"],
            # 吗/嘛
            "吗": ["嘛"],
            "嘛": ["吗"],
            # 呢/那
            "呢": ["呐"],
            # 就/旧
            "就": ["旧"],
            # 道/到
            "道": ["到"],
            "到": ["道"],
            # 知/只
            "知": ["只"],
            "只": ["知"],
            # 说/水
            "说": ["水"],
            # 听/挺
            "听": ["挺"],
            "挺": ["听"],
            # 看/砍
            "看": ["坎"],
            # 想/像
            "想": ["像"],
            # 好/号
            "好": ["号"],
            "号": ["好"],
            # 了/啦
            "了": ["啦"],
            "啦": ["了"],
        }

        return homophones

    def _is_chinese_char(self, char: str) -> bool:
        """判断是否为汉字"""
        return "\u4e00" <= char <= "\u9fff"

    def add_typos(self, text: str, max_typos: int = 2) -> Tuple[str, int]:
        """
        为文本添加错别字

        Args:
            text: 原始文本
            max_typos: 最多添加几个错字（默认最多2个）

        Returns:
            (处理后的文本, 实际添加的错字数量)
        """
        if not text or len(text) < 5:
            # 太短的文本不添加错字
            return text, 0

        # 提取所有汉字位置
        chinese_chars = []
        for i, char in enumerate(text):
            if self._is_chinese_char(char):
                chinese_chars.append((i, char))

        if len(chinese_chars) < 3:
            # 汉字太少，不添加错字
            return text, 0

        # 决定添加几个错字
        num_typos = 0
        for _ in range(max_typos):
            if random.random() < self.error_rate:
                num_typos += 1

        if num_typos == 0:
            return text, 0

        # 随机选择要替换的字
        typo_count = 0
        text_list = list(text)
        selected_positions = random.sample(
            chinese_chars, min(num_typos, len(chinese_chars))
        )

        for pos, original_char in selected_positions:
            # 查找同音字
            if original_char in self.common_homophones:
                candidates = self.common_homophones[original_char]
                if candidates:
                    # 随机选择一个同音字替换
                    typo_char = random.choice(candidates)
                    text_list[pos] = typo_char
                    typo_count += 1

                    if logger:
                        logger.debug(f"[打字错误] {original_char} → {typo_char}")

        result = "".join(text_list)

        if typo_count > 0 and logger:
            logger.info(f"[打字错误生成器] 添加了 {typo_count} 个错别字")

        return result, typo_count

    def should_add_typos(self, text: str) -> bool:
        """
        判断是否应该为这条消息添加错字

        Args:
            text: 消息文本

        Returns:
            True=应该添加，False=不添加
        """
        # 太短的消息不添加
        if len(text) < 10:
            return False

        # 包含特殊格式的消息不添加（如代码、命令等）
        if any(marker in text for marker in ["```", "`", "[", "]", "{", "}"]):
            return False

        # 包含URL的消息不添加
        if "http://" in text or "https://" in text or "www." in text:
            return False

        # 30%的概率添加错字（在符合条件的消息中）
        return random.random() < 0.3

    def process_reply(self, reply_text: str) -> str:
        """
        处理回复文本，可能添加错别字

        这是主要的对外接口，会自动判断是否需要添加错字

        Args:
            reply_text: 原始回复文本

        Returns:
            处理后的回复文本
        """
        if not reply_text:
            return reply_text

        # 判断是否应该添加错字
        if not self.should_add_typos(reply_text):
            return reply_text

        # 添加错字
        processed_text, typo_count = self.add_typos(reply_text)

        return processed_text
