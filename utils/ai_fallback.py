"""
AI 备用提供商（冗余 / Failover）调用助手

为插件中「直连 provider.text_chat()」的判断/生成型 AI 提供统一的备用提供商机制：
当某次调用超时、报错或返回空响应时，按用户配置的顺序自动切换到下一个备用提供商重试。

关键特性：
1. 超时按「每个提供商」单独计算（每次尝试都用同一个 timeout），不是所有提供商
   共享一个总预算。
2. 「返回空响应」也视为失败并触发切换（与超时 / 报错一致）。
3. 备用列表为空时，行为与「单次直连调用」完全一致（最小化改造、零副作用）。
4. 通过返回值 errored 区分「至少发生过一次超时 / 报错」与「全部尝试仅返回空响应」，
   供调用方精确保留各自的失败语义（例如读空气AI的 _decision_ai_error 标记）。
5. 每个提供商的失败原因都会输出明确的警告日志；切换备用时输出切换日志；
   全部提供商耗尽时输出最终汇总警告。

作者: Him666233
"""

import asyncio
from typing import Awaitable, Callable, List, Optional, Tuple

from astrbot.api import logger

from .ai_error_formatter import format_ai_error


def _build_ordered_provider_ids(
    primary_provider_id: str, fallback_provider_ids: Optional[List[str]]
) -> List[str]:
    """组装「主 + 备用」的有序去重提供商 ID 列表。

    - 主提供商始终排在第一位；空字符串表示「使用平台当前默认提供商」。
    - 备用列表按配置顺序追加，自动去除空白项与重复项（与已出现过的 ID 比较）。
    """
    primary = (primary_provider_id or "").strip()
    ordered: List[str] = [primary]
    seen = {primary}
    for pid in fallback_provider_ids or []:
        pid = (pid or "").strip()
        if pid and pid not in seen:
            ordered.append(pid)
            seen.add(pid)
    return ordered


def _provider_display_name(pid: str) -> str:
    """返回提供商在日志中的人类可读名称。"""
    if pid:
        return f"提供商「{pid}」"
    return "平台默认提供商"


async def call_ai_with_fallback(
    context,
    primary_provider_id: str,
    fallback_provider_ids: Optional[List[str]],
    attempt: Callable[[object], Awaitable[Optional[str]]],
    *,
    timeout: Optional[int],
    label: str = "AI",
) -> Tuple[Optional[str], Optional[object], bool]:
    """按「主提供商 → 各备用提供商」的顺序尝试调用 AI，返回首个成功的非空结果。

    Args:
        context: AstrBot Context，用于解析提供商。
        primary_provider_id: 主提供商 ID；空字符串 = 平台当前默认提供商。
        fallback_provider_ids: 备用提供商 ID 列表（有序）；None / 空 = 不启用备用。
        attempt: 异步可调用对象，签名 attempt(provider) -> 文本或 None。
                 调用方在其中完成实际的 provider.text_chat() 及取文本逻辑；
                 解析 / 人格 / 推理过滤等仍由调用方负责。
        timeout: 每次尝试的超时秒数；None = 不在本助手内计时（由平台自身管理超时）。
                 注意：该超时对「每一个」提供商单独生效，不是所有提供商共享的总预算。
        label: 日志前缀，用于区分调用来源。

    Returns:
        (text, provider, errored)
        - 成功：text 为非空文本，provider 为成功的提供商对象，errored=False。
        - 全部失败：text=None、provider=None；errored=True 表示至少发生过一次
          超时 / 报错，errored=False 表示全部尝试都只是返回了空响应。
    """
    ordered_ids = _build_ordered_provider_ids(primary_provider_id, fallback_provider_ids)
    total = len(ordered_ids)
    has_fallback = total > 1

    if has_fallback:
        names = ", ".join(
            _provider_display_name(pid) for pid in ordered_ids
        )
        logger.info(
            f"[{label}] 已启用备用AI机制，共 {total} 个提供商（按顺序尝试）：{names}"
        )

    failed_providers: List[str] = []  # 记录每个失败提供商的名称与原因
    errored = False

    for idx, pid in enumerate(ordered_ids):
        disp = _provider_display_name(pid)

        # ========== 解析提供商 ==========
        if pid:
            provider = context.get_provider_by_id(pid)
            if not provider and idx == 0:
                # 主提供商（非空ID）配置有误 → 沿用旧行为回退到平台默认提供商
                logger.warning(
                    f"[{label}] 无法找到配置的主提供商「{pid}」，回退使用平台默认提供商"
                )
                provider = context.get_using_provider()
                pid_disp = "平台默认提供商（主提供商「" + pid + "」未找到）"
            else:
                pid_disp = disp
        else:
            # 主提供商 ID 为空（idx==0 且 pid==""），走平台默认
            provider = context.get_using_provider()
            pid_disp = disp

        if not provider:
            if pid:
                logger.warning(f"[{label}] 无法解析{disp}，已被移除/停用，跳过")
            else:
                logger.warning(f"[{label}] 无法获取平台默认AI提供商，跳过")
            failed_providers.append(f"{disp}: 无法解析/已停用")
            continue

        # ========== 调用当前提供商 ==========
        seq = f"第 {idx + 1}/{total} 个提供商" if has_fallback else "AI提供商"

        try:
            if timeout is not None:
                # 每个提供商各自完整计时，互不影响（非总预算）
                result = await asyncio.wait_for(attempt(provider), timeout=timeout)
            else:
                # 不在插件侧计时，超时由平台自身管理（如主动对话生成）
                result = await attempt(provider)
        except asyncio.TimeoutError:
            errored = True
            reason = f"调用超时（超过 {timeout} 秒）"
            failed_providers.append(f"{disp}: {reason}")
            logger.warning(f"[{label}] {pid_disp} {reason}")
            if has_fallback and idx + 1 < total:
                next_disp = _provider_display_name(ordered_ids[idx + 1])
                logger.warning(f"[{label}] ↳ 正在切换到下一个备用提供商：{next_disp}")
            elif has_fallback:
                logger.warning(f"[{label}] ↳ 已无更多备用AI可切换，全部提供商均已尝试")
            continue
        except Exception as e:
            errored = True
            reason = format_ai_error(e, label)
            failed_providers.append(f"{disp}: {reason}")
            # format_ai_error 已经是一条完整日志，这里补充当前提供商信息
            logger.warning(f"[{label}] {pid_disp} 调用发生错误")
            if has_fallback and idx + 1 < total:
                next_disp = _provider_display_name(ordered_ids[idx + 1])
                logger.warning(f"[{label}] ↳ 正在切换到下一个备用提供商：{next_disp}")
            elif has_fallback:
                logger.warning(f"[{label}] ↳ 已无更多备用AI可切换，全部提供商均已尝试")
            continue

        # ========== 检查结果 ==========
        if result is None or not str(result).strip():
            reason = "返回空响应"
            failed_providers.append(f"{disp}: {reason}")
            logger.warning(f"[{label}] {pid_disp} {reason}")
            if has_fallback and idx + 1 < total:
                next_disp = _provider_display_name(ordered_ids[idx + 1])
                logger.warning(f"[{label}] ↳ 正在切换到下一个备用提供商：{next_disp}")
            elif has_fallback:
                logger.warning(f"[{label}] ↳ 已无更多备用AI可切换，全部提供商均已尝试")
            continue

        # ========== 成功 ==========
        if idx > 0:
            # 切换到了备用提供商才成功
            success_idx = idx + 1
            logger.warning(
                f"[{label}] ✅ 主提供商调用失败后，已在第 {success_idx}/{total} 个提供商（{pid_disp}）成功获取响应"
            )
        return result, provider, errored

    # ========== 全部提供商均失败 ==========
    if failed_providers:
        logger.warning(
            f"[{label}] ❌ 全部 {total} 个提供商均已尝试且均失败，详细原因如下："
        )
        # 逐条输出每个失败的原因，方便用户排查
        for i, fail in enumerate(failed_providers):
            logger.warning(f"[{label}]   ({i + 1}) {fail}")
    else:
        logger.warning(f"[{label}] ❌ 没有可用的AI提供商（均已尝试 {total} 个）")

    return None, None, errored
