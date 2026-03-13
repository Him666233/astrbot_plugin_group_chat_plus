"""
私信功能主处理模块

与群聊功能独立的私信处理逻辑，主要特点：
1. 每条消息都回复（无概率筛选和读空气AI）
2. 支持消息聚合（等待一段时间合并多条消息）
3. 独立配置（可与群聊配置不同）
4. 黑名单模式（禁用指定用户）
5. 图片处理（支持多模态直传和图片转文字，含省钱缓存）

作者: Him666233
版本: v1.2.1
"""

import time
import asyncio
import random
from typing import Optional, List, Dict, Any
from pathlib import Path

from astrbot.api.all import *
from astrbot.api import logger

# 私信专用图片处理器
from .private_chat_utils.private_chat_image_handler import (
    ImageHandler as PrivateChatImageHandler,
)
from .private_chat_utils.private_chat_image_description_cache import (
    ImageDescriptionCache,
)

# 私信专用消息处理器（用于添加时间戳和发送者信息）
from .private_chat_utils.private_chat_message_processor import (
    MessageProcessor as PrivateChatMessageProcessor,
)


class PrivateChatMain:
    """
    私信功能主消息类

    负责协调私信消息的接收、聚合、处理和回复
    """

    def __init__(
        self,
        context: Context,
        config: dict,
        plugin_instance=None,
        data_dir: str = None,
        private_chat_debug_mode: bool = False,
        # 省钱缓存配置（由 main.py 协调群聊/私信后传入，避免二次读取导致冲突）
        enable_image_description_cache: bool = False,
        image_description_cache: Optional[ImageDescriptionCache] = None,
    ):
        """
        初始化私信处理器

        Args:
            context: AstrBot Context对象
            config: 插件配置（包含私信相关配置）
            plugin_instance: 主插件实例（用于共享某些状态）
            data_dir: 插件数据目录路径（从主插件传入）
            private_chat_debug_mode: 私信调试日志开关
            enable_image_description_cache: 私信省钱缓存开关（由main.py协调后传入）
            image_description_cache: 共享图片描述缓存实例（由main.py协调后传入，与群聊共用）
        """
        self.context = context
        self.config = config
        self.plugin_instance = plugin_instance
        self.data_dir = data_dir
        self.private_chat_debug_mode = private_chat_debug_mode

        # === 私信部分相关配置集中读取处 ===
        self.enable_user_filter = config.get(
            "private_enable_user_filter", False
        )  # 用户名单过滤开关
        self.user_filter_mode = config.get(
            "private_user_filter_mode", "blacklist"
        )  # 名单模式: blacklist / whitelist
        self.user_filter_list = config.get(
            "private_user_filter_list", []
        )  # 过滤用户ID列表

        # === 消息格式配置（私信专用，与群聊配置独立） ===
        self.private_include_timestamp = config.get(
            "private_include_timestamp", True
        )  # 是否在消息前插入时间戳
        self.private_include_sender_info = config.get(
            "private_include_sender_info", True
        )  # 是否在消息前插入发送者ID和名称

        # === 消息聚合相关配置 ===
        self.enable_message_aggregator = config.get(
            "private_enable_message_aggregator", False
        )  # 消息聚合总开关
        self.aggregator_wait_time = config.get(
            "private_aggregator_wait_time", 5.0
        )  # 聚合等待时间（秒）

        # 聚合最大条数：-1=不限制，但硬上限50条
        _raw_max = config.get("private_aggregator_max_messages", 20)
        try:
            _raw_max = int(_raw_max)
        except (ValueError, TypeError):
            _raw_max = 20
        if _raw_max == -1:
            self.aggregator_max_messages = 50  # 硬上限保护
        elif _raw_max <= 0:
            self.aggregator_max_messages = 50
        else:
            self.aggregator_max_messages = min(_raw_max, 50)

        # 聚合分隔符：处理转义字符
        _raw_separator = config.get("private_aggregator_separator", "\\n\\n")
        self.aggregator_separator = str(_raw_separator).replace("\\n", "\n")

        # === 消息聚合用户过滤配置 ===
        self.enable_aggregator_filter = config.get(
            "private_enable_aggregator_filter", False
        )  # 聚合用户过滤开关
        self.aggregator_filter_mode = config.get(
            "private_aggregator_filter_mode", "blacklist"
        )  # 聚合名单模式: blacklist / whitelist
        self.aggregator_filter_list = config.get(
            "private_aggregator_filter_list", []
        )  # 聚合过滤用户ID列表

        # === 私信图片处理配置（私信专用，从 config 读取） ===
        self.enable_image_processing = config.get(
            "private_enable_image_processing", False
        )  # 图片处理（图片转文字）开关
        self.image_to_text_provider_id = config.get(
            "private_image_to_text_provider_id", ""
        )  # 图片转文字AI提供商ID
        self.image_to_text_prompt = config.get(
            "private_image_to_text_prompt", "请详细描述这张图片的内容"
        )  # 图片转文字提示词
        self.image_to_text_timeout = config.get(
            "private_image_to_text_timeout", 60
        )  # 图片转文字超时时间（秒）
        self.max_images_per_message = max(
            1, min(config.get("private_max_images_per_message", 10), 50)
        )  # 单条消息最大处理图片数（硬限制1-50）

        # === 省钱缓存配置（由 main.py 协调群聊/私信后通过参数传入） ===
        self.enable_image_description_cache = enable_image_description_cache

        # 共享图片描述缓存实例（仅在私信缓存开关开启时使用）
        self.image_description_cache = image_description_cache

        # === 消息聚合运行时状态 ===
        # 每个用户独立的待聚合消息状态
        # Key: sender_id (str), Value: {"messages": List[str], "images": List[Image], "timer_task": asyncio.Task, "event": AstrMessageEvent}
        self._aggregation_pending: Dict[str, Dict[str, Any]] = {}

        # 记录图片处理配置状态
        if self.private_chat_debug_mode:
            logger.info(
                f"[私信图片处理] 配置状态: "
                f"启用图片转文字={self.enable_image_processing}, "
                f"提供商ID={'(已配置)' if self.image_to_text_provider_id else '(空/多模态)'}, "
                f"省钱缓存={self.enable_image_description_cache}, "
                f"最大图片数={self.max_images_per_message}"
            )

    async def handle_message(self, event: AstrMessageEvent):
        """
        处理私信消息的主入口

        由主插件的 on_private_message 调用，接收完整的消息事件对象

        Args:
            event: AstrBot消息事件对象，包含完整的私信消息信息
        """
        if self.private_chat_debug_mode:
            logger.info(f"[私信处理] 收到私信消息，开始处理")

        # 用户名单过滤检查
        if self._should_filter_user(event):
            return

        # 消息聚合路由
        if self.enable_message_aggregator and self._should_aggregate_for_user(event):
            # 该用户启用了消息聚合，进入聚合等待流程
            await self._aggregate_message(event)
            return
        else:
            # 不聚合，直接处理
            await self._process_message(event)

    def _should_filter_user(self, event: AstrMessageEvent) -> bool:
        """
        检测发送者是否应被用户名单过滤

        支持黑名单和白名单两种模式：
        - blacklist: 名单内的用户被忽略
        - whitelist: 仅处理名单内的用户

        Args:
            event: 消息事件对象

        Returns:
            True=应过滤（跳过处理），False=正常处理
        """
        try:
            if not self.enable_user_filter:
                return False

            filter_list = self.user_filter_list
            if not filter_list:
                # 名单为空，不过滤任何用户
                return False

            # 提取发送者的用户ID
            sender_id = event.get_sender_id()
            sender_id_str = str(sender_id)

            # 检查用户是否在名单中（兼容字符串和数字类型的ID）
            in_list = (
                sender_id in filter_list
                or sender_id_str in filter_list
                or (
                    int(sender_id_str) in filter_list
                    if sender_id_str.isdigit()
                    else False
                )
            )

            if self.user_filter_mode == "whitelist":
                # 白名单模式：不在名单中的用户被过滤
                if not in_list:
                    if self.private_chat_debug_mode:
                        logger.info(
                            f"🚫 [私信用户过滤] 用户 {sender_id} 不在白名单中，跳过处理"
                        )
                    return True
            else:
                # 黑名单模式：在名单中的用户被过滤
                if in_list:
                    if self.private_chat_debug_mode:
                        logger.info(
                            f"🚫 [私信用户过滤] 用户 {sender_id} 在黑名单中，跳过处理"
                        )
                    return True

            return False

        except Exception as e:
            logger.error(f"[私信用户过滤] 发生错误: {e}", exc_info=True)
            return False

    def _should_aggregate_for_user(self, event: AstrMessageEvent) -> bool:
        """
        检测该用户的消息是否应该进行聚合

        根据聚合用户过滤配置判断：
        - 过滤关闭或名单为空时，对所有用户启用聚合
        - 白名单模式：仅名单内的用户启用聚合
        - 黑名单模式：名单内的用户不启用聚合

        Args:
            event: 消息事件对象

        Returns:
            True=应启用聚合，False=不聚合（直接处理）
        """
        try:
            if not self.enable_aggregator_filter:
                # 未启用聚合过滤，对所有用户启用聚合
                return True

            filter_list = self.aggregator_filter_list
            if not filter_list:
                # 名单为空，不过滤，对所有用户启用聚合
                return True

            sender_id = event.get_sender_id()
            sender_id_str = str(sender_id)

            # 检查用户是否在名单中（兼容字符串和数字类型的ID）
            in_list = (
                sender_id in filter_list
                or sender_id_str in filter_list
                or (
                    int(sender_id_str) in filter_list
                    if sender_id_str.isdigit()
                    else False
                )
            )

            if self.aggregator_filter_mode == "whitelist":
                # 白名单模式：仅名单内的用户启用聚合
                if not in_list and self.private_chat_debug_mode:
                    logger.info(
                        f"[私信消息聚合过滤] 用户 {sender_id} 不在白名单中，跳过聚合"
                    )
                return in_list
            else:
                # 黑名单模式：名单内的用户不启用聚合
                if in_list and self.private_chat_debug_mode:
                    logger.info(
                        f"[私信消息聚合过滤] 用户 {sender_id} 在黑名单中，跳过聚合"
                    )
                return not in_list

        except Exception as e:
            logger.error(f"[私信消息聚合过滤] 发生错误: {e}", exc_info=True)
            return True

    async def _aggregate_message(self, event: AstrMessageEvent):
        """
        将消息加入聚合队列

        如果该用户已有等待中的聚合定时器，取消旧定时器并追加消息，然后重启定时器。
        如果是该用户的第一条消息，创建新的聚合条目并启动定时器。
        达到最大聚合条数时立即提交处理。

        聚合期间同时保存每条消息的 Image 组件（含 URL），确保早期消息的图片
        不会因 event 覆盖而丢失，后续图片处理步骤可以正常获取所有图片的 URL。

        Args:
            event: 消息事件对象
        """
        sender_id = str(event.get_sender_id())
        message_text = event.get_message_str()

        # 提取当前消息中的 Image 组件（保留完整对象及 URL，用于后续图片处理）
        current_images = []
        if hasattr(event, "message_obj") and hasattr(event.message_obj, "message"):
            for comp in event.message_obj.message:
                if isinstance(comp, Image):
                    current_images.append(comp)

        if sender_id in self._aggregation_pending:
            # 该用户已有待聚合消息，取消旧定时器并追加
            pending = self._aggregation_pending[sender_id]

            # 取消已有的定时器任务
            if pending["timer_task"] and not pending["timer_task"].done():
                pending["timer_task"].cancel()
                try:
                    await pending["timer_task"]
                except asyncio.CancelledError:
                    pass

            pending["messages"].append(message_text)
            pending["images"].extend(current_images)
            pending["event"] = event  # 始终使用最新的事件对象

            if self.private_chat_debug_mode:
                count = len(pending["messages"])
                logger.info(
                    f"[私信消息聚合] 用户 {sender_id} 追加消息，当前累积 {count} 条"
                )

            # 检查是否达到最大聚合条数
            if len(pending["messages"]) >= self.aggregator_max_messages:
                if self.private_chat_debug_mode:
                    logger.info(
                        f"[私信消息聚合] 用户 {sender_id} 达到最大聚合条数 "
                        f"{self.aggregator_max_messages}，立即处理"
                    )
                await self._flush_aggregated(sender_id)
                return

        else:
            # 该用户的第一条消息，创建新的聚合条目
            self._aggregation_pending[sender_id] = {
                "messages": [message_text],
                "images": list(current_images),
                "timer_task": None,
                "event": event,
            }

            if self.private_chat_debug_mode:
                logger.info(
                    f"[私信消息聚合] 用户 {sender_id} 开始聚合，"
                    f"等待 {self.aggregator_wait_time} 秒"
                )

        # 启动（或重启）定时器
        self._aggregation_pending[sender_id]["timer_task"] = asyncio.create_task(
            self._aggregation_timer(sender_id)
        )

    async def _aggregation_timer(self, sender_id: str):
        """
        聚合等待定时器

        等待配置的时间后，如果没有被取消（即没有新消息到来），
        则将该用户的聚合消息提交处理。

        Args:
            sender_id: 用户ID
        """
        try:
            await asyncio.sleep(self.aggregator_wait_time)
            # 定时器到期且未被取消，提交聚合消息
            await self._flush_aggregated(sender_id)
        except asyncio.CancelledError:
            # 定时器被取消（有新消息到来），这是正常行为
            pass

    async def _flush_aggregated(self, sender_id: str):
        """
        提交聚合消息进行处理

        将该用户所有累积的消息以两个换行符合并为一条消息，
        然后传递给下游处理方法。

        Args:
            sender_id: 用户ID
        """
        if sender_id not in self._aggregation_pending:
            return

        pending = self._aggregation_pending.pop(sender_id)
        messages = pending["messages"]
        event = pending["event"]
        all_images = pending.get("images", [])

        # 用配置的分隔符合并所有消息
        combined_text = self.aggregator_separator.join(messages)

        # 分离早期消息的图片组件：
        # 最后一条事件的 Image 组件仍在 event.message_obj.message 中，
        # 会由 _process_message 的图片处理步骤从 event 中正常读取。
        # 只有早期消息的 Image 组件（其 event 已被覆盖）需要额外传递。
        current_event_image_ids = set()
        if hasattr(event, "message_obj") and hasattr(event.message_obj, "message"):
            current_event_image_ids = {
                id(comp)
                for comp in event.message_obj.message
                if isinstance(comp, Image)
            }
        earlier_images = [
            img for img in all_images if id(img) not in current_event_image_ids
        ]

        if self.private_chat_debug_mode:
            logger.info(
                f"[私信消息聚合] 用户 {sender_id} 聚合完成，"
                f"共 {len(messages)} 条消息，合并后长度 {len(combined_text)}，"
                f"早期图片 {len(earlier_images)} 张"
            )

        # 提交给下游处理（传递早期消息的图片组件，确保不丢失）
        await self._process_message(
            event, aggregated_text=combined_text, earlier_images=earlier_images
        )

    async def _process_message(
        self,
        event: AstrMessageEvent,
        aggregated_text: Optional[str] = None,
        earlier_images: Optional[List] = None,
    ):
        """
        私信消息的下游处理入口

        当消息通过所有过滤和聚合流程后，在此进行实际的消息处理。
        包含完整的图片处理流程（多模态直传 / 图片转文字 / 省钱缓存）。

        处理流程：
        1. 注入时间戳和发送者信息元数据
        2. 图片处理（当前事件的图片）
        2.5. 处理聚合期间早期消息的图片（如有）
        3. 将图片处理结果合并回消息文本
        4. 将最终内容传递给后续处理

        Args:
            event: 消息事件对象（聚合场景下为最后一条消息的事件）
            aggregated_text: 聚合后的消息文本，None 表示未经过聚合
            earlier_images: 聚合期间早期消息的 Image 组件列表（其 event 已被覆盖，
                           需额外传递以保留图片 URL），None 表示无早期图片
        """
        sender_id = event.get_sender_id()
        is_aggregated = aggregated_text is not None

        # === 第一步：添加时间戳和发送者信息 ===
        # 在图片处理之前注入元数据。
        # 图片处理器读取的是 event.message_obj.message（消息链中的 Image 组件），
        # 不受此处注入的文字内容影响，两步骤完全独立、互不干扰。
        # 两个开关各自独立：哪个开启就注入哪个。
        # 聚合和非聚合场景处理方式完全相同：到达此处时都是一条消息文本。
        raw_event_text = (
            event.get_message_str()
        )  # 当前事件的原始文本（用于步骤三尾部替换）
        base_text = aggregated_text if is_aggregated else raw_event_text

        if self.private_include_timestamp or self.private_include_sender_info:
            base_text = PrivateChatMessageProcessor.add_metadata_to_message(
                event,
                base_text or "",
                self.private_include_timestamp,
                self.private_include_sender_info,
            )
            if self.private_chat_debug_mode:
                logger.info(
                    f"[私信处理] 用户 {sender_id} 已注入元数据（时间戳={self.private_include_timestamp}，发送者信息={self.private_include_sender_info}）"
                )

        # === 第二步：图片处理（当前事件） ===
        # 从当前事件的消息链中提取和处理图片（多模态直传 / 图片转文字 / 省钱缓存）。
        # 聚合场景下此步骤仅处理最后一条消息的图片，早期消息的图片在步骤 2.5 中处理。
        image_cache_to_use = (
            self.image_description_cache
            if self.enable_image_description_cache
            else None
        )

        (
            should_continue,
            processed_text,
            image_urls,
            image_retained,
        ) = await PrivateChatImageHandler.process_message_images(
            event,
            self.context,
            self.enable_image_processing,
            self.image_to_text_provider_id,
            self.image_to_text_prompt,
            self.image_to_text_timeout,
            image_cache_to_use,
            self.max_images_per_message,
        )

        # 图片处理器返回 False 表示应丢弃此消息
        if not should_continue:
            if self.private_chat_debug_mode:
                logger.info(f"[私信处理] 用户 {sender_id} 消息在图片处理后被丢弃")
            return

        # === 第二步（补充）：处理聚合期间早期消息的图片 ===
        # 聚合时 event 会被最新消息覆盖，早期消息的 Image 组件（含 URL）
        # 已在聚合期间单独保存并通过 earlier_images 传入。
        # 此处根据配置对它们进行与当前事件图片相同的处理：
        # - 多模态模式：提取 URL 一并传递给 AI
        # - 图片转文字模式：调用 AI 将图片转为文字描述
        if earlier_images:
            # 限制总图片数不超过 max_images_per_message
            current_image_count = 0
            if hasattr(event, "message_obj") and hasattr(event.message_obj, "message"):
                current_image_count = sum(
                    1 for comp in event.message_obj.message if isinstance(comp, Image)
                )
            remaining_slots = max(0, self.max_images_per_message - current_image_count)
            limited_earlier = earlier_images[:remaining_slots]

            if limited_earlier:
                if (
                    not self.enable_image_processing
                    or not self.image_to_text_provider_id
                ):
                    # 多模态模式：提取早期图片的 URL，与当前事件的 URL 合并
                    extra_urls = await PrivateChatImageHandler._extract_image_urls(
                        limited_earlier
                    )
                    image_urls = extra_urls + image_urls  # 早期图片排前面（时间更早）
                    if extra_urls:
                        image_retained = True
                else:
                    # 图片转文字模式：将早期图片送入 AI 转换为文字描述
                    # 传入纯 Image 组件列表作为 message_chain，
                    # _convert_images_to_text 会逐个处理并生成 [图片内容: ...] 描述
                    earlier_result = (
                        await PrivateChatImageHandler._convert_images_to_text(
                            limited_earlier,  # message_chain（仅含 Image 组件）
                            self.context,
                            self.image_to_text_provider_id,
                            self.image_to_text_prompt,
                            limited_earlier,  # image_components = 同一列表
                            self.image_to_text_timeout,
                            image_cache_to_use,
                            len(limited_earlier),
                        )
                    )
                    if earlier_result:
                        # 早期图片的描述追加到当前处理结果前面（时间更早）
                        processed_text = earlier_result + "\n" + (processed_text or "")
                        image_retained = True

                if self.private_chat_debug_mode:
                    logger.info(
                        f"[私信处理] 用户 {sender_id} 处理了 {len(limited_earlier)} "
                        f"张早期聚合图片"
                    )

        # === 第三步：将图片处理结果合并回消息文本 ===
        # base_text 已含元数据前缀，尾部仍为原始消息文本（raw_event_text）。
        # 聚合与非聚合逻辑完全相同：用 processed_text 替换 base_text 尾部的原始文本，
        # 将图片描述无缝嵌入到正确位置（元数据前缀之后）。
        if raw_event_text and base_text.endswith(raw_event_text):
            final_text = base_text[: -len(raw_event_text)] + processed_text
        else:
            # raw_event_text 为空（纯图片消息）或无法精确匹配时，直接追加
            final_text = base_text + (processed_text or "")

        if self.private_chat_debug_mode:
            logger.info(
                f"[私信处理] 用户 {sender_id} 消息进入处理流程，"
                f"是否聚合: {is_aggregated}，"
                f"文本长度: {len(final_text) if final_text else 0}，"
                f"图片URL数: {len(image_urls)}，"
                f"图片保留: {image_retained}"
            )

        # === 第四步：后续处理（TODO: 后续私信处理逻辑在此扩展） ===
        # final_text: 最终处理后的消息文本（已包含元数据前缀 + 图片描述或纯文本）
        # image_urls: 多模态模式下的图片URL列表（供AI直接处理）
        # image_retained: 图片信息是否仍保留在消息中
