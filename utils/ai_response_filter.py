"""
AI响应过滤器 - 处理带思考链的AI返回
过滤掉AI输出中的思考过程标记，避免影响决策判断

作者: Him666233
版本: v1.1.2
"""

import re
from typing import Optional
from astrbot.api import logger

# 详细日志开关
DEBUG_MODE: bool = False


class AIResponseFilter:
    """
    AI响应过滤器

    主要功能：
    1. 移除常见的思考链标记（XML格式）
    2. 移除中文思考过程前缀
    3. 提取纯净的AI回复内容

    支持的思考链格式：
    - <thinking>...</thinking>
    - <think>...</think>
    - <thought>...</thought>
    - <reasoning>...</reasoning>
    - 中文前缀：思考：、分析：、判断：等
    """

    # XML风格的思考标签正则列表
    THINKING_TAG_PATTERNS = [
        r"<thinking>.*?</thinking>",
        r"<think>.*?</think>",
        r"<thought>.*?</thought>",
        r"<reasoning>.*?</reasoning>",
        r"<analysis>.*?</analysis>",
        r"<考虑>.*?</考虑>",
        r"<思考>.*?</思考>",
        r"<分析>.*?</分析>",
    ]

    # 中文思考过程前缀模式
    CHINESE_THINKING_PREFIXES = [
        r"^思考[：:]\s*",
        r"^分析[：:]\s*",
        r"^判断[：:]\s*",
        r"^推理[：:]\s*",
        r"^考虑[：:]\s*",
        r"^评估[：:]\s*",
        r"^我的想法[：:]\s*",
        r"^让我想想[：:]\s*",
    ]

    @staticmethod
    def filter_thinking_chain(response: str) -> str:
        """
        过滤AI响应中的思考链标记

        Args:
            response: 原始AI响应

        Returns:
            过滤后的响应文本
        """
        if not response or not isinstance(response, str):
            return response

        original_response = response

        # 第一步：移除XML风格的思考标签
        for pattern in AIResponseFilter.THINKING_TAG_PATTERNS:
            # 使用 DOTALL 标志，让 . 匹配包括换行符在内的所有字符
            response = re.sub(pattern, "", response, flags=re.DOTALL | re.IGNORECASE)

        # 第二步：移除中文思考过程前缀及其后的内容（更智能的处理）
        lines = response.split("\n")
        filtered_lines = []

        # 定义简单答案的集合（用于判断是否应该保留）
        # 包含决策判断和频率判断的所有可能答案
        simple_answers = {
            # 决策判断
            "yes",
            "y",
            "no",
            "n",
            "是",
            "否",
            "应该",
            "不应该",
            "回复",
            "不回复",
            # 频率判断
            "正常",
            "过于频繁",
            "过少",
            "太少",
            "太频繁",
            "频繁",
            "少",
            "合适",
            "适当",
        }

        for line in lines:
            line_stripped = line.strip()

            if not line_stripped:
                continue

            # 检查是否是思考前缀开头的行
            found_thinking_prefix = False
            extracted_answer = None

            for prefix_pattern in AIResponseFilter.CHINESE_THINKING_PREFIXES:
                match = re.match(prefix_pattern, line_stripped, flags=re.IGNORECASE)
                if match:
                    found_thinking_prefix = True
                    # 提取前缀后的内容
                    remaining = line_stripped[match.end() :].strip()
                    # 如果后面是简单答案，保留答案
                    if remaining.lower() in simple_answers:
                        extracted_answer = remaining
                    # 否则整行跳过（这是思考过程的描述）
                    break

            # 如果找到思考前缀
            if found_thinking_prefix:
                # 只保留提取到的简单答案（如果有）
                if extracted_answer:
                    filtered_lines.append(extracted_answer)
                # 否则跳过整行
            else:
                # 不是思考前缀行，保留
                filtered_lines.append(line)

        response = "\n".join(filtered_lines)

        # 第三步：清理多余的空白
        response = response.strip()

        # 第四步：移除可能存在的"回答："、"答："等前缀
        answer_prefixes = [
            r"^回答[：:]\s*",
            r"^答[：:]\s*",
            r"^结论[：:]\s*",
            r"^结果[：:]\s*",
        ]

        for prefix_pattern in answer_prefixes:
            response = re.sub(prefix_pattern, "", response, flags=re.IGNORECASE)

        response = response.strip()

        # 记录日志（如果内容发生了变化）
        if response != original_response and DEBUG_MODE:
            logger.info(f"[AI响应过滤] 检测到思考链内容并已过滤")
            logger.info(f"  原始响应前100字符: {original_response[:100]}...")
            logger.info(f"  过滤后响应: {response}")

        return response

    @staticmethod
    def extract_decision_answer(response: str) -> Optional[str]:
        """
        从可能包含思考链的响应中提取决策答案（yes/no）

        这是一个增强版提取器，专门用于决策AI的场景

        Args:
            response: AI响应文本

        Returns:
            提取到的答案（yes/no/是/否等），如果无法提取则返回None
        """
        if not response:
            return None

        # 先进行标准过滤
        filtered = AIResponseFilter.filter_thinking_chain(response)

        # 清理文本
        cleaned = filtered.strip().lower()

        # 移除标点符号
        cleaned = cleaned.rstrip(".,!?。,!?")

        # 优先检查完整匹配
        if cleaned in [
            "yes",
            "y",
            "no",
            "n",
            "是",
            "否",
            "应该",
            "不应该",
            "回复",
            "不回复",
        ]:
            return cleaned

        # 尝试提取第一个有效的yes/no
        yes_pattern = r"\b(yes|y|是|应该|回复)\b"
        no_pattern = r"\b(no|n|否|不应该|不回复)\b"

        # 先找no（因为"不应该"等否定词更具体）
        no_match = re.search(no_pattern, cleaned, re.IGNORECASE)
        if no_match:
            return no_match.group(1)

        # 再找yes
        yes_match = re.search(yes_pattern, cleaned, re.IGNORECASE)
        if yes_match:
            return yes_match.group(1)

        # 如果都找不到，返回清理后的文本（让调用者自己判断）
        return cleaned

    @staticmethod
    def extract_frequency_decision(response: str) -> Optional[str]:
        """
        从可能包含思考链的响应中提取频率判断（正常/过于频繁/过少）

        这是一个增强版提取器，专门用于频率调整的场景

        Args:
            response: AI响应文本

        Returns:
            提取到的判断结果，如果无法提取则返回None
        """
        if not response:
            return None

        # 先进行标准过滤
        filtered = AIResponseFilter.filter_thinking_chain(response)

        # 清理文本
        cleaned = filtered.strip().replace("。", "").replace("!", "").replace("！", "")

        # 检查完整匹配
        if cleaned in ["正常", "过于频繁", "过少"]:
            return cleaned

        # 扩展关键词匹配（更宽松的匹配，因为思考链过滤后可能只剩下简短的词）
        # 优先匹配"过于频繁"相关
        if "过于频繁" in cleaned or "过度频繁" in cleaned or "太频繁" in cleaned:
            return "过于频繁"

        # 单独的"频繁"也算（但要排除"不频繁"等否定情况）
        if "频繁" in cleaned and "不" not in cleaned and "过" not in cleaned:
            return "过于频繁"

        # 匹配"过少"相关（包括"太少"）
        if (
            "过少" in cleaned
            or "太少" in cleaned
            or "过于少" in cleaned
            or cleaned == "少"
        ):
            return "过少"

        # 匹配"正常"相关
        if "正常" in cleaned or "合适" in cleaned or "适当" in cleaned:
            return "正常"

        # 无法识别
        if DEBUG_MODE:
            logger.warning(f"[AI响应过滤] 无法从响应中提取频率判断: {cleaned[:50]}")

        return None
