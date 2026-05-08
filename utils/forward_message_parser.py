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
from astrbot.core.message.components import Forward, Plain
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
                    logger.info("[转发消息] 当前平台不支持 get_forward_msg API，跳过解析")
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

    logger.warning(f"[转发消息] 所有 get_forward_msg 尝试均失败，forward_id={forward_id}")
    return None


def _extract_nodes_from_response(response: Any) -> Optional[list]:
    if isinstance(response, list):
        return response

    if isinstance(response, str):
        parsed = _safe_json_loads(response)
        if parsed is not None:
            return _extract_nodes_from_response(parsed)
        return None

    if not isinstance(response, dict):
        return None

    data = response.get("data")
    if isinstance(data, list):
        return data

    for target in (data, response):
        if not isinstance(target, dict):
            continue
        for key in ("messages", "message", "nodes", "nodeList", "content"):
            nodes = target.get(key)
            if isinstance(nodes, list):
                return nodes
        target_type = str(target.get("type", "")).lower()
        if target_type in ("node", "nodes"):
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
        if not isinstance(node, dict):
            continue
        try:
            node_text = await _format_single_node(
                node=node,
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
        if forwarder_name:
            sender_str = f"{forwarder_name}(ID:{forwarder_id})"
        else:
            sender_str = f"用户(ID:{forwarder_id})"
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
    node_time = normalized_node["timestamp"]
    segments = normalized_node["segments"]

    text_parts = []
    nested_forward_texts = []

    for seg in segments:
        if not isinstance(seg, dict):
            continue

        seg_type = str(seg.get("type", "")).lower()
        seg_data = seg.get("data", {}) if isinstance(seg.get("data"), dict) else {}

        if seg_type in ("text", "plain"):
            text = seg_data.get("text", "")
            if isinstance(text, str) and text:
                text_parts.append(text)
        elif seg_type == "image":
            text_parts.append("[图片]")
        elif seg_type == "video":
            text_parts.append("[视频]")
        elif seg_type == "record":
            text_parts.append("[语音]")
        elif seg_type == "file":
            file_name = (
                seg_data.get("name")
                or seg_data.get("file_name")
                or seg_data.get("file")
                or "文件"
            )
            text_parts.append(f"[文件:{file_name}]")
        elif seg_type == "face":
            face_id = seg_data.get("id", "")
            text_parts.append(f"[表情:{face_id}]")
        elif seg_type == "at":
            qq = seg_data.get("qq") or seg_data.get("user_id") or ""
            name = seg_data.get("name") or seg_data.get("nickname") or ""
            if qq == "all":
                text_parts.append("@全体成员")
            elif name:
                text_parts.append(f"@{name}")
            else:
                text_parts.append(f"@{qq}")
        elif seg_type in ("forward", "forward_msg", "nodes"):
            nested_text = await _handle_nested_forward_segment(
                seg_data=seg_data,
                call_action=call_action,
                node_sender_name=sender_name,
                node_sender_id=sender_id,
                node_time=node_time,
                include_sender_info=include_sender_info,
                include_timestamp=include_timestamp,
                max_nesting_depth=max_nesting_depth,
                parse_context=parse_context,
                depth=depth,
                debug_mode=debug_mode,
            )
            if nested_text:
                nested_forward_texts.append(nested_text)
        elif seg_type == "json":
            raw_json = seg_data.get("data", "")
            if isinstance(raw_json, str) and raw_json.strip():
                multimsg_text = _try_parse_multimsg_json(raw_json)
                if multimsg_text:
                    text_parts.append(multimsg_text)
                else:
                    text_parts.append("[JSON消息]")
            else:
                text_parts.append("[JSON消息]")
        else:
            if seg_type:
                text_parts.append(f"[{seg_type}]")

    main_text = "".join(text_parts).strip()

    line_prefix_parts = []
    if include_timestamp and node_time and node_time > 0:
        time_str = _format_timestamp(node_time)
        if time_str:
            line_prefix_parts.append(f"[{time_str}]")
    if include_sender_info and (sender_name or sender_id):
        if sender_name:
            line_prefix_parts.append(f"{sender_name}(ID:{sender_id}):")
        elif sender_id:
            line_prefix_parts.append(f"用户(ID:{sender_id}):")
    line_prefix = " ".join(line_prefix_parts)

    result_parts = []

    if main_text:
        if line_prefix:
            result_parts.append(f"{indent}{line_prefix} {main_text}")
        else:
            result_parts.append(f"{indent}{main_text}")

    result_parts.extend(nested_forward_texts)

    if not result_parts:
        return None

    return "\n".join(result_parts)


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
        return await _expand_nested_forward_by_id(
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

    indent = "  " * new_depth
    return f"{indent}[嵌套转发消息]（无法获取内容）"


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

    sender_name, sender_id = _extract_sender_info(candidate)
    timestamp = _extract_node_timestamp(candidate)
    raw_content = candidate.get("message")
    if raw_content is None:
        raw_content = candidate.get("content")
    segments = _normalize_segments(raw_content)

    return {
        "sender_name": sender_name,
        "sender_id": sender_id,
        "timestamp": timestamp,
        "segments": segments,
    }


def _extract_sender_info(node: dict[str, Any]) -> tuple[str, str]:
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

    return str(sender_name or ""), str(sender_id or "")


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
        return seg_data

    if isinstance(seg_data, str):
        parsed = _safe_json_loads(seg_data)
        if parsed is not None:
            return _extract_inline_nodes_from_forward_segment(parsed)
        return None

    if not isinstance(seg_data, dict):
        return None

    for key in ("content", "messages", "nodes", "nodeList", "message"):
        nested = seg_data.get(key)
        if isinstance(nested, list):
            return nested
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
