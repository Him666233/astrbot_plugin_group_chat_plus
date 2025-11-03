"""
决策AI模块
负责调用AI判断是否应该回复消息（读空气功能）

作者: Him666233
版本: v1.0.6
"""

import asyncio
from astrbot.api.all import *


class DecisionAI:
    """
    决策AI，负责读空气判断

    主要功能：
    1. 构建判断提示词
    2. 调用AI分析是否应该回复
    3. 解析yes/no结果
    """

    # 系统判断提示词模板（积极参与模式）
    SYSTEM_DECISION_PROMPT = """
你是一个活跃、友好的群聊参与者，请判断是否回复当前这条新消息。

核心原则（重要！）：
1. **优先关注"当前新消息"的核心内容** - 这是判断的首要依据
2. **识别当前消息的主要问题或话题** - 判断是否与这个问题/话题相关
3. **历史上下文仅作参考** - 用于理解背景，但不要因为历史话题有趣就忽略当前消息的实际内容

⚠️ **【防止重复】必须检查的事项** ⚠️：
在判断是否回复之前，务必检查：
1) 查看历史上下文中标记为"【你自己的历史回复】"的所有消息
2) 判断：如果你回复当前消息，会不会与最近的历史回复表达相同或相似的观点？
3) 如果最近2-3条历史回复已经充分表达过相似观点，**应该返回 no（避免啰嗦重复）**
4) 只有当前消息提出新的问题、新的角度，或需要补充新信息时，才考虑回复

判断原则（倾向于积极参与）：

  建议回复的情况：
   - 当前消息与你之前的回复相关，**且有新的话题发展**
   - 当前消息提到了有趣的话题，你可以贡献**新的看法**
   - 当前消息有人提问或需要帮助
   - 当前消息的话题符合你的人格特点
   - 群聊气氛活跃，适合互动
   - 当前消息有讨论价值

  建议不回复的情况：
   - 当前消息明显是他人的私密对话
   - 当前消息只是系统通知或纯表情
   - 当前消息的话题完全超出你的知识范围
   - 当前消息包含【@指向说明】，说明是发给其他特定用户的，一般不应插入
   - **你最近的历史回复已经充分表达过相同观点，再次回复会重复啰嗦**
   - 当前消息只是在重复已讨论过的话题，没有新的发展

特殊标记说明：
   - 【@指向说明】表示消息通过@符号指定发送给其他特定用户，并非发给你
   - 看到此标记时，通常应该不回复，除非：
     1. 消息明确提到了你的名字或要求你参与
     2. 是公开讨论/辩论/征求意见等明显欢迎多人参与的场合
     3. 发送者在后续消息中明确邀请你加入讨论
   - 对于两人之间的私密对话、安慰、询问等，即使内容有趣也不要插入
   - 【原始内容】后面是实际的消息内容

重要提示：
- 你的目标是促进对话，不是保持沉默
- 不确定时倾向于回复，但对于【@指向说明】标记的消息要谨慎
- 根据你的人格特点决定活跃度
- 尊重他人的私密对话空间
- **记住：判断依据是"当前新消息"本身，不要被历史话题带偏**

输出要求：
   - 应该回复请输出: yes
   - 不应该回复请输出: no
   - 只输出yes或no，不要其他内容
   - 禁止输出任何解释、理由或元信息（如"我根据规则判断..."）

⚠️ 特别提醒：
   - 这只是判断是否回复，不是生成实际回复内容
   - 你的判断结果不会被用户看到
   - 只需要输出yes或no来表达你的判断即可

请开始判断：
"""

    @staticmethod
    async def should_reply(
        context: Context,
        event: AstrMessageEvent,
        formatted_message: str,
        provider_id: str,
        extra_prompt: str,
        timeout: int = 30,
        prompt_mode: str = "append",
    ) -> bool:
        """
        调用AI判断是否应该回复

        Args:
            context: Context对象
            event: 消息事件
            formatted_message: 格式化后的消息（含上下文）
            provider_id: AI提供商ID，空=默认
            extra_prompt: 用户自定义补充提示词
            timeout: 超时时间（秒）
            prompt_mode: 提示词模式，append=拼接，override=覆盖

        Returns:
            True=应该回复，False=不回复
        """
        try:
            # 获取AI提供商
            if provider_id:
                provider = context.get_provider_by_id(provider_id)
                if not provider:
                    logger.warning(f"无法找到提供商 {provider_id},使用默认提供商")
                    provider = context.get_using_provider()
            else:
                provider = context.get_using_provider()

            if not provider:
                logger.error("无法获取AI提供商")
                return False

            # 获取人格的system_prompt (参考SpectreCore的方式)
            try:
                # 尝试获取personas列表
                if hasattr(context, "provider_manager") and hasattr(
                    context.provider_manager, "personas"
                ):
                    personas = context.provider_manager.personas
                    # 获取默认人格
                    default_persona = None
                    if hasattr(context.provider_manager, "selected_default_persona"):
                        default_persona = (
                            context.provider_manager.selected_default_persona
                        )

                    if default_persona:
                        persona_prompt = default_persona.get("prompt", "")
                        logger.debug(
                            f"已获取人格提示词（provider_manager方式），长度: {len(persona_prompt)} 字符"
                        )
                    else:
                        # fallback: 使用persona_manager
                        default_persona = (
                            await context.persona_manager.get_default_persona_v3(
                                event.unified_msg_origin
                            )
                        )
                        persona_prompt = default_persona.get("prompt", "")
                        logger.debug(
                            f"已获取人格提示词（persona_manager方式），长度: {len(persona_prompt)} 字符"
                        )
                else:
                    # fallback: 使用persona_manager
                    default_persona = (
                        await context.persona_manager.get_default_persona_v3(
                            event.unified_msg_origin
                        )
                    )
                    persona_prompt = default_persona.get("prompt", "")
                    logger.debug(
                        f"已获取人格提示词（persona_manager方式），长度: {len(persona_prompt)} 字符"
                    )
            except Exception as e:
                logger.warning(f"获取人格设定失败: {e}，使用空人格")
                persona_prompt = ""

            # 构建完整的提示词，根据prompt_mode决定拼接还是覆盖
            if prompt_mode == "override" and extra_prompt and extra_prompt.strip():
                # 覆盖模式：直接使用用户自定义提示词
                full_prompt = formatted_message + "\n\n" + extra_prompt.strip()
                logger.debug("使用覆盖模式：用户自定义提示词完全替代默认系统提示词")
            else:
                # 拼接模式（默认）：使用默认提示词，如果有用户自定义则追加
                full_prompt = (
                    formatted_message + "\n\n" + DecisionAI.SYSTEM_DECISION_PROMPT
                )

                # 如果有用户自定义提示词,添加进去
                if extra_prompt and extra_prompt.strip():
                    full_prompt += f"\n\n用户补充说明:\n{extra_prompt.strip()}"
                    logger.debug("使用拼接模式：在默认系统提示词后追加用户自定义提示词")

            logger.debug(f"正在调用决策AI判断是否回复...")

            # 调用AI,添加超时控制
            async def call_decision_ai():
                response = await provider.text_chat(
                    prompt=full_prompt,
                    contexts=[],
                    image_urls=[],
                    func_tool=None,
                    system_prompt=persona_prompt,  # 包含人格设定
                )
                return response.completion_text

            # 使用用户配置的超时时间
            ai_response = await asyncio.wait_for(call_decision_ai(), timeout=timeout)

            # 解析AI的回复
            decision = DecisionAI._parse_decision(ai_response)

            if decision:
                logger.info("决策AI判断: 应该回复这条消息 (yes)")
            else:
                logger.info("决策AI判断: 不应该回复这条消息 (no)")

            return decision

        except asyncio.TimeoutError:
            logger.warning(
                f"决策AI调用超时（超过 {timeout} 秒），默认不回复，可在配置中调整 decision_ai_timeout 参数"
            )
            return False
        except Exception as e:
            logger.error(f"调用决策AI时发生错误: {e}")
            return False

    @staticmethod
    async def call_decision_ai(
        context: Context,
        event: AstrMessageEvent,
        prompt: str,
        provider_id: str = "",
        timeout: int = 30,
        prompt_mode: str = "append",
    ) -> str:
        """
        通用AI调用方法（供其他模块使用）

        Args:
            context: Context对象
            event: 消息事件
            prompt: 提示词内容
            provider_id: AI提供商ID，空=默认
            timeout: 超时时间（秒）
            prompt_mode: 提示词模式（暂未使用，保留以兼容调用）

        Returns:
            AI的回复文本，失败返回空字符串
        """
        try:
            # 获取AI提供商
            if provider_id:
                provider = context.get_provider_by_id(provider_id)
                if not provider:
                    logger.warning(f"无法找到提供商 {provider_id},使用默认提供商")
                    provider = context.get_using_provider()
            else:
                provider = context.get_using_provider()

            if not provider:
                logger.error("无法获取AI提供商")
                return ""

            # 获取人格设定
            try:
                if hasattr(context, "provider_manager") and hasattr(
                    context.provider_manager, "personas"
                ):
                    default_persona = None
                    if hasattr(context.provider_manager, "selected_default_persona"):
                        default_persona = (
                            context.provider_manager.selected_default_persona
                        )

                    if default_persona:
                        persona_prompt = default_persona.get("prompt", "")
                    else:
                        default_persona = (
                            await context.persona_manager.get_default_persona_v3(
                                event.unified_msg_origin
                            )
                        )
                        persona_prompt = default_persona.get("prompt", "")
                else:
                    default_persona = (
                        await context.persona_manager.get_default_persona_v3(
                            event.unified_msg_origin
                        )
                    )
                    persona_prompt = default_persona.get("prompt", "")
            except Exception as e:
                logger.warning(f"获取人格设定失败: {e}，使用空人格")
                persona_prompt = ""

            # 调用AI
            async def _call_ai():
                response = await provider.text_chat(
                    prompt=prompt,
                    contexts=[],
                    image_urls=[],
                    func_tool=None,
                    system_prompt=persona_prompt,
                )
                return response.completion_text

            # 使用超时控制
            ai_response = await asyncio.wait_for(_call_ai(), timeout=timeout)
            return ai_response or ""

        except asyncio.TimeoutError:
            logger.warning(f"AI调用超时（超过 {timeout} 秒）")
            return ""
        except Exception as e:
            logger.error(f"调用AI时发生错误: {e}")
            return ""

    @staticmethod
    def _parse_decision(ai_response: str) -> bool:
        """
        解析AI的决策回复（严格模式）

        严格解析AI的回复，避免误判

        Args:
            ai_response: AI的回复文本

        Returns:
            True=应该回复，False=不回复
        """
        if not ai_response:
            logger.debug("AI回复为空,默认判定为不回复（谨慎模式）")
            return False  # 空回复时谨慎处理

        # 清理回复文本
        cleaned_response = ai_response.strip().lower()

        # 移除可能的标点符号
        cleaned_response = cleaned_response.rstrip(".,!?。,!?")

        # 优先检查完整的yes/no
        if cleaned_response == "yes" or cleaned_response == "y":
            logger.debug(f"AI明确回复 '{ai_response}' (yes),判定为回复")
            return True

        if cleaned_response == "no" or cleaned_response == "n":
            logger.debug(f"AI明确回复 '{ai_response}' (no),判定为不回复")
            return False

        # 检查中文的明确回复
        if (
            cleaned_response == "是"
            or cleaned_response == "应该"
            or cleaned_response == "回复"
        ):
            logger.debug(f"AI明确回复 '{ai_response}' (肯定),判定为回复")
            return True

        if (
            cleaned_response == "否"
            or cleaned_response == "不"
            or cleaned_response == "不应该"
            or cleaned_response == "不回复"
        ):
            logger.debug(f"AI明确回复 '{ai_response}' (否定),判定为不回复")
            return False

        # 否定关键词列表（检查开头）
        negative_starts = ["no", "n", "否", "不", "别", "不要", "不应该", "不需要"]

        # 检查是否以否定词开头
        for keyword in negative_starts:
            if cleaned_response.startswith(keyword):
                logger.debug(
                    f"AI回复 '{ai_response}' 以否定词 '{keyword}' 开头,判定为不回复"
                )
                return False

        # 肯定关键词列表（检查开头）
        positive_starts = ["yes", "y", "是", "好", "可以", "应该", "回复", "要", "需要"]

        # 检查是否以肯定词开头
        for keyword in positive_starts:
            if cleaned_response.startswith(keyword):
                logger.debug(
                    f"AI回复 '{ai_response}' 以肯定词 '{keyword}' 开头,判定为回复"
                )
                return True

        # 默认情况：不明确的回复，采用谨慎策略
        logger.debug(f"AI回复 '{ai_response}' 不明确,默认判定为不回复（谨慎模式）")
        return False
