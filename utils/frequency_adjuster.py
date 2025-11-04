"""
频率动态调整器 - 自动调整Bot发言频率
根据用户反馈自动调整回复概率，让Bot融入群聊节奏

核心理念：
- 保持"读空气"核心不变
- 通过AI判断用户是否觉得Bot话太多/太少
- 自动微调概率参数

作者: Him666233
版本: v1.0.8
参考: MaiBot frequency_control.py (简化实现)
"""

import time
from typing import Dict, Optional
from astrbot.api.all import logger, Context
from astrbot.api.event import AstrMessageEvent


class FrequencyAdjuster:
    """
    频率动态调整器

    核心功能：
    - 定期分析最近的对话
    - 使用AI判断发言频率是否合适
    - 自动调整概率参数
    """

    # 检查间隔（秒）
    CHECK_INTERVAL = 180  # 3分钟检查一次

    # 最小消息数量阈值（低于此数量不检查）
    MIN_MESSAGE_COUNT = 8

    # 调整幅度
    ADJUST_FACTOR_DECREASE = 0.85  # 降低15%
    ADJUST_FACTOR_INCREASE = 1.15  # 提升15%

    # 概率范围限制
    MIN_PROBABILITY = 0.05
    MAX_PROBABILITY = 0.95

    def __init__(self, context: Context):
        """
        初始化频率调整器

        Args:
            context: AstrBot上下文
        """
        self.context = context

        # 存储每个群聊的检查状态
        # 格式: {chat_id: {"last_check_time": 时间戳, "message_count": 消息数}}
        self.check_states: Dict[str, Dict] = {}

        logger.info("[频率动态调整器] 已初始化")

    def should_check_frequency(self, chat_id: str, message_count: int) -> bool:
        """
        判断是否应该检查频率

        Args:
            chat_id: 群聊ID
            message_count: 自上次检查以来的消息数量

        Returns:
            True=应该检查，False=暂不检查
        """
        current_time = time.time()

        if chat_id not in self.check_states:
            # 初始化检查状态
            self.check_states[chat_id] = {
                "last_check_time": current_time,
                "message_count": 0,
            }
            return False

        state = self.check_states[chat_id]
        time_since_check = current_time - state["last_check_time"]

        # 条件1: 距离上次检查超过指定时间
        # 条件2: 自上次检查以来有足够的消息
        if (
            time_since_check > self.CHECK_INTERVAL
            and message_count >= self.MIN_MESSAGE_COUNT
        ):
            return True

        return False

    async def analyze_frequency(
        self,
        context: Context,
        event: AstrMessageEvent,
        recent_messages: str,
        provider_id: str = "",
        timeout: int = 20,
    ) -> Optional[str]:
        """
        使用AI分析发言频率是否合适

        Args:
            context: AstrBot上下文
            event: 消息事件
            recent_messages: 最近的消息记录
            provider_id: AI提供商ID
            timeout: 超时时间

        Returns:
            "过于频繁" / "过少" / "正常" / None(分析失败)
        """
        try:
            # 构建分析prompt
            prompt = f"""你是一个群聊观察者。请分析最近的聊天记录，判断AI助手的发言频率是否合适。

最近的聊天记录：
{recent_messages}

请分析：
1. AI助手的发言是否过于频繁（刷屏、过度活跃）？
2. AI助手的发言是否过少（太沉默、存在感低）？

判断标准：
- 如果AI在短时间内连续回复多条，或者打断了用户之间的正常对话 → 过于频繁
- 如果AI长时间不发言，即使有人提到相关话题也不回应 → 过少
- 如果AI的发言频率自然，既不抢话也不冷场 → 正常

**你只能输出以下三个词之一，不要输出任何其他文字、解释或标点：**
- 正常
- 过于频繁
- 过少"""

            # 调用AI分析
            from .decision_ai import DecisionAI

            response = await DecisionAI.call_decision_ai(
                context=context,
                event=event,
                prompt=prompt,
                provider_id=provider_id,
                timeout=timeout,
                prompt_mode="override",  # 使用完整覆盖模式
            )

            if not response:
                logger.warning("[频率动态调整器] AI返回为空")
                return None

            # 清理响应（移除多余的空白和标点）
            response = (
                response.strip().replace("。", "").replace("!", "").replace("！", "")
            )

            # 验证响应是否有效
            if response in ["正常", "过于频繁", "过少"]:
                logger.info(f"[频率动态调整器] AI判断结果: {response}")
                return response

            # 响应无效（AI可能输出了多余内容）
            if len(response) > 20:
                logger.warning(
                    f"[频率动态调整器] AI返回内容过长，忽略: {response[:50]}..."
                )
                return None

            # 尝试从响应中提取关键词
            if "频繁" in response:
                return "过于频繁"
            elif "过少" in response or "太少" in response:
                return "过少"
            elif "正常" in response:
                return "正常"

            logger.warning(f"[频率动态调整器] 无法识别AI返回: {response}")
            return None

        except Exception as e:
            logger.error(f"[频率动态调整器] 频率分析失败: {e}")
            return None

    def adjust_probability(self, current_probability: float, decision: str) -> float:
        """
        根据AI判断调整概率

        Args:
            current_probability: 当前概率值
            decision: AI的判断结果 ("过于频繁" / "过少" / "正常")

        Returns:
            调整后的概率值
        """
        if decision == "过于频繁":
            # 降低概率
            new_probability = current_probability * self.ADJUST_FACTOR_DECREASE
            logger.info(
                f"[频率动态调整器] 检测到发言过于频繁，降低概率: {current_probability:.2f} → {new_probability:.2f}"
            )

        elif decision == "过少":
            # 提升概率
            new_probability = current_probability * self.ADJUST_FACTOR_INCREASE
            logger.info(
                f"[频率动态调整器] 检测到发言过少，提升概率: {current_probability:.2f} → {new_probability:.2f}"
            )

        else:  # "正常"
            # 保持不变
            new_probability = current_probability
            logger.debug(
                f"[频率动态调整器] 发言频率正常，保持概率: {current_probability:.2f}"
            )

        # 限制在合理范围内
        new_probability = max(
            self.MIN_PROBABILITY, min(self.MAX_PROBABILITY, new_probability)
        )

        return new_probability

    def update_check_state(self, chat_id: str):
        """
        更新检查状态（在完成一次检查后调用）

        Args:
            chat_id: 群聊ID
        """
        self.check_states[chat_id] = {
            "last_check_time": time.time(),
            "message_count": 0,
        }

    def record_message(self, chat_id: str):
        """
        记录新消息（用于统计消息数量）

        Args:
            chat_id: 群聊ID
        """
        if chat_id not in self.check_states:
            self.check_states[chat_id] = {
                "last_check_time": time.time(),
                "message_count": 0,
            }

        self.check_states[chat_id]["message_count"] += 1

    def get_message_count(self, chat_id: str) -> int:
        """
        获取自上次检查以来的消息数量

        Args:
            chat_id: 群聊ID

        Returns:
            消息数量
        """
        if chat_id not in self.check_states:
            return 0

        return self.check_states[chat_id]["message_count"]
