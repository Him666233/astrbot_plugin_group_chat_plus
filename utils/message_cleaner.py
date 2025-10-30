"""
消息清理器模块
负责清理消息中的系统提示词，只保留原始用户消息

作者: Him666233
版本: v1.0.3
"""

import re
from astrbot.api.all import *


class MessageCleaner:
    """
    消息清理器

    主要功能：
    1. 移除系统自动添加的@消息提示词
    2. 移除决策AI相关的提示词
    3. 只保留原始用户消息内容
    """

    # @消息提示词的特征模式（用于识别和移除）
    AT_MESSAGE_PROMPT_PATTERNS = [
        r"注意，你正在社交媒体上.*?不要输出其他任何东西",
        r"\[当前时间:.*?\][\s\S]*?不要输出其他任何东西",
        r"用户只是通过@来唤醒你.*?不要输出其他任何东西",
        r"你友好地询问用户想要聊些什么.*?不要输出其他任何东西",
    ]

    # 决策AI提示词的特征模式
    DECISION_AI_PROMPT_PATTERNS = [
        r"=== 历史消息上下文 ===",
        r"=== 当前新消息 ===",
        r"请根据历史消息.*?请开始回复",
        r"你是一个活跃、友好的群聊参与者.*?请开始判断",
    ]

    @staticmethod
    def clean_message(message_text: str) -> str:
        """
        清理消息，移除系统添加的提示词

        Args:
            message_text: 原始消息（可能包含提示词）

        Returns:
            清理后的消息（只包含用户真实发送的内容）
        """
        if not message_text:
            return message_text

        cleaned = message_text

        # 移除@消息提示词
        for pattern in MessageCleaner.AT_MESSAGE_PROMPT_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

        # 移除决策AI提示词
        for pattern in MessageCleaner.DECISION_AI_PROMPT_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

        # 清理多余的空白行
        cleaned = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned)

        # 去除首尾空白
        cleaned = cleaned.strip()

        return cleaned

    @staticmethod
    def extract_raw_message_from_event(event: AstrMessageEvent) -> str:
        """
        从事件中提取纯净的原始消息（不含任何系统添加的内容）

        优先使用message chain来提取，避免获取到系统添加的提示词

        Args:
            event: 消息事件

        Returns:
            原始消息文本
        """
        try:
            # 方法1: 从消息链中提取（最可靠）
            if hasattr(event, "message_obj") and hasattr(event.message_obj, "message"):
                from astrbot.api.message_components import Plain, At, Image, Reply

                raw_parts = []
                for component in event.message_obj.message:
                    if isinstance(component, Plain):
                        # 纯文本组件
                        raw_parts.append(component.text)
                    elif isinstance(component, At):
                        # @组件，保留@标记
                        if hasattr(component, "qq"):
                            raw_parts.append(f"[At:{component.qq}]")
                    elif isinstance(component, Image):
                        # 图片组件，保留图片标记
                        raw_parts.append("[图片]")
                    elif isinstance(component, Reply):
                        # 引用消息组件，提取引用信息
                        reply_text = MessageCleaner._format_reply_component(component)
                        if reply_text:
                            raw_parts.append(reply_text)

                if raw_parts:
                    raw_message = "".join(raw_parts).strip()
                    # 只有当提取到非空消息时才返回
                    if raw_message:
                        logger.debug(
                            f"[消息清理] 从消息链提取原始消息: {raw_message[:100]}..."
                        )
                        return raw_message
                    else:
                        # 提取到空消息，记录警告并继续尝试其他方法
                        logger.warning(
                            f"[消息清理] 方法1提取到空消息！raw_parts={raw_parts[:5]}，尝试方法2"
                        )

            # 方法2: 使用get_message_str（可能包含提示词，需要清理）
            plain_message = event.get_message_str()
            logger.debug(
                f"[消息清理] 方法2: get_message_str()={plain_message[:100] if plain_message else '(空)'}"
            )
            if plain_message:
                cleaned = MessageCleaner.clean_message(plain_message)
                logger.debug(
                    f"[消息清理] 从plain提取并清理: {cleaned[:100] if cleaned else '(空消息)'}..."
                )
                if cleaned:
                    return cleaned
                else:
                    logger.warning("[消息清理] 方法2清理后为空，尝试方法3")

            # 方法3: 使用get_message_outline（最后的备选）
            outline_message = event.get_message_outline()
            logger.debug(
                f"[消息清理] 方法3: get_message_outline()={outline_message[:100] if outline_message else '(空)'}"
            )
            cleaned = MessageCleaner.clean_message(outline_message)
            logger.debug(
                f"[消息清理] 从outline提取并清理: {cleaned[:100] if cleaned else '(空消息)'}..."
            )
            if not cleaned:
                logger.warning(
                    f"[消息清理] 所有方法都返回空消息！event.message_str={event.message_str[:100] if event.message_str else '(空)'}"
                )
            return cleaned

        except Exception as e:
            logger.error(f"[消息清理] 提取原始消息失败: {e}")
            # 发生错误时返回空字符串
            return ""

    @staticmethod
    def _format_reply_component(reply_component) -> str:
        """
        格式化引用消息组件为文本表示

        Args:
            reply_component: Reply组件

        Returns:
            格式化后的引用消息文本
        """
        try:
            # 尝试提取引用的消息内容
            # Reply组件可能包含：sender_name, message_content等字段
            parts = []

            # 尝试获取发送者名称
            sender_name = None
            if hasattr(reply_component, "sender_name"):
                sender_name = reply_component.sender_name
            elif hasattr(reply_component, "sender"):
                if hasattr(reply_component.sender, "nickname"):
                    sender_name = reply_component.sender.nickname

            # 尝试获取消息内容
            message_content = None
            if hasattr(reply_component, "message_str"):
                message_content = reply_component.message_str
            elif hasattr(reply_component, "message"):
                message_content = reply_component.message

            # 构建引用消息格式
            if sender_name and message_content:
                return f"[引用消息({sender_name}: {message_content})]"
            elif message_content:
                return f"[引用消息: {message_content}]"
            else:
                return "[引用消息]"

        except Exception as e:
            logger.debug(f"[消息清理] 格式化引用消息失败: {e}")
            return "[引用消息]"

    @staticmethod
    def is_empty_at_message(raw_message: str, is_at_message: bool) -> bool:
        """
        判断是否是纯@消息（只有@没有其他内容）

        Args:
            raw_message: 原始消息
            is_at_message: 是否是@消息

        Returns:
            True=纯@消息（只有@标记），False=有其他内容
        """
        if not is_at_message:
            return False

        # 移除所有@标记
        without_at = re.sub(r"\[At:\d+\]", "", raw_message)
        # 移除空白字符
        without_at = without_at.strip()

        # 如果移除@后为空，说明是纯@消息
        is_empty = len(without_at) == 0

        if is_empty:
            logger.debug("[消息清理] 检测到纯@消息（无其他内容）")

        return is_empty
