"""
消息处理器模块
负责消息预处理，添加时间戳、发送者信息等元数据

v1.0.4 更新：
- 添加发送者识别系统提示（根据触发方式）
- 在开启include_sender_info时，在消息末尾添加系统提示帮助AI识别发送者

作者: Him666233
版本: v1.2.1
"""

import re
from datetime import datetime
from astrbot.api.all import *
from astrbot.api.message_components import At, Plain

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
            mention_info: @别人的信息字典（如果存在）
            trigger_type: 触发方式，可选值: "at", "keyword", "ai_decision"
            poke_info: 戳一戳信息字典（v1.0.9新增，如果存在）
            is_empty_at: 是否是空@消息（只有@没有其他内容）
            recent_pending_summary: 最近缓存消息摘要文本（空@时直接嵌入提示词，避免AI在长历史中找不到）

        Returns:
            添加元数据后的文本
        """
        try:
            # 获取时间戳（格式：YYYY-MM-DD 星期几 HH:MM:SS，与历史消息一致）
            timestamp_str = ""
            if include_timestamp:
                timestamp_str = MessageProcessor._format_timestamp_unified(event)

            # 获取发送者信息
            sender_prefix = ""
            if include_sender_info:
                sender_id = event.get_sender_id()
                sender_name = event.get_sender_name()
                if sender_name:
                    # 格式：发送者名字(ID:xxx)，与历史消息完全一致
                    sender_prefix = f"{sender_name}(ID:{sender_id})"
                else:
                    sender_prefix = f"用户(ID:{sender_id})"

            # 组合格式：[时间] 发送者(ID:xxx): 消息内容
            # 与上下文格式化保持一致
            if timestamp_str and sender_prefix:
                processed_message = f"[{timestamp_str}] {sender_prefix}: {message_text}"
            elif timestamp_str:
                processed_message = f"[{timestamp_str}] {message_text}"
            elif sender_prefix:
                processed_message = f"{sender_prefix}: {message_text}"
            else:
                processed_message = message_text

            # 如果存在@别人的信息，添加系统提示
            if mention_info and isinstance(mention_info, dict):
                mentioned_id = mention_info.get("mentioned_user_id", "")
                mentioned_name = mention_info.get("mentioned_user_name", "")

                if mentioned_id:
                    # 构建系统提示（使用特殊标记【】，确保不会被MessageCleaner过滤）
                    # 注意：措辞要对决策AI和回复AI都适用，不要加"请判断是否回复"这种话
                    mention_notice = (
                        f"\n【@指向说明】这条消息通过@符号指定发送给其他用户"
                    )
                    if mentioned_name:
                        mention_notice += (
                            f"（被@用户：{mentioned_name}，ID：{mentioned_id}）"
                        )
                    else:
                        mention_notice += f"（被@用户ID：{mentioned_id}）"
                    mention_notice += "，并非发给你本人。"
                    mention_notice += f"\n【原始内容】{message_text}"

                    # 将原消息内容替换为包含系统提示的版本
                    # 保持元数据格式不变，只在消息内容部分添加提示
                    if timestamp_str and sender_prefix:
                        processed_message = (
                            f"[{timestamp_str}] {sender_prefix}: {mention_notice}"
                        )
                    elif timestamp_str:
                        processed_message = f"[{timestamp_str}] {mention_notice}"
                    elif sender_prefix:
                        processed_message = f"{sender_prefix}: {mention_notice}"
                    else:
                        processed_message = mention_notice

            if timestamp_str or sender_prefix:
                if DEBUG_MODE:
                    logger.info(
                        f"消息已添加元数据（统一格式）: [{timestamp_str}] {sender_prefix}"
                    )

            # 🆕 v1.0.9: 添加戳一戳系统提示（如果存在）
            # 注意：使用[]括号而非【】括号，确保能被MessageCleaner正确过滤
            if poke_info and isinstance(poke_info, dict):
                is_poke_bot = poke_info.get("is_poke_bot", False)
                poke_sender_id = poke_info.get("sender_id", "")
                poke_sender_name = poke_info.get("sender_name", "未知用户")
                poke_target_id = poke_info.get("target_id", "")
                poke_target_name = poke_info.get("target_name", "未知用户")

                if is_poke_bot:
                    # 戳的是机器人自己
                    poke_notice = f"\n[戳一戳提示]有人在戳你，戳你的人是{poke_sender_name}(ID:{poke_sender_id})"
                    if DEBUG_MODE:
                        logger.info(
                            f"已添加戳一戳提示（戳机器人）: 戳人者={poke_sender_name}"
                        )
                else:
                    # 戳的是别人
                    poke_notice = f"\n[戳一戳提示]这是一个戳一戳消息，但不是戳你的，是{poke_sender_name}(ID:{poke_sender_id})在戳{poke_target_name}(ID:{poke_target_id})"
                    if DEBUG_MODE:
                        logger.info(
                            f"已添加戳一戳提示（戳别人）: 戳人者={poke_sender_name}, 被戳者={poke_target_name}"
                        )

                processed_message += poke_notice

            # 🆕 v1.0.4: 添加发送者识别系统提示（根据触发方式）
            # 只在开启了 include_sender_info 的情况下添加
            if include_sender_info and trigger_type:
                sender_id = event.get_sender_id()
                sender_name = event.get_sender_name()
                sender_info_text = (
                    f"{sender_name}(ID:{sender_id})"
                    if sender_name
                    else f"用户(ID:{sender_id})"
                )

                # 根据触发方式添加不同的系统提示
                if trigger_type == "at":
                    # @消息触发
                    # 🔧 修复：区分空@消息和带消息的@消息，给AI不同的提示
                    if is_empty_at:
                        # 纯@消息（没有文字内容）
                        if recent_pending_summary:
                            # 🆕 有近期缓存消息且时间差在阈值内：展示上下文，让AI自行判断意图
                            system_notice = (
                                f"\n\n[系统提示]{sender_info_text} 只是单纯@了你，没有附带任何新的消息内容。\n"
                                f"📋 以下是@你之前群里刚刚出现的最近几条消息（可能来自不同的人）：\n"
                                f"{recent_pending_summary}\n\n"
                                f"🤔 请你像真人一样判断这个情况：\n"
                                f"- 这个人@你，是想让你接着上面这些内容说/回答吗？\n"
                                f"- 还是ta只是随便叫一下你，并不一定想让你回应那些话？\n"
                                f"- 哪怕是同一个人之前自己发的消息，也不代表ta现在@你就一定是要你回应那些。\n"
                                f"⚠️ 不要默认必须回答上面那几条消息。如果你判断不清楚ta到底想让你干什么，"
                                f"就自然地问一句，比如「？」或者「怎么了」，就像真人一样。"
                            )
                        else:
                            # 无近期缓存（时间间隔过久或本就没有）：自然询问，无需搜索历史
                            system_notice = (
                                f"\n\n[系统提示]{sender_info_text} 单独@了你，但没有附带任何消息内容，"
                                f"而且近期没有需要你特别接上的上下文。\n"
                                f"💬 就像真人收到一条无内容@消息一样，自然地回应就好——"
                                f"可以问句「？」或「怎么了，找我有事吗？」之类的话。"
                            )
                    else:
                        # @消息+文字内容
                        system_notice = (
                            f"\n\n[系统提示]注意，现在有人在直接@你并且给你发送了这条消息，"
                            f"@你的那个人是{sender_info_text}"
                        )
                elif trigger_type == "keyword":
                    # 关键词触发：提示AI仔细观察上下文，自然判断如何回复
                    system_notice = (
                        f"\n\n[系统提示]注意，你刚刚发现这条消息里面包含和你有关的信息，"
                        f"这条消息的发送者是{sender_info_text}。\n"
                        f"🔍 请仔细观察上下文和对话走向，结合发送者的实际意图，"
                        f"像真人一样自然地决定怎么回复——不要只因为关键词就机械回应。"
                    )
                elif trigger_type == "ai_decision":
                    # AI主动回复（中性描述，不预设结果）
                    system_notice = f"\n\n[系统提示]注意，你看到了这条消息，发送这条消息的人是{sender_info_text}"
                else:
                    system_notice = ""

                if system_notice:
                    processed_message += system_notice
                    if DEBUG_MODE:
                        logger.info(f"已添加发送者识别提示（触发方式: {trigger_type}）")

            return processed_message

        except Exception as e:
            logger.error(f"添加消息元数据时发生错误: {e}")
            # 发生错误时返回原始消息
            return message_text

    @staticmethod
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
            mention_info: @别人的信息字典（如果存在）
            trigger_type: 触发方式，可选值: "at", "keyword", "ai_decision"
            poke_info: 戳一戳信息字典（v1.0.9新增，如果存在）
            is_empty_at: 是否是空@消息（只有@没有其他内容）

        Returns:
            添加元数据后的文本
        """
        try:
            # 获取时间戳（格式：YYYY-MM-DD 星期几 HH:MM:SS）
            timestamp_str = ""
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
                except:
                    # 如果时间戳转换失败，使用当前时间
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

            # 获取发送者信息
            sender_prefix = ""
            if include_sender_info:
                if sender_name:
                    # 格式：发送者名字(ID:xxx)，与历史消息完全一致
                    sender_prefix = f"{sender_name}(ID:{sender_id})"
                else:
                    sender_prefix = f"用户(ID:{sender_id})"

            # 组合格式：[时间] 发送者(ID:xxx): 消息内容
            if timestamp_str and sender_prefix:
                processed_message = f"[{timestamp_str}] {sender_prefix}: {message_text}"
            elif timestamp_str:
                processed_message = f"[{timestamp_str}] {message_text}"
            elif sender_prefix:
                processed_message = f"{sender_prefix}: {message_text}"
            else:
                processed_message = message_text

            # 如果存在@别人的信息，添加系统提示
            if mention_info and isinstance(mention_info, dict):
                mentioned_id = mention_info.get("mentioned_user_id", "")
                mentioned_name = mention_info.get("mentioned_user_name", "")

                if mentioned_id:
                    # 构建系统提示（使用特殊标记【】，确保不会被MessageCleaner过滤）
                    # 注意：措辞要对决策AI和回复AI都适用，不要加"请判断是否回复"这种话
                    mention_notice = (
                        f"\n【@指向说明】这条消息通过@符号指定发送给其他用户"
                    )
                    if mentioned_name:
                        mention_notice += (
                            f"（被@用户：{mentioned_name}，ID：{mentioned_id}）"
                        )
                    else:
                        mention_notice += f"（被@用户ID：{mentioned_id}）"
                    mention_notice += "，并非发给你本人。"
                    mention_notice += f"\n【原始内容】{message_text}"

                    # 将原消息内容替换为包含系统提示的版本
                    # 保持元数据格式不变，只在消息内容部分添加提示
                    if timestamp_str and sender_prefix:
                        processed_message = (
                            f"[{timestamp_str}] {sender_prefix}: {mention_notice}"
                        )
                    elif timestamp_str:
                        processed_message = f"[{timestamp_str}] {mention_notice}"
                    elif sender_prefix:
                        processed_message = f"{sender_prefix}: {mention_notice}"
                    else:
                        processed_message = mention_notice

            if timestamp_str or sender_prefix:
                logger.info(
                    f"消息已添加元数据（从缓存，统一格式）: [{timestamp_str}] {sender_prefix}"
                )

            # 🆕 v1.0.9: 添加戳一戳系统提示（如果存在）
            # 注意：使用[]括号而非【】括号，确保能被MessageCleaner正确过滤
            if poke_info and isinstance(poke_info, dict):
                is_poke_bot = poke_info.get("is_poke_bot", False)
                poke_sender_id = poke_info.get("sender_id", "")
                poke_sender_name = poke_info.get("sender_name", "未知用户")
                poke_target_id = poke_info.get("target_id", "")
                poke_target_name = poke_info.get("target_name", "未知用户")

                if is_poke_bot:
                    # 戳的是机器人自己
                    poke_notice = f"\n[戳一戳提示]有人在戳你，戳你的人是{poke_sender_name}(ID:{poke_sender_id})"
                    logger.info(
                        f"已添加戳一戳提示（戳机器人）: 戳人者={poke_sender_name}"
                    )
                else:
                    # 戳的是别人
                    poke_notice = f"\n[戳一戳提示]这是一个戳一戳消息，但不是戳你的，是{poke_sender_name}(ID:{poke_sender_id})在戳{poke_target_name}(ID:{poke_target_id})"
                    logger.info(
                        f"已添加戳一戳提示（戳别人）: 戳人者={poke_sender_name}, 被戳者={poke_target_name}"
                    )

                processed_message += poke_notice

            # 🆕 v1.0.4: 添加发送者识别系统提示（根据触发方式）
            # 只在开启了 include_sender_info 的情况下添加
            if include_sender_info and trigger_type:
                sender_info_text = (
                    f"{sender_name}(ID:{sender_id})"
                    if sender_name
                    else f"用户(ID:{sender_id})"
                )

                # 根据触发方式添加不同的系统提示
                if trigger_type == "at":
                    # @消息触发
                    # 🔧 修复：区分空@消息和带消息的@消息，给AI不同的提示
                    if is_empty_at:
                        # 纯@消息（没有文字内容）
                        # 🔧 修复：使用更强烈明确的提示词，引导AI关注历史最后几条消息
                        system_notice = (
                            f"\n\n[系统提示]{sender_info_text} @了你，但没有附带新的消息内容。\n"
                            f"🔍 这很可能意味着：该用户在催促你回复之前的某条消息！\n\n"
                            f"【必须执行的检查步骤】：\n"
                            f"1️⃣ 立即查看【历史消息上下文】的**末尾部分**（最后3-5条消息）\n"
                            f"2️⃣ 找出{sender_info_text}在@你之前发送的最后一条消息\n"
                            f"3️⃣ 如果找到了该用户之前的消息→请直接针对那条消息的内容作出回复\n"
                            f"4️⃣ 如果历史中完全没有该用户的其他消息→再询问对方有什么事\n\n"
                            f"⚠️ 注意：不要忽略历史消息！用户单独@你通常是因为你漏掉了回复他之前的某条话。"
                        )
                    else:
                        # @消息+文字内容
                        system_notice = (
                            f"\n\n[系统提示]注意，现在有人在直接@你并且给你发送了这条消息，"
                            f"@你的那个人是{sender_info_text}"
                        )
                elif trigger_type == "keyword":
                    # 关键词触发
                    system_notice = f"\n\n[系统提示]注意，你刚刚发现这条消息里面包含和你有关的信息，这条消息的发送者是{sender_info_text}"
                elif trigger_type == "ai_decision":
                    # AI主动回复（中性描述，不预设结果）
                    system_notice = f"\n\n[系统提示]注意，你看到了这条消息，发送这条消息的人是{sender_info_text}"
                else:
                    system_notice = ""

                if system_notice:
                    processed_message += system_notice
                    logger.info(
                        f"已添加发送者识别提示（从缓存，触发方式: {trigger_type}）"
                    )

            return processed_message

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

            # 如果有昵称,格式为: 昵称(ID: xxx)
            if sender_name:
                return f"[发送者: {sender_name}(ID: {sender_id})]"
            else:
                # 如果没有昵称,只显示ID
                return f"[发送者ID: {sender_id}]"

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
