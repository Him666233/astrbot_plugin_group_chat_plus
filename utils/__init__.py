"""
工具模块初始化
导出所有工具类供主插件使用

作者: Him666233
版本: v1.1.2
"""

from .probability_manager import ProbabilityManager
from .message_processor import MessageProcessor
from .image_handler import ImageHandler
from .context_manager import ContextManager
from .decision_ai import DecisionAI
from .reply_handler import ReplyHandler
from .memory_injector import MemoryInjector
from .tools_reminder import ToolsReminder
from .keyword_checker import KeywordChecker
from .message_cleaner import MessageCleaner
from .attention_manager import AttentionManager

# v1.0.2 新增功能
from .typo_generator import TypoGenerator
from .mood_tracker import MoodTracker
from .frequency_adjuster import FrequencyAdjuster
from .typing_simulator import TypingSimulator

# v1.1.0 新增功能
from .proactive_chat_manager import ProactiveChatManager
from .time_period_manager import TimePeriodManager

# v1.1.2 新增功能
from .ai_response_filter import AIResponseFilter

# 全局调试日志开关（供各模块统一读取）
DEBUG_MODE: bool = False


def set_debug_mode(enabled: bool) -> None:
    """
    由主插件调用，统一设置调试日志开关
    所有模块应读取 utils.DEBUG_MODE 作为最终判定
    """
    global DEBUG_MODE
    DEBUG_MODE = bool(enabled)


__all__ = [
    "ProbabilityManager",
    "MessageProcessor",
    "ImageHandler",
    "ContextManager",
    "DecisionAI",
    "ReplyHandler",
    "MemoryInjector",
    "ToolsReminder",
    "KeywordChecker",
    "MessageCleaner",
    "AttentionManager",
    # v1.0.2 开始的新增
    "TypoGenerator",
    "MoodTracker",
    "FrequencyAdjuster",
    "TypingSimulator",
    # v1.1.0 开始的新增
    "ProactiveChatManager",
    "TimePeriodManager",
    # v1.1.2 开始的新增
    "AIResponseFilter",
    # 全局调试
    "DEBUG_MODE",
    "set_debug_mode",
]
