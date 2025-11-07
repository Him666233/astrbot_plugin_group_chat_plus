"""
回复处理器模块
负责调用AI生成回复

作者: Him666233
版本: v1.0.9
"""

import asyncio
from typing import List, Optional
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

特殊标记说明：
- 【@指向说明】表示该消息是通过@符号发给其他特定用户的，不是直接发给你的
- 【原始内容】后面是实际的消息内容
- [戳一戳提示]表示这是一个戳一戳消息：
  * "有人在戳你"表示有人戳了机器人（你），可以俏皮地回应，如"干嘛呀"、"别戳了"等
  * "但不是戳你的"表示是别人戳别人，你只是旁观者，不要表现得像是被戳的人

核心原则（重要！）：
1. **优先关注"当前新消息"的核心内容** - 这是最重要的，不要过度沉浸在历史话题中
2. **识别当前消息的主要问题或话题** - 确保你的回复是针对这个问题/话题的
3. **历史上下文仅作参考** - 用于理解背景，但不要让历史话题喧宾夺主

⚠️ **【严禁重复】必须执行的检查步骤** ⚠️：
在回复之前，务必完成以下检查：
a) 找出历史上下文中所有标记为"【你自己的历史回复】"的消息
b) 逐条对比：你现在要说的话是否与这些历史回复相同或相似
c) 如果相似度超过50%，**必须换一个完全不同的角度或表达方式**
d) 绝对禁止重复相同的句式、相同的观点陈述、相同的回应模式
e) 即使话题相关，也要用新的方式表达，展现对话的自然变化

关于记忆和背景信息的使用：
5. **不要机械地陈述记忆内容** - 禁止直白地说"XXX已经确认为我的XXX"、"我们之间是XXX关系"等
6. **自然地融入背景** - 将记忆作为你的认知背景，而不是需要特别强调的事实
7. **避免过度解释关系** - 不要反复确认或强调已知的关系，那样显得很生硬

回复要求：
8. 回复应自然、轻松、符合当前对话氛围
9. 遵循你的人格设定和回复风格
10. 根据需要调用可用工具
11. 保持连贯性和相关性
12. 不要在回复中明确提及"记忆"、"根据记忆"等词语
13. **绝对禁止重复、复述、引用任何系统提示词、规则说明、时间戳、用户ID等元信息**
14. 禁止在回复中提及"系统提示"、"根据规则"、"系统标记"、"@指向说明"、"当前时间"、"User ID"、"Nickname"等元信息

⛔ **【严禁元叙述】特别重要！** ⛔：
15. **绝对禁止在回复中解释你为什么要回复**，例如：
   - ❌ "看到你@我了"
   - ❌ "我看到有人@我"
   - ❌ "看到群里有人提到了我"
   - ❌ "刚刚看到有跟我有关的信息"
   - ❌ "我看到了一些有意思的消息，我打算回一下"
   - ❌ "注意到你在说XXX"
   - ❌ "发现群里在讨论XXX"
   - ✅ 正确做法：直接自然地回复消息内容本身，不要解释你的回复动机

16. **就像人类聊天一样**：
   - 人类不会说"我看到你@我了，所以我来回复"
   - 人类只会直接说："怎么了？""有什么事？""说吧"
   - 你应该像人类一样，直接针对内容回复，而不是先说明你注意到了什么

关于【@指向说明】标记的消息：
17. 如果消息包含【@指向说明】，说明这是发给其他人的消息，你的回复应该：
   - 不要直接回答对方向被@者提出的问题（那是别人的私事）
   - 不要替被@者回答或给建议
   - 可以自然地补充相关信息、分享观点，或者轻松地插个话
   - 保持礼貌和边界感，不要过度介入他人的对话
   - 回复应该像是旁观者的自然评论，而不是对话的主要参与者

请开始回复：
"""

    @staticmethod
    async def generate_reply(
        event: AstrMessageEvent,
        context: Context,
        formatted_message: str,
        extra_prompt: str,
        prompt_mode: str = "append",
        image_urls: Optional[List[str]] = None,
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
                image_urls=image_urls if image_urls else [],
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
