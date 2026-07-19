"""
Identity Prompt 身份提示模块
向 AI 注入当前环境中的账号名称/ID 以及（可选）聊天环境名称/ID

核心原则：
- 提示词使用中性语言，区分"平台账号标识"和"人格身份"
- 任何字段获取失败时使用占位符回退
- 全部字段未知时返回空字符串，调用方跳过注入

作者: Him666233
"""

import asyncio
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 标签常量
IDENTITY_TAG = "[系统信息-自身身份]"
ENVIRONMENT_TAG = "[系统信息-当前环境]"

# 占位符常量
PLACEHOLDER_NAME = "[未知名称]"
PLACEHOLDER_ID = "[未知ID]"
PLACEHOLDER_GROUP_NAME = "[未知群名]"
PLACEHOLDER_GROUP_ID = "[未知群ID]"

# group_info 异步获取超时（秒）
GROUP_INFO_TIMEOUT = 5.0


class IdentityPromptBuilder:
    """构建统一的身份提示文本。所有字段都有占位符回退，全空返回空字符串。"""

    # ── 提示词模板（中性措辞，条件化人格说明） ──

    _IDENTITY_BLOCK_TEMPLATE = (
        "\n\n{IDENTITY_TAG}\n"
        "当前环境中你使用的账号名称: {self_name}\n"
        "当前环境中你使用的账号ID: {self_id}\n"
        "{GROUP_ROLE_LINE}"
        "—— 以上为平台账号层面的标识信息。如果你当前拥有人格设定（persona），"
        "请以人格中定义的身份和名字为准；如果你没有人格设定，"
        "则将上述信息作为你在当前环境中的身份参考即可。\n"
    )

    _ENVIRONMENT_BLOCK_TEMPLATE = (
        "\n{ENVIRONMENT_TAG}\n"
        "当前聊天环境的名称: {group_name}\n"
        "当前聊天环境的ID: {group_id}\n"
        "—— 以上为你当前所处环境的基本参考信息。如果你当前拥有人格设定（persona），"
        "请结合人格来理解此环境；如果你没有人格设定，"
        "则将上述信息作为当前对话场景的参考即可。\n"
    )

    # ── 公开方法 ──

    @staticmethod
    def build(
        self_name: Optional[str] = None,
        self_id: Optional[str] = None,
        group_name: Optional[str] = None,
        group_id: Optional[str] = None,
        include_group_info: bool = False,
        group_role: Optional[str] = None,
        log_prefix: str = "[身份提示]",
    ) -> str:
        """
        构建身份提示文本块。

        Args:
            self_name: 当前环境中的账号名称，None → 占位符
            self_id:   当前环境中的账号 ID，None → 占位符
            group_name: 聊天环境名称，None → 占位符
            group_id:   聊天环境 ID，None → 占位符
            include_group_info: 是否追加环境信息块
            group_role: 当前环境中的群身份标签（群主/管理员/群成员），
                        None 或空字符串 → 不追加角色行
            log_prefix: 日志前缀

        Returns:
            格式化的提示文本块。
            如果没有任何有效信息（包括 self_name 和 self_id 均为空/None），返回 ""。
        """
        # 解析占位符
        resolved_name = (self_name or "").strip() or PLACEHOLDER_NAME
        resolved_id = (self_id or "").strip() or PLACEHOLDER_ID

        # 极端情况：自身名称和 ID 均无有效信息
        has_any_self_info = bool(
            (self_name or "").strip() or (self_id or "").strip()
        )
        if not has_any_self_info:
            logger.warning(
                f"{log_prefix} 自身名称和 ID 均为空/未知，跳过注入身份提示"
            )
            return ""

        # 构建群身份角色行（仅当传入有效角色时）
        resolved_role = (group_role or "").strip()
        if resolved_role:
            resolved_role_text = f"当前环境中你的身份: {resolved_role}\n"
        else:
            resolved_role_text = ""

        # 构建身份块
        identity_text = IdentityPromptBuilder._IDENTITY_BLOCK_TEMPLATE.format(
            IDENTITY_TAG=IDENTITY_TAG,
            self_name=resolved_name,
            self_id=resolved_id,
            GROUP_ROLE_LINE=resolved_role_text,
        )

        # 可选：构建环境块
        if include_group_info:
            resolved_group_name = (
                (group_name or "").strip() or PLACEHOLDER_GROUP_NAME
            )
            resolved_group_id = (
                (group_id or "").strip() or PLACEHOLDER_GROUP_ID
            )
            identity_text += IdentityPromptBuilder._ENVIRONMENT_BLOCK_TEMPLATE.format(
                ENVIRONMENT_TAG=ENVIRONMENT_TAG,
                group_name=resolved_group_name,
                group_id=resolved_group_id,
            )

        logger.info(
            f"{log_prefix} 已构建身份提示（self_name={resolved_name}, "
            f"self_id={resolved_id}, "
            f"group={'有' if include_group_info else '无'}）"
        )
        return identity_text

    # ── 辅助方法 ──

    @staticmethod
    def resolve_self_info(event) -> Tuple[Optional[str], str]:
        """
        从 event 中分层解析 self_name 和 self_id（同步回退版）。

        注意：AstrBot 框架各平台均未提供 get_self_name() 方法，
        因此 self_name 在同步路径下几乎总是 None。
        推荐使用 resolve_self_name_async() 异步获取 bot 自身名称。

        策略：
        1. event.get_self_id() → self_id（所有平台可用）
        2. hasattr(event, 'get_self_name') → self_name（平台通常不提供）
        3. 失败 → self_name 为 None（由 build() 填入占位符）

        Returns:
            (self_name: Optional[str], self_id: str)
        """
        self_id = ""
        self_name = None

        try:
            self_id = str(event.get_self_id() or "")
        except Exception:
            self_id = ""

        try:
            if hasattr(event, "get_self_name") and callable(event.get_self_name):
                name = event.get_self_name()
                if name and str(name).strip():
                    self_name = str(name).strip()
        except Exception:
            pass

        return self_name, self_id

    @staticmethod
    async def resolve_self_name_async(event=None, *, bot=None) -> Optional[str]:
        """
        异步获取 bot 自身的账号名称，支持多种平台。

        Args:
            event: AstrMessageEvent（有则优先从中提取 bot / raw_message）
            bot:  平台客户端实例（无 event 时使用，如主动对话场景）

        策略（按优先级）：
        1. event.get_self_name() → 同步方法（部分平台可能未来支持）
        2. bot.call_action("get_login_info") → OneBot/aiocqhttp 平台
        3. event.message_obj.raw_message → 部分扩展实现可能携带 self_nickname
        4. 全部失败 → 返回 None（由 build() 填入占位符 [未知名称]）

        Returns:
            bot 的账号名称，失败返回 None
        """
        # 第 1 层：同步 get_self_name（框架未来可能支持）
        if event is not None:
            try:
                if hasattr(event, "get_self_name") and callable(event.get_self_name):
                    name = event.get_self_name()
                    if name and str(name).strip():
                        return str(name).strip()
            except Exception:
                pass

        # 第 2 层：通过 bot 实例调用 get_login_info API
        # （aiocqhttp / OneBot V11 标准）
        _bot = bot
        if _bot is None and event is not None:
            _bot = getattr(event, "bot", None)
        if _bot is not None:
            nick = await IdentityPromptBuilder._try_get_login_info(_bot)
            if nick:
                return nick

        # 第 3 层：从 raw_message 中尝试提取
        # （部分扩展实现如 NapCat/LLOneBot 可能在 notice 中携带 self_nickname）
        if event is not None:
            try:
                msg_obj = getattr(event, "message_obj", None)
                if msg_obj is not None:
                    raw = getattr(msg_obj, "raw_message", None)
                    if isinstance(raw, dict):
                        for key in ("self_nickname", "self_name", "bot_nickname"):
                            val = raw.get(key)
                            if val and str(val).strip():
                                logger.info(
                                    f"[身份提示] 从 raw_message.{key} 获取 bot 名称: {val}"
                                )
                                return str(val).strip()
            except Exception:
                pass

        logger.info("[身份提示] 无法从任何来源获取 bot 自身名称，将使用占位符")
        return None

    @staticmethod
    async def _try_get_login_info(bot) -> Optional[str]:
        """通过 bot 实例调用 get_login_info 获取自身昵称。

        返回昵称字符串，失败返回 None。
        """
        try:
            call_action = getattr(bot, "call_action", None)
            if not callable(call_action):
                api = getattr(bot, "api", None)
                call_action = getattr(api, "call_action", None) if api else None
            if not callable(call_action):
                return None
            result = await asyncio.wait_for(
                call_action("get_login_info"),
                timeout=GROUP_INFO_TIMEOUT,
            )
            if isinstance(result, dict):
                nick = (
                    result.get("nickname")
                    or result.get("nick")
                    or ""
                )
                if nick and str(nick).strip():
                    logger.info(
                        f"[身份提示] 通过 get_login_info 获取 bot 名称: {nick}"
                    )
                    return str(nick).strip()
                data = result.get("data")
                if isinstance(data, dict):
                    nick = (
                        data.get("nickname")
                        or data.get("nick")
                        or ""
                    )
                    if nick and str(nick).strip():
                        logger.info(
                            f"[身份提示] 通过 get_login_info(data) 获取 bot 名称: {nick}"
                        )
                        return str(nick).strip()
        except asyncio.TimeoutError:
            logger.info(
                f"[身份提示] get_login_info 超时"
                f"（{GROUP_INFO_TIMEOUT}s），回退到占位符"
            )
        except Exception:
            pass
        return None

    @staticmethod
    async def resolve_group_info(
        event,
        group_id: str = "",
        include_group_info: bool = False,
    ) -> Tuple[Optional[str], str]:
        """
        分层解析 group_name 和 group_id。

        策略：
        1. event.message_obj.group.group_name → group_name（同步，最快）
        2. await event.get_group() → group_name（异步，QQ/Slack/Mattermost）
        3. 失败 → group_name 为 None（由 build() 填入占位符）

        所有异常内部捕获，永不抛出。

        Returns:
            (group_name: Optional[str], group_id: str)
        """
        if not include_group_info:
            return None, group_id

        resolved_group_id = group_id or ""
        group_name = None

        # 第 1 层：同步读取 message_obj.group.group_name
        try:
            msg_obj = getattr(event, "message_obj", None)
            if msg_obj is not None:
                group = getattr(msg_obj, "group", None)
                if group is not None:
                    gn = getattr(group, "group_name", None)
                    if gn and str(gn).strip():
                        group_name = str(gn).strip()
                        if not resolved_group_id:
                            resolved_group_id = str(
                                getattr(group, "group_id", "") or ""
                            )
                        logger.info(
                            f"[身份提示] 从 message_obj.group 获取群名: {group_name}"
                        )
        except Exception:
            pass

        # 第 2 层：异步调用 event.get_group()
        if group_name is None:
            try:
                get_group = getattr(event, "get_group", None)
                if get_group is not None and callable(get_group):
                    group_obj = await asyncio.wait_for(
                        get_group(), timeout=GROUP_INFO_TIMEOUT
                    )
                    if group_obj is not None:
                        gn = getattr(group_obj, "group_name", None)
                        if gn and str(gn).strip():
                            group_name = str(gn).strip()
                            if not resolved_group_id:
                                resolved_group_id = str(
                                    getattr(group_obj, "group_id", "") or ""
                                )
                            logger.info(
                                f"[身份提示] 从 event.get_group() 获取群名: {group_name}"
                            )
            except asyncio.TimeoutError:
                logger.info(
                    "[身份提示] event.get_group() 超时"
                    f"（{GROUP_INFO_TIMEOUT}s），回退到占位符"
                )
            except Exception:
                pass

        # 第 3 层：还是没拿到 → None，由 build() 填占位符
        if group_name is None:
            if not resolved_group_id:
                resolved_group_id = PLACEHOLDER_GROUP_ID
            logger.info("[身份提示] 无法获取群名，将使用占位符")

        return group_name, resolved_group_id

    @staticmethod
    def build_save_prefix(
        self_name: Optional[str] = None,
        self_id: Optional[str] = None,
        group_name: Optional[str] = None,
        group_id: Optional[str] = None,
        save_group_mode: str = "identity_only",
        group_role: Optional[str] = None,
        log_prefix: str = "[身份提示-保存]",
    ) -> str:
        """
        构建保存 AI 回复时的身份信息前缀。

        与 build() 不同，这是用于附加到保存的 AI 回复文本前面的简短标识，
        让 AI 在回看历史时能识别这条消息是哪个账号发出的。

        Args:
            self_name: 当前环境中的账号名称
            self_id:   当前环境中的账号 ID
            group_name: 聊天环境名称
            group_id:   聊天环境 ID
            save_group_mode: "identity_only" 仅附加账号信息，"with_group" 同时附加环境信息
            group_role: 当前环境中的群身份标签（群主/管理员/群成员），
                        None 或空字符串 → 不追加身份字段
            log_prefix: 日志前缀

        Returns:
            格式化的前缀字符串。如果 self_name 和 self_id 均为空，返回 ""。
        """
        resolved_name = (self_name or "").strip() or PLACEHOLDER_NAME
        resolved_id = (self_id or "").strip() or PLACEHOLDER_ID
        resolved_role = (group_role or "").strip()

        has_any_info = bool(
            (self_name or "").strip() or (self_id or "").strip()
        )
        if not has_any_info:
            logger.warning(
                f"{log_prefix} 自身名称和 ID 均为空/未知，跳过构建保存前缀"
            )
            return ""

        # 构建前缀
        if save_group_mode == "with_group":
            resolved_group_name = (
                (group_name or "").strip() or PLACEHOLDER_GROUP_NAME
            )
            resolved_group_id = (
                (group_id or "").strip() or PLACEHOLDER_GROUP_ID
            )
            if resolved_role:
                prefix = (
                    f"[账号: {resolved_name} | ID: {resolved_id}"
                    f" | 身份: {resolved_role}"
                    f" | 环境: {resolved_group_name} (ID: {resolved_group_id})]\n"
                )
            else:
                prefix = (
                    f"[账号: {resolved_name} | ID: {resolved_id}"
                    f" | 环境: {resolved_group_name} (ID: {resolved_group_id})]\n"
                )
        else:
            if resolved_role:
                prefix = (
                    f"[账号: {resolved_name} | ID: {resolved_id}"
                    f" | 身份: {resolved_role}]\n"
                )
            else:
                prefix = f"[账号: {resolved_name} | ID: {resolved_id}]\n"

        logger.info(
            f"{log_prefix} 已构建保存前缀（"
            f"名称={resolved_name}, ID={resolved_id}"
            f"{', 身份=' + resolved_role if resolved_role else ''}"
            f"{', 含环境信息' if save_group_mode == 'with_group' else ''}"
            f"）"
        )
        return prefix
