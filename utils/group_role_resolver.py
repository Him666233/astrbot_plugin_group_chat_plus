"""
GroupRoleResolver 群成员角色解析模块
通过 OneBot get_group_member_info API 获取群成员角色（群主/管理员/群成员）

核心原则：
- 带 TTL 缓存，避免重复 API 调用
- 任何异常或未知值均返回空字符串，调用方自行跳过
- 仅 aiocqhttp 平台可用，其他平台自动降级

作者: Him666233
"""

import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# 角色映射：API 原始值 → 中文标签
_ROLE_MAPPING: Dict[str, str] = {
    "owner": "群主",
    "admin": "管理员",
    "member": "普通群成员",
}


class GroupRoleResolver:
    """群成员角色解析器，带 TTL 缓存。

    缓存设计：
    - Key:  "{group_id}:{user_id}"
    - Value: (中文标签, 写入时间戳)
    - TTL:  300 秒（5 分钟）
    - 最大容量: 500 条，溢出时清空全部缓存
    """

    _role_cache: Dict[str, Tuple[str, float]] = {}
    CACHE_TTL: float = 300.0
    MAX_CACHE_SIZE: int = 500

    # ── 公开方法 ──

    @classmethod
    async def resolve_role(cls, event, group_id: str, user_id: str) -> str:
        """解析群成员角色，返回中文标签。

        Args:
            event:     AstrMessageEvent 实例
            group_id:  群号字符串
            user_id:   用户 QQ 号字符串

        Returns:
            "群主" / "管理员" / "群成员"，失败时返回 ""
        """
        # 1. 入参校验
        gid = (group_id or "").strip()
        uid = (user_id or "").strip()
        if not gid or not uid:
            return ""

        # 2. 查缓存
        cache_key = cls._make_cache_key(gid, uid)
        cached = cls._get_from_cache(cache_key)
        if cached is not None:
            return cached

        # 3. 缓存未命中 → API 调用
        raw_role = await cls.resolve_role_raw(event, gid, uid)
        label = cls._role_to_label(raw_role)

        # 4. 写入缓存（即使是空字符串也缓存，避免对失败结果重复调用）
        cls._set_cache(cache_key, label)

        if not raw_role:
            logger.info(
                f"[群身份] 未获取到用户 {uid} 在群 {gid} 的角色信息"
                f"（平台不支持或 API 失败）"
            )
        else:
            logger.info(
                f"[群身份] 用户 {uid} 在群 {gid} 的角色: {label}"
            )

        return label

    @classmethod
    async def resolve_role_raw(cls, event, group_id: str, user_id: str) -> str:
        """直接调用 OneBot API，不做缓存。

        完全复用 main.py _resolve_group_member_name 的 API 调用模式。

        Returns:
            "owner" / "admin" / "member" / ""
        """
        gid = (group_id or "").strip()
        uid = (user_id or "").strip()
        if not gid or not uid:
            return ""

        try:
            # 获取 bot 实例（与 _resolve_group_member_name 相同模式）
            bot = getattr(event, "bot", None)
            call_action = getattr(bot, "call_action", None) if bot else None
            if not callable(call_action):
                api = getattr(bot, "api", None) if bot else None
                call_action = getattr(api, "call_action", None) if api else None

            if not callable(call_action):
                logger.info(
                    "[群身份] 无法获取 call_action（平台可能不是 aiocqhttp），跳过角色解析"
                )
                return ""

            # 调用 get_group_member_info API
            result = await call_action(
                "get_group_member_info",
                group_id=int(gid) if gid.isdigit() else gid,
                user_id=int(uid) if uid.isdigit() else uid,
            )

            # 提取 role 字段（兼容两种返回格式）
            if isinstance(result, dict):
                role = result.get("role")
                if role:
                    return str(role).strip()
                data = result.get("data")
                if isinstance(data, dict):
                    role = data.get("role")
                    if role:
                        return str(role).strip()

            return ""

        except Exception as e:
            logger.info(f"[群身份] API 调用失败（已降级忽略）: {e}")
            return ""

    @classmethod
    def clear_cache(cls) -> None:
        """清空全部缓存。"""
        cls._role_cache.clear()
        logger.info("[群身份] 缓存已清空")

    # ── 内部方法 ──

    @classmethod
    def _role_to_label(cls, role: str) -> str:
        """API 原始值 → 中文标签。未知值返回空字符串。"""
        if not role:
            return ""
        return _ROLE_MAPPING.get(str(role).strip().lower(), "")

    @classmethod
    def _make_cache_key(cls, group_id: str, user_id: str) -> str:
        return f"{group_id}:{user_id}"

    @classmethod
    def _get_from_cache(cls, cache_key: str) -> Optional[str]:
        """从缓存读取，自动检查 TTL。过期返回 None。"""
        entry = cls._role_cache.get(cache_key)
        if entry is None:
            return None
        label, timestamp = entry
        if time.time() - timestamp > cls.CACHE_TTL:
            del cls._role_cache[cache_key]
            return None
        return label

    @classmethod
    def _set_cache(cls, cache_key: str, label: str) -> None:
        """写入缓存，超容量时清理最旧条目。"""
        # 超容量清理
        if len(cls._role_cache) >= cls.MAX_CACHE_SIZE:
            # 按时间戳排序，清理最旧的 20%
            sorted_entries = sorted(
                cls._role_cache.items(), key=lambda x: x[1][1]
            )
            remove_count = max(int(cls.MAX_CACHE_SIZE * 0.2), 1)
            for old_key, _ in sorted_entries[:remove_count]:
                del cls._role_cache[old_key]
            logger.info(
                f"[群身份] 缓存超容量（{cls.MAX_CACHE_SIZE}），"
                f"已清理 {remove_count} 条最旧条目"
            )

        cls._role_cache[cache_key] = (label, time.time())
