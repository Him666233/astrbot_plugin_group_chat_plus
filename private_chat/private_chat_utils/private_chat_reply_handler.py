"""
回复处理器模块
负责调用AI生成回复

作者: Him666233
版本: v1.2.1

v1.2.0 更新：
- 改用 event.request_llm() 替代 provider.text_chat()，支持其他插件的钩子注入
- 添加标记机制，让 main.py 的 on_llm_request 钩子能识别并处理上下文
"""

import asyncio
from datetime import datetime
from astrbot.api.all import *
from astrbot.api.event import AstrMessageEvent

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False
from astrbot.core.provider.entities import ProviderRequest

# 🆕 v1.2.0: 标记键名，用于标识请求来自本插件
PLUGIN_REQUEST_MARKER = "_group_chat_plus_request"
# 🆕 v1.2.0: 存储插件自定义上下文的键名
PLUGIN_CUSTOM_CONTEXTS = "_group_chat_plus_contexts"
# 🆕 v1.2.0: 存储插件自定义系统提示词的键名
PLUGIN_CUSTOM_SYSTEM_PROMPT = "_group_chat_plus_system_prompt"
# 🆕 v1.2.0: 存储插件自定义 prompt 的键名
PLUGIN_CUSTOM_PROMPT = "_group_chat_plus_prompt"
# 🆕 v1.2.0: 存储图片 URL 列表的键名
PLUGIN_IMAGE_URLS = "_group_chat_plus_image_urls"
# 🔧 存储插件自身的工具集（ToolSet），用于在 on_llm_request 钩子中恢复
PLUGIN_FUNC_TOOL = "_group_chat_plus_func_tool"
# 🔧 存储当前用户消息原文（短字符串），用于向量检索类插件（如 livingmemory）的记忆召回
PLUGIN_CURRENT_MESSAGE = "_group_chat_plus_current_message"


class ReplyHandler:
    """
    回复处理器

    主要功能：
    1. 构建回复提示词
    2. 调用AI生成回复
    3. 检测是否已被其他插件处理
    """

    # 系统回复提示词
    # 🔧 v1.2.0: 调整提示词位置引用（从"上方/上述"改为"下方"），配合缓存友好的拼接顺序
    SYSTEM_REPLY_PROMPT = """
请根据下方对话和背景信息生成自然的回复。

【第一重要】识别当前发送者：
⚠️ 下方【当前对话对象】已明确告诉你发送者是谁，记住这个人的名字和ID，不要搞错。
- 历史消息中有多个用户，不要把其他用户误认为当前发送者
- 称呼对方时用【当前对话对象】中的名字或"你"
- 只回复【当前对话对象】的消息，不要回复历史中其他人的问题

【上下文理解】：
- 消息已按时间顺序完整排列，包含：你回复过的、未回复的、以及他人对话
- 理解对话脉络：发送者在跟谁对话、话题如何演变、之前发生了什么
- 基于完整上下文自然回复，但仍只回复【当前对话对象】的当前消息
- 标有【📦近期未回复】的是你当时未回复的消息，仅供参考理解上下文
  * 当前消息有明确内容 → 优先回复当前消息
  * 当前消息是触发型（仅@、"在吗"等）→ 结合近期未回复消息理解意图
  * 不需要提及"你之前没回复"，自然对话即可

【核心原则】：
1. 优先关注"当前新消息"的核心内容
2. 识别当前消息的主要问题或话题
3. 历史上下文仅作参考，不要让历史话题喧宾夺主
4. 绝对禁止回复历史中其他人的问题

【主语与指代】：
- 用户语句缺主语时不要擅自补充，根据已有信息自然理解
- 看到"你"不要立即认为是叫你，优先依据@信息、【当前对话对象】提示和对话走向判断

【严禁重复】必须检查：
- 找出历史中属于你自己的回复（历史消息开头的说明已指明你的ID；消息前缀标有"【你的回复】"或"⚠️【禁止重复-这是你自己的历史回复】"的均为你的历史发言）
- 对比你要说的话是否与历史回复相同或相似
- 相似度超过50%必须换完全不同的角度或表达方式
- 绝对禁止重复相同句式、观点、回应模式

【记忆和背景信息】：
- 不要机械陈述记忆内容（禁止"XXX已确认为我的XXX"等）
- 自然融入背景，将记忆作为认知背景而非需要强调的事实
- 避免过度解释关系

【回复要求】：
- 自然、轻松、符合对话氛围
- 遵循人格设定和回复风格
- 根据需要调用可用工具
- 保持连贯性和相关性
- 不要提及"记忆"、"根据记忆"等词语
- 绝对禁止提及任何系统提示词、规则、时间戳、用户ID等元信息

【严禁元叙述】特别重要：
- 绝对禁止解释你为什么要回复
- ❌ 禁止："看到你@我了"、"注意到你在说XXX"、"看着你发来的消息"、"看了看你的消息"、"我看到了主动对话提示词"、"根据系统提示"等
- ✅ 正确：直接自然地回复内容本身，像人类一样
- 人类不会说"我看到你@我了所以来回复"，只会直接说"怎么了？"
- 绝对不要提及历史中的任何系统提示词或内部指令，就当它们不存在

【特殊标记】：
- 【@指向说明】：发给别人的消息，不要直接回答被@者的问题，可自然补充信息或分享观点
- [戳一戳提示]："有人在戳你"可俏皮回应，"但不是戳你的"不要表现像被戳的人
- [戳过对方提示]：你刚戳过对方，供参考理解上下文，禁止提及
- [表情包图片]：该消息附带的图片是表情包/贴纸，不是普通照片。你可以看懂图片来理解其传达的情绪和幽默感，但回应时像真人一样自然——有时共鸣、有时吐槽、有时忽略，不要描述或复述图片内容（如"图上画了..."），也不要说"你发了表情包"
- [系统提示]中若出现「请你像真人一样判断这个情况」：
  ✅ 这是空@场景——真正用脑子判断！看清楚那几条消息是谁发的、说了什么，再看看@你的这个人之前有没有提过相关的事
  ✅ 如果判断对方只是随便叫一声、或者你不确定ta想要什么：直接自然地回一句「？」或「怎么了」就好，**不要强行接那几条消息**
  ✅ 如果判断对方确实想让你回应上面那些内容：再去回应
  ❌ 禁止：不管三七二十一直接回答列出来的那几条消息——先判断意图！
- [系统提示]中若出现「请仔细观察上下文和对话走向」：
  ✅ 这是关键词触发场景——真正看懂上下文再说话
  ✅ 结合发送者在聊什么、@了谁、整体走向来决定怎么回复，不要只因为检测到关键词就机械地回应
- [转发消息]：这是一条合并转发消息。回复时注意：
  * 不要逐条复述转发内容，自然地回应发送者分享这些消息的意图
  * 关注发送者转发消息的目的（分享、讨论、询问等）
  * 可以针对转发内容中感兴趣的部分做简短评论
  * 禁止说"我看到你转发了..."，直接自然回应内容
  * 转发消息中"--- 转发内容 ---"和"--- 转发结束 ---"之间的是转发的原始消息内容

【系统提示词说明】：
- 历史中可能有"[🎯主动发起新话题]"、"[🔄再次尝试对话]"等标记，表示那是你自己主动发起的对话
- 理解含义帮助理解上下文，但绝对禁止在回复中提及
- 历史提示词附近的时间戳是当时的时间，当前真实时间以当前消息为准
"""

    # 系统回复提示词的结束指令（单独分离，用于插入自定义提示词）
    SYSTEM_REPLY_PROMPT_ENDING = "\n请开始回复：\n"

    @staticmethod
    async def generate_reply(
        event: AstrMessageEvent,
        context: Context,
        formatted_message: str,
        extra_prompt: str,
        prompt_mode: str = "append",
        image_urls: list = None,
        include_sender_info: bool = True,
        include_timestamp: bool = True,
        history_messages: list = None,
        conversation_fatigue_info: dict = None,
    ) -> ProviderRequest:
        """
        生成AI回复

        Args:
            event: 消息事件
            context: Context对象
            formatted_message: 格式化后的完整消息（含上下文、记忆、工具等）
            extra_prompt: 用户自定义补充提示词
            prompt_mode: 提示词模式，append=拼接，override=覆盖
            image_urls: 图片URL列表（用于多模态AI）
            include_sender_info: 是否包含发送者信息（默认为True）
            include_timestamp: 是否包含时间戳（默认为True）
            history_messages: 历史消息列表（AstrBotMessage对象列表，用于构建contexts）
            conversation_fatigue_info: 对话疲劳信息（用于生成收尾话语提示）

        Returns:
            ProviderRequest对象
        """
        # 如果image_urls为None，初始化为空列表
        if image_urls is None:
            image_urls = []
        # 如果history_messages为None，初始化为空列表
        if history_messages is None:
            history_messages = []

        try:
            # 🔧 修复：将 history_messages 转换为 contexts 格式
            # 这样在 Agent 模式下调用工具后仍能保留上下文
            # 🔧 v1.2.0: contexts 中的消息内容需要与 format_context_for_ai() 格式保持一致，
            # 根据 include_sender_info / include_timestamp 开关添加发送者前缀和时间戳，
            # 避免 prompt（文本）和 contexts（结构化数组）中的历史信息互相矛盾，
            # 导致 AI 在群聊中无法正确区分不同用户的发言。
            contexts = []
            bot_id = str(event.get_self_id())

            for msg in history_messages:
                try:
                    # 提取消息内容
                    content = ""
                    if hasattr(msg, "message_str"):
                        content = msg.message_str or ""

                    # 跳过空消息
                    if not content or not content.strip():
                        continue

                    # 判断角色：如果是机器人自己发送的消息，role = assistant；否则 role = user
                    role = "user"
                    sender_name = ""
                    sender_id = ""
                    if hasattr(msg, "sender") and msg.sender:
                        sender_id = str(getattr(msg.sender, "user_id", ""))
                        sender_name = getattr(msg.sender, "nickname", "") or ""
                        if sender_id and sender_id == bot_id:
                            role = "assistant"

                    # 🔧 v1.2.0: 为 user 角色的消息添加发送者前缀，
                    # 与 format_context_for_ai() 保持一致的格式，
                    # 确保 AI 能在 contexts 中区分不同用户的发言
                    if role == "user" and include_sender_info:
                        if sender_name:
                            content = f"{sender_name}(ID:{sender_id}): {content}"
                        elif sender_id:
                            content = f"用户(ID:{sender_id}): {content}"

                    # 🔧 v1.2.0: 添加时间戳前缀（如果启用），
                    # 与 format_context_for_ai() 的时间戳格式保持一致
                    if (
                        include_timestamp
                        and hasattr(msg, "timestamp")
                        and msg.timestamp
                    ):
                        try:
                            dt = datetime.fromtimestamp(msg.timestamp)
                            weekday_names = [
                                "周一",
                                "周二",
                                "周三",
                                "周四",
                                "周五",
                                "周六",
                                "周日",
                            ]
                            weekday = weekday_names[dt.weekday()]
                            time_str = dt.strftime(f"%Y-%m-%d {weekday} %H:%M:%S")
                            content = f"[{time_str}] {content}"
                        except Exception:
                            pass

                    contexts.append({"role": role, "content": content})

                except Exception as e:
                    if DEBUG_MODE:
                        logger.warning(f"转换历史消息到contexts失败: {e}")
                    continue

            if DEBUG_MODE and contexts:
                logger.info(
                    f"🔧 [修复] 已将 {len(contexts)} 条历史消息转换为contexts格式"
                )

        except Exception as e:
            logger.error(f"构建contexts时发生错误: {e}")
            contexts = []

        try:
            # 🆕 提取当前发送者信息，用于强化识别（仅在开启 include_sender_info 时添加）
            sender_emphasis = ""
            sender_id = event.get_sender_id()
            sender_name = event.get_sender_name()
            if include_sender_info:
                separator = "=" * 60
                if sender_name:
                    sender_emphasis = (
                        f"\n\n{separator}\n"
                        f"⚠️ 【当前对话对象】重要提醒 ⚠️\n"
                        f"{separator}\n"
                        f"当前给你发消息的人是：{sender_name}（用户ID：{sender_id}）\n\n"
                        f"请特别注意：\n"
                        f"- 当前和你对话的人是 {sender_name}（ID:{sender_id}），不是其他人\n"
                        f"- 历史消息中可能有多个用户的发言，请不要混淆\n"
                        f"- 无论历史中有谁说过什么，当前对话的对象是 {sender_name}\n"
                        f'- 称呼对方时，可以直接用"{sender_name}"或"你"，不要叫错人\n'
                        f"{separator}\n"
                    )
                else:
                    sender_emphasis = (
                        f"\n\n{separator}\n"
                        f"⚠️ 【当前对话对象】重要提醒 ⚠️\n"
                        f"{separator}\n"
                        f"当前给你发消息的人的用户ID是：{sender_id}\n\n"
                        f"请特别注意：\n"
                        f"- 当前和你对话的人是用户（ID:{sender_id}），不是其他人\n"
                        f"- 历史消息中可能有多个用户的发言，请不要混淆\n"
                        f"- 无论历史中有谁说过什么，当前对话的对象是当前发送者（ID:{sender_id}）\n"
                        f"{separator}\n"
                    )

            # 🆕 v1.2.0: 构建对话疲劳收尾提示（当启用疲劳机制且需要收尾时）
            fatigue_closing_prompt = ""
            if conversation_fatigue_info and conversation_fatigue_info.get(
                "should_add_closing_hint", False
            ):
                fatigue_level = conversation_fatigue_info.get("fatigue_level", "none")
                consecutive_replies = conversation_fatigue_info.get(
                    "consecutive_replies", 0
                )
                separator = "=" * 60

                if fatigue_level == "heavy":
                    fatigue_closing_prompt = (
                        f"\n\n{separator}\n"
                        f"🔄 【对话收尾提示】\n"
                        f"{separator}\n"
                        f"⚠️ 你已经与这个用户连续对话了 {consecutive_replies} 轮，是时候自然地结束对话了。\n\n"
                        f"请在回复中自然地表达收尾意愿，例如：\n"
                        f"- '好了，我先去忙了~'\n"
                        f"- '行，那先这样吧'\n"
                        f"- '嗯嗯，有空再聊~'\n"
                        f"- '好的，我去做点别的事了'\n\n"
                        f"⚠️ 重要：\n"
                        f"- 收尾话语要自然，符合你的人格设定\n"
                        f"- 不要生硬地说'我要结束对话了'\n"
                        f"- 可以结合当前话题自然过渡\n"
                        f"- 绝对禁止提及'疲劳'、'连续对话'、'系统提示'等元信息\n"
                        f"{separator}\n"
                    )
                elif fatigue_level == "medium":
                    fatigue_closing_prompt = (
                        f"\n\n{separator}\n"
                        f"🔄 【对话收尾提示】\n"
                        f"{separator}\n"
                        f"ℹ️ 你与这个用户已经连续对话了 {consecutive_replies} 轮，可以考虑适当收尾。\n\n"
                        f"如果话题已经聊得差不多了，可以自然地表达收尾意愿，例如：\n"
                        f"- '嗯嗯，差不多就这样~'\n"
                        f"- '好的好的'\n"
                        f"- '行吧，有空再聊'\n\n"
                        f"⚠️ 注意：这只是建议，如果话题还有延续性，可以继续正常回复。\n"
                        f"绝对禁止提及'疲劳'、'连续对话'、'系统提示'等元信息。\n"
                        f"{separator}\n"
                    )

            # 🔧 v1.2.0: 缓存友好的提示词拼接顺序
            # 将静态内容（系统回复提示词、用户额外提示词）放在最前面，
            # 动态内容（对话上下文、发送者信息、疲劳提示）放在后面。
            # 这样AI服务商的前缀缓存（prefix caching）可以命中静态部分，降低调用成本。
            if prompt_mode == "override" and extra_prompt and extra_prompt.strip():
                # 覆盖模式：用户自定义提示词在前（静态），动态内容在后
                full_prompt = (
                    extra_prompt.strip()
                    + "\n\n"
                    + formatted_message
                    + sender_emphasis
                    + fatigue_closing_prompt
                )
                if DEBUG_MODE:
                    logger.info(
                        "使用覆盖模式：用户自定义提示词完全替代默认系统提示词（缓存友好顺序）"
                    )
            else:
                # 拼接模式（默认）：系统提示词（静态）在前，动态内容在后
                full_prompt = ReplyHandler.SYSTEM_REPLY_PROMPT

                # 如果有用户自定义提示词,紧跟在系统提示词后面（也是相对静态的）
                if extra_prompt and extra_prompt.strip():
                    full_prompt += f"\n\n用户补充说明:\n{extra_prompt.strip()}\n"
                    if DEBUG_MODE:
                        logger.info(
                            "使用拼接模式：用户自定义提示词紧跟系统提示词（缓存友好顺序）"
                        )

                # 添加结束指令（静态）
                full_prompt += ReplyHandler.SYSTEM_REPLY_PROMPT_ENDING

                # 动态内容放在最后
                full_prompt += (
                    "\n" + formatted_message + sender_emphasis + fatigue_closing_prompt
                )

            logger.info(
                f"正在调用AI生成回复（当前发送者：{sender_name or '未知'}，ID:{sender_id}）..."
            )

            # 获取工具管理器并保存为 ToolSet（兼容新旧版本 AstrBot）
            func_tools_mgr = context.get_llm_tool_manager()
            plugin_tool_set = None
            try:
                plugin_tool_set = func_tools_mgr.get_full_tool_set()
                # 过滤未激活的工具（与平台 _ensure_persona_and_skills 行为一致）
                for tool in list(plugin_tool_set.tools):
                    if hasattr(tool, "active") and not tool.active:
                        plugin_tool_set.remove_tool(tool.name)
            except Exception:
                pass

            # 🔧 修复：直接使用 persona_manager 获取最新人格配置，支持多会话和实时更新
            system_prompt = ""
            begin_dialogs_text = ""
            try:
                # 直接调用 get_default_persona_v3() 获取最新人格配置
                # 这样可以确保：1. 每次都获取最新配置 2. 支持不同会话使用不同人格
                default_persona = await context.persona_manager.get_default_persona_v3(
                    event.unified_msg_origin
                )

                system_prompt = default_persona.get("prompt", "")

                # 获取begin_dialogs并转换为文本（而不是放在contexts中）
                begin_dialogs = default_persona.get("_begin_dialogs_processed", [])
                if begin_dialogs:
                    # 将begin_dialogs转换为文本格式，并入prompt
                    dialog_parts = []
                    for dialog in begin_dialogs:
                        role = dialog.get("role", "user")
                        content = dialog.get("content", "")
                        if role == "user":
                            dialog_parts.append(f"用户: {content}")
                        elif role == "assistant":
                            dialog_parts.append(f"AI: {content}")
                    if dialog_parts:
                        begin_dialogs_text = (
                            "\n=== 预设对话 ===\n" + "\n".join(dialog_parts) + "\n\n"
                        )

                if DEBUG_MODE:
                    logger.info(
                        f"✅ 已获取当前人格配置（persona_manager），人格名: {default_persona.get('name', 'default')}, 长度: {len(system_prompt)} 字符"
                    )
                    if begin_dialogs_text:
                        logger.info(
                            f"已获取begin_dialogs并转换为文本，长度: {len(begin_dialogs_text)} 字符"
                        )
            except Exception as e:
                logger.warning(f"获取人格设定失败: {e}，使用空人格")

            # 如果有begin_dialogs，将其添加到prompt开头
            if begin_dialogs_text:
                full_prompt = begin_dialogs_text + full_prompt

            # 🆕 v1.2.0: 改用 event.request_llm() 替代 provider.text_chat()
            # 这样可以让其他插件（如 emotionai）的 on_llm_request 钩子生效
            # 同时通过 event.set_extra() 传递标记，让 main.py 的钩子能识别并处理上下文冲突
            if image_urls:
                if DEBUG_MODE:
                    logger.info(f"🟢 [多模态AI] 传递 {len(image_urls)} 张图片给LLM")
                    if logger.level <= 10:  # DEBUG级别
                        for i, url in enumerate(image_urls):
                            logger.info(f"  图片 {i}: {url}")

            # 🔧 修复：防止 contexts 末尾出现连续 "user" 角色消息导致部分 LLM 返回空响应
            # 问题根因：新版 AstrBot (>=4.14) 的 ToolLoopAgentRunner 会将 contexts 列表的每条消息
            #           追加到消息列表，然后再把 prompt 作为额外的 "user" 消息追加在末尾。
            #           若 contexts 最后一条也是 "user" 消息，则形成连续的两条 user 消息。
            #           部分 LLM（尤其是某些国产模型）遇到连续 user 消息时会直接返回空响应，
            #           导致 "LLM returned empty assistant message with no tool calls" 警告。
            # 解决方案：移除 contexts 末尾所有连续的 "user" 消息。
            #           这些消息的内容已包含在 full_prompt（格式化历史文本）中，不会丢失任何信息。
            # 兼容性：旧版 AstrBot 中 contexts 通常为空列表，此修改无影响。
            while contexts and contexts[-1].get("role") == "user":
                contexts.pop()

            # 🆕 v1.2.0: 设置标记，让 main.py 的 on_llm_request 钩子能识别这是来自本插件的请求
            event.set_extra(PLUGIN_REQUEST_MARKER, True)
            # 存储插件自定义的上下文（用于替换平台 LTM 注入的上下文）
            event.set_extra(PLUGIN_CUSTOM_CONTEXTS, contexts)
            # 存储插件自定义的系统提示词
            event.set_extra(PLUGIN_CUSTOM_SYSTEM_PROMPT, system_prompt)
            # 存储插件自定义的完整 prompt（含历史上下文），供 on_llm_request 钩子恢复使用
            event.set_extra(PLUGIN_CUSTOM_PROMPT, full_prompt)
            # 存储图片 URL 列表
            event.set_extra(PLUGIN_IMAGE_URLS, image_urls)
            # 🔧 存储插件自身的工具集（ToolSet），用于在 on_llm_request 钩子中恢复
            # 新版 AstrBot 的 build_main_agent 会注入框架工具（shell/cron等），需要用插件的工具集替换
            event.set_extra(PLUGIN_FUNC_TOOL, plugin_tool_set)

            # 🔧 提取当前用户消息原文（不含历史上下文），作为向量检索类插件的召回查询词
            current_message_for_retrieval = event.get_message_str() or ""
            event.set_extra(PLUGIN_CURRENT_MESSAGE, current_message_for_retrieval)

            if DEBUG_MODE:
                logger.info(
                    f"🔧 [兼容模式] 已设置插件标记，将通过 event.request_llm() 调用 AI"
                )
                logger.info(f"  - contexts 数量: {len(contexts)}")
                logger.info(f"  - system_prompt 长度: {len(system_prompt)}")
                logger.info(f"  - full_prompt 长度: {len(full_prompt)}")
                logger.info(f"  - image_urls 数量: {len(image_urls)}")
                logger.info(
                    f"  - 向量检索用短消息长度: {len(current_message_for_retrieval)}"
                )

            # 🆕 v1.2.0: 使用 event.request_llm() 发起请求
            # 这会触发平台的 on_llm_request 钩子，让其他插件能注入提示词
            # main.py 的 on_llm_request 钩子（priority=-1）会检测标记并把 req.prompt 换回完整 full_prompt
            # 🔧 兼容说明：func_tool_manager 在旧版 AstrBot (<=4.13) 中生效，
            # 在新版 (>=4.14) 中被静默忽略。保留此参数以确保旧版兼容。
            # 新版的工具注入问题由 on_llm_request 钩子中恢复 plugin_tool_set 来解决。
            return event.request_llm(
                prompt=current_message_for_retrieval,
                func_tool_manager=func_tools_mgr,
                session_id=event.session_id,
                image_urls=image_urls,
                contexts=contexts,
                system_prompt=system_prompt,
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

            if result is None:
                return False

            # AstrBot 会将字符串结果转换为 MessageEventResult
            if isinstance(result, MessageEventResult):
                has_stream = bool(getattr(result, "async_stream", None))
                has_chain = bool(getattr(result, "chain", []) or [])
                is_llm = bool(
                    getattr(result, "is_llm_result", None) and result.is_llm_result()
                )
                is_stopped = bool(
                    getattr(result, "result_type", None) == EventResultType.STOP
                )
                is_stream_state = bool(
                    getattr(result, "result_content_type", None)
                    in {
                        ResultContentType.STREAMING_RESULT,
                        ResultContentType.STREAMING_FINISH,
                    }
                )

                if has_stream or has_chain or is_llm or is_stopped or is_stream_state:
                    logger.info("检测到该消息已经被其他插件处理")
                    return True

                return False

            # 未知类型的结果，保持向后兼容：只要非空视为已处理
            if result:
                logger.info("检测到该消息已经被其他插件处理")
                return True

            return False

        except Exception as e:
            logger.error(f"检查消息是否已回复时发生错误: {e}")
            # 发生错误时,为安全起见,返回True避免重复回复
            return True
