"""
消息清理器模块
负责清理消息中的系统提示词，只保留原始用户消息

v1.0.4 更新：
- 添加对发送者识别系统提示的清理规则
- 在保存到官方历史时过滤掉系统提示

v1.1.0 更新：
- 🆕 增加主动对话提示词的特殊处理
- 主动对话的系统提示词会保留到官方历史（让AI理解上下文）
- 使用特殊标记 [PROACTIVE_CHAT] 标识主动对话消息

v1.1.2 更新：
- 🔧 增强清理规则，添加更多系统提示词的检测模式
- 新增清理：情绪状态、背景信息、记忆列表、工具列表、对话对象提醒等
- 修复：系统提示词在保存时未被完全清除的问题
- 新增规则：核心原则、严禁重复、元叙述、用户补充说明等大段提示词

v1.2.0 更新：
- 🆕 新增拟人增强模式历史决策记录的过滤规则
- 新增清理：历史判断记录、兴趣话题检测提示等

v1.2.1 更新：
- 🆕 适配人格中立化改造的新格式 [系统信息-xxx] / [系统指令-xxx] / [系统提示-xxx] 标记
- 新增清理：发送者识别、对话对象、疲劳收尾、元指令声明、时间活跃度、关键词触发、兴趣话题、对话疲劳、主动对话上下文、历史上下文识别等新格式标记
- 🆕 适配新版历史标记格式：【禁止重复-你的历史回复】前缀、历史分隔线、追加消息身份提醒
- 新增清理：新版当前消息分隔线（含"以上全部是历史消息"提示）、回复密度提示


作者: Him666233
版本: v1.2.1
"""

import re
from astrbot.api.all import *
from astrbot.api.message_components import Plain, At, Image, Reply
from astrbot.core.message.components import Forward

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class MessageCleaner:
    """
    消息清理器

    主要功能：
    1. 移除系统自动添加的@消息提示词
    2. 移除决策AI相关的提示词
    3. 只保留原始用户消息内容
    4. 🆕 v1.1.0: 特殊处理主动对话提示词（保留到历史）
    """

    # 🆕 v1.1.0: 主动对话标记
    # 用于标识AI主动发起的对话，这个标记和相关提示词会保留到官方历史
    PROACTIVE_CHAT_MARKER = "[PROACTIVE_CHAT]"

    # 🆕 v1.1.0: 主动对话系统提示词的特征模式
    # 这些提示词会被保留到官方历史，让AI理解自己是主动发起的
    PROACTIVE_CHAT_PROMPT_PATTERNS = [
        r"\[🎯主动发起新话题\]",  # 🆕 v1.1.2: 首次主动对话标记
        r"\[🔄再次尝试对话\]",  # 🆕 v1.1.2: 重试场景标记
        r"\[系统提示 - 主动发起新话题场景\]",
        r"你刚刚主动发起了一个新话题",
        r"这是你主动发起的对话",
    ]

    # @消息提示词的特征模式（用于识别和移除）
    AT_MESSAGE_PROMPT_PATTERNS = [
        r"注意，你正在社交媒体上.*?不要输出其他任何东西",
        r"\[当前时间:.*?\][\s\S]*?不要输出其他任何东西",
        r"用户只是通过@来唤醒你.*?不要输出其他任何东西",
        r"你友好地询问用户想要聊些什么.*?不要输出其他任何东西",
        # 新增：更通用的系统提示词模式
        r"\[当前时间:\d{4}-\d{2}-\d{2}\s+周[一二三四五六日]\s+\d{2}:\d{2}:\d{2}\]",
        r"\[User ID:.*?Nickname:.*?\]",
        r"\[当前情绪状态:.*?\]",  # 🆕 情绪状态提示（旧格式）
        r"\[系统信息-情绪参考:.*?\]",  # 🆕 情绪状态提示（新格式）
        # 🆕 v1.3.0: 人格中立化改造 - 新格式 [系统信息-xxx] 标记
        r"\[系统信息-当前发送者\][^\n]*\n注意：[^\n]*\n",  # 发送者识别（决策AI），含两行注意
        r"\[系统信息-当前对话对象\][^\n]*\n注意：[^\n]*\n",  # 对话对象识别（回复AI），含两行注意
        r"\[系统提示-对话收尾\][\s\S]*?(?=\n\n|$)",  # 疲劳收尾提示
        r"\[以下是系统行为指令[^\]]*\]",  # 元指令声明
        r"注意，你正在社交媒体上中与用户进行聊天.*",
        r"用户只是通过@来唤醒你，但并未在这条消息中输入内容.*",
        r"回复要符合人设，不要太过机械化.*",
        r"你仅需要输出要回复用户的内容.*",
        # 🆕 v1.0.4: 发送者识别系统提示词（用于保存到官方历史时过滤）
        # 注意：使用 \s* 匹配任意数量的空白符，\[ \] 转义方括号
        r"\s*\[系统提示\]注意,现在有人在直接@你并且给你发送了这条消息，@你的那个人是.*",
        r"\s*\[系统提示\]注意，现在有人在直接@你并且给你发送了这条消息，@你的那个人是.*",
        r"\s*\[系统提示\]注意，你刚刚发现这条消息里面包含和你有关的信息，这条消息的发送者是.*",
        r"\s*\[系统提示\]注意，你看到了这条消息，发送这条消息的人是.*",
        # 🆕 v1.0.9: 戳一戳提示词过滤规则（用于保存到官方历史时过滤）
        r"\s*\[戳一戳提示\]有人在戳你，戳你的人是.*",
        r"\s*\[戳一戳提示\]这是一个戳一戳消息，但不是戳你的，是.*在戳.*",
        # 🆕 v1.1.1: 戳过对方提示（AI刚刚主动戳过对方，供AI参考，不应保存）
        r"\s*\[戳过对方提示\]你刚刚戳过这条消息的发送者.*",
        # 🆕 空@时嵌入的多行提示词（有缓存摘要版和无缓存版）
        # 注意：必须在通用单行[系统提示]规则之前，否则头部被先删掉导致多行规则失效
        r"\[系统提示\][^\n]+单独@了你，没有附带任何文字内容。\n以下是@你之前[\s\S]*?用你自己的方式回应就好。",
        r"\[系统提示\][^\n]+单独@了你，没有附带任何消息内容，也没有特别需要接上的近期上下文，自然回应就好。",
        r"\[系统提示\][^\n]+单独@了你，没有附带任何消息内容，可能只是叫你出来，也可能是有事想说——自然回应就好。",
        # 🔧 修复：兜底规则——当通用单行规则先删掉[系统提示]首行后，多行残留内容（缓存摘要+结尾说明）仍会留下
        # 此规则专门清除这部分残留内容，确保不会被保存到历史
        r"以下是@你之前群里出现的最近几条消息（可能来自不同的人）：[\s\S]*?用你自己的方式回应就好。",
        # 关键词触发多行提示词（包含上下文观察指引）
        r"\[系统提示\]注意，你刚刚发现这条消息里面包含和你有关的信息[\s\S]*?机械回应。",
        # 🔧 修复：添加更强的模式匹配，确保所有[]和【】括起来的系统提示都被过滤
        r"\n+\s*\[系统提示\][^\n]*",  # 匹配所有[系统提示]开头的内容
        r"\n+\s*\[戳一戳提示\][^\n]*",  # 匹配所有[戳一戳提示]开头的内容
        r"\n+\s*\[戳过对方提示\][^\n]*",  # 匹配所有[戳过对方提示]开头的内容
        # 🆕 v1.1.3: 人格提示词过滤规则
        r"【当前人格设定】[\s\S]*?(?=\n\[当前时间:|\n\[User ID:|$)",  # 人格设定整块
    ]

    # 决策AI提示词的特征模式
    DECISION_AI_PROMPT_PATTERNS = [
        r"=== 历史消息上下文 ===",
        r"=+ 【重要】当前新消息.*?=+",
        r"=== 当前新消息 ===",
        r"请根据历史消息.*?请开始回复",
        r"你是一个活跃、友好的群聊参与者.*?请开始判断",
        r"核心原则（重要！）：[\s\S]*?请开始回复",
        r"核心原则（重要！）：[\s\S]*?请开始判断",
        # 🆕 添加更多大段系统提示词模式
        r"=== 背景信息 ===[\s\S]*?(?=\n\n|$)",  # 背景信息部分（包含记忆）
        r"💭 相关记忆：[\s\S]*?(?=\n\n|$)",  # 记忆列表
        r"=== 可用工具列表 ===[\s\S]*?(?=请根据上述对话|请开始回复|$)",  # 工具列表
        r"当前平台共有 \d+ 个可用工具:[\s\S]*?(?=请根据上述对话|请开始回复|$)",  # 工具详细信息
        r"============================================================\n*⚠️ 【当前对话对象】重要提醒 ⚠️[\s\S]*?============================================================",  # 对话对象提醒
        r"当前和你对话的人是.*?(?=\n|$)",  # 修改后的对话对象识别（中性表述）
        r"当前对话的对象是.*?(?=\n|$)",  # 修改后的对话对象识别（中性表述）
        r"【第一重要】识别当前发送者：[\s\S]*?(?=请开始回复|$)",  # 发送者识别说明
        r"特殊标记说明：[\s\S]*?(?=请开始回复|$)",  # 特殊标记说明
        r"⚠️ \*\*【关于历史中的系统提示词】重要说明\*\* ⚠️：[\s\S]*?(?=请开始回复|$)",  # 历史提示词说明
        r"核心原则（重要！）：[\s\S]*?(?=请开始回复|$)",  # 核心原则说明
        r"⚠️ \*\*【严禁重复】必须执行的检查步骤\*\* ⚠️：[\s\S]*?(?=请开始回复|$)",  # 严禁重复说明
        r"关于记忆和背景信息的使用：[\s\S]*?(?=请开始回复|$)",  # 记忆使用说明
        r"回复要求：[\s\S]*?(?=请开始回复|$)",  # 回复要求
        r"⛔ \*\*【严禁元叙述】特别重要！\*\* ⛔：[\s\S]*?(?=请开始回复|$)",  # 严禁元叙述
        r"关于【@指向说明】标记的消息：[\s\S]*?(?=请开始回复|$)",  # @指向说明
        r"用户补充说明:[\s\S]*?(?=请开始回复|$)",  # 用户补充说明
        r"请开始回复：\s*$",  # 最后的请开始回复
        r"当前给你发消息的人是：.*?\n",  # 当前发送者提示
        r"请特别注意：[\s\S]*?(?=\n\n|请根据上述对话|请开始回复|$)",  # 特别注意部分
        r"... 还有 \d+ 条记忆",  # 记忆条数提示
        r"\(这些信息可能对理解当前对话有帮助[\s\S]*?\)",  # 记忆使用提示
        r"\(以上是你可以调用的所有工具[\s\S]*?\)",  # 工具说明提示
        # 🆕 v1.2.0: 拟人增强模式 - 历史决策记录提示词
        r"\n*=+\n*📋 【你之前的判断记录】[\s\S]*?=+\n*",  # 历史决策记录完整块
        r"提示：保持判断的一致性，如果话题没有变化或没有新的互动需求，[\s\S]*?避免过于频繁地打扰对话。",  # 历史决策提示
        r"\d{2}:\d{2}:\d{2}: [✅❌][^\n]+",  # 单条决策记录（时间戳: 决策 - 原因）
        r"【步骤9】🎭 拟人增强[\s\S]*?(?=\n|$)",  # 拟人增强日志（不应出现在消息中，但以防万一）
        r"🎭 检测到兴趣话题[\s\S]*?(?=\n|$)",  # 兴趣话题检测提示
        r"🎭 已注入历史决策记录到提示词",  # 历史决策注入日志
        # 🆕 v1.2.0: 对话疲劳相关提示词
        r"\n*=+\n*🔄 【对话疲劳提示】[\s\S]*?=+\n*",  # 决策AI的疲劳提示
        r"\n*=+\n*🔄 【对话收尾提示】[\s\S]*?=+\n*",  # 回复AI的收尾提示
        r"与当前用户的连续对话轮次:[\s\S]*?(?=\n\n|$)",  # 疲劳轮次信息
        r"你已经与这个用户连续对话了 \d+ 轮[\s\S]*?(?=\n\n|$)",  # 收尾提示内容
        # 🆕 v1.3.0: 人格中立化改造 - 新格式 [系统信息-xxx] 标记
        r"\[系统信息-时间与活跃度\][\s\S]*?(?=\n\n|$)",
        r"\[系统信息-关键词触发\][\s\S]*?(?=\n\n|$)",
        r"\[系统信息-兴趣话题\][\s\S]*?(?=\n\n|$)",
        r"\[系统信息-对话疲劳\][\s\S]*?(?=\n\n|$)",
        r"\[系统信息-主动对话上下文\][\s\S]*?(?=\n\n|$)",
        r"\[系统指令-历史上下文识别\][\s\S]*?(?=请开始|$)",
        r"你是一个群聊参与者，请严格按照你的人格设定[\s\S]*?请开始判断",  # 新版决策AI开头
        # 🆕 窗口缓冲消息区域（追加消息提示词，保存时需过滤）
        r"--- 以下是你收到这条消息后，同一用户或其他用户紧接着又发的消息 ---[\s\S]*?--- 以上为紧接着的追加消息 ---",
        r"这些消息不一定是对你说的，请自行参考判断是否需要在回复中一并考虑。",
        r"重要：这些追加消息的发送者可能与当前对话对象不同，请根据每条消息的发送者名字和ID仔细区分。",
        # 🆕 v1.2.1: 新版历史标记和分隔线
        r"【禁止重复-你的历史回复】",  # 新版 bot 历史回复前缀标记
        r"=== 以上全部是历史消息，你已经处理过了，不要重复回答 ===",  # 新版历史分隔提示
        r"=== 【重要】以下是当前新消息（请优先关注这条消息的核心内容）===",  # 新版当前消息分隔线
        r"\[系统信息-回复密度\][\s\S]*?(?=\n\n|$)",  # 回复密度提示
    ]

    @staticmethod
    def clean_message(message_text: str) -> str:
        """
        清理消息，移除系统添加的提示词

        ⚠️ 注意：此方法会移除所有系统提示词，包括主动对话的提示词
        如果需要保留主动对话提示词，请使用 clean_message_preserve_proactive

        Args:
            message_text: 原始消息（可能包含提示词）

        Returns:
            清理后的消息（只包含用户真实发送的内容）
        """
        if not message_text:
            return message_text

        cleaned = message_text

        # 移除@消息提示词
        for pattern in MessageCleaner.AT_MESSAGE_PROMPT_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

        # 移除决策AI提示词
        for pattern in MessageCleaner.DECISION_AI_PROMPT_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

        # 清理多余的分隔符（=====）
        cleaned = re.sub(r"\n*=+\n*", "\n", cleaned)

        # 清理多余的空白行
        cleaned = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned)

        # 去除首尾空白
        cleaned = cleaned.strip()

        return cleaned

    @staticmethod
    def is_proactive_chat_message(message_text: str) -> bool:
        """
        🆕 v1.1.0: 检测消息是否为主动对话消息

        Args:
            message_text: 消息文本

        Returns:
            True=主动对话消息, False=普通消息
        """
        if not message_text:
            return False

        # 检查是否包含主动对话标记
        if MessageCleaner.PROACTIVE_CHAT_MARKER in message_text:
            return True

        # 检查是否包含主动对话提示词特征
        for pattern in MessageCleaner.PROACTIVE_CHAT_PROMPT_PATTERNS:
            if re.search(pattern, message_text):
                return True

        return False

    @staticmethod
    def clean_message_preserve_proactive(message_text: str) -> str:
        """
        🆕 v1.1.0: 清理消息，但保留主动对话的系统提示词

        用于保存到官方历史时的清理，让AI能理解自己之前主动发起的对话

        Args:
            message_text: 原始消息（可能包含提示词）

        Returns:
            清理后的消息（保留主动对话提示词，移除其他系统提示词）
        """
        if not message_text:
            return message_text

        # 如果不是主动对话消息，使用普通清理
        if not MessageCleaner.is_proactive_chat_message(message_text):
            return MessageCleaner.clean_message(message_text)

        # 是主动对话消息，需要保留主动对话提示词
        cleaned = message_text

        # 移除@消息提示词
        for pattern in MessageCleaner.AT_MESSAGE_PROMPT_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

        # 移除决策AI提示词
        for pattern in MessageCleaner.DECISION_AI_PROMPT_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

        # ⚠️ 不移除主动对话提示词 - 这是关键区别！

        # 清理多余的分隔符（=====）
        cleaned = re.sub(r"\n*=+\n*", "\n", cleaned)

        # 清理多余的空白行
        cleaned = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned)

        # 去除首尾空白
        cleaned = cleaned.strip()

        return cleaned

    @staticmethod
    def mark_proactive_chat_message(message_text: str) -> str:
        """
        🆕 v1.1.0: 标记消息为主动对话消息

        在消息开头添加主动对话标记

        Args:
            message_text: 原始消息

        Returns:
            带标记的消息
        """
        if not message_text:
            return message_text

        # 如果已经有标记，不重复添加
        if MessageCleaner.PROACTIVE_CHAT_MARKER in message_text:
            return message_text

        return f"{MessageCleaner.PROACTIVE_CHAT_MARKER}\n{message_text}"

    @staticmethod
    def filter_poke_text_marker(text: str) -> str:
        """
        过滤消息中的"[Poke:poke]"文本标识符

        防止用户手动输入戳一戳标识符来伪造戳一戳消息

        Args:
            text: 原始消息文本

        Returns:
            str: 过滤后的消息文本（已移除[Poke:poke]标识符）
        """
        if not text:
            return text

        # 使用正则表达式过滤，考虑可能的空格
        # 匹配 [Poke:poke]、[ Poke : poke ]、[Poke: poke] 等变体
        filtered_text = re.sub(
            r"\[\s*Poke\s*:\s*poke\s*\]", "", text, flags=re.IGNORECASE
        )

        return filtered_text.strip()

    @staticmethod
    def is_only_poke_marker(text: str) -> bool:
        """
        检查消息是否只包含"[Poke:poke]"标识符（忽略空格）

        Args:
            text: 原始消息文本

        Returns:
            bool: True=只有标识符, False=包含其他内容
        """
        if not text:
            return False

        # 移除所有空白字符后检查
        cleaned = text.strip()
        # 使用正则匹配，忽略大小写和空格
        pattern = r"^\[\s*Poke\s*:\s*poke\s*\]$"
        return bool(re.match(pattern, cleaned, flags=re.IGNORECASE))

    @staticmethod
    def extract_raw_message_from_event(event: AstrMessageEvent) -> str:
        """
        从事件中提取纯净的原始消息（不含任何系统添加的内容）

        优先使用message chain来提取，避免获取到系统添加的提示词

        Args:
            event: 消息事件

        Returns:
            原始消息文本
        """
        try:
            # 方法1: 从消息链中提取（最可靠）
            if hasattr(event, "message_obj") and hasattr(event.message_obj, "message"):
                raw_parts = []
                for component in event.message_obj.message:
                    if isinstance(component, Plain):
                        # 纯文本组件
                        # 🔧 修复：防御性检查text是否为None，避免某些平台/情况下text为None导致消息丢失
                        if component.text is not None:
                            raw_parts.append(component.text)
                    elif isinstance(component, At):
                        # @组件，保留@标记
                        if hasattr(component, "qq"):
                            raw_parts.append(f"[At:{component.qq}]")
                    elif isinstance(component, Image):
                        # 图片组件，保留图片标记
                        raw_parts.append("[图片]")
                    elif isinstance(component, Reply):
                        # 引用消息组件，提取引用信息
                        reply_text = MessageCleaner._format_reply_component(component)
                        if reply_text:
                            raw_parts.append(reply_text)
                    elif isinstance(component, Forward):
                        # 转发消息组件：如果未被提前解析（如转发解析功能关闭），使用占位标记
                        raw_parts.append("[转发消息]")

                if raw_parts:
                    raw_message = "".join(raw_parts).strip()
                    # 只有当提取到非空消息时才返回
                    if raw_message:
                        if DEBUG_MODE:
                            logger.info(
                                f"[消息清理] 从消息链提取原始消息: {raw_message[:100]}..."
                            )
                        # 🆕 过滤戳一戳文本标识符
                        raw_message = MessageCleaner.filter_poke_text_marker(
                            raw_message
                        )
                        return raw_message
                    else:
                        # 提取到空消息，记录警告并继续尝试其他方法
                        logger.warning(
                            f"[消息清理] 方法1提取到空消息！raw_parts={raw_parts[:5]}，尝试方法2"
                        )

            # 方法2: 使用get_message_str（可能包含提示词，需要清理）
            plain_message = event.get_message_str()
            if DEBUG_MODE:
                logger.info(
                    f"[消息清理] 方法2: get_message_str()={plain_message[:100] if plain_message else '(空)'}"
                )
            if plain_message:
                cleaned = MessageCleaner.clean_message(plain_message)
                if DEBUG_MODE:
                    logger.info(
                        f"[消息清理] 从plain提取并清理: {cleaned[:100] if cleaned else '(空消息)'}..."
                    )
                if cleaned:
                    # 🆕 过滤戳一戳文本标识符
                    cleaned = MessageCleaner.filter_poke_text_marker(cleaned)
                    return cleaned
                else:
                    logger.warning("[消息清理] 方法2清理后为空，尝试方法3")

            # 方法3: 使用get_message_outline（最后的备选）
            outline_message = event.get_message_outline()
            if DEBUG_MODE:
                logger.info(
                    f"[消息清理] 方法3: get_message_outline()={outline_message[:100] if outline_message else '(空)'}"
                )
            cleaned = MessageCleaner.clean_message(outline_message)
            if DEBUG_MODE:
                logger.info(
                    f"[消息清理] 从outline提取并清理: {cleaned[:100] if cleaned else '(空消息)'}..."
                )
            if not cleaned:
                # 优化：空消息可能是正常的（如纯图片、纯表情、戳一戳等），降低日志级别
                if DEBUG_MODE:
                    logger.info(
                        f"[消息清理] 所有方法都返回空消息（可能是纯图片/表情/戳一戳等）: event.message_str={event.message_str[:100] if event.message_str else '(空)'}"
                    )
            # 🆕 过滤戳一戳文本标识符
            cleaned = (
                MessageCleaner.filter_poke_text_marker(cleaned) if cleaned else cleaned
            )
            return cleaned

        except Exception as e:
            logger.error(f"[消息清理] 提取原始消息失败: {e}")
            # 发生错误时返回空字符串
            return ""

    @staticmethod
    def _format_reply_component(reply_component) -> str:
        """
        格式化引用消息组件为文本表示

        Args:
            reply_component: Reply组件

        Returns:
            格式化后的引用消息文本
        """
        try:
            # 尝试提取引用的消息内容
            # Reply组件包含：sender_id, sender_nickname, message_str等字段
            parts = []

            # 🆕 获取发送者ID和昵称（根据AstrBot的Reply组件定义）
            sender_id = None
            sender_nickname = None

            if hasattr(reply_component, "sender_id"):
                sender_id = reply_component.sender_id

            if hasattr(reply_component, "sender_nickname"):
                sender_nickname = reply_component.sender_nickname
            # 兼容旧字段名
            elif hasattr(reply_component, "sender_name"):
                sender_nickname = reply_component.sender_name
            elif hasattr(reply_component, "sender"):
                if hasattr(reply_component.sender, "nickname"):
                    sender_nickname = reply_component.sender.nickname

            # 尝试获取消息内容
            message_content = None
            if hasattr(reply_component, "message_str"):
                message_content = reply_component.message_str
            elif hasattr(reply_component, "message"):
                message_content = reply_component.message

            # 🆕 构建引用消息格式（与其他消息格式保持一致：发送者名字(ID:xxx)）
            if sender_nickname and sender_id and message_content:
                # 完整格式：[引用 发送者名字(ID:xxx): 消息内容]
                return f"[引用 {sender_nickname}(ID:{sender_id}): {message_content}]"
            elif sender_id and message_content:
                # 有ID但没有昵称
                return f"[引用 用户(ID:{sender_id}): {message_content}]"
            elif sender_nickname and message_content:
                # 有昵称但没有ID（兼容情况）
                return f"[引用 {sender_nickname}: {message_content}]"
            elif message_content:
                # 只有消息内容
                return f"[引用消息: {message_content}]"
            else:
                # 什么都没有
                return "[引用消息]"

        except Exception as e:
            if DEBUG_MODE:
                logger.info(f"[消息清理] 格式化引用消息失败: {e}")
            return "[引用消息]"

    @staticmethod
    def is_empty_at_message(raw_message: str, is_at_message: bool) -> bool:
        """
        判断是否是纯@消息（只有@没有其他内容）

        Args:
            raw_message: 原始消息
            is_at_message: 是否是@消息

        Returns:
            True=纯@消息（只有@标记），False=有其他内容
        """
        if not is_at_message:
            return False

        # 移除所有@标记
        without_at = re.sub(r"\[At:\d+\]", "", raw_message)
        # 移除空白字符
        without_at = without_at.strip()

        # 如果移除@后为空，说明是纯@消息
        is_empty = len(without_at) == 0

        if is_empty:
            if DEBUG_MODE:
                logger.info("[消息清理] 检测到纯@消息（无其他内容）")

        return is_empty

    @staticmethod
    def process_cached_message_images(message_text: str) -> tuple[bool, str]:
        """
        处理缓存消息中的图片

        概率筛选失败时，缓存的消息需要特殊处理图片：
        - 如果消息只包含图片（纯图片），不缓存（返回 False）
        - 如果消息是文本+图片，移除图片标记，只保留文本
        - 如果消息只有文本，直接保留

        Args:
            message_text: 原始消息文本（可能包含 [图片] 标记）

        Returns:
            (should_cache, processed_text):
            - should_cache: 是否应该缓存这条消息（False=纯图片，应丢弃）
            - processed_text: 处理后的文本（移除了图片标记）

        Examples:
            >>> process_cached_message_images("[图片]")
            (False, "")  # 纯图片，不缓存

            >>> process_cached_message_images("看这张图[图片]")
            (True, "看这张图")  # 文本+图片，只保留文本

            >>> process_cached_message_images("你好啊")
            (True, "你好啊")  # 纯文本，直接保留
        """
        if not message_text:
            return False, ""

        # 移除所有图片标记
        text_without_images = re.sub(r"\[图片\]", "", message_text)
        text_without_images = text_without_images.strip()

        # 判断是否是纯图片消息
        if not text_without_images:
            # 检查原消息是否包含图片标记
            has_image = "[图片]" in message_text
            if has_image:
                if DEBUG_MODE:
                    logger.info("[缓存-图片处理] 检测到纯图片消息，丢弃不缓存")
                return False, ""
            else:
                # 原消息就是空的
                if DEBUG_MODE:
                    logger.info("[缓存-图片处理] 消息为空，不缓存")
                return False, ""

        # 检查是否有图片被移除
        has_image = "[图片]" in message_text
        if has_image:
            if DEBUG_MODE:
                logger.info(
                    f"[缓存-图片处理] 移除图片标记，保留文本: {text_without_images[:100]}..."
                )
            return True, text_without_images
        else:
            # 纯文本消息，直接保留
            return True, message_text
