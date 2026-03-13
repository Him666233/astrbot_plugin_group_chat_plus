"""
消息质量预判模块
在概率掷骰之前对消息进行轻量级内容分析，调整触发概率

核心功能：
1. 疑问句检测 - 消息含问号或配置的疑问词时概率提升
2. 水消息检测 - 消息完整匹配配置的水消息词时概率降低
3. 极短消息检测 - <=2字符且非问句时概率降低
4. 所有规则完全由配置驱动，默认值为合理的内置词列表

作者: Him666233
版本: v1.2.1
"""

import re
from typing import Tuple, List
from astrbot.api.all import logger

# 详细日志开关
DEBUG_MODE: bool = False


class MessageQualityScorer:
    """
    消息质量预判器

    对消息内容做轻量级分析，返回概率调整值。
    正值=提升概率，负值=降低概率。

    所有规则完全由配置驱动：
    - 水消息词列表（整句完整匹配）
    - 疑问词列表（包含匹配）
    用户可在配置中直接修改这两个列表，默认值为合理的预设词表。
    """

    # 配置（由 main.py 初始化）
    _enabled: bool = False
    _question_boost: float = 0.15
    _water_reduce: float = 0.10

    # 规则（完全由配置驱动）
    _water_words_set: frozenset = frozenset()  # 水消息词集合（整句完整匹配，O(1)查找）
    _question_re: re.Pattern = None  # 疑问词正则（包含匹配）

    @classmethod
    def initialize(cls, config: dict) -> None:
        """初始化，配置由 main.py 统一提取后传入"""
        cls._enabled = config["enable_message_quality_scoring"]
        cls._question_boost = config["message_quality_question_boost"]
        cls._water_reduce = config["message_quality_water_reduce"]

        # 水消息词列表 → frozenset（去重、过滤空串）
        raw_water: List[str] = config.get("message_quality_water_words", [])
        cls._water_words_set = frozenset(
            w.strip() for w in raw_water if isinstance(w, str) and w.strip()
        )

        # 疑问词列表 → 编译为正则（包含匹配）
        raw_question: List[str] = config.get("message_quality_question_words", [])
        valid_words = [
            w.strip() for w in raw_question if isinstance(w, str) and w.strip()
        ]
        if valid_words:
            # 同时匹配问号字符和配置的疑问词
            all_patterns = [re.escape(w) for w in valid_words] + [r"[？?]"]
            try:
                cls._question_re = re.compile("|".join(all_patterns))
            except re.error as e:
                logger.warning(f"[消息质量] 疑问词正则编译失败: {e}，已禁用疑问句检测")
                cls._question_re = None
        else:
            # 至少保留问号检测
            cls._question_re = re.compile(r"[？?]")

        if DEBUG_MODE:
            logger.info(
                f"[消息质量] 已初始化: 疑问提升={cls._question_boost}, "
                f"水消息降低={cls._water_reduce}, "
                f"水消息词={len(cls._water_words_set)}个, "
                f"疑问词正则={'已编译' if cls._question_re else '无'}"
            )

    @classmethod
    def score_message(cls, text: str) -> Tuple[float, str]:
        """
        对消息进行质量评分

        Args:
            text: 原始消息文本

        Returns:
            (概率调整值, 原因说明)
            正值=提升概率，负值=降低概率，0=不调整
        """
        if not cls._enabled or not text:
            return 0.0, ""

        text_stripped = text.strip()
        has_question_mark = "?" in text_stripped or "？" in text_stripped

        # 极短消息（<=2字符且非问句）视为水消息
        if len(text_stripped) <= 2 and not has_question_mark:
            return -cls._water_reduce, "极短消息"

        # 水消息词检测（整句完整匹配，集合查找）
        # 疑问句检测（包含匹配），疑问句优先级高于水消息
        is_question = has_question_mark or (
            cls._question_re is not None and cls._question_re.search(text_stripped)
        )
        if is_question:
            return cls._question_boost, "疑问句"

        if text_stripped in cls._water_words_set:
            return -cls._water_reduce, "水消息"

        return 0.0, ""
