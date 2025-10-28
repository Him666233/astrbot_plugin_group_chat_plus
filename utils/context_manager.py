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
版本: v1.0.0
"""

from typing import List, Dict, Any, Optional
from astrbot.api.all import *
import os
import json
from datetime import datetime


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
            data_dir: 数据目录路径，如果为None则使用默认路径
        """
        if data_dir:
            # 使用插件提供的数据目录
            ContextManager.base_storage_path = os.path.join(data_dir, "chat_history")
        else:
            # 向后兼容：使用旧的硬编码路径
            ContextManager.base_storage_path = os.path.join(
                os.getcwd(), "data", "chat_history"
            )

        if not os.path.exists(ContextManager.base_storage_path):
            os.makedirs(ContextManager.base_storage_path, exist_ok=True)
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
            # 返回空消息对象
            return AstrBotMessage()

    @staticmethod
    def _get_storage_path(platform_name: str, is_private: bool, chat_id: str) -> str:
        """
        获取历史消息的本地存储路径

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID

        Returns:
            JSON文件路径
        """
        if not ContextManager.base_storage_path:
            ContextManager.init()

        chat_type = "private" if is_private else "group"
        directory = os.path.join(
            ContextManager.base_storage_path, platform_name, chat_type
        )

        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        return os.path.join(directory, f"{chat_id}.json")

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
                logger.debug("配置为不获取历史消息")
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

            if not os.path.exists(file_path):
                logger.debug(f"历史消息文件不存在: {file_path}")
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

            # 如果配置为-1,返回所有历史消息
            if max_messages == -1:
                logger.debug(f"获取所有历史消息,共 {len(history)} 条")
                return history

            # 限制消息数量,只保留最新的
            if len(history) > max_messages:
                history = history[-max_messages:]
                logger.debug(f"历史消息超过限制,只保留最新的 {max_messages} 条")
            else:
                logger.debug(f"获取历史消息 {len(history)} 条")

            return history

        except Exception as e:
            logger.error(f"读取历史消息失败: {e}")
            return []

    @staticmethod
    async def format_context_for_ai(
        history_messages: List[AstrBotMessage], current_message: str, bot_id: str
    ) -> str:
        """
        将历史消息格式化为AI可理解的文本

        Args:
            history_messages: 历史消息列表
            current_message: 当前消息
            bot_id: 机器人ID，用于识别自己的回复

        Returns:
            格式化后的文本
        """
        try:
            formatted_parts = []

            # 如果有历史消息,添加历史消息部分
            if history_messages:
                formatted_parts.append("=== 历史消息上下文 ===")

                for msg in history_messages:
                    # 获取发送者信息
                    sender_name = "未知用户"
                    sender_id = "unknown"
                    is_bot = False

                    if hasattr(msg, "sender") and msg.sender:
                        sender_name = msg.sender.nickname or "未知用户"
                        sender_id = msg.sender.user_id or "unknown"
                        # 判断是否是机器人自己的消息
                        is_bot = sender_id == bot_id

                    # 获取消息时间
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
                        from astrbot.api.message_components import Plain

                        for comp in msg.message:
                            if isinstance(comp, Plain):
                                message_content += comp.text

                    # 格式化消息
                    if is_bot:
                        # AI自己的回复,特殊标注
                        formatted_parts.append(
                            f"[{time_str}] 你自己回复: {message_content}"
                        )
                    else:
                        # 其他用户的消息
                        formatted_parts.append(
                            f"[{time_str}] {sender_name}(ID:{sender_id}): {message_content}"
                        )

                formatted_parts.append("")  # 空行分隔

            # 添加当前消息部分
            formatted_parts.append("=== 当前新消息 ===")
            formatted_parts.append(current_message)

            result = "\n".join(formatted_parts)
            logger.debug(f"上下文格式化完成,总长度: {len(result)} 字符")
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
            user_msg.message_str = message_text
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

            # 保存到自定义文件（使用安全的JSON序列化）
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            history_dicts = [ContextManager._message_to_dict(msg) for msg in history]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history_dicts, f, ensure_ascii=False, indent=2)

            logger.debug(f"用户消息已保存到自定义历史记录")

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
                                logger.debug(f"组件转换失败，跳过: {comp_err}")
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

                    logger.debug(
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
            bot_msg.message_str = bot_message_text
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
            bot_msg.sender = MessageMember(
                user_id=event.get_self_id(), nickname="AstrBot"
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

            # 保存到自定义文件（使用安全的JSON序列化）
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            history_dicts = [ContextManager._message_to_dict(msg) for msg in history]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(history_dicts, f, ensure_ascii=False, indent=2)

            logger.debug(f"AI回复消息已保存到自定义历史记录")

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
                                logger.debug(f"组件转换失败，跳过: {comp_err}")
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

                    logger.debug(
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
            logger.debug(
                f"[官方保存] 准备保存到官方对话系统，会话: {unified_msg_origin}"
            )

            # 2. 获取conversation_manager
            cm = context.conversation_manager

            # 3. 获取当前对话ID，如果没有则创建
            curr_cid = await cm.get_curr_conversation_id(unified_msg_origin)
            if not curr_cid:
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

            logger.debug(f"[官方保存] 当前对话有 {len(history_list)} 条历史消息")

            # 6. 添加用户消息和AI回复
            history_list.append({"role": "user", "content": user_message})
            history_list.append({"role": "assistant", "content": bot_message})

            logger.debug(
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
                        logger.debug(f"[官方保存] {m} 列表参数类型不匹配: {te}")
                    except Exception as e:
                        logger.warning(f"[官方保存] {m}（列表）失败: {e}")

                    # 尝试字符串格式
                    try:
                        history_str = json.dumps(history_list, ensure_ascii=False)
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
            # 1. 获取unified_msg_origin（会话标识）
            unified_msg_origin = event.unified_msg_origin
            logger.info(f"========== [官方保存+缓存转正] 开始保存 ==========")
            logger.info(f"[官方保存+缓存转正] unified_msg_origin: {unified_msg_origin}")
            logger.info(f"[官方保存+缓存转正] 缓存消息: {len(cached_messages)} 条")
            logger.info(f"[官方保存+缓存转正] 用户消息长度: {len(user_message)} 字符")
            logger.info(f"[官方保存+缓存转正] AI回复长度: {len(bot_message)} 字符")

            # 2. 获取conversation_manager
            cm = context.conversation_manager
            logger.info(
                f"[官方保存+缓存转正] ConversationManager类型: {type(cm).__name__}"
            )

            # 3. 获取当前对话ID，如果没有则创建
            curr_cid = await cm.get_curr_conversation_id(unified_msg_origin)
            logger.info(f"[官方保存+缓存转正] 当前对话ID: {curr_cid}")

            if not curr_cid:
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
                logger.info(f"[官方保存+缓存转正] 新对话标题: {title}")
                logger.info(f"[官方保存+缓存转正] 平台ID: {event.get_platform_id()}")

                # 使用new_conversation创建
                try:
                    curr_cid = await cm.new_conversation(
                        unified_msg_origin=unified_msg_origin,
                        platform_id=event.get_platform_id(),
                        title=title,
                        content=[],
                    )
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
            logger.info(f"[官方保存+缓存转正] 正在获取对话历史...")
            try:
                conversation = await cm.get_conversation(
                    unified_msg_origin=unified_msg_origin, conversation_id=curr_cid
                )
                logger.info(
                    f"[官方保存+缓存转正] 获取对话对象: {conversation is not None}"
                )
                if conversation:
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
                    logger.info(
                        f"[官方保存+缓存转正] 解析历史记录成功: {len(history_list)} 条"
                    )
                except (json.JSONDecodeError, TypeError) as parse_err:
                    logger.warning(f"[官方保存+缓存转正] 解析历史记录失败: {parse_err}")
                    history_list = []
            else:
                logger.info(f"[官方保存+缓存转正] 对话历史为空，从头开始")
                history_list = []

            # 6. 添加需要转正的缓存消息（去重）
            if cached_messages:
                logger.info(f"[官方保存+缓存转正] 开始处理缓存消息转正...")
                # 提取现有历史中的消息内容（用于去重）
                existing_contents = set()
                for msg in history_list:
                    if isinstance(msg, dict) and "content" in msg:
                        existing_contents.add(msg["content"])

                logger.info(
                    f"[官方保存+缓存转正] 现有历史内容数: {len(existing_contents)} 条"
                )

                # 过滤并添加不重复的缓存消息
                added_count = 0
                skipped_count = 0
                for cached_msg in cached_messages:
                    if isinstance(cached_msg, dict) and "content" in cached_msg:
                        if cached_msg["content"] not in existing_contents:
                            history_list.append(
                                {"role": "user", "content": cached_msg["content"]}
                            )
                            existing_contents.add(
                                cached_msg["content"]
                            )  # 避免缓存内部重复
                            added_count += 1
                        else:
                            skipped_count += 1

                logger.info(
                    f"[官方保存+缓存转正] 缓存消息处理完成: 总数={len(cached_messages)}, 添加={added_count}, 跳过(重复)={skipped_count}"
                )
            else:
                logger.info(f"[官方保存+缓存转正] 无缓存消息需要转正")

            # 7. 添加当前用户消息
            history_list.append({"role": "user", "content": user_message})
            logger.info(f"[官方保存+缓存转正] 添加用户消息: {user_message[:50]}...")

            # 8. 添加AI回复
            history_list.append({"role": "assistant", "content": bot_message})
            logger.info(f"[官方保存+缓存转正] 添加AI回复: {bot_message[:50]}...")

            logger.info(
                f"[官方保存+缓存转正] 准备保存，总消息数: {len(history_list)} 条"
            )
            logger.info(f"[官方保存+缓存转正] ========== 调用底层保存方法 ==========")

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
