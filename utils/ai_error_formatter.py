"""
AI服务商错误格式化器 - 将原始异常转换为清晰可读的错误信息

核心功能：
1. 识别 HTTP 状态码错误（502/503/504/500 等），明确标注为「AI 服务商故障」
2. 检测 HTML 响应体（网关/CDN 错误页面），截断并提取关键信息
3. 对超长错误信息自动截断，避免日志爆炸
4. 区分「网络/服务商问题」和「代码逻辑问题」，方便快速定位

作者: Him666233
版本: v1.0.0
"""

import re
from typing import Optional

# 错误信息最大显示长度（超过则截断）
_MAX_ERROR_LENGTH = 300

# 常见 HTTP 状态码映射
_HTTP_STATUS_MAP = {
    400: "请求参数错误（Bad Request）",
    401: "认证失败（Unauthorized），请检查 API Key",
    403: "访问被拒绝（Forbidden）",
    404: "API 接口不存在（Not Found）",
    429: "请求频率超限（Rate Limit）",
    500: "AI 服务商内部服务器错误",
    502: "AI 服务商网关错误（Bad Gateway），服务可能暂时不可用",
    503: "AI 服务商服务不可用（Service Unavailable）",
    504: "AI 服务商网关超时（Gateway Timeout）",
}

# HTML 错误页面特征关键词
_HTML_ERROR_KEYWORDS = [
    "<!DOCTYPE html>",
    "<html",
    "<title>",
    "cloudflare",
    "bad gateway",
    "service unavailable",
    "error code",
    "ray id",
]

# 上游空输出/空响应特征关键词
_UPSTREAM_EMPTY_OUTPUT_KEYWORDS = [
    "upstream_empty_output",
    "upstream model returned empty output",
    "model returned no usable output",
    "no usable output",
    "empty output",
    "empty assistant message",
]


def format_ai_error(
    exception: Exception,
    context_label: str = "AI调用",
) -> str:
    """
    格式化 AI 调用异常，返回清晰可读的错误描述

    Args:
        exception: 捕获的异常对象
        context_label: 调用上下文标签，如「主动对话生成」「读空气判断」等

    Returns:
        格式化后的错误字符串，适合直接传入 logger.error()
    """
    raw_msg = str(exception).strip()
    if not raw_msg:
        raw_msg = type(exception).__name__

    # 1. 检测 HTML 响应（网关/CDN 错误页）
    if _is_html_response(raw_msg):
        status_info = _extract_http_status(raw_msg)
        return _build_html_error_message(context_label, status_info)

    # 2. 检测上游模型空输出（优先于 HTTP 429 处理，避免误判成普通限流）
    if _is_upstream_empty_output(raw_msg):
        return _build_upstream_empty_output_message(context_label, raw_msg)

    # 3. 检测 HTTP 状态码
    status_code = _extract_http_status(raw_msg)
    if status_code and status_code in _HTTP_STATUS_MAP:
        return _build_http_error_message(context_label, status_code, raw_msg)

    # 4. 检测常见网络错误关键词
    network_hint = _detect_network_error(raw_msg)
    if network_hint:
        return _build_network_error_message(context_label, network_hint, raw_msg)

    # 5. 默认：截断过长的错误信息
    return _build_generic_error_message(context_label, raw_msg)


def _is_html_response(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _HTML_ERROR_KEYWORDS) and len(text) > 200


def _is_upstream_empty_output(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in _UPSTREAM_EMPTY_OUTPUT_KEYWORDS)


def _extract_http_status(text: str) -> Optional[int]:
    patterns = [
        r"(\d{3})\s*:\s*[A-Za-z\s]+$",  # "502: Bad gateway"
        r"[Ee]rror\s+[Cc]ode\s*:?\s*(\d{3})",  # "Error code: 502"
        r"HTTP[/\s]*(\d{3})",  # "HTTP 502"
        r"status[\s]*:?[\s]*(\d{3})",  # "status: 502"
        r"(\d{3})\s+(Bad Gateway|Service Unavailable|Gateway Timeout|Internal Server Error)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            code = int(match.group(1))
            if 400 <= code <= 599:
                return code
    return None


def _detect_network_error(text: str) -> Optional[str]:
    lower = text.lower()
    hints = {
        "connection": "网络连接失败",
        "timeout": "请求超时",
        "ssl": "SSL/TLS 证书问题",
        "certificate": "证书验证失败",
        "dns": "DNS 解析失败",
        "refused": "连接被拒绝",
        "reset": "连接被重置",
        "broken pipe": "连接中断",
        "socket": "Socket 连接异常",
    }
    for keyword, hint in hints.items():
        if keyword in lower:
            return hint
    return None


def _truncate(msg: str, max_len: int = _MAX_ERROR_LENGTH) -> str:
    if len(msg) <= max_len:
        return msg
    return msg[:max_len] + f"... (已截断，原始长度 {len(msg)} 字符)"


def _build_html_error_message(label: str, status: Optional[int]) -> str:
    code_str = f" HTTP {status}" if status else ""
    detail = (
        _HTTP_STATUS_MAP.get(status, "")
        if status
        else "返回了 HTML 错误页面（可能是网关/代理/CNAM 错误）"
    )
    return (
        f"[{label}] ⚠️ AI 服务商故障{code_str}：{detail}\n"
        f"   → 这不是插件代码的问题，请检查 AI API 服务是否正常运行"
    )


def _build_upstream_empty_output_message(label: str, raw: str) -> str:
    truncated = _truncate(raw)
    return (
        f"[{label}] ⚠️ 上游模型返回空输出：模型/中转接口这次没有返回可用内容"
        f"\n   → 这通常不是插件逻辑错误，更像是上游模型波动、兼容接口异常或瞬时拥堵"
        f"\n   → 原始信息: {truncated}"
    )


def _build_http_error_message(label: str, code: int, raw: str) -> str:
    detail = _HTTP_STATUS_MAP.get(code, "未知 HTTP 错误")
    is_provider_fault = code >= 500
    fault_type = "AI 服务商故障" if is_provider_fault else "请求参数/配置问题"
    extra = _truncate(raw) if len(raw) < _MAX_ERROR_LENGTH and raw != detail else ""
    extra_line = f"\n   → 原始信息: {extra}" if extra else ""
    return f"[{label}] ⚠️ {fault_type}（HTTP {code}）：{detail}{extra_line}"


def _build_network_error_message(label: str, hint: str, raw: str) -> str:
    truncated = _truncate(raw)
    return (
        f"[{label}] ⚠️ 网络问题（{hint}）：{_truncate(truncated)}\n"
        f"   → 请检查网络连接或 AI 服务商是否可达"
    )


def _build_generic_error_message(label: str, raw: str) -> str:
    truncated = _truncate(raw)
    return f"[{label}] 发生错误: {truncated}"
