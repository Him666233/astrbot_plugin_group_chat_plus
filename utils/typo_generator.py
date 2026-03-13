"""
打字错误生成器 - 基于拼音相似性的中文错别字生成
让AI回复显得更像真人，添加少量自然的错别字

核心理念：
- 保持"读空气"为主，错字为辅
- 仅在回复生成后添加，不影响AI判断逻辑
- 低概率、高自然度

作者: Him666233
版本: v1.2.1
参考: MaiBot typo_generator.py (简化实现)
"""

import random
import json
import os
from typing import Optional, Tuple, Dict, List, Any
from pypinyin import Style, pinyin

from astrbot.api.all import logger

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class TypoGenerator:
    """
    简化版错别字生成器

    核心功能：
    - 基于拼音相似性替换汉字
    - 优先替换常用字
    - 低概率触发，保持自然
    """

    def __init__(
        self, error_rate: float = 0.02, config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化错别字生成器

        Args:
            error_rate: 错别字生成概率，默认2%（建议0.01-0.05）
            config: 插件配置字典，包含自定义同音字映射等配置
        """
        self.error_rate = error_rate

        # 从配置读取参数，如果没有配置则使用默认值
        if config is None:
            config = {}

        # 说明：配置由 main.py 统一提取后传入，此处直接使用传入的值，
        # 不再提供默认值（避免 AstrBot 平台多次读取配置的问题）

        # 详细日志开关
        self.debug_mode = config.get("enable_debug_log", False)  # 此项可选，允许默认值

        # 错字相关可配置参数（直接使用传入的值）
        self.min_text_length = config["typo_min_text_length"]
        self.min_chinese_chars = config["typo_min_chinese_chars"]
        self.min_message_length = config["typo_min_message_length"]
        self.min_typo_count = config["typo_min_count"]
        self.max_typo_count = config["typo_max_count"]

        # 常见同音字映射表（精简版，避免加载大型字典）
        # 格式：{字: [同音字列表]}
        self.common_homophones = self._init_common_homophones(config)

        if DEBUG_MODE or self.debug_mode:
            logger.info(
                f"[打字错误生成器] 已初始化，错字率: {error_rate:.1%}，"
                f"错字数量范围: {self.min_typo_count}-{self.max_typo_count}"
            )

    def _get_default_homophones(self) -> Dict[str, List[str]]:
        """
        获取默认的同音字映射表

        Returns:
            默认的同音字映射字典
        """
        return {
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
            # 那/哪
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
            # 呢/呐
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
            # 看/坎
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

    def _parse_custom_homophones(self, custom_json: str) -> Dict[str, List[str]]:
        """
        解析自定义同音字配置

        Args:
            custom_json: JSON格式的自定义同音字配置

        Returns:
            解析后的同音字字典，解析失败返回空字典
        """
        if not custom_json or not custom_json.strip():
            return {}

        try:
            parsed = json.loads(custom_json)
            if not isinstance(parsed, dict):
                logger.warning("[打字错误生成器] 自定义同音字配置格式错误：应为字典")
                return {}

            # 验证格式：{字: [同音字列表]}
            result = {}
            for key, value in parsed.items():
                if not isinstance(key, str) or len(key) != 1:
                    logger.warning(
                        f"[打字错误生成器] 同音字配置键'{key}'应为单个汉字，已跳过"
                    )
                    continue
                if isinstance(value, list):
                    # 过滤非字符串和非单字的值
                    valid_chars = [
                        v for v in value if isinstance(v, str) and len(v) == 1
                    ]
                    if valid_chars:
                        result[key] = valid_chars
                elif isinstance(value, str) and len(value) == 1:
                    result[key] = [value]
                else:
                    logger.warning(
                        f"[打字错误生成器] 同音字'{key}'的值格式错误，已跳过"
                    )

            if result and (DEBUG_MODE or getattr(self, "debug_mode", False)):
                logger.info(f"[打字错误生成器] 已加载 {len(result)} 个自定义同音字配置")

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"[打字错误生成器] 解析自定义同音字JSON失败: {e}")
            return {}
        except Exception as e:
            logger.warning(f"[打字错误生成器] 处理自定义同音字配置时出错: {e}")
            return {}

    def _init_common_homophones(
        self, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[str]]:
        """
        初始化常见同音字映射表

        使用高频易混淆的字对，而非完整字典
        这样可以避免依赖大型数据文件，且效果更自然

        Args:
            config: 插件配置字典

        Returns:
            合并后的同音字映射表
        """
        # 获取默认同音字配置
        homophones = self._get_default_homophones()

        # 从配置中读取自定义同音字（直接使用传入的值）
        if config:
            custom_json = config["typo_homophones"]
            custom_homophones = self._parse_custom_homophones(custom_json)
            if not custom_json:
                logger.info(f"[打字错误生成器] 未读取到自定义同音字配置，使用默认配置")
            # 合并配置：自定义配置覆盖默认配置
            if custom_homophones:
                for char, alternatives in custom_homophones.items():
                    homophones[char] = alternatives
                logger.info(
                    f"[打字错误生成器] 已合并自定义同音字配置，总计 {len(homophones)} 个字"
                )

        return homophones

    def _is_chinese_char(self, char: str) -> bool:
        """判断是否为汉字"""
        return "\u4e00" <= char <= "\u9fff"

    def add_typos(self, text: str, max_typos: Optional[int] = None) -> Tuple[str, int]:
        """
        为文本添加错别字

        Args:
            text: 原始文本
            max_typos: 最多添加几个错字，默认使用配置值

        Returns:
            (处理后的文本, 实际添加的错字数量)
        """
        # 使用配置的最大错字数，如果未指定
        if max_typos is None:
            max_typos = self.max_typo_count

        if not text or len(text) < self.min_text_length:
            # 太短的文本不添加错字
            return text, 0

        # 提取所有汉字位置
        chinese_chars = []
        for i, char in enumerate(text):
            if self._is_chinese_char(char):
                chinese_chars.append((i, char))

        if len(chinese_chars) < self.min_chinese_chars:
            # 汉字太少，不添加错字
            return text, 0

        # 决定添加几个错字（在最小和最大范围内）
        num_typos = self.min_typo_count  # 从最小值开始
        for _ in range(max_typos - self.min_typo_count):
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

                    if logger and DEBUG_MODE:
                        logger.info(f"[打字错误] {original_char} → {typo_char}")

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
        if len(text) < self.min_message_length:
            return False

        # 包含特殊格式的消息不添加（如代码、命令等）
        if any(marker in text for marker in ["```", "`", "[", "]", "{", "}"]):
            return False

        # 包含URL的消息不添加
        if "http://" in text or "https://" in text or "www." in text:
            return False

        # 根据 error_rate 决定是否添加错字
        return random.random() < self.error_rate

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
