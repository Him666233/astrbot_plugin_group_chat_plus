"""
转发消息解析器 - Forward Message Parser

将 QQ 合并转发消息解析为可读纯文本，支持嵌套转发。

工作原理：
1. 检测消息链中的 Forward 组件
2. 通过 OneBot get_forward_msg API 获取实际转发内容
3. 递归解析节点（支持嵌套转发）
4. 格式化为可读纯文本并替换消息链

支持平台：aiocqhttp (OneBot v11) - 需配合 NapCat、Lagrange 等 OneBot 实现
其他平台：自动跳过，不影响正常使用

所有配置通过方法参数传入，本模块不直接读取任何配置。
"""

import json
import time
from datetime import datetime
from typing import Any, Optional

from astrbot.api import logger
from astrbot.core.message.components import (
    At,
    AtAll,
    Face,
    File,
    Forward,
    Image,
    Node,
    Nodes,
    Plain,
    Record,
    Reply,
    Video,
)
from astrbot.core.platform.astr_message_event import AstrMessageEvent


FORWARD_NESTING_HARD_LIMIT = 10
FORWARD_API_CALL_HARD_LIMIT = 30


class ForwardMessageParser:
    """转发消息解析器 - 将转发消息解析为可读纯文本"""

    @staticmethod
    async def try_parse_and_replace(
        event: AstrMessageEvent,
        include_sender_info: bool,
        include_timestamp: bool,
        max_nesting_depth: int = 3,
        debug_mode: bool = False,
    ) -> bool:
        try:
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return False
            message_chain = event.message_obj.message
            if not message_chain:
                return False

            forward_indices = []
            for i, component in enumerate(message_chain):
                if isinstance(component, Forward):
                    forward_indices.append(i)

            if not forward_indices:
                return False

            if debug_mode:
                logger.info(f"[转发消息] 检测到 {len(forward_indices)} 个转发消息组件")

            call_action = _get_call_action(event)
            if call_action is None:
                if debug_mode:
                    logger.info(
                        "[转发消息] 当前平台不支持 get_forward_msg API，跳过解析"
                    )
                return False

            effective_max_depth = min(
                max(max_nesting_depth, 0), FORWARD_NESTING_HARD_LIMIT
            )
            parse_context = _create_parse_context()

            forwarder_name = event.get_sender_name() or ""
            forwarder_id = event.get_sender_id() or ""
            event_timestamp = getattr(event.message_obj, "timestamp", 0) or int(
                time.time()
            )

            any_parsed = False

            for idx in reversed(forward_indices):
                forward_comp = message_chain[idx]
                forward_id = getattr(forward_comp, "id", None)
                if not forward_id:
                    if debug_mode:
                        logger.info("[转发消息] Forward 组件无 id 字段，跳过")
                    continue

                if debug_mode:
                    logger.info(f"[转发消息] 正在获取转发内容，ID: {forward_id}")

                nodes = await _get_forward_nodes_by_id(
                    call_action,
                    str(forward_id),
                    parse_context,
                    debug_mode,
                )

                if nodes is None:
                    logger.warning(
                        f"[转发消息] 获取转发内容失败，forward_id={forward_id}，"
                        "已替换为占位标识"
                    )
                    placeholder = _build_header(
                        "[转发消息]（内容获取失败）",
                        forwarder_name,
                        forwarder_id,
                        event_timestamp,
                        include_sender_info,
                        include_timestamp,
                        is_nested=False,
                    )
                    message_chain[idx] = Plain(text=placeholder)
                    any_parsed = True
                    continue

                formatted_text = await _format_forward_message(
                    nodes=nodes,
                    call_action=call_action,
                    forwarder_name=forwarder_name,
                    forwarder_id=forwarder_id,
                    event_timestamp=event_timestamp,
                    include_sender_info=include_sender_info,
                    include_timestamp=include_timestamp,
                    max_nesting_depth=effective_max_depth,
                    parse_context=parse_context,
                    depth=0,
                    debug_mode=debug_mode,
                )

                message_chain[idx] = Plain(text=formatted_text)
                any_parsed = True

                if debug_mode:
                    logger.info(
                        f"[转发消息] 已解析转发消息（{len(nodes)} 条节点），"
                        f"API 调用次数: {parse_context['api_call_count']}"
                    )

            if any_parsed:
                new_str_parts = []
                for comp in message_chain:
                    if isinstance(comp, Plain):
                        if comp.text is not None:
                            new_str_parts.append(str(comp.text))
                    else:
                        new_str_parts.append(f"[{getattr(comp, 'type', 'Unknown')}]")
                event.message_obj.message_str = " ".join(new_str_parts)
                event.message_str = event.message_obj.message_str

            return any_parsed

        except Exception as e:
            logger.warning(f"[转发消息] 解析转发消息时发生异常（已跳过）: {e}")
            return False


def _create_parse_context() -> dict[str, Any]:
    return {
        "api_call_count": 0,
        "active_forward_ids": set(),
        "forward_cache": {},
        "message_cache": {},
    }


def _get_call_action(event: AstrMessageEvent):
    try:
        bot = getattr(event, "bot", None)
        if bot is None:
            return None
        call_action = getattr(bot, "call_action", None)
        if callable(call_action):
            return call_action
        api = getattr(bot, "api", None)
        if api is not None:
            call_action = getattr(api, "call_action", None)
            if callable(call_action):
                return call_action
        return None
    except Exception:
        return None


async def _get_forward_nodes_by_id(
    call_action,
    forward_id: str,
    parse_context: dict[str, Any],
    debug_mode: bool = False,
) -> Optional[list]:
    forward_id_str = str(forward_id).strip()
    if not forward_id_str:
        return None

    forward_cache = parse_context["forward_cache"]
    if forward_id_str in forward_cache:
        if debug_mode:
            logger.debug(f"[转发消息] 命中转发缓存，ID: {forward_id_str}")
        return forward_cache[forward_id_str]

    if parse_context["api_call_count"] >= FORWARD_API_CALL_HARD_LIMIT:
        if debug_mode:
            logger.debug(
                f"[转发消息] API 调用次数已达上限，跳过获取转发内容，ID: {forward_id_str}"
            )
        forward_cache[forward_id_str] = None
        return None

    parse_context["api_call_count"] += 1
    nodes = await _fetch_forward_nodes(call_action, forward_id_str, debug_mode)
    forward_cache[forward_id_str] = nodes
    return nodes


async def _fetch_forward_nodes(
    call_action,
    forward_id: str,
    debug_mode: bool = False,
) -> Optional[list]:
    params_list = [
        {"message_id": forward_id},
        {"id": forward_id},
    ]
    forward_id_str = str(forward_id).strip()
    if forward_id_str.isdigit():
        int_id = int(forward_id_str)
        params_list.extend(
            [
                {"message_id": int_id},
                {"id": int_id},
            ]
        )

    for params in params_list:
        try:
            result = await call_action("get_forward_msg", **params)
            nodes = _extract_nodes_from_response(result)
            if nodes is not None:
                return nodes
        except Exception as e:
            if debug_mode:
                logger.debug(f"[转发消息] get_forward_msg 参数 {params} 失败: {e}")
            continue

    # get_forward_msg failed — try get_msg as fallback.
    # Nested forward IDs are often regular message IDs, not forward resource IDs.
    for params in params_list:
        try:
            result = await call_action("get_msg", **params)
            if isinstance(result, dict):
                data = (
                    result.get("data")
                    if isinstance(result.get("data"), dict)
                    else result
                )
                message = data.get("message")
                if isinstance(message, list):
                    sender = data.get("sender", {})
                    msg_time = data.get("time", 0)
                    return [{"sender": sender, "time": msg_time, "message": message}]
        except Exception:
            continue

    if debug_mode:
        logger.debug(
            f"[转发消息] 所有 get_forward_msg / get_msg 尝试均失败，forward_id={forward_id}（将尝试 inline fallback）"
        )
    return None


def _extract_nodes_from_response(response: Any) -> Optional[list]:
    if isinstance(response, list) and len(response) > 0:
        return _coerce_inline_nodes_list(response)

    if isinstance(response, str):
        parsed = _safe_json_loads(response)
        if parsed is not None:
            return _extract_nodes_from_response(parsed)
        return None

    if not isinstance(response, dict):
        return None

    data = response.get("data")
    if isinstance(data, list) and len(data) > 0:
        return _coerce_inline_nodes_list(data)

    for target in (data, response):
        if not isinstance(target, dict):
            continue
        target_type = str(target.get("type", "")).lower()
        if target_type == "node":
            return [target]
        for key in ("messages", "message", "nodes", "nodeList", "content"):
            nodes = target.get(key)
            if isinstance(nodes, list) and len(nodes) > 0:
                return _coerce_inline_nodes_list(nodes, target)
        if target_type == "nodes":
            nested_data = target.get("data")
            if isinstance(nested_data, dict):
                nested_nodes = _extract_inline_nodes_from_forward_segment(nested_data)
                if nested_nodes is not None:
                    return nested_nodes

    return None


async def _format_forward_message(
    nodes: list,
    call_action,
    forwarder_name: str,
    forwarder_id: str,
    event_timestamp: int,
    include_sender_info: bool,
    include_timestamp: bool,
    max_nesting_depth: int,
    parse_context: dict[str, Any],
    depth: int = 0,
    debug_mode: bool = False,
) -> str:
    indent = "  " * depth
    is_nested = depth > 0

    label = "[嵌套转发消息]" if is_nested else "[转发消息]"
    header = _build_header(
        label,
        forwarder_name,
        forwarder_id,
        event_timestamp,
        include_sender_info,
        include_timestamp,
        is_nested=is_nested,
    )

    sep_label = "嵌套转发" if is_nested else "转发"
    sep_start = f"{indent}--- {sep_label}内容 ---"
    sep_end = f"{indent}--- {sep_label}结束 ---"

    body_lines = []
    for node in nodes:
        normalized_input = _coerce_forward_node(node)
        if not isinstance(normalized_input, dict):
            continue
        try:
            node_text = await _format_single_node(
                node=normalized_input,
                call_action=call_action,
                include_sender_info=include_sender_info,
                include_timestamp=include_timestamp,
                max_nesting_depth=max_nesting_depth,
                parse_context=parse_context,
                depth=depth,
                indent=indent,
                debug_mode=debug_mode,
            )
            if node_text:
                body_lines.append(node_text)
        except Exception as e:
            if debug_mode:
                logger.debug(f"[转发消息] 解析节点失败（跳过）: {e}")
            continue

    if not body_lines:
        return f"{indent}{header}\n{sep_start}\n{indent}（转发内容为空或解析失败）\n{sep_end}"

    body = "\n".join(body_lines)
    return f"{indent}{header}\n{sep_start}\n{body}\n{sep_end}"


def _coerce_forward_node(node: Any) -> Optional[dict[str, Any]]:
    if isinstance(node, dict):
        return node
    if isinstance(node, Node):
        return {
            "sender": {
                "nickname": getattr(node, "name", "") or "",
                "user_id": getattr(node, "uin", "") or "",
            },
            "time": getattr(node, "time", 0) or 0,
            "message": list(getattr(node, "content", []) or []),
        }
    return None


def _build_header(
    label: str,
    forwarder_name: str,
    forwarder_id: str,
    timestamp: int,
    include_sender_info: bool,
    include_timestamp: bool,
    is_nested: bool = False,
) -> str:
    parts = []

    if include_timestamp and timestamp and timestamp > 0:
        time_str = _format_timestamp(timestamp)
        if time_str:
            parts.append(f"[{time_str}]")

    parts.append(label)

    if include_sender_info and (forwarder_name or forwarder_id):
        display_name = (
            forwarder_name
            if (forwarder_name and forwarder_name != str(forwarder_id))
            else ""
        )
        if display_name:
            sender_str = (
                f"{display_name}(ID:{forwarder_id})" if forwarder_id else display_name
            )
        elif forwarder_id:
            sender_str = f"未知用户(ID:{forwarder_id})"
        else:
            sender_str = "未知用户"
        parts.append(f"由 {sender_str} 转发的消息：")
    else:
        parts.append("：")

    return " ".join(parts)


async def _format_single_node(
    node: dict,
    call_action,
    include_sender_info: bool,
    include_timestamp: bool,
    max_nesting_depth: int,
    parse_context: dict[str, Any],
    depth: int,
    indent: str,
    debug_mode: bool = False,
) -> Optional[str]:
    normalized_node = _normalize_forward_node(node)
    sender_name = normalized_node["sender_name"]
    sender_id = normalized_node["sender_id"]
    sender_role = normalized_node.get("sender_role", "")  # 🆕
    node_time = normalized_node["timestamp"]
    segments = normalized_node["segments"]

    main_text = await _format_segments_text(
        segments=segments,
        call_action=call_action,
        include_sender_info=include_sender_info,
        include_timestamp=include_timestamp,
        max_nesting_depth=max_nesting_depth,
        parse_context=parse_context,
        depth=depth,
        current_sender_name=sender_name,
        current_sender_id=sender_id,
        current_time=node_time,
        debug_mode=debug_mode,
    )
    main_text = main_text.strip()

    line_prefix_parts = []
    if include_timestamp and node_time and node_time > 0:
        time_str = _format_timestamp(node_time)
        if time_str:
            line_prefix_parts.append(f"[{time_str}]")
    if include_sender_info and (sender_name or sender_id):
        display_name = (
            sender_name if (sender_name and sender_name != str(sender_id)) else ""
        )
        if display_name:
            sender_part = (
                f"{display_name}(ID:{sender_id})" if sender_id else f"{display_name}"
            )
        elif sender_id:
            sender_part = f"未知用户(ID:{sender_id})"
        else:
            sender_part = "未知用户"
        # 🆕 追加群角色标签
        if sender_role and sender_role.strip():
            sender_part += f"[{sender_role.strip()}]"
        line_prefix_parts.append(f"{sender_part}:")
    line_prefix = " ".join(line_prefix_parts)

    result_parts = []

    if main_text:
        if line_prefix:
            result_parts.append(f"{indent}{line_prefix} {main_text}")
        else:
            result_parts.append(f"{indent}{main_text}")

    if not result_parts:
        return None

    return "\n".join(result_parts)


async def _format_segments_text(
    segments: list,
    call_action,
    include_sender_info: bool,
    include_timestamp: bool,
    max_nesting_depth: int,
    parse_context: dict[str, Any],
    depth: int,
    current_sender_name: str,
    current_sender_id: str,
    current_time: int,
    debug_mode: bool = False,
) -> str:
    parts: list[str] = []

    for seg in segments:
        try:
            seg_type, seg_data = _normalize_segment_for_format(seg)
            if not seg_type:
                continue

            if seg_type in ("text", "plain"):
                text = _first_text_content(seg_data, ("text", "content", "message"))
                if text:
                    parts.append(str(text))
            elif seg_type == "image":
                image_text = _format_media_segment(
                    "图片",
                    seg_data,
                    ("url", "file", "path", "file_id", "image_id", "id", "md5"),
                    failure_placeholder="[图片（识别失败）]",
                )
                if _is_emoji_image_segment(seg_data):
                    image_text = f"[表情包图片]{image_text}"
                parts.append(image_text)
            elif seg_type == "video":
                parts.append(
                    _format_media_segment(
                        "视频",
                        seg_data,
                        ("url", "file", "path", "file_id", "video_id", "id"),
                        failure_placeholder="[视频（识别失败）]",
                    )
                )
            elif seg_type in ("record", "audio", "voice"):
                parts.append(
                    _format_media_segment(
                        "语音",
                        seg_data,
                        ("url", "file", "path", "file_id", "audio_id", "id"),
                        failure_placeholder="[语音（识别失败）]",
                    )
                )
            elif seg_type == "file":
                parts.append(_format_file_segment(seg_data))
            elif seg_type == "face":
                face_id = _first_non_empty(seg_data, ("id", "face_id"))
                parts.append(f"[表情:{face_id}]" if face_id else "[表情]")
            elif seg_type == "at":
                parts.append(_format_at_segment(seg_data))
            elif seg_type == "reply":
                reply_text = await _format_reply_segment(
                    seg_data=seg_data,
                    call_action=call_action,
                    include_sender_info=include_sender_info,
                    include_timestamp=include_timestamp,
                    max_nesting_depth=max_nesting_depth,
                    parse_context=parse_context,
                    depth=depth,
                    debug_mode=debug_mode,
                )
                if reply_text:
                    parts.append(reply_text)
            elif seg_type in ("forward", "forward_msg", "nodes", "node"):
                nested_seg_data = (
                    {"content": [{"type": "node", "data": seg_data}]}
                    if seg_type == "node"
                    else seg_data
                )
                nested_text = await _handle_nested_forward_segment(
                    seg_data=nested_seg_data,
                    call_action=call_action,
                    node_sender_name=current_sender_name,
                    node_sender_id=current_sender_id,
                    node_time=current_time,
                    include_sender_info=include_sender_info,
                    include_timestamp=include_timestamp,
                    max_nesting_depth=max_nesting_depth,
                    parse_context=parse_context,
                    depth=depth,
                    debug_mode=debug_mode,
                )
                if nested_text:
                    _append_block_part(parts, nested_text)
            elif seg_type == "json":
                raw_json = _first_non_empty(seg_data, ("data", "json", "content"))
                if isinstance(raw_json, str) and raw_json.strip():
                    multimsg_text = _try_parse_multimsg_json(raw_json)
                    if multimsg_text:
                        _append_block_part(parts, f"[转发消息预览]\n{multimsg_text}")
                    else:
                        parts.append(_format_generic_segment("JSON消息", seg_data))
                else:
                    parts.append("[JSON消息]")
            elif seg_type == "xml":
                parts.append(_format_generic_segment("XML消息", seg_data))
            elif seg_type in ("share", "music", "contact", "location"):
                parts.append(_format_named_structured_segment(seg_type, seg_data))
            else:
                parts.append(_format_generic_segment(seg_type, seg_data))
        except Exception as e:
            if debug_mode:
                logger.debug(f"[转发消息] 解析消息段失败（已用占位替代）: {e}")
            placeholder = _fallback_placeholder_for_segment(seg)
            if placeholder:
                parts.append(placeholder)

    return "".join(parts)


def _append_block_part(parts: list[str], block_text: str) -> None:
    block_text = (block_text or "").strip()
    if not block_text:
        return
    if parts and not parts[-1].endswith("\n"):
        parts.append("\n")
    parts.append(block_text)
    parts.append("\n")


def _normalize_segment_for_format(seg: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(seg, dict):
        seg_type = str(seg.get("type", "") or "").lower()
        raw_data = seg.get("data")
        if isinstance(raw_data, dict):
            seg_data = dict(raw_data)
        elif raw_data is not None:
            seg_data = {"data": raw_data}
        else:
            seg_data = {
                key: value
                for key, value in seg.items()
                if key not in ("type", "data")
            }
        return seg_type, seg_data

    if isinstance(seg, Plain):
        return "text", {"text": seg.text}
    if isinstance(seg, AtAll):
        return "at", {"qq": "all", "name": "全体成员"}
    if isinstance(seg, At):
        return "at", {"qq": getattr(seg, "qq", ""), "name": getattr(seg, "name", "")}
    if isinstance(seg, Face):
        return "face", {"id": getattr(seg, "id", "")}
    if isinstance(seg, Image):
        return "image", _component_data(
            seg,
            (
                "url",
                "file",
                "path",
                "_type",
                "subType",
                "sub_type",
                "summary",
                "imageType",
                "image_type",
            ),
        )
    if isinstance(seg, Video):
        return "video", _component_data(seg, ("url", "file", "path", "cover"))
    if isinstance(seg, Record):
        return "record", _component_data(seg, ("url", "file", "path", "text"))
    if isinstance(seg, File):
        return "file", _component_data(seg, ("name", "file_", "url"))
    if isinstance(seg, Reply):
        return "reply", _component_data(
            seg,
            ("id", "chain", "sender_id", "sender_nickname", "time", "message_str"),
        )
    if isinstance(seg, Forward):
        return "forward", {"id": getattr(seg, "id", "")}
    if isinstance(seg, Node):
        return "node", {
            "user_id": getattr(seg, "uin", "") or "",
            "nickname": getattr(seg, "name", "") or "",
            "time": getattr(seg, "time", 0) or 0,
            "content": list(getattr(seg, "content", []) or []),
        }
    if isinstance(seg, Nodes):
        return "nodes", {"content": list(getattr(seg, "nodes", []) or [])}

    seg_type = str(getattr(seg, "type", "") or "")
    if "." in seg_type:
        seg_type = seg_type.rsplit(".", 1)[-1]
    return seg_type.lower(), _component_data(seg)


def _component_data(component: Any, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    if keys is None:
        keys = (
            "text",
            "qq",
            "name",
            "nickname",
            "id",
            "message_id",
            "user_id",
            "file_",
            "file",
            "url",
            "path",
            "content",
            "message",
            "chain",
            "sender_id",
            "sender_nickname",
            "time",
        )

    data: dict[str, Any] = {}
    for key in keys:
        if not hasattr(component, key):
            continue
        try:
            value = getattr(component, key)
        except Exception:
            continue
        if value is not None and value != "":
            data[key] = value
    return data


def _format_media_segment(
    label: str,
    seg_data: dict[str, Any],
    ref_keys: tuple[str, ...],
    failure_placeholder: str | None = None,
) -> str:
    ref = _first_non_empty(seg_data, ref_keys)
    if ref:
        return f"[{label}: {_safe_ref_text(ref)}]"

    raw_info = _compact_raw_data(seg_data)
    if failure_placeholder:
        if raw_info:
            return f"{failure_placeholder[:-1]}: {raw_info}]"
        return failure_placeholder
    if raw_info:
        return f"[{label}: {raw_info}]"
    return f"[{label}]"


def _is_emoji_image_segment(seg_data: dict[str, Any]) -> bool:
    if not isinstance(seg_data, dict):
        return False

    sub_type = seg_data.get("sub_type")
    if sub_type is None:
        sub_type = seg_data.get("subType")
    try:
        if sub_type == 1 or sub_type == "1" or int(sub_type) == 1:
            return True
    except Exception:
        pass

    summary = str(seg_data.get("summary") or "").strip()
    summary_lower = summary.lower()
    if "表情" in summary or "emoji" in summary_lower or "sticker" in summary_lower:
        return True

    image_type = (
        seg_data.get("type")
        or seg_data.get("_type")
        or seg_data.get("imageType")
        or seg_data.get("image_type")
    )
    image_type_text = str(image_type or "").strip().lower()
    return image_type_text in {"emoji", "sticker", "face", "meme"}


def _format_file_segment(seg_data: dict[str, Any]) -> str:
    file_name = _first_non_empty(
        seg_data, ("name", "file_name", "filename", "display", "title")
    )
    file_ref = _first_non_empty(seg_data, ("url", "file", "file_", "path", "id"))

    if file_name and file_ref and str(file_name) != str(file_ref):
        return f"[文件: {_safe_ref_text(file_name)}, {_safe_ref_text(file_ref)}]"
    if file_name:
        return f"[文件: {_safe_ref_text(file_name)}]"
    if file_ref:
        return f"[文件: {_safe_ref_text(file_ref)}]"

    raw_info = _compact_raw_data(seg_data)
    if raw_info:
        return f"[文件（识别失败）: {raw_info}]"
    return "[文件（识别失败）]"


def _format_at_segment(seg_data: dict[str, Any]) -> str:
    qq = _first_non_empty(seg_data, ("qq", "user_id", "id"))
    name = _first_non_empty(seg_data, ("name", "nickname", "card"))
    role = _first_non_empty(seg_data, ("role", "group_role"))

    if str(qq).lower() == "all":
        return "@全体成员"
    if name and qq and str(name) != str(qq):
        role_text = f"[{role}]" if role else ""
        return f"@{name}{role_text}"
    if name:
        return f"@{name}"
    if qq:
        return f"@未知用户(ID:{qq})"
    return "@未知用户"


async def _format_reply_segment(
    seg_data: dict[str, Any],
    call_action,
    include_sender_info: bool,
    include_timestamp: bool,
    max_nesting_depth: int,
    parse_context: dict[str, Any],
    depth: int,
    debug_mode: bool = False,
) -> str:
    reply_id = _first_non_empty(seg_data, ("id", "message_id", "seq"))
    sender_name = _first_non_empty(
        seg_data, ("sender_nickname", "sender_name", "nickname", "name")
    )
    sender_id = _first_non_empty(seg_data, ("sender_id", "user_id", "qq", "uin"))

    message_content = await _extract_inline_reply_content(
        seg_data=seg_data,
        call_action=call_action,
        include_sender_info=include_sender_info,
        include_timestamp=include_timestamp,
        max_nesting_depth=max_nesting_depth,
        parse_context=parse_context,
        depth=depth,
        debug_mode=debug_mode,
    )

    if not message_content and reply_id:
        reply_node = await _get_message_node_by_id(
            call_action,
            str(reply_id),
            parse_context,
            debug_mode,
        )
        if reply_node is not None:
            normalized = _normalize_forward_node(reply_node)
            sender_name = sender_name or normalized.get("sender_name", "")
            sender_id = sender_id or normalized.get("sender_id", "")
            message_content = await _format_segments_text(
                segments=normalized.get("segments", []),
                call_action=call_action,
                include_sender_info=include_sender_info,
                include_timestamp=include_timestamp,
                max_nesting_depth=max_nesting_depth,
                parse_context=parse_context,
                depth=depth + 1,
                current_sender_name=sender_name,
                current_sender_id=sender_id,
                current_time=normalized.get("timestamp", 0),
                debug_mode=debug_mode,
            )

    return _build_reply_text(
        sender_name=str(sender_name or ""),
        sender_id=str(sender_id or ""),
        message_content=(message_content or "").strip(),
        reply_id=str(reply_id or ""),
    )


async def _extract_inline_reply_content(
    seg_data: dict[str, Any],
    call_action,
    include_sender_info: bool,
    include_timestamp: bool,
    max_nesting_depth: int,
    parse_context: dict[str, Any],
    depth: int,
    debug_mode: bool = False,
) -> str:
    raw_content = None
    for key in ("chain", "message", "content", "origin"):
        value = seg_data.get(key)
        if value is not None:
            raw_content = value
            break

    if raw_content is not None:
        segments = _normalize_segments(raw_content)
        if segments:
            return await _format_segments_text(
                segments=segments,
                call_action=call_action,
                include_sender_info=include_sender_info,
                include_timestamp=include_timestamp,
                max_nesting_depth=max_nesting_depth,
                parse_context=parse_context,
                depth=depth + 1,
                current_sender_name=str(
                    _first_non_empty(
                        seg_data,
                        ("sender_nickname", "sender_name", "nickname", "name"),
                    )
                    or ""
                ),
                current_sender_id=str(
                    _first_non_empty(seg_data, ("sender_id", "user_id", "qq", "uin"))
                    or ""
                ),
                current_time=_safe_int(_first_non_empty(seg_data, ("time", "timestamp"))),
                debug_mode=debug_mode,
            )
        if isinstance(raw_content, str) and raw_content.strip():
            return raw_content.strip()

    message_str = _first_non_empty(seg_data, ("message_str", "text", "raw_message"))
    return str(message_str).strip() if message_str else ""


def _build_reply_text(
    sender_name: str,
    sender_id: str,
    message_content: str,
    reply_id: str = "",
) -> str:
    if sender_name and sender_id and sender_name != str(sender_id):
        sender_part = f"{sender_name}(ID:{sender_id})"
    elif sender_id:
        sender_part = f"未知用户(ID:{sender_id})"
    elif sender_name:
        sender_part = sender_name
    else:
        sender_part = ""

    if message_content:
        if sender_part:
            return f"[引用 >>> {sender_part}: {message_content}]\n"
        return f"[引用 >>> {message_content}]\n"

    missing = "(无法获取引用内容)"
    if reply_id:
        missing = f"(无法获取引用内容, ID:{reply_id})"
    if sender_part:
        return f"[引用 >>> {sender_part}: {missing}]\n"
    return f"[引用 >>> {missing}]\n"


async def _get_message_node_by_id(
    call_action,
    message_id: str,
    parse_context: dict[str, Any],
    debug_mode: bool = False,
) -> Optional[dict[str, Any]]:
    message_id_str = str(message_id or "").strip()
    if not message_id_str or call_action is None:
        return None

    message_cache = parse_context.setdefault("message_cache", {})
    if message_id_str in message_cache:
        return message_cache[message_id_str]

    if parse_context["api_call_count"] >= FORWARD_API_CALL_HARD_LIMIT:
        message_cache[message_id_str] = None
        return None

    params_list: list[dict[str, Any]] = [
        {"message_id": message_id_str},
        {"id": message_id_str},
    ]
    if message_id_str.isdigit():
        int_id = int(message_id_str)
        params_list.extend([{"message_id": int_id}, {"id": int_id}])

    parse_context["api_call_count"] += 1
    for params in params_list:
        try:
            result = await call_action("get_msg", **params)
            node = _extract_message_node_from_get_msg_response(result)
            if node is not None:
                message_cache[message_id_str] = node
                return node
        except Exception as e:
            if debug_mode:
                logger.debug(f"[转发消息] get_msg 获取引用消息 {params} 失败: {e}")
            continue

    message_cache[message_id_str] = None
    return None


def _extract_message_node_from_get_msg_response(response: Any) -> Optional[dict[str, Any]]:
    if isinstance(response, str):
        parsed = _safe_json_loads(response)
        if parsed is not None:
            return _extract_message_node_from_get_msg_response(parsed)
        return None

    if not isinstance(response, dict):
        return None

    data = response.get("data")
    if isinstance(data, dict):
        target = data
    else:
        target = response

    if str(target.get("type", "")).lower() == "node":
        return target

    raw_message = target.get("message")
    if raw_message is None:
        raw_message = target.get("content")
    if raw_message is None:
        raw_message = target.get("raw_message")
    if raw_message is None:
        return None

    return {
        "sender": target.get("sender", {}),
        "time": target.get("time") or target.get("timestamp") or target.get("date") or 0,
        "message": raw_message,
    }


def _format_named_structured_segment(seg_type: str, seg_data: dict[str, Any]) -> str:
    label_map = {
        "share": "分享",
        "music": "音乐",
        "contact": "联系人",
        "location": "位置",
    }
    label = label_map.get(seg_type, seg_type)
    title = _first_non_empty(seg_data, ("title", "name", "content", "text"))
    ref = _first_non_empty(seg_data, ("url", "audio", "image", "id"))
    if title and ref:
        return f"[{label}: {_safe_ref_text(title)}, {_safe_ref_text(ref)}]"
    if title:
        return f"[{label}: {_safe_ref_text(title)}]"
    if ref:
        return f"[{label}: {_safe_ref_text(ref)}]"
    return _format_generic_segment(label, seg_data)


def _format_generic_segment(label: str, seg_data: dict[str, Any]) -> str:
    raw_info = _compact_raw_data(seg_data)
    if raw_info:
        return f"[{label}: {raw_info}]"
    return f"[{label}]"


def _fallback_placeholder_for_segment(seg: Any) -> str:
    seg_type = ""
    try:
        if isinstance(seg, dict):
            seg_type = str(seg.get("type", "") or "").lower()
        else:
            seg_type = str(getattr(seg, "type", "") or "").lower()
    except Exception:
        seg_type = ""

    if "image" in seg_type:
        return "[图片（识别失败）]"
    if "video" in seg_type:
        return "[视频（识别失败）]"
    if "record" in seg_type or "audio" in seg_type or "voice" in seg_type:
        return "[语音（识别失败）]"
    if "file" in seg_type:
        return "[文件（识别失败）]"
    if "reply" in seg_type:
        return "[引用 >>> (无法获取引用内容)]\n"
    if "forward" in seg_type or "node" in seg_type:
        return "[嵌套转发消息]（无法获取内容）"
    return f"[{seg_type}]" if seg_type else "[未知消息段]"


def _first_non_empty(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value.strip()
            continue
        if value != "":
            return value
    return ""


def _first_text_content(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            if value != "":
                return value
            continue
        if value != "":
            return str(value)
    return ""


def _safe_ref_text(value: Any, max_len: int = 500) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if text.startswith("base64://"):
        return f"base64://...(len={max(len(text) - len('base64://'), 0)})"
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _compact_raw_data(data: dict[str, Any], max_len: int = 300) -> str:
    if not isinstance(data, dict) or not data:
        return ""
    try:
        safe_value = _make_compact_jsonable(data)
        raw = json.dumps(safe_value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        raw = str(data)
    raw = raw.replace("\r", " ").replace("\n", " ").strip()
    if len(raw) > max_len:
        raw = raw[:max_len] + "..."
    return raw


def _make_compact_jsonable(value: Any, depth: int = 0) -> Any:
    if depth > 2:
        return "..."
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in ("base64", "bytes"):
                result[key_text] = "[omitted]"
            else:
                result[key_text] = _make_compact_jsonable(item, depth + 1)
        return result
    if isinstance(value, list):
        return [_make_compact_jsonable(item, depth + 1) for item in value[:6]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str):
            return _safe_ref_text(value, max_len=160)
        return value
    return _safe_ref_text(value, max_len=160)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


async def _handle_nested_forward_segment(
    seg_data: dict,
    call_action,
    node_sender_name: str,
    node_sender_id: str,
    node_time: int,
    include_sender_info: bool,
    include_timestamp: bool,
    max_nesting_depth: int,
    parse_context: dict[str, Any],
    depth: int,
    debug_mode: bool = False,
) -> Optional[str]:
    new_depth = depth + 1

    if new_depth > max_nesting_depth:
        indent = "  " * new_depth
        return f"{indent}[嵌套转发消息]（嵌套层级过深，已省略详细内容）"

    nested_id = _extract_forward_id(seg_data)
    if nested_id:
        result = await _expand_nested_forward_by_id(
            nested_id=nested_id,
            call_action=call_action,
            node_sender_name=node_sender_name,
            node_sender_id=node_sender_id,
            node_time=node_time,
            include_sender_info=include_sender_info,
            include_timestamp=include_timestamp,
            max_nesting_depth=max_nesting_depth,
            parse_context=parse_context,
            depth=new_depth,
            debug_mode=debug_mode,
        )
        if not _should_try_inline_after_nested_id_result(result):
            return result
        # ID expansion failed or was capped; fall through to inline nodes if present.
    else:
        result = None

    nested_nodes = _extract_inline_nodes_from_forward_segment(seg_data)
    if nested_nodes is not None:
        return await _format_forward_message(
            nodes=nested_nodes,
            call_action=call_action,
            forwarder_name=node_sender_name,
            forwarder_id=node_sender_id,
            event_timestamp=node_time,
            include_sender_info=include_sender_info,
            include_timestamp=include_timestamp,
            max_nesting_depth=max_nesting_depth,
            parse_context=parse_context,
            depth=new_depth,
            debug_mode=debug_mode,
        )

    logger.warning(
        f"[转发消息] 嵌套转发解析失败：get_forward_msg 与 inline 回退均未获取到内容，"
        f"nested_id={nested_id or 'N/A'}，已替换为占位标识"
    )
    if result is not None:
        return result

    indent = "  " * new_depth
    return f"{indent}[嵌套转发消息]（无法获取内容）"


def _should_try_inline_after_nested_id_result(result: Optional[str]) -> bool:
    if not result:
        return True
    return any(
        marker in result
        for marker in (
            "（内容获取失败）",
            "（无法获取内容）",
            "（API调用次数已达上限",
        )
    )


async def _expand_nested_forward_by_id(
    nested_id: str,
    call_action,
    node_sender_name: str,
    node_sender_id: str,
    node_time: int,
    include_sender_info: bool,
    include_timestamp: bool,
    max_nesting_depth: int,
    parse_context: dict[str, Any],
    depth: int,
    debug_mode: bool = False,
) -> Optional[str]:
    indent = "  " * depth
    nested_id_str = str(nested_id).strip()
    if not nested_id_str:
        return f"{indent}[嵌套转发消息]（无法获取内容）"

    active_forward_ids = parse_context["active_forward_ids"]
    if nested_id_str in active_forward_ids:
        return f"{indent}[嵌套转发消息]（检测到重复嵌套转发，已跳过重复展开）"

    if (
        nested_id_str not in parse_context["forward_cache"]
        and parse_context["api_call_count"] >= FORWARD_API_CALL_HARD_LIMIT
    ):
        return f"{indent}[嵌套转发消息]（API调用次数已达上限，已省略详细内容）"

    nested_nodes = await _get_forward_nodes_by_id(
        call_action,
        nested_id_str,
        parse_context,
        debug_mode,
    )
    if nested_nodes is None:
        return f"{indent}[嵌套转发消息]（内容获取失败）"

    active_forward_ids.add(nested_id_str)
    try:
        return await _format_forward_message(
            nodes=nested_nodes,
            call_action=call_action,
            forwarder_name=node_sender_name,
            forwarder_id=node_sender_id,
            event_timestamp=node_time,
            include_sender_info=include_sender_info,
            include_timestamp=include_timestamp,
            max_nesting_depth=max_nesting_depth,
            parse_context=parse_context,
            depth=depth,
            debug_mode=debug_mode,
        )
    finally:
        active_forward_ids.discard(nested_id_str)


def _normalize_forward_node(node: dict[str, Any]) -> dict[str, Any]:
    candidate = dict(node)
    inner_data = node.get("data") if isinstance(node.get("data"), dict) else None
    if str(node.get("type", "")).lower() == "node" and inner_data:
        merged = dict(inner_data)
        for key in ("sender", "time", "timestamp", "message", "content"):
            if key in node and key not in merged:
                merged[key] = node[key]
        candidate = merged
    elif inner_data and not any(
        key in node for key in ("sender", "message", "content", "nickname", "user_id")
    ):
        candidate = dict(inner_data)

    sender_name, sender_id, sender_role = _extract_sender_info(candidate)
    timestamp = _extract_node_timestamp(candidate)
    raw_content = candidate.get("message")
    if raw_content is None:
        raw_content = candidate.get("content")
    segments = _normalize_segments(raw_content)

    return {
        "sender_name": sender_name,
        "sender_id": sender_id,
        "sender_role": sender_role,  # 🆕
        "timestamp": timestamp,
        "segments": segments,
    }


def _extract_sender_info(node: dict[str, Any]) -> tuple[str, str, str]:
    sender = node.get("sender") if isinstance(node.get("sender"), dict) else {}

    sender_name = (
        sender.get("nickname")
        or sender.get("card")
        or sender.get("name")
        or node.get("nickname")
        or node.get("name")
        or node.get("user_name")
        or ""
    )
    sender_id = (
        sender.get("user_id")
        or sender.get("uin")
        or sender.get("id")
        or sender.get("qq")
        or node.get("user_id")
        or node.get("uin")
        or node.get("id")
        or node.get("qq")
        or ""
    )
    # 🆕 提取群角色（OneBot v11 转发消息节点中 sender.role 字段，值为 owner/admin/member）
    sender_role_raw = str(sender.get("role", "") or "").strip()
    if sender_role_raw:
        _role_map = {"owner": "群主", "admin": "管理员", "member": "普通群成员"}
        sender_role = _role_map.get(sender_role_raw, "")
    else:
        sender_role = ""

    return str(sender_name or ""), str(sender_id or ""), sender_role


def _extract_node_timestamp(node: dict[str, Any]) -> int:
    node_time = node.get("time")
    if node_time is None:
        node_time = node.get("timestamp")
    if node_time is None:
        node_time = node.get("date")
    if isinstance(node_time, (int, float)):
        return int(node_time)
    try:
        return int(node_time)
    except (ValueError, TypeError):
        return 0


def _normalize_segments(raw_content: Any) -> list:
    if isinstance(raw_content, list):
        return raw_content
    if isinstance(raw_content, dict):
        if raw_content.get("type"):
            return [raw_content]
        for key in ("chain", "message", "content", "origin"):
            nested = raw_content.get(key)
            if isinstance(nested, list) and _looks_like_message_segment_list(nested):
                return nested
        nested = _extract_inline_nodes_from_forward_segment(raw_content)
        if nested is not None:
            return [{"type": "nodes", "data": {"content": nested}}]
    if isinstance(raw_content, str):
        raw_content = raw_content.strip()
        if not raw_content:
            return []
        parsed = _safe_json_loads(raw_content)
        if parsed is not None:
            normalized = _normalize_segments(parsed)
            if normalized:
                return normalized
        return [{"type": "text", "data": {"text": raw_content}}]
    return []


def _extract_forward_id(seg_data: dict[str, Any]) -> str:
    nested_id = seg_data.get("id") or seg_data.get("message_id")
    if nested_id is None:
        return ""
    return str(nested_id).strip()


def _extract_inline_nodes_from_forward_segment(seg_data: Any) -> Optional[list]:
    if isinstance(seg_data, list):
        return _coerce_inline_nodes_list(seg_data)

    if isinstance(seg_data, str):
        parsed = _safe_json_loads(seg_data)
        if parsed is not None:
            return _extract_inline_nodes_from_forward_segment(parsed)
        return None

    if not isinstance(seg_data, dict):
        return None

    if _looks_like_single_node_data(seg_data):
        return [{"type": "node", "data": seg_data}]

    for key in ("content", "messages", "nodes", "nodeList", "message"):
        nested = seg_data.get(key)
        if isinstance(nested, list):
            return _coerce_inline_nodes_list(nested, seg_data)
        if isinstance(nested, str):
            parsed = _safe_json_loads(nested)
            if parsed is not None:
                extracted = _extract_inline_nodes_from_forward_segment(parsed)
                if extracted is not None:
                    return extracted
        if isinstance(nested, dict):
            extracted = _extract_inline_nodes_from_forward_segment(nested)
            if extracted is not None:
                return extracted

    nested_data = seg_data.get("data")
    if nested_data is not None:
        extracted = _extract_inline_nodes_from_forward_segment(nested_data)
        if extracted is not None:
            return extracted

    return None


def _coerce_inline_nodes_list(
    items: list, parent_data: Optional[dict[str, Any]] = None
) -> Optional[list]:
    if not isinstance(items, list) or not items:
        return None

    if _looks_like_message_segment_list(items):
        return [_build_inline_node_from_segments(items, parent_data)]

    return items


def _looks_like_message_segment_list(items: Any) -> bool:
    if not isinstance(items, list) or not items:
        return False

    has_message_segment = any(_looks_like_message_segment_item(item) for item in items)
    if not has_message_segment:
        return False

    has_non_node_item = any(not _looks_like_forward_node_item(item) for item in items)
    return has_non_node_item


def _looks_like_message_segment_item(item: Any) -> bool:
    if isinstance(item, (Plain, AtAll, At, Face, Image, Video, Record, File, Reply, Forward, Nodes)):
        return True
    if isinstance(item, Node):
        return False
    if not isinstance(item, dict):
        return False

    item_type = str(item.get("type", "") or "").lower()
    return item_type in {
        "text",
        "plain",
        "image",
        "video",
        "record",
        "audio",
        "voice",
        "file",
        "face",
        "at",
        "reply",
        "forward",
        "forward_msg",
        "nodes",
        "json",
        "xml",
        "share",
        "music",
        "contact",
        "location",
    }


def _looks_like_forward_node_item(item: Any) -> bool:
    if isinstance(item, Node):
        return True
    if not isinstance(item, dict):
        return False

    item_type = str(item.get("type", "") or "").lower()
    if item_type == "node":
        return True
    if _looks_like_single_node_data(item):
        return True

    data = item.get("data")
    if isinstance(data, dict):
        return item_type == "node" or _looks_like_single_node_data(data)

    return False


def _build_inline_node_from_segments(
    segments: list, parent_data: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    node_data: dict[str, Any] = {"content": segments}
    if isinstance(parent_data, dict):
        for key in (
            "sender",
            "time",
            "timestamp",
            "date",
            "nickname",
            "name",
            "user_name",
            "user_id",
            "uin",
            "qq",
        ):
            if key in parent_data and key not in node_data:
                node_data[key] = parent_data[key]
    return {"type": "node", "data": node_data}


def _looks_like_single_node_data(seg_data: dict[str, Any]) -> bool:
    if not isinstance(seg_data, dict):
        return False
    has_message_payload = any(key in seg_data for key in ("content", "message"))
    has_node_identity = any(
        key in seg_data
        for key in (
            "sender",
            "user_id",
            "uin",
            "qq",
            "nickname",
            "name",
            "user_name",
            "time",
            "timestamp",
            "date",
        )
    )
    return has_message_payload and has_node_identity


def _safe_json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _format_timestamp(unix_timestamp: int) -> str:
    try:
        if not unix_timestamp or unix_timestamp <= 0:
            return ""
        dt = datetime.fromtimestamp(unix_timestamp)
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[dt.weekday()]
        return dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")
    except Exception:
        return ""


def _try_parse_multimsg_json(raw_json: str) -> Optional[str]:
    try:
        raw_json = raw_json.replace("&#44;", ",")
        parsed = json.loads(raw_json)
        if not isinstance(parsed, dict):
            return None
        if parsed.get("app") != "com.tencent.multimsg":
            return None

        config = parsed.get("config")
        if not isinstance(config, dict) or config.get("forward") != 1:
            return None

        meta = parsed.get("meta")
        if not isinstance(meta, dict):
            return None
        detail = meta.get("detail")
        if not isinstance(detail, dict):
            return None
        news_items = detail.get("news")
        if not isinstance(news_items, list):
            return None

        texts = []
        for item in news_items:
            if not isinstance(item, dict):
                continue
            text_content = item.get("text")
            if isinstance(text_content, str):
                cleaned = text_content.strip().replace("[图片]", "").strip()
                if cleaned:
                    texts.append(cleaned)

        return "\n".join(texts).strip() or None
    except Exception:
        return None
