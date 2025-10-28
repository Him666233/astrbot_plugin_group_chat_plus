"""
群聊增强插件 - Group Chat Plus
基于AI读空气的群聊增强插件，让bot更懂氛围

核心功能：
1. AI读空气判断 - 智能决定是否回复消息
2. 动态概率调整 - 回复后提高触发概率，促进连续对话
3. 图片识别支持 - 可将图片转为文字描述
4. 上下文记忆 - 自动管理聊天历史
5. 记忆植入 - 集成长期记忆系统
6. 工具提醒 - 提示AI可用的功能
7. @消息快速响应 - 跳过概率判断直接回复
8. 智能缓存 - 避免对话上下文丢失
9. 官方历史同步 - 自动保存到系统对话记录

缓存工作原理：
- 通过初筛的消息先放入缓存
- AI不回复时保存到自定义存储，保留上下文
- AI回复时一次性转存到官方系统并清空缓存
- 自动清理超过30分钟的旧消息，最多保留10条

使用提示：
- 只在群聊生效，私聊消息不处理
- enabled_groups留空=全部群启用，填群号=仅指定群启用
- @消息会跳过所有判断直接回复

作者: Him666233
版本: v1.0.0
"""

import random
import time
from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.core.star.star_tools import StarTools

# 导入所有工具模块
from .utils import (
    ProbabilityManager,
    MessageProcessor,
    ImageHandler,
    ContextManager,
    DecisionAI,
    ReplyHandler,
    MemoryInjector,
    ToolsReminder,
    KeywordChecker,
    MessageCleaner,
)


@register(
    "chat_plus",
    "Him666233",
    "一个以AI读空气为主的群聊聊天效果增强插件",
    "v1.0.0",
    "https://github.com/Him666233/astrbot_plugin_group_chat_plus",
)
class ChatPlus(Star):
    """
    群聊增强插件主类

    采用事件监听而非消息拦截，确保与其他插件兼容
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        """
        初始化插件

        Args:
            context: AstrBot的Context对象，包含各种API
            config: 插件配置
        """
        super().__init__(context)
        self.context = context
        self.config = config

        # 获取调试日志开关
        self.debug_mode = config.get("enable_debug_log", False)

        # 初始化上下文管理器（使用插件专属数据目录）
        # 注意：StarTools.get_data_dir() 会自动检测插件名称
        data_dir = StarTools.get_data_dir()
        ContextManager.init(str(data_dir))

        # 初始化消息缓存（用于保存"通过筛选但未回复"的消息）
        # 格式: {chat_id: [{"role": "user", "content": "消息内容", "timestamp": 时间戳}]}
        self.pending_messages_cache = {}

        # 标记本插件正在处理的会话（用于after_message_sent筛选）
        # 格式: {chat_id: True}
        self.processing_sessions = {}

        logger.info("=" * 50)
        logger.info("群聊增强插件已加载 - v1.0.0")
        logger.info(f"初始读空气概率: {config.get('initial_probability', 0.1)}")
        logger.info(f"回复后概率: {config.get('after_reply_probability', 0.8)}")
        logger.info(f"概率提升持续时间: {config.get('probability_duration', 300)}秒")
        logger.info(f"启用的群组: {config.get('enabled_groups', [])} (留空=全部)")
        logger.info(f"详细日志模式: {'开启' if self.debug_mode else '关闭'}")
        logger.info("=" * 50)

        if self.debug_mode:
            logger.debug("【调试模式】配置详情:")
            logger.debug(
                f"  - 读空气AI提供商: {config.get('decision_ai_provider_id', '默认')}"
            )
            logger.debug(f"  - 包含时间戳: {config.get('include_timestamp', True)}")
            logger.debug(
                f"  - 包含发送者信息: {config.get('include_sender_info', True)}"
            )
            logger.debug(
                f"  - 最大上下文消息数: {config.get('max_context_messages', 20)}"
            )
            logger.debug(
                f"  - 启用图片处理: {config.get('enable_image_processing', False)}"
            )
            logger.debug(
                f"  - 启用记忆植入: {config.get('enable_memory_injection', False)}"
            )
            logger.debug(
                f"  - 启用工具提醒: {config.get('enable_tools_reminder', False)}"
            )

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """
        群消息事件监听

        采用监听模式，不影响其他插件和官方功能

        Args:
            event: 消息事件对象
        """
        try:
            # 处理群消息
            async for result in self._process_message(event):
                yield result
        except Exception as e:
            logger.error(f"处理群消息时发生错误: {e}", exc_info=True)

    async def _perform_initial_checks(self, event: AstrMessageEvent) -> tuple:
        """
        执行初始检查

        Returns:
            (should_continue, platform_name, is_private, chat_id)
            - should_continue: 是否继续处理
            - 其他: 基本信息
        """
        if self.debug_mode:
            logger.debug("=" * 60)
            logger.debug("【步骤1】开始基础检查")

        # 检查是否启用
        if not self._is_enabled(event):
            if self.debug_mode:
                logger.debug("【步骤1】群组未启用插件,跳过处理")
            return False, None, None, None

        # 检查是否是机器人自己的消息
        if MessageProcessor.is_message_from_bot(event):
            logger.debug("忽略机器人自己的消息")
            return False, None, None, None

        # 获取基本信息
        platform_name = event.get_platform_name()
        is_private = event.is_private_chat()
        chat_id = event.get_group_id() if not is_private else event.get_sender_id()

        if self.debug_mode:
            logger.debug(f"【步骤1】基础信息:")
            logger.debug(f"  平台: {platform_name}")
            logger.debug(f"  类型: {'私聊' if is_private else '群聊'}")
            logger.debug(f"  会话ID: {chat_id}")
            logger.debug(
                f"  发送者: {event.get_sender_name()}({event.get_sender_id()})"
            )

        # 黑名单关键词检查
        if self.debug_mode:
            logger.debug("【步骤2】检查黑名单关键词")

        blacklist_keywords = self.config.get("blacklist_keywords", [])
        if KeywordChecker.check_blacklist_keywords(event, blacklist_keywords):
            logger.info("消息包含黑名单关键词，忽略处理")
            if self.debug_mode:
                logger.debug("【步骤2】黑名单关键词匹配，丢弃消息")
                logger.debug("=" * 60)
            return False, None, None, None

        return True, platform_name, is_private, chat_id

    async def _check_message_triggers(self, event: AstrMessageEvent) -> tuple:
        """
        检查消息触发器（@消息和触发关键词）

        Returns:
            (is_at_message, has_trigger_keyword)
        """
        # 判断是否是@消息
        is_at_message = MessageProcessor.is_at_message(event)

        # 强制日志：@消息判断结果（用于排查旧版QQ兼容问题）
        logger.info(
            f"⭐ [@消息判断] 结果: {'✅是@消息' if is_at_message else '❌非@消息'}"
        )

        if self.debug_mode:
            logger.debug(
                f"【步骤3】@消息检测: {'是@消息' if is_at_message else '非@消息'}"
            )

        # 触发关键词检查
        if self.debug_mode:
            logger.debug("【步骤4】检查触发关键词")

        trigger_keywords = self.config.get("trigger_keywords", [])
        has_trigger_keyword = KeywordChecker.check_trigger_keywords(
            event, trigger_keywords
        )

        # 强制日志：触发关键词判断结果
        logger.info(
            f"⭐ [触发关键词判断] 结果: {'✅包含关键词' if has_trigger_keyword else '❌无关键词'}"
        )

        if has_trigger_keyword:
            logger.info("消息包含触发关键词，跳过读空气判断")
            if self.debug_mode:
                logger.debug("【步骤4】检测到触发关键词，跳过读空气判断")

        return is_at_message, has_trigger_keyword

    async def _check_probability_before_processing(
        self,
        platform_name: str,
        is_private: bool,
        chat_id: str,
        is_at_message: bool,
        has_trigger_keyword: bool,
    ) -> bool:
        """
        执行概率判断（在图片处理之前）

        Returns:
            True=继续处理, False=丢弃消息
        """
        # @消息或触发关键词消息跳过概率判断
        if not is_at_message and not has_trigger_keyword:
            # 概率判断
            if self.debug_mode:
                logger.debug("【步骤5】开始读空气概率判断")

            should_process = await self._check_probability(
                platform_name, is_private, chat_id
            )
            if not should_process:
                logger.debug("读空气概率判断: 不处理此消息")
                if self.debug_mode:
                    logger.debug("【步骤5】概率判断失败,丢弃消息")
                    logger.debug("=" * 60)
                return False

            logger.debug("读空气概率判断: 决定处理此消息")
            if self.debug_mode:
                logger.debug("【步骤5】概率判断通过,继续处理")
        else:
            # @消息或触发关键词，跳过概率判断
            if is_at_message:
                logger.info("检测到@消息,跳过概率判断")
                if self.debug_mode:
                    logger.debug("【步骤5】@消息,跳过概率判断,必定处理")

            if has_trigger_keyword:
                logger.info("检测到触发关键词,跳过概率判断")
                if self.debug_mode:
                    logger.debug("【步骤5】触发关键词消息,跳过概率判断,必定处理")

        return True

    async def _check_ai_decision(
        self,
        event: AstrMessageEvent,
        formatted_context: str,
        is_at_message: bool,
        has_trigger_keyword: bool,
    ) -> bool:
        """
        执行AI决策判断（在处理完消息内容后）

        Returns:
            True=应该回复, False=不回复
        """
        # @消息或触发关键词消息跳过AI决策判断
        if not is_at_message and not has_trigger_keyword:
            # 决策AI判断
            if self.debug_mode:
                logger.debug("【步骤9】调用决策AI判断是否回复")

            should_reply = await DecisionAI.should_reply(
                self.context,
                event,
                formatted_context,
                self.config.get("decision_ai_provider_id", ""),
                self.config.get("decision_ai_extra_prompt", ""),
                self.config.get("decision_ai_timeout", 30),
            )

            if not should_reply:
                logger.info("决策AI判断: 不应该回复此消息")
                return False

            logger.info("决策AI判断: 应该回复此消息")
            return True
        else:
            # @消息，检查是否已被其他插件处理
            if is_at_message:
                if ReplyHandler.check_if_already_replied(event):
                    logger.info("@消息已被其他插件处理,跳过回复")
                    if self.debug_mode:
                        logger.debug("【步骤9】@消息已被处理,退出")
                        logger.debug("=" * 60)
                    return False

            # @消息或触发关键词，必定回复
            if self.debug_mode:
                logger.debug("【步骤9】@消息或触发关键词,跳过AI决策,必定回复")

            return True

    async def _process_message_content(
        self, event: AstrMessageEvent, chat_id: str, is_at_message: bool
    ) -> tuple:
        """
        处理消息内容（元数据、图片、上下文）

        Returns:
            (should_continue, original_message_text, message_text, formatted_context)
        """
        # 添加时间戳和发送者信息
        if self.debug_mode:
            logger.debug("【步骤6】提取纯净原始消息并添加元数据")

        # 使用MessageCleaner提取纯净的原始消息（不含系统提示词）
        original_message_text = MessageCleaner.extract_raw_message_from_event(event)
        if self.debug_mode:
            logger.debug(f"  纯净原始消息: {original_message_text[:100]}...")

        # 检查是否是空@消息
        is_empty_at = MessageCleaner.is_empty_at_message(
            original_message_text, is_at_message
        )
        if is_empty_at:
            logger.info("检测到纯@消息（无其他内容）")
            if self.debug_mode:
                logger.debug("  纯@消息将使用特殊处理")

        message_text = MessageProcessor.add_metadata_to_message(
            event,
            original_message_text,
            self.config.get("include_timestamp", True),
            self.config.get("include_sender_info", True),
        )

        if self.debug_mode:
            logger.debug(f"  添加元数据后消息: {message_text[:150]}...")

        # 处理图片（在缓存之前）
        # 这样如果图片被过滤，消息就不会被缓存
        if self.debug_mode:
            logger.debug("【步骤6.5】处理图片内容")

        should_continue, processed_message = await ImageHandler.process_message_images(
            event,
            self.context,
            self.config.get("enable_image_processing", False),
            self.config.get("image_to_text_scope", "all"),
            self.config.get("image_to_text_provider_id", ""),
            self.config.get("image_to_text_prompt", "请详细描述这张图片的内容"),
            is_at_message,
            self.config.get("image_to_text_timeout", 60),
        )

        if not should_continue:
            logger.info("图片处理后决定丢弃此消息（图片被过滤或处理失败）")
            if self.debug_mode:
                logger.debug("【步骤6.5】图片处理判定丢弃消息，不缓存")
                logger.debug("=" * 60)
            return False, None, None, None

        # 缓存当前用户消息（图片处理通过后再缓存）
        # 注意：缓存处理后的消息（不含元数据），在保存时再添加元数据
        # processed_message 已经是经过图片处理的最终结果（可能是过滤后、转文字后、或原始消息）
        if self.debug_mode:
            logger.debug("【步骤7】缓存处理后的用户消息（不含元数据，保存时再添加）")
            logger.debug(f"  原始消息（提取自event）: {original_message_text[:200]}...")
            logger.debug(f"  处理后消息（图片处理后）: {processed_message[:200]}...")

        # 缓存处理后的消息内容，不包含元数据
        # 保存发送者信息和时间戳，用于后续添加元数据
        cached_message = {
            "role": "user",
            "content": processed_message,  # 处理后的消息（可能已过滤图片、转文字、或保留原样）
            "timestamp": time.time(),
            # 保存发送者信息，用于转正时添加正确的元数据
            "sender_id": event.get_sender_id(),
            "sender_name": event.get_sender_name(),
            "message_timestamp": event.message_obj.timestamp
            if hasattr(event, "message_obj") and hasattr(event.message_obj, "timestamp")
            else None,
        }

        # 强制日志：缓存内容（不受debug_mode控制）
        logger.info(f"🔵 [缓存] 原始消息: {original_message_text[:100]}")
        logger.info(f"🔵 [缓存] 处理后消息: {processed_message[:100]}")
        logger.info(f"🔵 [缓存] 已缓存内容: {cached_message['content'][:100]}")

        if self.debug_mode:
            logger.debug(f"  已缓存内容: {cached_message['content'][:200]}...")
            if processed_message != original_message_text:
                logger.debug(f"  ⚠️ 消息内容有变化！原始≠处理后")
            else:
                logger.debug(f"  消息内容无变化（原始==处理后）")

        if chat_id not in self.pending_messages_cache:
            self.pending_messages_cache[chat_id] = []

        # 清理旧消息
        current_time = time.time()
        cache_ttl = 1800
        old_count = len(self.pending_messages_cache[chat_id])
        self.pending_messages_cache[chat_id] = [
            msg
            for msg in self.pending_messages_cache[chat_id]
            if current_time - msg.get("timestamp", 0) < cache_ttl
        ]

        if self.debug_mode and old_count > len(self.pending_messages_cache[chat_id]):
            removed = old_count - len(self.pending_messages_cache[chat_id])
            logger.debug(f"  已清理过期缓存: {removed} 条（超过30分钟）")

        # 添加到缓存
        self.pending_messages_cache[chat_id].append(cached_message)
        if len(self.pending_messages_cache[chat_id]) > 10:
            removed_msg = self.pending_messages_cache[chat_id].pop(0)
            if self.debug_mode:
                logger.debug(f"  缓存已满，移除最旧消息")

        if self.debug_mode:
            logger.debug(f"  缓存消息数: {len(self.pending_messages_cache[chat_id])}")

        # 使用处理后的消息继续后续流程（包含图片描述或原始消息）
        message_text = processed_message

        # 提取历史上下文
        max_context = self.config.get("max_context_messages", 20)
        if self.debug_mode:
            logger.debug("【步骤8】提取历史上下文")
            logger.debug(f"  最大上下文数: {max_context}")

        history_messages = ContextManager.get_history_messages(event, max_context)

        # 合并缓存消息
        cached_messages_to_merge = []
        if (
            chat_id in self.pending_messages_cache
            and len(self.pending_messages_cache[chat_id]) > 1
        ):
            cached_messages = self.pending_messages_cache[chat_id][:-1]
            if cached_messages and history_messages:
                history_contents = set()
                for msg in history_messages:
                    if isinstance(msg, dict) and "content" in msg:
                        history_contents.add(msg["content"])

                for cached_msg in cached_messages:
                    if isinstance(cached_msg, dict) and "content" in cached_msg:
                        if cached_msg["content"] not in history_contents:
                            cached_messages_to_merge.append(cached_msg)
            elif cached_messages:
                cached_messages_to_merge = cached_messages

        if cached_messages_to_merge:
            if history_messages is None:
                history_messages = []
            history_messages.extend(cached_messages_to_merge)
            if self.debug_mode:
                logger.debug(f"  合并缓存消息: {len(cached_messages_to_merge)} 条")

        # 应用上下文限制
        if history_messages and max_context > 0 and len(history_messages) > max_context:
            history_messages = history_messages[-max_context:]

        if self.debug_mode:
            logger.debug(
                f"  最终历史消息: {len(history_messages) if history_messages else 0} 条"
            )

        # 格式化上下文
        bot_id = event.get_self_id()
        formatted_context = await ContextManager.format_context_for_ai(
            history_messages, message_text, bot_id
        )

        if self.debug_mode:
            logger.debug(f"  格式化后长度: {len(formatted_context)} 字符")

        return True, original_message_text, message_text, formatted_context

    async def _generate_and_send_reply(
        self,
        event: AstrMessageEvent,
        formatted_context: str,
        message_text: str,
        platform_name: str,
        is_private: bool,
        chat_id: str,
    ):
        """
        生成并发送回复，保存历史

        Returns:
            生成器，用于yield回复
        """
        # 注入记忆
        final_message = formatted_context

        if self.config.get("enable_memory_injection", False):
            if self.debug_mode:
                logger.debug("【步骤11】注入记忆内容")

            if MemoryInjector.check_memory_plugin_available(self.context):
                memories = await MemoryInjector.get_memories(self.context, event)
                if memories:
                    final_message = MemoryInjector.inject_memories_to_message(
                        final_message, memories
                    )
                    if self.debug_mode:
                        logger.debug(
                            f"  已注入记忆,长度增加: {len(final_message) - len(formatted_context)} 字符"
                        )
            else:
                logger.warning("记忆插件未安装或不可用,跳过记忆注入")

        # 注入工具信息
        if self.config.get("enable_tools_reminder", False):
            if self.debug_mode:
                logger.debug("【步骤12】注入工具信息")

            old_len = len(final_message)
            final_message = ToolsReminder.inject_tools_to_message(
                final_message, self.context
            )
            if self.debug_mode:
                logger.debug(
                    f"  已注入工具信息,长度增加: {len(final_message) - old_len} 字符"
                )

        # 调用AI生成回复
        if self.debug_mode:
            logger.debug("【步骤13】调用AI生成回复")
            logger.debug(f"  最终消息长度: {len(final_message)} 字符")

        reply_result = await ReplyHandler.generate_reply(
            event,
            self.context,
            final_message,
            self.config.get("reply_ai_extra_prompt", ""),
        )

        if self.debug_mode:
            logger.debug("【步骤13】AI回复生成完成")

        # 保存用户消息（从缓存读取并添加元数据）
        if self.debug_mode:
            logger.debug("【步骤14】保存用户消息")

        try:
            # 从缓存获取处理后的消息
            message_to_save = ""
            if (
                chat_id in self.pending_messages_cache
                and len(self.pending_messages_cache[chat_id]) > 0
            ):
                last_cached = self.pending_messages_cache[chat_id][-1]
                if isinstance(last_cached, dict) and "content" in last_cached:
                    # 获取处理后的消息内容（不含元数据）
                    raw_content = last_cached["content"]

                    # 强制日志：从缓存读取的内容
                    logger.info(f"🟢 [步骤14-读缓存] 内容: {raw_content[:100]}")

                    if self.debug_mode:
                        logger.debug(f"  从缓存读取的内容: {raw_content[:200]}...")

                    # 使用缓存中的发送者信息添加元数据
                    message_to_save = MessageProcessor.add_metadata_from_cache(
                        raw_content,
                        last_cached.get("sender_id", event.get_sender_id()),
                        last_cached.get("sender_name", event.get_sender_name()),
                        last_cached.get("message_timestamp")
                        or last_cached.get("timestamp"),
                        self.config.get("include_timestamp", True),
                        self.config.get("include_sender_info", True),
                    )

                    # 强制日志：添加元数据后的内容
                    logger.info(f"🟢 [步骤14-加元数据后] 内容: {message_to_save[:150]}")

            # 如果从缓存获取失败，使用当前处理后的消息并添加元数据
            if not message_to_save:
                logger.debug(
                    "【步骤14】⚠️ 缓存中无消息，使用当前处理后的消息（这不应该发生！）"
                )
                message_to_save = MessageProcessor.add_metadata_to_message(
                    event,
                    message_text,  # message_text 就是 processed_message
                    self.config.get("include_timestamp", True),
                    self.config.get("include_sender_info", True),
                )

            if self.debug_mode:
                logger.debug(f"  准备保存的完整消息: {message_to_save[:300]}...")

            await ContextManager.save_user_message(event, message_to_save, self.context)
            if self.debug_mode:
                logger.debug(
                    f"  ✅ 用户消息已保存到自定义存储: {len(message_to_save)} 字符"
                )
        except Exception as e:
            logger.error(f"保存用户消息时发生错误: {e}")

        # 发送回复
        yield reply_result

        # 调整概率
        if self.debug_mode:
            logger.debug("【步骤15】调整读空气概率")

        await ProbabilityManager.boost_probability(
            platform_name,
            is_private,
            chat_id,
            self.config.get("after_reply_probability", 0.8),
            self.config.get("probability_duration", 300),
        )

        if self.debug_mode:
            logger.debug("【步骤15】概率调整完成")
            logger.debug("=" * 60)
            logger.debug("✓ 消息处理流程完成")

        logger.info("消息处理完成,已发送回复并保存历史")

    async def _process_message(self, event: AstrMessageEvent):
        """
        消息处理主流程

        协调各个子步骤完成消息处理

        流程优化说明：
        - 概率判断在最前面，快速过滤不需要处理的消息
        - 避免对不需要处理的消息进行图片识别等耗时操作

        Args:
            event: 消息事件对象
        """
        # 步骤1: 执行初始检查（最基本的过滤）
        (
            should_continue,
            platform_name,
            is_private,
            chat_id,
        ) = await self._perform_initial_checks(event)
        if not should_continue:
            return

        # 步骤2: 检查消息触发器（决定是否跳过概率判断）
        is_at_message, has_trigger_keyword = await self._check_message_triggers(event)

        # 关键逻辑：触发关键词等同于@消息
        # 这样在 mention_only 模式下，包含关键词的消息也能正常处理图片
        should_treat_as_at = is_at_message or has_trigger_keyword

        # 强制日志：显示等同@消息处理的判断结果
        logger.info(
            f"⭐ [等同@消息] 判断: {'✅是' if should_treat_as_at else '❌否'} (is_at={is_at_message}, has_keyword={has_trigger_keyword})"
        )

        if should_treat_as_at and has_trigger_keyword and not is_at_message:
            logger.info("    ↳ 因包含触发关键词，将按@消息处理（含图片处理）")

        # 步骤3: 概率判断（第一道核心过滤，避免后续耗时处理）
        should_process = await self._check_probability_before_processing(
            platform_name, is_private, chat_id, is_at_message, has_trigger_keyword
        )
        if not should_process:
            return

        # 步骤4-6: 处理消息内容（图片处理等耗时操作）
        # 使用 should_treat_as_at 而不是 is_at_message，这样触发关键词也能触发图片处理
        result = await self._process_message_content(event, chat_id, should_treat_as_at)
        if not result[0]:  # should_continue为False
            return

        _, original_message_text, message_text, formatted_context = result

        # 步骤7: AI决策判断（第二道核心过滤）
        should_reply = await self._check_ai_decision(
            event, formatted_context, is_at_message, has_trigger_keyword
        )

        if not should_reply:
            # 不回复，但保存缓存的用户消息
            if self.debug_mode:
                logger.debug("【步骤9】决策AI返回NO,但保存缓存的用户消息")

            try:
                if (
                    chat_id in self.pending_messages_cache
                    and self.pending_messages_cache[chat_id]
                ):
                    last_cached_msg = self.pending_messages_cache[chat_id][-1]

                    # 获取处理后的消息内容（不含元数据）
                    raw_content = last_cached_msg["content"]

                    # 使用缓存中的发送者信息添加元数据
                    message_with_metadata = MessageProcessor.add_metadata_from_cache(
                        raw_content,
                        last_cached_msg.get("sender_id", event.get_sender_id()),
                        last_cached_msg.get("sender_name", event.get_sender_name()),
                        last_cached_msg.get("message_timestamp")
                        or last_cached_msg.get("timestamp"),
                        self.config.get("include_timestamp", True),
                        self.config.get("include_sender_info", True),
                    )

                    await ContextManager.save_user_message(
                        event,
                        message_with_metadata,
                        None,
                    )
                    logger.debug(f"已保存未回复的用户消息到自定义历史（已添加元数据）")
            except Exception as e:
                logger.warning(f"保存未回复消息失败: {e}")

            if self.debug_mode:
                logger.debug("=" * 60)
            return

        # 标记本插件正在处理此会话
        self.processing_sessions[chat_id] = True
        if self.debug_mode:
            logger.debug(f"  已标记会话 {chat_id} 为本插件处理中")

        # 步骤10-15: 生成并发送回复
        async for result in self._generate_and_send_reply(
            event, formatted_context, message_text, platform_name, is_private, chat_id
        ):
            yield result

    @filter.after_message_sent()
    async def after_message_sent(self, event: AstrMessageEvent):
        """
        消息发送后的钩子，保存AI回复到官方对话系统

        在这里保存是因为此时event.result已经完整设置

        注意：所有消息发送都会触发，需要检查是否本插件的回复
        """
        try:
            # 获取会话信息（用于检查标记）
            platform_name = event.get_platform_name()
            is_private = event.is_private_chat()
            chat_id = event.get_group_id() if not is_private else event.get_sender_id()

            # 检查是否为本插件处理的会话
            if chat_id not in self.processing_sessions:
                return  # 不是本插件触发的回复，忽略

            # 清除标记（无论成功与否，都要清除）
            del self.processing_sessions[chat_id]

            # 只处理有result的消息
            if not event._result or not hasattr(event._result, "chain"):
                logger.debug(f"[消息发送后] 会话 {chat_id} 没有result或chain，跳过")
                return

            # 检查是否为LLM result
            if not event._result.is_llm_result():
                logger.debug(f"[消息发送后] 会话 {chat_id} 不是LLM结果，跳过")
                return

            # 提取回复文本
            bot_reply_text = "".join(
                [comp.text for comp in event._result.chain if hasattr(comp, "text")]
            )
            if not bot_reply_text:
                logger.debug(f"[消息发送后] 会话 {chat_id} 回复文本为空，跳过")
                return

            logger.info(
                f"[消息发送后] 会话 {chat_id} - 开始保存AI回复到官方系统，长度: {len(bot_reply_text)} 字符"
            )

            # 保存AI回复到自定义存储
            await ContextManager.save_bot_message(event, bot_reply_text, self.context)

            # 获取用户消息（从缓存的最后一条消息）
            # 注意：缓存中的消息不包含元数据，需要在这里添加
            message_to_save = ""

            if (
                chat_id in self.pending_messages_cache
                and len(self.pending_messages_cache[chat_id]) > 0
            ):
                last_cached = self.pending_messages_cache[chat_id][-1]
                if isinstance(last_cached, dict) and "content" in last_cached:
                    # 获取处理后的消息内容（不含元数据）
                    raw_content = last_cached["content"]

                    # 强制日志：从缓存读取的内容
                    logger.info(f"🟡 [官方保存-读缓存] 内容: {raw_content[:100]}")

                    if self.debug_mode:
                        logger.debug(
                            f"[消息发送后] 从缓存读取内容: {raw_content[:200]}..."
                        )

                    # 使用缓存中的发送者信息添加元数据
                    message_to_save = MessageProcessor.add_metadata_from_cache(
                        raw_content,
                        last_cached.get("sender_id", event.get_sender_id()),
                        last_cached.get("sender_name", event.get_sender_name()),
                        last_cached.get("message_timestamp")
                        or last_cached.get("timestamp"),
                        self.config.get("include_timestamp", True),
                        self.config.get("include_sender_info", True),
                    )

                    # 强制日志：添加元数据后的内容
                    logger.info(
                        f"🟡 [官方保存-加元数据后] 内容: {message_to_save[:150]}"
                    )

            # 如果缓存中没有，尝试从当前消息提取
            if not message_to_save:
                logger.warning(
                    "[消息发送后] ⚠️ 缓存中无消息，从event提取消息（不应该发生）"
                )
                # 使用当前处理后的消息
                from .utils import MessageCleaner

                processed = MessageCleaner.extract_raw_message_from_event(event)
                if processed:
                    message_to_save = MessageProcessor.add_metadata_to_message(
                        event,
                        processed,
                        self.config.get("include_timestamp", True),
                        self.config.get("include_sender_info", True),
                    )
                    logger.debug(
                        f"[消息发送后] 从event提取的消息: {message_to_save[:200]}..."
                    )

            if not message_to_save:
                logger.warning("[消息发送后] 无法获取用户消息，跳过官方保存")
                return

            if self.debug_mode:
                logger.debug(
                    f"[消息发送后] 准备保存到官方系统的消息: {message_to_save[:300]}..."
                )

            # 准备需要转正的缓存消息（包含那些之前未回复的消息）
            # 缓存中的消息不包含元数据，需要在转正时添加
            cached_messages_to_convert = []
            if (
                chat_id in self.pending_messages_cache
                and len(self.pending_messages_cache[chat_id]) > 1
            ):
                # 获取缓存中除了最后一条（当前消息）之外的消息
                raw_cached = self.pending_messages_cache[chat_id][:-1]
                logger.info(f"[消息发送后] 发现 {len(raw_cached)} 条待转正的缓存消息")

                # 处理每条缓存消息，使用缓存中的发送者信息添加元数据
                for cached_msg in raw_cached:
                    if isinstance(cached_msg, dict) and "content" in cached_msg:
                        # 获取处理后的消息内容（不含元数据）
                        raw_content = cached_msg["content"]

                        # 使用缓存中保存的发送者信息添加元数据
                        # 这样每条消息都会有正确的发送者信息
                        msg_content = MessageProcessor.add_metadata_from_cache(
                            raw_content,
                            cached_msg.get("sender_id", "unknown"),
                            cached_msg.get("sender_name", "未知用户"),
                            cached_msg.get("message_timestamp")
                            or cached_msg.get("timestamp"),
                            self.config.get("include_timestamp", True),
                            self.config.get("include_sender_info", True),
                        )

                        # 添加到转正列表
                        cached_messages_to_convert.append(
                            {
                                "role": cached_msg.get("role", "user"),
                                "content": msg_content,
                            }
                        )

                        if self.debug_mode:
                            sender_info = f"{cached_msg.get('sender_name')}(ID: {cached_msg.get('sender_id')})"
                            logger.debug(
                                f"[消息发送后] 转正消息（已添加元数据，发送者: {sender_info}）: {msg_content[:100]}..."
                            )
            else:
                logger.debug(f"[消息发送后] 没有待转正的缓存消息")

            # 保存到官方对话系统（包含缓存转正+去重）
            # 注意：去重逻辑在 save_to_official_conversation_with_cache 内部处理
            # 会自动过滤掉与现有官方历史重复的消息
            logger.info(
                f"[消息发送后] 准备保存: 缓存{len(cached_messages_to_convert)}条 + 当前对话(用户+AI)"
            )
            success = await ContextManager.save_to_official_conversation_with_cache(
                event,
                cached_messages_to_convert,  # 待转正的缓存消息（未去重，交给方法内部处理）
                message_to_save,  # 当前用户消息（已添加时间戳和发送者信息）
                bot_reply_text,  # AI回复
                self.context,
            )

            if success:
                logger.info(f"[消息发送后] ✅ 成功保存到官方对话系统")
                # 成功保存后，清空该会话的消息缓存
                if chat_id in self.pending_messages_cache:
                    cleared_count = len(self.pending_messages_cache[chat_id])
                    # 清空整个缓存列表
                    self.pending_messages_cache[chat_id] = []

                    if self.debug_mode:
                        logger.debug(
                            f"[消息发送后] 已清空消息缓存: {cleared_count} 条消息"
                        )
                    else:
                        logger.debug(f"[消息发送后] 已清空消息缓存: {cleared_count} 条")
            else:
                logger.warning(f"[消息发送后] ⚠️ 保存到官方对话系统失败")
                if self.debug_mode:
                    logger.debug(f"[消息发送后] 保存失败，缓存保留（待下次使用或清理）")

        except Exception as e:
            logger.error(f"[消息发送后] 保存AI回复时发生错误: {e}", exc_info=True)

    def _is_enabled(self, event: AstrMessageEvent) -> bool:
        """
        检查当前群组是否启用插件

        判断逻辑：
        - 私聊直接返回False（不处理）
        - enabled_groups为空则全部群聊启用
        - enabled_groups有值则仅列表内的群启用

        Args:
            event: 消息事件对象

        Returns:
            True=启用，False=未启用
        """
        # 只处理群消息,不处理私聊
        if event.is_private_chat():
            logger.debug("插件不处理私聊消息")
            return False

        # 获取启用的群组列表
        enabled_groups = self.config.get("enabled_groups", [])

        # 如果列表为空,则在所有群聊中启用
        if not enabled_groups or len(enabled_groups) == 0:
            logger.debug("未配置群组列表,在所有群聊中启用")
            return True

        # 如果列表不为空,检查当前群组是否在列表中
        group_id = event.get_group_id()
        if group_id in enabled_groups:
            logger.debug(f"群组 {group_id} 在启用列表中")
            return True
        else:
            logger.debug(f"群组 {group_id} 未在启用列表中")
            return False

    async def _check_probability(
        self, platform_name: str, is_private: bool, chat_id: str
    ) -> bool:
        """
        读空气概率检查，决定是否处理消息

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID

        Returns:
            True=处理，False=跳过
        """
        # 获取当前概率
        current_probability = await ProbabilityManager.get_current_probability(
            platform_name,
            is_private,
            chat_id,
            self.config.get("initial_probability", 0.1),
        )

        if self.debug_mode:
            logger.debug(f"  当前概率: {current_probability:.2f}")
            logger.debug(
                f"  初始概率: {self.config.get('initial_probability', 0.1):.2f}"
            )
            logger.debug(f"  会话ID: {chat_id}")

        # 随机判断
        roll = random.random()
        should_process = roll < current_probability

        logger.debug(
            f"读空气概率检查: 当前概率={current_probability:.2f}, 随机值={roll:.2f}, 结果={'触发' if should_process else '未触发'}"
        )

        if self.debug_mode:
            logger.debug(f"  随机值: {roll:.4f}")
            logger.debug(
                f"  判定: {'通过' if should_process else '失败'} ({roll:.4f} {'<' if should_process else '>='} {current_probability:.4f})"
            )

        return should_process
