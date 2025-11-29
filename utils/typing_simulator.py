"""
回复延迟模拟器 - 模拟真人打字速度
让Bot的回复有自然的延迟，避免秒回

核心理念：
- 根据消息长度计算延迟
- 添加随机波动，更真实
- 不影响核心逻辑，仅在发送前延迟

作者: Him666233
版本: v1.1.2
"""

import asyncio
import random
from astrbot.api.all import logger

# 详细日志开关（与 main.py 同款方式：单独用 if 控制）
DEBUG_MODE: bool = False


class TypingSimulator:
    """
    打字延迟模拟器

    核心功能：
    - 根据消息长度计算延迟时间
    - 添加随机波动
    - 限制最大延迟时间
    """

    def __init__(
        self,
        typing_speed: float = 15.0,  # 字/秒
        min_delay: float = 0.5,  # 最小延迟（秒）
        max_delay: float = 3.0,  # 最大延迟（秒）
        random_factor: float = 0.3,  # 随机波动因子（±30%）
    ):
        """
        初始化打字模拟器

        Args:
            typing_speed: 打字速度（字/秒），默认15字/秒（约900字/分钟）
            min_delay: 最小延迟时间（秒）
            max_delay: 最大延迟时间（秒）
            random_factor: 随机波动因子，0.3表示±30%的随机波动
        """
        self.typing_speed = typing_speed
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.random_factor = random_factor

        if DEBUG_MODE:
            logger.info(
                f"[回复延迟模拟器] 已初始化，打字速度: {typing_speed}字/秒，延迟范围: {min_delay}-{max_delay}秒"
            )

    def calculate_delay(self, text: str) -> float:
        """
        计算延迟时间

        Args:
            text: 要发送的文本

        Returns:
            延迟时间（秒）
        """
        if not text:
            return self.min_delay

        # 计算文本长度（中文字符和英文字符都算1）
        text_length = len(text)

        # 基础延迟 = 文本长度 / 打字速度
        base_delay = text_length / self.typing_speed

        # 添加随机波动
        random_multiplier = 1.0 + random.uniform(
            -self.random_factor, self.random_factor
        )
        delay = base_delay * random_multiplier

        # 限制在合理范围内
        delay = max(self.min_delay, min(self.max_delay, delay))

        return delay

    async def simulate_typing(self, text: str) -> None:
        """
        模拟打字延迟

        Args:
            text: 要发送的文本
        """
        delay = self.calculate_delay(text)

        if DEBUG_MODE:
            logger.info(
                f"[回复延迟模拟器] 延迟 {delay:.2f} 秒（文本长度: {len(text)}）"
            )

        await asyncio.sleep(delay)

    def should_simulate(self, text: str) -> bool:
        """
        判断是否应该模拟延迟

        对于某些特殊情况（如很短的回复），可能不需要延迟

        Args:
            text: 要发送的文本

        Returns:
            True=应该延迟，False=不延迟
        """
        # 太短的消息（如"好的"、"嗯"）可以快速回复
        if len(text) <= 3:
            return False

        # 包含特殊标记的消息不延迟（如命令、工具调用结果等）
        if any(marker in text for marker in ["[", "]", "```", "{", "}"]):
            return False

        return True

    async def simulate_if_needed(self, text: str) -> None:
        """
        如果需要则模拟延迟

        这是主要的对外接口

        Args:
            text: 要发送的文本
        """
        if self.should_simulate(text):
            await self.simulate_typing(text)
        else:
            # 即使不模拟，也添加一个极短的延迟，避免完全的秒回
            await asyncio.sleep(self.min_delay * 0.5)
