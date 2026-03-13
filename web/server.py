"""
Web 配置面板 - aiohttp 服务器核心
"""

import os
import re
import json
import socket
import asyncio
from pathlib import Path
from aiohttp import web
from astrbot.api import logger

from .auth import AuthManager
from .security import SecurityManager

# 合法 session 名称：仅允许字母、数字、下划线、短横线、点号、感叹号
# 禁止 .. / \ 等路径遍历字符
_SAFE_SESSION_RE = re.compile(r"^[A-Za-z0-9_\-!.]+$")


class WebPanelServer:
    """Web 配置面板服务器"""

    def __init__(self, plugin, host="0.0.0.0", port=1451):
        self.plugin = plugin
        self.host = host
        self.port = port
        self.runner = None
        self._task = None

        # 获取插件数据目录
        self.data_dir = self._get_data_dir()

        # 初始化认证管理器
        self.auth_mgr = AuthManager(self.data_dir)

        # 每次插件重载/重启时轮换 JWT secret（web端发起的除外）
        skipped = self.auth_mgr.rotate_jwt_secret()
        if not skipped:
            logger.info("🔑 JWT secret 已轮换，所有旧登录会话已失效")

        # 初始化安全管理器
        self.security = SecurityManager(
            config=self._read_security_config(),
            data_dir=self.data_dir,
        )

        # 启动日志自动清理（异步任务）
        self._log_cleaner_task = None

        # 静态文件目录
        self.static_dir = Path(__file__).parent / "static"
        self.template_dir = Path(__file__).parent / "templates"

        # 创建 aiohttp 应用
        self.app = web.Application(middlewares=[self._auth_middleware])
        self._setup_routes()

    def _get_data_dir(self) -> str:
        """获取插件数据目录"""
        try:
            from astrbot.core.star.star_tools import StarTools

            return StarTools.get_data_dir("astrbot_plugin_group_chat_plus")
        except Exception:
            # 回退：使用插件目录下的 data 子目录
            fallback = Path(__file__).parent.parent / "web_data"
            fallback.mkdir(parents=True, exist_ok=True)
            return str(fallback.parent)

    def _get_data_path(self) -> Path:
        """获取插件数据目录 Path 对象"""
        try:
            from astrbot.core.star.star_tools import StarTools

            return Path(StarTools.get_data_dir("astrbot_plugin_group_chat_plus"))
        except Exception:
            return Path(__file__).parent.parent / "web_data"

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
            "web_panel_ip_bind_check": file_config.get("web_panel_ip_bind_check", True),
        }

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
            # X-Real-IP 优先（单层代理更准确）
            real_ip = request.headers.get("X-Real-IP", "").strip()
            if real_ip:
                return real_ip
            # X-Forwarded-For 取第一个（最原始客户端）
            xff = request.headers.get("X-Forwarded-For", "").strip()
            if xff:
                return xff.split(",")[0].strip()

        return peer_ip

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
        "/api/auth/change-password",  # 首次登录改密（需携带 token，但允许在此白名单以支持登录页 fetch）
    }

    # ---- 面板专用静态资源路径（需要 JWT 认证才能访问） ----
    _PANEL_STATIC_PREFIX = "/panel/static/"

    # ---- 面板主页（需要 JWT 认证） ----
    _PANEL_PAGE = "/panel"

    # ---- 安全响应头 ----
    _SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
    }

    # ---- 登录页允许的宽松 CSP（只含基础样式和登录逻辑）----
    _CSP_LOGIN = (
        "default-src 'none'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "form-action 'none'; "
        "frame-ancestors 'none';"
    )

    # ---- 面板页 CSP（允许内联脚本/样式供现有 JS 正常运行）----
    _CSP_PANEL = (
        "default-src 'none'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "form-action 'none'; "
        "frame-ancestors 'none';"
    )

    def _add_security_headers(
        self, response: web.Response, csp: str = None
    ) -> web.Response:
        """向响应添加安全头"""
        for k, v in self._SECURITY_HEADERS.items():
            response.headers[k] = v
        if csp:
            response.headers["Content-Security-Policy"] = csp
        return response

    @web.middleware
    async def _auth_middleware(self, request: web.Request, handler):
        """安全中间件：路径校验 → robots.txt → 防爬虫 → IP 过滤 → JWT 认证（含 IP 绑定）"""
        ip = self._get_client_ip(request)
        path = request.path
        user_agent = request.headers.get("User-Agent", "")

        # 0. 路径安全校验：拒绝包含路径遍历序列的请求
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

        # 1. 登录页公开静态资源（仅 main.css、login.css、utils.js、api.js）直接放行
        _LOGIN_PUBLIC_STATIC = (
            "/static/css/main.css",
            "/static/css/login.css",
            "/static/js/utils.js",
            "/static/js/api.js",
        )
        if path in _LOGIN_PUBLIC_STATIC:
            response = await handler(request)
            return self._add_security_headers(response, self._CSP_LOGIN)

        # 2. 面板专用静态资源（JS/CSS）—— 需要 Bearer token 或从 /panel 页跳转
        if path.startswith(self._PANEL_STATIC_PREFIX):
            token = self._extract_token(request)
            if not token:
                self.security.log_access(
                    ip, request.method, path, 403, note="未授权访问面板静态资源"
                )
                return web.Response(status=403, text="Forbidden")
            verify_ip = ip if self._ip_bind_check_cached else None
            payload = self.auth_mgr.verify_token(token, current_ip=verify_ip)
            if payload is None:
                self.security.log_access(
                    ip, request.method, path, 403, note="无效 token 访问面板静态资源"
                )
                return web.Response(status=403, text="Forbidden")
            request["user"] = payload
            request["client_ip"] = ip
            response = await handler(request)
            self.security.log_access(ip, request.method, path, response.status)
            return self._add_security_headers(response)

        # 3. 其余 /static/ 路径（登录页以外）一律拒绝直接访问
        if path.startswith("/static/") and path not in _LOGIN_PUBLIC_STATIC:
            self.security.log_access(
                ip, request.method, path, 403, note="拒绝直接访问内部静态资源"
            )
            return web.Response(status=403, text="Forbidden")

        # 4. robots.txt - 直接返回，无需认证、无需 IP 检查
        if path == "/robots.txt":
            return web.Response(
                text=self.security.get_robots_txt(),
                content_type="text/plain",
            )

        # 5. IP 访问控制（黑白名单 + 封禁检查）
        # 优先级：① 受保护 IP → ② 黑白名单 → ③ 封禁列表
        # 白名单命中的 IP 直接放行，不再经过封禁检查（封禁对白名单 IP 无效）
        allowed, reason = self.security.check_ip_allowed(ip)
        if not allowed:
            self.security.log_access(ip, request.method, path, 403)
            # 对非 API 请求返回友好的错误页面
            if not path.startswith("/api/"):
                return web.Response(
                    text=self._load_error_page("blocked", reason),
                    content_type="text/html",
                    status=403,
                )
            return web.json_response(
                {"ok": False, "msg": reason, "blocked": True}, status=403
            )

        # 6. 防爬虫检测（在 IP 放行后执行，受保护 IP 和白名单 IP 已在上一步被放行）
        # 已认证用户（持有有效 JWT）跳过防爬虫检测，避免自动刷新轮询被误判
        _skip_spider = False
        if self.security.anti_spider_enabled:
            token = self._extract_token(request)
            if token:
                payload = self.auth_mgr.verify_token(token, current_ip=ip)
                if payload is not None:
                    _skip_spider = True

        if self.security.anti_spider_enabled and not _skip_spider:
            is_spider, spider_reason = self.security.check_spider(ip, path, user_agent)
            if is_spider:
                note = self.security.get_auto_ban_note(spider_reason)
                self.security.auto_ban_spider(ip, spider_reason)
                self.security.log_access(ip, request.method, path, 403, note=note)
                if not path.startswith("/api/"):
                    return web.Response(
                        text=self._load_error_page(
                            "blocked", f"[防爬虫] {spider_reason}"
                        ),
                        content_type="text/html",
                        status=403,
                    )
                return web.json_response(
                    {"ok": False, "msg": "访问被拒绝", "blocked": True}, status=403
                )

        # 7. 公开路径 - 记录日志但不需认证
        if path in self._PUBLIC_PATHS:
            response = await handler(request)
            self.security.log_access(ip, request.method, path, response.status)
            # 登录页附加安全头
            if path == "/":
                return self._add_security_headers(response, self._CSP_LOGIN)
            return response

        # 8. 面板页（/panel）- 需要 JWT 认证，认证失败重定向到登录页
        if path == self._PANEL_PAGE:
            token = self._extract_token(request)
            if not token:
                return web.HTTPFound("/")
            verify_ip = ip if self._ip_bind_check_cached else None
            payload = self.auth_mgr.verify_token(token, current_ip=verify_ip)
            if payload is None:
                return web.HTTPFound("/")
            request["user"] = payload
            request["client_ip"] = ip
            response = await handler(request)
            self.security.log_access(ip, request.method, path, response.status)
            return self._add_security_headers(response, self._CSP_PANEL)

        # 9. 其他所有路径 - JWT 认证（含 IP 绑定校验）
        token = self._extract_token(request)
        if not token:
            self.security.log_access(ip, request.method, path, 401)
            # HTML 页面请求重定向到登录页
            if not path.startswith("/api/"):
                return web.HTTPFound("/")
            return web.json_response({"ok": False, "msg": "未登录"}, status=401)

        verify_ip = ip if self._ip_bind_check_cached else None
        payload = self.auth_mgr.verify_token(token, current_ip=verify_ip)
        if payload is None:
            self.security.log_access(ip, request.method, path, 401)
            # 区分 IP 变更和 token 过期/失效两种情况
            token_payload_no_ip = self.auth_mgr.verify_token(token, current_ip=None)
            if not path.startswith("/api/"):
                return web.HTTPFound("/")
            if token_payload_no_ip is not None:
                return web.json_response(
                    {
                        "ok": False,
                        "msg": "您的 IP 地址已变更，为安全起见请重新登录",
                        "reason": "ip_changed",
                    },
                    status=401,
                )
            else:
                return web.json_response(
                    {
                        "ok": False,
                        "msg": "登录已过期，请重新登录",
                        "reason": "token_expired",
                    },
                    status=401,
                )

        request["user"] = payload
        request["client_ip"] = ip
        response = await handler(request)
        self.security.log_access(ip, request.method, path, response.status)
        if path.startswith("/api/"):
            self._add_security_headers(response)
        return response

    def _extract_token(self, request: web.Request) -> str | None:
        """从 Authorization 头或 Cookie 中提取 JWT token"""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        # 从 Cookie 中读取（面板页跳转时用）
        token = request.cookies.get("gcp_token", "")
        return token if token else None

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
        r.add_post("/api/auth/logout", self._handle_logout)

        # 配置
        r.add_get("/api/config", self._handle_get_config)
        r.add_put("/api/config", self._handle_put_config)
        r.add_post("/api/config/reload", self._handle_reload)

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

    async def _handle_login_page(self, request: web.Request):
        """返回登录页（公开，无需认证）"""
        login_file = self.template_dir / "login.html"
        if login_file.exists():
            response = web.FileResponse(login_file)
            return self._add_security_headers(response, self._CSP_LOGIN)
        return web.Response(text="登录页文件缺失", status=500)

    async def _handle_panel_page(self, request: web.Request):
        """返回面板页（需要认证，中间件已验证）"""
        panel_file = self.template_dir / "panel.html"
        if panel_file.exists():
            response = web.FileResponse(panel_file)
            return self._add_security_headers(response, self._CSP_PANEL)
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
            # 备用内联页面（error.html 不存在时的兜底）
            safe_reason = html_mod.escape(reason)
            return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>访问出错</title>
<style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0f0f1a;color:#e8e8f0;font-family:sans-serif;}}
.box{{text-align:center;max-width:480px;padding:48px 32px;background:#1a1a2e;
border-radius:16px;border:1px solid rgba(255,80,80,0.3);}}
h1{{color:#ff6b6b;}}p{{color:#a0a0b8;line-height:1.8;}}</style></head>
<body><div class="box"><div style="font-size:64px">🚫</div>
<h1>访问出错</h1><p>{safe_reason or "请联系管理员。"}</p></div></body></html>"""

    async def _handle_error_page(self, request: web.Request):
        """
        统一错误/拦截页面（公开路由，无需认证）。
        通过 URL 参数 code 区分错误类型，reason 说明具体原因。
        页面内容不含任何内部代码结构信息，保障安全性。
        """
        code = request.rel_url.query.get("code", "error")
        reason = request.rel_url.query.get("reason", "")
        html_content = self._load_error_page(code, reason)
        return web.Response(
            text=html_content,
            content_type="text/html",
            status=403 if code == "blocked" else (404 if code == "404" else 400),
        )

    def _blocked_page_html(self, ip: str, reason: str) -> str:
        """生成被封禁/拒绝访问的友好 HTML 页面（复用统一错误页模板）"""
        return self._load_error_page("blocked", reason)

    def _collect_all_sessions(self) -> set:
        """从所有数据源收集全部已知会话 ID"""
        sessions = set()
        # 注意力数据
        for key in self._safe_get_attention_map():
            sessions.add(key)
        # 主动对话状态
        for key in self._safe_get_proactive_states():
            sessions.add(key)
        # 处理中会话
        if hasattr(self.plugin, "processing_sessions"):
            for key in self.plugin.processing_sessions:
                sessions.add(key)
        # 情绪追踪
        if hasattr(self.plugin, "mood_tracker") and self.plugin.mood_tracker:
            if hasattr(self.plugin.mood_tracker, "moods"):
                for key in self.plugin.mood_tracker.moods:
                    sessions.add(key)
        # 待转存消息缓存
        if hasattr(self.plugin, "pending_messages_cache"):
            for key in self.plugin.pending_messages_cache:
                sessions.add(key)
        # 频率调整器
        if (
            hasattr(self.plugin, "frequency_adjuster")
            and self.plugin.frequency_adjuster
            and hasattr(self.plugin.frequency_adjuster, "check_states")
        ):
            for key in self.plugin.frequency_adjuster.check_states:
                sessions.add(key)
        return sessions

    # ==================== 认证 Handler ====================

    async def _handle_login(self, request: web.Request):
        """登录（含暴力破解防护）"""
        ip = self._get_client_ip(request)

        # 暴力破解检查
        locked, wait_seconds = self.security.check_brute_force(ip)
        if locked:
            logger.warning(
                f"🔒 IP {ip} 因多次密码错误被暂时锁定，需等待 {wait_seconds} 秒"
            )
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

        token = self.auth_mgr.login(
            password, client_ip=ip if self._ip_bind_check_cached else None
        )
        if token is None:
            self.security.record_login_failure(ip)
            tracker = self.security.brute_force.get(ip)
            attempts = tracker.attempts if tracker else 0
            if attempts >= 5:
                logger.warning(f"🔒 IP {ip} 密码错误第 {attempts} 次，可能遭受暴力破解")
            return web.json_response({"ok": False, "msg": "密码错误"}, status=401)

        # 登录成功，重置失败计数
        self.security.reset_login_failures(ip)
        return web.json_response(
            {
                "ok": True,
                "token": token,
                "password_changed": self.auth_mgr.password_changed,
            }
        )

    async def _handle_auth_status(self, request: web.Request):
        """检查密码是否已修改"""
        return web.json_response(
            {
                "ok": True,
                "password_changed": self.auth_mgr.password_changed,
            }
        )

    async def _handle_change_password(self, request: web.Request):
        """修改密码（需要持有有效 token，通过 Authorization 头传入）"""
        ip = self._get_client_ip(request)

        # 验证调用者持有有效 token（防止无 token 时调用）
        token = self._extract_token(request)
        if not token or not self.auth_mgr.verify_token(token, current_ip=ip):
            return web.json_response({"ok": False, "msg": "请先登录"}, status=401)

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

        # 密码修改成功，auth_mgr内部已轮换 jwt_secret，导致所有其他端或旧 token 失效
        # 此时不再直接登录并返回新 token，而是通过清除当前响应的 Cookie 让所有设备都必须重新登录
        response = web.json_response({"ok": True})
        response.del_cookie("gcp_token")
        return response

    async def _handle_verify(self, request: web.Request):
        """验证 Token 有效性（已通过中间件即有效）"""
        return web.json_response({"ok": True})

    async def _handle_logout(self, request: web.Request):
        """登出（清除客户端 token，服务端记录日志）"""
        ip = self._get_client_ip(request)
        logger.info(f"🔑 用户从 {ip} 主动登出")
        response = web.json_response({"ok": True})
        # 清除 Cookie（如有设置）
        response.del_cookie("gcp_token")
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

    def _write_config_file(self, config_data: dict) -> bool:
        """直接写入配置文件"""
        config_path = self._get_config_file_path()
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8-sig") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"🌐 配置已写入: {config_path}")
            return True
        except Exception as e:
            logger.error(f"🌐 写入配置文件失败: {e}")
            return False

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
                "config_path": self._get_config_file_path(),
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

        # 校验类型
        validated = {}
        for key, value in updates.items():
            if key not in schema:
                errors.append(f"未知配置项: {key}")
                continue
            expected_type = schema[key].get("type", "string")
            if not self._validate_value(value, expected_type):
                errors.append(f"{key}: 类型不匹配，期望 {expected_type}")
                continue
            validated[key] = value

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
            for key, value in updates.items():
                if key in schema:
                    file_config[key] = value
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
                    token = data["data"]["token"]

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
        """延迟执行的 AstrBot 重启"""
        await asyncio.sleep(1.0)  # 等待 HTTP 响应完全发出
        try:
            import aiohttp as _aiohttp

            async with _aiohttp.ClientSession() as session:
                login_url = f"http://{host}:{port}/api/auth/login"
                async with session.post(
                    login_url,
                    json={"username": dbc["username"], "password": dbc["password"]},
                ) as resp:
                    data = await resp.json()
                    token = data["data"]["token"]

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
        """列出所有已知会话"""
        sessions = self._collect_all_sessions()
        # 也从聊天记录文件收集（支持嵌套目录结构）
        data_dir = self._get_data_path()
        chat_dir = data_dir / "chat_history"
        if chat_dir.exists():
            for f in chat_dir.rglob("*.json"):
                try:
                    rel = f.relative_to(chat_dir)
                except ValueError:
                    continue
                parts = rel.parts
                if len(parts) == 3:
                    sessions.add(f"{parts[0]}_{parts[1]}_{f.stem}")
                elif len(parts) == 1:
                    sessions.add(f.stem)

        return web.json_response(
            {
                "ok": True,
                "sessions": sorted(sessions),
            }
        )

    async def _handle_data_attention(self, request: web.Request):
        """获取会话注意力数据"""
        session = request.match_info["session"]
        if not session or not _SAFE_SESSION_RE.match(session):
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)
        _sn = self._safe_num
        attention_map = self._safe_get_attention_map()
        users_data = attention_map.get(session, {})

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
            if hasattr(tracker, "moods") and session in tracker.moods:
                raw = tracker.moods[session]
                mood_data = {
                    "current_mood": raw.get("current_mood", "平静"),
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
        }

        # 频率调整器状态
        if (
            hasattr(self.plugin, "frequency_adjuster")
            and self.plugin.frequency_adjuster
        ):
            fa = self.plugin.frequency_adjuster
            if hasattr(fa, "check_states") and session in fa.check_states:
                state = fa.check_states[session]
                prob_data["frequency_adjusted_probability"] = state.get(
                    "adjusted_probability"
                )
                prob_data["frequency_last_check"] = state.get("last_check_time", 0)

        # 临时概率提升
        boost_map = self._safe_get_proactive_boost()
        if session in boost_map:
            b = boost_map[session]
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
                "total_successes": state.get("total_successes", 0),
                "total_failures": state.get("total_failures", 0),
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
        try:
            from ..utils.cooldown_manager import CooldownManager

            if hasattr(CooldownManager, "_cooldown_map"):
                for users in CooldownManager._cooldown_map.values():
                    cooldown_users += len(users)
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

        # 注意力数据
        try:
            attention_map = self._safe_get_attention_map()
            users_data = attention_map.get(session, {})
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
                if hasattr(tracker, "moods") and session in tracker.moods:
                    raw = tracker.moods[session]
                    if isinstance(raw, dict):
                        mood_data = {
                            "current_mood": str(raw.get("current_mood", "平静")),
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
            }
            if (
                hasattr(self.plugin, "frequency_adjuster")
                and self.plugin.frequency_adjuster
            ):
                fa = self.plugin.frequency_adjuster
                if hasattr(fa, "check_states") and session in fa.check_states:
                    state = fa.check_states[session]
                    if isinstance(state, dict):
                        prob_data["frequency_adjusted_probability"] = _sn(
                            state.get("adjusted_probability")
                        )
                        prob_data["frequency_last_check"] = state.get(
                            "last_check_time", 0
                        )
            boost_map = self._safe_get_proactive_boost()
            if session in boost_map:
                b = boost_map[session]
                if isinstance(b, dict):
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

        # 主动对话状态
        try:
            proactive_states = self._safe_get_proactive_states()
            proactive_data = proactive_states.get(session, {})
            if proactive_data and isinstance(proactive_data, dict):
                cooldown_until = _sn(proactive_data.get("cooldown_until", 0))
                proactive_data = dict(proactive_data)
                if cooldown_until > now:
                    proactive_data["cooldown_remaining"] = round(cooldown_until - now)
                else:
                    proactive_data["cooldown_remaining"] = 0
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
                cached = self.plugin.pending_messages_cache.get(session, [])
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
                is_processing = session in self.plugin.processing_sessions
        except Exception:
            pass
        detail["is_processing"] = is_processing

        # 主动对话处理中
        try:
            detail["proactive_processing"] = session in getattr(
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
                    if str(cid) == session:
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
        try:
            from ..utils.cooldown_manager import CooldownManager

            if hasattr(CooldownManager, "_cooldown_map"):
                session_cooldowns = CooldownManager._cooldown_map.get(session, {})
                for uid, cinfo in session_cooldowns.items():
                    info = CooldownManager.get_cooldown_info(session, uid)
                    if info:
                        cooldown_users.append(
                            {
                                "user_id": str(uid),
                                "user_name": cinfo.get("user_name", ""),
                                "remaining": round(_sn(info.get("remaining_time", 0))),
                                "reason": cinfo.get("reason", ""),
                            }
                        )
        except Exception:
            pass
        detail["cooldowns"] = cooldown_users

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
                replies = self.plugin.recent_replies_cache.get(session, [])
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

        # 清除注意力数据
        try:
            from ..utils.attention_manager import AttentionManager

            if session in AttentionManager._attention_map:
                del AttentionManager._attention_map[session]
                cleared.append("attention")
        except Exception as e:
            logger.warning(f"🌐 清除注意力数据失败: {e}")

        # 清除主动对话状态
        try:
            from ..utils.proactive_chat_manager import ProactiveChatManager

            if session in ProactiveChatManager._chat_states:
                del ProactiveChatManager._chat_states[session]
                cleared.append("proactive_state")
            if session in ProactiveChatManager._temp_probability_boost:
                del ProactiveChatManager._temp_probability_boost[session]
                cleared.append("temp_boost")
        except Exception as e:
            logger.warning(f"🌐 清除主动对话状态失败: {e}")

        # 清除情绪数据
        if hasattr(self.plugin, "mood_tracker") and self.plugin.mood_tracker:
            if hasattr(self.plugin.mood_tracker, "moods"):
                if session in self.plugin.mood_tracker.moods:
                    del self.plugin.mood_tracker.moods[session]
                    cleared.append("mood")

        # 清除频率调整器状态
        if (
            hasattr(self.plugin, "frequency_adjuster")
            and self.plugin.frequency_adjuster
        ):
            if hasattr(self.plugin.frequency_adjuster, "check_states"):
                if session in self.plugin.frequency_adjuster.check_states:
                    del self.plugin.frequency_adjuster.check_states[session]
                    cleared.append("frequency")

        # 清除处理中标记
        if hasattr(self.plugin, "processing_sessions"):
            self.plugin.processing_sessions.pop(session, None)

        return cleared

    async def _handle_session_list(self, request: web.Request):
        """列出会话及元数据（合并文件会话 + 内存会话）"""
        sessions = {}

        # 1. 收集所有内存中的活跃会话
        in_memory_sessions = self._collect_all_sessions()
        for sid in in_memory_sessions:
            sessions[sid] = {
                "message_count": 0,
                "file_size": 0,
                "last_modified": 0,
                "has_file": False,
                "has_runtime_data": True,
            }

        # 2. 扫描自定义存储目录的聊天记录文件（支持嵌套目录结构）
        data_dir = self._get_data_path()
        chat_dir = data_dir / "chat_history"
        if chat_dir.exists():
            for f in chat_dir.rglob("*.json"):
                # 从路径还原 session_id
                try:
                    rel = f.relative_to(chat_dir)
                except ValueError:
                    continue
                parts = rel.parts
                if len(parts) == 3:
                    # 嵌套: platform/chat_type/chat_id.json
                    session_id = f"{parts[0]}_{parts[1]}_{f.stem}"
                elif len(parts) == 1:
                    # 平面: session_name.json（旧兼容）
                    session_id = f.stem
                else:
                    continue  # 跳过意外结构
                try:
                    stat = f.stat()
                    with open(f, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    msg_count = len(data) if isinstance(data, list) else 0
                    if session_id in sessions:
                        sessions[session_id].update(
                            {
                                "message_count": msg_count,
                                "file_size": stat.st_size,
                                "last_modified": stat.st_mtime,
                                "has_file": True,
                            }
                        )
                    else:
                        sessions[session_id] = {
                            "message_count": msg_count,
                            "file_size": stat.st_size,
                            "last_modified": stat.st_mtime,
                            "has_file": True,
                            "has_runtime_data": False,
                        }
                except Exception as e:
                    logger.debug(f"🌐 读取聊天记录文件 {f.name} 失败: {e}")
                    sessions.setdefault(
                        session_id,
                        {
                            "message_count": 0,
                            "has_file": True,
                            "has_runtime_data": session_id in in_memory_sessions,
                            "error": True,
                        },
                    )

        return web.json_response({"ok": True, "sessions": sessions})

    async def _handle_session_reset(self, request: web.Request):
        """重置会话数据"""
        session = request.match_info["session"]
        if not session or not _SAFE_SESSION_RE.match(session):
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)
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
        data_dir = self._get_data_path()
        cache_file = data_dir / "image_description_cache.json"
        if cache_file.exists():
            cache_file.unlink()
            return web.json_response({"ok": True, "msg": "图片缓存已清除"})
        return web.json_response({"ok": True, "msg": "无缓存文件"})

    def _get_chat_history_path(self, session: str) -> Path | None:
        """获取聊天记录文件路径（含路径遍历防护）

        支持两种存储结构：
        1. 嵌套目录: chat_history/{platform}/{chat_type}/{chat_id}.json
           （ContextManager 实际使用的格式）
        2. 平面文件: chat_history/{session}.json（旧兼容）

        Returns:
            安全的文件路径，若 session 名称不合法则返回 None
        """
        if not session or not _SAFE_SESSION_RE.match(session):
            return None
        data_dir = self._get_data_path()
        safe_dir = (data_dir / "chat_history").resolve()

        def _is_safe(p: Path) -> bool:
            try:
                return str(p.resolve()).startswith(str(safe_dir))
            except OSError:
                return False

        # 尝试解析 session 名为嵌套路径:
        # aiocqhttp_group_123456789 → aiocqhttp/group/123456789.json
        # aiocqhttp_private_123456789 → aiocqhttp/private/123456789.json
        parts = session.split("_", 2)  # 最多分3段
        nested_path = None
        if len(parts) >= 3:
            platform, chat_type, chat_id = parts[0], parts[1], parts[2]
            nested_path = (
                data_dir / "chat_history" / platform / chat_type / f"{chat_id}.json"
            )
            if nested_path.exists() and _is_safe(nested_path):
                return nested_path

        # 兼容：也检查平面路径
        flat_path = data_dir / "chat_history" / f"{session}.json"
        if flat_path.exists() and _is_safe(flat_path):
            return flat_path

        # 文件不存在时，优先返回嵌套路径（与 ContextManager 一致）
        if nested_path and _is_safe(nested_path):
            return nested_path
        if _is_safe(flat_path):
            return flat_path
        return None

    async def _handle_get_chat_history(self, request: web.Request):
        """查看自定义存储聊天记录"""
        session = request.match_info["session"]
        path = self._get_chat_history_path(session)

        if path is None:
            return web.json_response({"ok": False, "msg": "无效的会话名称"}, status=400)

        if not path.exists():
            return web.json_response({"ok": True, "messages": []})

        try:
            with open(path, "r", encoding="utf-8") as f:
                messages = json.load(f)
            return web.json_response({"ok": True, "messages": messages})
        except Exception as e:
            logger.error(f"🌐 读取聊天记录 [{session}] 失败: {e}", exc_info=True)
            return web.json_response({"ok": False, "msg": "读取失败"}, status=500)

    async def _handle_put_chat_history(self, request: web.Request):
        """编辑聊天记录"""
        session = request.match_info["session"]
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        messages = body.get("messages")
        if not isinstance(messages, list):
            return web.json_response(
                {"ok": False, "msg": "messages 必须是数组"}, status=400
            )

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
        data_dir = self._get_data_path()
        cache_file = data_dir / "image_description_cache.json"
        if not cache_file.exists():
            return web.json_response({"ok": True, "cache": {}, "count": 0})

        try:
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
                return web.json_response(
                    {
                        "ok": True,
                        "msg": "插件已重置，AstrBot 重启中...",
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
        if not session_id or not _SAFE_SESSION_RE.match(session_id):
            return web.json_response({"ok": False, "msg": "无效的会话ID"}, status=400)

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

            # 也清除文件
            cache_file = self._get_data_path() / "image_description_cache.json"
            if cache_file.exists():
                cache_file.unlink()

            if restart_mode == "restart":
                self._create_deferred_restart_task()
                return web.json_response(
                    {
                        "ok": True,
                        "msg": f"已清除 {count} 条缓存，AstrBot 重启中...",
                    }
                )
            else:
                self.auth_mgr.mark_web_initiated_reload()
                return web.json_response(
                    {
                        "ok": True,
                        "msg": f"已清除 {count} 条图片描述缓存",
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
    _SENSITIVE_FILES = {"auth.json"}

    def _validate_file_path(self, rel_path: str) -> Path | None:
        """校验文件路径安全性，返回绝对路径或 None

        - 禁止 .. 路径遍历
        - 必须在数据目录内
        - 仅允许安全字符
        """
        if not rel_path or ".." in rel_path or "\\" in rel_path:
            return None
        if not self._SAFE_PATH_RE.match(rel_path):
            return None

        data_dir = self._get_data_path()
        target = data_dir / rel_path
        # 解析符号链接后确认仍在数据目录内
        try:
            real_target = target.resolve()
            real_data = data_dir.resolve()
            if not str(real_target).startswith(str(real_data)):
                return None
        except Exception:
            return None
        return target

    async def _handle_file_list(self, request: web.Request):
        """列出数据目录下所有文件"""
        data_dir = self._get_data_path()
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
                    files.append(
                        {
                            "path": str(rel).replace("\\", "/"),
                            "name": item.name,
                            "directory": str(rel.parent).replace("\\", "/")
                            if str(rel.parent) != "."
                            else "",
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                            "is_json": item.suffix.lower() == ".json",
                            "protected": item.name in self._SENSITIVE_FILES,
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
        # 敏感文件禁止在 Web 端读取
        if target.name in self._SENSITIVE_FILES:
            return web.json_response(
                {
                    "ok": False,
                    "msg": "此文件包含敏感凭据信息，出于安全考虑不支持在线查看。如需查看，请前往服务器本地对应目录手动打开。",
                },
                status=403,
            )
        # 限制文件大小（最大 5MB）
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
            # 尝试 JSON 解析
            is_json = target.suffix.lower() == ".json"
            parsed = None
            if is_json:
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    pass  # 文件内容存在但 JSON 格式损坏，仍返回原始内容
            return web.json_response(
                {
                    "ok": True,
                    "path": rel_path,
                    "content": content,
                    "is_json": is_json,
                    "parsed": parsed,
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
        """保存文件内容（仅限 JSON 文件）"""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "msg": "无效请求"}, status=400)

        rel_path = body.get("path", "")
        content = body.get("content", "")
        target = self._validate_file_path(rel_path)

        if target is None:
            return web.json_response({"ok": False, "msg": "无效的文件路径"}, status=400)
        # 敏感文件禁止在 Web 端修改
        if target.name in self._SENSITIVE_FILES:
            return web.json_response(
                {"ok": False, "msg": "此文件包含敏感凭据信息，不允许通过 Web 端修改"},
                status=403,
            )
        if target.suffix.lower() != ".json":
            return web.json_response(
                {"ok": False, "msg": "仅允许编辑 JSON 文件"}, status=403
            )
        # 验证 JSON 格式
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            return web.json_response(
                {"ok": False, "msg": f"JSON 格式错误: {e}"}, status=400
            )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)
            logger.info(f"🌐 文件已保存: {rel_path}")
            return web.json_response(
                {
                    "ok": True,
                    "msg": f"文件已保存: {rel_path}",
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
        # 禁止删除认证和封禁文件
        protected_files = self._SENSITIVE_FILES | {"bans.json"}
        if target.name in protected_files:
            return web.json_response(
                {"ok": False, "msg": "此文件受保护，不可删除"}, status=403
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
