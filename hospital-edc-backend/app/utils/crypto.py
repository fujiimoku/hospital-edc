"""敏感字段（姓名/身份证）的 Fernet 对称加密工具。

- 密钥来自环境变量 FIELD_ENCRYPTION_KEY（Fernet key，base64 32字节）。
- 未配置密钥时明文透传（仅限开发环境）。
- decrypt 对历史明文数据（非 Fernet token）返回原值，保证向后兼容。
"""
import base64
import binascii
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_fernet = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if _fernet is None:
        key = settings.FIELD_ENCRYPTION_KEY
        if not key:
            return None
        # 允许直接填写任意字符串：用 sha256 派生合法 Fernet key
        try:
            _fernet = Fernet(key.encode())
        except (ValueError, binascii.Error):
            derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
            _fernet = Fernet(derived)
    return _fernet


def encrypt(plain: str | None) -> str | None:
    """加密明文；密钥未配置或入参为空时原样返回。"""
    if not plain:
        return plain
    f = _get_fernet()
    if f is None:
        return plain
    return f.encrypt(plain.encode()).decode()


def decrypt(token: str | None) -> str | None:
    """解密；入参为空、密钥未配置或解密失败（历史明文）时原样返回。"""
    if not token:
        return token
    f = _get_fernet()
    if f is None:
        return token
    try:
        return f.decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return token


def mask(value: str | None, keep: int = 1) -> str | None:
    """脱敏：保留前 keep 个字符，其余以 * 掩码（最长掩 4 位）。"""
    if not value:
        return value
    n = len(value)
    if n <= keep:
        return value
    return value[:keep] + "*" * min(n - keep, 4)
