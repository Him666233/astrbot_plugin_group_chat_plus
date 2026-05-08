"""
注意力冷却管理器模块

管理用户注意力冷却状态。当决策AI决定不回复时，
用户会被添加到候选冷却或正式冷却列表，阻止自动增加关注度，
直到满足解除条件。

核心功能：
1. 注意力冷却列表管理 - 添加、移除、查询用户注意力冷却状态
2. 候选冷却列表管理 - 在正式冷却前观察同一用户的后续消息
3. 超时自动解除 - 正式冷却与候选冷却超过最大时长时自动解除
4. 与关注列表同步 - 保持数据一致性
5. 旧版持久化数据迁移 - 仅在升级时读取旧冷却数据并迁入内存

作者: Him666233
版本: v1.2.2
"""

import time
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from astrbot.api.all import logger

# 调试日志开关
DEBUG_MODE: bool = False


class CooldownManager:
    """
    注意力冷却状态管理器（运行态内存）

    主要功能：
    1. 注意力冷却列表管理 - 追踪处于注意力冷却状态的用户
    2. 超时检测 - 自动解除过期的注意力冷却状态
    3. 数据同步 - 与关注列表同步
    4. 旧版数据迁移 - 支持将历史 cooldown_data.json 中的数据迁入内存

    数据结构：
    _cooldown_map: Dict[str, Dict[str, Dict[str, Any]]] = {
        "chat_key": {
            "user_id": {
                "cooldown_start": timestamp,
                "reason": str,
                "user_name": str,
            }
        }
    }
    """

    _cooldown_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
    _pending_cooldown_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
    _lock = asyncio.Lock()
    _initialized: bool = False

    MAX_COOLDOWN_DURATION: int = 600
    COOLDOWN_TRIGGER_THRESHOLD: float = 0.3
    ENABLE_PENDING_COOLDOWN: bool = True
    PENDING_COOLDOWN_GRACE_USER_MESSAGES: int = 1
    PENDING_COOLDOWN_MAX_WAIT_SECONDS: int = 60
    PENDING_COOLDOWN_SAME_USER_PROBABILITY_FLOOR: float = 0.18
    ENABLE_AUTO_RELEASE: bool = True

    @staticmethod
    def initialize(config: Optional[Dict[str, Any]] = None) -> None:
        """初始化注意力冷却管理器，仅加载配置，不做常态持久化。"""
        if config:
            CooldownManager._load_config(config)
        CooldownManager._initialized = True

        if DEBUG_MODE:
            logger.info("[注意力冷却] 运行态内存模式已初始化")
            logger.info(
                f"[注意力冷却] 配置：最大时长={CooldownManager.MAX_COOLDOWN_DURATION}秒，"
                f"阈值={CooldownManager.COOLDOWN_TRIGGER_THRESHOLD}，"
                f"待冷却观察={CooldownManager.ENABLE_PENDING_COOLDOWN}，"
                f"自动解冻={CooldownManager.ENABLE_AUTO_RELEASE}"
            )

    @staticmethod
    def _load_config(config: Dict[str, Any]) -> None:
        """从配置字典加载注意力冷却配置。"""
        CooldownManager.MAX_COOLDOWN_DURATION = max(
            0, int(config["cooldown_max_duration"])
        )
        CooldownManager.COOLDOWN_TRIGGER_THRESHOLD = float(
            config["cooldown_trigger_threshold"]
        )
        CooldownManager.ENABLE_PENDING_COOLDOWN = bool(
            config.get("enable_pending_attention_cooldown", True)
        )
        CooldownManager.PENDING_COOLDOWN_GRACE_USER_MESSAGES = max(
            1, int(config.get("pending_cooldown_grace_user_messages", 1))
        )
        CooldownManager.PENDING_COOLDOWN_MAX_WAIT_SECONDS = max(
            5, int(config.get("pending_cooldown_max_wait_seconds", 60))
        )
        CooldownManager.PENDING_COOLDOWN_SAME_USER_PROBABILITY_FLOOR = max(
            0.0,
            min(
                1.0,
                float(config.get("pending_cooldown_same_user_probability_floor", 0.18)),
            ),
        )
        CooldownManager.ENABLE_AUTO_RELEASE = bool(
            config.get("enable_cooldown_auto_release", True)
        )

    @staticmethod
    def _normalize_legacy_payload(data: Any) -> tuple[dict, dict]:
        """将旧版持久化结构标准化为 active/pending 两个 map。"""
        if not isinstance(data, dict):
            return {}, {}
        if "active" in data or "pending" in data:
            active = data.get("active", {}) or {}
            pending = data.get("pending", {}) or {}
            return (
                active if isinstance(active, dict) else {},
                pending if isinstance(pending, dict) else {},
            )
        return data, {}

    @staticmethod
    def _restore_active_entry(chat_key: str, user_id: str, info: Dict[str, Any]) -> None:
        if chat_key not in CooldownManager._cooldown_map:
            CooldownManager._cooldown_map[chat_key] = {}
        CooldownManager._cooldown_map[chat_key][user_id] = {
            "cooldown_start": float(info.get("cooldown_start", time.time()) or time.time()),
            "reason": str(info.get("reason", "legacy_migrated_cooldown") or "legacy_migrated_cooldown"),
            "user_name": str(info.get("user_name", "未知") or "未知"),
            "promoted_from_pending": bool(info.get("promoted_from_pending", False)),
            "trigger_message_id": str(info.get("trigger_message_id", "") or ""),
            "trigger_message_timestamp": float(info.get("trigger_message_timestamp", 0) or 0),
        }

    @staticmethod
    def _restore_pending_entry(chat_key: str, user_id: str, info: Dict[str, Any]) -> None:
        if chat_key not in CooldownManager._pending_cooldown_map:
            CooldownManager._pending_cooldown_map[chat_key] = {}
        CooldownManager._pending_cooldown_map[chat_key][user_id] = {
            "pending_start": float(info.get("pending_start", time.time()) or time.time()),
            "reason": str(info.get("reason", "legacy_migrated_pending") or "legacy_migrated_pending"),
            "user_name": str(info.get("user_name", "未知") or "未知"),
            "trigger_message_id": str(info.get("trigger_message_id", "") or ""),
            "trigger_message_timestamp": float(info.get("trigger_message_timestamp", 0) or 0),
            "trigger_attention_before": float(info.get("trigger_attention_before", 0.0) or 0.0),
            "trigger_attention_after": float(info.get("trigger_attention_after", 0.0) or 0.0),
            "grace_message_budget": max(
                1,
                int(
                    info.get(
                        "grace_message_budget",
                        CooldownManager.PENDING_COOLDOWN_GRACE_USER_MESSAGES,
                    )
                    or CooldownManager.PENDING_COOLDOWN_GRACE_USER_MESSAGES
                ),
            ),
            "consumed_user_messages": max(0, int(info.get("consumed_user_messages", 0) or 0)),
            "same_user_reengage_seen": bool(info.get("same_user_reengage_seen", False)),
            "last_same_user_message_id": str(info.get("last_same_user_message_id", "") or ""),
            "last_same_user_message_timestamp": float(info.get("last_same_user_message_timestamp", 0) or 0),
            "last_same_user_is_at_ai": bool(info.get("last_same_user_is_at_ai", False)),
            "last_same_user_mention_other": bool(info.get("last_same_user_mention_other", False)),
            "last_same_user_decision": str(info.get("last_same_user_decision", "unknown") or "unknown"),
            "decay_applied": bool(info.get("decay_applied", False)),
        }

    @staticmethod
    async def import_legacy_payload(data: Any, source_name: str = "legacy") -> Dict[str, int]:
        """将旧版持久化数据导入当前内存态。"""
        active_map, pending_map = CooldownManager._normalize_legacy_payload(data)
        imported_active = 0
        imported_pending = 0

        async with CooldownManager._lock:
            for chat_key, chat_users in active_map.items():
                if not isinstance(chat_users, dict):
                    continue
                for user_id, info in chat_users.items():
                    if not isinstance(info, dict):
                        continue
                    CooldownManager._restore_active_entry(str(chat_key), str(user_id), info)
                    imported_active += 1

            for chat_key, chat_users in pending_map.items():
                if not isinstance(chat_users, dict):
                    continue
                for user_id, info in chat_users.items():
                    if not isinstance(info, dict):
                        continue
                    CooldownManager._restore_pending_entry(str(chat_key), str(user_id), info)
                    imported_pending += 1

        logger.info(
            f"[注意力冷却] 已从 {source_name} 迁移旧数据：active={imported_active}, pending={imported_pending}"
        )
        return {"active": imported_active, "pending": imported_pending}

    @staticmethod
    async def migrate_from_legacy_file(file_path: Path) -> Dict[str, Any]:
        """从旧版独立 cooldown 文件迁移数据。"""
        result = {
            "found": False,
            "imported_active": 0,
            "imported_pending": 0,
            "cleaned": False,
            "error": "",
        }
        if not file_path.exists():
            return result

        result["found"] = True
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            imported = await CooldownManager.import_legacy_payload(
                payload, source_name=str(file_path)
            )
            result["imported_active"] = imported["active"]
            result["imported_pending"] = imported["pending"]
            try:
                file_path.unlink()
                result["cleaned"] = True
                logger.info(f"[注意力冷却] 已清理旧冷却持久化文件: {file_path}")
            except Exception as cleanup_err:
                result["error"] = f"cleanup_failed: {cleanup_err}"
                logger.warning(
                    f"[注意力冷却] 旧冷却文件迁移完成，但清理失败: {file_path}, error={cleanup_err}"
                )
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"[注意力冷却] 迁移旧冷却文件失败: {file_path}, error={e}", exc_info=True)
        return result

    @staticmethod
    def _build_pending_entry(
        user_name: str,
        reason: str,
        trigger_message_id: str = "",
        trigger_message_timestamp: float = 0,
        trigger_attention_before: float = 0.0,
        trigger_attention_after: float = 0.0,
        grace_message_budget: Optional[int] = None,
    ) -> Dict[str, Any]:
        budget = (
            grace_message_budget
            if grace_message_budget is not None
            else CooldownManager.PENDING_COOLDOWN_GRACE_USER_MESSAGES
        )
        return {
            "pending_start": time.time(),
            "reason": reason,
            "user_name": user_name,
            "trigger_message_id": trigger_message_id or "",
            "trigger_message_timestamp": trigger_message_timestamp or 0,
            "trigger_attention_before": trigger_attention_before,
            "trigger_attention_after": trigger_attention_after,
            "grace_message_budget": max(1, int(budget)),
            "consumed_user_messages": 0,
            "same_user_reengage_seen": False,
            "last_same_user_message_id": "",
            "last_same_user_message_timestamp": 0,
            "last_same_user_is_at_ai": False,
            "last_same_user_mention_other": False,
            "last_same_user_decision": "unknown",
            "decay_applied": False,
        }

    @staticmethod
    async def add_pending_cooldown(
        chat_key: str,
        user_id: str,
        user_name: str,
        reason: str = "decision_ai_no_reply",
        trigger_message_id: str = "",
        trigger_message_timestamp: float = 0,
        trigger_attention_before: float = 0.0,
        trigger_attention_after: float = 0.0,
        grace_message_budget: Optional[int] = None,
    ) -> bool:
        if not CooldownManager.ENABLE_PENDING_COOLDOWN:
            return False

        async with CooldownManager._lock:
            if chat_key not in CooldownManager._pending_cooldown_map:
                CooldownManager._pending_cooldown_map[chat_key] = {}

            chat_pending = CooldownManager._pending_cooldown_map[chat_key]

            if user_id in chat_pending:
                chat_pending[user_id] = CooldownManager._build_pending_entry(
                    user_name=user_name,
                    reason=reason,
                    trigger_message_id=trigger_message_id,
                    trigger_message_timestamp=trigger_message_timestamp,
                    trigger_attention_before=trigger_attention_before,
                    trigger_attention_after=trigger_attention_after,
                    grace_message_budget=grace_message_budget,
                )
                if DEBUG_MODE:
                    logger.info(
                        f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已在候选冷却中，已刷新观察窗口"
                    )
                return False

            chat_pending[user_id] = CooldownManager._build_pending_entry(
                user_name=user_name,
                reason=reason,
                trigger_message_id=trigger_message_id,
                trigger_message_timestamp=trigger_message_timestamp,
                trigger_attention_before=trigger_attention_before,
                trigger_attention_after=trigger_attention_after,
                grace_message_budget=grace_message_budget,
            )

            logger.info(
                f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已加入候选冷却列表，原因：{reason}"
            )
            return True

    @staticmethod
    async def get_pending_info(
        chat_key: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._pending_cooldown_map:
                return None
            chat_pending = CooldownManager._pending_cooldown_map[chat_key]
            if user_id not in chat_pending:
                return None
            info = chat_pending[user_id].copy()
            info["elapsed_time"] = time.time() - info.get("pending_start", 0)
            info["remaining_time"] = max(
                0,
                CooldownManager.PENDING_COOLDOWN_MAX_WAIT_SECONDS - info["elapsed_time"],
            )
            return info

    @staticmethod
    async def is_in_pending_cooldown(chat_key: str, user_id: str) -> bool:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._pending_cooldown_map:
                return False
            return user_id in CooldownManager._pending_cooldown_map[chat_key]

    @staticmethod
    async def clear_pending_cooldown(
        chat_key: str, user_id: str, reason: str = "manual"
    ) -> bool:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._pending_cooldown_map:
                return False

            chat_pending = CooldownManager._pending_cooldown_map[chat_key]
            if user_id not in chat_pending:
                return False

            pending_info = chat_pending[user_id]
            user_name = pending_info.get("user_name", "未知")
            duration = time.time() - pending_info.get("pending_start", 0)

            del chat_pending[user_id]
            if not chat_pending:
                del CooldownManager._pending_cooldown_map[chat_key]

            logger.info(
                f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已从候选冷却列表移除，"
                f"原因：{reason}，持续时间：{duration:.1f}秒"
            )
            return True

    @staticmethod
    async def promote_pending_to_active(
        chat_key: str, user_id: str, reason: str = "pending_promoted"
    ) -> bool:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._pending_cooldown_map:
                return False
            chat_pending = CooldownManager._pending_cooldown_map[chat_key]
            pending_info = chat_pending.get(user_id)
            if not pending_info:
                return False

            if chat_key not in CooldownManager._cooldown_map:
                CooldownManager._cooldown_map[chat_key] = {}

            CooldownManager._cooldown_map[chat_key][user_id] = {
                "cooldown_start": time.time(),
                "reason": reason,
                "user_name": pending_info.get("user_name", "未知"),
                "promoted_from_pending": True,
                "trigger_message_id": pending_info.get("trigger_message_id", ""),
                "trigger_message_timestamp": pending_info.get("trigger_message_timestamp", 0),
            }

            del chat_pending[user_id]
            if not chat_pending:
                del CooldownManager._pending_cooldown_map[chat_key]

            logger.info(
                f"[注意力冷却] 用户 {pending_info.get('user_name', '未知')}(ID:{user_id}) 候选冷却已升级为正式冷却，原因：{reason}"
            )
            return True

    @staticmethod
    async def consume_pending_by_same_user_message(
        chat_key: str,
        user_id: str,
        message_id: str = "",
        message_timestamp: float = 0,
        is_at_ai: bool = False,
        mention_other: bool = False,
        has_trigger_keyword: bool = False,
        is_empty_at: bool = False,
    ) -> Optional[Dict[str, Any]]:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._pending_cooldown_map:
                return None
            chat_pending = CooldownManager._pending_cooldown_map[chat_key]
            pending_info = chat_pending.get(user_id)
            if not pending_info:
                return None

            pending_info["last_same_user_message_id"] = message_id or ""
            pending_info["last_same_user_message_timestamp"] = message_timestamp or 0
            pending_info["last_same_user_is_at_ai"] = bool(is_at_ai)
            pending_info["last_same_user_mention_other"] = bool(mention_other)

            if is_at_ai or is_empty_at or (has_trigger_keyword and not mention_other):
                pending_info["same_user_reengage_seen"] = True
                pending_info["last_same_user_decision"] = "reengage_ai"
            elif mention_other:
                pending_info["consumed_user_messages"] = (
                    pending_info.get("consumed_user_messages", 0) + 1
                )
                pending_info["last_same_user_decision"] = "still_other_target"
            else:
                pending_info["consumed_user_messages"] = (
                    pending_info.get("consumed_user_messages", 0) + 1
                )
                pending_info["last_same_user_decision"] = "ambiguous"

            snapshot = pending_info.copy()
            snapshot["should_promote"] = (
                not pending_info.get("same_user_reengage_seen", False)
                and pending_info.get("consumed_user_messages", 0)
                >= pending_info.get(
                    "grace_message_budget",
                    CooldownManager.PENDING_COOLDOWN_GRACE_USER_MESSAGES,
                )
            )
            return snapshot

    @staticmethod
    async def mark_pending_decision_result(
        chat_key: str,
        user_id: str,
        should_reply: bool,
        explicitly_to_other: bool = False,
    ) -> Optional[str]:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._pending_cooldown_map:
                return None
            chat_pending = CooldownManager._pending_cooldown_map[chat_key]
            pending_info = chat_pending.get(user_id)
            if not pending_info:
                return None

            if should_reply or pending_info.get("same_user_reengage_seen", False):
                pending_info["last_same_user_decision"] = "reengage_ai"
                return "cancel"

            if explicitly_to_other:
                pending_info["last_same_user_decision"] = "still_other_target"

            if pending_info.get("consumed_user_messages", 0) >= pending_info.get(
                "grace_message_budget",
                CooldownManager.PENDING_COOLDOWN_GRACE_USER_MESSAGES,
            ):
                return "promote"

            return "keep"

    @staticmethod
    async def check_and_release_expired_pending(chat_key: str) -> List[str]:
        released_users: List[str] = []
        current_time = time.time()

        async with CooldownManager._lock:
            if chat_key not in CooldownManager._pending_cooldown_map:
                return released_users

            chat_pending = CooldownManager._pending_cooldown_map[chat_key]
            users_to_release: List[str] = []

            for user_id, pending_info in chat_pending.items():
                pending_start = pending_info.get("pending_start", 0)
                elapsed_time = current_time - pending_start
                if elapsed_time >= CooldownManager.PENDING_COOLDOWN_MAX_WAIT_SECONDS:
                    users_to_release.append(user_id)

            for user_id in users_to_release:
                user_info = chat_pending[user_id]
                user_name = user_info.get("user_name", "未知")
                duration = current_time - user_info.get("pending_start", 0)
                del chat_pending[user_id]
                released_users.append(user_id)
                logger.info(
                    f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 候选冷却已自动解除，原因：超时，持续时间：{duration:.1f}秒"
                )

            if not chat_pending:
                del CooldownManager._pending_cooldown_map[chat_key]

        return released_users

    @staticmethod
    async def is_user_under_cooldown_control(
        chat_key: str, user_id: str
    ) -> Tuple[bool, str]:
        async with CooldownManager._lock:
            if (
                chat_key in CooldownManager._cooldown_map
                and user_id in CooldownManager._cooldown_map[chat_key]
            ):
                return True, "active"
            if (
                chat_key in CooldownManager._pending_cooldown_map
                and user_id in CooldownManager._pending_cooldown_map[chat_key]
            ):
                return True, "pending"
            return False, "none"

    @staticmethod
    async def add_to_cooldown(
        chat_key: str,
        user_id: str,
        user_name: str,
        reason: str = "decision_ai_no_reply",
    ) -> bool:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._cooldown_map:
                CooldownManager._cooldown_map[chat_key] = {}

            chat_cooldowns = CooldownManager._cooldown_map[chat_key]

            if user_id in chat_cooldowns:
                if DEBUG_MODE:
                    logger.info(
                        f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已在注意力冷却中，跳过"
                    )
                return False

            if (
                chat_key in CooldownManager._pending_cooldown_map
                and user_id in CooldownManager._pending_cooldown_map[chat_key]
            ):
                del CooldownManager._pending_cooldown_map[chat_key][user_id]
                if not CooldownManager._pending_cooldown_map[chat_key]:
                    del CooldownManager._pending_cooldown_map[chat_key]

            chat_cooldowns[user_id] = {
                "cooldown_start": time.time(),
                "reason": reason,
                "user_name": user_name,
            }

            logger.info(
                f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已添加到注意力冷却列表，原因：{reason}"
            )
            return True

    @staticmethod
    async def remove_from_cooldown(
        chat_key: str, user_id: str, reason: str = "manual"
    ) -> bool:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._cooldown_map:
                return False

            chat_cooldowns = CooldownManager._cooldown_map[chat_key]
            if user_id not in chat_cooldowns:
                return False

            user_info = chat_cooldowns[user_id]
            user_name = user_info.get("user_name", "未知")
            cooldown_start = user_info.get("cooldown_start", 0)
            duration = time.time() - cooldown_start

            del chat_cooldowns[user_id]
            if not chat_cooldowns:
                del CooldownManager._cooldown_map[chat_key]

            logger.info(
                f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已从注意力冷却列表移除，"
                f"原因：{reason}，持续时间：{duration:.1f}秒"
            )
            return True

    @staticmethod
    async def handle_same_user_reengage(
        chat_key: str, user_id: str, is_at_ai: bool = False
    ) -> Dict[str, bool]:
        result = {"cleared_pending": False, "cleared_active": False}
        if await CooldownManager.is_in_pending_cooldown(chat_key, user_id):
            result["cleared_pending"] = await CooldownManager.clear_pending_cooldown(
                chat_key, user_id, reason="same_user_reengage"
            )
        return result

    @staticmethod
    async def is_in_cooldown(chat_key: str, user_id: str) -> bool:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._cooldown_map:
                return False
            return user_id in CooldownManager._cooldown_map[chat_key]

    @staticmethod
    async def get_cooldown_info(
        chat_key: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        async with CooldownManager._lock:
            if chat_key not in CooldownManager._cooldown_map:
                return None

            chat_cooldowns = CooldownManager._cooldown_map[chat_key]
            if user_id not in chat_cooldowns:
                return None

            info = chat_cooldowns[user_id].copy()
            info["elapsed_time"] = time.time() - info.get("cooldown_start", 0)
            info["remaining_time"] = max(
                0, CooldownManager.MAX_COOLDOWN_DURATION - info["elapsed_time"]
            )
            return info

    @staticmethod
    async def check_and_release_expired(chat_key: str) -> List[str]:
        released_users: List[str] = []
        current_time = time.time()

        if not CooldownManager.ENABLE_AUTO_RELEASE:
            return released_users

        async with CooldownManager._lock:
            if chat_key not in CooldownManager._cooldown_map:
                return released_users

            chat_cooldowns = CooldownManager._cooldown_map[chat_key]
            users_to_release: List[str] = []

            for user_id, cooldown_info in chat_cooldowns.items():
                cooldown_start = cooldown_info.get("cooldown_start", 0)
                elapsed_time = current_time - cooldown_start
                if elapsed_time >= CooldownManager.MAX_COOLDOWN_DURATION:
                    users_to_release.append(user_id)

            for user_id in users_to_release:
                user_info = chat_cooldowns[user_id]
                user_name = user_info.get("user_name", "未知")
                cooldown_start = user_info.get("cooldown_start", 0)
                duration = current_time - cooldown_start

                del chat_cooldowns[user_id]
                released_users.append(user_id)

                logger.info(
                    f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已自动解除注意力冷却，"
                    f"原因：超时，持续时间：{duration:.1f}秒"
                )

            if not chat_cooldowns:
                del CooldownManager._cooldown_map[chat_key]

        return released_users

    @staticmethod
    async def sync_with_attention_list(
        chat_key: str, attention_user_ids: List[str]
    ) -> List[str]:
        removed_users: List[str] = []
        pending_removed_users: List[str] = []

        async with CooldownManager._lock:
            if (
                chat_key not in CooldownManager._cooldown_map
                and chat_key not in CooldownManager._pending_cooldown_map
            ):
                return removed_users

            attention_set = set(attention_user_ids)

            if chat_key in CooldownManager._cooldown_map:
                chat_cooldowns = CooldownManager._cooldown_map[chat_key]
                users_to_remove = [
                    user_id
                    for user_id in chat_cooldowns.keys()
                    if user_id not in attention_set
                ]
                for user_id in users_to_remove:
                    user_info = chat_cooldowns[user_id]
                    user_name = user_info.get("user_name", "未知")
                    del chat_cooldowns[user_id]
                    removed_users.append(user_id)
                    logger.info(
                        f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已从注意力冷却列表移除，"
                        f"原因：与关注列表同步（用户不在关注列表中）"
                    )
                if not chat_cooldowns:
                    del CooldownManager._cooldown_map[chat_key]

            if chat_key in CooldownManager._pending_cooldown_map:
                chat_pending = CooldownManager._pending_cooldown_map[chat_key]
                for user_id in list(chat_pending.keys()):
                    if user_id not in attention_set:
                        del chat_pending[user_id]
                        pending_removed_users.append(user_id)
                if not chat_pending:
                    del CooldownManager._pending_cooldown_map[chat_key]

        return removed_users + pending_removed_users

    @staticmethod
    async def sync_with_attention_map(chat_key: str, attention_map: Optional[Dict[str, Any]]) -> List[str]:
        """与当前注意力追踪表同步，移除不再被追踪的 active / pending 用户。"""
        attention_user_ids = list((attention_map or {}).keys())
        return await CooldownManager.sync_with_attention_list(chat_key, attention_user_ids)

    @staticmethod
    async def clear_session_cooldown(chat_key: str) -> int:
        async with CooldownManager._lock:
            cleared_count = 0
            pending_cleared_count = 0

            if chat_key in CooldownManager._cooldown_map:
                cleared_count = len(CooldownManager._cooldown_map[chat_key])
                del CooldownManager._cooldown_map[chat_key]

            if chat_key in CooldownManager._pending_cooldown_map:
                pending_cleared_count = len(CooldownManager._pending_cooldown_map[chat_key])
                del CooldownManager._pending_cooldown_map[chat_key]

            total = cleared_count + pending_cleared_count
            if total > 0:
                logger.info(
                    f"[注意力冷却] 会话 {chat_key} 的冷却数据已清除，"
                    f"移除了 {cleared_count} 个正式冷却用户，{pending_cleared_count} 个候选冷却用户"
                )
            return total

    @staticmethod
    async def clear_all_cooldown() -> int:
        async with CooldownManager._lock:
            total_cleared = 0
            total_pending_cleared = 0
            for _, chat_cooldowns in CooldownManager._cooldown_map.items():
                total_cleared += len(chat_cooldowns)
            for _, chat_pending in CooldownManager._pending_cooldown_map.items():
                total_pending_cleared += len(chat_pending)

            CooldownManager._cooldown_map = {}
            CooldownManager._pending_cooldown_map = {}

            logger.info(
                f"[注意力冷却] 所有注意力冷却数据已清除，共移除了 {total_cleared} 个正式冷却用户，"
                f"{total_pending_cleared} 个候选冷却用户"
            )
            return total_cleared + total_pending_cleared

    @staticmethod
    def _validate_user_for_release(
        chat_key: str, user_id: str, attention_user_ids: Optional[List[str]] = None
    ) -> tuple[bool, str]:
        if chat_key not in CooldownManager._cooldown_map:
            return False, "会话不在注意力冷却中"

        chat_cooldowns = CooldownManager._cooldown_map[chat_key]
        if user_id not in chat_cooldowns:
            return False, "用户不在注意力冷却中"

        if attention_user_ids is not None and user_id not in attention_user_ids:
            return False, "用户不在关注列表中"

        return True, ""

    @staticmethod
    async def try_release_cooldown_on_reply(
        chat_key: str,
        user_id: str,
        trigger_type: str,
        attention_user_ids: Optional[List[str]] = None,
    ) -> bool:
        if await CooldownManager.is_in_pending_cooldown(chat_key, user_id):
            await CooldownManager.clear_pending_cooldown(
                chat_key, user_id, reason=f"reply_trigger:{trigger_type}"
            )
            return True

        async with CooldownManager._lock:
            is_valid, reason = CooldownManager._validate_user_for_release(
                chat_key, user_id, attention_user_ids
            )
            if not is_valid:
                if DEBUG_MODE:
                    logger.info(f"[注意力冷却] 跳过解除用户 {user_id}：{reason}")
                return False

            chat_cooldowns = CooldownManager._cooldown_map[chat_key]
            user_info = chat_cooldowns[user_id]
            user_name = user_info.get("user_name", "未知")
            cooldown_start = user_info.get("cooldown_start", 0)
            duration = time.time() - cooldown_start

            del chat_cooldowns[user_id]
            if not chat_cooldowns:
                del CooldownManager._cooldown_map[chat_key]

            logger.info(
                f"[注意力冷却] 用户 {user_name}(ID:{user_id}) 已解除注意力冷却，"
                f"触发类型：{trigger_type}，持续时间：{duration:.1f}秒"
            )
            return True
