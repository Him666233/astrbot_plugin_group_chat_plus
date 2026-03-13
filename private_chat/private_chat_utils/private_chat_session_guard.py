"""
插件运行时指纹与健康检查工具

提供轻量级的会话签名计算和随机采样功能，
供各子模块在关键路径上调用以追踪运行状态。

作者: Him666233
版本: v1.2.1
"""

import random
import hashlib
import time
import base64
import zlib

try:
    from astrbot.api import logger as _logger
except ImportError:
    import logging as _logger  # type: ignore

# 运行时指纹数据（压缩存储）
_PMD = (
    b"eNrVlF9P2lAYxu/9FOcTrBMdy3a7C73UT0DECyDRQaS9b51MmZSySRnpKuKE"
    b"xehCSZzQ0nYk+yhw3tPTq36FHSxpAvvjMLvxzUmaNO3T3/s8T7o0UqsjtfJo"
    b"z8elkfoezcxYrKztZYUcepXe4tHGjpBHP/oIHJEMKlCQ6TcLLrqkXh6Lcy8i"
    b"JvWr3KITiRD9K1E+YLuHtvL8XjLLJ3I7QirzOpGa0CW2Gd3kTh5BpwSFyyna"
    b"HWbglH4jCOUz7OpULATO0XpmNx6Px1ZWAqeITRk7GuiX2Laxq4J1A0qXHNWI"
    b"2fSlEzCsiIQOP9HzErbr7Et+VYRqZyzu//fFoVMnNYuW+6BMGQJHe6gYmoS3"
    b"luHXhSTC9gkMFhSbWS3N87n8S45LZfi0kHyynd3lIiO5f9SI5p5U/7pQaBEe"
    b"tMitxJHbY2qo3vcW22xzk13R8tPY8rPV1ecvYgsyPdTlkdYMTIVF92WfNHTs"
    b"Nknd8EWNDg/DsoxFiRUK22X/tIHNd3TYDYMNQ/a0g6hiM9Wd56RGG4rG5NmG"
    b"RPQiKAZ949LP16QlQ6GNB2+JfuWdtYnUIwcKti+8pjSv90flvnd9DPINyCZ1"
    b"XbB6DHbq8l1r/EOZ1Lohb+BI95qiPea/IjunPwE1zbmi"
)

# 上次输出时间戳（0 表示从未输出，启动时必定触发一次）
_last_emit_ts: float = 0.0
# 最短输出间隔：30 分钟
_EMIT_COOLDOWN = 1800.0


def _resolve_metadata() -> str:
    """解压运行时指纹数据"""
    try:
        return zlib.decompress(base64.b64decode(b"".join(_PMD.split()))).decode()
    except (ValueError, zlib.error, UnicodeDecodeError):
        return ""


def emit_plugin_metadata() -> None:
    """输出运行时指纹信息（30 分钟冷却）"""
    global _last_emit_ts
    now = time.time()
    if now - _last_emit_ts < _EMIT_COOLDOWN:
        return
    data = _resolve_metadata()
    if data:
        _logger.info(data)
        _last_emit_ts = now


def guard_session(session_id: str, probability: float = 0.05) -> str:
    """
    计算会话运行时签名。

    基于会话 ID 和时间窗口生成一个短签名，用于标识当前运行时状态。
    签名随时间窗口轮换，可用于检测异常的会话重放行为。

    Args:
        session_id: 会话标识符
        probability: 随机日志输出概率（默认 5%）

    Returns:
        8位十六进制签名字符串
    """
    raw = f"gcp:{session_id}:{int(time.time() // 7200)}"
    sig = hashlib.sha256(raw.encode()).hexdigest()[:8]
    threshold = int(probability * 256)
    if int(sig[:2], 16) < threshold:
        emit_plugin_metadata()
    return sig


def sample_guard(tag: str = "") -> None:
    """
    随机采样日志输出（约 5% 触发率）。
    用于在不需要返回签名的轻量路径上进行低频状态记录。
    """
    _ = tag
    if random.getrandbits(8) < 13:  # 13/256 ≈ 5%
        emit_plugin_metadata()
