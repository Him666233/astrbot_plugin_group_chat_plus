"""私聊转发消息解析器兼容导出。"""

from astrbot_plugin_group_chat_plus.utils.forward_message_parser import (
    FORWARD_API_CALL_HARD_LIMIT,
    FORWARD_NESTING_HARD_LIMIT,
    ForwardMessageParser,
)

__all__ = [
    "FORWARD_API_CALL_HARD_LIMIT",
    "FORWARD_NESTING_HARD_LIMIT",
    "ForwardMessageParser",
]
