"""
AI回复内容过滤器 - 可配置的内容清理模块
用于过滤AI输出中其他插件注入的提示词或额外内容

支持三种过滤模式：
1. 范围过滤: <开始标记>*<结束标记> - 过滤两个标记之间的所有内容（包含标记本身）
2. 头部过滤: {{>*<结束标记> - 从消息开头到结束标记（包含）全部过滤
3. 尾部过滤: <开始标记>*>}} - 从开始标记到消息末尾全部过滤

配置分为两套，互不影响：
- 输出过滤：控制AI输出给用户看的内容
- 保存过滤：控制AI保存到历史记录的内容

作者: Him666233
版本: v1.2.1
"""

import re
from typing import List, Optional, Tuple
from astrbot.api import logger

# 详细日志开关
DEBUG_MODE: bool = False

# 特殊标记符号（用于表示消息开头和末尾）
# 使用不常见的组合，避免与其他插件冲突
HEAD_MARKER = "{{>"  # 表示从消息开头开始
TAIL_MARKER = ">}}"  # 表示到消息末尾结束


class ContentFilter:
    """
    AI回复内容过滤器

    主要功能：
    1. 根据用户配置的规则过滤AI回复中的特定内容
    2. 支持范围过滤、头部过滤、尾部过滤三种模式
    3. 输出过滤和保存过滤完全独立，互不影响
    """

    @staticmethod
    def parse_filter_rule(rule: str) -> Optional[Tuple[str, str, str]]:
        """
        解析单条过滤规则

        规则格式：
        - 范围过滤: <开始标记>*<结束标记>
        - 头部过滤: {{>*<结束标记>
        - 尾部过滤: <开始标记>*>}}

        Args:
            rule: 过滤规则字符串

        Returns:
            (模式, 开始标记, 结束标记) 或 None（如果规则无效）
            模式: "range" | "head" | "tail"
        """
        if not rule or not isinstance(rule, str):
            return None

        rule = rule.strip()
        if not rule:
            return None

        # 检查是否包含通配符 *
        if "*" not in rule:
            if DEBUG_MODE:
                logger.warning(f"[内容过滤] 规则无效（缺少通配符*）: {rule}")
            return None

        # 分割规则
        parts = rule.split("*", 1)
        if len(parts) != 2:
            if DEBUG_MODE:
                logger.warning(f"[内容过滤] 规则格式错误: {rule}")
            return None

        start_marker = parts[0].strip()
        end_marker = parts[1].strip()

        # 判断过滤模式
        if start_marker == HEAD_MARKER:
            # 头部过滤模式: {{>*<结束标记>
            if not end_marker:
                if DEBUG_MODE:
                    logger.warning(f"[内容过滤] 头部过滤规则缺少结束标记: {rule}")
                return None
            return ("head", "", end_marker)

        elif end_marker == TAIL_MARKER:
            # 尾部过滤模式: <开始标记>*>}}
            if not start_marker:
                if DEBUG_MODE:
                    logger.warning(f"[内容过滤] 尾部过滤规则缺少开始标记: {rule}")
                return None
            return ("tail", start_marker, "")

        else:
            # 范围过滤模式: <开始标记>*<结束标记>
            if not start_marker or not end_marker:
                if DEBUG_MODE:
                    logger.warning(f"[内容过滤] 范围过滤规则缺少标记: {rule}")
                return None
            return ("range", start_marker, end_marker)

    @staticmethod
    def apply_single_rule(
        content: str, mode: str, start_marker: str, end_marker: str
    ) -> str:
        """
        应用单条过滤规则

        Args:
            content: 原始内容
            mode: 过滤模式 ("range" | "head" | "tail")
            start_marker: 开始标记
            end_marker: 结束标记

        Returns:
            过滤后的内容
        """
        if not content:
            return content

        original_content = content

        if mode == "head":
            # 头部过滤：从开头到结束标记（包含）
            # 查找结束标记的位置
            end_pos = content.find(end_marker)
            if end_pos != -1:
                # 移除从开头到结束标记（包含结束标记）的内容
                content = content[end_pos + len(end_marker) :]
                if DEBUG_MODE:
                    logger.info(f"[内容过滤] 头部过滤生效，移除到 '{end_marker}'")

        elif mode == "tail":
            # 尾部过滤：从开始标记到末尾（包含）
            # 查找开始标记的位置
            start_pos = content.find(start_marker)
            if start_pos != -1:
                # 移除从开始标记到末尾的内容
                content = content[:start_pos]
                if DEBUG_MODE:
                    logger.info(
                        f"[内容过滤] 尾部过滤生效，移除从 '{start_marker}' 开始的内容"
                    )

        elif mode == "range":
            # 范围过滤：移除开始标记和结束标记之间的内容（包含标记）
            # 使用循环处理多次出现的情况
            while True:
                start_pos = content.find(start_marker)
                if start_pos == -1:
                    break

                # 从开始标记位置之后查找结束标记
                end_pos = content.find(end_marker, start_pos + len(start_marker))
                if end_pos == -1:
                    # 找不到结束标记，停止处理
                    break

                # 移除这段内容（包含两个标记）
                content = content[:start_pos] + content[end_pos + len(end_marker) :]
                if DEBUG_MODE:
                    logger.info(
                        f"[内容过滤] 范围过滤生效，移除 '{start_marker}' 到 '{end_marker}' 之间的内容"
                    )

        # 清理多余的空白
        if content != original_content:
            # 移除连续的空行（保留最多一个空行）
            content = re.sub(r"\n{3,}", "\n\n", content)
            content = content.strip()

        return content

    @staticmethod
    def filter_content(content: str, rules: List[str]) -> str:
        """
        根据规则列表过滤内容

        Args:
            content: 原始内容
            rules: 过滤规则列表

        Returns:
            过滤后的内容
        """
        if not content or not rules:
            return content

        original_content = content

        for rule in rules:
            parsed = ContentFilter.parse_filter_rule(rule)
            if parsed:
                mode, start_marker, end_marker = parsed
                content = ContentFilter.apply_single_rule(
                    content, mode, start_marker, end_marker
                )

        if content != original_content and DEBUG_MODE:
            logger.info(f"[内容过滤] 过滤完成")
            logger.info(f"  原始长度: {len(original_content)}")
            logger.info(f"  过滤后长度: {len(content)}")

        return content

    @staticmethod
    def filter_for_output(content: str, enabled: bool, rules: List[str]) -> str:
        """
        过滤AI输出内容（用于发送给用户）

        Args:
            content: AI原始回复
            enabled: 是否启用输出过滤
            rules: 输出过滤规则列表

        Returns:
            过滤后的内容
        """
        if not enabled or not rules:
            return content

        if DEBUG_MODE:
            logger.info(f"[输出过滤] 开始过滤，规则数: {len(rules)}")

        return ContentFilter.filter_content(content, rules)

    @staticmethod
    def filter_for_save(content: str, enabled: bool, rules: List[str]) -> str:
        """
        过滤AI保存内容（用于保存到历史记录）

        Args:
            content: AI原始回复
            enabled: 是否启用保存过滤
            rules: 保存过滤规则列表

        Returns:
            过滤后的内容
        """
        if not enabled or not rules:
            return content

        if DEBUG_MODE:
            logger.info(f"[保存过滤] 开始过滤，规则数: {len(rules)}")

        return ContentFilter.filter_content(content, rules)


class ContentFilterManager:
    """
    内容过滤管理器

    封装过滤逻辑，提供简单的接口供主程序调用
    确保输出过滤和保存过滤完全独立
    """

    def __init__(
        self,
        enable_output_filter: bool = False,
        output_filter_rules: Optional[List[str]] = None,
        enable_save_filter: bool = False,
        save_filter_rules: Optional[List[str]] = None,
        debug_mode: bool = False,
    ):
        """
        初始化过滤管理器

        Args:
            enable_output_filter: 是否启用输出过滤
            output_filter_rules: 输出过滤规则列表
            enable_save_filter: 是否启用保存过滤
            save_filter_rules: 保存过滤规则列表
            debug_mode: 是否启用调试日志
        """
        self.enable_output_filter = enable_output_filter
        self.output_filter_rules = output_filter_rules or []
        self.enable_save_filter = enable_save_filter
        self.save_filter_rules = save_filter_rules or []

        # 设置调试模式
        global DEBUG_MODE
        DEBUG_MODE = debug_mode

        if debug_mode:
            logger.info(f"[内容过滤管理器] 初始化完成")
            logger.info(
                f"  输出过滤: {'启用' if enable_output_filter else '禁用'}, 规则数: {len(self.output_filter_rules)}"
            )
            logger.info(
                f"  保存过滤: {'启用' if enable_save_filter else '禁用'}, 规则数: {len(self.save_filter_rules)}"
            )

    def update_config(
        self,
        enable_output_filter: Optional[bool] = None,
        output_filter_rules: Optional[List[str]] = None,
        enable_save_filter: Optional[bool] = None,
        save_filter_rules: Optional[List[str]] = None,
    ):
        """
        更新过滤配置

        Args:
            enable_output_filter: 是否启用输出过滤
            output_filter_rules: 输出过滤规则列表
            enable_save_filter: 是否启用保存过滤
            save_filter_rules: 保存过滤规则列表
        """
        if enable_output_filter is not None:
            self.enable_output_filter = enable_output_filter
        if output_filter_rules is not None:
            self.output_filter_rules = output_filter_rules
        if enable_save_filter is not None:
            self.enable_save_filter = enable_save_filter
        if save_filter_rules is not None:
            self.save_filter_rules = save_filter_rules

    def process_for_output(self, content: str) -> str:
        """
        处理AI回复用于输出（发送给用户）

        注意：此方法只处理输出过滤，不影响保存内容

        Args:
            content: AI原始回复

        Returns:
            过滤后的内容（用于发送）
        """
        return ContentFilter.filter_for_output(
            content, self.enable_output_filter, self.output_filter_rules
        )

    def process_for_save(self, content: str) -> str:
        """
        处理AI回复用于保存（保存到历史记录）

        注意：此方法只处理保存过滤，不影响输出内容

        Args:
            content: AI原始回复

        Returns:
            过滤后的内容（用于保存）
        """
        return ContentFilter.filter_for_save(
            content, self.enable_save_filter, self.save_filter_rules
        )

    def process_both(self, content: str) -> Tuple[str, str]:
        """
        同时处理输出和保存（返回两个独立的结果）

        这是推荐的使用方式，确保两套过滤逻辑完全独立

        Args:
            content: AI原始回复

        Returns:
            (输出内容, 保存内容) - 两个独立过滤后的结果
        """
        output_content = self.process_for_output(content)
        save_content = self.process_for_save(content)
        return output_content, save_content
