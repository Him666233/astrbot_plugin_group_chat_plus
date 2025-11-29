"""
上下文管理器模块
负责提取和管理历史消息上下文

主要功能：
- 从本地和官方存储读取历史消息
- 格式化上下文供AI使用
- 保存用户消息和bot回复
- 支持缓存消息转正（避免上下文断裂）
- 详细的保存日志便于调试

作者: Him666233
版本: v1.1.2
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
from astrbot.api.all import *
from astrbot.api.message_components import Plain
import os
import json
from datetime import datetime

# 导入 MessageCleaner（延迟导入以避免循环依赖）
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .message_cleaner import MessageCleaner
# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class ContextManager:
    """
    上下文管理器

    负责历史消息的读取、保存和格式化：
    1. 从官方存储提取历史消息
    2. 控制上下文消息数量
    3. 格式化成AI可理解的文本
    """

    # 历史消息存储路径
    base_storage_path = None

    @staticmethod
    def init(data_dir: Optional[str] = None):
        """
        初始化上下文管理器，创建存储目录

        Args:
            data_dir: 数据目录路径，如果为None则功能将受限
        """
        if not data_dir:
            # 如果未提供data_dir，记录错误并禁用功能
            logger.error(
                "[上下文管理器] 未提供data_dir参数，历史消息存储功能将被禁用。"
                "请确保通过 StarTools.get_data_dir() 获取数据目录。"
            )
            ContextManager.base_storage_path = None
            return

        # 🔧 修复：统一使用 pathlib.Path 进行路径操作
        ContextManager.base_storage_path = Path(data_dir) / "chat_history"

        if not ContextManager.base_storage_path.exists():
            ContextManager.base_storage_path.mkdir(parents=True, exist_ok=True)
            if DEBUG_MODE:
                logger.info(f"上下文存储路径初始化: {ContextManager.base_storage_path}")

    @staticmethod
    def _message_to_dict(msg: AstrBotMessage) -> Dict[str, Any]:
        """
        将 AstrBotMessage 对象转换为可JSON序列化的字典

        Args:
            msg: AstrBotMessage 对象

        Returns:
            字典表示
        """
        try:
            msg_dict = {
                "message_str": msg.message_str if hasattr(msg, "message_str") else "",
                "platform_name": msg.platform_name
                if hasattr(msg, "platform_name")
                else "",
                "timestamp": msg.timestamp if hasattr(msg, "timestamp") else 0,
                "type": msg.type.value
                if hasattr(msg, "type") and hasattr(msg.type, "value")
                else "OtherMessage",
                "group_id": msg.group_id if hasattr(msg, "group_id") else None,
                "self_id": msg.self_id if hasattr(msg, "self_id") else "",
                "session_id": msg.session_id if hasattr(msg, "session_id") else "",
                "message_id": msg.message_id if hasattr(msg, "message_id") else "",
            }

            # 处理发送者信息
            if hasattr(msg, "sender") and msg.sender:
                msg_dict["sender"] = {
                    "user_id": msg.sender.user_id
                    if hasattr(msg.sender, "user_id")
                    else "",
                    "nickname": msg.sender.nickname
                    if hasattr(msg.sender, "nickname")
                    else "",
                }
            else:
                msg_dict["sender"] = None

            return msg_dict
        except Exception as e:
            logger.error(f"转换消息对象为字典失败: {e}")
            # 返回最小字典
            return {"message_str": "", "timestamp": 0}

    @staticmethod
    def _dict_to_message(msg_dict: Dict[str, Any]) -> AstrBotMessage:
        """
        将字典转换回 AstrBotMessage 对象

        Args:
            msg_dict: 消息字典

        Returns:
            AstrBotMessage 对象
        """
        try:
            msg = AstrBotMessage()
            msg.message_str = msg_dict.get("message_str", "")
            msg.platform_name = msg_dict.get("platform_name", "")
            msg.timestamp = msg_dict.get("timestamp", 0)

            # 处理消息类型
            # MessageType 是字符串枚举，值如 "GroupMessage", "FriendMessage", "OtherMessage"
            msg_type = msg_dict.get("type", "OtherMessage")
            if isinstance(msg_type, str):
                # 从字符串值创建枚举
                msg.type = MessageType(msg_type)
            elif isinstance(msg_type, int):
                # 兼容旧格式：如果是整数，映射到对应的类型
                # 这是为了处理可能存在的旧数据
                type_map = {
                    0: MessageType.OTHER_MESSAGE,
                    1: MessageType.GROUP_MESSAGE,
                    2: MessageType.FRIEND_MESSAGE,
                }
                msg.type = type_map.get(msg_type, MessageType.OTHER_MESSAGE)
            else:
                # 如果已经是 MessageType 对象，直接使用
                msg.type = msg_type

            msg.group_id = msg_dict.get("group_id")
            msg.self_id = msg_dict.get("self_id", "")
            msg.session_id = msg_dict.get("session_id", "")
            msg.message_id = msg_dict.get("message_id", "")

            # 处理发送者信息
            sender_dict = msg_dict.get("sender")
            if sender_dict:
                msg.sender = MessageMember(
                    user_id=sender_dict.get("user_id", ""),
                    nickname=sender_dict.get("nickname", ""),
                )

            return msg
        except Exception as e:
            logger.error(f"从字典转换为消息对象失败: {e}")
            # 返回一个空的消息对象而不是 None，避免后续处理出错
            empty_msg = AstrBotMessage()
            empty_msg.message_str = str(msg_dict.get("message_str", ""))
            empty_msg.timestamp = 0
            return empty_msg

    @staticmethod
    def _get_storage_path(platform_name: str, is_private: bool, chat_id: str) -> Path:
        """
        获取历史消息的本地存储路径

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID

        Returns:
            JSON文件路径（Path对象）
        """
        if not ContextManager.base_storage_path:
            ContextManager.init()

        # 🔧 修复：统一使用 pathlib.Path 进行路径操作
        chat_type = "private" if is_private else "group"
        directory = ContextManager.base_storage_path / platform_name / chat_type

        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

        return directory / f"{chat_id}.json"

    @staticmethod
    def get_history_messages(
        event: AstrMessageEvent, max_messages: int
    ) -> List[AstrBotMessage]:
        """
        获取历史消息记录

        Args:
            event: 消息事件对象
            max_messages: 最大消息数量
                - 正数: 限制条数
                - 0: 不获取
                - -1: 不限制

        Returns:
            历史消息列表
        """
        try:
            # 如果配置为0,不获取历史消息
            if max_messages == 0:
                if DEBUG_MODE:
                    logger.info("配置为不获取历史消息")
                return []

            # 获取平台和聊天信息
            platform_name = event.get_platform_name()
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            if not chat_id:
                logger.warning("无法获取聊天ID,跳过历史消息提取")
                return []

            # 读取历史消息文件
            file_path = ContextManager._get_storage_path(
                platform_name, is_private, chat_id
            )

            # 🔧 修复：使用 Path 对象的 exists() 方法
            if not file_path.exists():
                if DEBUG_MODE:
                    logger.info(f"历史消息文件不存在: {file_path}")
                return []

            # 使用安全的JSON反序列化
            with open(file_path, "r", encoding="utf-8") as f:
                history_dicts = json.load(f)

            if not history_dicts:
                return []

            # 将字典列表转换为 AstrBotMessage 对象列表
            history = [
                ContextManager._dict_to_message(msg_dict) for msg_dict in history_dicts
            ]

            # 过滤掉可能的 None 值（额外保护）
            history = [msg for msg in history if msg is not None]

            # 如果配置为-1,返回所有历史消息
            if max_messages == -1:
                logger.info(f"获取所有历史消息,共 {len(history)} 条")
                return history

            # 限制消息数量,只保留最新的
            if len(history) > max_messages:
                history = history[-max_messages:]
                logger.info(f"历史消息超过限制,只保留最新的 {max_messages} 条")
            else:
                logger.info(f"获取历史消息 {len(history)} 条")

            return history

        except Exception as e:
            logger.error(f"读取历史消息失败: {e}")
            return []

    @staticmethod
    def get_history_messages_by_params(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        max_messages: int,
    ) -> List[AstrBotMessage]:
        """
        根据参数获取历史消息记录（用于主动对话等场景，无需event对象）

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            max_messages: 最大消息数量
                - 正数: 限制条数
                - 0: 不获取
                - -1: 不限制

        Returns:
            历史消息列表
        """
        try:
            # 如果配置为0,不获取历史消息
            if max_messages == 0:
                if DEBUG_MODE:
                    logger.info("配置为不获取历史消息")
                return []

            if not chat_id:
                logger.warning("无法获取聊天ID,跳过历史消息提取")
                return []

            # 读取历史消息文件
            file_path = ContextManager._get_storage_path(
                platform_name, is_private, chat_id
            )

            # 🔧 修复：使用 Path 对象的 exists() 方法
            if not file_path.exists():
                if DEBUG_MODE:
                    logger.info(f"历史消息文件不存在: {file_path}")
                return []

            # 使用安全的JSON反序列化
            with open(file_path, "r", encoding="utf-8") as f:
                history_dicts = json.load(f)

            if not history_dicts:
                return []

            # 将字典列表转换为 AstrBotMessage 对象列表
            history = [
                ContextManager._dict_to_message(msg_dict) for msg_dict in history_dicts
            ]

            # 过滤掉可能的 None 值（额外保护）
            history = [msg for msg in history if msg is not None]

            # 如果配置为-1,返回所有历史消息
            if max_messages == -1:
                logger.info(f"获取所有历史消息,共 {len(history)} 条")
                return history

            # 限制消息数量,只保留最新的
            if len(history) > max_messages:
                history = history[-max_messages:]
                logger.info(f"历史消息超过限制,只保留最新的 {max_messages} 条")
            else:
                logger.info(f"获取历史消息 {len(history)} 条")

            return history

        except Exception as e:
            logger.error(f"读取历史消息失败: {e}")
            return []

    @staticmethod
    async def format_context_for_ai(
        history_messages: List[AstrBotMessage],
        current_message: str,
        bot_id: str,
        include_timestamp: bool = True,
        include_sender_info: bool = True,
    ) -> str:
        """
        将历史消息格式化为AI可理解的文本

        Args:
            history_messages: 历史消息列表
            current_message: 当前消息
            bot_id: 机器人ID，用于识别自己的回复
            include_timestamp: 是否包含时间戳（默认为True）
            include_sender_info: 是否包含发送者信息（默认为True）

        Returns:
            格式化后的文本
        """
        try:
            formatted_parts = []

            # 如果有历史消息,添加历史消息部分
            if history_messages:
                formatted_parts.append("=== 历史消息上下文 ===")

                for msg in history_messages:
                    # 跳过无效的消息对象
                    if msg is None or not isinstance(msg, AstrBotMessage):
                        logger.warning(f"跳过无效的历史消息对象: {type(msg)}")
                        continue
                    # 获取发送者信息（如果需要）
                    sender_name = "未知用户"
                    sender_id = "unknown"
                    is_bot = False

                    if hasattr(msg, "sender") and msg.sender:
                        sender_name = msg.sender.nickname or "未知用户"
                        sender_id = msg.sender.user_id or "unknown"
                        # 判断是否是机器人自己的消息
                        # 确保类型一致性：统一转换为字符串进行比较
                        is_bot = str(sender_id) == str(bot_id)

                        # 调试日志（仅在第一条消息时输出，避免刷屏）
                        if formatted_parts and len(formatted_parts) == 1:
                            if DEBUG_MODE:
                                logger.info(
                                    f"[上下文格式化] 机器人ID: {bot_id}, 当前消息发送者ID: {sender_id}, 是否为机器人: {is_bot}"
                                )

                    # 如果还没有判定为bot，尝试通过 self_id 判断
                    # 有时候消息没有正确的sender，但有self_id
                    if not is_bot and hasattr(msg, "self_id") and msg.self_id:
                        # 如果消息的 self_id 等于当前 bot_id，说明这是机器人发出的消息
                        # 但需要注意：self_id 通常表示"当前机器人的ID"
                        # 对于bot发送的消息，sender.user_id 应该等于 self_id
                        pass

                    # 获取消息时间（如果需要）
                    time_str = ""
                    if include_timestamp:
                        time_str = "未知时间"
                        if hasattr(msg, "timestamp") and msg.timestamp:
                            try:
                                dt = datetime.fromtimestamp(msg.timestamp)
                                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except:
                                pass

                    # 获取消息内容
                    message_content = ""
                    if hasattr(msg, "message_str"):
                        message_content = msg.message_str
                    elif hasattr(msg, "message"):
                        # 简单提取文本
                        for comp in msg.message:
                            if isinstance(comp, Plain):
                                message_content += comp.text

                    # 格式化消息（根据配置决定格式）
                    # 构建消息前缀部分
                    prefix_parts = []

                    # 添加时间戳（如果启用）
                    if include_timestamp and time_str:
                        prefix_parts.append(f"[{time_str}]")

                    # 添加发送者信息（如果启用）
                    if include_sender_info:
                        if is_bot:
                            # AI自己的回复,特殊标注（强调提醒不要重复）
                            # 🔧 修复：使用更强的标记，防止AI重复历史回复
                            prefix_parts.append(
                                f"⚠️【禁止重复-这是你自己的历史回复】{sender_name}(ID:{sender_id}):"
                            )
                        else:
                            # 其他用户的消息
                            prefix_parts.append(f"{sender_name}(ID:{sender_id}):")
                    else:
                        # 不包含发送者信息时，仍需要区分bot自己的消息
                        if is_bot:
                            prefix_parts.append("⚠️【禁止重复-这是你自己的历史回复】:")

                    # 组合完整消息
                    if prefix_parts:
                        formatted_msg = " ".join(prefix_parts) + " " + message_content
                    else:
                        formatted_msg = message_content

                    formatted_parts.append(formatted_msg)

                formatted_parts.append("")  # 空行分隔

            # 添加当前消息部分（强调重要性）
            formatted_parts.append("")  # 空行分隔
            formatted_parts.append("=" * 50)
            formatted_parts.append(
                "=== 【重要】当前新消息（请优先关注这条消息的核心内容）==="
            )
            formatted_parts.append("=" * 50)
            formatted_parts.append(current_message)
            formatted_parts.append("=" * 50)

            result = "\n".join(formatted_parts)
            if DEBUG_MODE:
                logger.info(f"上下文格式化完成,总长度: {len(result)} 字符")
            return result

        except Exception as e:
            logger.error(f"格式化上下文时发生错误: {e}")
            # 发生错误时,至少返回当前消息
            return current_message

    @staticmethod
    def calculate_context_size(
        history_messages: List[AstrBotMessage], current_message: str
    ) -> int:
        """
        计算上下文总消息数（含当前消息）

        Args:
            history_messages: 历史消息列表
            current_message: 当前消息

        Returns:
            总消息数
        """
        return len(history_messages) + 1

    @staticmethod
    async def save_user_message(
        event: AstrMessageEvent, message_text: str, context: "Context" = None
    ) -> bool:
        """
        保存用户消息（自定义存储+官方存储）

        Args:
            event: 消息事件
            message_text: 用户消息（可能已包含元数据）
            context: Context对象（可选）

        Returns:
            是否成功
        """
        try:
            # 导入 MessageCleaner
            from .message_cleaner import MessageCleaner

            # 🔧 修复：更强的清理，确保所有系统提示词被移除
            cleaned_message = MessageCleaner.clean_message(message_text)
            if not cleaned_message:
                # 如果清理后为空，使用原消息
                cleaned_message = message_text

            # 🔧 修复：二次清理，确保戳一戳和系统提示完全被移除
            # 检测更多的系统提示词特征
            if (
                "[系统提示]" in cleaned_message
                or "[戳一戳提示]" in cleaned_message
                or "[戳过对方提示]" in cleaned_message
                or "[当前时间:" in cleaned_message
                or "[User ID:" in cleaned_message
                or "[当前情绪状态:" in cleaned_message
                or "=== 历史消息上下文 ===" in cleaned_message
                or "=== 背景信息 ===" in cleaned_message
                or "💭 相关记忆：" in cleaned_message
                or "=== 可用工具列表 ===" in cleaned_message
                or "【当前对话对象】重要提醒" in cleaned_message
                or "【第一重要】识别当前发送者：" in cleaned_message
            ):
                # 如果仍然包含系统提示，再次清理
                import re

                cleaned_message = re.sub(
                    r"\n*\s*\[系统提示\][^\n]*", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"\n*\s*\[戳一戳提示\][^\n]*", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"\n*\s*\[戳过对方提示\][^\n]*", "", cleaned_message
                )
                # 清理额外的系统提示词
                cleaned_message = re.sub(
                    r"\[当前时间:\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"\[User ID:.*?Nickname:.*?\]", "", cleaned_message
                )
                cleaned_message = re.sub(r"\[当前情绪状态:.*?\]", "", cleaned_message)
                cleaned_message = re.sub(
                    r"=== 历史消息上下文 ===[\s\S]*?(?==== |$)", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"=== 背景信息 ===[\s\S]*?(?==== |$)", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"💭 相关记忆：[\s\S]*?(?==== |$)", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"=== 可用工具列表 ===[\s\S]*?(?=请根据上述对话|请开始回复|====|$)",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"当前平台共有 \d+ 个可用工具:[\s\S]*?(?=请根据上述对话|请开始回复|====|$)",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"============+\n*.*?【当前对话对象】重要提醒.*?\n*============+[\s\S]*?(?=\n\n[^\s=]|$)",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"【第一重要】识别当前发送者：[\s\S]*?(?=请开始回复|====|$)",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"=+\n*.*?【重要】当前新消息.*?\n*=+", "", cleaned_message
                )
                cleaned_message = cleaned_message.strip()
                if DEBUG_MODE:
                    logger.info("⚠️ [保存消息] 检测到系统提示残留，已二次清理")

            # 获取平台和聊天信息
            platform_name = event.get_platform_name()
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            if not chat_id:
                logger.warning("无法获取聊天ID,跳过消息保存")
                return False

            # 读取现有历史记录
            file_path = ContextManager._get_storage_path(
                platform_name, is_private, chat_id
            )
            history = ContextManager.get_history_messages(event, -1)  # 获取所有历史
            if history is None:
                history = []

            # 创建用户消息对象
            user_msg = AstrBotMessage()
            user_msg.message_str = cleaned_message
            user_msg.platform_name = platform_name
            user_msg.timestamp = int(datetime.now().timestamp())
            user_msg.type = (
                MessageType.GROUP_MESSAGE
                if not is_private
                else MessageType.FRIEND_MESSAGE
            )

            if not is_private:
                user_msg.group_id = chat_id

            # 设置发送者信息
            user_msg.sender = MessageMember(
                user_id=event.get_sender_id(),
                nickname=event.get_sender_name() or "未知用户",
            )
            user_msg.self_id = event.get_self_id()
            user_msg.session_id = (
                event.session_id if hasattr(event, "session_id") else chat_id
            )
            user_msg.message_id = f"user_{int(datetime.now().timestamp())}"

            # 添加到历史记录
            history.append(user_msg)

            # 限制历史记录数量（保留最新200条）
            if len(history) > 200:
                history = history[-200:]

            # 🔧 修复：使用 Path 对象的 parent.mkdir() 方法
            # 保存到自定义文件（使用安全的JSON序列化）
            file_path.parent.mkdir(parents=True, exist_ok=True)
            history_dicts = [ContextManager._message_to_dict(msg) for msg in history]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history_dicts, f, ensure_ascii=False, indent=2)

            if DEBUG_MODE:
                logger.info(f"用户消息已保存到自定义历史记录")

            # 保存到官方历史管理器（platform_message_history表）
            # 注意：这个表和conversation不同，是用于平台消息记录的
            if context:
                try:
                    # 获取消息链并转换为dict格式，确保JSON可序列化
                    message_chain_dict = []
                    if hasattr(event, "message_obj") and hasattr(
                        event.message_obj, "message"
                    ):
                        for comp in event.message_obj.message:
                            try:
                                comp_dict = await comp.to_dict()
                                # 确保字典内容是JSON可序列化的
                                # 移除或转换不可序列化的对象（如Image对象）
                                if isinstance(comp_dict, dict):
                                    serializable_dict = {}
                                    for k, v in comp_dict.items():
                                        if k == "data" and isinstance(v, dict):
                                            # 处理data字段，确保其内容可序列化
                                            serializable_data = {}
                                            for dk, dv in v.items():
                                                # 只保留基本类型和字符串
                                                if isinstance(
                                                    dv,
                                                    (str, int, float, bool, type(None)),
                                                ):
                                                    serializable_data[dk] = dv
                                                elif isinstance(dv, (list, dict)):
                                                    # 尝试JSON序列化测试
                                                    try:
                                                        json.dumps(dv)
                                                        serializable_data[dk] = dv
                                                    except (TypeError, ValueError):
                                                        # 不可序列化，转为字符串
                                                        serializable_data[dk] = str(dv)
                                                else:
                                                    # 其他对象转为字符串
                                                    serializable_data[dk] = str(dv)
                                            serializable_dict[k] = serializable_data
                                        elif isinstance(
                                            v, (str, int, float, bool, type(None))
                                        ):
                                            serializable_dict[k] = v
                                        else:
                                            serializable_dict[k] = str(v)
                                    message_chain_dict.append(serializable_dict)
                                else:
                                    message_chain_dict.append(comp_dict)
                            except Exception as comp_err:
                                if DEBUG_MODE:
                                    logger.info(f"组件转换失败，跳过: {comp_err}")
                                continue

                    if not message_chain_dict:
                        # 如果没有成功转换的消息链，创建纯文本消息
                        message_chain_dict = [
                            {"type": "text", "data": {"text": message_text}}
                        ]

                    # 调用官方历史管理器保存
                    await context.message_history_manager.insert(
                        platform_id=event.get_platform_id(),
                        user_id=chat_id,
                        content=message_chain_dict,
                        sender_id=event.get_sender_id(),
                        sender_name=event.get_sender_name() or "未知用户",
                    )

                    if DEBUG_MODE:
                        logger.info(
                            "用户消息已保存到官方历史管理器(platform_message_history)"
                        )

                except Exception as e:
                    logger.warning(
                        f"保存到官方历史管理器(platform_message_history)失败: {e}"
                    )
                    # 即使官方保存失败，自定义存储仍然成功
                    # 这不影响conversation_manager的保存

            return True

        except Exception as e:
            logger.error(f"保存用户消息失败: {e}")
            return False

    @staticmethod
    async def save_bot_message(
        event: AstrMessageEvent, bot_message_text: str, context: "Context" = None
    ) -> bool:
        """
        保存AI回复（自定义存储+官方存储）

        Args:
            event: 消息事件
            bot_message_text: AI回复文本
            context: Context对象（可选）

        Returns:
            是否成功
        """
        try:
            # 导入 MessageCleaner
            from .message_cleaner import MessageCleaner

            # 🔧 修复：更强的清理，确保所有系统提示词被移除
            cleaned_message = MessageCleaner.clean_message(bot_message_text)
            if not cleaned_message:
                # 如果清理后为空，使用原消息
                cleaned_message = bot_message_text

            # 🔧 修复：二次清理，确保戳一戳和系统提示完全被移除
            # 检测更多的系统提示词特征
            if (
                "[系统提示]" in cleaned_message
                or "[戳一戳提示]" in cleaned_message
                or "[戳过对方提示]" in cleaned_message
                or "[当前时间:" in cleaned_message
                or "[User ID:" in cleaned_message
                or "[当前情绪状态:" in cleaned_message
                or "=== 历史消息上下文 ===" in cleaned_message
                or "=== 背景信息 ===" in cleaned_message
                or "💭 相关记忆：" in cleaned_message
                or "=== 可用工具列表 ===" in cleaned_message
                or "【当前对话对象】重要提醒" in cleaned_message
                or "【第一重要】识别当前发送者：" in cleaned_message
            ):
                # 如果仍然包含系统提示，再次清理
                import re

                cleaned_message = re.sub(
                    r"\n*\s*\[系统提示\][^\n]*", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"\n*\s*\[戳一戳提示\][^\n]*", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"\n*\s*\[戳过对方提示\][^\n]*", "", cleaned_message
                )
                # 清理额外的系统提示词
                cleaned_message = re.sub(
                    r"\[当前时间:\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"\[User ID:.*?Nickname:.*?\]", "", cleaned_message
                )
                cleaned_message = re.sub(r"\[当前情绪状态:.*?\]", "", cleaned_message)
                cleaned_message = re.sub(
                    r"=== 历史消息上下文 ===[\s\S]*?(?==== |$)", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"=== 背景信息 ===[\s\S]*?(?==== |$)", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"💭 相关记忆：[\s\S]*?(?==== |$)", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"=== 可用工具列表 ===[\s\S]*?(?=请根据上述对话|请开始回复|====|$)",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"当前平台共有 \d+ 个可用工具:[\s\S]*?(?=请根据上述对话|请开始回复|====|$)",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"============+\n*.*?【当前对话对象】重要提醒.*?\n*============+[\s\S]*?(?=\n\n[^\s=]|$)",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"【第一重要】识别当前发送者：[\s\S]*?(?=请开始回复|====|$)",
                    "",
                    cleaned_message,
                )
                cleaned_message = re.sub(
                    r"=+\n*.*?【重要】当前新消息.*?\n*=+", "", cleaned_message
                )
                cleaned_message = cleaned_message.strip()
                if DEBUG_MODE:
                    logger.info("⚠️ [AI回复保存] 检测到系统提示残留，已二次清理")

            # 获取平台和聊天信息
            platform_name = event.get_platform_name()
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            if not chat_id:
                logger.warning("无法获取聊天ID,跳过消息保存")
                return False

            # 读取现有历史记录
            file_path = ContextManager._get_storage_path(
                platform_name, is_private, chat_id
            )
            history = ContextManager.get_history_messages(event, -1)  # 获取所有历史
            if history is None:
                history = []

            # 创建AI消息对象
            bot_msg = AstrBotMessage()
            bot_msg.message_str = cleaned_message
            bot_msg.platform_name = platform_name
            bot_msg.timestamp = int(datetime.now().timestamp())
            bot_msg.type = (
                MessageType.GROUP_MESSAGE
                if not is_private
                else MessageType.FRIEND_MESSAGE
            )

            if not is_private:
                bot_msg.group_id = chat_id

            # 设置发送者信息（AI自己）
            # 尝试获取机器人的真实昵称
            bot_nickname = "AI"  # 默认昵称
            try:
                # 尝试从平台获取机器人信息
                if hasattr(event, "get_self_name") and callable(event.get_self_name):
                    bot_nickname = event.get_self_name() or "AI"
                elif hasattr(event, "message_obj") and hasattr(
                    event.message_obj, "self_id"
                ):
                    # 有些平台可能在 message_obj 中保存了机器人名称
                    pass
            except Exception as e:
                logger.info(f"无法获取机器人昵称: {e}")

            bot_msg.sender = MessageMember(
                user_id=event.get_self_id(), nickname=bot_nickname
            )
            bot_msg.self_id = event.get_self_id()
            bot_msg.session_id = (
                event.session_id if hasattr(event, "session_id") else chat_id
            )
            bot_msg.message_id = f"bot_{int(datetime.now().timestamp())}"

            # 添加到历史记录
            history.append(bot_msg)

            # 限制历史记录数量（保留最新200条）
            if len(history) > 200:
                history = history[-200:]

            # 🔧 修复：使用 Path 对象的 parent.mkdir() 方法
            # 保存到自定义文件（使用安全的JSON序列化）
            file_path.parent.mkdir(parents=True, exist_ok=True)
            history_dicts = [ContextManager._message_to_dict(msg) for msg in history]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history_dicts, f, ensure_ascii=False, indent=2)

            if DEBUG_MODE:
                logger.info(f"AI回复消息已保存到自定义历史记录")

            # 保存到官方历史管理器（platform_message_history表）
            # 注意：这个表和conversation不同，是用于平台消息记录的
            if context:
                try:
                    # 从event的result中获取消息链
                    result = event.get_result()
                    message_chain_dict = []

                    if result and hasattr(result, "chain") and result.chain:
                        # 转换消息链为dict格式，确保JSON可序列化
                        for comp in result.chain:
                            try:
                                comp_dict = await comp.to_dict()
                                # 确保字典内容是JSON可序列化的
                                if isinstance(comp_dict, dict):
                                    serializable_dict = {}
                                    for k, v in comp_dict.items():
                                        if k == "data" and isinstance(v, dict):
                                            # 处理data字段，确保其内容可序列化
                                            serializable_data = {}
                                            for dk, dv in v.items():
                                                # 只保留基本类型和字符串
                                                if isinstance(
                                                    dv,
                                                    (str, int, float, bool, type(None)),
                                                ):
                                                    serializable_data[dk] = dv
                                                elif isinstance(dv, (list, dict)):
                                                    # 尝试JSON序列化测试
                                                    try:
                                                        json.dumps(dv)
                                                        serializable_data[dk] = dv
                                                    except (TypeError, ValueError):
                                                        # 不可序列化，转为字符串
                                                        serializable_data[dk] = str(dv)
                                                else:
                                                    # 其他对象转为字符串
                                                    serializable_data[dk] = str(dv)
                                            serializable_dict[k] = serializable_data
                                        elif isinstance(
                                            v, (str, int, float, bool, type(None))
                                        ):
                                            serializable_dict[k] = v
                                        else:
                                            serializable_dict[k] = str(v)
                                    message_chain_dict.append(serializable_dict)
                                else:
                                    message_chain_dict.append(comp_dict)
                            except Exception as comp_err:
                                if DEBUG_MODE:
                                    logger.info(f"组件转换失败，跳过: {comp_err}")
                                    continue

                    if not message_chain_dict:
                        # 如果没有消息链，创建纯文本消息
                        message_chain_dict = [
                            {"type": "text", "data": {"text": bot_message_text}}
                        ]

                    # 调用官方历史管理器保存
                    await context.message_history_manager.insert(
                        platform_id=event.get_platform_id(),
                        user_id=chat_id,
                        content=message_chain_dict,
                        sender_id=event.get_self_id(),
                        sender_name="AstrBot",
                    )

                    if DEBUG_MODE:
                        logger.info(
                            "AI回复消息已保存到官方历史管理器(platform_message_history)"
                        )

                except Exception as e:
                    logger.warning(
                        f"保存到官方历史管理器(platform_message_history)失败: {e}"
                    )
                    # 即使官方保存失败，自定义存储仍然成功
                    # 这不影响conversation_manager的保存

            return True

        except Exception as e:
            logger.error(f"保存AI消息失败: {e}")
            return False

    @staticmethod
    async def save_bot_message_by_params(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        bot_message_text: str,
        self_id: str,
        context: "Context" = None,
        platform_id: str = None,
    ) -> bool:
        """
        保存AI回复（用于主动对话等场景，无需event对象）
        复用 save_bot_message 的核心逻辑，保持一致性

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            bot_message_text: AI回复文本
            self_id: 机器人ID
            context: Context对象（可选，用于保存到官方存储）
            platform_id: 平台ID（可选，用于保存到官方存储）

        Returns:
            是否成功
        """
        try:
            # 导入 MessageCleaner
            from .message_cleaner import MessageCleaner

            # 🔧 修复：更强的清理，确保所有系统提示词被移除
            cleaned_message = MessageCleaner.clean_message(bot_message_text)
            if not cleaned_message:
                # 如果清理后为空，使用原消息
                cleaned_message = bot_message_text

            # 🔧 修复：二次清理，确保戳一戳和系统提示完全被移除
            if (
                "[系统提示]" in cleaned_message
                or "[戳一戳提示]" in cleaned_message
                or "[戳过对方提示]" in cleaned_message
            ):
                # 如果仍然包含系统提示，再次清理
                import re

                cleaned_message = re.sub(
                    r"\n*\s*\[系统提示\][^\n]*", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"\n*\s*\[戳一戳提示\][^\n]*", "", cleaned_message
                )
                cleaned_message = re.sub(
                    r"\n*\s*\[戳过对方提示\][^\n]*", "", cleaned_message
                )
                cleaned_message = cleaned_message.strip()

            if not chat_id:
                logger.warning("无法获取聊天ID,跳过消息保存")
                return False

            # 读取现有历史记录（使用 get_history_messages_by_params，与主动对话场景一致）
            file_path = ContextManager._get_storage_path(
                platform_name, is_private, chat_id
            )
            history = ContextManager.get_history_messages_by_params(
                platform_name, is_private, chat_id, -1
            )  # 获取所有历史
            if history is None:
                history = []

            # 创建AI消息对象（与 save_bot_message 保持一致）
            bot_msg = AstrBotMessage()
            bot_msg.message_str = cleaned_message
            bot_msg.platform_name = platform_name
            bot_msg.timestamp = int(datetime.now().timestamp())
            bot_msg.type = (
                MessageType.GROUP_MESSAGE
                if not is_private
                else MessageType.FRIEND_MESSAGE
            )

            if not is_private:
                bot_msg.group_id = chat_id

            # 设置发送者信息（AI自己）
            bot_msg.sender = MessageMember(user_id=self_id, nickname="AI")
            bot_msg.self_id = self_id
            bot_msg.session_id = chat_id
            bot_msg.message_id = f"bot_{int(datetime.now().timestamp())}"

            # 添加到历史记录
            history.append(bot_msg)

            # 限制历史记录数量（保留最新200条）
            if len(history) > 200:
                history = history[-200:]

            # 保存到自定义文件（使用安全的JSON序列化）
            file_path.parent.mkdir(parents=True, exist_ok=True)
            history_dicts = [ContextManager._message_to_dict(msg) for msg in history]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history_dicts, f, ensure_ascii=False, indent=2)

            logger.info(f"AI回复消息已保存到自定义历史记录")

            # 保存到官方历史管理器（platform_message_history表）
            # 与 save_bot_message 保持一致
            if context and platform_id:
                try:
                    # 构造消息链字典（与 save_bot_message 保持一致）
                    message_chain_dict = [
                        {"type": "text", "data": {"text": bot_message_text}}
                    ]

                    # 调用官方历史管理器保存
                    await context.message_history_manager.insert(
                        platform_id=platform_id,
                        user_id=chat_id,
                        content=message_chain_dict,
                        sender_id=self_id,
                        sender_name="AstrBot",
                    )

                    logger.info(
                        "AI回复消息已保存到官方历史管理器(platform_message_history)"
                    )

                except Exception as e:
                    logger.warning(
                        f"保存到官方历史管理器(platform_message_history)失败: {e}"
                    )
                    # 即使官方保存失败，自定义存储仍然成功

            return True

        except Exception as e:
            logger.error(f"保存AI消息失败: {e}")
            return False

    @staticmethod
    async def save_to_official_conversation(
        event: AstrMessageEvent, user_message: str, bot_message: str, context: "Context"
    ) -> bool:
        """
        保存消息到官方对话系统

        Args:
            event: 消息事件
            user_message: 用户消息（原始，不带元数据）
            bot_message: AI回复
            context: Context对象

        Returns:
            是否成功
        """
        try:
            # 1. 获取unified_msg_origin（会话标识）
            unified_msg_origin = event.unified_msg_origin
            if DEBUG_MODE:
                logger.info(
                    f"[官方保存] 准备保存到官方对话系统，会话: {unified_msg_origin}"
                )

            # 2. 获取conversation_manager
            cm = context.conversation_manager

            # 3. 获取当前对话ID，如果没有则创建
            curr_cid = await cm.get_curr_conversation_id(unified_msg_origin)
            if not curr_cid:
                if DEBUG_MODE:
                    logger.info(
                        f"[官方保存] 会话 {unified_msg_origin} 没有对话，创建新对话"
                    )
                # 获取群名作为标题
                chat_id = (
                    event.get_group_id()
                    if not event.is_private_chat()
                    else event.get_sender_id()
                )
                title = (
                    f"群聊 {chat_id}"
                    if not event.is_private_chat()
                    else f"私聊 {event.get_sender_name()}"
                )

                # 使用new_conversation创建
                curr_cid = await cm.new_conversation(
                    unified_msg_origin=unified_msg_origin,
                    platform_id=event.get_platform_id(),
                    title=title,
                    content=[],
                )
                if DEBUG_MODE:
                    logger.info(f"[官方保存] 创建新对话ID: {curr_cid}")

            if not curr_cid:
                logger.warning(f"[官方保存] 无法创建或获取对话ID")
                return False

            # 4. 获取当前对话的历史记录
            conversation = await cm.get_conversation(
                unified_msg_origin=unified_msg_origin, conversation_id=curr_cid
            )

            # 5. 构建完整的历史列表（包含已有历史+新消息）
            if conversation and conversation.content:
                history_list = conversation.content
            else:
                history_list = []

            if DEBUG_MODE:
                logger.info(f"[官方保存] 当前对话有 {len(history_list)} 条历史消息")

            # 6. 添加用户消息和AI回复
            history_list.append({"role": "user", "content": user_message})
            history_list.append({"role": "assistant", "content": bot_message})

            if DEBUG_MODE:
                logger.info(
                    f"[官方保存] 准备保存，新增2条消息，总计 {len(history_list)} 条"
                )

            # 7. 使用官方API保存（参考旧插件的成功方法）
            success = await ContextManager._try_official_save(
                cm, unified_msg_origin, curr_cid, history_list
            )

            if success:
                logger.info(
                    f"✅ [官方保存] 消息已保存到官方对话系统 (conversation_id: {curr_cid}, 总消息数: {len(history_list)})"
                )
                return True
            else:
                logger.error(f"[官方保存] 所有保存方法均失败")
                return False

        except Exception as e:
            logger.error(f"[官方保存] 保存到官方对话系统失败: {e}", exc_info=True)
            return False

    @staticmethod
    async def _try_official_save(
        cm, unified_msg_origin: str, conversation_id: str, history_list: list
    ) -> bool:
        """
        尝试多种方法保存到官方对话管理器

        Args:
            cm: conversation_manager对象
            unified_msg_origin: 会话来源标识
            conversation_id: 对话ID
            history_list: 历史消息列表

        Returns:
            是否成功
        """
        try:
            # 扩展的方法列表（完全按照旧插件）
            methods = [
                "update_conversation",  # 这是正确的主要保存方法
                "update_conversation_history",
                "set_conversation_history",
                "save_conversation_history",
                "save_history",
                # 追加式候选
                "append_conversation_history",
                "append_history",
                "add_conversation_history",
                "add_history",
                # 新增更多可能的API方法
                "update_history",
                "set_history",
                "store_conversation_history",
                "store_history",
                "record_conversation_history",
                "record_history",
            ]

            # 记录可用方法
            try:
                cm_type = type(cm).__name__
                available = [m for m in methods if hasattr(cm, m)]
                if DEBUG_MODE:
                    logger.info(
                        f"[官方保存] CM类型={cm_type}, 对话ID={conversation_id}, 消息数={len(history_list)}"
                    )
                    logger.info(f"[官方保存] 可用方法: {available}")
                    logger.info(f"[官方保存] unified_msg_origin: {unified_msg_origin}")
            except Exception as e:
                logger.warning(f"[官方保存] 记录CM信息失败: {e}")

            # 优先尝试以列表直接保存（按照旧插件的方式）
            for m in methods:
                if hasattr(cm, m):
                    # 尝试位置参数+列表
                    try:
                        if DEBUG_MODE:
                            logger.info(
                                f"[官方保存] >>> 尝试 {m} 使用列表参数，历史长度={len(history_list)}"
                            )
                        await getattr(cm, m)(
                            unified_msg_origin, conversation_id, history_list
                        )

                        logger.info(f"✅ [官方保存] {m} 成功（列表）")

                        # 验证是否真的保存成功
                        try:
                            verification = await cm.get_conversation(
                                unified_msg_origin, conversation_id
                            )
                            if verification:
                                if DEBUG_MODE:
                                    logger.info(
                                        f"✅ [官方保存] 验证成功：对话存在，ID={conversation_id}"
                                    )
                            else:
                                logger.warning(
                                    f"[官方保存] 验证失败：无法获取刚保存的对话"
                                )
                        except Exception as ve:
                            logger.warning(f"[官方保存] 验证检查失败: {ve}")

                        return True
                    except TypeError as te:
                        # 参数类型不匹配，尝试字符串格式
                        if DEBUG_MODE:
                            logger.info(f"[官方保存] {m} 列表参数类型不匹配: {te}")
                    except Exception as e:
                        logger.warning(f"[官方保存] {m}（列表）失败: {e}")

                    # 尝试字符串格式
                    try:
                        history_str = json.dumps(history_list, ensure_ascii=False)
                        if DEBUG_MODE:
                            logger.info(
                                f"[官方保存] >>> 尝试 {m} 使用字符串参数，长度={len(history_str)}"
                            )
                        await getattr(cm, m)(
                            unified_msg_origin, conversation_id, history_str
                        )

                        logger.info(f"✅ [官方保存] {m} 成功（字符串）")
                        return True
                    except Exception as e2:
                        logger.warning(f"[官方保存] {m}（字符串）失败: {e2}")

            logger.error(
                f"❌ [官方保存] 所有保存方法均失败！消息可能未保存到官方系统！"
            )
            return False

        except Exception as e:
            logger.error(f"[官方保存] 尝试官方持久化时发生严重异常: {e}", exc_info=True)
            return False

    @staticmethod
    async def save_to_official_conversation_with_cache(
        event: AstrMessageEvent,
        cached_messages: list,
        user_message: str,
        bot_message: str,
        context: "Context",
    ) -> bool:
        """
        保存到官方对话系统，支持缓存转正

        将缓存的未回复消息一起保存，避免上下文断裂

        Args:
            event: 消息事件
            cached_messages: 待转正的缓存消息（已去重）
            user_message: 当前用户消息（原始，不带元数据）
            bot_message: AI回复
            context: Context对象

        Returns:
            是否成功
        """
        try:
            # 导入 MessageCleaner
            from .message_cleaner import MessageCleaner

            # 清理消息，确保不包含系统提示词
            user_message = MessageCleaner.clean_message(user_message) or user_message
            bot_message = MessageCleaner.clean_message(bot_message) or bot_message

            # 清理缓存消息
            if cached_messages:
                for msg in cached_messages:
                    if isinstance(msg, dict) and "content" in msg:
                        original_content = msg["content"]
                        cleaned_content = MessageCleaner.clean_message(original_content)
                        if cleaned_content:
                            msg["content"] = cleaned_content

            # 1. 获取unified_msg_origin（会话标识）
            unified_msg_origin = event.unified_msg_origin
            if DEBUG_MODE:
                logger.info(f"========== [官方保存+缓存转正] 开始保存 ==========")
                logger.info(
                    f"[官方保存+缓存转正] unified_msg_origin: {unified_msg_origin}"
                )
                logger.info(f"[官方保存+缓存转正] 缓存消息: {len(cached_messages)} 条")
                logger.info(
                    f"[官方保存+缓存转正] 用户消息长度: {len(user_message)} 字符"
                )
                logger.info(f"[官方保存+缓存转正] AI回复长度: {len(bot_message)} 字符")

            # 2. 获取conversation_manager
            cm = context.conversation_manager
            if DEBUG_MODE:
                logger.info(
                    f"[官方保存+缓存转正] ConversationManager类型: {type(cm).__name__}"
                )

            # 3. 获取当前对话ID，如果没有则创建
            curr_cid = await cm.get_curr_conversation_id(unified_msg_origin)
            if DEBUG_MODE:
                logger.info(f"[官方保存+缓存转正] 当前对话ID: {curr_cid}")

            if not curr_cid:
                if DEBUG_MODE:
                    logger.info(
                        f"[官方保存+缓存转正] ❗ 会话 {unified_msg_origin} 没有对话，准备创建新对话"
                    )
                # 获取群名作为标题
                chat_id = (
                    event.get_group_id()
                    if not event.is_private_chat()
                    else event.get_sender_id()
                )
                title = (
                    f"群聊 {chat_id}"
                    if not event.is_private_chat()
                    else f"私聊 {event.get_sender_name()}"
                )
                if DEBUG_MODE:
                    logger.info(f"[官方保存+缓存转正] 新对话标题: {title}")
                    logger.info(
                        f"[官方保存+缓存转正] 平台ID: {event.get_platform_id()}"
                    )

                # 使用new_conversation创建
                try:
                    curr_cid = await cm.new_conversation(
                        unified_msg_origin=unified_msg_origin,
                        platform_id=event.get_platform_id(),
                        title=title,
                        content=[],
                    )
                    if DEBUG_MODE:
                        logger.info(
                            f"✅ [官方保存+缓存转正] 成功创建新对话，ID: {curr_cid}"
                        )
                except Exception as create_err:
                    logger.error(
                        f"❌ [官方保存+缓存转正] 创建对话失败: {create_err}",
                        exc_info=True,
                    )
                    return False

            if not curr_cid:
                logger.error(f"❌ [官方保存+缓存转正] 无法创建或获取对话ID")
                return False

            # 4. 获取当前对话的历史记录
            if DEBUG_MODE:
                logger.info(f"[官方保存+缓存转正] 正在获取对话历史...")
            try:
                conversation = await cm.get_conversation(
                    unified_msg_origin=unified_msg_origin, conversation_id=curr_cid
                )
                if DEBUG_MODE:
                    logger.info(
                        f"[官方保存+缓存转正] 获取对话对象: {conversation is not None}"
                    )
                if conversation:
                    if DEBUG_MODE:
                        logger.info(
                            f"[官方保存+缓存转正] 对话对象类型: {type(conversation).__name__}"
                        )
                        logger.info(
                            f"[官方保存+缓存转正] 对话标题: {getattr(conversation, 'title', 'N/A')}"
                        )
            except Exception as get_err:
                logger.error(
                    f"❌ [官方保存+缓存转正] 获取对话失败: {get_err}", exc_info=True
                )
                conversation = None

            # 5. 构建完整的历史列表
            if conversation and conversation.history:
                # history是JSON字符串，需要解析
                try:
                    history_list = json.loads(conversation.history)
                    if DEBUG_MODE:
                        logger.info(
                            f"[官方保存+缓存转正] 解析历史记录成功: {len(history_list)} 条"
                        )
                except (json.JSONDecodeError, TypeError) as parse_err:
                    logger.warning(f"[官方保存+缓存转正] 解析历史记录失败: {parse_err}")
                    history_list = []
            else:
                if DEBUG_MODE:
                    logger.info(f"[官方保存+缓存转正] 对话历史为空，从头开始")
                history_list = []

            # 6. 添加需要转正的缓存消息（去重）
            cache_converted = 0
            if cached_messages:
                if DEBUG_MODE:
                    logger.info(f"[官方保存+缓存转正] 开始处理缓存消息转正...")

                # 提取现有历史中的消息内容（用于去重）
                # 辅助函数：将content转换为可哈希格式
                def make_content_hashable(content):
                    """将content转换为可哈希格式，处理多模态消息（list类型）"""
                    if isinstance(content, list):
                        # 多模态消息，转为JSON字符串以便哈希
                        return json.dumps(content, ensure_ascii=False, sort_keys=True)
                    return content  # 字符串或其他可哈希类型

                existing_contents = set()
                for msg in history_list:
                    if isinstance(msg, dict) and "content" in msg:
                        try:
                            hashable_content = make_content_hashable(msg["content"])
                            existing_contents.add(hashable_content)
                        except (TypeError, ValueError) as e:
                            # 如果转换失败，记录警告并跳过
                            if DEBUG_MODE:
                                logger.warning(
                                    f"[官方保存+缓存转正] 无法哈希content: {e}"
                                )
                            continue

                if DEBUG_MODE:
                    logger.info(
                        f"[官方保存+缓存转正] 现有历史内容数: {len(existing_contents)} 条"
                    )

                # 过滤并添加不重复的缓存消息
                added_count = 0
                skipped_count = 0
                for cached_msg in cached_messages:
                    if isinstance(cached_msg, dict) and "content" in cached_msg:
                        try:
                            hashable_content = make_content_hashable(
                                cached_msg["content"]
                            )
                            if hashable_content not in existing_contents:
                                history_list.append(
                                    {"role": "user", "content": cached_msg["content"]}
                                )
                                existing_contents.add(
                                    hashable_content
                                )  # 避免缓存内部重复
                                added_count += 1
                            else:
                                skipped_count += 1
                        except (TypeError, ValueError) as e:
                            # 如果转换失败，仍然添加消息但不做去重
                            if DEBUG_MODE:
                                logger.warning(
                                    f"[官方保存+缓存转正] 缓存消息content转换失败: {e}，仍添加"
                                )
                            history_list.append(
                                {"role": "user", "content": cached_msg["content"]}
                            )
                            added_count += 1

                cache_converted = added_count
                if DEBUG_MODE:
                    logger.info(
                        f"[官方保存+缓存转正] 缓存消息处理完成: 总数={len(cached_messages)}, 添加={added_count}, 跳过(重复)={skipped_count}"
                    )
            else:
                if DEBUG_MODE:
                    logger.info(f"[官方保存+缓存转正] 无缓存消息需要转正")

            # 7. 添加当前用户消息
            history_list.append({"role": "user", "content": user_message})
            if DEBUG_MODE:
                logger.info(f"[官方保存+缓存转正] 添加用户消息: {user_message[:50]}...")

            # 8. 添加AI回复
            history_list.append({"role": "assistant", "content": bot_message})
            if DEBUG_MODE:
                logger.info(f"[官方保存+缓存转正] 添加AI回复: {bot_message[:50]}...")

            if DEBUG_MODE:
                logger.info(
                    f"[官方保存+缓存转正] 准备保存，总消息数: {len(history_list)} 条"
                )

            # 🔧 修复：限制历史长度，避免向量检索token溢出
            # 保留最近150条消息（约75轮对话），防止无限增长
            MAX_HISTORY_LENGTH = 150
            if len(history_list) > MAX_HISTORY_LENGTH:
                original_length = len(history_list)
                history_list = history_list[-MAX_HISTORY_LENGTH:]
                if DEBUG_MODE:
                    logger.info(
                        f"[官方保存+缓存转正] ⚠️ 历史过长，已截断: {original_length} -> {MAX_HISTORY_LENGTH} 条"
                    )
                else:
                    logger.info(
                        f"[官方保存+缓存转正] 历史截断: {original_length} -> {MAX_HISTORY_LENGTH} 条（避免向量检索溢出）"
                    )

            if DEBUG_MODE:
                logger.info(
                    f"[官方保存+缓存转正] ========== 调用底层保存方法 =========="
                )

            # 9. 使用官方API保存
            success = await ContextManager._try_official_save(
                cm, unified_msg_origin, curr_cid, history_list
            )

            if success:
                # 计算实际转正的缓存数量
                cache_converted = len(
                    [
                        m
                        for m in cached_messages
                        if isinstance(m, dict) and "content" in m
                    ]
                )

                logger.info(f"=" * 60)
                logger.info(f"✅✅✅ [官方保存+缓存转正] 保存成功！")
                logger.info(f"  对话ID: {curr_cid}")
                logger.info(f"  总消息数: {len(history_list)}")
                logger.info(f"  缓存转正: {cache_converted} 条")
                logger.info(f"  新增消息: 用户1条 + AI1条")
                logger.info(f"=" * 60)
                return True
            else:
                logger.error(f"❌❌❌ [官方保存+缓存转正] 保存失败！所有方法均失败！")
                return False

        except Exception as e:
            logger.error(
                f"❌❌❌ [官方保存+缓存转正] 保存过程发生严重异常: {e}", exc_info=True
            )
            return False
