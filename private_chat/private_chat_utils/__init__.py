"""
私信工具模块初始化
导出所有工具类供私信主模块使用

作者: Him666233
版本: v1.2.1
"""

from .private_chat_message_processor import MessageProcessor
from .private_chat_image_handler import ImageHandler
from .private_chat_image_description_cache import ImageDescriptionCache
from .private_chat_context_manager import ContextManager
from .private_chat_reply_handler import ReplyHandler
from .private_chat_memory_injector import MemoryInjector
from .private_chat_tools_reminder import ToolsReminder
from .private_chat_keyword_checker import KeywordChecker
from .private_chat_message_cleaner import MessageCleaner

# v1.0.2 新增功能
from .private_chat_typo_generator import TypoGenerator
from .private_chat_mood_tracker import MoodTracker
from .private_chat_typing_simulator import TypingSimulator

# v1.1.0 新增功能
from .private_chat_proactive_chat_manager import ProactiveChatManager
from .private_chat_time_period_manager import TimePeriodManager

# v1.2.0 新增功能 - 表情检测
from .private_chat_emoji_detector import EmojiDetector

# v1.2.0 新增功能 - 转发消息解析
from .private_chat_forward_message_parser import ForwardMessageParser

# v1.2.0 新增功能 - 内容过滤
from .private_chat_content_filter import ContentFilterManager

# 全局调试日志开关（供各模块统一读取）
DEBUG_MODE: bool = False


def set_debug_mode(enabled: bool) -> None:
    """
    由主插件调用，统一设置调试日志开关
    所有模块应读取 private_chat_utils.DEBUG_MODE 作为最终判定
    """
    global DEBUG_MODE
    DEBUG_MODE = bool(enabled)


__all__ = [
    "MessageProcessor",
    "ImageHandler",
    "ImageDescriptionCache",
    "ContextManager",
    "ReplyHandler",
    "MemoryInjector",
    "ToolsReminder",
    "KeywordChecker",
    "MessageCleaner",
    # v1.0.2 开始的新增
    "TypoGenerator",
    "MoodTracker",
    "TypingSimulator",
    # v1.1.0 开始的新增
    "ProactiveChatManager",
    "TimePeriodManager",
    # v1.2.0 开始的新增
    "EmojiDetector",
    "ForwardMessageParser",
    "ContentFilterManager",
    # 全局调试
    "DEBUG_MODE",
    "set_debug_mode",
]
