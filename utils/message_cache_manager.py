"""
消息缓存管理器
负责统一管理待决策消息的缓存、读取、合并和转正保存

作者: Him666233
版本: v1.2.1
"""

import time
from typing import List, Dict, Optional, Set, Tuple
from astrbot.api.event import AstrMessageEvent
from astrbot.api.platform import AstrBotMessage, MessageMember, MessageType
from astrbot.api import logger

from .message_processor import MessageProcessor
from .message_cleaner import MessageCleaner
from .proactive_chat_manager import ProactiveChatManager


class MessageCacheManager:
    """
    消息缓存管理器 - 统一管理所有缓存操作

    主要功能：
    1. 添加消息到缓存（自动清理过期、限制数量）
    2. 读取缓存消息并合并到上下文
    3. 准备缓存转正保存（添加元数据、去重）
    4. 清理已保存的缓存
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 600,
        max_cache_count: int = 20,
        debug_mode: bool = False,
        include_timestamp: bool = True,
        include_sender_info: bool = True,
    ):
        """
        初始化缓存管理器

        Args:
            cache_ttl_seconds: 缓存过期时间（秒）
            max_cache_count: 每个会话的最大缓存条数
            debug_mode: 是否开启调试模式
            include_timestamp: 转正时是否包含时间戳
            include_sender_info: 转正时是否包含发送者信息
        """
        self.pending_messages_cache: Dict[str, List[dict]] = {}
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_cache_count = max_cache_count
        self.debug_mode = debug_mode
        self.include_timestamp = include_timestamp
        self.include_sender_info = include_sender_info

    def add_to_cache(
        self,
        chat_id: str,
        message_data: dict,
        source: str = "unknown",
    ) -> int:
        """
        添加消息到缓存

        Args:
            chat_id: 会话ID
            message_data: 消息数据字典，应包含：
                - role: 角色（user/assistant）
                - content: 消息内容
                - timestamp: 缓存时间戳
                - message_id: 消息ID
                - sender_id: 发送者ID
                - sender_name: 发送者名称
                - message_timestamp: 消息原始时间戳
                - mention_info: @信息（可选）
                - is_at_message: 是否@消息
                - has_trigger_keyword: 是否触发关键词
                - poke_info: 戳一戳信息（可选）
                - image_urls: 图片URL列表（可选）
                - probability_filtered: 是否概率过滤（可选）
            source: 缓存来源（用于日志）

        Returns:
            缓存后的总条数
        """
        # 初始化缓存
        if chat_id not in self.pending_messages_cache:
            self.pending_messages_cache[chat_id] = []

        # ========== 🔧 优化：调整处理顺序防止误删新消息 ==========
        # 处理顺序：先清理过期 → 再限制数量 → 最后添加新消息
        # 这样可以避免新消息因缺少时间戳被过期检查误删
        # ============================================================

        # 步骤1: 清理过期消息（基于时间）
        if self.cache_ttl_seconds > 0:
            current_time = time.time()
            old_count = len(self.pending_messages_cache[chat_id])

            # 过滤掉过期消息
            self.pending_messages_cache[chat_id] = [
                msg
                for msg in self.pending_messages_cache[chat_id]
                if current_time
                - (msg.get("message_timestamp") or msg.get("timestamp", 0))
                < self.cache_ttl_seconds
            ]

            if self.debug_mode and old_count > len(
                self.pending_messages_cache[chat_id]
            ):
                removed = old_count - len(self.pending_messages_cache[chat_id])
                logger.info(
                    f"  [缓存管理器] 已清理过期缓存: {removed} 条（超过{self.cache_ttl_seconds}秒）"
                )

        # 步骤2: 限制缓存数量（在添加新消息前）
        if self.max_cache_count == 0:
            # 如果max_cache_count为0，清空所有缓存
            if self.pending_messages_cache[chat_id]:
                cleared = len(self.pending_messages_cache[chat_id])
                self.pending_messages_cache[chat_id] = []
                if self.debug_mode:
                    logger.info(
                        f"  [缓存管理器] 数量限制为0，清空所有缓存: {cleared} 条"
                    )
        elif self.max_cache_count > 0:
            # 如果当前缓存数量已达到或超过上限，需要删除旧消息为新消息预留空间
            current_count = len(self.pending_messages_cache[chat_id])
            if current_count >= self.max_cache_count:
                # 一次性排序，然后批量删除
                self.pending_messages_cache[chat_id].sort(
                    key=lambda m: m.get("message_timestamp") or m.get("timestamp", 0)
                )
                # 计算需要删除的数量（至少删除1条为新消息腾出空间）
                to_remove = current_count - self.max_cache_count + 1
                if self.debug_mode:
                    logger.info(
                        f"  [缓存管理器] 数量达到上限({self.max_cache_count}条)，批量移除最旧的{to_remove}条消息"
                    )
                # 批量删除
                self.pending_messages_cache[chat_id] = self.pending_messages_cache[
                    chat_id
                ][to_remove:]

        # 步骤3: 防御性去重检查（双重保险）
        # 🔧 虽然消息钩子已经做了去重，但这里再检查一次，防止异步逻辑导致的重复：
        #    场景：从平台 LTM 获取图片描述时，如果平台的 session_chats 中有重复记录
        #         （平台 LTM 没有去重机制），可能导致同一张图片被多次缓存
        message_id = message_data.get("message_id", "")
        if message_id:
            for cached_msg in self.pending_messages_cache[chat_id]:
                if cached_msg.get("message_id") == message_id:
                    if self.debug_mode:
                        content = message_data.get("content", "")
                        logger.info(
                            f"  [缓存防御性去重] 检测到重复 message_id，跳过: {content[:50]}..."
                        )
                    return len(self.pending_messages_cache[chat_id])

        # 步骤4: 添加新消息到缓存
        self.pending_messages_cache[chat_id].append(message_data)

        cache_count = len(self.pending_messages_cache[chat_id])

        # 日志输出
        logger.info(f"📦 [缓存-{source}] 已缓存消息 (共{cache_count}条)")

        if self.debug_mode:
            content_preview = (
                message_data.get("content", "")[:100]
                if message_data.get("content")
                else "(空)"
            )
            logger.info(f"  [缓存管理器] 缓存内容: {content_preview}...")

        return cache_count

    def get_cached_messages(
        self,
        chat_id: str,
        exclude_current: bool = True,
    ) -> List[dict]:
        """
        获取缓存消息（用于拼接上下文）

        Args:
            chat_id: 会话ID
            exclude_current: 是否排除最后一条（当前消息）

        Returns:
            过滤后的缓存消息列表
        """
        if chat_id not in self.pending_messages_cache:
            return []

        cached_messages = self.pending_messages_cache[chat_id]

        # 如果排除当前消息且至少有2条消息
        if exclude_current and len(cached_messages) > 1:
            cached_messages = cached_messages[:-1]
        elif exclude_current:
            # 只有1条消息，排除后为空
            return []

        # 过滤过期消息
        filtered_messages = ProactiveChatManager.filter_expired_cached_messages(
            cached_messages
        )

        return filtered_messages or []

    def merge_cache_to_history(
        self,
        chat_id: str,
        history_messages: Optional[List[AstrBotMessage]],
        event: AstrMessageEvent,
        exclude_current: bool = True,
    ) -> Tuple[List[AstrBotMessage], int, int]:
        """
        将缓存消息合并到历史消息

        Args:
            chat_id: 会话ID
            history_messages: 历史消息列表
            event: 消息事件（用于提取平台信息）
            exclude_current: 是否排除当前消息

        Returns:
            (merged_messages, cached_count, dedup_skipped_count)
            - merged_messages: 合并后的消息列表
            - cached_count: 缓存消息数量
            - dedup_skipped_count: 去重跳过的数量
        """
        if history_messages is None:
            history_messages = []

        # 获取缓存消息（仅普通缓存，排除窗口缓冲消息）
        try:
            cached_messages = self.get_regular_cached_messages(
                chat_id, exclude_current=exclude_current
            )
        except Exception:
            # 降级：使用所有缓存消息（老行为）
            cached_messages = self.get_cached_messages(
                chat_id, exclude_current=exclude_current
            )

        if not cached_messages:
            return history_messages, 0, 0

        cached_candidates_count = len(cached_messages)
        dedup_skipped = 0
        cached_messages_to_merge = []

        # 🔧 去重处理：防止缓存消息与官方历史存储重复
        # 注意：这里的去重与消息钩子的去重目的不同：
        #   - 消息钩子去重：防止平台重复推送同一消息（同一个 event 被推送多次）
        #   - 这里的去重：防止缓存消息与官方存储的历史消息重复（已转正的消息不应再次合并）
        if history_messages:
            # 构建去重集合（只存储 message_id）
            history_message_ids = set()

            for msg in history_messages:
                if isinstance(msg, AstrBotMessage):
                    # 收集 message_id
                    msg_id = getattr(msg, "message_id", None)
                    if (
                        msg_id
                        and not msg_id.startswith("cached_")
                        and not msg_id.startswith("official_")
                    ):
                        history_message_ids.add(msg_id)
                elif isinstance(msg, dict) and "message_id" in msg:
                    msg_id = msg.get("message_id")
                    if (
                        msg_id
                        and not str(msg_id).startswith("cached_")
                        and not str(msg_id).startswith("official_")
                    ):
                        history_message_ids.add(msg_id)

            # 检查每条缓存消息是否重复（只检查 message_id）
            for cached_msg in cached_messages:
                if isinstance(cached_msg, dict):
                    cached_msg_id = cached_msg.get("message_id")

                    # 只使用 message_id 判断是否重复
                    if cached_msg_id and not str(cached_msg_id).startswith("cached_"):
                        if cached_msg_id in history_message_ids:
                            dedup_skipped += 1
                            if self.debug_mode:
                                content = cached_msg.get("content", "")
                                logger.info(
                                    f"  [缓存去重] 跳过重复消息（message_id已存在）: {content[:50]}..."
                                )
                            continue

                    # 未重复，添加到合并列表
                    cached_messages_to_merge.append(cached_msg)
                    # 记录到去重集合
                    if cached_msg_id and not str(cached_msg_id).startswith("cached_"):
                        history_message_ids.add(cached_msg_id)
        else:
            cached_messages_to_merge = cached_messages

        if self.debug_mode:
            logger.info(
                f"  [缓存管理器] 缓存候选: {cached_candidates_count} 条, "
                f"去重跳过: {dedup_skipped} 条, 计划合并: {len(cached_messages_to_merge)} 条"
            )

        # 转换为 AstrBotMessage 对象
        cached_astrbot_messages = []
        for cached_msg in cached_messages_to_merge:
            if isinstance(cached_msg, dict):
                try:
                    msg_obj = AstrBotMessage()
                    msg_obj.message_str = cached_msg.get("content", "")
                    msg_obj.platform_name = event.get_platform_name()
                    msg_obj.timestamp = cached_msg.get(
                        "message_timestamp"
                    ) or cached_msg.get("timestamp", time.time())
                    msg_obj.type = (
                        MessageType.GROUP_MESSAGE
                        if not event.is_private_chat()
                        else MessageType.FRIEND_MESSAGE
                    )
                    if not event.is_private_chat():
                        msg_obj.group_id = event.get_group_id()
                    msg_obj.self_id = event.get_self_id()
                    msg_obj.session_id = (
                        event.session_id if hasattr(event, "session_id") else chat_id
                    )
                    msg_obj.message_id = (
                        f"cached_{cached_msg.get('timestamp', time.time())}"
                    )

                    # 设置发送者信息
                    sender_id = cached_msg.get("sender_id", "")
                    sender_name = cached_msg.get("sender_name", "未知用户")
                    if sender_id:
                        msg_obj.sender = MessageMember(
                            user_id=sender_id, nickname=sender_name
                        )

                    cached_astrbot_messages.append(msg_obj)
                except Exception as e:
                    logger.warning(
                        f"[缓存管理器] 转换缓存消息为 AstrBotMessage 失败: {e}，跳过该消息"
                    )
            else:
                cached_astrbot_messages.append(cached_msg)

        # 合并并排序
        if cached_astrbot_messages:
            all_messages = history_messages + cached_astrbot_messages
            all_messages.sort(
                key=lambda msg: (
                    msg.timestamp if hasattr(msg, "timestamp") and msg.timestamp else 0
                )
            )

            if self.debug_mode:
                logger.info(
                    f"  [缓存管理器] 已合并 {len(cached_astrbot_messages)} 条缓存消息到历史"
                )

            return all_messages, len(cached_astrbot_messages), dedup_skipped

        return history_messages, 0, dedup_skipped

    def prepare_cache_for_save(
        self,
        chat_id: str,
        current_msg_id: Optional[str],
        current_msg_timestamp: Optional[float],
        processing_msg_ids: Set[str],
        proactive_processing: bool = False,
    ) -> List[dict]:
        """
        准备要转正保存的缓存消息

        Args:
            chat_id: 会话ID
            current_msg_id: 当前消息ID
            current_msg_timestamp: 当前消息时间戳
            processing_msg_ids: 正在处理中的消息ID集合
            proactive_processing: 是否主动对话正在处理

        Returns:
            待转正的缓存消息列表（已添加元数据）
        """
        if chat_id not in self.pending_messages_cache:
            return []

        if len(self.pending_messages_cache[chat_id]) == 0:
            return []

        # 如果主动对话正在处理，跳过缓存转正
        if proactive_processing:
            if self.debug_mode:
                logger.info(f"  [缓存管理器] 主动对话正在处理，跳过缓存转正")
            return []

        # 过滤要转正的消息（Phase-1：仅处理普通缓存，跳过窗口缓冲消息）
        raw_cached = []
        skipped_processing = 0
        skipped_window_buffered = 0

        for msg in self.pending_messages_cache[chat_id]:
            msg_id = msg.get("message_id")
            msg_timestamp = msg.get("timestamp", 0)

            # 跳过窗口缓冲消息（Phase-2 单独保存）
            if msg.get("window_buffered", False):
                skipped_window_buffered += 1
                continue

            # 排除当前消息
            if current_msg_id and msg_id == current_msg_id:
                continue

            # 排除正在处理中的消息（这些消息会自己保存）
            if msg_id and msg_id in processing_msg_ids:
                skipped_processing += 1
                if self.debug_mode:
                    logger.info(
                        f"  [缓存管理器] 跳过正在处理中的消息: {msg_id[:30]}..."
                    )
                continue

            # 只保存时间戳早于当前消息的缓存消息
            if current_msg_timestamp and msg_timestamp >= current_msg_timestamp:
                continue

            raw_cached.append(msg)

        if self.debug_mode and skipped_window_buffered > 0:
            logger.info(
                f"  [缓存管理器] Phase-1 跳过 {skipped_window_buffered} 条窗口缓冲消息（待Phase-2保存）"
            )

        if skipped_processing > 0:
            logger.info(
                f"  [缓存管理器] 跳过 {skipped_processing} 条正在处理中的消息（并发保护）"
            )

        if not raw_cached:
            return []

        logger.info(f"  [缓存管理器] 发现 {len(raw_cached)} 条待转正的缓存消息")

        # 处理每条缓存消息，添加元数据
        cached_messages_to_convert = []
        for cached_msg in raw_cached:
            if isinstance(cached_msg, dict) and "content" in cached_msg:
                # 获取处理后的消息内容（不含元数据）
                raw_content = cached_msg["content"]

                # 确定触发方式
                trigger_type = None
                if cached_msg.get("has_trigger_keyword"):
                    trigger_type = "keyword"
                elif cached_msg.get("is_at_message"):
                    trigger_type = "at"
                else:
                    trigger_type = "ai_decision"

                # 使用缓存中保存的发送者信息添加元数据
                msg_content = MessageProcessor.add_metadata_from_cache(
                    raw_content,
                    cached_msg.get("sender_id", "unknown"),
                    cached_msg.get("sender_name", "未知用户"),
                    cached_msg.get("message_timestamp") or cached_msg.get("timestamp"),
                    self.include_timestamp,
                    self.include_sender_info,
                    cached_msg.get("mention_info"),
                    trigger_type,
                    cached_msg.get("poke_info"),
                )

                # 清理系统提示
                msg_content = MessageCleaner.clean_message(msg_content)

                # 保存图片URL
                cached_image_urls = cached_msg.get("image_urls", [])

                # 添加到转正列表
                convert_entry = {
                    "role": cached_msg.get("role", "user"),
                    "content": msg_content,
                }

                if cached_image_urls:
                    convert_entry["image_urls"] = cached_image_urls

                cached_messages_to_convert.append(convert_entry)

                if self.debug_mode:
                    sender_info = f"{cached_msg.get('sender_name')}(ID: {cached_msg.get('sender_id')})"
                    image_info = (
                        f", 图片{len(cached_image_urls)}张" if cached_image_urls else ""
                    )
                    logger.info(
                        f"  [缓存管理器] 转正消息（已添加元数据，发送者: {sender_info}{image_info}）: {msg_content[:100]}..."
                    )

        return cached_messages_to_convert

    def clear_saved_cache(
        self,
        chat_id: str,
        current_msg_id: Optional[str],
        current_msg_timestamp: Optional[float],
        processing_msg_ids: Set[str],
        proactive_processing: bool = False,
    ) -> Tuple[int, int]:
        """
        清理已保存的缓存

        Args:
            chat_id: 会话ID
            current_msg_id: 当前消息ID
            current_msg_timestamp: 当前消息时间戳
            processing_msg_ids: 正在处理中的消息ID集合
            proactive_processing: 是否主动对话正在处理

        Returns:
            (cleared_count, remaining_count)
        """
        if chat_id not in self.pending_messages_cache:
            return 0, 0

        # 如果主动对话正在处理，跳过缓存清理
        if proactive_processing:
            logger.info(
                f"  [缓存管理器] 主动对话正在处理，跳过缓存清理（由主动对话负责）"
            )
            return 0, len(self.pending_messages_cache[chat_id])

        original_count = len(self.pending_messages_cache[chat_id])

        # 保留：时间戳晚于当前消息的 或 正在处理中的消息 或 窗口缓冲消息
        new_cache = []
        for msg in self.pending_messages_cache[chat_id]:
            msg_id = msg.get("message_id")
            msg_timestamp = msg.get("timestamp", 0)

            # 保留窗口缓冲消息（Phase-1 不清除，等 Phase-2 处理）
            if msg.get("window_buffered", False):
                new_cache.append(msg)
                continue

            # 保留正在处理中的消息（排除当前消息）
            if msg_id and msg_id in processing_msg_ids and msg_id != current_msg_id:
                new_cache.append(msg)
                continue

            # 保留时间戳晚于当前消息的缓存消息
            if current_msg_timestamp and msg_timestamp > current_msg_timestamp:
                new_cache.append(msg)
                continue

        self.pending_messages_cache[chat_id] = new_cache
        cleared_count = original_count - len(new_cache)
        remaining_count = len(new_cache)

        if remaining_count > 0:
            logger.info(
                f"  [缓存管理器] 已清理 {cleared_count} 条已保存的缓存消息，"
                f"保留 {remaining_count} 条（正在处理中或后续消息）"
            )
        else:
            logger.info(f"  [缓存管理器] 已清空消息缓存: {cleared_count} 条")
            # 会话已无缓存消息，移除 key 防止 dict 无限膨胀
            del self.pending_messages_cache[chat_id]

        return cleared_count, remaining_count

    def get_cache_count(self, chat_id: str) -> int:
        """获取缓存消息数量"""
        if chat_id not in self.pending_messages_cache:
            return 0
        return len(self.pending_messages_cache[chat_id])

    def has_cache(self, chat_id: str) -> bool:
        """检查是否有缓存消息"""
        return self.get_cache_count(chat_id) > 0

    def get_regular_cached_messages(
        self,
        chat_id: str,
        exclude_current: bool = True,
    ) -> List[dict]:
        """
        获取普通缓存消息（排除窗口缓冲消息，用于合并到历史上下文）

        Args:
            chat_id: 会话ID
            exclude_current: 是否排除最后一条（当前消息）

        Returns:
            过滤后的普通缓存消息列表（不含 window_buffered=True 的消息）
        """
        if chat_id not in self.pending_messages_cache:
            return []

        cached_messages = self.pending_messages_cache[chat_id]

        # 如果排除当前消息且至少有2条消息
        if exclude_current and len(cached_messages) > 1:
            cached_messages = cached_messages[:-1]
        elif exclude_current:
            return []

        # 过滤掉窗口缓冲消息
        regular_messages = [
            msg for msg in cached_messages if not msg.get("window_buffered", False)
        ]

        # 过滤过期消息
        filtered_messages = ProactiveChatManager.filter_expired_cached_messages(
            regular_messages
        )

        return filtered_messages or []

    def get_window_buffered_messages(
        self,
        chat_id: str,
    ) -> List[dict]:
        """
        获取窗口缓冲消息（用于拼接到当前消息下方的追加区域）

        Args:
            chat_id: 会话ID

        Returns:
            窗口缓冲消息列表（window_buffered=True 的消息），按时间排序
        """
        if chat_id not in self.pending_messages_cache:
            return []

        window_msgs = [
            msg
            for msg in self.pending_messages_cache[chat_id]
            if msg.get("window_buffered", False)
        ]

        # 按时间排序
        window_msgs.sort(
            key=lambda m: m.get("message_timestamp") or m.get("timestamp", 0)
        )

        return window_msgs

    def prepare_window_buffered_for_save(
        self,
        chat_id: str,
        processing_msg_ids: Optional[Set[str]] = None,
    ) -> List[dict]:
        """
        准备窗口缓冲消息的转正数据（Phase-2 保存，在AI回复之后）

        Args:
            chat_id: 会话ID
            processing_msg_ids: 正在处理中的消息ID集合

        Returns:
            待转正的窗口缓冲消息列表（已添加元数据）
        """
        if processing_msg_ids is None:
            processing_msg_ids = set()

        window_msgs = self.get_window_buffered_messages(chat_id)
        if not window_msgs:
            return []

        logger.info(
            f"  [缓存管理器] Phase-2: 发现 {len(window_msgs)} 条窗口缓冲消息待转正"
        )

        cached_messages_to_convert = []
        for cached_msg in window_msgs:
            if not isinstance(cached_msg, dict) or "content" not in cached_msg:
                continue

            msg_id = cached_msg.get("message_id")
            # 跳过正在处理中的消息
            if msg_id and msg_id in processing_msg_ids:
                continue

            raw_content = cached_msg["content"]

            # 确定触发方式
            trigger_type = None
            if cached_msg.get("has_trigger_keyword"):
                trigger_type = "keyword"
            elif cached_msg.get("is_at_message"):
                trigger_type = "at"
            else:
                trigger_type = "ai_decision"

            # 使用缓存中保存的发送者信息添加元数据
            msg_content = MessageProcessor.add_metadata_from_cache(
                raw_content,
                cached_msg.get("sender_id", "unknown"),
                cached_msg.get("sender_name", "未知用户"),
                cached_msg.get("message_timestamp") or cached_msg.get("timestamp"),
                self.include_timestamp,
                self.include_sender_info,
                cached_msg.get("mention_info"),
                trigger_type,
                cached_msg.get("poke_info"),
            )

            # 清理系统提示
            msg_content = MessageCleaner.clean_message(msg_content)

            # 保存图片URL
            cached_image_urls = cached_msg.get("image_urls", [])

            convert_entry = {
                "role": cached_msg.get("role", "user"),
                "content": msg_content,
            }

            if cached_image_urls:
                convert_entry["image_urls"] = cached_image_urls

            cached_messages_to_convert.append(convert_entry)

            if self.debug_mode:
                sender_info = f"{cached_msg.get('sender_name')}(ID: {cached_msg.get('sender_id')})"
                logger.info(
                    f"  [缓存管理器] Phase-2 转正消息（发送者: {sender_info}）: {msg_content[:100]}..."
                )

        return cached_messages_to_convert

    def clear_window_buffered_cache(
        self,
        chat_id: str,
        saved_msg_ids: Optional[Set[str]] = None,
    ) -> Tuple[int, int]:
        """
        清理已保存的窗口缓冲消息（Phase-2 完成后调用）

        Args:
            chat_id: 会话ID
            saved_msg_ids: 已保存的消息ID集合（仅清除这些消息）。
                          为 None 时清除所有窗口缓冲消息。

        Returns:
            (cleared_count, remaining_count)
        """
        if chat_id not in self.pending_messages_cache:
            return 0, 0

        original_count = len(self.pending_messages_cache[chat_id])

        if saved_msg_ids is not None:
            # 仅清除已保存的窗口缓冲消息
            self.pending_messages_cache[chat_id] = [
                msg
                for msg in self.pending_messages_cache[chat_id]
                if not (
                    msg.get("window_buffered", False)
                    and msg.get("message_id") in saved_msg_ids
                )
            ]
        else:
            # 清除所有窗口缓冲消息
            self.pending_messages_cache[chat_id] = [
                msg
                for msg in self.pending_messages_cache[chat_id]
                if not msg.get("window_buffered", False)
            ]

        remaining_count = len(self.pending_messages_cache[chat_id])
        cleared_count = original_count - remaining_count

        if remaining_count == 0 and chat_id in self.pending_messages_cache:
            del self.pending_messages_cache[chat_id]

        if cleared_count > 0:
            logger.info(
                f"  [缓存管理器] Phase-2: 已清理 {cleared_count} 条窗口缓冲消息"
            )

        return cleared_count, remaining_count
