"""
Web 配置面板 - aiohttp 服务器核心
"""

import html
import os
import re
import json
import shutil
import socket
import asyncio
from pathlib import Path
from typing import Any
from aiohttp import web
from astrbot.api import logger

from .auth import AuthFailureReason, AuthManager
from .security import SecurityManager
from ..utils.probability_manager import ProbabilityManager

# 合法 session 名称：仅允许字母、数字、下划线、短横线、点号、感叹号
# 禁止 .. / \ 等路径遍历字符
_SAFE_SESSION_RE = re.compile(r"^[A-Za-z0-9_\-!.]+$")


class WebPanelServer:
    """Web 配置面板服务器"""

    def __init__(self, plugin, host="0.0.0.0", port=1451, data_dir: str | None = None):
        self.plugin = plugin
        self.host = host
        self.port = port
        self.runner = None
        self._task = None

        # 使用主插件已确定的 canonical 数据目录，避免不同重启路径漂移
        self.data_dir = self._resolve_data_dir(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_web_data()

        # 初始化认证管理器
        self.auth_mgr = AuthManager(str(self.data_dir))

        # 每次插件重载/重启时轮换 JWT secret（web端发起的除外）
        skipped = self.auth_mgr.rotate_jwt_secret()
        if not skipped:
            logger.info("🔑 JWT secret 已轮换，所有旧登录会话已失效")

        # 初始化安全管理器
        self.security = SecurityManager(
            config=self._read_security_config(),
            data_dir=str(self.data_dir),
        )

        # 启动日志自动清理（异步任务）
        self._log_cleaner_task = None

        # 静态文件目录
        self.static_dir = Path(__file__).parent / "static"
        self.template_dir = Path(__file__).parent / "templates"

        # 创建 aiohttp 应用
        self.app = web.Application(middlewares=[self._auth_middleware])
        self._setup_routes()

    def _resolve_data_dir(self, data_dir: str | None) -> Path:
        """解析 Web 面板使用的 canonical 插件数据目录"""
        if data_dir:
            return Path(data_dir).resolve()

        plugin_data_dir = getattr(self.plugin, "plugin_data_dir", None)
        if plugin_data_dir:
            return Path(plugin_data_dir).resolve()

        try:
            from astrbot.core.star.star_tools import StarTools

            return Path(StarTools.get_data_dir()).resolve()
        except Exception:
            fallback = Path(__file__).parent.parent / "data"
            return fallback.resolve()

    def _get_legacy_data_dirs(self) -> list[Path]:
        """收集历史版本可能使用过的数据目录，用于一次性迁移"""
        candidates: list[Path] = []

        try:
            from astrbot.core.star.star_tools import StarTools

            legacy_named = Path(
                StarTools.get_data_dir("astrbot_plugin_group_chat_plus")
            ).resolve()
            candidates.append(legacy_named)
        except Exception:
            pass

        candidates.append((Path(__file__).parent.parent / "web_data").resolve())

        unique_candidates: list[Path] = []
        seen: set[str] = set()
        canonical = self.data_dir.resolve()
        for path in candidates:
            normalized = str(path)
            if normalized in seen or path == canonical:
                continue
            seen.add(normalized)
            unique_candidates.append(path)
        return unique_candidates

    def _migrate_legacy_web_data(self):
        """迁移历史路径中的 web_data 认证文件到 canonical 数据目录"""
        canonical_web_data = self.data_dir / "web_data"
        canonical_web_data.mkdir(parents=True, exist_ok=True)
        canonical_auth_file = canonical_web_data / "auth.json"
        if canonical_auth_file.exists():
            self._warn_legacy_root_auth_file(canonical_auth_file)
            return

        for legacy_dir in self._get_legacy_data_dirs():
            legacy_auth_file = legacy_dir / "web_data" / "auth.json"
            if not legacy_auth_file.exists():
                continue

            shutil.copy2(legacy_auth_file, canonical_auth_file)
            logger.info(
                f"🌐 已迁移 Web 认证数据到当前插件数据目录: {legacy_auth_file} -> {canonical_auth_file}"
            )
            legacy_jwt_file = legacy_dir / "web_data" / "jwt_secret.json"
            canonical_jwt_file = canonical_web_data / "jwt_secret.json"
            if legacy_jwt_file.exists() and not canonical_jwt_file.exists():
                shutil.copy2(legacy_jwt_file, canonical_jwt_file)
                logger.info(
                    f"🌐 已迁移 JWT 密钥文件到当前插件数据目录: {legacy_jwt_file} -> {canonical_jwt_file}"
                )
            self._warn_legacy_root_auth_file(canonical_auth_file)
            return

        self._warn_legacy_root_auth_file(canonical_auth_file)

    def _warn_legacy_root_auth_file(self, canonical_auth_file: Path):
        """提示旧版本遗留的根目录 auth.json 处理建议"""
        legacy_root_auth = self.data_dir / "auth.json"
        if not legacy_root_auth.exists() or legacy_root_auth == canonical_auth_file:
            return

        if canonical_auth_file.exists():
            logger.warning(
                "🌐 检测到旧版本遗留的根目录 auth.json：当前版本实际使用 web_data/auth.json。"
                f"如旧版本密码保存在 {legacy_root_auth}，升级前请先将其移动到 {canonical_auth_file}，"
                "否则升级后可能需要重新设置 Web 面板密码。"
                "若当前目录同时存在两个 auth.json，且已确认 web_data/auth.json 正常可用，可手动删除根目录旧文件以避免混淆。"
            )
        else:
            logger.warning(
                "🌐 检测到旧版本遗留的根目录 auth.json，但当前 web_data/auth.json 不存在。"
                f"如需沿用旧密码，请先将 {legacy_root_auth} 移动到 {canonical_auth_file} 再升级/启动，"
                "否则系统会生成新的默认密码。"
            )

    def _read_security_config(self) -> dict:
        """从插件配置文件读取安全相关配置"""
        file_config = self._read_config_file()
        return {
            "web_panel_ip_mode": file_config.get("web_panel_ip_mode", "disabled"),
            "web_panel_ip_list": file_config.get("web_panel_ip_list", []),
            "web_panel_protected_ips": file_config.get("web_panel_protected_ips", []),
            "web_panel_anti_spider": file_config.get("web_panel_anti_spider", False),
            "web_panel_anti_spider_rate_limit": file_config.get(
                "web_panel_anti_spider_rate_limit", 60
            ),
            "web_panel_anti_spider_ban_duration": file_config.get(
                "web_panel_anti_spider_ban_duration", 300
            ),
            "web_panel_authenticated_rate_limit": file_config.get(
                "web_panel_authenticated_rate_limit",
                max(240, file_config.get("web_panel_anti_spider_rate_limit", 60) * 4),
            ),
            "web_panel_ip_bind_check": file_config.get("web_panel_ip_bind_check", True),
        }

    def _get_panel_version_text(self) -> str:
        """读取面板显示用插件版本号。"""
        metadata_file = Path(__file__).parent.parent / "metadata.yaml"
        try:
            raw = metadata_file.read_text(encoding="utf-8")
        except Exception:
            return ""

        match = re.search(r"^\s*version\s*:\s*(.+?)\s*$", raw, re.MULTILINE)
        if not match:
            return ""

        value = match.group(1).split("#", 1)[0].strip().strip("'\"")
        if not value:
            return ""
        if not value.lower().startswith("v"):
            value = f"v{value}"
        return html.escape(value, quote=True)

    def _render_panel_page(self) -> str | None:
        """渲染面板页并注入安全版本文本。"""
        panel_file = self.template_dir / "panel.html"
        if not panel_file.exists():
            return None
        content = panel_file.read_text(encoding="utf-8")
        return content.replace("__PLUGIN_VERSION__", self._get_panel_version_text())

    # ---- 获取客户端 IP ----

    def _get_client_ip(self, request: web.Request) -> str:
        """获取客户端真实 IP

        检测顺序：
        1. 若 peername 本身不是回环地址，直接使用（直连场景）
        2. 若 peername 是回环地址（127.x 或 ::1），说明走了反向代理，
           按顺序尝试 X-Real-IP → X-Forwarded-For 第一段
        3. 若配置了 web_panel_trust_proxy=True，无论 peername 如何都读取代理头
        """
        peername = request.transport.get_extra_info("peername")
        peer_ip = peername[0] if peername else "unknown"

        trust_proxy = self._trust_proxy_cached
        is_loopback = peer_ip in (
            "127.0.0.1",
            "::1",
            "localhost",
        ) or peer_ip.startswith("127.")

        if trust_proxy or is_loopback:
            real_ip = request.headers.get("X-Real-IP", "").strip()
            if real_ip:
                return real_ip
            xff = request.headers.get("X-Forwarded-For", "").strip()
            if xff:
                return xff.split(",")[0].strip()

        return peer_ip

    def _is_request_secure(self, request: web.Request) -> bool:
        """判断当前请求是否处于 HTTPS 安全上下文。"""
        if request.secure or request.scheme == "https":
            return True
        if self._trust_proxy_cached:
            proto = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
            if proto.lower() == "https":
                return True
        return False

    def _set_auth_cookie(
        self, request: web.Request, response: web.StreamResponse, token: str
    ):
        response.set_cookie(
            "gcp_token",
            token,
            httponly=True,
            samesite="Strict",
            secure=self._is_request_secure(request),
            path="/",
            max_age=24 * 60 * 60,
        )

    def _clear_auth_cookie(self, request: web.Request, response: web.StreamResponse):
        response.del_cookie(
            "gcp_token",
            path="/",
            samesite="Strict",
            secure=self._is_request_secure(request),
        )

    @property
    def _trust_proxy_cached(self) -> bool:
        """缓存 trust_proxy 配置，避免每次请求都读取磁盘"""
        if not hasattr(self, "_trust_proxy_val"):
            self._trust_proxy_val = self._read_config_file().get(
                "web_panel_trust_proxy", False
            )
        return self._trust_proxy_val

    def _invalidate_trust_proxy_cache(self):
        """配置更新时清除缓存"""
        if hasattr(self, "_trust_proxy_val"):
            del self._trust_proxy_val
        if hasattr(self, "_ip_bind_check_val"):
            del self._ip_bind_check_val
        if hasattr(self, "_config_file_cache"):
            del self._config_file_cache

    @property
    def _ip_bind_check_cached(self) -> bool:
        """缓存 ip_bind_check 配置，避免每次请求都读取磁盘"""
        if not hasattr(self, "_ip_bind_check_val"):
            self._ip_bind_check_val = self._read_config_file().get(
                "web_panel_ip_bind_check", True
            )
        return self._ip_bind_check_val

    # ---- 无需认证的路径白名单 ----
    _PUBLIC_PATHS = {
        "/",
        "/api/auth/login",
        "/api/auth/status",
        "/api/logo",
        "/favicon.ico",
        "/robots.txt",
        "/error",  # 统一错误/拦截页（公开，无需认证）
    }

    # ---- 面板专用静态资源路径（需要 JWT 认证才能访问） ----
    _PANEL_STATIC_PREFIX = "/panel/static/"

    # ---- 面板主页（需要 JWT 认证） ----
    _PANEL_PAGE = "/panel"

    # ---- 仅允许在 AstrBot 传统配置界面修改的 Web 面板安全底线配置 ----
    _WEB_CONFIG_READONLY_KEYS = {
        "enable_web_panel",
        "web_panel_port",
        "web_panel_host",
        "web_panel_reset_password",
        "web_panel_protected_ips",
        "web_panel_ip_bind_check",
        "web_panel_trust_proxy",
        "web_panel_heartbeat_visible_interval_seconds",
        "web_panel_heartbeat_hidden_interval_seconds",
        "web_panel_heartbeat_retry_base_seconds",
        "web_panel_heartbeat_retry_max_seconds",
        "web_panel_brute_force_window",
        "web_panel_brute_force_rate_window",
        "web_panel_brute_force_rate_count",
        "web_panel_brute_force_tiers",
        "web_panel_brute_force_ban_duration",
    }

    _CHAT_HISTORY_ALLOWED_KEYS = {
        "message_str",
        "platform_name",
        "timestamp",
        "type",
        "group_id",
        "self_id",
        "session_id",
        "message_id",
        "sender",
    }
    _CHAT_HISTORY_ALLOWED_SENDER_KEYS = {"user_id", "nickname"}
    _CHAT_HISTORY_SCALAR_TYPES = (str, int, float, bool, type(None))

    # ---- 安全响应头 ----
    _SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
    }

    # ---- 登录页 CSP 模板（script-src 使用 nonce，不再使用 unsafe-inline）----
    _CSP_LOGIN_TEMPLATE = (
        "default-src 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "script-src 'self' 'nonce-{nonce}'; "
        "connect-src 'self'; "
        "form-action 'none'; "
        "frame-ancestors 'none';"
    )
    _CSP_LOGIN_EMBED_TEMPLATE = (
        "default-src 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "script-src 'self' 'nonce-{nonce}'; "
        "connect-src 'self'; "
        "form-action 'none'; "
        "frame-ancestors 'self' http://127.0.0.1:* http://localhost:*;"
    )

    # ---- 面板页 CSP 模板（script-src 使用 nonce，style-src 保留 unsafe-inline 供动态 UI）----
    _CSP_PANEL_TEMPLATE = (
        "default-src 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "script-src 'self' 'nonce-{nonce}'; "
        "connect-src 'self'; "
        "form-action 'none'; "
        "frame-ancestors 'none';"
    )
    _CSP_PANEL_EMBED_TEMPLATE = (
        "default-src 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "script-src 'self' 'nonce-{nonce}'; "
        "connect-src 'self'; "
        "form-action 'none'; "
        "frame-ancestors 'self' http://127.0.0.1:* http://localhost:*;"
    )

    # ---- 错误页 CSP 模板（script-src 使用 nonce）----
    _CSP_ERROR_TEMPLATE = (
        "default-src 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "script-src 'self' 'nonce-{nonce}'; "
        "connect-src 'self'; "
        "form-action 'none'; "
        "frame-ancestors 'none';"
    )

    def _add_security_headers(
        self, response: web.Response, csp: str = None, allow_frame: bool = False
    ) -> web.Response:
        """向响应添加安全头"""
        for k, v in self._SECURITY_HEADERS.items():
            if allow_frame and k == "X-Frame-Options":
                continue
            response.headers[k] = v
        if csp:
            response.headers["Content-Security-Policy"] = csp
        return response

    @staticmethod
    def _is_embed_request(request: web.Request) -> bool:
        return request.query.get("embed") == "1"

    @staticmethod
    def _generate_nonce() -> str:
        """生成 CSP nonce（每次请求唯一，Base64 编码）"""
        import base64 as _b64

        return _b64.b64encode(os.urandom(24)).decode("ascii")

    def _build_csp(self, nonce: str, template: str) -> str:
        """根据模板和 nonce 构建 CSP 字符串"""
        return template.format(nonce=nonce)

    @staticmethod
    def _inject_nonce(html: str, nonce: str) -> str:
        """将 nonce 注入到 HTML 中所有内联 <script> 和 <style> 标签

        仅对不含 src 属性的 <script> 标签注入 nonce（内联脚本）。
        对所有 <style> 标签注入 nonce（内联样式）。
        外部脚本（<script src="...">）由 CSP 的 'self' 指令放行，无需 nonce。
        """
        import re as _re

        html = _re.sub(
            r"<script(?!\s+src=)(?!\s+nonce=)",
            f'<script nonce="{nonce}"',
            html,
        )
        html = _re.sub(
            r"<style(?!\s+nonce=)",
            f'<style nonce="{nonce}"',
            html,
        )
        return html

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler):
        """安全中间件：路径校验 → robots.txt → 防爬虫 → IP 过滤 → 会话认证"""
        ip = self._get_client_ip(request)
        path = request.path
        user_agent = request.headers.get("User-Agent", "")
        is_heartbeat = path == "/api/auth/heartbeat"

        if (
            ".." in path
            or "//" in path
            or "\\" in path
            or "%2e" in path.lower()
            or "%2f" in path.lower()
        ):
            self.security.log_access(
                ip, request.method, path, 400, note="路径遍历攻击尝试"
            )
            return web.json_response({"ok": False, "msg": "非法请求"}, status=400)

        _LOGIN_PUBLIC_STATIC = (
            "/static/css/main.css",
            "/static/css/login.css",
            "/static/js/utils.js",
            "/static/js/api.js",
            "/static/js/bg-animation.js",
        )
        if path in _LOGIN_PUBLIC_STATIC:
            response = await handler(request)
            return self._add_security_headers(response)

        if path.startswith(self._PANEL_STATIC_PREFIX):
            token = self._extract_token(request)
            if not token:
                self.security.log_access(
                    ip, request.method, path, 403, note="未授权访问面板静态资源"
                )
                return web.Response(status=403, text="Forbidden")
            verify_ip = ip if self._ip_bind_check_cached else None
            auth_result = self.auth_mgr.verify_token(token, current_ip=verify_ip)
            if not auth_result.ok:
                self.security.log_access(
                    ip, request.method, path, 403, note="无效 token 访问面板静态资源"
                )
                return web.Response(status=403, text="Forbidden")
            request["user"] = auth_result.payload
            request["client_ip"] = ip
            response = await handler(request)
            self.security.log_access(ip, request.method, path, response.status)
            return self._add_security_headers(response)

        if path.startswith("/static/") and path not in _LOGIN_PUBLIC_STATIC:
            self.security.log_access(
                ip, request.method, path, 403, note="拒绝直接访问内部静态资源"
            )
            return web.Response(status=403, text="Forbidden")

        if path == "/robots.txt":
            return web.Response(
                text=self.security.get_robots_txt(),
                content_type="text/plain",
            )

        allowed, reason = self.security.check_ip_allowed(ip)
        if not allowed:
            self.security.log_access(ip, request.method, path, 403)
            if not path.startswith("/api/"):
                nonce = self._generate_nonce()
                html = self._inject_nonce(
                    self._load_error_page("blocked", reason), nonce
                )
                csp = self._build_csp(nonce, self._CSP_ERROR_TEMPLATE)
                response = web.Response(
                    text=html,
                    content_type="text/html",
                    status=403,
                )
                return self._add_security_headers(response, csp)
            return web.json_response(
                {"ok": False, "msg": reason, "blocked": True}, status=403
            )

        auth_token = self._extract_token(request)
        verify_ip = ip if self._ip_bind_check_cached else None
        auth_result = None
        if auth_token:
            auth_result = self.auth_mgr.verify_token(
                auth_token,
                current_ip=verify_ip,
                touch=not is_heartbeat,
            )

        if self.security.anti_spider_enabled:
            if auth_result and auth_result.ok:
                session_id = (
                    auth_result.session.get("sid") if auth_result.session else ""
                )
                hit_limit, limit_reason = self.security.check_authenticated_rate_limit(
                    ip,
                    session_id,
                    path,
                    is_heartbeat=is_heartbeat,
                )
                if hit_limit:
                    note = self.security.get_auto_ban_note(limit_reason)
                    self.security.auto_ban_spider(ip, limit_reason)
                    self.security.log_access(ip, request.method, path, 403, note=note)
                    return web.json_response(
                        {"ok": False, "msg": "访问被拒绝", "blocked": True}, status=403
                    )
            else:
                is_spider, spider_reason = self.security.check_spider(
                    ip, path, user_agent
                )
                if is_spider:
                    note = self.security.get_auto_ban_note(spider_reason)
                    self.security.auto_ban_spider(ip, spider_reason)
                    self.security.log_access(ip, request.method, path, 403, note=note)
                    if not path.startswith("/api/"):
                        nonce = self._generate_nonce()
                        html = self._inject_nonce(
                            self._load_error_page(
                                "blocked", f"[防爬虫] {spider_reason}"
                            ),
                            nonce,
                        )
                        csp = self._build_csp(nonce, self._CSP_ERROR_TEMPLATE)
                        response = web.Response(
                            text=html,
                            content_type="text/html",
                            status=403,
                        )
                        return self._add_security_headers(response, csp)
                    return web.json_response(
                        {"ok": False, "msg": "访问被拒绝", "blocked": True}, status=403
                    )

        if path in self._PUBLIC_PATHS:
            response = await handler(request)
            access_note = request.get("access_note", "")
            self.security.log_access(
                ip, request.method, path, response.status, note=access_note
            )
            if path in {"/", "/error"}:
                return self._add_security_headers(
                    response,
                    allow_frame=path == "/" and self._is_embed_request(request),
                )
            return response

        if path == self._PANEL_PAGE:
            if not auth_result or not auth_result.ok:
                login_path = "/?embed=1" if self._is_embed_request(request) else "/"
                response = web.HTTPFound(login_path)
                self._clear_auth_cookie(request, response)
                return response
            request["user"] = auth_result.payload
            request["client_ip"] = ip
            response = await handler(request)
            self.security.log_access(ip, request.method, path, response.status)
            return self._add_security_headers(
                response,
                allow_frame=self._is_embed_request(request),
            )

        if not auth_token:
            self.security.log_access(ip, request.method, path, 401)
            if not path.startswith("/api/"):
                return web.HTTPFound("/")
            logger.info(
                f"🔒 未登录请求: {request.method} {path} ({ip}) — "
                f"This 401 is expected when no valid session exists; the frontend will redirect to login."
            )
            return web.json_response({"ok": False, "msg": "未登录"}, status=401)

        if not auth_result or not auth_result.ok:
            self.security.log_access(ip, request.method, path, 401)
            if not path.startswith("/api/"):
                response = web.HTTPFound("/")
                self._clear_auth_cookie(request, response)
                return response
            reason_code = (
                auth_result.reason
                if auth_result
                else AuthFailureReason.SIGNATURE_INVALID
            )
            msg = "登录已失效，请重新登录"
            if reason_code == AuthFailureReason.IP_CHANGED:
                msg = "您的 IP 地址已变更，为安全起见请重新登录"
            elif reason_code == AuthFailureReason.SERVER_RESTART:
                msg = "服务已重启，请重新登录"
            elif reason_code == AuthFailureReason.PASSWORD_CHANGED:
                msg = "密码已修改，请重新登录"
            elif reason_code == AuthFailureReason.PASSWORD_RESET:
                msg = "密码已重置，请重新登录"
            logger.info(
                f"🔒 会话失效请求: {request.method} {path} ({ip}) reason={reason_code} — "
                f"Session invalidated ({reason_code}), redirecting to login. 会话已失效（{reason_code}），将跳转至登录页。"
            )
            response = web.json_response(
                {"ok": False, "msg": msg, "reason": reason_code},
                status=401,
            )
            self._clear_auth_cookie(request, response)
            return response

        request["user"] = auth_result.payload
        request["auth_session"] = auth_result.session
        request["client_ip"] = ip
        response = await handler(request)
        access_note = request.get("access_note", "")
        self.security.log_access(
            ip, request.method, path, response.status, note=access_note
        )
        if path.startswith("/api/"):
            self._add_security_headers(response)
        return response

    def _extract_token(self, request: web.Request) -> str | None:
        """从 HttpOnly Cookie 优先提取 JWT token，兼容 Authorization 头。"""
        token = request.cookies.get("gcp_token", "")
        if token:
            return token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    def _setup_routes(self):
        """注册所有路由"""
        r = self.app.router

        # 登录页（公开，无需认证）
        r.add_get("/", self._handle_login_page)
        r.add_get("/favicon.ico", self._handle_favicon)

        # 统一错误/拦截页（公开，无需认证，通过 URL 参数区分错误类型）
        r.add_get("/error", self._handle_error_page)

        # 面板页（需要认证，服务器端验证 token 后返回 panel.html）
        r.add_get("/panel", self._handle_panel_page)

        # 认证 API
        r.add_post("/api/auth/login", self._handle_login)
        r.add_get("/api/auth/status", self._handle_auth_status)
        r.add_post("/api/auth/change-password", self._handle_change_password)
        r.add_get("/api/auth/verify", self._handle_verify)
        r.add_get("/api/auth/heartbeat", self._handle_heartbeat)
        r.add_post("/api/auth/logout", self._handle_logout)

        # 配置
        r.add_get("/api/config", self._handle_get_config)
        r.add_put("/api/config", self._handle_put_config)
        r.add_post("/api/config/reload", self._handle_reload)
        r.add_get("/api/config/download", self._handle_config_download)

        # 数据
        r.add_get("/api/data/sessions", self._handle_data_sessions)
        r.add_get("/api/data/attention/{session}", self._handle_data_attention)
        r.add_get("/api/data/mood/{session}", self._handle_data_mood)
        r.add_get("/api/data/probability/{session}", self._handle_data_probability)
        r.add_get("/api/data/proactive", self._handle_data_proactive)
        r.add_get("/api/data/overview", self._handle_data_overview)
        r.add_get("/api/data/status", self._handle_data_status)
        r.add_get("/api/data/session-detail/{session}", self._handle_session_detail)

        # 会话管理
        r.add_get("/api/session/list", self._handle_session_list)
        r.add_post("/api/session/reset/{session}", self._handle_session_reset)
        r.add_post("/api/session/clear-image-cache", self._handle_clear_image_cache)
        r.add_post("/api/session/clean-ghosts", self._handle_clean_ghost_sessions)
        r.add_get("/api/session/chat-history/{session}", self._handle_get_chat_history)
        r.add_put("/api/session/chat-history/{session}", self._handle_put_chat_history)
        r.add_get("/api/session/image-cache", self._handle_get_image_cache)

        # 指令执行
        r.add_post("/api/commands/reset", self._handle_cmd_reset)
        r.add_post("/api/commands/reset-here", self._handle_cmd_reset_here)
        r.add_post(
            "/api/commands/clear-image-cache", self._handle_cmd_clear_image_cache
        )

        # 安全管理
        r.add_get("/api/security/access-log", self._handle_access_log)
        r.add_get("/api/security/bans", self._handle_get_bans)
        r.add_post("/api/security/ban", self._handle_ban_ip)
        r.add_post("/api/security/unban", self._handle_unban_ip)
        r.add_post("/api/security/update-ban-note", self._handle_update_ban_note)
        r.add_get("/api/security/ip-config", self._handle_get_ip_config)
        r.add_put("/api/security/ip-config", self._handle_put_ip_config)

        # 文件管理
        r.add_get("/api/files/list", self._handle_file_list)
        r.add_get("/api/files/read", self._handle_file_read)
        r.add_put("/api/files/save", self._handle_file_save)
        r.add_post("/api/files/delete", self._handle_file_delete)

        # Logo（公开，用于登录页展示）
        r.add_get("/api/logo", self._handle_logo)

        # 登录页专用静态资源（main.css / login.css / utils.js / api.js 对外公开）
        if self.static_dir.exists():
            r.add_static(
                "/static/css/",
                path=str(self.static_dir / "css"),
                name="static_css_public",
            )
            # 仅允许登录页所需的 JS 文件（utils.js, api.js）
            r.add_get("/static/js/utils.js", self._handle_static_js_utils)
            r.add_get("/static/js/api.js", self._handle_static_js_api)
            r.add_get("/static/js/bg-animation.js", self._handle_static_js_bg_animation)

        # 面板专用静态资源（/panel/static/ 需要认证，由中间件保护）
        if self.static_dir.exists():
            r.add_static(
                "/panel/static/", path=str(self.static_dir), name="panel_static"
            )

    # ==================== 启停管理 ====================

    MAX_RETRY = 3  # 最大重试次数
    RETRY_DELAY = 2  # 重试间隔（秒）

    async def start(self):
        """启动 Web 服务器，端口被占用时最多重试 MAX_RETRY 次"""
        for attempt in range(1, self.MAX_RETRY + 1):
            try:
                self.runner = web.AppRunner(self.app)
                await self.runner.setup()
                site = web.TCPSite(self.runner, self.host, self.port)
                await site.start()
                # 收集本机所有 IPv4 地址
                _ips: list[str] = []
                try:
                    for _info in socket.getaddrinfo(socket.gethostname(), None):
                        if _info[0] == socket.AF_INET:
                            _ip = _info[4][0]
                            if _ip not in _ips:
                                _ips.append(_ip)
                except Exception:
                    pass
                if not _ips:
                    _ips = ["127.0.0.1"]
                _lines = [
                    "",
                    "  ✨✨✨",
                    "  Group Chat Plus Web 面板已启动，可访问",
                    "",
                    f"   ➜  本地:  http://localhost:{self.port}",
                ]
                for _ip in _ips:
                    _lines.append(f"   ➜  网络:  http://{_ip}:{self.port}")
                _lines.append("")
                logger.info("\n".join(_lines))
                # 启动日志自动清理任务
                self._start_log_cleaner()
                # 启动请求追踪数据定期清理任务（释放长期无活动 IP 的滑动窗口内存）
                self._start_tracking_cleanup()
                return  # 启动成功，直接返回
            except OSError as e:
                # 清理本次失败的 runner
                if self.runner:
                    try:
                        await self.runner.cleanup()
                    except Exception as cleanup_err:
                        logger.debug(f"🌐 清理 runner 时出错（已忽略）: {cleanup_err}")
                    self.runner = None

                if attempt < self.MAX_RETRY:
                    logger.warning(
                        f"🌐 Web 面板启动失败（第 {attempt}/{self.MAX_RETRY} 次），"
                        f"端口 {self.port} 可能被占用: {e}，"
                        f"{self.RETRY_DELAY}秒后重试..."
                    )
                    await asyncio.sleep(self.RETRY_DELAY)
                else:
                    logger.error(
                        f"🌐 Web 面板启动失败（已重试 {self.MAX_RETRY} 次），放弃启动。"
                        f"端口 {self.port} 被占用: {e}"
                    )
            except Exception as e:
                # 非端口占用的其他异常，直接放弃，不影响插件主功能
                if self.runner:
                    try:
                        await self.runner.cleanup()
                    except Exception as cleanup_err:
                        logger.debug(f"🌐 清理 runner 时出错（已忽略）: {cleanup_err}")
                    self.runner = None
                logger.error(
                    f"🌐 Web 面板启动遇到未知错误，放弃启动: {e}", exc_info=True
                )
                return

        # 所有重试都失败
        self.runner = None
        logger.error("🌐 Web 配置面板未能启动，插件其他功能不受影响。")

    async def stop(self):
        """停止 Web 服务器"""
        # 停止日志清理任务
        if self._log_cleaner_task and not self._log_cleaner_task.done():
            self._log_cleaner_task.cancel()
            try:
                await self._log_cleaner_task
            except asyncio.CancelledError:
                pass
        self._log_cleaner_task = None
        # 停止追踪数据清理任务
        if (
            hasattr(self, "_tracking_cleanup_task")
            and self._tracking_cleanup_task
            and not self._tracking_cleanup_task.done()
        ):
            self._tracking_cleanup_task.cancel()
            try:
                await self._tracking_cleanup_task
            except asyncio.CancelledError:
                pass
            self._tracking_cleanup_task = None
        if self.runner:
            try:
                await self.runner.cleanup()
                logger.info("🌐 Web 配置面板已停止")
            except Exception as e:
                logger.warning(f"🌐 Web 面板停止时出错（已忽略）: {e}")
            finally:
                self.runner = None

    def _start_log_cleaner(self):
        """启动日志自动清理后台任务"""
        if self._log_cleaner_task and not self._log_cleaner_task.done():
            return
        cfg = self._read_config_file()
        if not cfg.get("web_panel_log_auto_clean", False):
            return
        self._log_cleaner_task = asyncio.ensure_future(self._log_cleaner_loop())

    def _start_tracking_cleanup(self):
        """启动请求追踪数据定期清理（每小时一次，独立于日志清理配置）"""
        if (
            hasattr(self, "_tracking_cleanup_task")
            and self._tracking_cleanup_task
            and not self._tracking_cleanup_task.done()
        ):
            return
        self._tracking_cleanup_task = asyncio.ensure_future(
            self._tracking_cleanup_loop()
        )

    async def _tracking_cleanup_loop(self):
        """定期清理 _request_timestamps 和 _authenticated_request_timestamps 中超过 1 小时无活动的条目"""
        try:
            while True:
                await asyncio.sleep(3600)
                self.security.cleanup_stale_tracking_data(max_age_seconds=3600)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"🔒 请求追踪清理任务异常: {e}")

    async def _log_cleaner_loop(self):
        """日志自动清理循环任务"""
        try:
            while True:
                cfg = self._read_config_file()
                if not cfg.get("web_panel_log_auto_clean", False):
                    await asyncio.sleep(3600)  # 关闭时每小时检查一次是否重新开启
                    continue
                retention_days = max(
                    1, min(365, cfg.get("web_panel_log_retention_days", 7))
                )
                interval_hours = max(
                    1, min(168, cfg.get("web_panel_log_clean_interval_hours", 24))
                )
                deleted = self.security.clean_old_logs(retention_days)
                if deleted > 0:
                    logger.info(
                        f"🔒 日志自动清理：删除了 {deleted} 个超过 {retention_days} 天的日志文件"
                    )
                await asyncio.sleep(interval_hours * 3600)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"🔒 日志自动清理任务异常: {e}")

    # ==================== 页面 Handler ====================

    def _render_login_page(self) -> str:
        """渲染登录页，按需注入旧版密码文件升级提醒"""
        login_file = self.template_dir / "login.html"
        try:
            content = login_file.read_text(encoding="utf-8")
        except Exception:
            return ""

        legacy_root_auth = self.data_dir / "auth.json"
        canonical_auth = self.data_dir / "web_data" / "auth.json"
        notice_html = ""
        if legacy_root_auth.exists() and canonical_auth.exists():
            legacy_rel = self._safe_display_path(legacy_root_auth)
            canonical_rel = self._safe_display_path(canonical_auth)
            notice_html = (
                '<div class="login-upgrade-notice">'
                "<strong>⚠️ 旧版本升级提醒</strong>"
                "<p>检测到插件数据根目录仍存在旧版 <code>auth.json</code>，当前 Web 面板实际使用的是 <code>web_data/auth.json</code>。</p>"
                "<p>旧版本密码加密方式较弱（PBKDF2-SHA256），且新版本自动升级加密规则对旧文件无效。</p>"
                f"<p>旧文件位置：<code>{legacy_rel}</code><br>当前使用位置：<code>{canonical_rel}</code></p>"
                '<p class="legacy-warn-delete">建议直接手动删除旧版本密码文件</p>'
                "</div>"
            )
        elif legacy_root_auth.exists():
            legacy_rel = self._safe_display_path(legacy_root_auth)
            canonical_rel = self._safe_display_path(canonical_auth)
            notice_html = (
                '<div class="login-upgrade-notice">'
                "<strong>⚠️ 旧版本升级提醒</strong>"
                "<p>检测到插件数据根目录仍存在旧版 <code>auth.json</code>，但当前 <code>web_data/auth.json</code> 还不存在。</p>"
                f"<p>如需沿用旧密码，请先将 <code>{legacy_rel}</code> "
                f"移动到 <code>{canonical_rel}</code> 后再升级/启动，否则系统会重新生成默认密码。</p>"
                "</div>"
            )

        return content.replace("__LEGACY_AUTH_NOTICE__", notice_html)

    @staticmethod
    def _safe_display_path(full_path: Path) -> str:
        """将绝对路径转换为安全的相对显示路径（基于 astrBot 数据目录起点）"""
        try:
            rel = full_path.relative_to(Path(full_path.anchor))
            parts = rel.parts
            for i, part in enumerate(parts):
                if part.lower() in ("astrbot", "data"):
                    return str(Path(*parts[i:])).replace("\\", "/")
            return full_path.name
        except ValueError:
            return full_path.name

    async def _handle_login_page(self, request: web.Request):
        """返回登录页（公开，无需认证），使用 nonce-based CSP"""
        content = self._render_login_page()
        if content:
            embed = self._is_embed_request(request)
            nonce = self._generate_nonce()
            content = self._inject_nonce(content, nonce)
            csp_template = (
                self._CSP_LOGIN_EMBED_TEMPLATE if embed else self._CSP_LOGIN_TEMPLATE
            )
            csp = self._build_csp(nonce, csp_template)
            response = web.Response(text=content, content_type="text/html")
            return self._add_security_headers(response, csp, allow_frame=embed)
        return web.Response(text="登录页文件缺失", status=500)

    async def _handle_panel_page(self, request: web.Request):
        """返回面板页（需要认证，中间件已验证），使用 nonce-based CSP"""
        try:
            content = self._render_panel_page()
        except Exception:
            return web.Response(text="面板文件读取失败", status=500)
        if content is not None:
            embed = self._is_embed_request(request)
            nonce = self._generate_nonce()
            content = self._inject_nonce(content, nonce)
            csp_template = (
                self._CSP_PANEL_EMBED_TEMPLATE if embed else self._CSP_PANEL_TEMPLATE
            )
            csp = self._build_csp(nonce, csp_template)
            response = web.Response(text=content, content_type="text/html")
            return self._add_security_headers(response, csp, allow_frame=embed)
        return web.Response(text="面板文件缺失", status=500)

    async def _handle_favicon(self, request: web.Request):
        """favicon"""
        logo = Path(__file__).parent.parent / "logo.png"
        if logo.exists():
            return web.FileResponse(logo)
        return web.Response(status=404)

    async def _handle_static_js_utils(self, request: web.Request):
        """返回 utils.js（登录页需要）"""
        js_file = self.static_dir / "js" / "utils.js"
        if js_file.exists():
            return web.FileResponse(
                js_file, headers={"Content-Type": "application/javascript"}
            )
        return web.Response(status=404)

    async def _handle_static_js_api(self, request: web.Request):
        """返回 api.js（登录页需要）"""
        js_file = self.static_dir / "js" / "api.js"
        if js_file.exists():
            return web.FileResponse(
                js_file, headers={"Content-Type": "application/javascript"}
            )
        return web.Response(status=404)

    async def _handle_static_js_bg_animation(self, request: web.Request):
        """返回 bg-animation.js（登录页需要）"""
        js_file = self.static_dir / "js" / "bg-animation.js"
        if js_file.exists():
            return web.FileResponse(
                js_file, headers={"Content-Type": "application/javascript"}
            )
        return web.Response(status=404)

    async def _handle_logo(self, request: web.Request):
        """返回插件 Logo"""
        logo = self.static_dir / "img" / "logo.png"
        if not logo.exists():
            logo = Path(__file__).parent.parent / "logo.png"
        if logo.exists():
            return web.FileResponse(logo)
        return web.Response(status=404)

    def _load_error_page(self, code: str, reason: str = "") -> str:
        """
        加载统一错误页 HTML（从 error.html 模板文件读取）。

        error.html 通过 URL 参数展示错误信息，但作为后备方案，
        此方法也直接将 code/reason 内联到页面，避免二次请求。
        模板内的 JS 会读取自身内嵌的数据（而非 URL 参数），
        保证即使在无法发起额外请求的情况下也能正常显示。

        安全考量：reason 仅作为文本内容展示，不含任何内部路由或代码结构信息。
        """
        import html as html_mod

        error_file = self.template_dir / "error.html"
        try:
            content = error_file.read_text(encoding="utf-8")
            # 将 code 和 reason 注入到模板的占位符中
            safe_reason = html_mod.escape(reason)
            content = content.replace("__ERROR_CODE__", html_mod.escape(code))
            content = content.replace("__ERROR_REASON__", safe_reason)
            return content
        except Exception as e:
            logger.debug(f"🌐 加载 error.html 失败: {e}，使用内联备用页面")
            safe_reason = html_mod.escape(reason)
            return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>访问出错</title>
<style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0f0f1a;color:#e8e8f0;font-family:sans-serif;}}
.box{{text-align:center;max-width:480px;padding:48px 32px;background:#1a1a2e;
border-radius:16px;border:1px solid rgba(255,80,80,0.3);}}
h1{{color:#ff6b6b;}}p{{color:#a0a0b8;line-height:1.8;}}
.icon{{font-size:64px;}}</style></head>
<body><div class="box"><div class="icon">🚫</div>
<h1>访问出错</h1><p>{safe_reason or "请联系管理员。"}</p></div></body></html>"""

    async def _handle_error_page(self, request: web.Request):
        """统一错误/拦截页面（公开路由，无需认证），使用 nonce-based CSP"""
        code = request.rel_url.query.get("code", "error")
        reason = request.rel_url.query.get("reason", "")

        # 若为 blocked 页面，重新检查 IP 是否已解封（直接获取 IP，不依赖中间件注入）
        if code == "blocked":
            ip = self._get_client_ip(request)
            if ip:
                allowed, _ = self.security.check_ip_allowed(ip)
                if allowed:
                    raise web.HTTPFound("/")

        html_content = self._load_error_page(code, reason)
        nonce = self._generate_nonce()
        html_content = self._inject_nonce(html_content, nonce)
        csp = self._build_csp(nonce, self._CSP_ERROR_TEMPLATE)
        response = web.Response(
            text=html_content,
            content_type="text/html",
            status=403 if code == "blocked" else (404 if code == "404" else 400),
        )
        return self._add_security_headers(response, csp)

    def _blocked_page_html(self, ip: str, reason: str) -> str:
        """生成被封禁/拒绝访问的友好 HTML 页面（复用统一错误页模板）"""
        return self._load_error_page("blocked", reason)

    # ==================== 会话 Key 规范化工具 ====================

    @staticmethod
    def _split_compound_key(key: str) -> tuple[str | None, str | None, str | None]:
        """将复合 key 拆为 (platform, chat_type, chat_id)。
        格式: {platform}_{chat_type}_{chat_id}，chat_id 自身可含下划线。
        非复合格式返回 (None, None, key)。
        """
        parts = key.split("_", 2)
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        return None, None, key

    @staticmethod
    def _extract_chat_id(key: str) -> str:
        """从任意格式 key 中提取纯 chat_id。"""
        _, _, chat_id = WebPanelServer._split_compound_key(key)
        return chat_id

    def _build_chat_id_to_compound_map(self) -> dict[str, set[str]]:
        """构建 chat_id → {compound_keys} 的反向映射。

        扫描复合 key 来源（attention/cooldown/frequency/proactive）和文件路径，
        为每个 chat_id 收集所有对应的 compound key。
        用于将纯 chat_id 来源的运行时数据关联到正确的 canonical 会话。
        """
        cid_map: dict[str, set[str]] = {}

        def _add(key: str):
            plat, ctype, cid = self._split_compound_key(key)
            if plat and ctype:
                cid_map.setdefault(cid, set()).add(key)

        # 复合 key 运行时来源
        for key in self._safe_get_attention_map():
            _add(key)
        for key in self._safe_get_proactive_states():
            _add(key)
        if (
            hasattr(self.plugin, "frequency_adjuster")
            and self.plugin.frequency_adjuster
        ):
            if hasattr(self.plugin.frequency_adjuster, "check_states"):
                for key in self.plugin.frequency_adjuster.check_states:
                    _add(key)
        try:
            from ..utils.attention_manager import AttentionManager

            for key in getattr(AttentionManager, "_conversation_activity_map", {}):
                _add(key)
            for key in getattr(AttentionManager, "_fatigue_attention_block", {}):
                _add(key)
        except Exception:
            pass
        try:
            from ..utils.cooldown_manager import CooldownManager

            for key in getattr(CooldownManager, "_cooldown_map", {}):
                _add(key)
            for key in getattr(CooldownManager, "_pending_cooldown_map", {}):
                _add(key)
        except Exception:
            pass

        # 文件来源
        chat_dir = self.data_dir / "chat_history"
        if chat_dir.exists():
            for f in chat_dir.rglob("*.json"):
                try:
                    rel = f.relative_to(chat_dir)
                except ValueError:
                    continue
                parts = rel.parts
                if len(parts) == 3:
                    compound = f"{parts[0]}_{parts[1]}_{f.stem}"
                    cid_map.setdefault(f.stem, set()).add(compound)
                elif len(parts) == 1:
                    cid_map.setdefault(f.stem, set()).add(f.stem)

        return cid_map

    def _collect_all_sessions(self) -> set:
        """从所有数据源收集全部已知会话 ID（保留原始 key 格式）。

        返回的集合同时包含纯 chat_id 和复合 chat_key 两种格式。
        上层调用者根据需要自行规范化。
        """
        sessions = set()
        # 注意力数据
        for key in self._safe_get_attention_map():
            sessions.add(key)
        # 主动对话状态
        for key in self._safe_get_proactive_states():
            sessions.add(key)
        # 主动对话处理中会话
        if hasattr(self.plugin, "proactive_processing_sessions"):
            for key in self.plugin.proactive_processing_sessions:
                sessions.add(key)
        # 处理中会话
        if hasattr(self.plugin, "processing_sessions"):
            for chat_id in self.plugin.processing_sessions.values():
                sessions.add(chat_id)
        # 情绪追踪
        if hasattr(self.plugin, "mood_tracker") and self.plugin.mood_tracker:
            if hasattr(self.plugin.mood_tracker, "moods"):
                for key in self.plugin.mood_tracker.moods:
                    sessions.add(key)
        # 待转存消息缓存
        if hasattr(self.plugin, "pending_messages_cache"):
            for key in self.plugin.pending_messages_cache:
                sessions.add(key)
        # 最近回复缓存
        if hasattr(self.plugin, "recent_replies_cache"):
            for key in self.plugin.recent_replies_cache:
                sessions.add(key)
        # 等待窗口
        if hasattr(self.plugin, "_group_wait_windows"):
            for key in self.plugin._group_wait_windows:
                if isinstance(key, tuple) and len(key) == 2:
                    chat_id, _user_id = key
                    sessions.add(str(chat_id))
        # 频率调整器
        if (
            hasattr(self.plugin, "frequency_adjuster")
            and self.plugin.frequency_adjuster
            and hasattr(self.plugin.frequency_adjuster, "check_states")
        ):
            for key in self.plugin.frequency_adjuster.check_states:
                sessions.add(key)
        # 其他注意力相关运行态
        try:
            from ..utils.attention_manager import AttentionManager

            for key in getattr(AttentionManager, "_conversation_activity_map", {}):
                sessions.add(key)
            for key in getattr(AttentionManager, "_fatigue_attention_block", {}):
                sessions.add(key)
        except Exception:
            pass
        # 冷却运行态
        try:
            from ..utils.cooldown_manager import CooldownManager

            for key in getattr(CooldownManager, "_cooldown_map", {}):
                sessions.add(key)
            for key in getattr(CooldownManager, "_pending_cooldown_map", {}):
                sessions.add(key)
        except Exception:
            pass
        return sessions

    # ==================== 认证 Handler ====================

    async def _handle_login(self, request: web.Request):
        """登录（含暴力破解防护）"""
        ip = self._get_client_ip(request)

        locked, wait_seconds = self.security.check_brute_force(ip)
        if locked:
            logger.warning(
                f"🔒 IP {ip} 因多次密码错误被暂时锁定，需等待 {wait_seconds} 秒"
            )
            request["access_note"] = f"登录失败：已被暂时锁定（需等待{wait_seconds}秒）"
            return web.json_response(
                {
                    "ok": False,
                    "msg": f"密码错误次数过多，请等待 {wait_seconds} 秒后再试",
                    "locked": True,
                    "wait_seconds": wait_seconds,
                },
                status=429,
            )

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        password = body.get("password", "")
        if not password:
            return web.json_response({"ok": False, "msg": "请输入密码"}, status=400)

        device_id = request.cookies.get("gcp_device_id", "") or body.get(
            "device_id", ""
        )
        login_result = self.auth_mgr.login(
            password,
            client_ip=ip if self._ip_bind_check_cached else None,
            device_id=device_id,
            user_agent=request.headers.get("User-Agent", ""),
        )
        if login_result is None:
            result = self.security.record_login_failure(ip)
            action = result.get("action", "recorded")
            attempts = result.get("attempts", 0)
            lock_seconds = result.get("lock_seconds", 0)

            # 构建访问日志附注（平台日志由 security.record_login_failure 统一管理）
            if action == "rate_ban":
                note = (
                    f"登录失败：密码错误（频率异常，第{attempts}次，"
                    f"{result.get('rate_window', 0)}秒内失败{result.get('rate_count', 0)}次，已封禁IP）"
                )
            elif action == "permanent_ban":
                note = f"登录失败：密码错误（第{attempts}次，已达最大阈值，已封禁IP）"
            elif action == "tier_lock":
                note = f"登录失败：密码错误（第{attempts}次，已锁定{lock_seconds}秒）"
            else:
                note = f"登录失败：密码错误（第{attempts}次）"

            request["access_note"] = note

            if result.get("banned"):
                ban_duration = self.security.brute_force_ban_duration
                msg = (
                    "密码错误次数过多，IP 已被封禁"
                    if ban_duration == 0
                    else f"密码错误次数过多，IP 已被封禁 {ban_duration} 秒"
                )
                return web.json_response(
                    {
                        "ok": False,
                        "msg": msg,
                        "locked": True,
                        "wait_seconds": lock_seconds,
                    },
                    status=429,
                )

            if lock_seconds > 0:
                return web.json_response(
                    {
                        "ok": False,
                        "msg": f"密码错误次数过多，请等待 {lock_seconds} 秒后再试",
                        "locked": True,
                        "wait_seconds": lock_seconds,
                    },
                    status=429,
                )
            return web.json_response({"ok": False, "msg": "密码错误"}, status=401)

        self.security.reset_login_failures(ip)
        response = web.json_response(
            {
                "ok": True,
                "password_changed": self.auth_mgr.password_changed,
                "expires_at": login_result["expires_at"],
                "session_id": login_result["session_id"],
                "device_id": login_result["device_id"],
            }
        )
        self._set_auth_cookie(request, response, login_result["token"])
        response.set_cookie(
            "gcp_device_id",
            login_result["device_id"],
            httponly=False,
            samesite="Strict",
            secure=self._is_request_secure(request),
            path="/",
            max_age=365 * 24 * 60 * 60,
        )
        return response

    async def _handle_auth_status(self, request: web.Request):
        """检查密码是否已修改"""
        return web.json_response(
            {
                "ok": True,
                "password_changed": self.auth_mgr.password_changed,
            }
        )

    async def _handle_change_password(self, request: web.Request):
        """修改密码（需要持有有效 token）"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        old_pw = body.get("old_password", "")
        new_pw = body.get("new_password", "")
        if not old_pw or not new_pw:
            return web.json_response(
                {"ok": False, "msg": "请填写旧密码和新密码"}, status=400
            )
        if len(new_pw) < 6:
            return web.json_response({"ok": False, "msg": "新密码至少6位"}, status=400)
        if len(new_pw) > 128:
            return web.json_response({"ok": False, "msg": "新密码过长"}, status=400)

        if not self.auth_mgr.change_password(old_pw, new_pw):
            return web.json_response({"ok": False, "msg": "旧密码错误"}, status=401)

        response = web.json_response(
            {
                "ok": True,
                "msg": "密码修改成功，请重新登录",
                "force_relogin": True,
            }
        )
        self._clear_auth_cookie(request, response)
        return response

    async def _handle_verify(self, request: web.Request):
        """验证当前会话有效性"""
        payload = request.get("user") or {}
        auth_session = request.get("auth_session")
        if auth_session is None and payload.get("sid"):
            auth_session = self.auth_mgr._sessions.get(payload.get("sid"))
        status = self.auth_mgr.build_session_status(
            type("_VerifyResult", (), {"payload": payload, "session": auth_session})()
        )
        return web.json_response(
            {
                "ok": True,
                **status,
                "ip_bind_check_enabled": self._ip_bind_check_cached,
            }
        )

    async def _handle_heartbeat(self, request: web.Request):
        """低频心跳：刷新最近活跃时间并尽快发现会话失效。"""
        # 心跳只更新服务端最近活跃时间，不延长 JWT 24 小时绝对过期。
        # 一旦 token 过期、密码被改、服务端重启或 IP 变化（开启绑定时），
        # 下一个有效心跳会直接返回 401 reason，由前端统一处理重新登录。
        payload = request.get("user") or {}
        sid = payload.get("sid")
        if sid:
            self.auth_mgr.touch_session(sid, heartbeat=True, persist=True)
        auth_session = self.auth_mgr._sessions.get(sid) if sid else None
        status = self.auth_mgr.build_session_status(
            type(
                "_HeartbeatResult", (), {"payload": payload, "session": auth_session}
            )()
        )
        return web.json_response(
            {
                "ok": True,
                **status,
                "ip_bind_check_enabled": self._ip_bind_check_cached,
            }
        )

    async def _handle_logout(self, request: web.Request):
        """登出（仅注销当前会话）"""
        ip = self._get_client_ip(request)
        payload = request.get("user") or {}
        self.auth_mgr.revoke_session(payload.get("sid"), AuthFailureReason.REVOKED)
        logger.info(f"🔑 用户从 {ip} 主动登出")
        response = web.json_response({"ok": True})
        self._clear_auth_cookie(request, response)
        return response

    # ==================== 配置 Handler ====================

    def _load_schema(self) -> dict:
        """加载配置 schema"""
        schema_path = Path(__file__).parent.parent / "_conf_schema.json"
        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _get_config_file_path(self) -> str:
        """获取插件真实配置文件路径（兼容不同 AstrBot 版本）"""
        # 优先从 AstrBotConfig 对象上拿 config_path 属性
        if hasattr(self.plugin.config, "config_path"):
            return self.plugin.config.config_path
        # 回退：手动拼接
        try:
            from astrbot.core.config import get_astrbot_config_path

            config_dir = get_astrbot_config_path()
            return os.path.join(
                config_dir,
                "astrbot_plugin_group_chat_plus_config.json",
            )
        except Exception as e:
            logger.debug(f"🌐 获取配置路径失败，使用默认回退: {e}")
        # 最终回退
        return os.path.join(
            "data",
            "config",
            "astrbot_plugin_group_chat_plus_config.json",
        )

    def _read_config_file(self) -> dict:
        """直接从配置文件读取当前配置"""
        config_path = self._get_config_file_path()
        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"🌐 配置文件不存在: {config_path}")
            return {}
        except Exception as e:
            logger.error(f"🌐 读取配置文件失败: {e}")
            return {}

    def _get_config_file_cached(self) -> dict:
        """缓存配置文件内容，避免单次请求链路反复读盘。"""
        if not hasattr(self, "_config_file_cache"):
            self._config_file_cache = self._read_config_file()
        return dict(self._config_file_cache)

    @staticmethod
    def _is_relative_to(base: Path, target: Path) -> bool:
        """判断目标路径是否位于给定目录内。"""
        try:
            target.relative_to(base)
            return True
        except ValueError:
            return False

    def _is_path_within_root(self, root: Path, target: Path) -> bool:
        """解析符号链接后判断路径是否仍位于指定根目录下。"""
        try:
            real_root = root.resolve()
            real_target = target.resolve()
        except Exception:
            return False
        return self._is_relative_to(real_root, real_target)

    def _get_path_under_root(self, root: Path, rel_path: str) -> Path | None:
        """将相对路径解析到安全根目录下，若越界则返回 None。"""
        if not rel_path or ".." in rel_path or "\\" in rel_path:
            return None
        if not self._SAFE_PATH_RE.match(rel_path):
            return None
        target = root / rel_path
        return target if self._is_path_within_root(root, target) else None

    def _get_known_sessions(self) -> set[str]:
        """收集当前系统已知的会话 ID（运行态 + 历史文件）。"""
        sessions = set()
        sessions.update(str(sid) for sid in self._collect_all_sessions() if sid)

        chat_dir = self.data_dir / "chat_history"
        if chat_dir.exists():
            try:
                for file_path in chat_dir.rglob("*.json"):
                    try:
                        rel = file_path.relative_to(chat_dir)
                    except ValueError:
                        continue
                    parts = rel.parts
                    if len(parts) == 3:
                        sessions.add(f"{parts[0]}_{parts[1]}_{file_path.stem}")
                        sessions.add(file_path.stem)  # 同时添加 chat_id 短键
                    elif len(parts) == 1:
                        sessions.add(file_path.stem)
            except Exception as e:
                logger.debug(f"🌐 收集已知会话失败: {e}")
        return sessions

    def _require_known_session(self, session: str) -> tuple[bool, str]:
        """校验会话名合法且已存在于系统已知会话集合中。"""
        if not session or not _SAFE_SESSION_RE.match(session):
            return False, "无效的会话名称"
        if session not in self._get_known_sessions():
            return False, f"会话不存在: {session}"
        return True, ""

    def _validate_chat_history_message(self, item: Any) -> bool:
        """校验单条聊天记录结构是否兼容 ContextManager 持久化格式。"""
        if not isinstance(item, dict):
            return False
        if set(item.keys()) - self._CHAT_HISTORY_ALLOWED_KEYS:
            return False

        for key, value in item.items():
            if key == "sender":
                if value is None:
                    continue
                if not isinstance(value, dict):
                    return False
                if set(value.keys()) - self._CHAT_HISTORY_ALLOWED_SENDER_KEYS:
                    return False
                if not all(
                    isinstance(v, self._CHAT_HISTORY_SCALAR_TYPES)
                    for v in value.values()
                ):
                    return False
                continue

            if key == "timestamp":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    return False
                continue

            if key in {"group_id"}:
                if not isinstance(value, self._CHAT_HISTORY_SCALAR_TYPES):
                    return False
                continue

            if not isinstance(value, self._CHAT_HISTORY_SCALAR_TYPES):
                return False

        return True

    def _validate_chat_history_messages(self, messages: Any) -> tuple[bool, str]:
        """校验聊天记录数组结构。"""
        if not isinstance(messages, list):
            return False, "messages 必须是数组"
        for index, item in enumerate(messages):
            if not self._validate_chat_history_message(item):
                return False, f"第 {index + 1} 条消息结构不合法"
        return True, ""

    def _normalize_session_scope(self, session: str) -> tuple[str, str | None]:
        """将 session 标识解析为统一的 chat_key 与原始 chat_id。"""
        if not session or not _SAFE_SESSION_RE.match(session):
            return session, None
        parts = session.split("_", 2)
        if len(parts) >= 3:
            platform_name, chat_type, chat_id = parts[0], parts[1], parts[2]
            is_private = chat_type == "private"
            return ProbabilityManager.get_chat_key(
                platform_name, is_private, chat_id
            ), chat_id
        return session, None

    def _resolve_image_cache_file(self) -> Path | None:
        """定位图片描述缓存文件，兼容当前实现与旧版路径。"""
        candidates = [self.data_dir / "image_cache" / "descriptions.jsonl"]
        legacy_path = self.data_dir / "image_description_cache.json"
        if legacy_path not in candidates:
            candidates.append(legacy_path)
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]

    def _clear_image_cache_storage(self) -> bool:
        """仅清理图片描述缓存文件，不影响其他功能文件。"""
        cache_file = self._resolve_image_cache_file()
        if cache_file is None or not cache_file.exists():
            return False
        cache_file.unlink()
        return True

    def _write_config_file(self, config_data: dict) -> bool:
        """直接写入配置文件"""
        config_path = self._get_config_file_path()
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8-sig") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            self._config_file_cache = dict(config_data)
            logger.info(f"🌐 配置已写入: {config_path}")
            return True
        except Exception as e:
            logger.error(f"🌐 写入配置文件失败: {e}")
            return False

    def _build_protected_file_message(self, action: str) -> str:
        """返回受保护文件的统一拒绝提示。"""
        if action == "read":
            return "此文件属于核心安全文件，出于安全考虑不支持在线查看。"
        if action == "save":
            return "此文件属于核心安全文件，不允许通过 Web 端修改。"
        return "此文件属于核心安全文件，不允许通过 Web 端删除。"

    async def _handle_get_config(self, request: web.Request):
        """获取完整配置（从文件读取真实值 + schema）"""
        schema = self._load_schema()
        file_config = self._read_config_file()

        # 用 schema 默认值填充缺失项
        current = {}
        for key in schema:
            if key in file_config:
                current[key] = file_config[key]
            else:
                current[key] = schema[key].get("default")

        return web.json_response(
            {
                "ok": True,
                "schema": schema,
                "config": current,
                "config_file_name": os.path.basename(self._get_config_file_path()),
                "is_desktop": getattr(self.plugin, "is_desktop_mode", False),
                "desktop_info": {
                    "is_desktop": getattr(self.plugin, "is_desktop_mode", False),
                    "mode_setting": getattr(
                        self.plugin, "desktop_mode_setting", "auto"
                    ),
                    "detected_env": current.get("desktop_detected_env", ""),
                },
            }
        )

    async def _handle_put_config(self, request: web.Request):
        """批量更新配置值（直接写入配置文件）"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        updates = body.get("config", {})
        if not updates:
            return web.json_response({"ok": False, "msg": "无更新内容"}, status=400)

        schema = self._load_schema()
        errors = []
        forbidden_keys = []

        # 校验类型
        validated = {}
        for key, value in updates.items():
            if key not in schema:
                errors.append(f"未知配置项: {key}")
                continue
            if key in self._WEB_CONFIG_READONLY_KEYS:
                forbidden_keys.append(key)
                continue
            expected_type = schema[key].get("type", "string")
            if not self._validate_value(value, expected_type):
                errors.append(f"{key}: 类型不匹配，期望 {expected_type}")
                continue
            validated[key] = value

        if forbidden_keys:
            return web.json_response(
                {
                    "ok": False,
                    "msg": "以下配置仅允许在 AstrBot 传统配置界面修改: "
                    + ", ".join(forbidden_keys),
                },
                status=403,
            )

        if errors:
            return web.json_response(
                {"ok": False, "msg": "; ".join(errors)}, status=400
            )

        # 读取当前文件 → 合并修改 → 写回文件
        file_config = self._read_config_file()
        file_config.update(validated)

        if not self._write_config_file(file_config):
            return web.json_response(
                {"ok": False, "msg": "写入配置文件失败"}, status=500
            )

        # 如果安全相关配置发生变化，立即生效（无需重启）
        security_keys = {
            "web_panel_ip_mode",
            "web_panel_ip_list",
            "web_panel_protected_ips",
            "web_panel_anti_spider",
            "web_panel_anti_spider_rate_limit",
            "web_panel_anti_spider_ban_duration",
            "web_panel_ip_bind_check",
            "web_panel_brute_force_window",
            "web_panel_brute_force_rate_window",
            "web_panel_brute_force_rate_count",
            "web_panel_brute_force_tiers",
            "web_panel_brute_force_ban_duration",
        }
        if security_keys & set(validated.keys()):
            self.security.update_config(file_config)
            self._invalidate_trust_proxy_cache()
            logger.info("🔒 安全配置已实时更新")

        return web.json_response(
            {"ok": True, "msg": "配置已保存到文件（需重载插件生效）"}
        )

    def _validate_value(self, value, expected_type: str) -> bool:
        """校验配置值类型"""
        if expected_type == "bool":
            return isinstance(value, bool)
        if expected_type == "int":
            return isinstance(value, (int,)) and not isinstance(value, bool)
        if expected_type == "float":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type in ("string", "text"):
            return isinstance(value, str)
        if expected_type == "list":
            return isinstance(value, list)
        return True

    async def _handle_reload(self, request: web.Request):
        """保存配置并重载插件（非重启 AstrBot）"""
        # 1. 先读取前端传来的最新配置并写入文件
        try:
            body = await request.json()
            updates = body.get("config", {}) if body else {}
        except Exception:
            updates = {}

        if updates:
            schema = self._load_schema()
            file_config = self._read_config_file()
            forbidden_keys = []
            validation_errors = []
            validated_updates = {}
            for key, value in updates.items():
                if key not in schema:
                    validation_errors.append(f"未知配置项: {key}")
                    continue
                if key in self._WEB_CONFIG_READONLY_KEYS:
                    forbidden_keys.append(key)
                    continue
                expected_type = schema[key].get("type", "string")
                if not self._validate_value(value, expected_type):
                    validation_errors.append(f"{key}: 类型不匹配，期望 {expected_type}")
                    continue
                validated_updates[key] = value

            if forbidden_keys:
                return web.json_response(
                    {
                        "ok": False,
                        "msg": "以下配置仅允许在 AstrBot 传统配置界面修改: "
                        + ", ".join(forbidden_keys),
                    },
                    status=403,
                )

            if validation_errors:
                return web.json_response(
                    {"ok": False, "msg": "; ".join(validation_errors)},
                    status=400,
                )

            file_config.update(validated_updates)
            if not self._write_config_file(file_config):
                return web.json_response(
                    {"ok": False, "msg": "写入配置文件失败"}, status=500
                )

        # 2. 延迟重载：先返回响应，再触发插件重载
        # 不能在 handler 中直接 await reload()，因为 reload 会调用
        # terminate() 停止 web 服务器，导致当前 HTTP 连接断开，
        # 后续的 load() 可能永远不会执行（插件只关不开）
        try:
            # 标记本次重启由 Web 面板发起，使 JWT secret 不会被轮换（保持登录态）
            self.auth_mgr.mark_web_initiated_reload()
            self._create_deferred_reload_task()
            msg = "配置已保存，插件正在重载..." if updates else "插件正在重载..."
            logger.info("🌐 Web 面板触发插件重载（延迟执行）...")
            return web.json_response({"ok": True, "msg": msg})
        except Exception as e:
            logger.error(f"🌐 触发插件重载失败: {e}", exc_info=True)
            return web.json_response(
                {
                    "ok": False,
                    "msg": "配置已保存，但重载失败，请手动重启插件。",
                },
                status=500,
            )

    async def _handle_config_download(self, request: web.Request):
        """下载当前配置文件 —— 只读、安全加固、无路径参数

        安全设计：
        - 不接受任何前端传入的路径参数，文件路径由服务端内部确定
        - 仅允许下载插件自身的配置文件，禁止下载其他任何文件
        - 必须通过完整认证流程（JWT + IP 过滤 + 会话校验 + 防爬虫）
        - 只读操作，不提供写入/修改/删除能力
        - 不向前端暴露服务器绝对路径
        - 所有结果均写入 Web 端可查看的访问日志（含成功/失败说明）
        """
        config_path = self._get_config_file_path()
        filename = os.path.basename(config_path)

        # 防御性校验：确保文件名符合预期格式
        if not filename or not (
            filename.endswith("_config.json") or filename.endswith("_config.yaml")
        ):
            logger.warning(f"下载配置文件被拒绝：文件名格式不符合预期 — {filename}")
            request["access_note"] = f"下载配置文件失败：文件名格式异常 ({filename})"
            return web.json_response(
                {"ok": False, "msg": f"配置文件格式异常，无法下载: {filename}"},
                status=403,
            )

        if not os.path.exists(config_path):
            logger.warning(f"下载配置文件失败：文件不存在 — {config_path}")
            request["access_note"] = f"下载配置文件失败：文件不存在 ({filename})"
            return web.json_response(
                {"ok": False, "msg": "配置文件不存在，请检查插件是否正确加载"},
                status=404,
            )

        try:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except PermissionError:
            logger.error(f"下载配置文件失败：权限不足 — {config_path}")
            request["access_note"] = f"下载配置文件失败：权限不足 ({filename})"
            return web.json_response(
                {"ok": False, "msg": "读取配置文件权限不足"},
                status=403,
            )
        except Exception as e:
            logger.error(
                f"下载配置文件失败：读取错误 — {config_path}: {e}", exc_info=True
            )
            request["access_note"] = f"下载配置文件失败：读取错误 ({filename})"
            return web.json_response(
                {"ok": False, "msg": f"读取配置文件失败: {e}"},
                status=500,
            )

        logger.info(f"配置文件下载成功: {filename}")
        request["access_note"] = f"下载配置文件 ({filename})"

        # 以 JSON 返回文件内容，不设 Content-Disposition。
        # 由前端自行构建 Blob 下载，避免 Content-Disposition: attachment
        # 在 fetch 预检阶段干扰浏览器行为。
        return web.json_response(
            {
                "ok": True,
                "filename": filename,
                "content": content,
            }
        )

    # ==================== 延迟重载/重启 ====================

    def _create_deferred_reload_task(self):
        """创建延迟插件重载任务（确保 HTTP 响应先发出）

        任务内部先 sleep 等待响应发送完毕，再通过 AstrBot 仪表盘
        REST API 触发插件重载。使用独立的 HTTP 会话，不受插件
        terminate() 的影响。
        """
        # 在插件被终止前，提前捕获仪表盘连接信息
        host = self.plugin.host
        port = self.plugin.port
        dbc = dict(self.plugin.dbc)
        task = asyncio.ensure_future(self._do_deferred_reload(host, port, dbc))
        # 保持强引用，避免 Python 3.12+ 的 Task GC 警告
        self._deferred_tasks = getattr(self, "_deferred_tasks", set())
        self._deferred_tasks.add(task)
        task.add_done_callback(self._deferred_tasks.discard)

    async def _do_deferred_reload(self, host, port, dbc):
        """延迟执行的插件重载

        优先通过 AstrBot 仪表盘 REST API（公开稳定接口）触发重载，
        降级使用 context._star_manager.reload()（私有属性，可能随版本变动）。
        """
        await asyncio.sleep(1.0)  # 等待 HTTP 响应完全发出

        # ---- 主路径：通过 AstrBot 仪表盘 REST API ----
        try:
            import aiohttp as _aiohttp

            async with _aiohttp.ClientSession() as session:
                # 获取仪表盘认证 token
                login_url = f"http://{host}:{port}/api/auth/login"
                async with session.post(
                    login_url,
                    json={"username": dbc["username"], "password": dbc["password"]},
                ) as resp:
                    data = await resp.json()
                    token = (
                        data.get("data", {}).get("token")
                        if isinstance(data, dict)
                        else None
                    )
                    if not token:
                        raise RuntimeError(f"登录响应格式错误: {data}")

                # 调用仪表盘的插件重载 API
                reload_url = f"http://{host}:{port}/api/plugin/reload"
                async with session.post(
                    reload_url,
                    json={"name": "astrbot_plugin_group_chat_plus"},
                    headers={"Authorization": f"Bearer {token}"},
                ) as resp:
                    data = await resp.json()
                    if data.get("status") == "ok":
                        logger.info("🌐 插件重载成功（通过仪表盘 API）")
                        return
                    else:
                        raise RuntimeError(f"仪表盘返回: {data.get('message', data)}")
        except Exception as e:
            logger.warning(f"🌐 通过仪表盘 API 重载失败: {e}，尝试降级方案...")

        # ---- 降级路径：直接调用 star_manager（私有 API） ----
        try:
            star_manager = self.plugin.context._star_manager
            if star_manager is None:
                raise RuntimeError("无法获取插件管理器")
            success, err_msg = await star_manager.reload(
                "astrbot_plugin_group_chat_plus"
            )
            if success:
                logger.info("🌐 插件重载成功（通过 star_manager 降级）")
            else:
                logger.error(f"🌐 插件重载失败: {err_msg}")
        except Exception as e:
            logger.error(f"🌐 插件重载异常（所有方式均失败）: {e}", exc_info=True)

    def _create_deferred_restart_task(self):
        """创建延迟 AstrBot 重启任务（确保 HTTP 响应先发出）"""
        host = self.plugin.host
        port = self.plugin.port
        dbc = dict(self.plugin.dbc)
        task = asyncio.ensure_future(self._do_deferred_restart(host, port, dbc))
        self._deferred_tasks = getattr(self, "_deferred_tasks", set())
        self._deferred_tasks.add(task)
        task.add_done_callback(self._deferred_tasks.discard)

    async def _do_deferred_restart(self, host, port, dbc):
        """延迟执行的 AstrBot 重启

        桌面端兼容：桌面端进程由 Tauri 托管，HTTP API 触发的 os.execv() 重启
        在 Windows 上实际是新建进程+退出当前，可能导致 Tauri 丢失子进程跟踪。
        """
        await asyncio.sleep(1.0)  # 等待 HTTP 响应完全发出
        is_desktop = getattr(self.plugin, "is_desktop_mode", False)
        if is_desktop:
            logger.warning(
                "🖥️ [桌面端] 通过 Web 面板触发重启。桌面端进程由 Tauri 托管，"
                "如重启后无响应，请通过桌面端托盘菜单手动重启后端。"
            )
        try:
            import aiohttp as _aiohttp

            async with _aiohttp.ClientSession() as session:
                login_url = f"http://{host}:{port}/api/auth/login"
                async with session.post(
                    login_url,
                    json={"username": dbc["username"], "password": dbc["password"]},
                ) as resp:
                    data = await resp.json()
                    token = (
                        data.get("data", {}).get("token")
                        if isinstance(data, dict)
                        else None
                    )
                    if not token:
                        raise RuntimeError(f"登录响应格式错误: {data}")

                restart_url = f"http://{host}:{port}/api/stat/restart-core"
                async with session.post(
                    restart_url,
                    headers={"Authorization": f"Bearer {token}"},
                ) as resp:
                    if resp.status == 200:
                        logger.info("🌐 AstrBot 重启请求已发送")
                    else:
                        raise RuntimeError(f"HTTP {resp.status}")
        except Exception as e:
            logger.warning(f"🌐 通过仪表盘 API 重启失败: {e}，尝试降级...")
            try:
                await self.plugin.restart_core()
            except Exception as e2:
                logger.error(f"🌐 AstrBot 重启异常: {e2}", exc_info=True)

    # ==================== 数据 Handler ====================

    def _safe_get_attention_map(self) -> dict:
        """安全获取注意力数据"""
        try:
            from ..utils.attention_manager import AttentionManager

            return dict(AttentionManager._attention_map)
        except Exception as e:
            logger.debug(f"🌐 获取注意力数据失败: {e}")
            return {}

    def _safe_get_proactive_states(self) -> dict:
        """安全获取主动对话状态"""
        try:
            from ..utils.proactive_chat_manager import ProactiveChatManager

            return dict(ProactiveChatManager._chat_states)
        except Exception as e:
            logger.debug(f"🌐 获取主动对话状态失败: {e}")
            return {}

    def _safe_get_proactive_boost(self) -> dict:
        """安全获取临时概率提升状态"""
        try:
            from ..utils.proactive_chat_manager import ProactiveChatManager

            return dict(ProactiveChatManager._temp_probability_boost)
        except Exception as e:
            logger.debug(f"🌐 获取临时概率提升失败: {e}")
            return {}

    async def _handle_data_sessions(self, request: web.Request):
        """列出所有已知会话，返回 canonical compound key 列表"""
        cid_map = self._build_chat_id_to_compound_map()

        # 规范化为 compound key（复合 key 优先，因为含平台/类型信息且跨平台唯一）
        canonical = set()
        for compounds in cid_map.values():
            canonical.update(compounds)

        # 纯 chat_id 来源若不在 map 中则直接加入
        raw = self._collect_all_sessions()
        for key in raw:
            plat, ctype, cid = self._split_compound_key(key)
            if plat and ctype:
                canonical.add(key)
            elif cid not in cid_map:
                canonical.add(cid)

        return web.json_response({"ok": True, "sessions": sorted(canonical)})

    def _find_in_dict_by_chat_id(self, d: dict, session: str):
        """在 dict 中查找 session，先精确匹配，再按 chat_id 规范化匹配。"""
        if session in d:
            return d[session]
        target_cid = self._extract_chat_id(session)
        for k, v in d.items():
            if self._extract_chat_id(k) == target_cid:
                return v
        return None

    async def _handle_data_attention(self, request: web.Request):
        """获取会话注意力数据"""
        session = request.match_info["session"]
        if not session or not _SAFE_SESSION_RE.match(session):
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)
        _sn = self._safe_num
        attention_map = self._safe_get_attention_map()
        users_data = self._find_in_dict_by_chat_id(attention_map, session) or {}

        result = []
        import time as _time

        now = _time.time()
        for uid, profile in users_data.items():
            if not isinstance(profile, dict):
                continue
            result.append(
                {
                    "user_id": str(uid),
                    "attention_score": _sn(
                        profile.get("attention_score", 0), ndigits=4
                    ),
                    "emotion": _sn(profile.get("emotion", 0), ndigits=4),
                    "interaction_count": profile.get("interaction_count", 0),
                    "last_interaction": profile.get("last_interaction", 0),
                    "idle_seconds": round(
                        now - _sn(profile.get("last_interaction", now))
                    ),
                    "preview": str(profile.get("last_message_preview", "")),
                }
            )

        result.sort(key=lambda x: x["attention_score"], reverse=True)
        return web.json_response({"ok": True, "users": result})

    async def _handle_data_mood(self, request: web.Request):
        """获取会话情绪数据"""
        session = request.match_info["session"]
        if not session or not _SAFE_SESSION_RE.match(session):
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)
        mood_data = {}
        if hasattr(self.plugin, "mood_tracker") and self.plugin.mood_tracker:
            tracker = self.plugin.mood_tracker
            if hasattr(tracker, "moods"):
                raw = self._find_in_dict_by_chat_id(tracker.moods, session)
            else:
                raw = None
            if raw:
                mood_data = {
                    "current_mood": raw.get("mood", "平静"),
                    "intensity": round(raw.get("intensity", 0), 4),
                    "last_update": raw.get("last_update", 0),
                }
        return web.json_response({"ok": True, "mood": mood_data})

    async def _handle_data_probability(self, request: web.Request):
        """获取会话当前概率状态"""
        session = request.match_info["session"]
        if not session or not _SAFE_SESSION_RE.match(session):
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)
        import time as _time

        prob_data = {
            "initial_probability": self.plugin.config.get("initial_probability", 0.3),
            "after_reply_probability": self.plugin.config.get(
                "after_reply_probability", 0.8
            ),
            "probability_duration": self.plugin.config.get("probability_duration", 120),
            "attention_mechanism_enabled": self.plugin.config.get(
                "enable_attention_mechanism", False
            ),
            "mode": "attention"
            if self.plugin.config.get("enable_attention_mechanism", False)
            else "traditional",
        }

        # 传统回复后提升状态（ProbabilityManager 内部按 chat_id 查找，兼容两种格式）
        try:
            probability_status = (
                await ProbabilityManager.get_probability_status_snapshot(session)
            )
            reply_boost_until = probability_status.get("reply_boost_until", 0)
            if reply_boost_until > _time.time():
                prob_data["reply_boost"] = {
                    "value": probability_status.get("reply_boost_probability", 0),
                    "remaining_seconds": round(reply_boost_until - _time.time()),
                    "source": probability_status.get(
                        "reply_boost_source", "after_reply_probability"
                    ),
                }
            base_until = probability_status.get("base_until", 0)
            if base_until > _time.time():
                prob_data["base_override"] = {
                    "value": probability_status.get("base_probability", 0),
                    "remaining_seconds": round(base_until - _time.time()),
                    "source": probability_status.get("base_source", "unknown"),
                }
        except Exception as e:
            logger.debug(f"🌐 概率状态快照读取异常 [{session}]: {e}")

        # 频率调整器状态（复合 key 存储，尝试两种格式匹配）
        if (
            hasattr(self.plugin, "frequency_adjuster")
            and self.plugin.frequency_adjuster
        ):
            fa = self.plugin.frequency_adjuster
            if hasattr(fa, "check_states"):
                state = self._find_in_dict_by_chat_id(fa.check_states, session)
                if state:
                    prob_data["frequency_adjusted_probability"] = state.get(
                        "adjusted_probability"
                    )
                    prob_data["frequency_last_check"] = state.get("last_check_time", 0)

        # 临时概率提升（复合 key 存储，尝试两种格式匹配）
        boost_map = self._safe_get_proactive_boost()
        b = self._find_in_dict_by_chat_id(boost_map, session)
        if b:
            remaining = b.get("boost_until", 0) - _time.time()
            if remaining > 0:
                prob_data["temp_boost"] = {
                    "value": b.get("boost_value", 0),
                    "remaining_seconds": round(remaining),
                }

        return web.json_response({"ok": True, "probability": prob_data})

    async def _handle_data_proactive(self, request: web.Request):
        """获取主动对话统计"""
        states = self._safe_get_proactive_states()
        result = {}
        for chat_key, state in states.items():
            result[chat_key] = {
                "proactive_active": state.get("proactive_active", False),
                "last_proactive_time": state.get("last_proactive_time", 0),
                "consecutive_failures": state.get("consecutive_failures", 0),
                "cooldown_until": state.get("cooldown_until", 0),
                "total_successes": state.get("successful_interactions", 0),
                "total_failures": state.get("failed_interactions", 0),
                "interaction_score": state.get("interaction_score", 50),
            }
        return web.json_response({"ok": True, "proactive": result})

    async def _handle_data_overview(self, request: web.Request):
        """总览仪表盘数据"""
        attention_map = self._safe_get_attention_map()
        proactive_states = self._safe_get_proactive_states()

        total_sessions = len(
            set(list(attention_map.keys()) + list(proactive_states.keys()))
        )
        total_tracked_users = sum(len(v) for v in attention_map.values())
        processing_count = len(getattr(self.plugin, "processing_sessions", {}))

        # 额外全局统计
        total_cached_messages = 0
        if hasattr(self.plugin, "pending_messages_cache"):
            for msgs in self.plugin.pending_messages_cache.values():
                total_cached_messages += len(msgs)

        active_wait_windows = 0
        if hasattr(self.plugin, "_group_wait_windows"):
            active_wait_windows = len(self.plugin._group_wait_windows)

        cooldown_users = 0
        pending_cooldown_users = 0
        try:
            from ..utils.cooldown_manager import CooldownManager

            if hasattr(CooldownManager, "_cooldown_map"):
                for users in CooldownManager._cooldown_map.values():
                    cooldown_users += len(users)
            if hasattr(CooldownManager, "_pending_cooldown_map"):
                for users in CooldownManager._pending_cooldown_map.values():
                    pending_cooldown_users += len(users)
        except Exception:
            pass

        seen_count = len(getattr(self.plugin, "_seen_message_ids", {}))
        duplicate_blocked = len(getattr(self.plugin, "_duplicate_blocked_messages", {}))

        proactive_processing = len(
            getattr(self.plugin, "proactive_processing_sessions", {})
        )

        return web.json_response(
            {
                "ok": True,
                "overview": {
                    "total_sessions": total_sessions,
                    "total_tracked_users": total_tracked_users,
                    "active_processing": processing_count,
                    "proactive_active_count": sum(
                        1
                        for s in proactive_states.values()
                        if s.get("proactive_active")
                    ),
                    "total_cached_messages": total_cached_messages,
                    "active_wait_windows": active_wait_windows,
                    "cooldown_users": cooldown_users,
                    "pending_cooldown_users": pending_cooldown_users,
                    "seen_messages": seen_count,
                    "duplicate_blocked": duplicate_blocked,
                    "proactive_processing": proactive_processing,
                },
            }
        )

    async def _handle_data_status(self, request: web.Request):
        """各功能启用/禁用状态"""
        cfg = self.plugin.config
        return web.json_response(
            {
                "ok": True,
                "status": {
                    "group_chat": cfg.get("enable_group_chat", True),
                    "attention_mechanism": cfg.get("enable_attention_mechanism", False),
                    "mood_system": cfg.get("enable_mood_system", True),
                    "frequency_adjuster": cfg.get("enable_frequency_adjuster", True),
                    "proactive_chat": cfg.get("enable_proactive_chat", False),
                    "typing_simulator": cfg.get("enable_typing_simulator", True),
                    "typo_generator": cfg.get("enable_typo_generator", True),
                    "image_processing": cfg.get("enable_image_processing", False),
                    "memory_injection": cfg.get("enable_memory_injection", False),
                    "humanize_mode": cfg.get("enable_humanize_mode", False),
                    "private_chat": cfg.get("enable_private_chat", False),
                    "dynamic_reply_probability": cfg.get(
                        "enable_dynamic_reply_probability", False
                    ),
                    "dynamic_proactive_probability": cfg.get(
                        "enable_dynamic_proactive_probability", False
                    ),
                    "duplicate_filter": cfg.get("enable_duplicate_filter", True),
                    "conversation_fatigue": cfg.get(
                        "enable_conversation_fatigue", False
                    ),
                    "complaint_system": cfg.get("enable_complaint_system", True),
                    "adaptive_proactive": cfg.get("enable_adaptive_proactive", True),
                },
            }
        )

    @staticmethod
    def _safe_num(val, default=0, ndigits=None):
        """安全转换数值，处理 NaN/Infinity/None 等异常值"""
        import math

        if val is None:
            val = default
        try:
            val = float(val)
        except (TypeError, ValueError):
            return default
        if math.isnan(val) or math.isinf(val):
            return default
        if ndigits is not None:
            return round(val, ndigits)
        return val

    async def _handle_session_detail(self, request: web.Request):
        """获取会话的完整运行时数据"""
        session = request.match_info["session"]
        if not session or not _SAFE_SESSION_RE.match(session):
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)

        try:
            return await self._build_session_detail(session)
        except Exception as e:
            logger.error(f"🌐 获取会话详情 [{session}] 失败: {e}", exc_info=True)
            return web.json_response(
                {"ok": False, "msg": f"获取会话数据时发生内部错误: {e}"},
                status=500,
            )

    async def _build_session_detail(self, session: str):
        """构建会话详情数据（内部实现）"""
        import time as _time

        now = _time.time()
        _sn = self._safe_num
        detail = {"session_id": session}
        # 纯 chat_id 用于匹配仅使用 chat_id 为 key 的数据源
        session_cid = self._extract_chat_id(session)

        # 注意力数据（兼容两种 key 格式）
        try:
            attention_map = self._safe_get_attention_map()
            users_data = self._find_in_dict_by_chat_id(attention_map, session) or {}
            users_list = []
            for uid, profile in users_data.items():
                if not isinstance(profile, dict):
                    continue
                users_list.append(
                    {
                        "user_id": str(uid),
                        "attention_score": _sn(
                            profile.get("attention_score", 0), ndigits=4
                        ),
                        "emotion": _sn(profile.get("emotion", 0), ndigits=4),
                        "interaction_count": profile.get("interaction_count", 0),
                        "last_interaction": profile.get("last_interaction", 0),
                        "idle_seconds": round(
                            now - _sn(profile.get("last_interaction", now))
                        ),
                        "preview": str(profile.get("last_message_preview", "")),
                    }
                )
            users_list.sort(key=lambda x: x["attention_score"], reverse=True)
            detail["attention"] = {
                "user_count": len(users_list),
                "users": users_list,
            }
        except Exception as e:
            logger.debug(f"🌐 会话详情-注意力数据异常 [{session}]: {e}")
            detail["attention"] = {"user_count": 0, "users": []}

        # 情绪数据
        try:
            mood_data = {}
            if hasattr(self.plugin, "mood_tracker") and self.plugin.mood_tracker:
                tracker = self.plugin.mood_tracker
                if hasattr(tracker, "moods"):
                    raw = self._find_in_dict_by_chat_id(tracker.moods, session)
                else:
                    raw = None
                if raw:
                    if isinstance(raw, dict):
                        mood_data = {
                            "current_mood": str(raw.get("mood", "平静")),
                            "intensity": _sn(raw.get("intensity", 0), ndigits=4),
                            "last_update": raw.get("last_update", 0),
                        }
            detail["mood"] = mood_data
        except Exception as e:
            logger.debug(f"🌐 会话详情-情绪数据异常 [{session}]: {e}")
            detail["mood"] = {}

        # 概率数据
        try:
            prob_data = {
                "initial_probability": _sn(
                    self.plugin.config.get("initial_probability", 0.3)
                ),
                "after_reply_probability": _sn(
                    self.plugin.config.get("after_reply_probability", 0.8)
                ),
                "probability_duration": self.plugin.config.get(
                    "probability_duration", 120
                ),
                "attention_mechanism_enabled": self.plugin.config.get(
                    "enable_attention_mechanism", False
                ),
                "mode": "attention"
                if self.plugin.config.get("enable_attention_mechanism", False)
                else "traditional",
            }
            try:
                probability_status = (
                    await ProbabilityManager.get_probability_status_snapshot(session)
                )
                reply_boost_until = _sn(probability_status.get("reply_boost_until", 0))
                if reply_boost_until > now:
                    prob_data["reply_boost"] = {
                        "value": _sn(
                            probability_status.get("reply_boost_probability", 0)
                        ),
                        "remaining_seconds": round(reply_boost_until - now),
                        "source": probability_status.get(
                            "reply_boost_source", "after_reply_probability"
                        ),
                    }
                base_until = _sn(probability_status.get("base_until", 0))
                if base_until > now:
                    prob_data["base_override"] = {
                        "value": _sn(probability_status.get("base_probability", 0)),
                        "remaining_seconds": round(base_until - now),
                        "source": probability_status.get("base_source", "unknown"),
                    }
            except Exception as e:
                logger.debug(f"🌐 会话详情-概率快照异常 [{session}]: {e}")
            if (
                hasattr(self.plugin, "frequency_adjuster")
                and self.plugin.frequency_adjuster
            ):
                fa = self.plugin.frequency_adjuster
                if hasattr(fa, "check_states"):
                    state = self._find_in_dict_by_chat_id(fa.check_states, session)
                    if isinstance(state, dict):
                        prob_data["frequency_adjusted_probability"] = _sn(
                            state.get("adjusted_probability")
                        )
                        prob_data["frequency_last_check"] = state.get(
                            "last_check_time", 0
                        )
            boost_map = self._safe_get_proactive_boost()
            b = self._find_in_dict_by_chat_id(boost_map, session)
            if b and isinstance(b, dict):
                remaining = _sn(b.get("boost_until", 0)) - now
                if remaining > 0:
                    prob_data["temp_boost"] = {
                        "value": _sn(b.get("boost_value", 0)),
                        "remaining_seconds": round(remaining),
                    }
            detail["probability"] = prob_data
        except Exception as e:
            logger.debug(f"🌐 会话详情-概率数据异常 [{session}]: {e}")
            detail["probability"] = {}

        # 主动对话状态（兼容两种 key 格式；仅暴露前端需要的字段，避免泄露内部数据）
        try:
            proactive_states = self._safe_get_proactive_states()
            raw = self._find_in_dict_by_chat_id(proactive_states, session) or {}
            if raw and isinstance(raw, dict):
                cooldown_until = _sn(raw.get("cooldown_until", 0))
                cooldown_remaining = (
                    round(cooldown_until - now) if cooldown_until > now else 0
                )
                proactive_data = {
                    "proactive_active": raw.get("proactive_active", False),
                    "cooldown_remaining": cooldown_remaining,
                    "successful_interactions": raw.get("successful_interactions", 0),
                    "failed_interactions": raw.get("failed_interactions", 0),
                    "interaction_score": _sn(
                        raw.get("interaction_score", 50), ndigits=1
                    ),
                }
            else:
                proactive_data = {}
            detail["proactive"] = proactive_data
        except Exception as e:
            logger.debug(f"🌐 会话详情-主动对话异常 [{session}]: {e}")
            detail["proactive"] = {}

        # 消息缓存详情
        cache_count = 0
        cache_messages = []
        try:
            if hasattr(self.plugin, "pending_messages_cache"):
                cached = self.plugin.pending_messages_cache.get(session_cid, [])
                cache_count = len(cached)
                for m in cached:
                    cache_messages.append(
                        {
                            "role": m.get("role", "unknown"),
                            "content": str(m.get("content", ""))[:100],
                            "timestamp": m.get("timestamp", 0),
                            "sender_name": m.get("sender_name", ""),
                        }
                    )
        except Exception:
            pass
        detail["message_cache_count"] = cache_count
        detail["message_cache"] = cache_messages

        # 处理中状态
        is_processing = False
        try:
            if hasattr(self.plugin, "processing_sessions"):
                is_processing = session_cid in self.plugin.processing_sessions.values()
        except Exception:
            pass
        detail["is_processing"] = is_processing

        # 主动对话处理中
        try:
            detail["proactive_processing"] = session in getattr(
                self.plugin, "proactive_processing_sessions", {}
            ) or session_cid in getattr(
                self.plugin, "proactive_processing_sessions", {}
            )
        except Exception:
            detail["proactive_processing"] = False

        # 等待窗口
        wait_windows = []
        try:
            if hasattr(self.plugin, "_group_wait_windows"):
                for key, winfo in list(self.plugin._group_wait_windows.items()):
                    if not isinstance(key, tuple) or len(key) != 2:
                        continue
                    cid, uid = key
                    if str(cid) in (session, session_cid):
                        wait_windows.append(
                            {
                                "user_id": str(uid),
                                "extra_count": winfo.get("extra_count", 0),
                                "deadline": winfo.get("deadline", 0),
                                "remaining": max(
                                    0,
                                    round(winfo.get("deadline", 0) - now),
                                ),
                            }
                        )
        except Exception:
            pass
        detail["wait_windows"] = wait_windows

        # 冷却状态
        cooldown_users = []
        pending_cooldown_users = []
        try:
            from ..utils.cooldown_manager import CooldownManager
            import time as _time

            if hasattr(CooldownManager, "_cooldown_map"):
                session_cooldowns = CooldownManager._cooldown_map.get(session, {})
                for uid, cinfo in session_cooldowns.items():
                    info = await CooldownManager.get_cooldown_info(session, uid)
                    if info:
                        cooldown_users.append(
                            {
                                "user_id": str(uid),
                                "user_name": cinfo.get("user_name", ""),
                                "remaining": round(_sn(info.get("remaining_time", 0))),
                                "reason": cinfo.get("reason", ""),
                                "phase": "active",
                            }
                        )
            if hasattr(CooldownManager, "_pending_cooldown_map"):
                session_pending = CooldownManager._pending_cooldown_map.get(session, {})
                for uid, pinfo in session_pending.items():
                    pending_cooldown_users.append(
                        {
                            "user_id": str(uid),
                            "user_name": pinfo.get("user_name", ""),
                            "remaining": round(
                                max(
                                    0,
                                    _sn(
                                        CooldownManager.PENDING_COOLDOWN_MAX_WAIT_SECONDS
                                        - (
                                            _time.time() - pinfo.get("pending_start", 0)
                                        ),
                                        0,
                                    ),
                                )
                            ),
                            "reason": pinfo.get("reason", ""),
                            "grace_message_budget": pinfo.get(
                                "grace_message_budget", 0
                            ),
                            "consumed_user_messages": pinfo.get(
                                "consumed_user_messages", 0
                            ),
                            "phase": "pending",
                        }
                    )
        except Exception:
            pass
        detail["cooldowns"] = cooldown_users
        detail["pending_cooldowns"] = pending_cooldown_users

        # 回复密度
        density_data = {}
        try:
            from ..utils.reply_density_manager import ReplyDensityManager

            density_data = ReplyDensityManager.get_density_info(session)
        except Exception:
            pass
        detail["reply_density"] = density_data if isinstance(density_data, dict) else {}

        # 会话活跃度
        activity_data = {}
        try:
            from ..utils.attention_manager import AttentionManager

            act_map = getattr(AttentionManager, "_conversation_activity_map", {})
            if session in act_map:
                raw = act_map[session]
                if isinstance(raw, dict):
                    activity_data = {
                        "activity_score": _sn(raw.get("activity_score", 0), ndigits=4),
                        "last_bot_reply": raw.get("last_bot_reply", 0),
                        "peak_user_id": str(raw.get("peak_user_id", "")),
                        "peak_user_name": str(raw.get("peak_user_name", "")),
                        "peak_attention": _sn(raw.get("peak_attention", 0), ndigits=4),
                    }
        except Exception:
            pass
        detail["conversation_activity"] = activity_data

        # 疲劳锁定
        fatigue_list = []
        try:
            from ..utils.attention_manager import AttentionManager

            fatigue_map = getattr(AttentionManager, "_fatigue_attention_block", {})
            if session in fatigue_map:
                for uid, finfo in fatigue_map[session].items():
                    fatigue_list.append(
                        {
                            "user_id": str(uid),
                            "fatigue_level": finfo.get("fatigue_level", ""),
                            "blocked_at": finfo.get("blocked_at", 0),
                        }
                    )
        except Exception:
            pass
        detail["fatigue_blocks"] = fatigue_list

        # 最近回复缓存
        recent_replies_count = 0
        try:
            if hasattr(self.plugin, "recent_replies_cache"):
                replies = self.plugin.recent_replies_cache.get(session_cid, [])
                recent_replies_count = len(replies)
        except Exception:
            pass
        detail["recent_replies_count"] = recent_replies_count

        # 聊天记录文件信息
        try:
            path = self._get_chat_history_path(session)
            if path and path.exists():
                try:
                    stat = path.stat()
                    detail["chat_history_file"] = {
                        "exists": True,
                        "file_size": stat.st_size,
                        "last_modified": stat.st_mtime,
                    }
                except OSError as e:
                    logger.debug(f"🌐 获取聊天记录文件信息失败 [{path}]: {e}")
                    detail["chat_history_file"] = {"exists": True}
            else:
                detail["chat_history_file"] = {"exists": False}
        except Exception:
            detail["chat_history_file"] = {"exists": False}

        return web.json_response({"ok": True, "detail": detail})

    # ==================== 会话管理 Handler ====================

    def _clear_session_data(self, session: str) -> list:
        """清理指定会话的运行态数据，返回已清理的模块列表"""
        cleared = []
        session_key, chat_id = self._normalize_session_scope(session)

        # 清除注意力数据
        try:
            from ..utils.attention_manager import AttentionManager

            if session in AttentionManager._attention_map:
                del AttentionManager._attention_map[session]
                cleared.append("attention")
            elif session_key in AttentionManager._attention_map:
                del AttentionManager._attention_map[session_key]
                cleared.append("attention")
        except Exception as e:
            logger.warning(f"🌐 清除注意力数据失败: {e}")

        # 清除主动对话状态
        try:
            from ..utils.proactive_chat_manager import ProactiveChatManager

            if session in ProactiveChatManager._chat_states:
                del ProactiveChatManager._chat_states[session]
                cleared.append("proactive_state")
            elif session_key in ProactiveChatManager._chat_states:
                del ProactiveChatManager._chat_states[session_key]
                cleared.append("proactive_state")
            if session in ProactiveChatManager._temp_probability_boost:
                del ProactiveChatManager._temp_probability_boost[session]
                cleared.append("temp_boost")
            elif session_key in ProactiveChatManager._temp_probability_boost:
                del ProactiveChatManager._temp_probability_boost[session_key]
                cleared.append("temp_boost")
        except Exception as e:
            logger.warning(f"🌐 清除主动对话状态失败: {e}")

        # 清除注意力冷却数据
        try:
            from ..utils.cooldown_manager import CooldownManager

            cooldown_hit = False
            for key in {session, session_key}:
                if (
                    key in CooldownManager._cooldown_map
                    or key in CooldownManager._pending_cooldown_map
                ):
                    CooldownManager._cooldown_map.pop(key, None)
                    CooldownManager._pending_cooldown_map.pop(key, None)
                    cooldown_hit = True
            if cooldown_hit:
                cleared.append("cooldown")
        except Exception as e:
            logger.warning(f"🌐 清除冷却数据失败: {e}")

        # 清除情绪数据（支持三种 key 格式）
        if hasattr(self.plugin, "mood_tracker") and self.plugin.mood_tracker:
            if hasattr(self.plugin.mood_tracker, "moods"):
                for key in {session, session_key, chat_id}:
                    if key and key in self.plugin.mood_tracker.moods:
                        del self.plugin.mood_tracker.moods[key]
                        cleared.append("mood")
                        break

        # 清除频率调整器状态（支持三种 key 格式）
        if (
            hasattr(self.plugin, "frequency_adjuster")
            and self.plugin.frequency_adjuster
        ):
            if hasattr(self.plugin.frequency_adjuster, "check_states"):
                for key in {session, session_key, chat_id}:
                    if key and key in self.plugin.frequency_adjuster.check_states:
                        del self.plugin.frequency_adjuster.check_states[key]
                        cleared.append("frequency")
                        break

        # 清除处理中标记
        if hasattr(self.plugin, "processing_sessions"):
            target_ids = {session, session_key}
            if chat_id:
                target_ids.add(chat_id)
            stale_message_ids = [
                message_id
                for message_id, current_chat_id in self.plugin.processing_sessions.items()
                if current_chat_id in target_ids
            ]
            for message_id in stale_message_ids:
                self.plugin.processing_sessions.pop(message_id, None)

        # 清除主动对话处理中标记
        if hasattr(self.plugin, "proactive_processing_sessions"):
            self.plugin.proactive_processing_sessions.pop(session, None)
            self.plugin.proactive_processing_sessions.pop(session_key, None)

        # 清除待转存消息缓存（尝试多种 key 格式）
        if hasattr(self.plugin, "pending_messages_cache"):
            for key in {session, session_key, chat_id}:
                if key and key in self.plugin.pending_messages_cache:
                    del self.plugin.pending_messages_cache[key]
                    cleared.append("pending_messages_cache")

        # 清除最近回复缓存（尝试多种 key 格式）
        if hasattr(self.plugin, "recent_replies_cache"):
            for key in {session, session_key, chat_id}:
                if key and key in self.plugin.recent_replies_cache:
                    del self.plugin.recent_replies_cache[key]
                    cleared.append("recent_replies")

        # 清除等待窗口（key 为 (chat_id, user_id) 元组）
        if hasattr(self.plugin, "_group_wait_windows"):
            target_ids = {session, session_key}
            if chat_id:
                target_ids.add(chat_id)
            stale_windows = [
                wk
                for wk, _ in self.plugin._group_wait_windows.items()
                if isinstance(wk, tuple) and len(wk) >= 1 and str(wk[0]) in target_ids
            ]
            for wk in stale_windows:
                self.plugin._group_wait_windows.pop(wk, None)
            if stale_windows:
                cleared.append("group_wait_windows")

        # 清除对话活跃度映射
        try:
            from ..utils.attention_manager import AttentionManager

            for key in {session, session_key}:
                if key and key in AttentionManager._conversation_activity_map:
                    del AttentionManager._conversation_activity_map[key]
                    cleared.append("conversation_activity")
                    break
            for key in {session, session_key}:
                if key and key in AttentionManager._fatigue_attention_block:
                    del AttentionManager._fatigue_attention_block[key]
                    cleared.append("fatigue_attention_block")
                    break
        except Exception:
            pass

        return cleared

    async def _handle_session_list(self, request: web.Request):
        """列出会话及元数据——使用 compound chat_key 作为 canonical ID。

        不同平台的同一 chat_id 会产生不同的 canonical key，不会错误合并。
        例如 aiocqhttp_group_123456789 和 gewechat_group_123456789 是两个独立的条目。
        """
        sessions: dict[str, dict] = {}

        # 1. 构建 chat_id → compound_keys 映射
        cid_map = self._build_chat_id_to_compound_map()

        # 2. 收集纯 chat_id 运行时数据标记
        raw_runtime = self._collect_all_sessions()
        plain_runtime_cids: set[str] = set()  # 有运行时数据的 chat_id
        for key in raw_runtime:
            plat, ctype, cid = self._split_compound_key(key)
            if plat and ctype:
                pass  # 复合 key，在第 3 步处理
            else:
                plain_runtime_cids.add(cid)

        # 3. 为每个 compound key 创建 canonical 条目
        all_compound_keys: set[str] = set()
        for compounds in cid_map.values():
            all_compound_keys.update(compounds)
        # 也加入运行时中的复合 key（可能未出现在 cid_map 中，例如无文件的新会话）
        for key in raw_runtime:
            plat, ctype, cid = self._split_compound_key(key)
            if plat and ctype:
                all_compound_keys.add(key)

        for ckey in all_compound_keys:
            _, _, cid = self._split_compound_key(ckey)
            has_rt = ckey in raw_runtime or cid in plain_runtime_cids
            if not has_rt and cid in cid_map:
                has_rt = any(ck in raw_runtime for ck in cid_map[cid])
            sessions[ckey] = {
                "message_count": 0,
                "file_size": 0,
                "last_modified": 0,
                "has_file": False,
                "has_runtime_data": has_rt,
            }

        # 4. 纯 chat_id 且无对应 compound key 的孤立运行时条目
        for cid in plain_runtime_cids:
            if cid not in cid_map and cid not in sessions:
                sessions[cid] = {
                    "message_count": 0,
                    "file_size": 0,
                    "last_modified": 0,
                    "has_file": False,
                    "has_runtime_data": True,
                }

        # 5. 扫描文件，按 chat_id 匹配到 canonical 条目
        chat_dir = self.data_dir / "chat_history"
        if chat_dir.exists():
            for f in chat_dir.rglob("*.json"):
                try:
                    rel = f.relative_to(chat_dir)
                except ValueError:
                    continue
                parts = rel.parts
                if len(parts) == 3:
                    compound_key = f"{parts[0]}_{parts[1]}_{f.stem}"
                    file_cid = f.stem
                elif len(parts) == 1:
                    compound_key = f.stem
                    file_cid = f.stem
                else:
                    continue

                # 找到匹配的 canonical 条目（优先精确 compound key 匹配，其次 chat_id 匹配）
                if compound_key in sessions:
                    target_key = compound_key
                elif file_cid in sessions:
                    target_key = file_cid
                elif file_cid in cid_map:
                    # 文件存在但未直接匹配到 canonical 条目；检查其 chat_id
                    # 是否通过复合 key 关联到了运行时数据
                    target_key = compound_key
                    has_rt = file_cid in plain_runtime_cids
                    if not has_rt:
                        for ck in cid_map.get(file_cid, []):
                            if ck in raw_runtime:
                                has_rt = True
                                break
                    sessions.setdefault(
                        target_key,
                        {
                            "message_count": 0,
                            "file_size": 0,
                            "last_modified": 0,
                            "has_file": True,
                            "has_runtime_data": has_rt,
                        },
                    )
                else:
                    target_key = compound_key
                    sessions.setdefault(
                        target_key,
                        {
                            "message_count": 0,
                            "file_size": 0,
                            "last_modified": 0,
                            "has_file": True,
                            "has_runtime_data": False,
                        },
                    )

                try:
                    stat = f.stat()
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    msg_count = len(data) if isinstance(data, list) else 0
                    sessions[target_key].update(
                        {
                            "message_count": msg_count,
                            "file_size": stat.st_size,
                            "last_modified": stat.st_mtime,
                            "has_file": True,
                        }
                    )
                except Exception as e:
                    logger.debug(f"🌐 读取聊天记录文件 {f.name} 失败: {e}")
                    sessions[target_key].update(
                        {
                            "has_file": True,
                            "error": True,
                        }
                    )

        return web.json_response({"ok": True, "sessions": sessions})

    async def _handle_clean_ghost_sessions(self, request: web.Request):
        """清理孤立会话文件（没有对应运行时状态的聊天记录文件）"""
        raw_runtime = self._collect_all_sessions()
        # 规范化为 chat_id 集合以便精确匹配
        in_memory_cids = {self._extract_chat_id(k) for k in raw_runtime}
        chat_dir = self.data_dir / "chat_history"
        if not chat_dir.exists():
            return web.json_response({"ok": True, "msg": "无聊天记录目录"})

        deleted = 0
        skipped_no_runtime = 0
        skipped_path_fail = 0
        total_files = 0
        for f in chat_dir.rglob("*.json"):
            total_files += 1
            try:
                rel = f.relative_to(chat_dir)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) == 3:
                chat_id = f.stem
            elif len(parts) == 1:
                chat_id = f.stem
            else:
                continue
            # 只删除确实没有运行时状态的孤立文件
            if chat_id not in in_memory_cids:
                # 安全检查：确保文件在 chat_history 目录内
                rel_str = rel.as_posix()
                resolved = self._get_path_under_root(chat_dir, rel_str)
                if resolved is None:
                    logger.warning(f"🌐 清理孤立文件路径校验失败: rel={rel_str!r}")
                    skipped_path_fail += 1
                    continue
                if not resolved.exists():
                    logger.warning(f"🌐 清理孤立文件不存在(解析后): {resolved}")
                    skipped_path_fail += 1
                    continue
                try:
                    resolved.unlink()
                    deleted += 1
                    logger.info(f"🌐 已清理孤立会话文件: {rel_str}")
                except Exception as e:
                    logger.warning(f"🌐 清理孤立会话文件失败 {f}: {e}")
            else:
                skipped_no_runtime += 1

        logger.info(
            f"🌐 清理孤立会话完成: total={total_files} deleted={deleted} "
            f"skipped_no_runtime={skipped_no_runtime} skipped_path_fail={skipped_path_fail} "
            f"in_memory_cids={sorted(in_memory_cids)[:20]}"
        )
        return web.json_response(
            {"ok": True, "msg": f"已清理 {deleted} 个孤立会话文件"}
        )

    async def _handle_session_reset(self, request: web.Request):
        """重置会话数据"""
        session = request.match_info["session"]
        session_ok, session_msg = self._require_known_session(session)
        if not session_ok:
            status = 400 if "无效" in session_msg else 404
            return web.json_response({"ok": False, "msg": session_msg}, status=status)
        cleared = self._clear_session_data(session)

        # 同时设置历史截止时间戳
        try:
            from ..utils.context_manager import ContextManager

            # 兼容：以 "_" 或 ":" 分隔
            import re

            parts = re.split(r"[:_]", session)
            chat_id = parts[-1] if len(parts) >= 3 else session
            if chat_id:
                ContextManager.set_history_cutoff(chat_id)
                cleared.append("history_cutoff")
        except Exception as e:
            logger.warning(f"🌐 设置历史截止点失败: {e}")

        return web.json_response(
            {
                "ok": True,
                "msg": f"已清除会话 {session} 的数据",
                "cleared": cleared,
            }
        )

    async def _handle_clear_image_cache(self, request: web.Request):
        """清除图片描述缓存"""
        cleared = self._clear_image_cache_storage()
        return web.json_response(
            {"ok": True, "msg": "图片缓存已清除" if cleared else "无缓存文件"}
        )

    def _get_chat_history_path(self, session: str) -> Path | None:
        """获取聊天记录文件路径（含路径遍历防护）

        支持两种存储结构：
        1. 嵌套目录: chat_history/{platform}/{chat_type}/{chat_id}.json
        2. 平面文件: chat_history/{session}.json（旧兼容）

        当 session 为纯 chat_id 时，会搜索子目录定位文件。
        """
        if not session or not _SAFE_SESSION_RE.match(session):
            return None
        safe_dir = (self.data_dir / "chat_history").resolve()

        # 尝试解析 session 名为嵌套路径:
        # aiocqhttp_group_123456789 → aiocqhttp/group/123456789.json
        parts = session.split("_", 2)
        nested_path = None
        if len(parts) >= 3:
            platform, chat_type, chat_id = parts[0], parts[1], parts[2]
            nested_rel = f"{platform}/{chat_type}/{chat_id}.json"
            nested_path = self._get_path_under_root(safe_dir, nested_rel)
            if nested_path is not None and nested_path.exists():
                return nested_path

        # 兼容：检查平面路径
        flat_path = self._get_path_under_root(safe_dir, f"{session}.json")
        if flat_path is not None and flat_path.exists():
            return flat_path

        # 纯 chat_id 格式：搜索子目录定位文件
        # chat_id 已通过 _SAFE_SESSION_RE 校验，不含 .. 或 /
        if len(parts) < 3 and safe_dir.exists():
            for child in safe_dir.iterdir():
                if not child.is_dir():
                    continue
                for sub in ("group", "private"):
                    candidate = child / sub / f"{session}.json"
                    try:
                        candidate = candidate.resolve()
                        if (
                            self._is_path_within_root(safe_dir, candidate)
                            and candidate.exists()
                        ):
                            return candidate
                    except Exception:
                        continue
            # 纯 chat_id 无已有文件：不返回路径，防止在错误位置创建 flat 文件
            # ContextManager 会在消息首次保存时创建正确的嵌套路径
            return None

        # 文件不存在时，优先返回嵌套路径（与 ContextManager 一致）
        if nested_path is not None:
            return nested_path
        return flat_path

    async def _handle_get_chat_history(self, request: web.Request):
        """查看自定义存储聊天记录"""
        session = request.match_info["session"]
        session_ok, session_msg = self._require_known_session(session)
        if not session_ok:
            status = 400 if "无效" in session_msg else 404
            return web.json_response({"ok": False, "msg": session_msg}, status=status)

        path = self._get_chat_history_path(session)
        if path is None:
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)

        if not path.exists():
            return web.json_response({"ok": True, "messages": []})

        try:
            with open(path, "r", encoding="utf-8") as f:
                messages = json.load(f)
            valid, error_msg = self._validate_chat_history_messages(messages)
            if not valid:
                logger.warning(f"🌐 聊天记录结构异常 [{session}]: {error_msg}")
                return web.json_response(
                    {
                        "ok": False,
                        "msg": "聊天记录文件结构异常，请先在服务器本地检查后再处理",
                    },
                    status=500,
                )
            return web.json_response({"ok": True, "messages": messages})
        except Exception as e:
            logger.error(f"🌐 读取聊天记录 [{session}] 失败: {e}", exc_info=True)
            return web.json_response({"ok": False, "msg": "读取失败"}, status=500)

    async def _handle_put_chat_history(self, request: web.Request):
        """编辑聊天记录"""
        session = request.match_info["session"]
        session_ok, session_msg = self._require_known_session(session)
        if not session_ok:
            status = 400 if "无效" in session_msg else 404
            return web.json_response({"ok": False, "msg": session_msg}, status=status)
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        messages = body.get("messages")
        valid, error_msg = self._validate_chat_history_messages(messages)
        if not valid:
            return web.json_response({"ok": False, "msg": error_msg}, status=400)

        path = self._get_chat_history_path(session)
        if path is None:
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            return web.json_response(
                {
                    "ok": True,
                    "msg": f"已保存 {len(messages)} 条消息",
                }
            )
        except Exception as e:
            logger.error(f"🌐 保存聊天记录 [{session}] 失败: {e}", exc_info=True)
            return web.json_response({"ok": False, "msg": "保存失败"}, status=500)

    async def _handle_get_image_cache(self, request: web.Request):
        """查看图片描述缓存"""
        cache_file = self._resolve_image_cache_file()
        if cache_file is None or not cache_file.exists():
            return web.json_response({"ok": True, "cache": {}, "count": 0})

        try:
            if cache_file.suffix.lower() == ".jsonl":
                cache = {}
                count = 0
                with open(cache_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        url = entry.get("u")
                        desc = entry.get("d")
                        if not url or not desc:
                            continue
                        cache[url] = desc
                        count += 1
                return web.json_response(
                    {
                        "ok": True,
                        "cache": cache,
                        "count": count,
                    }
                )

            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
            return web.json_response(
                {
                    "ok": True,
                    "cache": cache,
                    "count": len(cache) if isinstance(cache, dict) else 0,
                }
            )
        except Exception as e:
            logger.error(f"🌐 读取图片缓存失败: {e}", exc_info=True)
            return web.json_response(
                {"ok": False, "msg": "读取缓存失败，请查看日志"}, status=500
            )

    # ==================== 指令执行 Handler ====================

    async def _handle_cmd_reset(self, request: web.Request):
        """从 Web 端执行 gcp_reset（全局重置）"""
        try:
            body = await request.json()
        except Exception:
            body = {}
        restart_mode = body.get("restart_mode", "reload")

        try:
            if hasattr(self.plugin, "_reset_plugin_data_and_reload"):
                await self.plugin._reset_plugin_data_and_reload()

            if restart_mode == "restart":
                self._create_deferred_restart_task()
                is_desktop = getattr(self.plugin, "is_desktop_mode", False)
                msg = "插件已重置，AstrBot 重启中..."
                if is_desktop:
                    msg += "（桌面端：如重启后无响应，请通过托盘菜单手动重启）"
                return web.json_response(
                    {
                        "ok": True,
                        "msg": msg,
                        "is_desktop": is_desktop,
                    }
                )
            else:
                self.auth_mgr.mark_web_initiated_reload()
                self._create_deferred_reload_task()
                return web.json_response(
                    {
                        "ok": True,
                        "msg": "插件已重置，正在重载...",
                    }
                )
        except Exception as e:
            logger.error(f"🌐 执行 gcp_reset 失败: {e}", exc_info=True)
            return web.json_response(
                {"ok": False, "msg": "执行重置操作失败，请查看日志"}, status=500
            )

    async def _handle_cmd_reset_here(self, request: web.Request):
        """从 Web 端执行 gcp_reset_here（指定会话重置）"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        session_id = body.get("session_id", "")
        restart_mode = body.get("restart_mode", "reload")
        session_ok, session_msg = self._require_known_session(session_id)
        if not session_ok:
            status = 400 if "无效" in session_msg else 404
            return web.json_response({"ok": False, "msg": session_msg}, status=status)

        try:
            cleared = self._clear_session_data(session_id)

            # 提取 chat_id 并设置历史截止时间戳
            try:
                from ..utils.context_manager import ContextManager
                import re

                parts = re.split(r"[:_]", session_id)
                chat_id = parts[-1] if len(parts) >= 3 else session_id
                if chat_id:
                    ContextManager.set_history_cutoff(chat_id)
                    cleared.append("history_cutoff")
            except Exception as e:
                logger.warning(f"🌐 设置历史截止点失败: {e}")

            # 删除会话的聊天历史文件
            history_path = self._get_chat_history_path(session_id)
            if history_path is not None and history_path.exists():
                history_path.unlink()
                cleared.append("chat_history_file")

            if restart_mode == "restart":
                self._create_deferred_restart_task()
                return web.json_response(
                    {
                        "ok": True,
                        "msg": f"会话 {session_id} 已重置，AstrBot 重启中...",
                        "cleared": cleared,
                    }
                )
            else:
                return web.json_response(
                    {
                        "ok": True,
                        "msg": f"会话 {session_id} 已重置",
                        "cleared": cleared,
                    }
                )
        except Exception as e:
            logger.error(f"🌐 执行 gcp_reset_here 失败: {e}", exc_info=True)
            return web.json_response(
                {"ok": False, "msg": "执行会话重置失败，请查看日志"}, status=500
            )

    async def _handle_cmd_clear_image_cache(self, request: web.Request):
        """从 Web 端执行 gcp_clear_image_cache"""
        try:
            body = await request.json()
        except Exception:
            body = {}
        restart_mode = body.get("restart_mode", "reload")

        try:
            count = 0
            if (
                hasattr(self.plugin, "image_description_cache")
                and self.plugin.image_description_cache
            ):
                stats = self.plugin.image_description_cache.get_stats()
                count = stats.get("entry_count", 0)
                self.plugin.image_description_cache.clear()

            cleared_file = self._clear_image_cache_storage()
            if not count and cleared_file:
                count = -1

            if restart_mode == "restart":
                self._create_deferred_restart_task()
                msg = (
                    f"已清除 {count} 条缓存，AstrBot 重启中..."
                    if count >= 0
                    else "图片缓存已清除，AstrBot 重启中..."
                )
                return web.json_response(
                    {
                        "ok": True,
                        "msg": msg,
                    }
                )
            else:
                self.auth_mgr.mark_web_initiated_reload()
                msg = (
                    f"已清除 {count} 条图片描述缓存" if count >= 0 else "图片缓存已清除"
                )
                return web.json_response(
                    {
                        "ok": True,
                        "msg": msg,
                    }
                )
        except Exception as e:
            logger.error(f"🌐 执行 clear_image_cache 失败: {e}", exc_info=True)
            return web.json_response(
                {"ok": False, "msg": "清除缓存失败，请查看日志"}, status=500
            )

    # ==================== 安全管理 Handler ====================

    async def _handle_access_log(self, request: web.Request):
        """获取访问日志"""
        page = int(request.query.get("page", 1))
        size = int(request.query.get("size", 50))
        logs, total = self.security.get_access_logs(page, size)
        return web.json_response(
            {
                "ok": True,
                "logs": logs,
                "total": total,
                "page": page,
            }
        )

    async def _handle_get_bans(self, request: web.Request):
        """获取封禁列表"""
        bans = self.security.get_ban_list()
        return web.json_response({"ok": True, "bans": bans})

    async def _handle_ban_ip(self, request: web.Request):
        """封禁 IP"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        ip = body.get("ip", "")
        duration = body.get("duration")  # None=永久, 数字=秒
        reason = body.get("reason", "手动封禁")

        success, msg = self.security.ban_ip(ip, reason, duration)
        if success:
            logger.info(f"🔒 IP {ip} 已被封禁: {reason}")
        return web.json_response({"ok": success, "msg": msg})

    async def _handle_unban_ip(self, request: web.Request):
        """解封 IP"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        ip = body.get("ip", "")
        if not ip:
            return web.json_response({"ok": False, "msg": "请指定 IP"}, status=400)

        self.security.unban_ip(ip)
        logger.info(f"🔓 IP {ip} 已被解封")
        return web.json_response({"ok": True, "msg": f"已解封 {ip}"})

    async def _handle_update_ban_note(self, request: web.Request):
        """更新封禁备注"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        ip = body.get("ip", "")
        reason = body.get("reason", "")
        if not ip:
            return web.json_response({"ok": False, "msg": "请指定 IP"}, status=400)

        ban = self.security.ban_map.get(ip)
        if ban is None:
            return web.json_response(
                {"ok": False, "msg": f"IP {ip} 不在封禁列表中"}, status=404
            )

        ban.reason = reason
        self.security._save_bans()
        return web.json_response({"ok": True, "msg": "备注已更新"})

    async def _handle_get_ip_config(self, request: web.Request):
        """获取当前 IP 访问控制配置"""
        return web.json_response(
            {
                "ok": True,
                "ip_mode": self.security.ip_mode,
                "ip_list": self.security.ip_list,
                "protected_ips": self.security.protected_ips,
                "ip_bind_check": self._ip_bind_check_cached,
            }
        )

    async def _handle_put_ip_config(self, request: web.Request):
        """更新 IP 访问控制配置（实时生效 + 写入配置文件）"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        ip_mode = body.get("ip_mode")
        ip_list = body.get("ip_list")

        # 受保护 IP 不允许通过 Web 端修改，是底线安全配置
        # 只能通过 AstrBot 传统配置界面修改，防止 Web 面板被攻破后攻击者篡改
        if "protected_ips" in body:
            return web.json_response(
                {
                    "ok": False,
                    "msg": "受保护 IP 名单不可通过 Web 面板修改，请使用 AstrBot 传统配置界面",
                },
                status=403,
            )

        # IP 绑定校验同为安全敏感配置，不允许通过 Web 端修改
        if "ip_bind_check" in body:
            return web.json_response(
                {
                    "ok": False,
                    "msg": "IP 绑定校验配置不可通过 Web 面板修改，请使用 AstrBot 传统配置界面",
                },
                status=403,
            )

        # 校验 ip_mode
        valid_modes = {"disabled", "whitelist", "blacklist"}
        if ip_mode is not None and ip_mode not in valid_modes:
            return web.json_response(
                {"ok": False, "msg": f"ip_mode 必须是 {valid_modes} 之一"},
                status=400,
            )

        # 校验列表类型
        if ip_list is not None and not isinstance(ip_list, list):
            return web.json_response(
                {"ok": False, "msg": "ip_list 必须是数组"}, status=400
            )

        # 读取当前配置文件并更新（不触碰 protected_ips）
        file_config = self._read_config_file()
        if ip_mode is not None:
            file_config["web_panel_ip_mode"] = ip_mode
        if ip_list is not None:
            file_config["web_panel_ip_list"] = ip_list

        if not self._write_config_file(file_config):
            return web.json_response(
                {"ok": False, "msg": "写入配置文件失败"}, status=500
            )

        # 注意：IP 黑白名单配置需重启插件生效（与传统配置项行为统一）
        # 前端在调用此接口后应提示用户重启，或直接调用 /api/config/reload 触发重启
        logger.info("🔒 IP 访问控制配置已写入文件（需重启插件生效）")

        return web.json_response(
            {
                "ok": True,
                "msg": "IP 访问控制配置已保存，重启插件后生效",
            }
        )

    # ==================== 文件管理 Handler ====================

    # 安全路径校验正则：仅允许安全字符
    _SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_\-!./]+$")

    # 敏感文件：禁止在 Web 端读取、编辑、删除
    _SENSITIVE_FILES = {"auth.json", "jwt_secret.json", "sessions.json", "bans.json"}

    _PROTECTED_PATTERNS = ("access_log",)
    _TEXT_FILE_SUFFIXES = {
        ".json",
        ".jsonl",
        ".txt",
        ".log",
        ".md",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
        ".toml",
        ".csv",
        ".env",
    }

    def _validate_file_path(self, rel_path: str) -> Path | None:
        """校验文件路径安全性，返回绝对路径或 None

        - 禁止 .. 路径遍历
        - 必须在数据目录内
        - 仅允许安全字符
        """
        return self._get_path_under_root(self.data_dir, rel_path)

    def _is_protected_file(self, filename: str) -> bool:
        """检查文件名是否属于受保护的敏感文件（大小写不敏感，防止 NTFS 大小写绕过）"""
        lower = filename.lower()
        if lower in self._SENSITIVE_FILES:
            return True
        return any(lower.startswith(p) for p in self._PROTECTED_PATTERNS)

    def _is_probably_text_file(self, target: Path) -> bool:
        """判断文件是否适合在线文本查看/编辑"""
        if target.suffix.lower() in self._TEXT_FILE_SUFFIXES:
            return True
        try:
            with open(target, "rb") as f:
                chunk = f.read(4096)
        except Exception:
            return False
        if not chunk:
            return True
        if b"\x00" in chunk:
            return False
        try:
            chunk.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    def _build_file_capabilities(self, target: Path) -> dict:
        """根据文件类型和保护规则生成前端可用能力（含符号链接绕过防护）"""
        is_protected = self._is_protected_file(target.name)
        if not is_protected:
            # 防止符号链接绕过：检查 resolve 后的真实文件名
            try:
                resolved = target.resolve()
                if resolved.name != target.name:
                    is_protected = self._is_protected_file(resolved.name)
            except Exception:
                pass
        is_json = target.suffix.lower() == ".json"
        is_text = False if is_protected else self._is_probably_text_file(target)
        can_read = not is_protected and is_text
        can_edit = can_read
        can_delete = not is_protected
        status = (
            "protected" if is_protected else ("editable" if can_edit else "delete_only")
        )
        return {
            "protected": is_protected,
            "is_json": is_json,
            "is_text": is_text,
            "can_read": can_read,
            "can_edit": can_edit,
            "can_delete": can_delete,
            "status": status,
        }

    async def _handle_file_list(self, request: web.Request):
        """列出数据目录下所有文件"""
        data_dir = self.data_dir
        files = []

        if not data_dir.exists():
            return web.json_response({"ok": True, "files": []})

        try:
            for item in sorted(data_dir.rglob("*")):
                if not item.is_file():
                    continue
                # 跳过 __pycache__ 等
                rel = item.relative_to(data_dir)
                if any(p.startswith("__") for p in rel.parts):
                    continue
                try:
                    stat = item.stat()
                    capabilities = self._build_file_capabilities(item)
                    files.append(
                        {
                            "path": str(rel).replace("\\", "/"),
                            "name": item.name,
                            "directory": str(rel.parent).replace("\\", "/")
                            if str(rel.parent) != "."
                            else "",
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                            **capabilities,
                        }
                    )
                except OSError as e:
                    logger.debug(f"🌐 获取文件 {item} 信息失败: {e}")
                    continue
        except Exception as e:
            logger.warning(f"🌐 扫描数据目录失败: {e}")

        return web.json_response({"ok": True, "files": files})

    async def _handle_file_read(self, request: web.Request):
        """读取指定文件内容"""
        rel_path = request.query.get("path", "")
        target = self._validate_file_path(rel_path)
        if target is None:
            return web.json_response({"ok": False, "msg": "无效的文件路径"}, status=400)
        if not target.exists():
            return web.json_response({"ok": False, "msg": "文件不存在"}, status=404)

        capabilities = self._build_file_capabilities(target)
        if not capabilities["can_read"]:
            if capabilities["protected"]:
                logger.warning(f"🌐 已拒绝读取受保护文件: {rel_path}")
                return web.json_response(
                    {
                        "ok": False,
                        "msg": self._build_protected_file_message("read"),
                    },
                    status=403,
                )
            return web.json_response(
                {"ok": False, "msg": "此文件不是可在线查看的文本文件"},
                status=415,
            )

        try:
            size = target.stat().st_size
            if size > 5 * 1024 * 1024:
                return web.json_response(
                    {"ok": False, "msg": "文件过大（超过 5MB），无法在线查看"},
                    status=413,
                )
        except OSError as e:
            logger.debug(f"🌐 获取文件大小失败 [{target}]: {e}")

        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
            parsed = None
            if capabilities["is_json"]:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    pass
            return web.json_response(
                {
                    "ok": True,
                    "path": rel_path,
                    "content": content,
                    "parsed": parsed,
                    **capabilities,
                }
            )
        except UnicodeDecodeError:
            return web.json_response(
                {"ok": False, "msg": "文件非文本格式，无法读取"},
                status=415,
            )
        except Exception as e:
            logger.error(f"🌐 读取文件失败 [{rel_path}]: {e}", exc_info=True)
            return web.json_response({"ok": False, "msg": "读取文件失败"}, status=500)

    async def _handle_file_save(self, request: web.Request):
        """保存文件内容"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        rel_path = body.get("path", "")
        content = body.get("content", "")
        target = self._validate_file_path(rel_path)

        if target is None:
            return web.json_response({"ok": False, "msg": "无效的文件路径"}, status=400)
        if target.exists() and not target.is_file():
            return web.json_response(
                {"ok": False, "msg": "目标路径不是普通文件"}, status=400
            )

        capabilities = self._build_file_capabilities(target)
        if not capabilities["can_edit"]:
            if capabilities["protected"]:
                logger.warning(f"🌐 已拒绝修改受保护文件: {rel_path}")
                return web.json_response(
                    {"ok": False, "msg": self._build_protected_file_message("save")},
                    status=403,
                )
            return web.json_response(
                {"ok": False, "msg": "此文件不是可在线编辑的文本文件"},
                status=403,
            )

        parsed = None
        if capabilities["is_json"]:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                return web.json_response(
                    {"ok": False, "msg": f"JSON 格式错误: {e}"}, status=400
                )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                if capabilities["is_json"]:
                    json.dump(parsed, f, ensure_ascii=False, indent=2)
                else:
                    f.write(content)
            logger.info(f"🌐 文件已保存: {rel_path}")
            return web.json_response(
                {
                    "ok": True,
                    "msg": f"文件已保存: {rel_path}",
                    **capabilities,
                }
            )
        except Exception as e:
            logger.error(f"🌐 保存文件失败 [{rel_path}]: {e}", exc_info=True)
            return web.json_response({"ok": False, "msg": "保存文件失败"}, status=500)

    async def _handle_file_delete(self, request: web.Request):
        """删除文件"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        rel_path = body.get("path", "")
        target = self._validate_file_path(rel_path)

        if target is None:
            return web.json_response({"ok": False, "msg": "无效的文件路径"}, status=400)
        if not target.exists():
            return web.json_response({"ok": False, "msg": "文件不存在"}, status=404)
        # 禁止删除认证和封禁文件（含符号链接绕过防护）
        protected = self._is_protected_file(target.name)
        if not protected:
            try:
                resolved = target.resolve()
                if resolved.name != target.name:
                    protected = self._is_protected_file(resolved.name)
            except Exception:
                pass
        if protected:
            logger.warning(f"🌐 已拒绝删除受保护文件: {rel_path}")
            return web.json_response(
                {"ok": False, "msg": self._build_protected_file_message("delete")},
                status=403,
            )

        try:
            target.unlink()
            logger.info(f"🌐 文件已删除: {rel_path}")
            return web.json_response(
                {
                    "ok": True,
                    "msg": f"文件已删除: {rel_path}",
                }
            )
        except Exception as e:
            logger.error(f"🌐 删除文件失败 [{rel_path}]: {e}", exc_info=True)
            return web.json_response({"ok": False, "msg": "删除文件失败"}, status=500)
