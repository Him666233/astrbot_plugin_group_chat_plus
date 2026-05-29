"""
Web 配置面板 - 安全管理器
IP 过滤、封禁、暴力破解防护、访问日志（含持久化）、防爬虫系统
"""

import time
import json
import re
import ipaddress
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from astrbot.api import logger


@dataclass
class AccessLogEntry:
    """访问日志条目"""

    timestamp: float
    ip: str
    method: str
    path: str
    status: int
    note: str = ""  # 附加说明（如防爬虫触发原因）


@dataclass
class BanEntry:
    """IP 封禁条目"""

    ip: str
    reason: str
    banned_at: float
    expires_at: Optional[float] = None  # None = 永久


@dataclass
class BruteForceTracker:
    """暴力破解追踪（纯内存，重启清空）"""

    attempts: int = 0
    locked_until: float = 0.0
    last_attempt: float = 0.0
    reached_max_tier: bool = False
    rate_timestamps: list = None  # 懒初始化，避免可变默认值共享


# 暴力破解阶梯延迟配置：(失败次数阈值, 锁定秒数)
_BRUTE_FORCE_TIERS = [
    (5, 30),
    (10, 60),
    (15, 300),
    (20, 600),
    (30, 1800),
    (50, 3600),
]

# 访问日志文件最大大小（1MB）
_LOG_FILE_MAX_SIZE = 1 * 1024 * 1024
# 保留的历史日志文件数量
_LOG_FILE_MAX_ROTATIONS = 2
# 已登录认证请求默认速率阈值（次/分钟）
_DEFAULT_AUTHENTICATED_RATE_LIMIT = 240

# 可疑 User-Agent 特征（正则）
_SUSPICIOUS_UA_PATTERNS = [
    re.compile(
        r"bot|crawler|spider|scraper|scan|wget|curl|python-requests|go-http-client|okhttp|libwww",
        re.I,
    ),
    re.compile(r"zgrab|masscan|nmap|nikto|sqlmap|nuclei|dirbuster|gobuster", re.I),
]

# robots.txt 内容（君子协议）
_ROBOTS_TXT = """\
User-agent: *
Disallow: /

# 本站点是私有管理面板。
# 严禁任何自动化抓取、扫描或爬取行为。
# 该提示仅作访问声明，违规访问可能触发 IP 封锁。
"""

# 扫描行为路径特征
_SCAN_PATH_PATTERNS = [
    r"\.php$",
    r"\.asp$",
    r"\.jsp$",
    r"wp-admin",
    r"\.env$",
    r"\.git/",
    r"admin\.php",
    r"phpinfo",
    r"\.sql$",
]


class SecurityManager:
    """集中式安全状态管理"""

    def __init__(self, config: dict, data_dir: str):
        # IP 访问控制（从配置读取，规范化所有 IP 为统一格式）
        self.ip_mode: str = config.get("web_panel_ip_mode", "disabled")
        self.ip_list: List[str] = [
            SecurityManager._normalize_ip(ip)
            for ip in config.get("web_panel_ip_list", [])
        ]
        self.protected_ips: List[str] = [
            SecurityManager._normalize_ip(ip)
            for ip in config.get("web_panel_protected_ips", [])
        ]

        # 配置校验：检查 IP 名单中的潜在错误（无效IP、CIDR网段、未指定地址等）
        SecurityManager._validate_ip_list_entries(self.ip_list, "web_panel_ip_list")
        SecurityManager._validate_ip_list_entries(
            self.protected_ips, "web_panel_protected_ips"
        )

        # 防爬虫配置
        self.anti_spider_enabled: bool = config.get("web_panel_anti_spider", False)
        self.anti_spider_rate_limit: int = config.get(
            "web_panel_anti_spider_rate_limit", 60
        )
        self.anti_spider_ban_duration: int = config.get(
            "web_panel_anti_spider_ban_duration", 300
        )
        self.authenticated_rate_limit: int = config.get(
            "web_panel_authenticated_rate_limit",
            max(_DEFAULT_AUTHENTICATED_RATE_LIMIT, self.anti_spider_rate_limit * 4),
        )
        # 每 IP 请求计数（1分钟滑动窗口）: ip -> deque of timestamps
        self._request_timestamps: Dict[str, deque] = defaultdict(lambda: deque())
        # 已登录请求计数（1分钟滑动窗口）: bucket -> deque of timestamps
        self._authenticated_request_timestamps: Dict[str, deque] = defaultdict(
            lambda: deque()
        )

        # 访问日志 - 内存环形缓冲
        self.access_log: deque = deque(maxlen=10000)

        # IP 封禁表 - 内存 + 持久化
        self.ban_map: Dict[str, BanEntry] = {}
        self._data_dir = Path(data_dir)
        self._web_data_dir = self._data_dir / "web_data"
        self._web_data_dir.mkdir(parents=True, exist_ok=True)
        self._ban_file = self._web_data_dir / "bans.json"
        self._load_bans()

        # 访问日志持久化文件 (JSONL 格式)
        self._log_file = self._web_data_dir / "access_log.jsonl"

        # 加载历史访问日志到内存
        self._load_access_logs()

        # 暴力破解追踪 - 纯内存，重启清空
        self.brute_force: Dict[str, BruteForceTracker] = {}

        # 暴力破解可配置参数（从配置文件读取）
        self.brute_force_window: int = config.get("web_panel_brute_force_window", 3600)
        self.brute_force_rate_window: int = config.get(
            "web_panel_brute_force_rate_window", 10
        )
        self.brute_force_rate_count: int = config.get(
            "web_panel_brute_force_rate_count", 3
        )
        self.brute_force_ban_duration: int = config.get(
            "web_panel_brute_force_ban_duration", 0
        )
        self.brute_force_tiers: List[Tuple[int, int]] = self._parse_tiers(
            config.get("web_panel_brute_force_tiers", "")
        )

        # 启动时清理受保护 IP 误写入的封禁记录
        self._purge_protected_from_bans()

    # ==================== 辅助 ====================

    @staticmethod
    def _normalize_ip(ip: str) -> str:
        """将 IP 地址规范化为标准字符串形式。

        对 IPv4 保持点分十进制；对 IPv6 压缩为 RFC 5952 规范形式。
        这使得同一地址的不同文本表示（如 2001:db8::1 与 2001:db8:0:0:0:0:0:1）
        在字符串比较时能正确匹配。

        若输入为非法 IP 地址，返回原字符串（防御性降级）。
        """
        if not ip:
            return ip
        try:
            return str(ipaddress.ip_address(ip.strip()))
        except ValueError:
            return ip.strip()

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        """检查字符串是否为合法的 IPv4 或 IPv6 地址（不含 CIDR 网段）。"""
        if not ip:
            return False
        try:
            ipaddress.ip_address(ip.strip())
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_network_notation(ip: str) -> bool:
        """检查字符串是否为 CIDR 网段表示法（如 192.168.0.0/16）。"""
        if not ip:
            return False
        try:
            ipaddress.ip_network(ip.strip(), strict=False)
            return "/" in ip  # 只有含 / 才算网段，避免裸 IP 被误判
        except ValueError:
            return False

    @staticmethod
    def _validate_ip_list_entries(ip_list: list, list_name: str):
        """校验 IP 名单条目，对无效/误导性配置输出警告日志。

        检测以下问题：
        - 无效 IP 且非 CIDR 网段 → 永远不会匹配任何客户端
        - CIDR 网段表示法 → 系统不支持子网匹配，不会按预期工作
        - 未指定地址（0.0.0.0 / ::）→ 永远不会匹配实际对端 IP
        """
        _UNSPECIFIED = {
            "0.0.0.0": "IPv4 未指定地址",
            "::": "IPv6 未指定地址",
        }
        for entry in ip_list:
            if not entry or not entry.strip():
                continue
            entry = entry.strip()

            if entry in _UNSPECIFIED:
                # 根据名单类型给出针对性说明
                if list_name == "web_panel_protected_ips":
                    _hint = "该条目不会匹配任何实际客户端 IP，无法起到保护作用。"
                else:
                    _hint = (
                        "该条目不会匹配任何实际客户端 IP："
                        "白名单模式 → 全员无法访问；黑名单模式 → 无实际拦截效果。"
                    )
                logger.warning(
                    f"🔒 配置警告：{list_name} 中包含 {entry}"
                    f"（{_UNSPECIFIED[entry]}）。{_hint}"
                )
                continue

            if SecurityManager._is_network_notation(entry):
                # CIDR 网段在黑/白名单中均无效
                _hint = (
                    "系统不支持子网/IP段匹配，该条目不会按网段生效。"
                    "如需匹配整个网段，请逐条添加各 IP 地址。"
                )
                logger.warning(
                    f"🔒 配置警告：{list_name} 中包含 {entry}，疑似 CIDR 网段表示法。"
                    f"{_hint}"
                )
                continue

            if not SecurityManager._is_valid_ip(entry):
                # 无效 IP 在黑/白名单中均无效
                if list_name == "web_panel_protected_ips":
                    _hint = "无法起到保护作用。"
                else:
                    _hint = "白名单模式 → 全员无法访问；黑名单模式 → 无实际拦截效果。"
                logger.warning(
                    f"🔒 配置警告：{list_name} 中包含 {entry}，不是合法的 IPv4/IPv6 地址。"
                    f"该条目永远不会匹配任何客户端 IP，可能是配置错误。{_hint}"
                )

    def _is_protected(self, ip: str) -> bool:
        """检查 IP 是否在受保护名单中"""
        return self._normalize_ip(ip) in self.protected_ips

    @staticmethod
    def _parse_tiers(raw_value) -> List[Tuple[int, int]]:
        """从配置原始值解析阶梯列表，无效时回退到默认值。

        Args:
            raw_value: 可以是 str (JSON), list, 或其他无效值

        Returns:
            排序后的 [(count, seconds), ...] 列表
        """
        try:
            if isinstance(raw_value, list) and all(
                isinstance(t, (list, tuple)) and len(t) == 2 for t in raw_value
            ):
                parsed = [(int(t[0]), int(t[1])) for t in raw_value]
                parsed.sort(key=lambda x: x[0])
                if parsed:
                    return parsed
        except (ValueError, TypeError):
            pass

        try:
            if isinstance(raw_value, str) and raw_value.strip():
                parsed = json.loads(raw_value)
                if isinstance(parsed, list) and all(
                    isinstance(t, (list, tuple)) and len(t) == 2 for t in parsed
                ):
                    result = [(int(t[0]), int(t[1])) for t in parsed]
                    result.sort(key=lambda x: x[0])
                    if result:
                        return result
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return _BRUTE_FORCE_TIERS

    def _purge_protected_from_bans(self):
        """
        启动时检查：若受保护 IP 出现在封禁表中则自动删除并输出警告日志。
        防止配置文件被手动篡改导致管理员 IP 被锁定。
        """
        to_remove = [ip for ip in self.ban_map if self._is_protected(ip)]
        if to_remove:
            for ip in to_remove:
                del self.ban_map[ip]
                logger.warning(
                    f"🔒 安全检测：受保护 IP {ip} 出现在封禁列表中，已自动移除。"
                    f"受保护 IP 不可被封禁，请检查配置文件是否被篡改。"
                )
            self._save_bans()

    # ==================== IP 访问控制 ====================

    def check_ip_allowed(self, ip: str) -> Tuple[bool, str]:
        """
        综合检查 IP 是否允许访问。

        优先级（从高到低）：
        1. 受保护 IP → 永远放行，不受任何机制影响
        2. 黑白名单检查（whitelist / blacklist / disabled）
           - 白名单命中 → 直接放行，跳过封禁检查（封禁对白名单 IP 无效）
           - 黑名单命中 → 直接拒绝
           - disabled → 继续向下检查
        3. 封禁列表检查（手动封禁 + 防爬虫自动封禁共用同一 ban_map）
           - 已封禁则拒绝；过期封禁自动清除并持久化

        设计说明：
        - 白名单 IP 在第②步被放行，不再执行封禁检查，因此手动/自动封禁对白名单 IP 无效
        - 这符合「白名单 = 永远信任」的语义，防止管理员 IP 被意外封禁

        Returns:
            (allowed, reason) - 是否允许 及 拒绝原因
        """
        ip = self._normalize_ip(ip)

        # ① 受保护 IP 永远放行（最高优先级）
        if self._is_protected(ip):
            return True, ""

        # ② 黑白名单检查（先于封禁检查）
        if self.ip_mode == "whitelist":
            if self.ip_list and ip in self.ip_list:
                # 白名单命中 → 直接放行，封禁检查不适用
                return True, ""
            else:
                return False, "IP 不在白名单中，无权访问"

        if self.ip_mode == "blacklist":
            if self.ip_list and ip in self.ip_list:
                return False, "IP 在黑名单中，无权访问"
            # 黑名单未命中 → 继续检查封禁

        # ③ 封禁列表检查（disabled 模式或黑名单未命中时执行）
        ban = self.ban_map.get(ip)
        if ban is not None:
            if ban.expires_at is not None and time.time() > ban.expires_at:
                # 封禁已过期 → 清除并持久化，避免过期记录无限堆积
                del self.ban_map[ip]
                self._save_bans()
            else:
                return False, f"IP {ip} 已被封禁: {ban.reason}"

        return True, ""

    # ==================== 防爬虫 ====================

    def get_robots_txt(self) -> str:
        """返回 robots.txt 内容"""
        return _ROBOTS_TXT

    def check_spider(self, ip: str, path: str, user_agent: str) -> Tuple[bool, str]:
        """
        检测是否为爬虫行为。

        Returns:
            (is_spider, reason) - 是否为爬虫 及 原因（空字符串表示正常）
        """
        if not self.anti_spider_enabled:
            return False, ""

        ip = self._normalize_ip(ip)

        # 受保护 IP 豁免
        if self._is_protected(ip):
            return False, ""

        # 白名单模式下豁免
        if self.ip_mode == "whitelist" and ip in self.ip_list:
            return False, ""

        # 1. 可疑 User-Agent
        for pattern in _SUSPICIOUS_UA_PATTERNS:
            if pattern.search(user_agent or ""):
                return True, f"可疑 User-Agent: {user_agent[:80]}"

        # 2. 访问频率（1分钟滑动窗口速率限制）
        now = time.time()
        window = self._request_timestamps[ip]
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.popleft()
        window.append(now)

        if len(window) > self.anti_spider_rate_limit:
            return (
                True,
                f"请求频率过高：{len(window)} 次/分钟（阈值 {self.anti_spider_rate_limit}）",
            )

        # 3. 扫描行为路径特征
        for pat in _SCAN_PATH_PATTERNS:
            if re.search(pat, path, re.I):
                return True, f"扫描行为检测（路径特征）: {path}"

        return False, ""

    def check_authenticated_rate_limit(
        self,
        ip: str,
        session_id: str,
        path: str,
        *,
        is_heartbeat: bool = False,
        is_auto_refresh: bool = False,
    ) -> Tuple[bool, str]:
        """检查已登录请求的速率，心跳和自动刷新请求直接放行不计入窗口。"""
        if not self.anti_spider_enabled:
            return False, ""
        ip = self._normalize_ip(ip)
        if self._is_protected(ip):
            return False, ""
        if self.ip_mode == "whitelist" and ip in self.ip_list:
            return False, ""
        if not session_id:
            return False, ""

        # 心跳和自动刷新直接放行，不参与速率窗口计数
        # 放在 window.append 之前以确保不会虚增计数挤压手动操作配额
        if is_heartbeat or is_auto_refresh:
            return False, ""

        now = time.time()
        window = self._authenticated_request_timestamps[f"{session_id}:{ip}"]
        cutoff = now - 60
        while window and window[0] < cutoff:
            window.popleft()
        window.append(now)

        if len(window) > self.authenticated_rate_limit:
            return (
                True,
                f"已登录请求频率过高：{len(window)} 次/分钟（阈值 {self.authenticated_rate_limit}），路径: {path}",
            )
        return False, ""

    def auto_ban_spider(self, ip: str, reason: str):
        """防爬虫触发时自动临时封禁（受保护 IP 豁免）"""
        ip = self._normalize_ip(ip)
        if self._is_protected(ip):
            return
        if ip not in self.ban_map:
            self.ban_ip(
                ip, reason=f"[防爬虫] {reason}", duration=self.anti_spider_ban_duration
            )
            logger.warning(
                f"🕷️ 防爬虫：已临时封禁 {ip}（{self.anti_spider_ban_duration}秒）：{reason}"
            )

    def get_auto_ban_note(self, reason: str) -> str:
        """生成防爬虫自动封禁的访问日志附注（包含封禁时长，便于前端渲染）"""
        return f"[防爬虫自动封禁] 原因: {reason} | 封禁时长: {self.anti_spider_ban_duration}秒"

    # ==================== 访问日志 ====================

    def log_access(self, ip: str, method: str, path: str, status: int, note: str = ""):
        """记录一次访问（内存 + 持久化文件）"""
        entry = AccessLogEntry(
            timestamp=time.time(),
            ip=ip,
            method=method,
            path=path,
            status=status,
            note=note,
        )
        self.access_log.append(entry)
        self._append_log_to_file(entry)

    def _append_log_to_file(self, entry: AccessLogEntry):
        """追加日志到 JSONL 文件，自动轮转"""
        try:
            if self._log_file.exists():
                try:
                    size = self._log_file.stat().st_size
                except OSError:
                    size = 0
                if size >= _LOG_FILE_MAX_SIZE:
                    self._rotate_log_files()

            line = json.dumps(asdict(entry), ensure_ascii=False) + "\n"
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.debug(f"🔒 写入访问日志文件失败: {e}")

    def _rotate_log_files(self):
        """轮转日志文件：当前文件 → .1 → .2 → 删除"""
        try:
            for i in range(_LOG_FILE_MAX_ROTATIONS, 0, -1):
                src = self._web_data_dir / f"access_log.{i}.jsonl"
                if i == _LOG_FILE_MAX_ROTATIONS:
                    if src.exists():
                        src.unlink()
                else:
                    dst = self._web_data_dir / f"access_log.{i + 1}.jsonl"
                    if src.exists():
                        src.rename(dst)
            if self._log_file.exists():
                dst = self._web_data_dir / "access_log.1.jsonl"
                self._log_file.rename(dst)
        except Exception as e:
            logger.warning(f"🔒 日志轮转失败: {e}")

    def _load_access_logs(self):
        """启动时从持久化文件加载最近的访问日志到内存"""
        files_to_load = []
        for i in range(_LOG_FILE_MAX_ROTATIONS, 0, -1):
            f = self._web_data_dir / f"access_log.{i}.jsonl"
            if f.exists():
                files_to_load.append(f)
        if self._log_file.exists():
            files_to_load.append(self._log_file)

        loaded = 0
        for log_file in files_to_load:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            entry = AccessLogEntry(
                                timestamp=data.get("timestamp", 0),
                                ip=data.get("ip", ""),
                                method=data.get("method", ""),
                                path=data.get("path", ""),
                                status=data.get("status", 0),
                                note=data.get("note", ""),
                            )
                            self.access_log.append(entry)
                            loaded += 1
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception as e:
                logger.debug(f"🔒 加载访问日志文件 {log_file.name} 失败: {e}")

        if loaded > 0:
            logger.info(f"🔒 已从持久化文件恢复 {loaded} 条访问日志")

    def clean_old_logs(self, retention_days: int) -> int:
        """
        清理超过 retention_days 天的日志文件。

        Returns:
            删除的文件数量
        """
        cutoff = time.time() - retention_days * 86400
        deleted = 0
        try:
            log_files = list(self._web_data_dir.glob("access_log*.jsonl"))
            for f in log_files:
                try:
                    mtime = f.stat().st_mtime
                    if mtime < cutoff:
                        f.unlink()
                        deleted += 1
                        logger.info(f"🔒 已删除过期日志文件: {f.name}")
                except Exception as e:
                    logger.debug(f"🔒 删除日志文件 {f.name} 失败: {e}")
        except Exception as e:
            logger.warning(f"🔒 清理日志文件失败: {e}")
        # 同步清理内存中的旧日志
        if cutoff > 0:
            new_log = deque(
                (e for e in self.access_log if e.timestamp >= cutoff), maxlen=10000
            )
            self.access_log = new_log
        return deleted

    def get_access_logs(self, page: int = 1, size: int = 50) -> Tuple[List[dict], int]:
        """
        分页获取访问日志（最新在前）

        Returns:
            (logs_list, total_count)
        """
        total = len(self.access_log)
        all_logs = list(self.access_log)
        all_logs.reverse()

        start = (page - 1) * size
        end = start + size
        page_logs = all_logs[start:end]

        return [asdict(e) for e in page_logs], total

    # ==================== IP 封禁管理 ====================

    def ban_ip(
        self, ip: str, reason: str = "手动封禁", duration: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        封禁 IP。受保护 IP 无法封禁，尝试封禁时输出警告日志。

        Args:
            ip: 要封禁的 IP（IPv4/IPv6 均可，自动规范化为标准形式）
            reason: 封禁原因
            duration: 封禁时长（秒），None=永久

        Returns:
            (success, message)
        """
        if not ip:
            return False, "IP 地址不能为空"

        ip = self._normalize_ip(ip)

        if not self._is_valid_ip(ip):
            return False, f"无效的 IP 地址格式: {ip}"

        if self._is_protected(ip):
            logger.warning(
                f"🔒 尝试封禁受保护 IP {ip} 被拒绝（原因：{reason}）。"
                f"受保护 IP 不可被任何机制封禁，请通过传统配置文件调整受保护 IP 名单。"
            )
            return False, f"IP {ip} 在受保护名单中，无法封禁"

        expires_at = None
        if duration is not None:
            expires_at = time.time() + duration

        self.ban_map[ip] = BanEntry(
            ip=ip,
            reason=reason,
            banned_at=time.time(),
            expires_at=expires_at,
        )
        self._save_bans()

        duration_str = "永久" if duration is None else f"{int(duration)}秒"
        return True, f"已封禁 {ip}（{duration_str}）"

    def unban_ip(self, ip: str):
        """解封 IP"""
        ip = self._normalize_ip(ip)
        self.ban_map.pop(ip, None)
        self._save_bans()

    def get_ban_list(self) -> List[dict]:
        """获取封禁列表，自动清理过期条目，同时确保受保护 IP 不出现在列表中"""
        now = time.time()
        expired = [
            ip
            for ip, ban in self.ban_map.items()
            if ban.expires_at is not None and now > ban.expires_at
        ]
        # 顺便检查是否有受保护 IP 混入（防御性检查）
        protected_leaked = [ip for ip in self.ban_map if self._is_protected(ip)]
        if protected_leaked:
            for ip in protected_leaked:
                del self.ban_map[ip]
                logger.warning(
                    f"🔒 安全检测：受保护 IP {ip} 出现在封禁列表中，已自动移除。"
                )

        for ip in expired:
            if ip in self.ban_map:
                del self.ban_map[ip]
        if expired or protected_leaked:
            self._save_bans()

        result = []
        for ip, ban in self.ban_map.items():
            entry = asdict(ban)
            if ban.expires_at is not None:
                entry["remaining_seconds"] = max(0, int(ban.expires_at - now))
            else:
                entry["remaining_seconds"] = None
            result.append(entry)
        return result

    def _load_bans(self):
        """从文件加载封禁数据，并清理已过期的条目（避免重启后过期记录无限堆积）"""
        if not self._ban_file.exists():
            return
        try:
            with open(self._ban_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            now = time.time()
            loaded_count = 0
            expired_count = 0
            for item in data:
                raw_ip = item.get("ip", "")
                normalized_ip = self._normalize_ip(raw_ip)
                ban = BanEntry(
                    ip=normalized_ip,
                    reason=item.get("reason", ""),
                    banned_at=item.get("banned_at", 0),
                    expires_at=item.get("expires_at"),
                )
                # 过滤掉已过期的临时封禁（永久封禁 expires_at=None 永远保留）
                if ban.expires_at is not None and now > ban.expires_at:
                    expired_count += 1
                    continue
                self.ban_map[ban.ip] = ban
                loaded_count += 1
            # 若有过期记录被清理，回写文件
            if expired_count > 0:
                self._save_bans()
                logger.info(
                    f"🔒 启动清理：已移除 {expired_count} 条过期封禁记录（保留 {loaded_count} 条有效记录）"
                )
        except Exception as e:
            logger.warning(f"🔒 加载封禁数据失败: {e}")

    def _save_bans(self):
        """持久化封禁数据"""
        try:
            self._ban_file.parent.mkdir(parents=True, exist_ok=True)
            data = [asdict(ban) for ban in self.ban_map.values()]
            with open(self._ban_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"🔒 保存封禁数据失败: {e}")

    # ==================== 暴力破解防护 ====================

    def check_brute_force(self, ip: str) -> Tuple[bool, int]:
        """
        检查 IP 是否因暴力破解被锁定

        Returns:
            (is_locked, wait_seconds) - 是否被锁定及剩余等待秒数
        """
        ip = self._normalize_ip(ip)
        tracker = self.brute_force.get(ip)
        if tracker is None:
            return False, 0

        now = time.time()

        # 窗口期衰减：超时无新失败则自动清零计数
        if (
            self.brute_force_window > 0
            and (now - tracker.last_attempt) > self.brute_force_window
        ):
            self.brute_force.pop(ip, None)
            return False, 0

        if tracker.locked_until > now:
            remaining = int(tracker.locked_until - now) + 1
            return True, remaining

        return False, 0

    def record_login_failure(self, ip: str) -> dict:
        """记录一次登录失败并返回操作详情。

        Returns:
            dict with keys: action, attempts, lock_seconds, banned
                action: 'rate_ban' | 'permanent_ban' | 'tier_lock' | 'recorded'
        """
        ip = self._normalize_ip(ip)
        now = time.time()
        tracker = self.brute_force.get(ip)

        if tracker is None:
            tracker = BruteForceTracker(last_attempt=now)
            tracker.rate_timestamps = []
            self.brute_force[ip] = tracker

        tracker.attempts += 1
        tracker.last_attempt = now

        max_threshold, max_seconds = self.brute_force_tiers[-1]

        # 计算当前阶梯对应的锁定时长
        lock_seconds = 0
        for threshold, seconds in self.brute_force_tiers:
            if tracker.attempts >= threshold:
                lock_seconds = seconds

        # === 分支 1: 频率检测（速度限制，用于对抗脚本攻击）===
        if self.brute_force_rate_window > 0 and self.brute_force_rate_count > 1:
            cutoff = now - self.brute_force_rate_window
            tracker.rate_timestamps = [
                t for t in tracker.rate_timestamps if t >= cutoff
            ]
            tracker.rate_timestamps.append(now)
            if len(tracker.rate_timestamps) >= self.brute_force_rate_count:
                duration = self.brute_force_ban_duration
                ban_duration = duration if duration > 0 else None
                self.ban_ip(
                    ip,
                    reason=(
                        f"[暴力破解] 频率异常（第{tracker.attempts}次，"
                        f"{self.brute_force_rate_window}秒内失败{len(tracker.rate_timestamps)}次）"
                    ),
                    duration=ban_duration,
                )
                logger.warning(
                    f"🔒 IP {ip} 登录频率异常，已封禁。"
                    f"（第{tracker.attempts}次，"
                    f"{self.brute_force_rate_window}秒内{len(tracker.rate_timestamps)}次失败）"
                )
                return {
                    "action": "rate_ban",
                    "attempts": tracker.attempts,
                    "banned": True,
                    "lock_seconds": 0,
                    "rate_count": len(tracker.rate_timestamps),
                    "rate_window": self.brute_force_rate_window,
                }

        # === 分支 2: 已达最大阶梯且锁已过期后再次尝试 → 封禁 ===
        if tracker.attempts >= max_threshold:
            tracker.reached_max_tier = True
        if (
            tracker.reached_max_tier
            and tracker.locked_until <= now
            and tracker.attempts > max_threshold
        ):
            duration = self.brute_force_ban_duration
            ban_duration = duration if duration > 0 else None
            self.ban_ip(
                ip,
                reason=(
                    f"[暴力破解] 已达最大阶梯阈值（第{tracker.attempts}次），"
                    f"解锁后继续尝试"
                ),
                duration=ban_duration,
            )
            logger.warning(
                f"🔒 IP {ip} 登录失败次数已达最大阈值（{tracker.attempts}次），已封禁"
            )
            return {
                "action": "permanent_ban",
                "attempts": tracker.attempts,
                "banned": True,
                "lock_seconds": 0,
            }

        # === 分支 3: 阶梯锁定 ===
        if lock_seconds > 0:
            tracker.locked_until = now + lock_seconds
            if tracker.attempts >= 15:
                logger.warning(
                    f"🔒 IP {ip} 密码错误第 {tracker.attempts} 次，锁定 {lock_seconds} 秒"
                )
            return {
                "action": "tier_lock",
                "attempts": tracker.attempts,
                "banned": False,
                "lock_seconds": lock_seconds,
            }

        # === 分支 4: 仅记录，未锁定 ===
        return {
            "action": "recorded",
            "attempts": tracker.attempts,
            "banned": False,
            "lock_seconds": 0,
        }

    def reset_login_failures(self, ip: str):
        """登录成功后重置失败计数"""
        ip = self._normalize_ip(ip)
        self.brute_force.pop(ip, None)

    # ==================== 内存清理 ====================

    def cleanup_stale_tracking_data(self, max_age_seconds: int = 3600):
        """清理超过指定时间无活动的请求追踪数据，释放内存。

        包括滑动窗口计数器（60 秒窗口，清洗阈值 1 小时）和
        暴力破解追踪器（按可配置窗口期清洗，最少保留 24 小时兜底）。
        """
        now = time.time()
        cutoff = now - max_age_seconds

        for ip in list(self._request_timestamps.keys()):
            dq = self._request_timestamps.get(ip)
            if dq is None:
                continue
            while dq and dq[0] < cutoff:
                dq.popleft()
            if not dq:
                try:
                    del self._request_timestamps[ip]
                except KeyError:
                    pass

        for key in list(self._authenticated_request_timestamps.keys()):
            dq = self._authenticated_request_timestamps.get(key)
            if dq is None:
                continue
            while dq and dq[0] < cutoff:
                dq.popleft()
            if not dq:
                try:
                    del self._authenticated_request_timestamps[key]
                except KeyError:
                    pass

        # 暴力破解追踪器清理：仅在用户启用窗口期衰减时生效
        # 若用户关闭衰减（brute_force_window=0），则永远不清理，
        # 保留原设计语义：防止慢速暴力破解攻击者利用清理重置计数。
        if self.brute_force_window > 0:
            bf_cutoff = now - max(self.brute_force_window, 86400)
            for ip in list(self.brute_force.keys()):
                tracker = self.brute_force.get(ip)
                if tracker is None:
                    continue
                if tracker.locked_until <= now and tracker.last_attempt < bf_cutoff:
                    del self.brute_force[ip]

    # ==================== 配置更新 ====================

    def update_config(self, config: dict):
        """运行时更新安全配置，并检查受保护 IP 是否与封禁表冲突"""
        self.ip_mode = config.get("web_panel_ip_mode", "disabled")
        self.ip_list = [
            self._normalize_ip(ip) for ip in config.get("web_panel_ip_list", [])
        ]
        old_protected = set(self.protected_ips)
        self.protected_ips = [
            self._normalize_ip(ip) for ip in config.get("web_panel_protected_ips", [])
        ]

        # 配置校验（与 __init__ 中逻辑一致）
        SecurityManager._validate_ip_list_entries(self.ip_list, "web_panel_ip_list")
        SecurityManager._validate_ip_list_entries(
            self.protected_ips, "web_panel_protected_ips"
        )

        self.anti_spider_enabled = config.get("web_panel_anti_spider", False)
        self.anti_spider_rate_limit = config.get("web_panel_anti_spider_rate_limit", 60)
        self.anti_spider_ban_duration = config.get(
            "web_panel_anti_spider_ban_duration", 300
        )
        self.authenticated_rate_limit = config.get(
            "web_panel_authenticated_rate_limit",
            max(_DEFAULT_AUTHENTICATED_RATE_LIMIT, self.anti_spider_rate_limit * 4),
        )

        # 暴力破解可配置参数
        self.brute_force_window = config.get("web_panel_brute_force_window", 3600)
        self.brute_force_rate_window = config.get(
            "web_panel_brute_force_rate_window", 10
        )
        self.brute_force_rate_count = config.get("web_panel_brute_force_rate_count", 3)
        self.brute_force_ban_duration = config.get(
            "web_panel_brute_force_ban_duration", 0
        )
        self.brute_force_tiers = self._parse_tiers(
            config.get("web_panel_brute_force_tiers", "")
        )

        # 若受保护 IP 名单发生变化，重新检查封禁表
        new_protected = set(self.protected_ips)
        if new_protected != old_protected:
            self._purge_protected_from_bans()
