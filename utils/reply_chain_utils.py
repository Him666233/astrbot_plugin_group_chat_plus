"""
引用消息（Reply）链解析工具

背景
----
AstrBot 的 `Reply` 组件有两个内容来源：

1. `Reply.chain`：被引用消息的**原始消息段列表**（如 [Plain, Image, At]），
   由平台适配器在拉取被引用消息时填充。
2. `Reply.message_str`：被引用消息解析后的**纯文本**字符串，只包含文字段。

当被引用消息是「纯图片」（没有任何文字）时 `message_str` 为空字符串。
此时若只看 `message_str`，引用内容就会丢失，表现为
`[引用 >>> 用户(ID:xxx): (无法获取引用内容)]`，AI 也就看不到被引用的图片。

本模块提供统一的 chain 遍历 / 文本渲染工具，供群聊与私信两条链路复用，
避免同一个「下钻 Reply.chain」逻辑在各处重复实现、修一处漏一处。

图片顺序约定
------------
`analyze_chain`（图片检测）、`render_chain_text`（文本渲染）以及调用方
`_extract_image_urls`（图片 URL 提取）**三者都按「展开后的消息链顺序」编号**，
即先顶层、遇到引用时在引用位置插入被引用消息的内容。
只要三者使用同一顺序，引用消息里的图片就能正确对应到自己的描述。

作者: Him666233
版本: V1.2.3.hotfix.2
"""

from typing import Any, Iterator, List, Optional, Tuple

from astrbot.api.message_components import Plain, At, AtAll, Image, Face, Reply

# 尝试导入非文本媒体组件（不同 AstrBot 版本路径可能不同）
try:
    from astrbot.core.message.components import Video, Record, File
except ImportError:
    try:
        from astrbot.api.message_components import Video, Record, File
    except ImportError:
        Video = None
        Record = None
        File = None

# 与 utils/image_handler.py 保持一致：限制递归深度，
# 避免异常平台数据构造出循环引用或超深引用链。
MAX_REPLY_NESTING_DEPTH: int = 3

# 引用内容完全无法还原时的占位文案
UNAVAILABLE_REPLY_CONTENT: str = "(无法获取引用内容)"

# 图片占位标记（未被识别时使用）
IMAGE_PLACEHOLDER: str = "[图片]"


def _coerce_plain_text(value: Any) -> str:
    """把 Plain.text 安全转成字符串（部分平台可能给出 None）。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def get_reply_chain(component: Any) -> List[Any]:
    """安全获取 Reply 组件内嵌的原始消息链。"""
    chain = getattr(component, "chain", None)
    if isinstance(chain, (list, tuple)):
        return list(chain)
    return []


def iter_chain(
    chain: List[Any],
    max_depth: int = MAX_REPLY_NESTING_DEPTH,
) -> Iterator[Tuple[Any, int]]:
    """按顺序展开消息链，遇到 Reply 组件时递归展开其 chain。

    Reply 组件自身也会被产出，因此调用方可以区分「引用本身」与「引用内的段」。

    Args:
        chain: 消息链
        max_depth: 最大递归深度，超过时不再下钻（但仍产出 Reply 自身）

    Yields:
        (component, depth)：组件与其所在引用层级（顶层为 0）
    """

    def _walk(components: List[Any], depth: int) -> Iterator[Tuple[Any, int]]:
        for component in components or []:
            yield component, depth
            if isinstance(component, Reply) and depth < max_depth:
                yield from _walk(get_reply_chain(component), depth + 1)

    yield from _walk(chain, 0)


def _legacy_reply_text(reply_component: Any) -> Optional[str]:
    """读取旧字段（message_str / message）中的引用正文文本。"""
    for attr in ("message_str", "message"):
        value = getattr(reply_component, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def format_reply_component(
    reply_component: Any,
    self_id: Any = None,
    content: Optional[str] = None,
) -> str:
    """把引用组件格式化为 `[引用 >>> 发送者(你)(ID:xxx): 正文]`。

    Args:
        reply_component: Reply 组件
        self_id: 机器人自身 ID，用于给「引用自己的消息」加 (你) 标记
        content: 已解析好的正文文本；为 None 时由 :func:`resolve_reply_content` 解析
    """
    sender_id = getattr(reply_component, "sender_id", None)
    sender_nickname = (
        getattr(reply_component, "sender_nickname", None)
        or getattr(reply_component, "sender_name", None)
    )
    if not sender_nickname and hasattr(reply_component, "sender"):
        sender_nickname = getattr(reply_component.sender, "nickname", None)

    # 部分平台把 sender_nickname 直接填成了 sender_id，此时视为没有昵称
    if sender_nickname and sender_id and str(sender_nickname) == str(sender_id):
        sender_nickname = None

    is_self = self_id and sender_id and str(sender_id) == str(self_id)
    self_suffix = "(你)" if is_self else ""

    if content is None:
        content = resolve_reply_content(reply_component)

    if content:
        if sender_nickname and sender_id:
            return f"[引用 >>> {sender_nickname}{self_suffix}(ID:{sender_id}): {content}]"
        if sender_id:
            return f"[引用 >>> 未知用户{self_suffix}(ID:{sender_id}): {content}]"
        if sender_nickname:
            return f"[引用 >>> {sender_nickname}{self_suffix}: {content}]"
        return f"[引用 >>> {content}]"

    # 内容无法还原：保留引用框架，至少让 AI 知道「这里有一条引用」
    if sender_nickname and sender_id:
        return (
            f"[引用 >>> {sender_nickname}{self_suffix}(ID:{sender_id}): "
            f"{UNAVAILABLE_REPLY_CONTENT}]"
        )
    if sender_id:
        return (
            f"[引用 >>> 未知用户{self_suffix}(ID:{sender_id}): "
            f"{UNAVAILABLE_REPLY_CONTENT}]"
        )
    if sender_nickname:
        return f"[引用 >>> {sender_nickname}{self_suffix}: {UNAVAILABLE_REPLY_CONTENT}]"
    return ""


def resolve_reply_content(
    reply_component: Any,
    max_depth: int = MAX_REPLY_NESTING_DEPTH,
) -> Optional[str]:
    """还原被引用消息的正文文本。

    优先使用结构化 `chain`（被引用消息是纯图片时 `message_str` 为空，
    只有 chain 里才有 Image 段）；chain 不可用时回退到 `message_str`。

    Returns:
        正文文本（图片渲染为 `[图片]`）；完全无法还原时返回 None。
    """
    reply_chain = get_reply_chain(reply_component)
    if reply_chain:
        rendered = render_chain_text(
            reply_chain,
            max_depth=max(0, max_depth - 1),
        ).strip()
        if rendered:
            return rendered
    return _legacy_reply_text(reply_component)


def render_chain_text(
    chain: List[Any],
    self_id: Any = None,
    image_placeholder: str = IMAGE_PLACEHOLDER,
    image_descriptions: Optional[dict] = None,
    max_depth: int = MAX_REPLY_NESTING_DEPTH,
) -> str:
    """把消息链渲染为纯文本（媒体渲染为占位标记，可选用识别结果替换）。

    与 `ImageHandler._render_message_chain` 的输出格式保持一致。

    Args:
        chain: 消息链
        self_id: 机器人自身 ID（用于引用里的 (你) 标记）
        image_placeholder: 图片未被识别时的占位标记
        image_descriptions: {图片序号: 描述}，序号按展开后的消息链顺序编号
        max_depth: 最大递归深度

    Returns:
        渲染后的文本
    """
    image_index = [0]

    def _render(components: List[Any], depth: int) -> str:
        buffer: List[str] = []
        for component in components or []:
            if isinstance(component, Plain):
                buffer.append(_coerce_plain_text(component.text))
            elif isinstance(component, Image):
                idx = image_index[0]
                image_index[0] += 1
                description = (image_descriptions or {}).get(idx)
                buffer.append(
                    f"[图片内容: {description}]" if description else image_placeholder
                )
            elif isinstance(component, At):
                buffer.append(f"[At:{getattr(component, 'qq', '')}]")
            elif isinstance(component, AtAll):
                buffer.append("[At:all]")
            elif isinstance(component, Face):
                buffer.append(f"[表情:{getattr(component, 'id', '')}]")
            elif isinstance(component, Reply):
                nested = ""
                if depth < max_depth:
                    nested = _render(get_reply_chain(component), depth + 1).strip()
                if not nested:
                    nested = _legacy_reply_text(component) or ""
                formatted = format_reply_component(
                    component, self_id=self_id, content=nested
                )
                if formatted:
                    buffer.append(formatted)
            elif Video is not None and isinstance(component, Video):
                buffer.append("[视频]")
            elif Record is not None and isinstance(component, Record):
                buffer.append("[语音]")
            elif File is not None and isinstance(component, File):
                file_name = getattr(component, "name", "") or ""
                buffer.append(f"[文件: {file_name}]" if file_name else "[文件]")
        return "".join(buffer)

    return _render(chain, 0)


def analyze_chain(
    chain: List[Any],
    max_depth: int = MAX_REPLY_NESTING_DEPTH,
    media_as_text: bool = True,
) -> Tuple[bool, bool, List[Any]]:
    """分析消息链中的图片与文字（递归下钻 Reply.chain）。

    Reply 组件本身视为「有内容」，避免「引用 + 图片」被当成纯图片丢弃。

    Args:
        chain: 消息链
        max_depth: 最大递归深度
        media_as_text: 视频/语音/文件是否视为「有内容」。群聊链路传 True
            （与 `ImageHandler._analyze_message` 一致）；私信链路传 False
            以保持原有语义不变。

    Returns:
        (是否有图片, 是否有文字, 图片组件列表)
    """
    has_image = False
    has_text = False
    image_components: List[Any] = []

    for component, _depth in iter_chain(chain, max_depth):
        if isinstance(component, Image):
            has_image = True
            image_components.append(component)
        elif isinstance(component, Plain):
            if _coerce_plain_text(component.text).strip():
                has_text = True
        elif isinstance(component, Reply):
            has_text = True
        elif media_as_text:
            if Video is not None and isinstance(component, Video):
                has_text = True
            elif Record is not None and isinstance(component, Record):
                has_text = True
            elif File is not None and isinstance(component, File):
                has_text = True

    return has_image, has_text, image_components


def has_image_in_chain(
    chain: List[Any], max_depth: int = MAX_REPLY_NESTING_DEPTH
) -> bool:
    """消息链中是否存在图片（含被引用消息里的图片）。"""
    return analyze_chain(chain, max_depth)[0]
