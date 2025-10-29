"""
消息处理器模块
负责消息预处理，添加时间戳、发送者信息等元数据

作者: Him666233
版本: v1.0.1
"""

from datetime import datetime
from astrbot.api.all import *


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

        Returns:
            添加元数据后的文本
        """
        try:
            # 获取时间戳（格式：YYYY-MM-DD HH:MM:SS，与历史消息一致）
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

            if timestamp_str or sender_prefix:
                logger.debug(
                    f"消息已添加元数据（统一格式）: [{timestamp_str}] {sender_prefix}"
                )

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
    ) -> str:
        """
        使用缓存中的发送者信息为消息添加元数据

        格式与历史消息保持一致：[时间] 发送者名字(ID:xxx): 消息内容

        用于缓存消息转正时，使用原始发送者的信息而不是当前event的发送者

        Args:
            message_text: 原始消息
            sender_id: 发送者ID（从缓存中获取）
            sender_name: 发送者昵称（从缓存中获取）
            message_timestamp: 消息时间戳（从缓存中获取）
            include_timestamp: 是否包含时间戳
            include_sender_info: 是否包含发送者信息

        Returns:
            添加元数据后的文本
        """
        try:
            # 获取时间戳（格式：YYYY-MM-DD HH:MM:SS）
            timestamp_str = ""
            if include_timestamp and message_timestamp:
                try:
                    dt = datetime.fromtimestamp(message_timestamp)
                    timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    # 如果时间戳转换失败，使用当前时间
                    dt = datetime.now()
                    timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")

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

            if timestamp_str or sender_prefix:
                logger.debug(
                    f"消息已添加元数据（从缓存，统一格式）: [{timestamp_str}] {sender_prefix}"
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
                    return dt.strftime("%Y-%m-%d %H:%M:%S")

            # 如果消息对象没有时间戳,使用当前时间
            dt = datetime.now()
            return dt.strftime("%Y-%m-%d %H:%M:%S")

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
                    return dt.strftime("%Y年%m月%d日 %H:%M:%S")

            # 如果消息对象没有时间戳,使用当前时间
            dt = datetime.now()
            return dt.strftime("%Y年%m月%d日 %H:%M:%S")

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
                logger.debug(
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
                from astrbot.api.message_components import At

                bot_id = event.get_self_id()
                message_chain = event.message_obj.message

                for component in message_chain:
                    if isinstance(component, At):
                        # 检查At的目标是否是机器人
                        if hasattr(component, "qq") and str(component.qq) == str(
                            bot_id
                        ):
                            logger.debug("检测到@机器人的消息（At组件）")
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
                message_text = event.get_message_plain()

                # 强制日志：显示文本@检测的详细信息（用于排查）
                logger.debug(
                    f"[文本@检测] bot_id={bot_id}, bot_name={bot_name}, message={message_text[:50] if message_text else 'None'}"
                )

                # 检查是否包含 @机器人ID 或 @机器人名称
                if message_text:
                    # 检查 @机器人ID
                    if f"@{bot_id}" in message_text:
                        logger.debug(f"检测到@机器人的消息（文本@ID: @{bot_id}）")
                        return True

                    # 检查 @机器人名称（支持部分匹配，如 @Monika(AI) 也能匹配 @Monika）
                    if bot_name:
                        # 使用 startswith 检查 @bot_name 后面可以跟任何字符
                        import re

                        # 检查是否有 @bot_name 后面跟着非字母数字（如空格、括号等）或字符串结束
                        pattern = rf"@{re.escape(bot_name)}(?:[^a-zA-Z0-9_]|$)"
                        if re.search(pattern, message_text):
                            logger.debug(
                                f"检测到@机器人的消息（文本@名称: @{bot_name}）"
                            )
                            return True
            except Exception as e:
                logger.debug(f"文本@检测时出错: {e}")

            return False

        except Exception as e:
            logger.error(f"判断@消息时发生错误: {e}")
            return False
