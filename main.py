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
    KeywordChecker
)


@register("chat_plus","Him666233","一个以AI读空气为主的群聊聊天效果增强插件","v1.0.0","https://github.com/Him666233/astrbot_plugin_group_chat_plus")
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
        self.debug_mode = config.get('enable_debug_log', False)
        
        # 初始化上下文管理器
        ContextManager.init()
        
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
            logger.debug(f"  - 读空气AI提供商: {config.get('decision_ai_provider_id', '默认')}")
            logger.debug(f"  - 包含时间戳: {config.get('include_timestamp', True)}")
            logger.debug(f"  - 包含发送者信息: {config.get('include_sender_info', True)}")
            logger.debug(f"  - 最大上下文消息数: {config.get('max_context_messages', 20)}")
            logger.debug(f"  - 启用图片处理: {config.get('enable_image_processing', False)}")
            logger.debug(f"  - 启用记忆植入: {config.get('enable_memory_injection', False)}")
            logger.debug(f"  - 启用工具提醒: {config.get('enable_tools_reminder', False)}")
    
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
    
    async def _process_message(self, event: AstrMessageEvent):
        """
        消息处理主流程
        
        处理步骤：
        1. 基础检查 - 群组启用状态、是否bot自己的消息
        2. 黑名单过滤
        3. @消息识别
        4. 触发词检测
        5. 读空气概率判断（@消息和触发词跳过）
        6. 添加消息元数据（时间戳、发送者）
        7. 图片处理
        8. 上下文提取
        9. 决策AI判断（@消息和触发词跳过）
        10. 记忆注入
        11. 工具提醒
        12. AI生成回复
        13. 保存历史
        14. 概率调整
        
        Args:
            event: 消息事件对象
        """
        # === 第1步: 基础检查 ===
        if self.debug_mode:
            logger.debug("=" * 60)
            logger.debug("【步骤1】开始基础检查")
        
        # 检查是否启用
        if not self._is_enabled(event):
            if self.debug_mode:
                logger.debug("【步骤1】群组未启用插件,跳过处理")
            return
        
        # 检查是否是机器人自己的消息,避免自己回复自己
        if MessageProcessor.is_message_from_bot(event):
            logger.debug("忽略机器人自己的消息")
            return
        
        # 获取基本信息
        platform_name = event.get_platform_name()
        is_private = event.is_private_chat()
        chat_id = event.get_group_id() if not is_private else event.get_sender_id()
        
        if self.debug_mode:
            logger.debug(f"【步骤1】基础信息:")
            logger.debug(f"  平台: {platform_name}")
            logger.debug(f"  类型: {'私聊' if is_private else '群聊'}")
            logger.debug(f"  会话ID: {chat_id}")
            logger.debug(f"  发送者: {event.get_sender_name()}({event.get_sender_id()})")
        
        # === 第2步: 黑名单关键词检查 ===
        if self.debug_mode:
            logger.debug("【步骤2】检查黑名单关键词")
        
        blacklist_keywords = self.config.get('blacklist_keywords', [])
        if KeywordChecker.check_blacklist_keywords(event, blacklist_keywords):
            logger.info("消息包含黑名单关键词，忽略处理")
            if self.debug_mode:
                logger.debug("【步骤2】黑名单关键词匹配，丢弃消息")
                logger.debug("=" * 60)
            return
        
        # === 第3步: 判断是否是@消息 ===
        is_at_message = MessageProcessor.is_at_message(event)
        if self.debug_mode:
            logger.debug(f"【步骤3】@消息检测: {'是@消息' if is_at_message else '非@消息'}")
        
        # === 第4步: 触发关键词检查 ===
        if self.debug_mode:
            logger.debug("【步骤4】检查触发关键词")
        
        trigger_keywords = self.config.get('trigger_keywords', [])
        has_trigger_keyword = KeywordChecker.check_trigger_keywords(event, trigger_keywords)
        
        if has_trigger_keyword:
            logger.info("消息包含触发关键词，跳过读空气判断")
            if self.debug_mode:
                logger.debug("【步骤4】检测到触发关键词，跳过读空气判断")
        
        # === 第5步: 读空气概率判断 ===
        # @消息或触发关键词消息跳过概率判断,一定要处理
        if not is_at_message and not has_trigger_keyword:
            if self.debug_mode:
                logger.debug("【步骤5】开始读空气概率判断")
            should_process = self._check_probability(platform_name, is_private, chat_id)
            if not should_process:
                logger.debug("读空气概率判断: 不处理此消息")
                if self.debug_mode:
                    logger.debug("【步骤5】概率判断失败,丢弃消息")
                    logger.debug("=" * 60)
                return
            logger.debug("读空气概率判断: 决定处理此消息")
            if self.debug_mode:
                logger.debug("【步骤5】概率判断通过,继续处理")
        else:
            if is_at_message:
                logger.info("检测到@消息,跳过概率判断")
                if self.debug_mode:
                    logger.debug("【步骤5】@消息,跳过概率判断,必定处理")
            if has_trigger_keyword:
                logger.info("检测到触发关键词,跳过概率判断")
                if self.debug_mode:
                    logger.debug("【步骤5】触发关键词消息,跳过概率判断,必定处理")
        
        # === 第6步: 添加时间戳和发送者信息 ===
        if self.debug_mode:
            logger.debug("【步骤6】添加消息元数据")
        
        # 保存原始消息（不含元数据）用于后续保存
        original_message_text = event.get_message_outline()
        
        if self.debug_mode:
            logger.debug(f"  原始消息: {original_message_text[:100]}...")
        
        # 添加元数据用于AI处理
        message_text = MessageProcessor.add_metadata_to_message(
            event,
            original_message_text,
            self.config.get('include_timestamp', True),
            self.config.get('include_sender_info', True)
        )
        
        if self.debug_mode:
            logger.debug(f"  处理后消息: {message_text[:150]}...")
        
        # === 第6.5步: 缓存当前用户消息（用于处理"通过筛选但未回复"的情况）===
        if self.debug_mode:
            logger.debug("【步骤6.5】缓存用户消息")
        
        # 根据配置为消息添加元数据（时间戳+发送者信息）
        # 这样转正时就不需要额外处理了
        message_with_metadata = MessageProcessor.add_metadata_to_message(
            event,
            original_message_text,
            self.config.get('include_timestamp', True),
            self.config.get('include_sender_info', True)
        )
        
        # 将带元数据的消息添加到缓存（注意：这里只是准备，实际保存在步骤9或after_message_sent）
        cached_message = {
            "role": "user",
            "content": message_with_metadata,  # 保存带元数据的消息
            "timestamp": time.time(),
            "image_description": None  # 预留字段，第7步会填充图片描述
        }
        
        # 确保缓存列表存在
        if chat_id not in self.pending_messages_cache:
            self.pending_messages_cache[chat_id] = []
        
        # 清理30分钟前的旧消息（避免缓存积累太久）
        # 注意：过期的消息会被完全移除，包括其图片描述
        current_time = time.time()
        cache_ttl = 1800  # 30分钟 = 1800秒
        old_count = len(self.pending_messages_cache[chat_id])
        self.pending_messages_cache[chat_id] = [
            msg for msg in self.pending_messages_cache[chat_id]
            if current_time - msg.get("timestamp", 0) < cache_ttl
        ]
        
        if self.debug_mode and old_count > len(self.pending_messages_cache[chat_id]):
            removed = old_count - len(self.pending_messages_cache[chat_id])
            logger.debug(f"  已清理过期缓存: {removed} 条（超过30分钟）")
        
        # 添加到缓存（限制最多10条，避免内存积累）
        self.pending_messages_cache[chat_id].append(cached_message)
        if len(self.pending_messages_cache[chat_id]) > 10:
            # 移除最旧的消息（包括其图片描述）
            removed_msg = self.pending_messages_cache[chat_id].pop(0)
            if self.debug_mode:
                had_image = removed_msg.get('image_description') is not None if isinstance(removed_msg, dict) else False
                logger.debug(f"  缓存已满，移除最旧消息{'（含图片描述）' if had_image else ''}")
        
        if self.debug_mode:
            logger.debug(f"  缓存消息数: {len(self.pending_messages_cache[chat_id])}")
        
        # === 第7步: 处理图片 ===
        if self.debug_mode:
            logger.debug("【步骤7】处理图片内容")
            logger.debug(f"  图片处理: {'启用' if self.config.get('enable_image_processing', False) else '禁用'}")
            logger.debug(f"  图片转文字应用范围: {self.config.get('image_to_text_scope', 'all')}")
            logger.debug(f"  图片转文字超时: {self.config.get('image_to_text_timeout', 60)} 秒")
            logger.debug(f"  当前消息类型: {'@消息' if is_at_message else '普通消息'}")
        
        should_continue, processed_message = await ImageHandler.process_message_images(
            event,
            self.context,
            self.config.get('enable_image_processing', False),
            self.config.get('image_to_text_scope', 'all'),
            self.config.get('image_to_text_provider_id', ''),
            self.config.get('image_to_text_prompt', '请详细描述这张图片的内容'),
            is_at_message,
            self.config.get('image_to_text_timeout', 60)
        )
        
        if not should_continue:
            logger.info("图片处理后决定丢弃此消息")
            if self.debug_mode:
                logger.debug("【步骤7】图片处理判定丢弃消息")
                logger.debug("=" * 60)
            return
        
        message_text = processed_message
        
        # 检查是否进行了图片转文字（三个条件都满足）
        image_processed = (
            self.config.get('enable_image_processing', False) and  # 配置开启
            self.config.get('image_to_text_provider_id', '') and  # 填了provider
            processed_message != original_message_text  # 转换成功（内容有变化）
        )
        
        if image_processed:
            # 提取图片描述部分（processed_message相对于original_message_text的增量）
            # 将图片描述保存到缓存的最后一条消息
            if chat_id in self.pending_messages_cache and self.pending_messages_cache[chat_id]:
                last_cached = self.pending_messages_cache[chat_id][-1]
                last_cached["image_description"] = processed_message  # 保存完整的处理后消息
                
                if self.debug_mode:
                    logger.debug(f"【步骤7】已保存图片描述到缓存")
                    logger.debug(f"  原始消息长度: {len(original_message_text)}")
                    logger.debug(f"  处理后长度: {len(processed_message)}")
        
        if self.debug_mode:
            logger.debug(f"【步骤7】图片处理完成，图片描述已{'保存' if image_processed else '无'}")
        
        # === 第8步: 提取历史上下文（合并缓存消息）===
        max_context = self.config.get('max_context_messages', 20)
        if self.debug_mode:
            logger.debug("【步骤8】提取历史上下文")
            logger.debug(f"  最大上下文数: {max_context}")
        
        history_messages = ContextManager.get_history_messages(event, max_context)
        
        # 合并缓存中的消息（排除当前消息），并去重
        cached_messages_to_merge = []
        if chat_id in self.pending_messages_cache and len(self.pending_messages_cache[chat_id]) > 1:
            # 获取缓存中除了最后一条（当前消息）之外的所有消息
            cached_messages = self.pending_messages_cache[chat_id][:-1]
            
            if cached_messages and history_messages:
                # 提取历史消息的内容集合（用于去重）
                history_contents = set()
                for msg in history_messages:
                    if isinstance(msg, dict) and 'content' in msg:
                        history_contents.add(msg['content'])
                
                # 过滤掉重复的缓存消息（优先保留历史消息）
                for cached_msg in cached_messages:
                    if isinstance(cached_msg, dict) and 'content' in cached_msg:
                        if cached_msg['content'] not in history_contents:
                            cached_messages_to_merge.append(cached_msg)
                        elif self.debug_mode:
                            logger.debug(f"  跳过重复缓存消息: {cached_msg['content'][:50]}...")
                
                if self.debug_mode:
                    logger.debug(f"  去重前缓存: {len(cached_messages)} 条，去重后: {len(cached_messages_to_merge)} 条")
            elif cached_messages:
                # 如果没有历史消息，直接使用所有缓存
                cached_messages_to_merge = cached_messages
        
        # 合并去重后的缓存消息
        if cached_messages_to_merge:
            if history_messages is None:
                history_messages = []
            history_messages.extend(cached_messages_to_merge)
            
            if self.debug_mode:
                logger.debug(f"  合并缓存消息: {len(cached_messages_to_merge)} 条")
        
        # 应用上下文数量限制
        if history_messages and max_context > 0 and len(history_messages) > max_context:
            history_messages = history_messages[-max_context:]
            if self.debug_mode:
                logger.debug(f"  应用上下文限制，截取最近 {max_context} 条")
        
        if self.debug_mode:
            logger.debug(f"  最终历史消息: {len(history_messages) if history_messages else 0} 条")
        
        # 格式化上下文
        bot_id = event.get_self_id()
        formatted_context = await ContextManager.format_context_for_ai(
            history_messages,
            message_text,
            bot_id
        )
        
        if self.debug_mode:
            logger.debug(f"  格式化后长度: {len(formatted_context)} 字符")
        
        # === 第9步: 决策AI判断(是否回复) ===
        # @消息或触发关键词消息跳过这一步,直接回复
        if not is_at_message and not has_trigger_keyword:
            if self.debug_mode:
                logger.debug("【步骤9】调用决策AI判断是否回复")
                logger.debug(f"  决策AI提供商: {self.config.get('decision_ai_provider_id', '默认')}")
            
            should_reply = await DecisionAI.should_reply(
                self.context,
                event,  # 传入event以获取人格
                formatted_context,
                self.config.get('decision_ai_provider_id', ''),
                self.config.get('decision_ai_extra_prompt', '')
            )
            
            if not should_reply:
                logger.info("决策AI判断: 不应该回复此消息")
                if self.debug_mode:
                    logger.debug("【步骤9】决策AI返回NO,但保存缓存的用户消息")
                
                # 虽然不回复，但将缓存的消息保存到自定义历史（避免上下文断裂）
                try:
                    if chat_id in self.pending_messages_cache and self.pending_messages_cache[chat_id]:
                        # 保存当前缓存的最后一条消息（即本次用户消息）
                        last_cached_msg = self.pending_messages_cache[chat_id][-1]
                        await ContextManager.save_user_message(
                            event,
                            last_cached_msg["content"],
                            None  # 不保存到官方历史，只保存到自定义存储
                        )
                        logger.debug(f"已保存未回复的用户消息到自定义历史")
                        
                        # 注意：不清空缓存，下次触发时仍可使用
                except Exception as e:
                    logger.warning(f"保存未回复消息失败: {e}")
                
                if self.debug_mode:
                    logger.debug("=" * 60)
                return
            
            logger.info("决策AI判断: 应该回复此消息")
            if self.debug_mode:
                logger.debug("【步骤9】决策AI返回YES,继续处理")
        else:
            # 对于@消息或触发关键词消息,先检查是否已经被其他插件处理
            if self.debug_mode:
                if is_at_message:
                    logger.debug("【步骤9】@消息,跳过决策AI")
                if has_trigger_keyword:
                    logger.debug("【步骤9】触发关键词消息,跳过决策AI")
            
            if is_at_message and ReplyHandler.check_if_already_replied(event):
                logger.info("@消息已被其他插件处理,跳过回复")
                if self.debug_mode:
                    logger.debug("【步骤9】@消息已被处理,退出")
                    logger.debug("=" * 60)
                return
        
        # 标记本插件正在处理此会话（用于after_message_sent识别本插件的回复）
        self.processing_sessions[chat_id] = True
        if self.debug_mode:
            logger.debug(f"  已标记会话 {chat_id} 为本插件处理中")
        
        # === 第10步: 移除判断提示词(如果有) ===
        # 决策AI的提示词已经在formatted_context中,但为了确保准确性,重新格式化消息
        # 所以这里实际上已经自动移除了
        
        # === 第11步: 注入记忆(如果启用) ===
        final_message = formatted_context
        
        if self.config.get('enable_memory_injection', False):
            if self.debug_mode:
                logger.debug("【步骤11】注入记忆内容")
            
            # 检查记忆插件是否可用
            if MemoryInjector.check_memory_plugin_available(self.context):
                memories = await MemoryInjector.get_memories(self.context, event)
                if memories:
                    if self.debug_mode:
                        logger.debug(f"  记忆内容预览: {memories[:200]}...")
                    
                    final_message = MemoryInjector.inject_memories_to_message(
                        final_message,
                        memories
                    )
                    if self.debug_mode:
                        logger.debug(f"  已注入记忆,长度增加: {len(final_message) - len(formatted_context)} 字符")
                else:
                    logger.debug("未获取到记忆内容")
                    if self.debug_mode:
                        logger.debug("  记忆内容为空")
            else:
                logger.warning("记忆插件未安装或不可用,跳过记忆注入")
                if self.debug_mode:
                    logger.debug("  记忆插件不可用")
        elif self.debug_mode:
            logger.debug("【步骤11】跳过记忆注入(未启用)")
        
        # === 第12步: 注入工具信息(如果启用) ===
        if self.config.get('enable_tools_reminder', False):
            if self.debug_mode:
                logger.debug("【步骤12】注入工具信息")
            
            old_len = len(final_message)
            final_message = ToolsReminder.inject_tools_to_message(
                final_message,
                self.context
            )
            
            if self.debug_mode:
                logger.debug(f"  已注入工具信息,长度增加: {len(final_message) - old_len} 字符")
        elif self.debug_mode:
            logger.debug("【步骤12】跳过工具信息注入(未启用)")
        
        # === 第13步: 调用AI生成回复 ===
        if self.debug_mode:
            logger.debug("【步骤13】调用AI生成回复")
            logger.debug(f"  最终消息长度: {len(final_message)} 字符")
        
        reply_result = await ReplyHandler.generate_reply(
            event,
            self.context,
            final_message,
            self.config.get('reply_ai_extra_prompt', '')
        )
        
        if self.debug_mode:
            logger.debug("【步骤13】AI回复生成完成")
        
        # === 第14步: 保存用户消息（在发送回复之前）===
        # 先保存用户消息到自定义存储
        if self.debug_mode:
            logger.debug("【步骤14】保存用户消息")
        
        try:
            await ContextManager.save_user_message(event, message_text, self.context)
            if self.debug_mode:
                logger.debug(f"  用户消息已保存: {len(message_text)} 字符")
        except Exception as e:
            logger.error(f"保存用户消息时发生错误: {e}")
        
        # 发送回复
        yield reply_result
        
        # 注意：AI回复的保存将在 after_message_sent 钩子中进行
        # 因为只有在消息发送后，event.result 才会被正确设置
        
        # === 第15步: 调整读空气概率 ===
        # AI已经回复,提升概率以促进连续对话
        if self.debug_mode:
            logger.debug("【步骤15】调整读空气概率")
            logger.debug(f"  新概率: {self.config.get('after_reply_probability', 0.8)}")
            logger.debug(f"  持续时间: {self.config.get('probability_duration', 300)}秒")
        
        ProbabilityManager.boost_probability(
            platform_name,
            is_private,
            chat_id,
            self.config.get('after_reply_probability', 0.8),
            self.config.get('probability_duration', 300)
        )
        
        if self.debug_mode:
            logger.debug("【步骤15】概率调整完成")
            logger.debug("=" * 60)
            logger.debug("✓ 消息处理流程完成")
        
        logger.info("消息处理完成,已发送回复并保存历史")
    
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
            bot_reply_text = "".join([comp.text for comp in event._result.chain if hasattr(comp, 'text')])
            if not bot_reply_text:
                logger.debug(f"[消息发送后] 会话 {chat_id} 回复文本为空，跳过")
                return
            
            logger.info(f"[消息发送后] 会话 {chat_id} - 开始保存AI回复到官方系统，长度: {len(bot_reply_text)} 字符")
            
            # 保存AI回复到自定义存储
            await ContextManager.save_bot_message(event, bot_reply_text, self.context)
            
            # 获取用户消息（从缓存的最后一条消息）
            # 注意：缓存中的消息已经包含了元数据（时间戳+发送者信息）
            message_to_save = ""
            image_desc = None
            
            if chat_id in self.pending_messages_cache and len(self.pending_messages_cache[chat_id]) > 0:
                last_cached = self.pending_messages_cache[chat_id][-1]
                if isinstance(last_cached, dict) and 'content' in last_cached:
                    message_to_save = last_cached['content']  # 已包含元数据
                    # 检查是否有图片描述
                    if 'image_description' in last_cached and last_cached['image_description']:
                        image_desc = last_cached['image_description']
            
            # 如果缓存中没有，尝试从event获取原始消息并添加元数据
            if not message_to_save:
                original_message = event.get_message_plain()
                if original_message:
                    message_to_save = MessageProcessor.add_metadata_to_message(
                        event,
                        original_message,
                        self.config.get('include_timestamp', True),
                        self.config.get('include_sender_info', True)
                    )
            
            if not message_to_save:
                logger.warning("[消息发送后] 无法获取用户消息，跳过官方保存")
                return
            
            # 如果有图片描述，融合到消息中
            if image_desc:
                # 图片描述替换原始消息部分
                # image_desc 已经是完整的处理后消息（包含原文+图片描述）
                # 需要用 image_desc 替换 message_to_save 中的原始消息部分
                # 保留元数据部分（时间戳和发送者信息）
                
                # 提取元数据前缀（时间戳+发送者信息）
                original_msg_in_cache = event.get_message_outline()
                
                # 找到原始消息在 message_to_save 中的位置
                if original_msg_in_cache in message_to_save:
                    # 替换原始消息为图片描述消息
                    message_to_save = message_to_save.replace(original_msg_in_cache, image_desc)
                    if self.debug_mode:
                        logger.debug(f"[消息发送后] 已融合图片描述，最终长度: {len(message_to_save)} 字符")
                else:
                    # 如果找不到（不应该发生），直接在后面追加
                    message_to_save = message_to_save + "\n" + image_desc
                    if self.debug_mode:
                        logger.debug(f"[消息发送后] 追加图片描述，最终长度: {len(message_to_save)} 字符")
            
            if self.debug_mode:
                logger.debug(f"[消息发送后] 保存消息（已含元数据{'和图片描述' if image_desc else ''}）: {message_to_save[:100]}...")
            
            # 准备需要转正的缓存消息（包含那些之前未回复的消息）
            # 需要处理图片描述：如果缓存消息有图片描述，融合进去
            cached_messages_to_convert = []
            if chat_id in self.pending_messages_cache and len(self.pending_messages_cache[chat_id]) > 1:
                # 获取缓存中除了最后一条（当前消息）之外的消息
                raw_cached = self.pending_messages_cache[chat_id][:-1]
                logger.info(f"[消息发送后] 发现 {len(raw_cached)} 条待转正的缓存消息")
                
                # 处理每条缓存消息，融合图片描述
                for cached_msg in raw_cached:
                    if isinstance(cached_msg, dict) and 'content' in cached_msg:
                        msg_content = cached_msg['content']
                        
                        # 检查是否有图片描述
                        if 'image_description' in cached_msg and cached_msg['image_description']:
                            # 有图片描述，需要融合
                            # 注意：cached_msg['content'] 是带元数据的原始消息
                            # cached_msg['image_description'] 是处理后的完整消息（包含原文+图片描述）
                            # 我们需要用图片描述替换原始消息部分
                            
                            # 简化处理：直接用元数据前缀 + 图片描述
                            # 从 msg_content 提取元数据前缀（时间戳+发送者信息）
                            # 然后拼接图片描述
                            
                            # 由于无法从缓存中获取原始的 event，简化处理：
                            # 直接保存图片描述（已包含原文），添加到content后
                            # 或者替换策略：找到原始消息部分并替换
                            
                            # 更简单的方法：保存时直接用 image_description
                            # 但要保留元数据（时间戳和发送者信息）
                            # 假设元数据格式： [时间] [发送者] 原始消息
                            # 需要保留 [时间] [发送者] 部分，替换后面的内容
                            
                            # 查找最后一个 ] 的位置作为元数据结束标记
                            last_bracket = msg_content.rfind(']')
                            if last_bracket != -1:
                                # 提取元数据部分（到最后一个]后面的空格）
                                metadata_end = msg_content.find(' ', last_bracket)
                                if metadata_end != -1:
                                    metadata_prefix = msg_content[:metadata_end + 1]
                                    # 拼接元数据 + 图片描述
                                    msg_content = metadata_prefix + cached_msg['image_description']
                                    if self.debug_mode:
                                        logger.debug(f"[消息发送后] 缓存消息融合图片描述")
                                else:
                                    # 没找到空格，直接用图片描述
                                    msg_content = cached_msg['image_description']
                            else:
                                # 没找到]，说明没有元数据，直接用图片描述
                                msg_content = cached_msg['image_description']
                        
                        # 添加到转正列表
                        cached_messages_to_convert.append({
                            "role": cached_msg.get("role", "user"),
                            "content": msg_content
                        })
            else:
                logger.debug(f"[消息发送后] 没有待转正的缓存消息")
            
            # 保存到官方对话系统（包含缓存转正+去重）
            # 注意：去重逻辑在 save_to_official_conversation_with_cache 内部处理
            # 会自动过滤掉与现有官方历史重复的消息
            logger.info(f"[消息发送后] 准备保存: 缓存{len(cached_messages_to_convert)}条 + 当前对话(用户+AI)")
            success = await ContextManager.save_to_official_conversation_with_cache(
                event,
                cached_messages_to_convert,  # 待转正的缓存消息（未去重，交给方法内部处理）
                message_to_save,  # 当前用户消息（已添加时间戳和发送者信息）
                bot_reply_text,  # AI回复
                self.context
            )
            
            if success:
                logger.info(f"[消息发送后] ✅ 成功保存到官方对话系统")
                # 成功保存后，清空该会话的消息缓存（包括图片描述）
                if chat_id in self.pending_messages_cache:
                    cleared_count = len(self.pending_messages_cache[chat_id])
                    # 统计清空的图片描述数量
                    image_desc_count = sum(
                        1 for msg in self.pending_messages_cache[chat_id]
                        if isinstance(msg, dict) and msg.get('image_description')
                    )
                    # 清空整个缓存列表（包括所有消息和图片描述）
                    self.pending_messages_cache[chat_id] = []
                    
                    if self.debug_mode:
                        logger.debug(f"[消息发送后] 已清空消息缓存: {cleared_count} 条消息")
                        if image_desc_count > 0:
                            logger.debug(f"[消息发送后] 已清空图片描述: {image_desc_count} 条")
                    else:
                        logger.debug(f"[消息发送后] 已清空消息缓存: {cleared_count} 条（含 {image_desc_count} 条图片描述）")
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
        enabled_groups = self.config.get('enabled_groups', [])
        
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
    
    def _check_probability(
        self,
        platform_name: str,
        is_private: bool,
        chat_id: str
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
        current_probability = ProbabilityManager.get_current_probability(
            platform_name,
            is_private,
            chat_id,
            self.config.get('initial_probability', 0.1)
        )
        
        if self.debug_mode:
            logger.debug(f"  当前概率: {current_probability:.2f}")
            logger.debug(f"  初始概率: {self.config.get('initial_probability', 0.1):.2f}")
            logger.debug(f"  会话ID: {chat_id}")
        
        # 随机判断
        roll = random.random()
        should_process = roll < current_probability
        
        logger.debug(f"读空气概率检查: 当前概率={current_probability:.2f}, 随机值={roll:.2f}, 结果={'触发' if should_process else '未触发'}")
        
        if self.debug_mode:
            logger.debug(f"  随机值: {roll:.4f}")
            logger.debug(f"  判定: {'通过' if should_process else '失败'} ({roll:.4f} {'<' if should_process else '>='} {current_probability:.4f})")
        
        return should_process
      