"""
Web 配置面板 - 安全管理器
IP 过滤、封禁、暴力破解防护、访问日志（含持久化）、防爬虫系统
"""

import os
import time
import json
import re
from collections import deque, defaultdict
from dataclasses import dataclass, field, asdict
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
    first_attempt: float = 0.0


# 暴力破解阶梯延迟配置：(失败次数阈值, 锁定秒数)
_BRUTE_FORCE_TIERS = [
    (5, 30),
    (10, 60),
    (15, 300),
    (20, 600),
]

# 访问日志文件最大大小（1MB）
_LOG_FILE_MAX_SIZE = 1 * 1024 * 1024
# 保留的历史日志文件数量
_LOG_FILE_MAX_ROTATIONS = 2

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

# This is a private administration panel.
# All automated access, crawling and scraping is strictly prohibited.
# This notice is a courtesy; unauthorized access may result in IP blocking.
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
        # IP 访问控制（从配置读取）
        self.ip_mode: str = config.get("web_panel_ip_mode", "disabled")
        self.ip_list: List[str] = list(config.get("web_panel_ip_list", []))
        self.protected_ips: List[str] = list(config.get("web_panel_protected_ips", []))

        # 防爬虫配置
        self.anti_spider_enabled: bool = config.get("web_panel_anti_spider", False)
        self.anti_spider_rate_limit: int = config.get(
            "web_panel_anti_spider_rate_limit", 60
        )
        self.anti_spider_ban_duration: int = config.get(
            "web_panel_anti_spider_ban_duration", 300
        )
        # 每 IP 请求计数（1分钟滑动窗口）: ip -> deque of timestamps
        self._request_timestamps: Dict[str, deque] = defaultdict(lambda: deque())

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

        # 启动时清理受保护 IP 误写入的封禁记录
        self._purge_protected_from_bans()

    # ==================== 辅助 ====================

    def _is_protected(self, ip: str) -> bool:
        """检查 IP 是否在受保护名单中"""
        return ip in self.protected_ips

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

    def auto_ban_spider(self, ip: str, reason: str):
        """防爬虫触发时自动临时封禁（受保护 IP 豁免）"""
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
            ip: 要封禁的 IP
            reason: 封禁原因
            duration: 封禁时长（秒），None=永久

        Returns:
            (success, message)
        """
        if not ip:
            return False, "IP 地址不能为空"

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
                ban = BanEntry(
                    ip=item["ip"],
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
        tracker = self.brute_force.get(ip)
        if tracker is None:
            return False, 0

        now = time.time()
        if tracker.locked_until > now:
            remaining = int(tracker.locked_until - now) + 1
            return True, remaining

        return False, 0

    def record_login_failure(self, ip: str):
        """记录一次登录失败"""
        now = time.time()
        tracker = self.brute_force.get(ip)
        if tracker is None:
            tracker = BruteForceTracker(attempts=0, locked_until=0.0, first_attempt=now)
            self.brute_force[ip] = tracker

        tracker.attempts += 1

        lock_seconds = 0
        for threshold, seconds in _BRUTE_FORCE_TIERS:
            if tracker.attempts >= threshold:
                lock_seconds = seconds

        if lock_seconds > 0:
            tracker.locked_until = now + lock_seconds
            logger.warning(
                f"🔒 IP {ip} 密码错误第 {tracker.attempts} 次，锁定 {lock_seconds} 秒"
            )

    def reset_login_failures(self, ip: str):
        """登录成功后重置失败计数"""
        self.brute_force.pop(ip, None)

    # ==================== 配置更新 ====================

    def update_config(self, config: dict):
        """运行时更新安全配置，并检查受保护 IP 是否与封禁表冲突"""
        self.ip_mode = config.get("web_panel_ip_mode", "disabled")
        self.ip_list = list(config.get("web_panel_ip_list", []))
        old_protected = set(self.protected_ips)
        self.protected_ips = list(config.get("web_panel_protected_ips", []))
        self.anti_spider_enabled = config.get("web_panel_anti_spider", False)
        self.anti_spider_rate_limit = config.get("web_panel_anti_spider_rate_limit", 60)
        self.anti_spider_ban_duration = config.get(
            "web_panel_anti_spider_ban_duration", 300
        )

        # 若受保护 IP 名单发生变化，重新检查封禁表
        new_protected = set(self.protected_ips)
        if new_protected != old_protected:
            self._purge_protected_from_bans()
