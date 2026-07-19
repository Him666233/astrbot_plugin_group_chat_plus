"""
消息处理器模块
负责消息预处理，添加时间戳、发送者信息等元数据

v1.0.4 更新：
- 添加发送者识别系统提示（根据触发方式）
- 在开启include_sender_info时，在消息末尾添加系统提示帮助AI识别发送者

作者: Him666233
版本: V1.2.3.hotfix.2
"""

import re
from datetime import datetime
from astrbot.api.all import *
from astrbot.api.message_components import At

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class MessageProcessor:
    """
    消息处理器

    主要功能：
    1. 添加时间戳
    2. 添加发送者信息（ID和昵称）
    3. 格式化消息便于AI理解
    """

    @staticmethod
    def build_persistent_poke_event_text(
        poke_info: dict = None,
        perspective: str = "user",
    ) -> str:
        """构建可保留到历史中的戳一戳事件文本。"""
        try:
            if not poke_info or not isinstance(poke_info, dict):
                return ""

            sender_id = str(poke_info.get("sender_id", "") or "")
            sender_name = str(poke_info.get("sender_name", "") or "").strip()
            if not sender_name or sender_name == sender_id:
                sender_name = "未知用户"
            sender_role = str(poke_info.get("sender_group_role", "") or "").strip()
            target_id = str(poke_info.get("target_id", "") or "")
            target_name = str(poke_info.get("target_name", "") or "").strip()
            if not target_name or target_name == target_id:
                target_name = "未知用户"
            target_role = str(poke_info.get("target_group_role", "") or "").strip()
            is_poke_bot = bool(poke_info.get("is_poke_bot", False))

            if sender_id:
                sender_text = f"{sender_name}(ID:{sender_id})"
                if sender_role:
                    sender_text += f"[{sender_role}]"
            else:
                sender_text = sender_name or "未知用户"
                if sender_role and sender_text != "未知用户":
                    sender_text += f"[{sender_role}]"
            if target_id:
                target_text = f"{target_name}(ID:{target_id})"
                if target_role:
                    target_text += f"[{target_role}]"
            else:
                target_text = target_name or "未知用户"
                if target_role and target_text != "未知用户":
                    target_text += f"[{target_role}]"

            if perspective == "assistant":
                if not target_text:
                    return ""
                return f"[戳一戳事件]你戳了{target_text}"

            if is_poke_bot:
                if not sender_text:
                    return "[戳一戳事件]有人戳了你"
                return f"[戳一戳事件]有人戳了你，发起者是{sender_text}"

            if not sender_text and not target_text:
                return "[戳一戳事件]发生了一次戳一戳互动"
            if not sender_text:
                return f"[戳一戳事件]这不是戳你的消息，有人戳了{target_text}"
            if not target_text:
                return f"[戳一戳事件]这不是戳你的消息，{sender_text}戳了别人"
            return f"[戳一戳事件]这不是戳你的消息，{sender_text}戳了{target_text}"
        except Exception as e:
            logger.warning(f"构建可持久化戳一戳事件文本失败: {e}")
            return ""

    @staticmethod
    def _normalize_mention_info(mention_info: dict | None) -> dict:
        if not mention_info or not isinstance(mention_info, dict):
            return {}
        return mention_info

    @staticmethod
    def _build_inline_at_map(mention_info: dict | None) -> dict:
        mention_info = MessageProcessor._normalize_mention_info(mention_info)
        mentions = mention_info.get("mentions")
        if not isinstance(mentions, list):
            return {}

        inline_map = {}
        for mention in mentions:
            if not isinstance(mention, dict):
                continue
            user_id = str(mention.get("user_id", "") or "").strip()
            if not user_id or user_id.lower() == "all":
                continue
            if user_id in inline_map:
                continue
            if mention.get("is_bot"):
                inline_map[user_id] = "你"
                continue
            if mention.get("resolved"):
                user_name = str(mention.get("user_name", "") or "").strip()
                if user_name and user_name != user_id:
                    inline_map[user_id] = user_name
                else:
                    inline_map[user_id] = "未知用户"
            else:
                inline_map[user_id] = "未知用户"
        return inline_map

    @staticmethod
    def _replace_at_tokens(message_text: str, mention_info: dict | None) -> str:
        if not message_text:
            return message_text

        mention_info = MessageProcessor._normalize_mention_info(mention_info)
        if not mention_info:
            return message_text

        mentions = mention_info.get("mentions")
        if not isinstance(mentions, list) or not mentions:
            return message_text

        # 构建队列（包含 all → "全体成员"、解析失败等全部逻辑）
        mention_queue = []
        for mention in mentions:
            if not isinstance(mention, dict):
                continue
            user_id = str(mention.get("user_id", "") or "").strip()
            if not user_id:
                continue
            group_role = str(mention.get("group_role", "") or "").strip()
            if user_id.lower() == "all":
                mention_queue.append({"user_id": "all", "resolved_name": "全体成员", "group_role": ""})
                continue
            if mention.get("is_bot"):
                mention_queue.append({"user_id": user_id, "resolved_name": "你", "group_role": group_role})
                continue
            if mention.get("resolved"):
                user_name = str(mention.get("user_name", "") or "").strip()
                mention_queue.append(
                    {
                        "user_id": user_id,
                        "resolved_name": user_name
                        if (user_name and user_name != user_id)
                        else "未知用户",
                        "group_role": group_role,
                    }
                )
            else:
                mention_queue.append({"user_id": user_id, "resolved_name": "未知用户", "group_role": group_role})

        if not mention_queue:
            return message_text

        # 将队列转为查表字典（同 ID 保留首次出现的 (resolved_name, group_role)），消除顺序依赖
        lookup = {}
        for entry in mention_queue:
            uid = entry["user_id"]
            if uid not in lookup:
                lookup[uid] = (entry["resolved_name"], entry.get("group_role", ""))

        def _replace(match: re.Match) -> str:
            token_id = str(match.group(1) or "").strip()
            token_resolved = match.group(2)
            if token_resolved is not None:
                return match.group(0)
            resolved = lookup.get(token_id)
            if resolved:
                name, role = resolved
                if role:
                    return f"[At:{token_id}|{name}|{role}]"
                return f"[At:{token_id}|{name}]"
            return match.group(0)

        return re.sub(r"\[At:([^\]|]+)(?:\|([^\]]*))?\]", _replace, message_text)

    @staticmethod
    def inline_resolve_mentions(message_text: str, mention_info: dict | None) -> str:
        return MessageProcessor._replace_at_tokens(message_text, mention_info)

    @staticmethod
    def format_message_for_context_display(
        message_text: str,
        mention_info: dict | None = None,
        is_at_all_message: bool = False,
        persistent_poke_event_text: str = "",
        poke_trace_text: str = "",
    ) -> str:
        message_text = MessageProcessor.inline_resolve_mentions(
            message_text, mention_info
        )

        mention_info = MessageProcessor._normalize_mention_info(mention_info)
        mention_notice = MessageProcessor.build_mention_direction_notice(mention_info)
        if mention_notice and mention_notice not in message_text:
            if message_text.strip():
                message_text += f"\n{mention_notice}"
            else:
                message_text = mention_notice

        has_at_all = bool(is_at_all_message or mention_info.get("has_at_all", False))
        if has_at_all:
            message_text += (
                "\n【@全体成员说明】这是一条@全体成员消息。"
                "它也包含你，但不一定是专门只对你说的。"
            )

        persistent_poke_event_text = (persistent_poke_event_text or "").strip()
        if (
            persistent_poke_event_text
            and persistent_poke_event_text not in message_text
        ):
            if message_text.strip():
                message_text = f"{message_text}\n{persistent_poke_event_text}"
            else:
                message_text = persistent_poke_event_text

        poke_trace_text = (poke_trace_text or "").strip()
        if poke_trace_text and poke_trace_text not in message_text:
            if message_text.strip():
                message_text = f"{message_text}\n{poke_trace_text}"
            else:
                message_text = poke_trace_text

        return message_text

    @staticmethod
    def build_mention_direction_notice(mention_info: dict | None) -> str:
        mention_info = MessageProcessor._normalize_mention_info(mention_info)
        if not mention_info or not mention_info.get("has_at_others"):
            return ""

        if mention_info.get("has_at_ai"):
            return "【@指向说明】这条消息除了@你，也@了其他用户，不一定只是在对你一个人说。"
        return "【@指向说明】这条消息通过@符号指定了其他用户，并非只发给你本人。"

    @staticmethod
    def _build_environment_tag(group_name: str, group_id: str) -> str:
        """构建 [环境: name(ID:id)] 标签，含冗余回退。
        无 group_id → 返回空（如私聊场景）
        group_name 为空 → [未知群名] 占位"""
        if not group_id or not str(group_id).strip():
            return ""
        resolved_name = (group_name or "").strip() or "[未知群名]"
        return f"[环境: {resolved_name}(ID:{str(group_id).strip()})]"

    @staticmethod
    # 兼容旧调用：recent_pending_summary / empty_at_context_prompt 已弃用，
    # 但主流程和若干保存链路仍沿用原签名，暂时保留参数以避免影响功能。
    #   - recent_pending_summary / empty_at_context_prompt 替補：
    #     _build_single_at_message_context + _build_single_at_message_reply_hint
    #     （在 main.py 独立构建，由 reply handler 注入，不再经本方法拼接）。
    #   - poke_info 在本方法内未使用，保留参数仅为兼容旧签名。
    #     替补 A：build_persistent_poke_event_text(poke_info) → persistent_poke_event_text
    #     替补 B：main.py 直接从 poke_info 构建 _poke_notice_text → format_context_for_ai 追加
    def add_metadata_to_message(
        event: AstrMessageEvent,
        message_text: str,
        include_timestamp: bool,
        include_sender_info: bool,
        mention_info: dict = None,
        trigger_type: str = None,
        poke_info: dict = None,
        is_empty_at: bool = False,
        recent_pending_summary: str = "",
        empty_at_context_prompt: str = "",
        is_at_all_message: bool = False,
        *,
        persistent_poke_event_text: str = "",
        poke_trace_text: str = "",
        include_environment_info: bool = False,
        group_role: str = "",
    ) -> str:
        """
        为消息添加元数据（时间戳和发送者）

        格式与历史消息保持一致，便于AI识别：
        [时间] 发送者名字(ID:xxx): 消息内容

        Args:
            event: 消息事件
            message_text: 原始消息
            include_timestamp: 是否包含时间戳
            include_sender_info: 是否包含发送者信息
            mention_info: 统一的@解析结果（可包含@AI/@他人/@全体、重复@等复合场景）
            trigger_type: 触发方式，可选值: "at", "keyword", "ai_decision"
            poke_info: 戳一戳信息字典（v1.0.9新增）。
                注意：本方法内未使用此参数，戳一戳提示已改为由上层流程
                （build_persistent_poke_event_text + format_context_for_ai）注入。
                保留此参数仅为兼容旧调用签名，传值无实际效果。
            is_empty_at: 是否是单独无信息@消息（只有@没有其他内容）
            recent_pending_summary: 已弃用。替补见 _build_single_at_message_context +
                _build_single_at_message_reply_hint（main.py）。
                保留参数仅用于兼容旧调用，传 "" 即可。
            empty_at_context_prompt: 已弃用。替补见 _build_empty_at_context_prompt →
                _build_single_at_message_reply_hint（main.py）。
                保留参数仅用于兼容旧调用，传 "" 即可。

        Returns:
            添加元数据后的文本
        """
        try:
            # 收集所有系统元数据（冒号前的内容）
            system_parts = []

            # 1. 时间戳
            if include_timestamp:
                timestamp_str = MessageProcessor._format_timestamp_unified(event)
                if timestamp_str:
                    system_parts.append(f"[{timestamp_str}]")

            # 2. 发送者信息（不带冒号）
            if include_sender_info:
                sender_id = event.get_sender_id()
                sender_name = event.get_sender_name()
                display_name = (
                    sender_name
                    if (sender_name and sender_name != str(sender_id))
                    else ""
                )
                if display_name:
                    system_parts.append(
                        f"{display_name}(ID:{sender_id})" if sender_id else display_name
                    )
                elif sender_id:
                    system_parts.append(f"未知用户(ID:{sender_id})")
                else:
                    system_parts.append("未知用户")

                # 环境标注（与发送者信息合并，不另起一行）
                if include_environment_info:
                    gid = event.get_group_id()
                    if gid:
                        gname = ""
                        try:
                            msg_obj = getattr(event, "message_obj", None)
                            if msg_obj:
                                grp = getattr(msg_obj, "group", None)
                                if grp:
                                    gn = getattr(grp, "group_name", None)
                                    if gn and str(gn).strip():
                                        gname = str(gn).strip()
                        except Exception:
                            pass
                        env_tag = MessageProcessor._build_environment_tag(gname, str(gid))
                        if env_tag:
                            system_parts.append(env_tag)

                # 群身份标签（紧跟在发送者信息和环境标注之后）
                if group_role and group_role.strip():
                    system_parts.append(f"[{group_role.strip()}]")

            # 3. @指向说明
            mention_notice = MessageProcessor.build_mention_direction_notice(
                mention_info
            )
            if mention_notice:
                system_parts.append(mention_notice)

            # 4. 戳一戳提示不由 message_processor 注入（因此 poke_info 参数在本方法内未使用），
            # 而是由主流程在消息组装完成后追加到消息下方（分隔符之内），
            # 保存时由 MessageCleaner.FILTER_RULES 自动过滤。
            # 替补链路：
            #   A. build_persistent_poke_event_text(poke_info) → persistent_poke_event_text
            #   B. main.py 从 poke_info 构建 _poke_notice_text → format_context_for_ai 追加

            # 5. @全体成员说明
            has_at_all = bool(
                is_at_all_message
                or MessageProcessor._normalize_mention_info(mention_info).get(
                    "has_at_all", False
                )
            )
            if has_at_all:
                system_parts.append(
                    "【@全体成员说明】这是一条@全体成员消息。它也包含你，但不一定是专门只对你说的。"
                )
                if DEBUG_MODE:
                    logger.info("已添加@全体成员说明（当前消息）")

            # 6. 发送者识别系统提示（根据触发方式）
            if include_sender_info and trigger_type:
                sender_id = event.get_sender_id()
                sender_name = event.get_sender_name()
                display_name = (
                    sender_name
                    if (sender_name and sender_name != str(sender_id))
                    else ""
                )
                if display_name:
                    sender_info_text = (
                        f"{display_name}(ID:{sender_id})" if sender_id else display_name
                    )
                elif sender_id:
                    sender_info_text = f"未知用户(ID:{sender_id})"
                else:
                    sender_info_text = "未知用户"

                if trigger_type == "at":
                    if is_empty_at:
                        system_notice = (
                            f"[系统提示]{sender_info_text} 单独@了你，没有附带任何消息内容。"
                            f"自然回应就好。"
                        )
                    else:
                        system_notice = (
                            f"[系统提示]注意，现在有人在直接@你并且给你发送了这条消息，"
                            f"@你的那个人是{sender_info_text}"
                        )
                elif trigger_type == "keyword":
                    system_notice = (
                        f"[系统提示]注意，这条消息中出现了和你有关的信息，"
                        f"发送者是{sender_info_text}。"
                        f"请先结合最近上下文理解对方现在在聊什么、这句话主要是对谁说的，"
                        f"然后像正常聊天一样自然回应。"
                    )
                elif trigger_type == "ai_decision":
                    system_notice = f"[系统提示]注意，你看到了这条消息，发送这条消息的人是{sender_info_text}"
                else:
                    system_notice = ""

                if system_notice:
                    system_parts.append(system_notice)
                    if DEBUG_MODE:
                        logger.info(f"已添加发送者识别提示（触发方式: {trigger_type}）")

            # 7. 持久化戳一戳事件文本
            if persistent_poke_event_text and persistent_poke_event_text.strip():
                system_parts.append(persistent_poke_event_text.strip())

            # 8. 戳过对方提示
            if poke_trace_text and poke_trace_text.strip():
                system_parts.append(poke_trace_text.strip())

            # 用户消息内容（含内联@解析）
            user_part = MessageProcessor.inline_resolve_mentions(
                message_text, mention_info
            )

            # 组装：冒号前是系统元数据，冒号后是用户消息
            if system_parts:
                result = " ".join(system_parts) + ": " + user_part
            else:
                result = user_part

            if DEBUG_MODE and system_parts:
                logger.info(
                    f"消息已添加元数据（新格式，冒号为系统/用户边界）: "
                    f"{' '.join(system_parts)} | {user_part[:50]}..."
                )

            return result

        except Exception as e:
            logger.error(f"添加消息元数据时发生错误: {e}")
            # 发生错误时返回原始消息
            return message_text

    @staticmethod
    # 兼容旧调用：empty_at_context_prompt 已弃用，
    # 但缓存转正与若干保存链路仍沿用原签名，暂时保留参数以避免影响功能。
    #   - empty_at_context_prompt 替补：
    #     _build_single_at_message_context + _build_single_at_message_reply_hint（main.py）。
    #   - poke_info 在本方法内未使用，保留参数仅为兼容旧签名。替补链路同 add_metadata_to_message。
    def add_metadata_from_cache(
        message_text: str,
        sender_id: str,
        sender_name: str,
        message_timestamp: float,
        include_timestamp: bool,
        include_sender_info: bool,
        mention_info: dict = None,
        trigger_type: str = None,
        poke_info: dict = None,
        is_empty_at: bool = False,
        empty_at_context_prompt: str = "",
        is_at_all_message: bool = False,
        *,
        persistent_poke_event_text: str = "",
        poke_trace_text: str = "",
        include_environment_info: bool = False,
        group_id: str = "",
        group_name: str = "",
        group_role: str = "",
    ) -> str:
        """
        使用缓存中的发送者信息为消息添加元数据

        格式与历史消息保持一致：[时间] 发送者名字(ID:xxx): 消息内容

        用于缓存消息转正时，使用原始发送者的信息而不是当前event的发送者

        Args:
            message_text: 消息文本
            sender_id: 发送者ID（从缓存中获取）
            sender_name: 发送者名称（从缓存中获取）
            message_timestamp: 消息时间戳（从缓存中获取）
            include_timestamp: 是否包含时间戳
            include_sender_info: 是否包含发送者信息
            mention_info: 统一的@解析结果（可包含@AI/@他人/@全体、重复@等复合场景）
            trigger_type: 触发方式，可选值: "at", "keyword", "ai_decision"
            poke_info: 戳一戳信息字典（v1.0.9新增）。
                注意：本方法内未使用此参数，替补路径同 add_metadata_to_message。
                保留此参数仅为兼容旧调用签名。
            is_empty_at: 是否是单独无信息@消息（只有@没有其他内容）
            empty_at_context_prompt: 已弃用。替补见 _build_empty_at_context_prompt →
                _build_single_at_message_reply_hint（main.py）。
                保留参数仅用于兼容旧调用，传 "" 即可。

        Returns:
            添加元数据后的文本
        """
        try:
            # 收集所有系统元数据（冒号前的内容）
            system_parts = []

            # 1. 时间戳
            if include_timestamp and message_timestamp:
                try:
                    dt = datetime.fromtimestamp(message_timestamp)
                    weekday_names = [
                        "周一",
                        "周二",
                        "周三",
                        "周四",
                        "周五",
                        "周六",
                        "周日",
                    ]
                    weekday = weekday_names[dt.weekday()]
                    timestamp_str = dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")
                except Exception:
                    dt = datetime.now()
                    weekday_names = [
                        "周一",
                        "周二",
                        "周三",
                        "周四",
                        "周五",
                        "周六",
                        "周日",
                    ]
                    weekday = weekday_names[dt.weekday()]
                    timestamp_str = dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")
                system_parts.append(f"[{timestamp_str}]")

            # 2. 发送者信息（不带冒号）
            if include_sender_info:
                display_name = (
                    sender_name
                    if (sender_name and sender_name != str(sender_id))
                    else ""
                )
                if display_name:
                    system_parts.append(
                        f"{display_name}(ID:{sender_id})" if sender_id else display_name
                    )
                elif sender_id:
                    system_parts.append(f"未知用户(ID:{sender_id})")
                else:
                    system_parts.append("未知用户")

                # 环境标注（与发送者信息合并，不另起一行）
                if include_environment_info and group_id:
                    env_tag = MessageProcessor._build_environment_tag(group_name or "", str(group_id))
                    if env_tag:
                        system_parts.append(env_tag)

                # 群身份标签（紧跟在发送者信息和环境标注之后）
                if group_role and group_role.strip():
                    system_parts.append(f"[{group_role.strip()}]")

            # 3. @指向说明
            mention_notice = MessageProcessor.build_mention_direction_notice(
                mention_info
            )
            if mention_notice:
                system_parts.append(mention_notice)

            # 4. 戳一戳提示不由 message_processor 注入（因此 poke_info 参数在本方法内未使用），
            # 而是由主流程在消息组装完成后追加到消息下方（分隔符之内），
            # 保存时由 MessageCleaner.FILTER_RULES 自动过滤。
            # 替补链路：
            #   A. build_persistent_poke_event_text(poke_info) → persistent_poke_event_text
            #   B. main.py 从 poke_info 构建 _poke_notice_text → format_context_for_ai 追加

            # 5. @全体成员说明
            has_at_all = bool(
                is_at_all_message
                or MessageProcessor._normalize_mention_info(mention_info).get(
                    "has_at_all", False
                )
            )
            if has_at_all:
                system_parts.append(
                    "【@全体成员说明】这是一条@全体成员消息。它也包含你，但不一定是专门只对你说的。"
                )
                logger.info("已添加@全体成员说明（从缓存）")

            # 6. 发送者识别系统提示（根据触发方式）
            if include_sender_info and trigger_type:
                display_name = (
                    sender_name
                    if (sender_name and sender_name != str(sender_id))
                    else ""
                )
                if display_name:
                    sender_info_text = (
                        f"{display_name}(ID:{sender_id})" if sender_id else display_name
                    )
                elif sender_id:
                    sender_info_text = f"未知用户(ID:{sender_id})"
                else:
                    sender_info_text = "未知用户"

                if trigger_type == "at":
                    if is_empty_at:
                        system_notice = (
                            f"[系统提示]{sender_info_text} 单独@了你，没有附带任何消息内容，"
                            f"可能只是叫你出来，也可能是有事想说——自然回应就好。"
                        )
                    else:
                        system_notice = (
                            f"[系统提示]注意，现在有人在直接@你并且给你发送了这条消息，"
                            f"@你的那个人是{sender_info_text}"
                        )
                elif trigger_type == "keyword":
                    system_notice = f"[系统提示]注意，你刚刚发现这条消息里面包含和你有关的信息，这条消息的发送者是{sender_info_text}"
                elif trigger_type == "ai_decision":
                    system_notice = f"[系统提示]注意，你看到了这条消息，发送这条消息的人是{sender_info_text}"
                else:
                    system_notice = ""

                if system_notice:
                    system_parts.append(system_notice)
                    logger.info(
                        f"已添加发送者识别提示（从缓存，触发方式: {trigger_type}）"
                    )

            # 7. 持久化戳一戳事件文本
            if persistent_poke_event_text and persistent_poke_event_text.strip():
                system_parts.append(persistent_poke_event_text.strip())

            # 8. 戳过对方提示
            if poke_trace_text and poke_trace_text.strip():
                system_parts.append(poke_trace_text.strip())

            # 用户消息内容（含内联@解析）
            user_part = MessageProcessor.inline_resolve_mentions(
                message_text, mention_info
            )

            # 组装：冒号前是系统元数据，冒号后是用户消息
            if system_parts:
                result = " ".join(system_parts) + ": " + user_part
            else:
                result = user_part

            if system_parts:
                logger.info(
                    f"消息已添加元数据（从缓存，新格式，冒号为系统/用户边界）: "
                    f"{' '.join(system_parts)} | {user_part[:50]}..."
                )

            return result

        except Exception as e:
            logger.error(f"从缓存添加消息元数据时发生错误: {e}")
            # 发生错误时返回原始消息
            return message_text

    @staticmethod
    def _format_timestamp_unified(event: AstrMessageEvent) -> str:
        """
        格式化时间戳（统一格式，与历史消息一致）

        格式：YYYY-MM-DD HH:MM:SS

        Args:
            event: 消息事件

        Returns:
            格式化的时间戳，失败返回空
        """
        try:
            # 尝试从消息对象获取时间戳
            if hasattr(event, "message_obj") and hasattr(
                event.message_obj, "timestamp"
            ):
                timestamp = event.message_obj.timestamp
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp)
                    weekday_names = [
                        "周一",
                        "周二",
                        "周三",
                        "周四",
                        "周五",
                        "周六",
                        "周日",
                    ]
                    weekday = weekday_names[dt.weekday()]
                    return dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")

            # 如果消息对象没有时间戳,使用当前时间
            dt = datetime.now()
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            weekday = weekday_names[dt.weekday()]
            return dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")

        except Exception as e:
            logger.warning(f"格式化时间戳失败: {e}")
            return ""

    @staticmethod
    def _format_timestamp(event: AstrMessageEvent) -> str:
        """
        格式化时间戳（旧格式，保留用于兼容性）

        格式：YYYY年MM月DD日 HH:MM:SS

        Args:
            event: 消息事件

        Returns:
            格式化的时间戳，失败返回空
        """
        try:
            # 尝试从消息对象获取时间戳
            if hasattr(event, "message_obj") and hasattr(
                event.message_obj, "timestamp"
            ):
                timestamp = event.message_obj.timestamp
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp)
                    weekday_names = [
                        "周一",
                        "周二",
                        "周三",
                        "周四",
                        "周五",
                        "周六",
                        "周日",
                    ]
                    weekday = weekday_names[dt.weekday()]
                    return dt.strftime(f"%Y年%m月%d日 {weekday} %H:%M:%S")

            # 如果消息对象没有时间戳,使用当前时间
            dt = datetime.now()
            weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            weekday = weekday_names[dt.weekday()]
            return dt.strftime(f"%Y年%m月%d日 {weekday} %H:%M:%S")

        except Exception as e:
            logger.warning(f"格式化时间戳失败: {e}")
            return ""

    @staticmethod
    def _format_sender_info(event: AstrMessageEvent) -> str:
        """
        格式化发送者信息

        格式：[发送者: 昵称(ID: user_id)]

        Args:
            event: 消息事件

        Returns:
            格式化的发送者信息，失败返回空
        """
        try:
            sender_id = event.get_sender_id()
            sender_name = event.get_sender_name()
            display_name = (
                sender_name if (sender_name and sender_name != str(sender_id)) else ""
            )

            if display_name:
                return (
                    f"[发送者: {display_name}(ID: {sender_id})]"
                    if sender_id
                    else f"[发送者: {display_name}]"
                )
            elif sender_id:
                return f"[发送者: 未知用户(ID: {sender_id})]"
            else:
                return "[发送者: 未知用户]"

        except Exception as e:
            logger.warning(f"格式化发送者信息失败: {e}")
            return ""

    @staticmethod
    def is_message_from_bot(event: AstrMessageEvent) -> bool:
        """
        判断消息是否来自bot自己

        避免bot回复自己导致循环

        Args:
            event: 消息事件

        Returns:
            True=bot自己的消息，False=其他人
        """
        try:
            sender_id = event.get_sender_id()
            bot_id = event.get_self_id()

            # 如果发送者ID等于机器人ID,说明是自己发的
            is_bot = sender_id == bot_id

            if is_bot:
                logger.info(
                    f"检测到机器人自己的消息,将忽略: sender_id={sender_id}, bot_id={bot_id}"
                )

            return is_bot

        except Exception as e:
            logger.error(f"判断消息来源时发生错误: {e}")
            # 发生错误时,为安全起见,返回True避免处理可能有问题的消息
            return True

    @staticmethod
    def is_at_message(event: AstrMessageEvent) -> bool:
        """
        判断消息是否@了bot

        @消息需跳过读空气直接回复

        支持两种@方式：
        1. At组件（标准方式）
        2. 文本形式的@ （兼容旧版本QQ，如：@小明）

        Args:
            event: 消息事件

        Returns:
            True=@了bot，False=没有@
        """
        try:
            # 方法1: 检查消息链中是否有At组件指向机器人（优先使用）
            if hasattr(event, "message_obj") and hasattr(event.message_obj, "message"):
                bot_id = event.get_self_id()
                message_chain = event.message_obj.message

                for component in message_chain:
                    if isinstance(component, At):
                        # 检查At的目标是否是机器人
                        if hasattr(component, "qq") and str(component.qq) == str(
                            bot_id
                        ):
                            if DEBUG_MODE:
                                logger.info("检测到@机器人的消息（At组件）")
                            return True

            # 方法2: 检查消息文本中是否包含@机器人（兼容旧版本QQ）
            # 获取机器人的名称和ID
            try:
                bot_id = event.get_self_id()
                # 尝试获取机器人昵称（如果有的话）
                bot_name = None
                if hasattr(event, "unified_msg_origin"):
                    # 从 unified_msg_origin 中提取机器人名称
                    # 格式通常是：BotName:MessageType:ChatID
                    origin_parts = str(event.unified_msg_origin).split(":")
                    if len(origin_parts) > 0:
                        bot_name = origin_parts[0]

                # 获取消息文本
                message_text = event.get_message_str()

                # 强制日志：显示文本@检测的详细信息（用于排查）
                if DEBUG_MODE:
                    logger.info(
                        f"[文本@检测] bot_id={bot_id}, bot_name={bot_name}, message={message_text[:50] if message_text else 'None'}"
                    )

                # 检查是否包含 @机器人ID 或 @机器人名称
                if message_text:
                    # 检查 @机器人ID
                    if f"@{bot_id}" in message_text:
                        if DEBUG_MODE:
                            logger.info(f"检测到@机器人的消息（文本@ID: @{bot_id}）")
                        return True

                    # 检查 @机器人名称（支持部分匹配，如 @Monika(AI) 也能匹配 @Monika）
                    if bot_name:
                        # 使用 startswith 检查 @bot_name 后面可以跟任何字符
                        # 检查是否有 @bot_name 后面跟着非字母数字（如空格、括号等）或字符串结束
                        pattern = rf"@{re.escape(bot_name)}(?:[^a-zA-Z0-9_]|$)"
                        if re.search(pattern, message_text):
                            if DEBUG_MODE:
                                logger.info(
                                    f"检测到@机器人的消息（文本@名称: @{bot_name}）"
                                )
                            return True
            except Exception as e:
                if DEBUG_MODE:
                    logger.info(f"文本@检测时出错: {e}")

            return False

        except Exception as e:
            logger.error(f"判断@消息时发生错误: {e}")
            return False
