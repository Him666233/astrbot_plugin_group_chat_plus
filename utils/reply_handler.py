"""
回复处理器模块
负责调用AI生成回复

作者: Him666233
版本: v1.0.2
"""

import asyncio
from astrbot.api.all import *
from astrbot.core.provider.entities import ProviderRequest


class ReplyHandler:
    """
    回复处理器

    主要功能：
    1. 构建回复提示词
    2. 调用AI生成回复
    3. 检测是否已被其他插件处理
    """

    # 系统回复提示词
    SYSTEM_REPLY_PROMPT = """
请根据上述对话和背景信息生成自然的回复。

注意事项：
1. 回复应自然、符合上下文
2. 遵循你的人格设定和回复风格
3. 根据需要调用可用工具
4. 保持连贯性和相关性
5. 不要在回复中明确提及"记忆"、"根据记忆"等词语，而是自然地融入相关信息

请开始回复：
"""

    @staticmethod
    async def generate_reply(
        event: AstrMessageEvent,
        context: Context,
        formatted_message: str,
        extra_prompt: str,
        prompt_mode: str = "append",
    ) -> ProviderRequest:
        """
        生成AI回复

        Args:
            event: 消息事件
            context: Context对象
            formatted_message: 格式化后的完整消息（含上下文、记忆、工具等）
            extra_prompt: 用户自定义补充提示词
            prompt_mode: 提示词模式，append=拼接，override=覆盖

        Returns:
            ProviderRequest对象
        """
        try:
            # 构建完整的提示词，根据prompt_mode决定拼接还是覆盖
            if prompt_mode == "override" and extra_prompt and extra_prompt.strip():
                # 覆盖模式：直接使用用户自定义提示词
                full_prompt = formatted_message + "\n\n" + extra_prompt.strip()
                logger.debug("使用覆盖模式：用户自定义提示词完全替代默认系统提示词")
            else:
                # 拼接模式（默认）：使用默认提示词，如果有用户自定义则追加
                full_prompt = (
                    formatted_message + "\n\n" + ReplyHandler.SYSTEM_REPLY_PROMPT
                )

                # 如果有用户自定义提示词,添加进去
                if extra_prompt and extra_prompt.strip():
                    full_prompt += f"\n\n用户补充说明:\n{extra_prompt.strip()}"
                    logger.debug("使用拼接模式：在默认系统提示词后追加用户自定义提示词")

            logger.debug("正在调用AI生成回复...")

            # 获取工具管理器(如果需要)
            func_tools_mgr = context.get_llm_tool_manager()

            # 获取人格的system_prompt (参考SpectreCore的方式)
            system_prompt = ""
            contexts = []
            try:
                # 尝试获取personas列表
                if hasattr(context, "provider_manager") and hasattr(
                    context.provider_manager, "personas"
                ):
                    # 获取默认人格
                    default_persona = None
                    if hasattr(context.provider_manager, "selected_default_persona"):
                        default_persona = (
                            context.provider_manager.selected_default_persona
                        )

                    if default_persona:
                        system_prompt = default_persona.get("prompt", "")
                        # 获取begin_dialogs作为上下文
                        begin_dialogs = default_persona.get(
                            "_begin_dialogs_processed", []
                        )
                        if begin_dialogs:
                            contexts.extend(begin_dialogs)
                        logger.debug(
                            f"已获取人格提示词（provider_manager方式），长度: {len(system_prompt)} 字符"
                        )
                    else:
                        # fallback: 使用persona_manager
                        default_persona = (
                            await context.persona_manager.get_default_persona_v3(
                                event.unified_msg_origin
                            )
                        )
                        system_prompt = default_persona.get("prompt", "")
                        logger.debug(
                            f"已获取人格提示词（persona_manager方式），长度: {len(system_prompt)} 字符"
                        )
                else:
                    # fallback: 使用persona_manager
                    default_persona = (
                        await context.persona_manager.get_default_persona_v3(
                            event.unified_msg_origin
                        )
                    )
                    system_prompt = default_persona.get("prompt", "")
                    logger.debug(
                        f"已获取人格提示词（persona_manager方式），长度: {len(system_prompt)} 字符"
                    )
            except Exception as e:
                logger.warning(f"获取人格设定失败: {e}，使用空人格")

            # 使用event.request_llm来生成回复
            # 直接传入system_prompt，不使用conversation
            return event.request_llm(
                prompt=full_prompt,
                func_tool_manager=func_tools_mgr,
                contexts=contexts,  # 包含begin_dialogs
                system_prompt=system_prompt,  # 直接使用人格的prompt
                image_urls=[],
            )

        except Exception as e:
            logger.error(f"生成AI回复时发生错误: {e}")
            # 返回错误消息
            return event.plain_result(f"生成回复时发生错误: {str(e)}")

    @staticmethod
    def check_if_already_replied(event: AstrMessageEvent) -> bool:
        """
        检查消息是否已被其他插件处理

        用于@消息兼容，避免重复回复

        Args:
            event: 消息事件

        Returns:
            True=已有回复，False=尚未回复
        """
        try:
            # 检查event的result字段
            # 如果已经有result,说明已经被处理了
            result = event.get_result()

            if result is not None:
                logger.debug("检测到该消息已经被其他插件处理")
                return True

            return False

        except Exception as e:
            logger.error(f"检查消息是否已回复时发生错误: {e}")
            # 发生错误时,为安全起见,返回True避免重复回复
            return True
