"""
Web 配置面板 - 认证模块
Argon2id 密码哈希（内存硬化，防 GPU 暴力破解）+ JWT + 服务端会话表
支持从旧版 PBKDF2-SHA256 透明自动迁移，用户无感知
"""

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import string
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

# Logger 导入（兼容 astrbot 环境）
try:
    from astrbot.api import logger
except ImportError:

    class _FallbackLogger:
        def info(self, msg):
            print(f"[Web Panel] INFO: {msg}")

        def warning(self, msg):
            print(f"[Web Panel] WARNING: {msg}")

        def error(self, msg):
            print(f"[Web Panel] ERROR: {msg}")

    logger = _FallbackLogger()

_DEFAULT_PW_LENGTH = 12
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
HASH_VERSION_ARGON2 = "argon2id"
HASH_VERSION_PBKDF2 = "pbkdf2"
PBKDF2_ITERATIONS = 100000
JWT_EXPIRY = 86400
_SESSION_HISTORY_RETENTION = 7 * 24 * 60 * 60
_MAX_REVOKED_REVISIONS = 16

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import (
        InvalidHashError,
        VerificationError,
        VerifyMismatchError,
    )

    _ph = PasswordHasher(
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=32,
        salt_len=16,
    )
    _ARGON2_AVAILABLE = True
except ImportError:
    _ph = None
    _ARGON2_AVAILABLE = False
    logger.warning(
        "⚠️ argon2-cffi 未安装，密码哈希将回退到 PBKDF2-SHA256。"
        "请执行 pip install argon2-cffi>=23.1.0 以启用 Argon2id 保护。"
    )


@dataclass
class AuthCheckResult:
    ok: bool
    payload: dict | None = None
    reason: str | None = None
    session: dict | None = None


class AuthFailureReason:
    EXPIRED = "expired"
    IP_CHANGED = "ip_changed"
    REVOKED = "revoked"
    SESSION_MISSING = "session_missing"
    SIGNATURE_INVALID = "signature_invalid"
    SERVER_RESTART = "server_restart"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    MALFORMED = "malformed"


def _generate_random_password(length: int = _DEFAULT_PW_LENGTH) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _b64url_encode(data: bytes) -> str:
    return __import__("base64").urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return __import__("base64").urlsafe_b64decode(s.encode("ascii"))


def _now() -> int:
    return int(time.time())


def _hash_user_agent(user_agent: str) -> str:
    if not user_agent:
        return ""
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()[:16]


def hash_password_argon2(password: str) -> str:
    if not _ARGON2_AVAILABLE:
        raise RuntimeError("argon2-cffi 未安装，无法使用 Argon2id 哈希")
    return _ph.hash(password)


def hash_password(password: str, salt: bytes = None) -> tuple:
    if _ARGON2_AVAILABLE:
        return hash_password_argon2(password), ""
    if salt is None:
        salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return dk.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, salt_hex: str = "") -> bool:
    if stored_hash.startswith("$argon2"):
        if not _ARGON2_AVAILABLE:
            logger.error(
                "auth.json 使用 Argon2id 哈希，但 argon2-cffi 未安装，无法验证密码"
            )
            return False
        try:
            return _ph.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        except Exception:
            return False

    if not salt_hex:
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(dk.hex(), stored_hash)


def create_jwt(payload: dict, secret: str) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = dict(payload)
    now = _now()
    payload["exp"] = now + JWT_EXPIRY
    payload["iat"] = now
    body = _b64url_encode(json.dumps(payload).encode())
    msg = f"{header}.{body}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return f"{header}.{body}.{_b64url_encode(sig)}"


def verify_jwt(token: str, secret: str) -> tuple[dict | None, str | None]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None, AuthFailureReason.MALFORMED
        header_b64, body_b64, sig_b64 = parts
        msg = f"{header_b64}.{body_b64}".encode("ascii")
        expected_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None, AuthFailureReason.SIGNATURE_INVALID
        payload = json.loads(_b64url_decode(body_b64))
        if payload.get("exp", 0) < time.time():
            return payload, AuthFailureReason.EXPIRED
        return payload, None
    except Exception:
        return None, AuthFailureReason.MALFORMED


class AuthManager:
    """认证管理器 - 管理密码存储、JWT 和服务端会话"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir) / "web_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.auth_file = self.data_dir / "auth.json"
        self.jwt_secret_file = self.data_dir / "jwt_secret.json"
        self.sessions_file = self.data_dir / "sessions.json"
        self._auth_data = None
        self._jwt_data = None
        self._sessions: dict[str, dict] = {}
        self._ensure_auth_file()
        self._load_sessions()
        self._cleanup_sessions(persist=True)

    def _build_auth_data(self, password: str, password_changed: bool) -> dict:
        pw_hash, salt = hash_password(password)
        return {
            "password_hash": pw_hash,
            "salt": salt,
            "hash_version": HASH_VERSION_ARGON2
            if _ARGON2_AVAILABLE
            else HASH_VERSION_PBKDF2,
            "password_changed": password_changed,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @staticmethod
    def _build_jwt_data() -> dict:
        return {
            "jwt_secret": os.urandom(32).hex(),
            "token_revision": 1,
            "revoked_revisions": {},
        }

    def _set_temporary_password(self, password: str, *, reason: str):
        self._auth_data = self._build_auth_data(password, password_changed=False)
        self._jwt_data = self._build_jwt_data()
        self._jwt_data["_temp_plain_password"] = password
        self._sessions = {}
        self._save()
        self._save_jwt()
        self._save_sessions()
        if reason == "initial":
            logger.warning(f"🔑 Web 面板初始密码已随机生成: {password}")
            logger.warning(
                "⚠️ 安全警告：此默认密码以明文方式暂存于 jwt_secret.json 中，"
                "请务必登录后立即修改为自定义密码！修改后明文副本将自动删除。"
                "若不及时修改，存在密码泄露风险。"
            )
        elif reason == "reset":
            logger.warning(f"🔑 Web 面板密码已重置为: {password}")
            logger.warning(
                "⚠️ 安全警告：新重置的默认密码以明文方式暂存于 jwt_secret.json 中，"
                "请尽快登录并修改为自定义密码！修改后明文副本将自动删除。"
            )

    def _ensure_auth_file(self):
        if not self.auth_file.exists():
            self._set_temporary_password(_generate_random_password(), reason="initial")
        else:
            self._load()
            self._migrate_jwt_secret_from_auth()
            self._ensure_jwt_secret_file()
        self._remind_temp_password_if_needed()

    def _migrate_jwt_secret_from_auth(self):
        if (
            "jwt_secret" not in self._auth_data
            and "_web_initiated_reload" not in self._auth_data
        ):
            return

        migrated_fields = {}
        for field in ("jwt_secret", "_web_initiated_reload"):
            if field in self._auth_data:
                migrated_fields[field] = self._auth_data.pop(field)

        if self.jwt_secret_file.exists():
            try:
                with open(self.jwt_secret_file, "r", encoding="utf-8") as f:
                    existing_jwt_data = json.load(f)
            except Exception:
                existing_jwt_data = self._build_jwt_data()
        else:
            existing_jwt_data = self._build_jwt_data()

        existing_jwt_data.update(migrated_fields)
        existing_jwt_data.setdefault("jwt_secret", os.urandom(32).hex())
        existing_jwt_data.setdefault("token_revision", 1)
        existing_jwt_data.setdefault("revoked_revisions", {})
        self._jwt_data = existing_jwt_data
        self._save_jwt()
        self._save()
        logger.info(
            "🔒 安全迁移：jwt_secret 已从 auth.json 分离到独立文件 jwt_secret.json，"
            "密码数据与 JWT 密钥不再同文件存储"
        )

    def _ensure_jwt_secret_file(self):
        if self._jwt_data is not None:
            return
        if self.jwt_secret_file.exists():
            self._load_jwt()
        else:
            self._jwt_data = self._build_jwt_data()
            self._save_jwt()

    def _remind_temp_password_if_needed(self):
        if self.password_changed:
            return
        temp_pw = self._jwt_data.get("_temp_plain_password")
        if temp_pw:
            logger.warning(f"🔑 Web 面板当前仍在使用初始随机密码: {temp_pw}")
            logger.warning(
                "⚠️ 安全警告：默认密码以明文方式暂存于 jwt_secret.json 中，"
                "请尽快登录并修改为自定义密码！修改后明文副本将自动删除。"
                "继续使用默认密码存在安全风险。"
            )
        else:
            logger.warning(
                "⚠️ Web 面板当前仍在使用初始密码（明文副本不可用），"
                "如遗忘密码请在插件配置中触发密码重置。建议尽快修改为自定义密码。"
            )

    def _load(self):
        with open(self.auth_file, "r", encoding="utf-8") as f:
            self._auth_data = json.load(f)

    def _load_jwt(self):
        try:
            with open(self.jwt_secret_file, "r", encoding="utf-8") as f:
                self._jwt_data = json.load(f)
        except Exception:
            self._jwt_data = self._build_jwt_data()
            self._save_jwt()
        self._jwt_data.setdefault("jwt_secret", os.urandom(32).hex())
        self._jwt_data.setdefault("token_revision", 1)
        self._jwt_data.setdefault("revoked_revisions", {})

    def _load_sessions(self):
        if not self.sessions_file.exists():
            self._sessions = {}
            return
        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._sessions = data
            else:
                self._sessions = {}
        except Exception as e:
            logger.warning(f"🔒 加载会话数据失败: {e}")
            self._sessions = {}

    def _save(self):
        save_data = {
            k: v
            for k, v in self._auth_data.items()
            if k not in ("jwt_secret", "_web_initiated_reload")
        }
        with open(self.auth_file, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

    def _save_jwt(self):
        with open(self.jwt_secret_file, "w", encoding="utf-8") as f:
            json.dump(self._jwt_data, f, indent=2, ensure_ascii=False)

    def _save_sessions(self):
        with open(self.sessions_file, "w", encoding="utf-8") as f:
            json.dump(self._sessions, f, indent=2, ensure_ascii=False)

    def _cleanup_sessions(self, persist: bool = False):
        now = _now()
        cutoff = now - _SESSION_HISTORY_RETENTION
        changed = False
        for sid in list(self._sessions.keys()):
            session = self._sessions[sid]
            expires_at = int(session.get("expires_at", 0) or 0)
            status = session.get("status", "active")
            updated_at = int(
                session.get("revoked_at")
                or session.get("last_heartbeat_at")
                or session.get("last_seen_at")
                or session.get("created_at")
                or 0
            )
            if status == "active" and expires_at and expires_at <= now:
                session["status"] = "expired"
                session["reason"] = AuthFailureReason.EXPIRED
                session["revoked_at"] = now
                changed = True
                updated_at = now
            if updated_at and updated_at < cutoff:
                del self._sessions[sid]
                changed = True
        if changed and persist:
            self._save_sessions()

    def _advance_token_revision(self, reason: str):
        current = int(self._jwt_data.get("token_revision", 1))
        revoked = dict(self._jwt_data.get("revoked_revisions", {}))
        revoked[str(current)] = reason
        while len(revoked) > _MAX_REVOKED_REVISIONS:
            oldest = sorted(revoked.keys(), key=lambda item: int(item))[0]
            revoked.pop(oldest, None)
        self._jwt_data["revoked_revisions"] = revoked
        self._jwt_data["token_revision"] = current + 1
        self._save_jwt()

    def _revoke_all_sessions(self, reason: str):
        if not self._sessions:
            return
        now = _now()
        for session in self._sessions.values():
            session["status"] = "revoked"
            session["reason"] = reason
            session["revoked_at"] = now
        self._save_sessions()

    @staticmethod
    def _normalize_ip(ip: str | None) -> str:
        """将 IP 地址规范化为标准字符串形式（IPv4/IPv6 统一比较）。"""
        if not ip:
            return ""
        try:
            return str(ipaddress.ip_address(ip.strip()))
        except ValueError:
            return ip.strip()

    def _create_session(
        self, *, device_id: str, client_ip: str | None, user_agent: str
    ) -> dict:
        now = _now()
        sid = uuid.uuid4().hex
        expires_at = now + JWT_EXPIRY
        record = {
            "sid": sid,
            "device_id": device_id or uuid.uuid4().hex,
            "created_at": now,
            "expires_at": expires_at,
            "last_seen_at": now,
            "last_heartbeat_at": 0,
            "status": "active",
            "reason": "",
            "bound_ip": self._normalize_ip(client_ip),
            "ua_hash": _hash_user_agent(user_agent),
        }
        self._sessions[sid] = record
        self._save_sessions()
        return record

    def touch_session(
        self, sid: str, *, heartbeat: bool = False, persist: bool = False
    ):
        session = self._sessions.get(sid)
        if not session:
            return
        now = _now()
        session["last_seen_at"] = now
        if heartbeat:
            session["last_heartbeat_at"] = now
        if persist:
            self._save_sessions()

    @property
    def password_changed(self) -> bool:
        return self._auth_data.get("password_changed", False)

    @property
    def jwt_secret(self) -> str:
        return self._jwt_data["jwt_secret"]

    @property
    def token_revision(self) -> int:
        return int(self._jwt_data.get("token_revision", 1))

    def login(
        self,
        password: str,
        client_ip: str | None = None,
        device_id: str | None = None,
        user_agent: str = "",
    ) -> dict | None:
        # 每次成功登录都会创建独立 sid / device_id，对应独立会话。
        # 因此多设备、多浏览器、多次登录并存是允许的，默认不会互踢。
        if not verify_password(
            password,
            self._auth_data["password_hash"],
            self._auth_data.get("salt", ""),
        ):
            return None

        if _ARGON2_AVAILABLE and not self._auth_data["password_hash"].startswith(
            "$argon2"
        ):
            self._auth_data["password_hash"] = hash_password_argon2(password)
            self._auth_data["salt"] = ""
            self._auth_data["hash_version"] = HASH_VERSION_ARGON2
            self._save()
            logger.info("🔒 密码哈希已从 PBKDF2 自动升级至 Argon2id（更强抗暴力破解）")

        self._cleanup_sessions(persist=True)
        session = self._create_session(
            device_id=device_id or uuid.uuid4().hex,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        payload = {
            "sid": session["sid"],
            "rev": self.token_revision,
            "sub": "admin",
            "changed": self.password_changed,
        }
        if client_ip:
            payload["ip"] = client_ip
        token = create_jwt(payload, self.jwt_secret)
        return {
            "token": token,
            "session_id": session["sid"],
            "device_id": session["device_id"],
            "expires_at": session["expires_at"],
        }

    def verify_token(
        self,
        token: str,
        current_ip: str | None = None,
        *,
        touch: bool = True,
        heartbeat: bool = False,
        persist_touch: bool = False,
    ) -> AuthCheckResult:
        # 登录 IP 绑定校验仍然保留原有开关语义：
        # - web_panel_ip_bind_check=True：token 内记录登录 IP，后续请求/心跳都校验；
        # - web_panel_ip_bind_check=False：不做 IP 变化失效。
        # 这里只负责会话有效性判断，不刷新 24 小时绝对过期时间。
        payload, jwt_reason = verify_jwt(token, self.jwt_secret)
        if payload is None:
            return AuthCheckResult(
                False, reason=jwt_reason or AuthFailureReason.SIGNATURE_INVALID
            )
        if jwt_reason == AuthFailureReason.EXPIRED:
            sid = payload.get("sid")
            if sid and sid in self._sessions:
                self._sessions[sid]["status"] = "expired"
                self._sessions[sid]["reason"] = AuthFailureReason.EXPIRED
                self._sessions[sid]["revoked_at"] = _now()
                self._save_sessions()
            return AuthCheckResult(
                False, payload=payload, reason=AuthFailureReason.EXPIRED
            )

        token_revision = int(payload.get("rev", 0) or 0)
        if token_revision != self.token_revision:
            revoked_revisions = self._jwt_data.get("revoked_revisions", {})
            reason = revoked_revisions.get(
                str(token_revision), AuthFailureReason.REVOKED
            )
            return AuthCheckResult(False, payload=payload, reason=reason)

        sid = payload.get("sid")
        if not sid:
            return AuthCheckResult(
                False, payload=payload, reason=AuthFailureReason.SESSION_MISSING
            )

        session = self._sessions.get(sid)
        if not session:
            return AuthCheckResult(
                False, payload=payload, reason=AuthFailureReason.SESSION_MISSING
            )

        status = session.get("status", "active")
        if status != "active":
            return AuthCheckResult(
                False,
                payload=payload,
                session=session,
                reason=session.get("reason") or AuthFailureReason.REVOKED,
            )

        now = _now()
        expires_at = int(session.get("expires_at", 0) or 0)
        if expires_at and expires_at <= now:
            session["status"] = "expired"
            session["reason"] = AuthFailureReason.EXPIRED
            session["revoked_at"] = now
            self._save_sessions()
            return AuthCheckResult(
                False,
                payload=payload,
                session=session,
                reason=AuthFailureReason.EXPIRED,
            )

        if (
            current_ip
            and payload.get("ip")
            and payload["ip"] != self._normalize_ip(current_ip)
        ):
            session["status"] = "revoked"
            session["reason"] = AuthFailureReason.IP_CHANGED
            session["revoked_at"] = now
            self._save_sessions()
            return AuthCheckResult(
                False,
                payload=payload,
                session=session,
                reason=AuthFailureReason.IP_CHANGED,
            )

        if touch:
            self.touch_session(sid, heartbeat=heartbeat, persist=persist_touch)
            session = self._sessions.get(sid, session)

        return AuthCheckResult(True, payload=payload, session=session)

    def revoke_session(self, sid: str | None, reason: str = AuthFailureReason.REVOKED):
        if not sid or sid not in self._sessions:
            return
        session = self._sessions[sid]
        session["status"] = "revoked"
        session["reason"] = reason
        session["revoked_at"] = _now()
        self._save_sessions()

    def change_password(self, old_password: str, new_password: str) -> bool:
        if not verify_password(
            old_password,
            self._auth_data["password_hash"],
            self._auth_data.get("salt", ""),
        ):
            return False
        pw_hash, salt = hash_password(new_password)
        self._auth_data["password_hash"] = pw_hash
        self._auth_data["salt"] = salt
        self._auth_data["hash_version"] = (
            HASH_VERSION_ARGON2 if _ARGON2_AVAILABLE else HASH_VERSION_PBKDF2
        )
        self._auth_data["password_changed"] = True
        self._save()
        self._jwt_data.pop("_temp_plain_password", None)
        self._advance_token_revision(AuthFailureReason.PASSWORD_CHANGED)
        self._revoke_all_sessions(AuthFailureReason.PASSWORD_CHANGED)
        return True

    def rotate_jwt_secret(self) -> bool:
        if self._jwt_data.get("_web_initiated_reload"):
            self._jwt_data.pop("_web_initiated_reload", None)
            self._save_jwt()
            logger.info("🔑 Web 面板发起的重启，登录态保留")
            return True

        self._advance_token_revision(AuthFailureReason.SERVER_RESTART)
        self._revoke_all_sessions(AuthFailureReason.SERVER_RESTART)
        return False

    def mark_web_initiated_reload(self):
        self._jwt_data["_web_initiated_reload"] = True
        self._save_jwt()

    def reset_to_default(self):
        self._set_temporary_password(_generate_random_password(), reason="reset")

    def build_session_status(self, result: AuthCheckResult) -> dict:
        session = result.session or {}
        payload = result.payload or {}
        expires_at = int(session.get("expires_at") or payload.get("exp") or 0)
        now = _now()
        ttl_seconds = max(0, expires_at - now) if expires_at else 0
        return {
            "session_id": session.get("sid") or payload.get("sid") or "",
            "device_id": session.get("device_id", ""),
            "expires_at": expires_at,
            "server_time": now,
            "ttl_seconds": ttl_seconds,
            "password_changed": self.password_changed,
        }
