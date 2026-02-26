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


# 硬上限常量
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
        """
        尝试解析事件中的转发消息并替换消息链。
        支持嵌套转发，递归深度受 max_nesting_depth 控制（硬上限10层）。

        所有配置通过参数传入，不直接读取 config。

        Args:
            event: AstrBot 消息事件
            include_sender_info: 是否包含发送者信息（名字+ID）
            include_timestamp: 是否包含时间戳
            max_nesting_depth: 嵌套转发最大解析深度（0=不解析嵌套，硬上限10）
            debug_mode: 是否输出调试日志

        Returns:
            True 表示检测到并成功解析了转发消息，False 表示无转发或解析失败。
        """
        try:
            # 检查消息链是否存在
            if not hasattr(event, "message_obj") or not hasattr(
                event.message_obj, "message"
            ):
                return False
            message_chain = event.message_obj.message
            if not message_chain:
                return False

            # 查找 Forward 组件
            forward_indices = []
            for i, component in enumerate(message_chain):
                if isinstance(component, Forward):
                    forward_indices.append(i)

            if not forward_indices:
                return False

            if debug_mode:
                logger.info(f"[转发消息] 检测到 {len(forward_indices)} 个转发消息组件")

            # 检查平台支持：需要 bot 具有 call_action 方法（aiocqhttp 特有）
            call_action = _get_call_action(event)
            if call_action is None:
                if debug_mode:
                    logger.info(
                        "[转发消息] 当前平台不支持 get_forward_msg API，跳过解析"
                    )
                return False

            # 限制嵌套深度在硬上限内
            effective_max_depth = min(
                max(max_nesting_depth, 0), FORWARD_NESTING_HARD_LIMIT
            )

            # API 调用计数器（跨所有递归共享）
            api_call_counter = {"count": 0}

            # 获取转发者信息（即触发此事件的发送者）
            forwarder_name = event.get_sender_name() or ""
            forwarder_id = event.get_sender_id() or ""

            # 获取事件时间戳
            event_timestamp = getattr(event.message_obj, "timestamp", 0) or int(
                time.time()
            )

            any_parsed = False

            # 逆序遍历，这样替换不会影响前面的索引
            for idx in reversed(forward_indices):
                forward_comp = message_chain[idx]
                forward_id = getattr(forward_comp, "id", None)
                if not forward_id:
                    if debug_mode:
                        logger.info(f"[转发消息] Forward 组件无 id 字段，跳过")
                    continue

                if debug_mode:
                    logger.info(f"[转发消息] 正在获取转发内容，ID: {forward_id}")

                # 调用 API 获取转发消息内容
                api_call_counter["count"] += 1
                nodes = await _fetch_forward_nodes(call_action, forward_id, debug_mode)

                if nodes is None:
                    # API 失败，使用占位文本
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

                # 解析节点内容为文本
                formatted_text = await _format_forward_message(
                    nodes=nodes,
                    call_action=call_action,
                    forwarder_name=forwarder_name,
                    forwarder_id=forwarder_id,
                    event_timestamp=event_timestamp,
                    include_sender_info=include_sender_info,
                    include_timestamp=include_timestamp,
                    max_nesting_depth=effective_max_depth,
                    api_call_counter=api_call_counter,
                    depth=0,
                    debug_mode=debug_mode,
                )

                # 替换 Forward 组件为 Plain 纯文本
                message_chain[idx] = Plain(text=formatted_text)
                any_parsed = True

                if debug_mode:
                    logger.info(
                        f"[转发消息] 已解析转发消息（{len(nodes)} 条节点），"
                        f"API 调用次数: {api_call_counter['count']}"
                    )

            # 更新 message_str
            if any_parsed:
                new_str_parts = []
                for comp in message_chain:
                    if isinstance(comp, Plain):
                        if comp.text is not None:
                            new_str_parts.append(comp.text)
                    else:
                        # 保留其他组件的原始文本表示
                        new_str_parts.append(f"[{getattr(comp, 'type', 'Unknown')}]")
                event.message_obj.message_str = " ".join(new_str_parts)
                event.message_str = event.message_obj.message_str

            return any_parsed

        except Exception as e:
            logger.warning(f"[转发消息] 解析转发消息时发生异常（已跳过）: {e}")
            return False


def _get_call_action(event: AstrMessageEvent):
    """
    获取 event 上的 bot.call_action 方法。
    仅 aiocqhttp 平台有此方法，其他平台返回 None。
    """
    try:
        bot = getattr(event, "bot", None)
        if bot is None:
            return None
        # aiocqhttp 的 bot 对象直接有 call_action
        call_action = getattr(bot, "call_action", None)
        if callable(call_action):
            return call_action
        # 某些实现可能在 api 子对象上
        api = getattr(bot, "api", None)
        if api is not None:
            call_action = getattr(api, "call_action", None)
            if callable(call_action):
                return call_action
        return None
    except Exception:
        return None


async def _fetch_forward_nodes(
    call_action,
    forward_id: str,
    debug_mode: bool = False,
) -> Optional[list]:
    """
    调用 get_forward_msg API 获取转发消息节点列表。
    兼容多种 OneBot 实现的参数格式和响应结构。

    Returns:
        节点列表 list[dict]，失败返回 None
    """
    # 尝试多种参数格式（不同 OneBot 实现可能使用不同参数名）
    params_list = [
        {"message_id": forward_id},
        {"id": forward_id},
    ]
    # 如果 id 是纯数字，额外尝试整数格式
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

    logger.warning(
        f"[转发消息] 所有 get_forward_msg 尝试均失败，forward_id={forward_id}"
    )
    return None


def _extract_nodes_from_response(response: Any) -> Optional[list]:
    """
    从 get_forward_msg API 响应中提取节点列表。
    兼容多种响应结构。
    """
    # 某些实现可能直接返回节点列表
    if isinstance(response, list) and len(response) > 0:
        return response

    if not isinstance(response, dict):
        return None

    # 尝试从 data 字段解包
    data = response.get("data")
    if isinstance(data, list) and len(data) > 0:
        # 某些实现返回 {"data": [node1, node2, ...]}
        return data
    if isinstance(data, dict):
        search_target = data
    else:
        search_target = response

    # 尝试多种字段名
    for key in ("messages", "message", "nodes", "nodeList"):
        nodes = search_target.get(key)
        if isinstance(nodes, list) and len(nodes) > 0:
            return nodes

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
    api_call_counter: dict,
    depth: int = 0,
    debug_mode: bool = False,
) -> str:
    """
    将转发消息节点格式化为可读纯文本。
    支持嵌套转发的递归解析。

    Args:
        nodes: 消息节点列表
        call_action: OneBot call_action 方法
        forwarder_name: 转发者名字
        forwarder_id: 转发者ID
        event_timestamp: 事件时间戳
        include_sender_info: 是否包含发送者信息
        include_timestamp: 是否包含时间戳
        max_nesting_depth: 最大嵌套深度
        api_call_counter: API 调用计数器（共享字典 {"count": n}）
        depth: 当前递归深度（0=最外层）
        debug_mode: 调试模式

    Returns:
        格式化后的纯文本字符串
    """
    indent = "  " * depth
    is_nested = depth > 0

    # 构建头部
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

    # 构建分隔符
    sep_label = "嵌套转发" if is_nested else "转发"
    sep_start = f"{indent}--- {sep_label}内容 ---"
    sep_end = f"{indent}--- {sep_label}结束 ---"

    # 解析每个节点
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
                api_call_counter=api_call_counter,
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
        # 所有节点解析失败
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
    """
    构建转发消息的头部文本。

    根据 include_sender_info 和 include_timestamp 配置：
    - 两者都开：[时间戳] [转发消息] 由 名字(ID:xxx) 转发的消息：
    - 只开sender：[转发消息] 由 名字(ID:xxx) 转发的消息：
    - 只开时间戳：[时间戳] [转发消息]：
    - 都关：[转发消息]：
    """
    parts = []

    # 时间戳部分
    if include_timestamp and timestamp and timestamp > 0:
        time_str = _format_timestamp(timestamp)
        if time_str:
            parts.append(f"[{time_str}]")

    # 标签
    parts.append(label)

    # 转发者信息
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
    api_call_counter: dict,
    depth: int,
    indent: str,
    debug_mode: bool = False,
) -> Optional[str]:
    """
    格式化单个转发节点为文本行。

    Returns:
        格式化的文本行，或 None（无内容）
    """
    # 提取发送者信息
    sender = node.get("sender") if isinstance(node.get("sender"), dict) else {}
    sender_name = (
        sender.get("nickname") or sender.get("card") or sender.get("user_id") or ""
    )
    sender_id = str(sender.get("user_id", ""))

    # 提取时间戳
    node_time = node.get("time", 0)
    if not isinstance(node_time, (int, float)):
        try:
            node_time = int(node_time)
        except (ValueError, TypeError):
            node_time = 0

    # 提取消息内容（兼容 message / content 字段）
    raw_content = node.get("message") or node.get("content") or []
    segments = _normalize_segments(raw_content)

    # 解析 segments 为文本，同时检测嵌套转发
    text_parts = []
    nested_forward_texts = []

    for seg in segments:
        if not isinstance(seg, dict):
            continue

        seg_type = seg.get("type", "")
        seg_data = seg.get("data", {}) if isinstance(seg.get("data"), dict) else {}

        if seg_type in ("text", "plain"):
            text = seg_data.get("text", "")
            if text:
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
            qq = seg_data.get("qq", "")
            name = seg_data.get("name", "")
            if qq == "all":
                text_parts.append("@全体成员")
            elif name:
                text_parts.append(f"@{name}")
            else:
                text_parts.append(f"@{qq}")
        elif seg_type in ("forward", "forward_msg", "nodes"):
            # 嵌套转发
            nested_text = await _handle_nested_forward(
                seg_data=seg_data,
                call_action=call_action,
                node_sender_name=sender_name,
                node_sender_id=sender_id,
                node_time=node_time,
                include_sender_info=include_sender_info,
                include_timestamp=include_timestamp,
                max_nesting_depth=max_nesting_depth,
                api_call_counter=api_call_counter,
                depth=depth,
                debug_mode=debug_mode,
            )
            if nested_text:
                nested_forward_texts.append(nested_text)
        elif seg_type == "json":
            # JSON 消息（可能是小程序卡片等）
            raw_json = seg_data.get("data", "")
            if isinstance(raw_json, str) and raw_json.strip():
                # 尝试解析为合并转发 JSON
                multimsg_text = _try_parse_multimsg_json(raw_json)
                if multimsg_text:
                    text_parts.append(multimsg_text)
                else:
                    text_parts.append("[JSON消息]")
            else:
                text_parts.append("[JSON消息]")
        else:
            # 其他未知类型
            if seg_type:
                text_parts.append(f"[{seg_type}]")

    # 组合文本
    main_text = "".join(text_parts).strip()

    # 构建行前缀
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

    # 添加嵌套转发文本
    for nested_text in nested_forward_texts:
        result_parts.append(nested_text)

    if not result_parts:
        return None

    return "\n".join(result_parts)


async def _handle_nested_forward(
    seg_data: dict,
    call_action,
    node_sender_name: str,
    node_sender_id: str,
    node_time: int,
    include_sender_info: bool,
    include_timestamp: bool,
    max_nesting_depth: int,
    api_call_counter: dict,
    depth: int,
    debug_mode: bool = False,
) -> Optional[str]:
    """
    处理嵌套转发消息。

    Returns:
        嵌套转发的格式化文本，或 None
    """
    new_depth = depth + 1

    # 检查嵌套深度限制
    if new_depth > max_nesting_depth:
        indent = "  " * new_depth
        return f"{indent}[嵌套转发消息]（嵌套层级过深，已省略详细内容）"

    # 检查 API 调用次数限制
    if api_call_counter["count"] >= FORWARD_API_CALL_HARD_LIMIT:
        indent = "  " * new_depth
        return f"{indent}[嵌套转发消息]（API调用次数已达上限，已省略详细内容）"

    # 尝试获取嵌套转发 ID
    nested_id = seg_data.get("id") or seg_data.get("message_id")
    if not nested_id:
        # 可能内容直接在 data.content 中（某些 OneBot 实现）
        nested_content = seg_data.get("content")
        if isinstance(nested_content, list):
            # 直接解析内联节点
            return await _format_forward_message(
                nodes=nested_content,
                call_action=call_action,
                forwarder_name=node_sender_name,
                forwarder_id=node_sender_id,
                event_timestamp=node_time,
                include_sender_info=include_sender_info,
                include_timestamp=include_timestamp,
                max_nesting_depth=max_nesting_depth,
                api_call_counter=api_call_counter,
                depth=new_depth,
                debug_mode=debug_mode,
            )
        indent = "  " * new_depth
        return f"{indent}[嵌套转发消息]（无法获取内容）"

    # 调用 API 获取嵌套转发内容
    api_call_counter["count"] += 1
    nested_nodes = await _fetch_forward_nodes(call_action, str(nested_id), debug_mode)

    if nested_nodes is None:
        indent = "  " * new_depth
        return f"{indent}[嵌套转发消息]（内容获取失败）"

    # 递归格式化
    return await _format_forward_message(
        nodes=nested_nodes,
        call_action=call_action,
        forwarder_name=node_sender_name,
        forwarder_id=node_sender_id,
        event_timestamp=node_time,
        include_sender_info=include_sender_info,
        include_timestamp=include_timestamp,
        max_nesting_depth=max_nesting_depth,
        api_call_counter=api_call_counter,
        depth=new_depth,
        debug_mode=debug_mode,
    )


def _normalize_segments(raw_content) -> list:
    """
    将各种格式的消息内容统一为 segment 列表。
    兼容 list[dict]、str (JSON)、str (纯文本) 格式。
    """
    if isinstance(raw_content, list):
        return raw_content
    if isinstance(raw_content, str):
        raw_content = raw_content.strip()
        if not raw_content:
            return []
        # 尝试解析为 JSON
        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        # 纯文本
        return [{"type": "text", "data": {"text": raw_content}}]
    return []


def _format_timestamp(unix_timestamp: int) -> str:
    """
    将 Unix 时间戳格式化为可读字符串。
    格式：YYYY-MM-DD 星期几 HH:MM:SS（与插件其他部分保持一致）
    """
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
    """
    尝试从 JSON 消息中解析合并转发的摘要信息。
    QQ 的合并转发有时以 com.tencent.multimsg JSON 格式出现。
    """
    try:
        # 处理 HTML 实体
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
