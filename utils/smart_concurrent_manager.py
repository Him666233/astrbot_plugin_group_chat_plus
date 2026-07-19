"""
智能并发管理器 - Smart Concurrent Manager

在 concurrent_mode=smart 时管理群聊消息的批次协调。

新版核心逻辑：
1. 消息到达后尽早按 arrival_seq 注册，确保先后顺序稳定
2. 主消息（anchor）只能由当前批次中 arrival_seq 最小的消息担任
3. 只有 anchor 可以在决策前吸收已准备好的后续消息
4. 被 anchor 吸收的消息会被标记为 consumed，后续独立链路直接跳过

设计目标：
- 顺序以真实到达顺序为准，而不是谁先跑到某个异步点
- 支持同群多用户并发批处理
- 与 GWW 解耦，但可共享“追加消息”上下文表达方式
"""

import asyncio
import time
from typing import Dict, List, Optional
from astrbot.api import logger


class SmartConcurrentManager:
    """Smart 模式下的群聊批次协调器。"""

    # {chat_id: {processing_id: entry}}
    _pending: Dict[str, Dict[str, dict]] = {}

    # {processing_id: {consumed_at: float, anchor_processing_id: str}}
    _consumed: Dict[str, dict] = {}

    _lock: asyncio.Lock = None

    # 注册或消费状态的过期时间，避免异常路径残留内存
    _EXPIRE_SECONDS: float = 15.0

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    async def register_arrival(
        cls,
        chat_id: str,
        processing_id: str,
        source_event_id: str = "",
        arrival_seq: int = 0,
        arrival_monotonic: float = 0.0,
    ) -> None:
        """尽早注册消息到达顺序。"""
        try:
            lock = cls._get_lock()
            async with lock:
                if chat_id not in cls._pending:
                    cls._pending[chat_id] = {}

                existing = cls._pending[chat_id].get(processing_id, {})
                cls._pending[chat_id][processing_id] = {
                    **existing,
                    "processing_id": processing_id,
                    "source_event_id": source_event_id
                    or existing.get("source_event_id", ""),
                    "arrival_seq": arrival_seq or existing.get("arrival_seq", 0),
                    "arrival_monotonic": arrival_monotonic
                    or existing.get("arrival_monotonic", 0.0)
                    or time.monotonic(),
                    "registered_at": existing.get("registered_at", time.time()),
                    "payload_ready": existing.get("payload_ready", False),
                }
                cls._cleanup_expired_locked(chat_id)
        except Exception as e:
            logger.warning(f"[SmartConcurrent] register_arrival 失败: {e}")

    @classmethod
    async def attach_payload(
        cls,
        chat_id: str,
        processing_id: str,
        content: str,
        sender_name: str,
        sender_id: str,
        cached_data: dict,
        is_forced: bool = False,
        can_be_merged_when_forced: bool = False,
    ) -> None:
        """在消息完成前置处理后，挂载可用于批处理的载荷。"""
        try:
            lock = cls._get_lock()
            async with lock:
                if chat_id not in cls._pending:
                    cls._pending[chat_id] = {}

                existing = cls._pending[chat_id].get(processing_id, {})
                cls._pending[chat_id][processing_id] = {
                    **existing,
                    "processing_id": processing_id,
                    "content": content,
                    "sender_name": sender_name,
                    "sender_id": sender_id,
                    "cached_data": cached_data,
                    "is_forced": is_forced,
                    "can_be_merged_when_forced": can_be_merged_when_forced,
                    "payload_ready": True,
                    "payload_attached_at": time.time(),
                }
                cls._cleanup_expired_locked(chat_id)
        except Exception as e:
            logger.warning(f"[SmartConcurrent] attach_payload 失败: {e}")

    @classmethod
    async def is_consumed(cls, processing_id: str) -> bool:
        return processing_id in cls._consumed

    @classmethod
    async def get_consumer(cls, processing_id: str) -> Optional[str]:
        info = cls._consumed.get(processing_id)
        if not info:
            return None
        return info.get("anchor_processing_id")

    @classmethod
    async def has_earlier_pending(cls, chat_id: str, processing_id: str) -> bool:
        """检查是否还有更早到达、尚未完成的消息。"""
        try:
            lock = cls._get_lock()
            async with lock:
                cls._cleanup_expired_locked(chat_id)
                current = cls._pending.get(chat_id, {}).get(processing_id)
                if not current:
                    return False

                current_seq = current.get("arrival_seq", 0)
                for pid, entry in cls._pending.get(chat_id, {}).items():
                    if pid == processing_id:
                        continue
                    if entry.get("arrival_seq", 0) < current_seq:
                        return True
                return False
        except Exception as e:
            logger.warning(f"[SmartConcurrent] has_earlier_pending 失败: {e}")
            return False

    @classmethod
    async def has_pending(cls, chat_id: str) -> bool:
        """检查当前会话是否存在尚未被 claim/清理的 Smart 待处理消息。"""
        try:
            lock = cls._get_lock()
            async with lock:
                cls._cleanup_expired_locked(chat_id)
                return bool(cls._pending.get(chat_id))
        except Exception as e:
            logger.warning(f"[SmartConcurrent] has_pending 失败: {e}")
            return False

    # 单批次最多吸收的消息数（防止极端并发下上下文溢出）
    _MAX_BATCH_SIZE: int = 20

    @classmethod
    async def claim_batch(cls, chat_id: str, processing_id: str) -> dict:
        """
        尝试让当前消息成为 anchor，并吸收后续已准备好的消息。

        返回：
        - is_consumed=True: 当前消息已被更早的 anchor 吸收，应直接退出
        - is_anchor=True: 当前消息是本批次 anchor，merged_entries 为已吸收的后续消息
        - is_anchor=False: 当前消息暂时还不是 anchor（理论上前面已有等待逻辑）
        """
        try:
            lock = cls._get_lock()
            async with lock:
                cls._cleanup_expired_locked(chat_id)

                consumed_info = cls._consumed.get(processing_id)
                if consumed_info:
                    return {
                        "is_consumed": True,
                        "anchor_processing_id": consumed_info.get(
                            "anchor_processing_id"
                        ),
                        "merged_entries": [],
                    }

                chat_pending = cls._pending.get(chat_id, {})
                current = chat_pending.get(processing_id)
                if not current:
                    return {
                        "is_missing": True,
                        "is_anchor": False,
                        "merged_entries": [],
                    }

                ordered_entries = sorted(
                    chat_pending.values(),
                    key=lambda entry: (
                        entry.get("arrival_seq", 0),
                        entry.get("arrival_monotonic", 0.0),
                    ),
                )

                if not ordered_entries:
                    return {"is_anchor": False, "merged_entries": []}

                anchor = ordered_entries[0]
                if anchor.get("processing_id") != processing_id:
                    return {
                        "is_anchor": False,
                        "blocked_by": anchor.get("processing_id"),
                        "merged_entries": [],
                    }

                merged_entries: List[dict] = []
                current_is_forced = bool(current.get("is_forced", False))

                for entry in ordered_entries[1:]:
                    entry_pid = entry.get("processing_id")
                    if not entry_pid or entry_pid == processing_id:
                        continue

                    # 达到批次上限：停止吸收，剩余消息留在 pending 由下一批次处理
                    if len(merged_entries) >= cls._MAX_BATCH_SIZE:
                        break

                    # 关键词等强制触发仍作为边界；@AI 消息可显式允许被吸收，
                    # 由消费侧设置 call_llm=True 阻止平台默认 LLM 二次处理。
                    if entry.get("is_forced", False) and not entry.get(
                        "can_be_merged_when_forced", False
                    ):
                        break

                    # 只吸收连续且已准备好载荷的后续消息。
                    # 如果跳过一个更早但尚未准备好的消息继续吸收后面的消息，
                    # 会让批次时间顺序交叉，图片/转发慢处理时尤其明显。
                    if not entry.get("payload_ready", False):
                        break

                    merged_entries.append(entry)
                    cls._consumed[entry_pid] = {
                        "consumed_at": time.time(),
                        "anchor_processing_id": processing_id,
                    }

                # 当前 anchor 开始正式处理后，不再保留在 pending 中
                chat_pending.pop(processing_id, None)

                # 已吸收的 follower 也从 pending 中移除
                for entry in merged_entries:
                    entry_pid = entry.get("processing_id")
                    if entry_pid:
                        chat_pending.pop(entry_pid, None)

                if not chat_pending:
                    cls._pending.pop(chat_id, None)

                return {
                    "is_anchor": True,
                    "is_consumed": False,
                    "anchor_entry": current,
                    "anchor_is_forced": current_is_forced,
                    "merged_entries": merged_entries,
                }
        except Exception as e:
            logger.warning(f"[SmartConcurrent] claim_batch 失败: {e}")
            return {"is_anchor": False, "merged_entries": []}

    @classmethod
    async def remove_self(cls, chat_id: str, processing_id: str) -> None:
        """清理当前消息的 pending / consumed 痕迹。"""
        try:
            lock = cls._get_lock()
            async with lock:
                if chat_id in cls._pending:
                    cls._pending[chat_id].pop(processing_id, None)
                    if not cls._pending[chat_id]:
                        cls._pending.pop(chat_id, None)
                cls._consumed.pop(processing_id, None)
                cls._cleanup_expired_locked(chat_id)
        except Exception as e:
            logger.warning(f"[SmartConcurrent] remove_self 失败: {e}")

    @classmethod
    def _cleanup_expired_locked(cls, chat_id: str) -> None:
        now = time.time()

        if chat_id in cls._pending:
            expired_pending = []
            for pid, entry in cls._pending[chat_id].items():
                registered_at = entry.get("registered_at", now)
                attached_at = entry.get("payload_attached_at", registered_at)
                base_ts = max(registered_at, attached_at)
                if now - base_ts > cls._EXPIRE_SECONDS:
                    expired_pending.append(pid)

            for pid in expired_pending:
                cls._pending[chat_id].pop(pid, None)

            if not cls._pending[chat_id]:
                cls._pending.pop(chat_id, None)

        expired_consumed = [
            pid
            for pid, info in cls._consumed.items()
            if now - info.get("consumed_at", now) > cls._EXPIRE_SECONDS
        ]
        for pid in expired_consumed:
            cls._consumed.pop(pid, None)
