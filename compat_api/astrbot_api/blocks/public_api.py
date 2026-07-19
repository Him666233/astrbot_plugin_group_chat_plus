"""AstrBot 公开 API 与旧路径回退导入。

本文件只负责导出业务代码常用的公开对象；如果公开入口不可用，
再回退到旧版或内部路径，避免业务模块直接散落多套导入写法。
"""

from __future__ import annotations

from typing import Any

from astrbot.api import logger

try:
    from astrbot.api.event import AstrMessageEvent, MessageChain
except Exception:  # pragma: no cover - 兼容旧版 AstrBot 导出结构
    from astrbot.core.message.message_event_result import MessageChain
    from astrbot.core.platform import AstrMessageEvent

try:
    from astrbot.api.provider import LLMResponse, ProviderRequest
except Exception:  # pragma: no cover - 兼容旧版 AstrBot 导出结构
    from astrbot.core.provider.entities import LLMResponse, ProviderRequest

try:
    from astrbot.api.star import Context, Star, StarTools
except Exception:  # pragma: no cover - 兼容旧版 AstrBot 导出结构
    from astrbot.core.star import Context, Star, StarTools

try:
    from astrbot.api.platform import AstrBotMessage, MessageMember, MessageType
except Exception:  # pragma: no cover - 兼容旧版 AstrBot 导出结构
    from astrbot.core.platform import AstrBotMessage, MessageMember, MessageType

try:
    import astrbot.api.message_components as Comp
except Exception:  # pragma: no cover - 兼容旧版 AstrBot 导出结构
    import astrbot.core.message.components as Comp


def _component(name: str) -> Any:
    return getattr(Comp, name, None)


BaseMessageComponent = _component("BaseMessageComponent")
Plain = _component("Plain")
At = _component("At")
AtAll = _component("AtAll")
Image = _component("Image")
Reply = _component("Reply")
Face = _component("Face")
Forward = _component("Forward")
Node = _component("Node")
Nodes = _component("Nodes")
Poke = _component("Poke")
Video = _component("Video")
Record = _component("Record")
File = _component("File")

__all__ = [
    "AstrBotMessage",
    "AstrMessageEvent",
    "At",
    "AtAll",
    "BaseMessageComponent",
    "Comp",
    "Context",
    "Face",
    "File",
    "Forward",
    "Image",
    "LLMResponse",
    "MessageChain",
    "MessageMember",
    "MessageType",
    "Node",
    "Nodes",
    "Plain",
    "Poke",
    "ProviderRequest",
    "Record",
    "Reply",
    "Star",
    "StarTools",
    "Video",
    "logger",
]
