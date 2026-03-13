"""
Web 配置面板 - 认证模块
PBKDF2-SHA256 密码哈希 + 轻量 JWT 实现
"""

import hashlib
import hmac
import os
import json
import time
import base64
import secrets
import string
from pathlib import Path

# Logger 导入（兼容 astrbot 环境）
try:
    from astrbot.api import logger
except ImportError:
    # 回退：简单的 logger 实现，输出到控制台
    class _FallbackLogger:
        def info(self, msg):
            print(f"[Web Panel] INFO: {msg}")

        def warning(self, msg):
            print(f"[Web Panel] WARNING: {msg}")

        def error(self, msg):
            print(f"[Web Panel] ERROR: {msg}")

    logger = _FallbackLogger()

# 默认密码长度（首次启动时随机生成）
_DEFAULT_PW_LENGTH = 12


def _generate_random_password(length: int = _DEFAULT_PW_LENGTH) -> str:
    """生成随机密码（字母+数字+特殊字符）"""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# PBKDF2 迭代次数
PBKDF2_ITERATIONS = 100000
# JWT 过期时间（秒）
JWT_EXPIRY = 86400  # 24小时


def _b64url_encode(data: bytes) -> str:
    """Base64url 编码（无填充）"""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Base64url 解码"""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s.encode("ascii"))


def hash_password(password: str, salt: bytes = None) -> tuple:
    """
    PBKDF2-SHA256 密码哈希
    Returns: (hash_hex, salt_hex)
    """
    if salt is None:
        salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return dk.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
    """验证密码，使用 hmac.compare_digest 防止时序攻击"""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(dk.hex(), stored_hash)


def create_jwt(payload: dict, secret: str) -> str:
    """创建 JWT token (HMAC-SHA256)"""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = dict(payload)
    payload["exp"] = int(time.time()) + JWT_EXPIRY
    payload["iat"] = int(time.time())
    body = _b64url_encode(json.dumps(payload).encode())
    msg = f"{header}.{body}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return f"{header}.{body}.{_b64url_encode(sig)}"


def verify_jwt(token: str, secret: str) -> dict | None:
    """验证 JWT token，返回 payload 或 None"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, body_b64, sig_b64 = parts
        msg = f"{header_b64}.{body_b64}".encode("ascii")
        expected_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(body_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


class AuthManager:
    """认证管理器 - 管理密码存储和 JWT"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir) / "web_data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.auth_file = self.data_dir / "auth.json"
        self._auth_data = None
        self._ensure_auth_file()

    def _ensure_auth_file(self):
        """确保 auth.json 存在，不存在则用随机密码初始化"""
        if not self.auth_file.exists():
            random_pw = _generate_random_password()
            pw_hash, salt = hash_password(random_pw)
            self._auth_data = {
                "password_hash": pw_hash,
                "salt": salt,
                "password_changed": False,
                "jwt_secret": os.urandom(32).hex(),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._save()
            logger.info(
                f"🔑 Web 面板初始密码已随机生成: {random_pw}  （请登录后立即修改密码）"
            )
        else:
            self._load()

    def _load(self):
        """从文件加载认证数据"""
        with open(self.auth_file, "r", encoding="utf-8") as f:
            self._auth_data = json.load(f)

    def _save(self):
        """保存认证数据到文件"""
        with open(self.auth_file, "w", encoding="utf-8") as f:
            json.dump(self._auth_data, f, indent=2, ensure_ascii=False)

    @property
    def password_changed(self) -> bool:
        return self._auth_data.get("password_changed", False)

    def login(self, password: str, client_ip: str = None) -> str | None:
        """登录验证，成功返回 JWT token（含 IP 绑定），失败返回 None"""
        if verify_password(
            password,
            self._auth_data["password_hash"],
            self._auth_data["salt"],
        ):
            payload = {"sub": "admin", "changed": self.password_changed}
            if client_ip:
                payload["ip"] = client_ip
            token = create_jwt(payload, self._auth_data["jwt_secret"])
            return token
        return None

    def verify_token(self, token: str, current_ip: str = None) -> dict | None:
        """验证 token 有效性，含 IP 绑定校验"""
        payload = verify_jwt(token, self._auth_data["jwt_secret"])
        if payload is None:
            return None
        # IP 绑定校验：token 中记录的 IP 与当前请求 IP 不一致则失效
        if current_ip and payload.get("ip") and payload["ip"] != current_ip:
            return None
        return payload

    def change_password(self, old_password: str, new_password: str) -> bool:
        """修改密码，需验证旧密码"""
        if not verify_password(
            old_password,
            self._auth_data["password_hash"],
            self._auth_data["salt"],
        ):
            return False
        pw_hash, salt = hash_password(new_password)
        self._auth_data["password_hash"] = pw_hash
        self._auth_data["salt"] = salt
        self._auth_data["password_changed"] = True
        # 更换 JWT secret，使旧 token 失效
        self._auth_data["jwt_secret"] = os.urandom(32).hex()
        self._save()
        return True

    def rotate_jwt_secret(self) -> bool:
        """轮换 JWT secret，使所有已发放的 token 立即失效。

        每次插件重载/重启时调用，强制用户重新登录。
        若本次重启由 Web 面板自身发起，则跳过轮换以保持登录态。

        Returns:
            True = 已跳过轮换（Web 面板发起的重启，登录态保留）
            False = 已轮换（正常重启，登录态失效）
        """
        if self._auth_data.get("_web_initiated_reload"):
            # Web 面板发起的重启：清除标记，保留 secret
            self._auth_data.pop("_web_initiated_reload", None)
            self._save()
            logger.info("🔑 Web 面板发起的重启，JWT secret 保持不变（登录态保留）")
            return True
        else:
            self._auth_data["jwt_secret"] = os.urandom(32).hex()
            self._save()
            return False

    def mark_web_initiated_reload(self):
        """标记本次重启由 Web 面板发起，下次 rotate_jwt_secret 将跳过轮换"""
        self._auth_data["_web_initiated_reload"] = True
        self._save()

    def reset_to_default(self):
        """重置密码为随机值，强制要求首次改密"""
        random_pw = _generate_random_password()
        pw_hash, salt = hash_password(random_pw)
        self._auth_data = {
            "password_hash": pw_hash,
            "salt": salt,
            "password_changed": False,
            "jwt_secret": os.urandom(32).hex(),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._save()
        logger.info(f"🔑 Web 面板密码已重置为: {random_pw}  （请尽快登录并修改密码）")
