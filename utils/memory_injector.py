"""
记忆注入器模块
负责调用记忆插件获取长期记忆内容

支持两种记忆插件模式：
1. Legacy模式（旧版）：
   - 插件：strbot_plugin_play_sy (又叫 ai_memory)
   - 方式：通过 LLM Tool 调用 get_memories 工具函数
   - 耦合：直接访问 handler 属性（紧密耦合）

2. LivingMemory模式（新版）：
   - 插件：astrbot_plugin_livingmemory
   - 方式：通过插件实例访问 memory_engine.search_memories()
   - 耦合：使用公开API，松耦合
   - 特性：混合检索、智能总结、自动遗忘、会话隔离、人格隔离

⚠️ 重要说明：
- 两种模式互斥，只能选择其中一种
- LivingMemory模式强制启用会话隔离和人格隔离
- 每次调用都会实时获取当前人格ID，支持动态人格切换

作者: Him666233
版本: v1.2.0
"""

from typing import Optional
from datetime import datetime
from astrbot.api.all import *

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class MemoryInjector:
    """
    记忆注入器

    主要功能：
    1. 检测记忆插件是否可用（支持Legacy和LivingMemory两种模式）
    2. 调用记忆插件获取长期记忆
    3. 将记忆内容注入到消息中
    4. 支持动态人格切换（每次调用实时获取人格ID）

    支持的插件模式：
    - Legacy: strbot_plugin_play_sy (紧密耦合，通过Tool调用)
    - LivingMemory: astrbot_plugin_livingmemory (松耦合，通过公开API)

    隔离策略：
    - 强制会话隔离：每个会话的记忆独立
    - 强制人格隔离：支持多人格场景，避免人格记忆混淆
    - 实时人格获取：不缓存人格ID，每次调用都重新获取
    """

    @staticmethod
    def check_memory_plugin_available(context: Context, mode: str = "legacy") -> bool:
        """
        检查记忆插件是否可用

        Args:
            context: Context对象
            mode: 插件模式，"legacy"或"livingmemory"

        Returns:
            True=可用，False=不可用
        """
        try:
            if mode == "legacy":
                # Legacy模式：检查get_memories工具是否注册
                tool_manager = context.get_llm_tool_manager()
                if not tool_manager:
                    if DEBUG_MODE:
                        logger.info("[Legacy模式] 无法获取LLM工具管理器")
                    return False

                get_memories_tool = tool_manager.get_func("get_memories")
                if get_memories_tool:
                    if DEBUG_MODE:
                        logger.info(
                            "[Legacy模式] 检测到 strbot_plugin_play_sy 插件已安装"
                        )
                    return True

                if DEBUG_MODE:
                    logger.info("[Legacy模式] 未检测到 strbot_plugin_play_sy 插件")
                return False

            elif mode == "livingmemory":
                # LivingMemory模式：检查插件实例是否存在
                star_metadata = context.get_registered_star(
                    "astrbot_plugin_livingmemory"
                )
                if not star_metadata:
                    if DEBUG_MODE:
                        logger.info("[LivingMemory模式] 未找到 LivingMemory 插件")
                    return False

                if not star_metadata.activated:
                    if DEBUG_MODE:
                        logger.info("[LivingMemory模式] LivingMemory 插件未激活")
                    return False

                if not star_metadata.star_cls:
                    if DEBUG_MODE:
                        logger.info("[LivingMemory模式] LivingMemory 插件实例不存在")
                    return False

                # 检查插件是否已初始化
                plugin_instance = star_metadata.star_cls
                if not hasattr(plugin_instance, "_initialization_complete"):
                    if DEBUG_MODE:
                        logger.info(
                            "[LivingMemory模式] LivingMemory 插件缺少初始化状态"
                        )
                    return False

                if not plugin_instance._initialization_complete:
                    if DEBUG_MODE:
                        logger.info(
                            "[LivingMemory模式] LivingMemory 插件尚未完成初始化"
                        )
                    return False

                if (
                    not hasattr(plugin_instance, "memory_engine")
                    or not plugin_instance.memory_engine
                ):
                    if DEBUG_MODE:
                        logger.info(
                            "[LivingMemory模式] LivingMemory 插件的 memory_engine 未初始化"
                        )
                    return False

                if DEBUG_MODE:
                    logger.info("[LivingMemory模式] 检测到 LivingMemory 插件已就绪")
                return True

            else:
                logger.warning(f"不支持的记忆插件模式: {mode}")
                return False

        except Exception as e:
            logger.error(f"检查记忆插件时发生错误 (mode={mode}): {e}")
            return False

    @staticmethod
    async def get_memories(
        context: Context, event: AstrMessageEvent, mode: str = "legacy", top_k: int = 5
    ) -> Optional[str]:
        """
        调用记忆插件获取记忆内容（支持双模式）

        支持两种插件模式：
        - legacy: 通过 get_memories 工具函数调用（紧密耦合）
        - livingmemory: 通过 memory_engine.search_memories() 调用（松耦合）

        ⚠️ 重要特性：
        - 强制会话隔离：每个会话的记忆独立
        - 强制人格隔离：每次调用实时获取当前人格ID
        - 不缓存人格：支持动态人格切换场景

        Args:
            context: Context对象
            event: 消息事件
            mode: 插件模式，"legacy" 或 "livingmemory"
            top_k: 召回记忆数量（仅LivingMemory模式有效）
                   - 正整数：召回指定数量的记忆
                   - -1：召回所有相关记忆（最多1000条）

        📊 LivingMemory排序机制（自动按优先级排序）：
            1. 综合得分 = 相关性 × 重要性 × 时间新鲜度
            2. 按综合得分降序排序
            3. 返回前 top_k 条（或全部）

        ⚠️ 注意：返回的记忆已按重要性和相关性排序，前面的更重要！

        Returns:
            记忆文本，失败返回None
        """
        try:
            if mode == "legacy":
                # ===== Legacy模式：通过Tool调用 =====
                tool_manager = context.get_llm_tool_manager()
                if not tool_manager:
                    logger.warning("[Legacy模式] 无法获取LLM工具管理器")
                    return None

                get_memories_tool = tool_manager.get_func("get_memories")
                if not get_memories_tool:
                    logger.warning("[Legacy模式] 未找到get_memories工具")
                    return None

                if hasattr(event, "unified_msg_origin"):
                    logger.info(
                        f"[Legacy模式] 正在调用记忆插件获取记忆...\n"
                        f"  🔑 unified_msg_origin: {event.unified_msg_origin}"
                    )

                # ⚠️ 紧密耦合：直接访问 handler 属性
                if hasattr(get_memories_tool, "handler"):
                    memory_result = await get_memories_tool.handler(event=event)
                else:
                    logger.warning("[Legacy模式] get_memories工具没有handler属性")
                    return None

                if memory_result and isinstance(memory_result, str):
                    logger.info(f"[Legacy模式] 成功获取记忆: {len(memory_result)} 字符")
                    if DEBUG_MODE:
                        logger.info(f"[Legacy模式] 记忆内容:\n{memory_result}")
                    return memory_result
                else:
                    logger.info("[Legacy模式] 记忆插件返回空内容")
                    return "当前没有任何记忆。"

            elif mode == "livingmemory":
                # ===== LivingMemory模式：通过公开API调用 =====
                star_metadata = context.get_registered_star(
                    "astrbot_plugin_livingmemory"
                )
                if not star_metadata or not star_metadata.star_cls:
                    logger.warning("[LivingMemory模式] 插件实例不存在")
                    return None

                plugin_instance = star_metadata.star_cls

                # 检查初始化状态
                if not getattr(plugin_instance, "_initialization_complete", False):
                    logger.warning("[LivingMemory模式] 插件尚未完成初始化")
                    return None

                if (
                    not hasattr(plugin_instance, "memory_engine")
                    or not plugin_instance.memory_engine
                ):
                    logger.warning("[LivingMemory模式] memory_engine 未初始化")
                    return None

                memory_engine = plugin_instance.memory_engine

                # 获取会话ID和人格ID（每次都实时获取，不缓存）
                session_id = event.unified_msg_origin

                # 实时获取当前人格ID（支持动态人格切换）
                try:
                    persona_id = (
                        context.persona_manager.get_personas_by_key(session_id).name
                        if context.persona_manager
                        else None
                    )
                except Exception as pe:
                    logger.debug(f"[LivingMemory模式] 获取人格ID失败: {pe}")
                    persona_id = None

                # 获取用户消息内容
                user_message = ""
                if hasattr(event, "message_str") and event.message_str:
                    user_message = event.message_str
                elif hasattr(event, "message") and event.message:
                    user_message = str(event.message)

                if not user_message:
                    logger.warning("[LivingMemory模式] 无法获取用户消息内容")
                    return None

                # 处理 top_k=-1 的情况（召回全部）
                actual_top_k = top_k
                if top_k == -1:
                    actual_top_k = 1000  # 设置一个合理的上限，避免性能问题
                    logger.info(
                        f"[LivingMemory模式] top_k=-1，将召回所有相关记忆（最多{actual_top_k}条）"
                    )

                logger.info(
                    f"[LivingMemory模式] 正在调用记忆引擎...\n"
                    f"  🔑 session_id: {session_id}\n"
                    f"  👤 persona_id: {persona_id}\n"
                    f"  📝 query: {user_message[:50]}...\n"
                    f"  🔢 top_k: {top_k} (实际: {actual_top_k})\n"
                    f"  📊 排序: 相关性×重要性×新鲜度 (自动优先返回重要记忆)"
                )

                # 调用 memory_engine.search_memories()
                # 强制传入 session_id 和 persona_id 实现双重隔离
                # LivingMemory会自动按综合得分排序：相关性 × 重要性 × 时间新鲜度
                memories = await memory_engine.search_memories(
                    query=user_message,
                    k=actual_top_k,  # 使用处理后的 top_k
                    session_id=session_id,  # 强制会话隔离
                    persona_id=persona_id,  # 强制人格隔离
                )

                if not memories:
                    logger.info("[LivingMemory模式] 未找到相关记忆")
                    return "当前没有任何记忆。"

                # 格式化记忆内容（详细格式：类似Legacy模式，含时间戳）
                # 注意：memories已经按综合得分排序，索引号越小越重要
                memory_texts = []
                for i, mem in enumerate(memories, 1):
                    content = getattr(mem, "content", "")
                    metadata = getattr(mem, "metadata", {})

                    # 提取重要性信息
                    importance = (
                        metadata.get("importance", 0.5)
                        if isinstance(metadata, dict)
                        else 0.5
                    )

                    # 转换为星级显示（1-5颗星）
                    star_count = max(1, min(5, int(importance * 5)))
                    importance_stars = "⭐" * star_count

                    # 提取时间戳并格式化
                    create_time = (
                        metadata.get("create_time")
                        if isinstance(metadata, dict)
                        else None
                    )
                    time_str = "未知时间"
                    if create_time:
                        try:
                            dt = datetime.fromtimestamp(float(create_time))
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except (ValueError, TypeError, OSError):
                            time_str = "未知时间"

                    # 详细格式：序号 + 内容 + 重要程度 + 时间
                    memory_text = (
                        f"{i}. {content}\n"
                        f"   重要程度: {importance_stars} ({star_count}/5)\n"
                        f"   时间: {time_str}"
                    )
                    memory_texts.append(memory_text)

                result = "\n\n".join(memory_texts)
                logger.info(
                    f"[LivingMemory模式] 成功获取 {len(memories)} 条记忆，总长度: {len(result)} 字符"
                )

                if DEBUG_MODE:
                    logger.info(
                        f"[LivingMemory模式] 记忆内容:\n"
                        f"{'=' * 60}\n"
                        f"{result}\n"
                        f"{'=' * 60}"
                    )

                return result

            else:
                logger.error(f"不支持的记忆插件模式: {mode}")
                return None

        except Exception as e:
            logger.error(f"获取记忆时发生错误 (mode={mode}): {e}", exc_info=True)
            return None

    @staticmethod
    async def get_memories_by_session(
        context: Context, unified_msg_origin: str, mode: str = "legacy", top_k: int = 5
    ) -> Optional[str]:
        """
        通过 unified_msg_origin 获取记忆内容（用于主动对话场景）

        ⚠️ 注意：主动对话场景的特殊处理
        - Legacy模式：直接传递 unified_msg_origin 即可
        - LivingMemory模式：使用会话最近的对话内容作为检索query

        Args:
            context: Context对象
            unified_msg_origin: 统一消息来源标识 (格式: "platform:MessageType:chat_id")
            mode: 插件模式，"legacy" 或 "livingmemory"
            top_k: 召回记忆数量（仅LivingMemory模式有效）

        Returns:
            记忆文本，失败返回None
        """
        try:
            logger.info(
                f"[主动对话-{mode}模式] 调用记忆插件获取记忆\n"
                f"  unified_msg_origin: {unified_msg_origin}"
            )

            if mode == "legacy":
                # Legacy模式：构造模拟事件对象
                from types import SimpleNamespace

                mock_event = SimpleNamespace()
                mock_event.unified_msg_origin = unified_msg_origin

                # 直接复用 get_memories 方法
                result = await MemoryInjector.get_memories(
                    context, mock_event, mode="legacy"
                )

                if result is None:
                    logger.warning(
                        f"[主动对话-Legacy] 记忆获取失败\n"
                        f"  unified_msg_origin: {unified_msg_origin}"
                    )
                    return "当前没有任何记忆。"
                return result

            elif mode == "livingmemory":
                # LivingMemory模式：需要查询字符串，使用会话历史或通用查询
                from types import SimpleNamespace

                mock_event = SimpleNamespace()
                mock_event.unified_msg_origin = unified_msg_origin

                # 为主动对话场景构造通用query
                # 可以使用"最近的对话"、"我们之前聊了什么"等通用查询
                mock_event.message_str = "最近的对话内容和背景信息"

                # 处理 top_k=-1 的情况
                if top_k == -1:
                    logger.info(
                        "[主动对话-LivingMemory] 配置为召回所有记忆（最多1000条）"
                    )

                # 调用 get_memories 方法
                result = await MemoryInjector.get_memories(
                    context, mock_event, mode="livingmemory", top_k=top_k
                )

                if result is None:
                    logger.warning(
                        f"[主动对话-LivingMemory] 记忆获取失败\n"
                        f"  unified_msg_origin: {unified_msg_origin}"
                    )
                    return "当前没有任何记忆。"
                return result

            else:
                logger.error(f"[主动对话] 不支持的记忆插件模式: {mode}")
                return None

        except Exception as e:
            logger.error(
                f"[主动对话] 获取记忆时发生错误 (mode={mode}): {e}", exc_info=True
            )
            return None

    @staticmethod
    def inject_memories_to_message(original_message: str, memories: str) -> str:
        """
        将记忆内容注入到消息

        Args:
            original_message: 原始消息（含上下文）
            memories: 记忆内容

        Returns:
            注入记忆后的文本
        """
        if not memories or not memories.strip():
            logger.info("没有记忆内容需要注入")
            return original_message

        # 🔧 幂等性检查：避免重复注入
        if "=== 背景信息 ===" in original_message:
            logger.warning("检测到消息中已存在背景信息标记，跳过重复注入")
            if DEBUG_MODE:
                logger.info(
                    f"原始消息已包含记忆内容，长度: {len(original_message)} 字符"
                )
            return original_message

        # 在消息末尾添加记忆部分
        injected_message = original_message + "\n\n=== 背景信息 ===\n" + memories
        injected_message += "\n\n(这些信息可能对理解当前对话有帮助，请自然地融入到你的回答中，而不要明确提及)"

        logger.info(f"成功注入记忆: {len(memories)} 字符")
        if DEBUG_MODE:
            logger.info(f"注入后的消息内容:\n{injected_message}")
        return injected_message
