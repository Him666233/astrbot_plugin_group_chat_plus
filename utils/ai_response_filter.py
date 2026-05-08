"""
AI响应过滤器 - 处理带思考链/额外推理块的AI返回
过滤掉AI输出中的思考过程标记，并提取最终判定结果

作者: Him666233
版本: v1.2.1
"""

import re
from typing import Optional, Dict, Any, Tuple
from astrbot.api import logger

# 详细日志开关
DEBUG_MODE: bool = False


class AIResponseFilter:
    """
    AI响应过滤器

    主要功能：
    1. 移除常见的思考链标记（XML格式）
    2. 移除中文思考过程前缀
    3. 提取自定义额外推理块
    4. 归一化判断型AI的最终输出
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

    ANSWER_PREFIXES = [
        r"^回答[：:]\s*",
        r"^答[：:]\s*",
        r"^结论[：:]\s*",
        r"^结果[：:]\s*",
        r"^最终答案[：:]\s*",
        r"^最终判断[：:]\s*",
    ]

    @staticmethod
    def filter_thinking_chain(response: str) -> str:
        """
        过滤AI响应中的模型原生思考链标记

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
            response = re.sub(pattern, "", response, flags=re.DOTALL | re.IGNORECASE)

        # 第二步：移除中文思考过程前缀及其后的内容（更智能的处理）
        lines = response.split("\n")
        filtered_lines = []

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
            "适合",
            "不适合",
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

            found_thinking_prefix = False
            extracted_answer = None

            for prefix_pattern in AIResponseFilter.CHINESE_THINKING_PREFIXES:
                match = re.match(prefix_pattern, line_stripped, flags=re.IGNORECASE)
                if match:
                    found_thinking_prefix = True
                    remaining = line_stripped[match.end() :].strip()
                    if remaining.lower() in simple_answers:
                        extracted_answer = remaining
                    break

            if found_thinking_prefix:
                if extracted_answer:
                    filtered_lines.append(extracted_answer)
            else:
                filtered_lines.append(line)

        response = "\n".join(filtered_lines).strip()
        response = AIResponseFilter._strip_answer_prefixes(response)

        if response != original_response and DEBUG_MODE:
            logger.info("[AI响应过滤] 检测到模型原生思考链并已过滤")
            logger.info(f"  原始响应前100字符: {original_response[:100]}...")
            logger.info(f"  过滤后响应: {response}")

        return response

    @staticmethod
    def _strip_answer_prefixes(response: str) -> str:
        """移除常见答案前缀"""
        if not response:
            return response

        cleaned = response.strip()
        for prefix_pattern in AIResponseFilter.ANSWER_PREFIXES:
            cleaned = re.sub(prefix_pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    @staticmethod
    def _extract_custom_reasoning_block(
        response: str, start_marker: str = "", end_marker: str = ""
    ) -> Tuple[str, str]:
        """
        提取自定义额外推理块，并从文本中剥离

        Returns:
            (剥离后的文本, 推理文本)
        """
        if not response:
            return response, ""

        start_marker = (start_marker or "").strip()
        end_marker = (end_marker or "").strip()
        if not start_marker or not end_marker:
            return response, ""

        pattern = re.compile(
            re.escape(start_marker) + r"([\s\S]*?)" + re.escape(end_marker),
            re.IGNORECASE,
        )

        reasoning_blocks = [
            m.group(1).strip() for m in pattern.finditer(response) if m.group(1).strip()
        ]
        filtered = pattern.sub("", response).strip()

        reasoning_text = "\n\n".join(reasoning_blocks).strip()
        filtered = re.sub(r"\n{3,}", "\n\n", filtered).strip()
        filtered = AIResponseFilter._strip_answer_prefixes(filtered)
        return filtered, reasoning_text

    @staticmethod
    def _build_parse_result(
        response: str,
        start_marker: str,
        end_marker: str,
        normalized_answer: Optional[str],
    ) -> Dict[str, Any]:
        """构造统一解析结果"""
        filtered = AIResponseFilter.filter_thinking_chain(response)
        final_text, reasoning_text = AIResponseFilter._extract_custom_reasoning_block(
            filtered, start_marker, end_marker
        )
        final_text = AIResponseFilter._strip_answer_prefixes(final_text)
        return {
            "filtered_text": final_text,
            "reasoning_text": reasoning_text,
            "normalized_answer": normalized_answer,
            "parse_success": normalized_answer is not None,
        }

    @staticmethod
    def _extract_last_non_empty_line(text: str) -> str:
        """提取最后一个非空行。"""
        if not text:
            return ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines[-1] if lines else ""

    @staticmethod
    def _normalize_tail_token(token: str) -> str:
        """对最终答案候选行做轻量清理。"""
        if not token:
            return ""
        cleaned = token.strip()
        cleaned = AIResponseFilter._strip_answer_prefixes(cleaned)
        cleaned = cleaned.strip().rstrip(".,!?。,!？；;:：")
        return cleaned.strip()

    @staticmethod
    def _decision_exact_map() -> Dict[str, str]:
        return {
            "yes": "yes",
            "y": "y",
            "no": "no",
            "n": "n",
            "是": "是",
            "否": "否",
            "应该": "应该",
            "不应该": "不应该",
            "回复": "回复",
            "不回复": "不回复",
            "适合": "适合",
            "合适": "适合",
            "可以发起": "适合",
            "可以主动发起": "适合",
            "适合发起": "适合",
            "适合主动发起": "适合",
            "适合主动对话": "适合",
            "适合主动发言": "适合",
            "适合插话": "适合",
            "可以插话": "适合",
            "可以接话": "适合",
            "可以自然接入": "适合",
            "不适合": "不适合",
            "不合适": "不适合",
            "现在不适合": "不适合",
            "暂时不适合": "不适合",
            "目前不适合": "不适合",
            "不适合发起": "不适合",
            "不适合主动发起": "不适合",
            "不适合主动对话": "不适合",
            "不适合主动发言": "不适合",
            "不适合插话": "不适合",
            "不建议": "不适合",
            "跳过": "不适合",
            "跳过这次": "不适合",
            "跳过本次": "不适合",
        }

    @staticmethod
    def _frequency_exact_map() -> Dict[str, str]:
        return {
            "正常": "正常",
            "过于频繁": "过于频繁",
            "过少": "过少",
            "合适": "正常",
            "适当": "正常",
            "适中": "正常",
            "刚好": "正常",
            "偏少": "过少",
            "有点少": "过少",
            "太少": "过少",
            "偏频繁": "过于频繁",
            "有点频繁": "过于频繁",
            "太频繁": "过于频繁",
        }

    @staticmethod
    def parse_decision_response(
        response: str, start_marker: str = "", end_marker: str = ""
    ) -> Dict[str, Any]:
        """
        解析决策型AI响应（读空气/主动对话判断）
        """
        if not response:
            return {
                "filtered_text": "",
                "reasoning_text": "",
                "normalized_answer": None,
                "parse_success": False,
            }

        filtered = AIResponseFilter.filter_thinking_chain(response)
        final_text, reasoning_text = AIResponseFilter._extract_custom_reasoning_block(
            filtered, start_marker, end_marker
        )
        exact_decision_map = AIResponseFilter._decision_exact_map()
        tail_line = AIResponseFilter._extract_last_non_empty_line(final_text)
        tail_cleaned = AIResponseFilter._normalize_tail_token(tail_line).lower()
        if tail_cleaned in exact_decision_map:
            normalized_answer = exact_decision_map[tail_cleaned]
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": normalized_answer,
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": True,
            }

        cleaned = final_text.strip().lower().rstrip(".,!?。,!？；;:：")
        cleaned = AIResponseFilter._strip_answer_prefixes(cleaned)

        proactive_negative_patterns = [
            r"不适合",
            r"不合适",
            r"不建议",
            r"跳过(?:这次|本次)?",
            r"暂时不适合",
            r"目前不适合",
            r"现在不适合",
            r"不适宜",
            r"不宜主动",
            r"不适合主动",
            r"不适合发起",
            r"不适合插话",
            r"不方便主动",
            r"无需主动",
            r"不需要主动",
        ]
        for pattern in proactive_negative_patterns:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return {
                    "filtered_text": final_text,
                    "reasoning_text": reasoning_text,
                    "normalized_answer": "不适合",
                    "parse_success": True,
                    "tail_line": tail_line,
                    "tail_candidate": tail_cleaned,
                    "protocol_followed": False,
                }

        proactive_positive_patterns = [
            r"适合",
            r"合适",
            r"可以主动发起",
            r"可以发起",
            r"适合主动",
            r"适合发起",
            r"适合插话",
            r"可以插话",
            r"可以接话",
            r"可以自然接入",
            r"可以自然参与",
            r"适合参与",
        ]
        for pattern in proactive_positive_patterns:
            if re.search(pattern, cleaned, re.IGNORECASE):
                return {
                    "filtered_text": final_text,
                    "reasoning_text": reasoning_text,
                    "normalized_answer": "适合",
                    "parse_success": True,
                    "tail_line": tail_line,
                    "tail_candidate": tail_cleaned,
                    "protocol_followed": False,
                }

        negative_tokens = ["不应该", "不回复", "否"]
        for token in negative_tokens:
            if token in cleaned:
                return {
                    "filtered_text": final_text,
                    "reasoning_text": reasoning_text,
                    "normalized_answer": token,
                    "parse_success": True,
                    "tail_line": tail_line,
                    "tail_candidate": tail_cleaned,
                    "protocol_followed": False,
                }

        positive_tokens = ["应该", "回复"]
        for token in positive_tokens:
            if token in cleaned:
                return {
                    "filtered_text": final_text,
                    "reasoning_text": reasoning_text,
                    "normalized_answer": token,
                    "parse_success": True,
                    "tail_line": tail_line,
                    "tail_candidate": tail_cleaned,
                    "protocol_followed": False,
                }

        english_no_match = re.search(r"\b(no|n)\b", cleaned, re.IGNORECASE)
        if english_no_match:
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": english_no_match.group(1).lower(),
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": False,
            }

        english_yes_match = re.search(r"\b(yes|y)\b", cleaned, re.IGNORECASE)
        if english_yes_match:
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": english_yes_match.group(1).lower(),
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": False,
            }

        if cleaned.startswith("是") or cleaned.endswith("是"):
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": "是",
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": False,
            }

        if DEBUG_MODE:
            logger.warning(f"[AI响应过滤] 无法从响应中提取决策判断: {final_text[:80]}")

        return {
            "filtered_text": final_text,
            "reasoning_text": reasoning_text,
            "normalized_answer": None,
            "parse_success": False,
            "tail_line": tail_line,
            "tail_candidate": tail_cleaned,
            "protocol_followed": False,
        }

    @staticmethod
    def extract_decision_answer(
        response: str, start_marker: str = "", end_marker: str = ""
    ) -> Optional[str]:
        """
        兼容旧调用：提取决策答案（yes/no/适合/不适合）
        """
        return AIResponseFilter.parse_decision_response(
            response, start_marker, end_marker
        ).get("normalized_answer")

    @staticmethod
    def parse_frequency_response(
        response: str, start_marker: str = "", end_marker: str = ""
    ) -> Dict[str, Any]:
        """
        解析频率判断型AI响应（正常/过于频繁/过少）
        """
        if not response:
            return {
                "filtered_text": "",
                "reasoning_text": "",
                "normalized_answer": None,
                "parse_success": False,
            }

        filtered = AIResponseFilter.filter_thinking_chain(response)
        final_text, reasoning_text = AIResponseFilter._extract_custom_reasoning_block(
            filtered, start_marker, end_marker
        )
        exact_map = AIResponseFilter._frequency_exact_map()
        tail_line = AIResponseFilter._extract_last_non_empty_line(final_text)
        tail_cleaned = AIResponseFilter._normalize_tail_token(tail_line)
        if tail_cleaned in exact_map:
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": exact_map[tail_cleaned],
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": True,
            }

        cleaned = (
            final_text.strip().replace("。", "").replace("!", "").replace("！", "")
        )
        cleaned = cleaned.replace("?", "").replace("？", "").strip()
        cleaned = AIResponseFilter._strip_answer_prefixes(cleaned)

        if "过于频繁" in cleaned or "过度频繁" in cleaned or "太频繁" in cleaned:
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": "过于频繁",
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": False,
            }

        if re.search(r"(?:有点|偏)?频繁", cleaned) and "不频繁" not in cleaned:
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": "过于频繁",
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": False,
            }

        if (
            "过少" in cleaned
            or "太少" in cleaned
            or "过于少" in cleaned
            or cleaned == "少"
            or "偏少" in cleaned
            or "有点少" in cleaned
        ):
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": "过少",
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": False,
            }

        if (
            "正常" in cleaned
            or "合适" in cleaned
            or "适当" in cleaned
            or "适中" in cleaned
        ):
            return {
                "filtered_text": final_text,
                "reasoning_text": reasoning_text,
                "normalized_answer": "正常",
                "parse_success": True,
                "tail_line": tail_line,
                "tail_candidate": tail_cleaned,
                "protocol_followed": False,
            }

        if DEBUG_MODE:
            logger.warning(f"[AI响应过滤] 无法从响应中提取频率判断: {cleaned[:50]}")

        return {
            "filtered_text": final_text,
            "reasoning_text": reasoning_text,
            "normalized_answer": None,
            "parse_success": False,
            "tail_line": tail_line,
            "tail_candidate": tail_cleaned,
            "protocol_followed": False,
        }

    @staticmethod
    def extract_frequency_decision(
        response: str, start_marker: str = "", end_marker: str = ""
    ) -> Optional[str]:
        """
        兼容旧调用：提取频率判断（正常/过于频繁/过少）
        """
        return AIResponseFilter.parse_frequency_response(
            response, start_marker, end_marker
        ).get("normalized_answer")
