"""
消息处理器模块
负责消息预处理，添加时间戳、发送者信息等元数据

作者: Him666233
版本: v1.0.0
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
        include_sender_info: bool
    ) -> str:
        """
        为消息添加元数据（时间戳和发送者）
        
        Args:
            event: 消息事件
            message_text: 原始消息
            include_timestamp: 是否包含时间戳
            include_sender_info: 是否包含发送者信息
            
        Returns:
            添加元数据后的文本
        """
        metadata_parts = []
        
        try:
            # 添加时间戳信息
            if include_timestamp:
                timestamp_str = MessageProcessor._format_timestamp(event)
                if timestamp_str:
                    metadata_parts.append(f"[时间: {timestamp_str}]")
            
            # 添加发送者信息
            if include_sender_info:
                sender_info = MessageProcessor._format_sender_info(event)
                if sender_info:
                    metadata_parts.append(sender_info)
            
            # 如果有元数据,则拼接到消息前面
            if metadata_parts:
                metadata_prefix = " ".join(metadata_parts)
                processed_message = f"{metadata_prefix}\n{message_text}"
                logger.debug(f"消息已添加元数据: {metadata_prefix}")
                return processed_message
            else:
                return message_text
                
        except Exception as e:
            logger.error(f"添加消息元数据时发生错误: {e}")
            # 发生错误时返回原始消息
            return message_text
    
    @staticmethod
    def _format_timestamp(event: AstrMessageEvent) -> str:
        """
        格式化时间戳
        
        格式：YYYY年MM月DD日 HH:MM:SS
        
        Args:
            event: 消息事件
            
        Returns:
            格式化的时间戳，失败返回空
        """
        try:
            # 尝试从消息对象获取时间戳
            if hasattr(event, 'message_obj') and hasattr(event.message_obj, 'timestamp'):
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
            is_bot = (sender_id == bot_id)
            
            if is_bot:
                logger.debug(f"检测到机器人自己的消息,将忽略: sender_id={sender_id}, bot_id={bot_id}")
            
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
        
        Args:
            event: 消息事件
            
        Returns:
            True=@了bot，False=没有@
        """
        try:
            # 检查消息链中是否有At组件指向机器人
            if hasattr(event, 'message_obj') and hasattr(event.message_obj, 'message'):
                from astrbot.api.message_components import At
                
                bot_id = event.get_self_id()
                message_chain = event.message_obj.message
                
                for component in message_chain:
                    if isinstance(component, At):
                        # 检查At的目标是否是机器人
                        if hasattr(component, 'qq') and str(component.qq) == str(bot_id):
                            logger.debug("检测到@机器人的消息")
                            return True
            
            return False
            
        except Exception as e:
            logger.error(f"判断@消息时发生错误: {e}")
            return False

