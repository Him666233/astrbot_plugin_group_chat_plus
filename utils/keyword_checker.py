"""
关键词检查工具
负责检查消息中的触发关键词和黑名单关键词

作者: Him666233
版本: v1.0.0
"""

from astrbot.api.all import *


class KeywordChecker:
    """关键词检查工具类"""

    @staticmethod
    def check_trigger_keywords(event: AstrMessageEvent, keywords: list) -> bool:
        """
        检查消息是否包含触发关键词

        Args:
            event: 消息事件
            keywords: 触发关键词列表

        Returns:
            True=包含，False=不包含
        """
        if not keywords:
            return False

        try:
            # 获取消息文本（参考SpectreCore的实现）
            message_text = event.get_message_outline()

            # 检查是否包含关键词
            for keyword in keywords:
                if keyword and keyword in message_text:
                    logger.debug(f"检测到触发关键词: {keyword}")
                    return True

            return False

        except Exception as e:
            logger.error(f"检查触发关键词时发生错误: {e}")
            return False

    @staticmethod
    def check_blacklist_keywords(event: AstrMessageEvent, keywords: list) -> bool:
        """
        检查消息是否包含黑名单关键词

        Args:
            event: 消息事件
            keywords: 黑名单关键词列表

        Returns:
            True=包含，False=不包含
        """
        if not keywords:
            return False

        try:
            # 获取消息文本
            message_text = event.get_message_outline()

            # 检查是否包含黑名单关键词
            for keyword in keywords:
                if keyword and keyword in message_text:
                    logger.debug(f"检测到黑名单关键词: {keyword}")
                    return True

            return False

        except Exception as e:
            logger.error(f"检查黑名单关键词时发生错误: {e}")
            return False
