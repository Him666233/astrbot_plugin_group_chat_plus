"""
注意力机制管理器模块 - Enhanced Version
负责管理AI对多个用户的注意力和情绪态度，实现更自然的对话焦点

核心功能：
1. 多用户注意力追踪 - 同时记录多个用户的注意力分数
2. 渐进式注意力调整 - 平滑的概率变化，避免跳变
3. 指数衰减机制 - 注意力随时间自然衰减
4. 情绪系统 - 对不同用户维护情绪态度，影响回复倾向
5. 完全会话隔离 - 每个聊天独立的注意力和情绪数据

升级说明：
- v1.0.2: 初始注意力机制（单用户）
- Enhanced: 多用户追踪 + 情绪系统 + 渐进式调整

作者: Him666233
版本: v1.0.2
"""

import time
import asyncio
import math
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from astrbot.api.all import *


class AttentionManager:
    """
    增强版注意力机制管理器（支持持久化）

    主要功能：
    1. 多用户注意力图谱 - 同时追踪多个用户的注意力分数（0-1）
    2. 情绪态度系统 - 对每个用户维护情绪值（-1到1）
    3. 渐进式调整 - 注意力和情绪平滑变化
    4. 指数衰减 - 随时间自然衰减，不突然清零
    5. 会话完全隔离 - 每个chat_key独立数据
    6. 持久化存储 - 数据保存到 data/plugin_data/chat_plus/attention_data.json

    扩展接口：
    - update_emotion() - 手动更新用户情绪
    - get_user_profile() - 获取用户完整档案
    - register_interaction() - 记录自定义交互事件
    """

    # 多用户注意力图谱
    # 格式: {
    #   "chat_key": {
    #     "user_123": {
    #       "attention_score": 0.8,  # 注意力分数 0-1
    #       "emotion": 0.5,          # 情绪值 -1(负面)到1(正面)
    #       "last_interaction": timestamp,
    #       "interaction_count": 5,
    #       "last_message_preview": "最后一条消息的预览"
    #     }
    #   }
    # }
    _attention_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
    _lock = asyncio.Lock()  # 异步锁
    _storage_path: Optional[Path] = None  # 持久化存储路径
    _initialized: bool = False

    # 配置参数（可通过配置文件调整）
    MAX_TRACKED_USERS = 10  # 每个聊天最多追踪的用户数
    ATTENTION_DECAY_HALFLIFE = 300  # 注意力半衰期（秒）
    EMOTION_DECAY_HALFLIFE = 600  # 情绪半衰期（秒）
    MIN_ATTENTION_SCORE = 0.0  # 最小注意力分数
    MAX_ATTENTION_SCORE = 1.0  # 最大注意力分数
    AUTO_SAVE_INTERVAL = 60  # 自动保存间隔（秒）
    _last_save_time: float = 0  # 上次保存时间

    @staticmethod
    def initialize(data_dir: Optional[str] = None) -> None:
        """
        初始化注意力管理器（设置存储路径并加载数据）

        Args:
            data_dir: 数据目录路径（由 StarTools.get_data_dir() 提供）
        """
        if AttentionManager._initialized:
            return

        if data_dir:
            AttentionManager._storage_path = Path(data_dir) / "attention_data.json"
        else:
            # 使用默认路径（不推荐，应该由插件提供）
            AttentionManager._storage_path = Path("data") / "attention_data.json"

        # 加载已有数据
        AttentionManager._load_from_disk()
        AttentionManager._initialized = True

        logger.info(
            f"[注意力机制] 持久化存储已初始化: {AttentionManager._storage_path}"
        )

    @staticmethod
    def _load_from_disk() -> None:
        """从磁盘加载注意力数据"""
        if (
            not AttentionManager._storage_path
            or not AttentionManager._storage_path.exists()
        ):
            logger.debug("[注意力机制] 无历史数据文件，从空白开始")
            return

        try:
            with open(AttentionManager._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                AttentionManager._attention_map = data
                logger.info(f"[注意力机制] 已加载 {len(data)} 个会话的注意力数据")
        except Exception as e:
            logger.error(f"[注意力机制] 加载数据失败: {e}，将从空白开始")
            AttentionManager._attention_map = {}

    @staticmethod
    def _save_to_disk(force: bool = False) -> None:
        """
        保存注意力数据到磁盘

        Args:
            force: 是否强制保存（跳过时间检查）
        """
        if not AttentionManager._storage_path:
            return

        # 检查是否需要保存（避免频繁写磁盘）
        current_time = time.time()
        if (
            not force
            and (current_time - AttentionManager._last_save_time)
            < AttentionManager.AUTO_SAVE_INTERVAL
        ):
            return

        try:
            # 确保目录存在
            AttentionManager._storage_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存数据
            with open(AttentionManager._storage_path, "w", encoding="utf-8") as f:
                json.dump(
                    AttentionManager._attention_map, f, ensure_ascii=False, indent=2
                )

            AttentionManager._last_save_time = current_time
            logger.debug(
                f"[注意力机制] 数据已保存到磁盘 ({len(AttentionManager._attention_map)} 个会话)"
            )
        except Exception as e:
            logger.error(f"[注意力机制] 保存数据失败: {e}")

    @staticmethod
    async def _auto_save_if_needed() -> None:
        """自动保存（如果距离上次保存超过阈值）"""
        AttentionManager._save_to_disk(force=False)

    @staticmethod
    def get_chat_key(platform_name: str, is_private: bool, chat_id: str) -> str:
        """
        获取聊天的唯一标识（确保会话隔离）

        Args:
            platform_name: 平台名称（如aiocqhttp, gewechat等）
            is_private: 是否私聊
            chat_id: 聊天ID（群号或用户ID）

        Returns:
            唯一标识键
        """
        chat_type = "private" if is_private else "group"
        return f"{platform_name}_{chat_type}_{chat_id}"

    @staticmethod
    def _calculate_decay(elapsed_time: float, halflife: float) -> float:
        """
        计算指数衰减系数

        使用公式: decay = 0.5^(elapsed_time / halflife)

        Args:
            elapsed_time: 经过的时间（秒）
            halflife: 半衰期（秒）

        Returns:
            衰减系数（0-1）
        """
        if elapsed_time <= 0:
            return 1.0
        if halflife <= 0:
            return 1.0
        return math.pow(0.5, elapsed_time / halflife)

    @staticmethod
    async def _init_user_profile(user_id: str, user_name: str) -> Dict[str, Any]:
        """
        初始化用户档案

        Args:
            user_id: 用户ID
            user_name: 用户名字

        Returns:
            初始化的用户档案字典
        """
        return {
            "user_id": user_id,
            "user_name": user_name,
            "attention_score": 0.0,  # 初始注意力为0
            "emotion": 0.0,  # 初始情绪中性
            "last_interaction": time.time(),
            "interaction_count": 0,
            "last_message_preview": "",
        }

    @staticmethod
    async def _apply_attention_decay(
        profile: Dict[str, Any], current_time: float
    ) -> None:
        """
        应用注意力和情绪的时间衰减

        Args:
            profile: 用户档案
            current_time: 当前时间戳
        """
        elapsed = current_time - profile.get("last_interaction", current_time)

        # 注意力衰减
        attention_decay = AttentionManager._calculate_decay(
            elapsed, AttentionManager.ATTENTION_DECAY_HALFLIFE
        )
        profile["attention_score"] *= attention_decay

        # 情绪衰减（向0中性值）
        emotion_decay = AttentionManager._calculate_decay(
            elapsed, AttentionManager.EMOTION_DECAY_HALFLIFE
        )
        profile["emotion"] *= emotion_decay

    @staticmethod
    async def _cleanup_inactive_users(
        chat_users: Dict[str, Dict[str, Any]], current_time: float
    ) -> int:
        """
        清理长时间未互动且注意力极低的用户

        清理条件：
        1. 注意力分数 < 0.05 (几乎为0)
        2. 超过 30分钟 未互动

        Args:
            chat_users: 用户字典
            current_time: 当前时间戳

        Returns:
            清理的用户数量
        """
        INACTIVE_THRESHOLD = 1800  # 30分钟
        ATTENTION_THRESHOLD = 0.05  # 注意力阈值

        to_remove = []
        for user_id, profile in chat_users.items():
            elapsed = current_time - profile.get("last_interaction", current_time)
            attention = profile.get("attention_score", 0.0)

            # 满足清理条件：长时间未互动 且 注意力极低
            if elapsed > INACTIVE_THRESHOLD and attention < ATTENTION_THRESHOLD:
                to_remove.append(
                    (user_id, profile.get("user_name", "unknown"), attention, elapsed)
                )

        # 执行清理
        removed_count = 0
        for user_id, user_name, attention, elapsed in to_remove:
            del chat_users[user_id]
            removed_count += 1
            logger.debug(
                f"[注意力机制-清理] 移除不活跃用户: {user_name}(ID:{user_id}), "
                f"注意力={attention:.3f}, 未互动{elapsed / 60:.1f}分钟"
            )

        return removed_count

    @staticmethod
    async def record_replied_user(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        user_id: str,
        user_name: str,
        message_preview: str = "",
        attention_boost_step: float = 0.4,
        attention_decrease_step: float = 0.1,
        emotion_boost_step: float = 0.1,
    ) -> None:
        """
        记录AI回复的目标用户（增强版）

        在AI发送回复后调用，更新用户的注意力分数和情绪

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            user_id: 被回复的用户ID
            user_name: 被回复的用户名字
            message_preview: 消息预览（可选）
            attention_boost_step: 被回复用户注意力增加幅度（默认0.4）
            attention_decrease_step: 其他用户注意力减少幅度（默认0.1）
            emotion_boost_step: 被回复用户情绪增加幅度（默认0.1）
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        async with AttentionManager._lock:
            # 初始化chat_key
            if chat_key not in AttentionManager._attention_map:
                AttentionManager._attention_map[chat_key] = {}

            chat_users = AttentionManager._attention_map[chat_key]

            # 获取或创建用户档案
            if user_id not in chat_users:
                chat_users[user_id] = await AttentionManager._init_user_profile(
                    user_id, user_name
                )

            profile = chat_users[user_id]

            # 应用衰减（更新前先衰减）
            await AttentionManager._apply_attention_decay(profile, current_time)

            # 提升注意力（渐进式，使用配置的增加幅度）
            old_attention = profile["attention_score"]
            profile["attention_score"] = min(
                profile["attention_score"] + attention_boost_step,
                AttentionManager.MAX_ATTENTION_SCORE,
            )

            # 轻微提升情绪（被回复是正面交互，使用配置的增加幅度）
            profile["emotion"] = min(profile["emotion"] + emotion_boost_step, 1.0)

            # 更新其他信息
            profile["last_interaction"] = current_time
            profile["interaction_count"] = profile.get("interaction_count", 0) + 1
            profile["user_name"] = user_name  # 更新名字（可能改了昵称）
            if message_preview:
                profile["last_message_preview"] = message_preview[:50]

            # 降低其他用户的注意力（使用配置的减少幅度）
            for other_user_id, other_profile in chat_users.items():
                if other_user_id != user_id:
                    await AttentionManager._apply_attention_decay(
                        other_profile, current_time
                    )
                    other_profile["attention_score"] = max(
                        other_profile["attention_score"] - attention_decrease_step,
                        AttentionManager.MIN_ATTENTION_SCORE,
                    )

            # 智能清理：移除注意力极低且长时间未互动的用户
            await AttentionManager._cleanup_inactive_users(chat_users, current_time)

            # 如果还是超过限制，按优先级移除
            if len(chat_users) > AttentionManager.MAX_TRACKED_USERS:
                # 综合排序：注意力分数和最后互动时间
                # 注意力越低、时间越久远 → 优先级越低
                sorted_users = sorted(
                    chat_users.items(),
                    key=lambda x: (
                        x[1]["attention_score"] + 0.0001,  # 避免除零
                        x[1]["last_interaction"],
                    ),
                )
                # 移除最低优先级的用户
                to_remove_count = len(chat_users) - AttentionManager.MAX_TRACKED_USERS
                for i in range(to_remove_count):
                    removed_user_id = sorted_users[i][0]
                    removed_name = chat_users[removed_user_id].get(
                        "user_name", "unknown"
                    )
                    del chat_users[removed_user_id]
                    logger.debug(
                        f"[注意力机制] 移除低优先级用户: {removed_name}(ID:{removed_user_id}), "
                        f"注意力={sorted_users[i][1]['attention_score']:.3f}"
                    )

            logger.info(
                f"[注意力机制-增强] 会话 {chat_key} - 回复 {user_name}(ID:{user_id}), "
                f"注意力 {old_attention:.2f}→{profile['attention_score']:.2f}, "
                f"情绪 {profile['emotion']:.2f}, "
                f"互动次数 {profile['interaction_count']}"
            )

            # 自动保存数据（如果距离上次保存超过阈值）
            await AttentionManager._auto_save_if_needed()

    @staticmethod
    async def get_adjusted_probability(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        current_user_id: str,
        current_user_name: str,
        current_probability: float,
        attention_increased_probability: float,
        attention_decreased_probability: float,
        attention_duration: int,
        enabled: bool,
    ) -> float:
        """
        根据注意力机制和情绪系统调整概率（增强版）

        考虑因素：
        1. 用户的注意力分数（渐进式调整）
        2. 对该用户的情绪态度（正面提升，负面降低）
        3. 时间衰减（自然衰减，不突然清零）
        4. 多用户平衡（综合考虑多个用户）

        兼容性说明：
        - 保持与旧配置兼容（attention_increased/decreased_probability）
        - 但改为渐进式调整，而非直接替换

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            current_user_id: 当前消息发送者ID
            current_user_name: 当前消息发送者名字
            current_probability: 当前概率（未调整前）
            attention_increased_probability: （兼容参数）最大提升概率
            attention_decreased_probability: （兼容参数）最低降低概率
            attention_duration: （兼容参数）用于判断是否清理旧数据
            enabled: 是否启用注意力机制

        Returns:
            调整后的概率值（保证在 [0, 1] 范围内）
        """
        # 如果未启用注意力机制，直接返回原概率（确保在有效范围）
        if not enabled:
            return max(0.0, min(1.0, current_probability))

        # === 输入参数边界检测 ===
        # 确保所有概率参数都在 [0, 1] 范围内
        current_probability = max(0.0, min(1.0, current_probability))
        attention_increased_probability = max(
            0.0, min(1.0, attention_increased_probability)
        )
        attention_decreased_probability = max(
            0.0, min(1.0, attention_decreased_probability)
        )

        # 确保逻辑关系正确：increased >= decreased
        if attention_increased_probability < attention_decreased_probability:
            logger.warning(
                f"[注意力机制-边界检测] 配置异常: increased({attention_increased_probability:.2f}) < "
                f"decreased({attention_decreased_probability:.2f})，已自动修正"
            )
            attention_increased_probability, attention_decreased_probability = (
                attention_decreased_probability,
                attention_increased_probability,
            )

        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        async with AttentionManager._lock:
            # 如果该聊天没有记录，返回原概率
            if chat_key not in AttentionManager._attention_map:
                logger.debug(
                    f"[注意力机制-增强] 会话 {chat_key} - 无历史记录，使用原概率"
                )
                return current_probability

            chat_users = AttentionManager._attention_map[chat_key]

            # 如果当前用户没有档案，返回原概率
            if current_user_id not in chat_users:
                logger.debug(
                    f"[注意力机制-增强] 用户 {current_user_name} 无档案，使用原概率"
                )
                return current_probability

            profile = chat_users[current_user_id]

            # 应用时间衰减
            await AttentionManager._apply_attention_decay(profile, current_time)

            # 清理长时间未互动的用户（超过 attention_duration * 3）
            cleanup_threshold = current_time - (attention_duration * 3)
            users_to_remove = [
                uid
                for uid, prof in chat_users.items()
                if prof.get("last_interaction", 0) < cleanup_threshold
            ]
            if users_to_remove:
                for uid in users_to_remove:
                    del chat_users[uid]
                    logger.debug(f"[注意力机制-增强] 清理长时间未互动用户: {uid}")
                # 清理后保存
                await AttentionManager._auto_save_if_needed()

            # 获取注意力分数和情绪
            attention_score = profile.get("attention_score", 0.0)
            emotion = profile.get("emotion", 0.0)
            last_interaction = profile.get("last_interaction", current_time)
            elapsed = current_time - last_interaction

            # === 渐进式概率调整算法 ===
            # 基础调整：根据注意力分数
            # attention_score 范围 0-1
            # - 0.0: 无注意力 → 使用原概率或略低
            # - 0.5: 中等注意力 → 适度提升
            # - 1.0: 高注意力 → 显著提升

            if attention_score > 0.1:  # 有一定注意力
                # 计算提升幅度（渐进式）
                # 使用配置的 attention_increased_probability 作为参考最大值
                max_boost = attention_increased_probability - current_probability
                actual_boost = max_boost * attention_score
                adjusted_probability = current_probability + actual_boost

                # 情绪修正（正面情绪进一步提升，负面情绪降低）
                # emotion 范围确保在 [-1, 1]，影响因子在 [0.7, 1.3]
                emotion = max(-1.0, min(1.0, emotion))  # 边界检测
                emotion_factor = 1.0 + (emotion * 0.3)  # emotion范围-1到1，影响±30%
                adjusted_probability *= emotion_factor

                # === 严格的边界限制（三重保障）===
                # 1. 首先限制不超过 0.98（防止 100% 回复）
                adjusted_probability = min(adjusted_probability, 0.98)
                # 2. 然后限制不低于 attention_decreased_probability
                adjusted_probability = max(
                    adjusted_probability, attention_decreased_probability
                )
                # 3. 最终强制限制在 [0, 1] 范围（防止任何异常情况）
                adjusted_probability = max(0.0, min(1.0, adjusted_probability))

                logger.info(
                    f"[注意力机制-增强] 🎯 {current_user_name}(ID:{current_user_id}), "
                    f"注意力={attention_score:.2f}, 情绪={emotion:+.2f}, "
                    f"概率 {current_probability:.2f} → {adjusted_probability:.2f} "
                    f"(互动次数:{profile.get('interaction_count', 0)}, "
                    f"距上次:{elapsed:.0f}秒)"
                )

                return adjusted_probability
            else:
                # 注意力很低（<0.1），略微降低概率
                adjusted_probability = max(
                    current_probability * 0.8,  # 降低20%
                    attention_decreased_probability,
                )

                # === 最终边界检测（确保在 [0, 1] 范围内）===
                adjusted_probability = max(0.0, min(1.0, adjusted_probability))

                logger.debug(
                    f"[注意力机制-增强] 👤 {current_user_name}(ID:{current_user_id}), "
                    f"注意力低({attention_score:.2f}), "
                    f"概率 {current_probability:.2f} → {adjusted_probability:.2f}"
                )

                return adjusted_probability

    @staticmethod
    async def clear_attention(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        清除注意力状态

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            user_id: 可选，指定用户ID则只清除该用户，否则清除整个会话
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)

        async with AttentionManager._lock:
            if chat_key in AttentionManager._attention_map:
                if user_id:
                    # 清除特定用户
                    if user_id in AttentionManager._attention_map[chat_key]:
                        del AttentionManager._attention_map[chat_key][user_id]
                        logger.debug(
                            f"[注意力机制-增强] 会话 {chat_key} 用户 {user_id} 注意力已清除"
                        )
                else:
                    # 清除整个会话
                    del AttentionManager._attention_map[chat_key]
                    logger.debug(
                        f"[注意力机制-增强] 会话 {chat_key} 所有注意力状态已清除"
                    )

    @staticmethod
    async def get_attention_info(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        获取注意力信息（用于调试和监控）

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            user_id: 可选，指定用户ID则只返回该用户，否则返回所有用户

        Returns:
            注意力信息字典，如果没有记录则返回None
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)

        async with AttentionManager._lock:
            if chat_key not in AttentionManager._attention_map:
                return None

            chat_users = AttentionManager._attention_map[chat_key]

            if user_id:
                # 返回特定用户
                return chat_users.get(user_id, None)
            else:
                # 返回所有用户（深拷贝）
                return {uid: profile.copy() for uid, profile in chat_users.items()}

    # ========== 扩展接口（供未来功能使用） ==========

    @staticmethod
    async def update_emotion(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        user_id: str,
        emotion_delta: float,
        user_name: str = "",
    ) -> None:
        """
        手动更新用户情绪值（扩展接口）

        可用于根据消息内容分析情绪，或手动调整情绪

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            user_id: 用户ID
            emotion_delta: 情绪变化量（-1到1）
            user_name: 用户名（可选）
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        async with AttentionManager._lock:
            if chat_key not in AttentionManager._attention_map:
                AttentionManager._attention_map[chat_key] = {}

            chat_users = AttentionManager._attention_map[chat_key]

            if user_id not in chat_users:
                chat_users[user_id] = await AttentionManager._init_user_profile(
                    user_id, user_name
                )

            profile = chat_users[user_id]

            # 应用衰减
            await AttentionManager._apply_attention_decay(profile, current_time)

            # 更新情绪
            old_emotion = profile["emotion"]
            profile["emotion"] = max(-1.0, min(1.0, profile["emotion"] + emotion_delta))

            logger.debug(
                f"[注意力机制-扩展] 更新用户 {user_id} 情绪: "
                f"{old_emotion:.2f} → {profile['emotion']:.2f} (Δ{emotion_delta:+.2f})"
            )

    @staticmethod
    async def get_user_profile(
        platform_name: str, is_private: bool, chat_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取用户完整档案（扩展接口）

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            user_id: 用户ID

        Returns:
            用户档案字典，不存在返回None
        """
        return await AttentionManager.get_attention_info(
            platform_name, is_private, chat_id, user_id
        )

    @staticmethod
    async def register_interaction(
        platform_name: str,
        is_private: bool,
        chat_id: str,
        user_id: str,
        user_name: str,
        attention_delta: float = 0.0,
        emotion_delta: float = 0.0,
        message_preview: str = "",
    ) -> None:
        """
        记录自定义交互事件（扩展接口）

        可用于记录非回复类型的交互（如点赞、转发等）

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            user_id: 用户ID
            user_name: 用户名
            attention_delta: 注意力变化量
            emotion_delta: 情绪变化量
            message_preview: 消息预览
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        async with AttentionManager._lock:
            if chat_key not in AttentionManager._attention_map:
                AttentionManager._attention_map[chat_key] = {}

            chat_users = AttentionManager._attention_map[chat_key]

            if user_id not in chat_users:
                chat_users[user_id] = await AttentionManager._init_user_profile(
                    user_id, user_name
                )

            profile = chat_users[user_id]

            # 应用衰减
            await AttentionManager._apply_attention_decay(profile, current_time)

            # 更新注意力
            if attention_delta != 0.0:
                profile["attention_score"] = max(
                    AttentionManager.MIN_ATTENTION_SCORE,
                    min(
                        AttentionManager.MAX_ATTENTION_SCORE,
                        profile["attention_score"] + attention_delta,
                    ),
                )

            # 更新情绪
            if emotion_delta != 0.0:
                profile["emotion"] = max(
                    -1.0, min(1.0, profile["emotion"] + emotion_delta)
                )

            # 更新其他信息
            profile["last_interaction"] = current_time
            if message_preview:
                profile["last_message_preview"] = message_preview[:50]

            logger.debug(
                f"[注意力机制-扩展] 记录交互: {user_name}(ID:{user_id}), "
                f"注意力Δ{attention_delta:+.2f}, 情绪Δ{emotion_delta:+.2f}"
            )

    @staticmethod
    async def get_top_attention_users(
        platform_name: str, is_private: bool, chat_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取注意力最高的用户列表（扩展接口）

        可用于分析当前对话焦点

        Args:
            platform_name: 平台名称
            is_private: 是否私聊
            chat_id: 聊天ID
            limit: 返回数量限制

        Returns:
            用户档案列表，按注意力分数降序排序
        """
        chat_key = AttentionManager.get_chat_key(platform_name, is_private, chat_id)
        current_time = time.time()

        async with AttentionManager._lock:
            if chat_key not in AttentionManager._attention_map:
                return []

            chat_users = AttentionManager._attention_map[chat_key]

            # 应用衰减并排序
            user_list = []
            for user_id, profile in chat_users.items():
                await AttentionManager._apply_attention_decay(profile, current_time)
                user_list.append(profile.copy())

            # 按注意力分数降序排序
            user_list.sort(key=lambda x: x.get("attention_score", 0.0), reverse=True)

            return user_list[:limit]
