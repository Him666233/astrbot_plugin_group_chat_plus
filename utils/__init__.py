"""
工具模块初始化
导出所有工具类供主插件使用

作者: Him666233
版本: v1.0.4
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
]
