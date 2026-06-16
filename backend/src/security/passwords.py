from __future__ import annotations

import hashlib

import bcrypt


def _normalize_password_bytes(password: str) -> bytes:
    """
    bcrypt only considers the first 72 bytes. To avoid surprises and to support
    long passwords safely, we pre-hash if needed.
    """
    pw = (password or "").encode("utf-8")
    if len(pw) > 72:
        pw = hashlib.sha256(pw).digest()
    return pw


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("password_too_short")
    pw = _normalize_password_bytes(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pw, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        pw = _normalize_password_bytes(password)
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except Exception:
        return False


