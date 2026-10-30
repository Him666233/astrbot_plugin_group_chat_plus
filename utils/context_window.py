"""缓存友好的上下文窗口（块锚定截断）。

问题
----
原实现每轮取 ``history_messages[-max_context:]``。列表是持续增长的，所以
新消息一进来，窗口起点就跟着往前挪一条 —— 发给模型的 prompt 前缀每轮都变。
对支持前缀缓存的供应商（DeepSeek / Anthropic / OpenAI 等），前缀一变，
缓存从断点起全部失效，只有 system prompt 那一小段还能命中。

实测（生产环境，单群 80 条上下文）：缓存命中恒为 6144 token、十次请求方差为零，
两次请求的共同前缀只有 100 个字符（正好是历史块那段固定说明），
而历史正文每轮全额付费。

做法
----
把窗口起点钉在一条具体消息上（"锚点"）：

1. 记住窗口首条消息的稳定键；
2. 下一轮在新列表里把这条消息找回来，窗口从它开始；
3. 只有当新消息多到超出上限时，才按 ``block`` 整数倍整体前移一次；
4. 两次前移之间是**纯尾部追加** —— 这正是前缀缓存最想要的形态。

代价：窗口长度不再恒定，会在 ``limit - block + 1`` 到 ``limit`` 之间浮动。

关闭方式
--------
``block <= 0`` 时本模块直接返回原列表，调用方应退回旧的
``history_messages[-limit:]`` 行为。默认关闭，保证老部署行为不变。
"""

from __future__ import annotations

from typing import Any, Dict, List, NamedTuple, Tuple

AnchorKey = Tuple


class WindowResult(NamedTuple):
    """一次块锚定计算的结果。"""

    window: List[Any]
    """截断后的窗口。"""

    start: int
    """窗口在输入列表中的起始下标。"""

    advanced: int
    """本次前移了几个块（0 表示锚点未动）。"""

    anchor_found: bool
    """是否在输入列表里找回了上一轮的锚点。"""


def message_key(msg: Any) -> AnchorKey:
    """给消息算一个跨轮稳定的键，用来在下一轮重新找到同一条消息。

    优先用 ``message_id``；缓存消息的 id 形如 ``cached_<ts>``，同一条消息
    被重新组装后 id 会变，所以这类消息退化为「内容 + 时间 + 发送者」指纹。
    """
    mid = getattr(msg, "message_id", None)
    if mid and not str(mid).startswith("cached_"):
        return ("id", str(mid))
    sender = getattr(getattr(msg, "sender", None), "user_id", "") or ""
    return (
        "c",
        str(getattr(msg, "message_str", "") or "")[:32],
        int(getattr(msg, "timestamp", 0) or 0),
        str(sender),
    )


def anchored_window(
    chat_id: str,
    messages: List[Any],
    limit: int,
    block: int,
    anchors: Dict[str, AnchorKey],
) -> WindowResult:
    """按块锚定取窗口。

    Args:
        chat_id: 会话标识，锚点按它分开存（多群互不影响）。
        messages: 已按时间排序的完整消息列表。
        limit: 窗口上限（条）。
        block: 一次前移多少条；``<= 0`` 表示关闭锚定。
        anchors: 锚点存储（会被就地更新）。

    Returns:
        ``WindowResult``。``block <= 0`` 或列表未超限时，``window`` 就是入参本身。
    """
    if not messages or not isinstance(limit, int) or limit <= 0:
        return WindowResult(messages, 0, 0, False)

    if block <= 0 or len(messages) <= limit:
        # 关闭锚定，或还没到上限：原样返回，不动锚点
        return WindowResult(messages, 0, 0, False)

    # 保护：block 逼近 limit 时会把窗口挤成个位数。
    # 例如 limit=80、block=80，前移一次后窗口只剩 1 条 —— 等于把上下文砍没了。
    # 夹到上限的一半，保证窗口长度至少还有 limit/2。
    if block > limit // 2:
        block = max(1, limit // 2)

    start = len(messages) - limit  # 兜底：找不到锚点就退回末尾窗口

    anchor = anchors.get(chat_id)
    anchor_found = False
    if anchor is not None:
        for i, msg in enumerate(messages):
            if message_key(msg) == anchor:
                start = i
                anchor_found = True
                break

    advanced = 0
    while len(messages) - start > limit:
        start += block
        advanced += 1

    if start >= len(messages) or start < 0:
        # 兜底路径：锚点算出来的位置不合法，重来
        start = max(0, len(messages) - limit)
        advanced = 0
        anchor_found = False

    anchors[chat_id] = message_key(messages[start])
    return WindowResult(messages[start:], start, advanced, anchor_found)


def clear_anchors(anchors: Dict[str, AnchorKey]) -> None:
    """清空锚点（重置会话或插件重载时用）。"""
    anchors.clear()
