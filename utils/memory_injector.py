"""
记忆注入器模块
负责调用记忆插件获取长期记忆内容

⚠️ 耦合警告：
本模块与 strbot_plugin_play_sy 插件存在紧密耦合关系。
具体依赖：
- 依赖该插件的 get_memories 工具函数
- 直接访问该工具的 handler 属性（非公开API）
- 如果 strbot_plugin_play_sy 插件的内部实现发生变化，本模块可能失效

建议：
- 使用前确保已安装 strbot_plugin_play_sy 插件
- 如果该插件更新导致兼容性问题，需要相应更新本模块
- 未来应考虑使用更稳定的插件间通信机制

作者: Him666233
版本: v1.0.1
"""

from typing import Optional
from astrbot.api.all import *


class MemoryInjector:
    """
    记忆注入器

    主要功能：
    1. 检测记忆插件（strbot_plugin_play_sy）是否可用
    2. 调用记忆插件的get_memories工具
    3. 将记忆内容注入到消息中

    ⚠️ 耦合说明：
    本类通过直接访问 strbot_plugin_play_sy 插件的内部 handler 属性来调用功能。
    这是一种不稳定的集成方式，可能在插件更新后失效。
    """

    @staticmethod
    def check_memory_plugin_available(context: Context) -> bool:
        """
        检查记忆插件是否可用

        通过检查get_memories工具是否注册来判断

        Args:
            context: Context对象

        Returns:
            True=可用，False=不可用
        """
        try:
            # 获取LLM工具管理器
            tool_manager = context.get_llm_tool_manager()
            if not tool_manager:
                logger.debug("无法获取LLM工具管理器")
                return False

            # 检查是否有get_memories工具
            get_memories_tool = tool_manager.get_func("get_memories")
            if get_memories_tool:
                logger.debug("检测到记忆插件已安装(找到get_memories工具)")
                return True

            logger.debug("未检测到记忆插件(未找到get_memories工具)")
            return False

        except Exception as e:
            logger.error(f"检查记忆插件时发生错误: {e}")
            return False

    @staticmethod
    async def get_memories(context: Context, event: AstrMessageEvent) -> Optional[str]:
        """
        调用记忆插件获取记忆内容

        通过get_memories工具函数获取长期记忆

        ⚠️ 实现警告：
        本方法直接访问 get_memories 工具的 handler 属性，这是一种侵入式的调用方式。
        如果 strbot_plugin_play_sy 插件的内部实现发生变化（例如重命名 handler 属性），
        本方法将失效。这是一个已知的技术债务，未来应寻找更稳定的集成方案。

        Args:
            context: Context对象
            event: 消息事件

        Returns:
            记忆文本，失败返回None
        """
        try:
            # 获取LLM工具管理器
            tool_manager = context.get_llm_tool_manager()
            if not tool_manager:
                logger.warning("无法获取LLM工具管理器")
                return None

            # 使用get_func方法查找get_memories工具
            get_memories_tool = tool_manager.get_func("get_memories")

            if not get_memories_tool:
                logger.warning("未找到get_memories工具,可能记忆插件未正确注册")
                return None

            logger.debug("正在调用记忆插件获取记忆...")

            # ⚠️ 紧密耦合点：直接访问内部 handler 属性
            # 这依赖于 strbot_plugin_play_sy 插件的具体实现细节
            # 如果插件重构，此处可能需要更新
            if hasattr(get_memories_tool, "handler"):
                memory_result = await get_memories_tool.handler(event=event)
            else:
                logger.warning("get_memories工具没有handler属性，可能插件版本不兼容")
                return None

            if memory_result and isinstance(memory_result, str):
                logger.info(f"成功获取记忆: {len(memory_result)} 字符")
                # 详细日志：显示实际获取到的记忆内容
                logger.debug(f"获取到的记忆内容:\n{memory_result}")
                return memory_result
            else:
                logger.debug("记忆插件返回空内容或无记忆")
                return "当前没有任何记忆。"

        except Exception as e:
            logger.error(f"获取记忆时发生错误: {e}")
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
            logger.debug("没有记忆内容需要注入")
            return original_message

        # 在消息末尾添加记忆部分
        injected_message = original_message + "\n\n=== 背景信息 ===\n" + memories
        injected_message += "\n\n(这些信息可能对理解当前对话有帮助，请自然地融入到你的回答中，而不要明确提及)"

        logger.debug("记忆已注入到消息中")
        return injected_message
