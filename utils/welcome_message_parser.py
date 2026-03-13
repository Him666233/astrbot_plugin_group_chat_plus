"""
新成员入群消息解析器 - Welcome Message Parser

将 QQ 群新成员加入事件（group_increase）解析为系统提示文本，
让 AI 能正确理解"有新人加入"而非误判为空消息。

支持平台：aiocqhttp (OneBot v11) - 需配合 NapCat、Lagrange 等 OneBot 实现
其他平台：自动跳过，不影响正常使用

所有配置通过方法参数传入，本模块不直接读取任何配置。
"""

import time
from datetime import datetime
from typing import Optional, Tuple

from astrbot.api import logger
from astrbot.core.message.components import Plain
from astrbot.core.platform.astr_message_event import AstrMessageEvent


class WelcomeMessageParser:
    """新成员入群消息解析器"""

    @staticmethod
    async def try_parse_and_replace(
        event: AstrMessageEvent,
        include_sender_info: bool,
        include_timestamp: bool,
        debug_mode: bool = False,
    ) -> bool:
        """
        检测事件是否为新成员入群通知，如果是则将空消息替换为系统提示文本。

        Args:
            event: AstrBot 消息事件
            include_sender_info: 是否包含成员信息（名字+ID）
            include_timestamp: 是否包含时间戳
            debug_mode: 是否输出调试日志

        Returns:
            True 表示检测到并成功解析了入群事件，False 表示非入群事件或不支持的平台。
        """
        try:
            raw = _get_raw_message(event)
            if raw is None:
                return False

            # 检查是否为 group_increase 事件
            if not (
                isinstance(raw, dict)
                and raw.get("post_type") == "notice"
                and raw.get("notice_type") == "group_increase"
            ):
                return False

            # 排除机器人自身入群
            if raw.get("user_id") == raw.get("self_id"):
                if debug_mode:
                    logger.info("[入群解析] 机器人自身入群事件，跳过")
                return False

            user_id = str(raw.get("user_id", ""))
            group_id = str(raw.get("group_id", ""))
            sub_type = raw.get("sub_type", "approve")  # approve / invite

            # 尝试获取新成员昵称
            nickname = await _try_get_member_nickname(
                event, user_id, group_id, debug_mode
            )

            # 构建系统提示文本
            prompt_text = _build_welcome_prompt(
                nickname=nickname,
                user_id=user_id,
                sub_type=sub_type,
                include_sender_info=include_sender_info,
                include_timestamp=include_timestamp,
                timestamp=getattr(event.message_obj, "timestamp", 0)
                or int(time.time()),
            )

            # 替换消息链和 message_str
            event.message_obj.message = [Plain(text=prompt_text)]
            event.message_obj.message_str = prompt_text
            event.message_str = prompt_text

            if debug_mode:
                logger.info(f"[入群解析] 已解析新成员入群事件: {prompt_text}")

            return True

        except Exception as e:
            logger.warning(f"[入群解析] 解析入群事件时发生异常（已跳过）: {e}")
            return False


def _get_raw_message(event: AstrMessageEvent):
    """安全获取 raw_message"""
    try:
        if hasattr(event, "message_obj") and hasattr(event.message_obj, "raw_message"):
            return event.message_obj.raw_message
    except Exception:
        pass
    return None


async def _try_get_member_nickname(
    event: AstrMessageEvent,
    user_id: str,
    group_id: str,
    debug_mode: bool,
) -> str:
    """
    尝试通过 API 获取新成员昵称。
    失败时回退到 sender.nickname 或 user_id。
    """
    # 先尝试从 event.sender 获取（适配器可能已设置）
    fallback = ""
    try:
        sender = getattr(event.message_obj, "sender", None)
        if sender:
            fallback = getattr(sender, "nickname", "") or ""
    except Exception:
        pass

    # 尝试通过 call_action 获取更准确的昵称
    try:
        bot = getattr(event, "bot", None)
        if bot is None:
            return fallback or user_id

        call_action = getattr(bot, "call_action", None)
        if not callable(call_action):
            api = getattr(bot, "api", None)
            if api:
                call_action = getattr(api, "call_action", None)
        if not callable(call_action):
            return fallback or user_id

        # 尝试 get_group_member_info
        try:
            result = await call_action(
                "get_group_member_info",
                group_id=int(group_id) if group_id.isdigit() else group_id,
                user_id=int(user_id) if user_id.isdigit() else user_id,
            )
            if isinstance(result, dict):
                nick = (
                    result.get("card")
                    or result.get("nickname")
                    or result.get("user_name")
                    or ""
                )
                if nick:
                    return nick
                # 可能在 data 字段里
                data = result.get("data")
                if isinstance(data, dict):
                    nick = data.get("card") or data.get("nickname") or ""
                    if nick:
                        return nick
        except Exception as e:
            if debug_mode:
                logger.debug(f"[入群解析] get_group_member_info 失败: {e}")

    except Exception as e:
        if debug_mode:
            logger.debug(f"[入群解析] 获取昵称失败: {e}")

    return fallback or user_id


def _build_welcome_prompt(
    nickname: str,
    user_id: str,
    sub_type: str,
    include_sender_info: bool,
    include_timestamp: bool,
    timestamp: int,
) -> str:
    """构建入群系统提示文本"""
    parts = []

    # 时间戳
    if include_timestamp and timestamp and timestamp > 0:
        time_str = _format_timestamp(timestamp)
        if time_str:
            parts.append(f"[{time_str}]")

    # 系统提示标签
    parts.append("[系统提示]")

    # 入群方式
    join_method = "被邀请加入" if sub_type == "invite" else "加入"

    # 成员信息
    if include_sender_info and (nickname or user_id):
        if nickname and nickname != user_id:
            parts.append(f"新成员 {nickname}(ID:{user_id}) {join_method}了群聊")
        else:
            parts.append(f"新成员(ID:{user_id}) {join_method}了群聊")
    else:
        parts.append(f"有新成员{join_method}了群聊")

    return " ".join(parts)


def _format_timestamp(unix_timestamp: int) -> str:
    """将 Unix 时间戳格式化为可读字符串（与插件其他部分保持一致）"""
    try:
        if not unix_timestamp or unix_timestamp <= 0:
            return ""
        dt = datetime.fromtimestamp(unix_timestamp)
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[dt.weekday()]
        return dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")
    except Exception:
        return ""
