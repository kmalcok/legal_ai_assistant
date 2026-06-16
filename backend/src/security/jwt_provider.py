from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable

import jwt

from ..config import jwt_config


def _mode() -> str:
    return str(jwt_config().jwt_mode or "hs256").strip().lower()


def _read_key_file(path: str) -> str:
    p = Path(path).expanduser()
    return p.read_text(encoding="utf-8")


def _hs256_key() -> str | bytes:
    cfg = jwt_config()
    secret = str(cfg.jwt_secret or "")
    if len(secret.encode("utf-8")) >= 32:
        return secret
    # PyJWT warns for very short HMAC secrets. For local/dev installs that still
    # use a weak shared secret, derive a stable 32-byte HMAC key instead of
    # passing the raw short string through directly.
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _encode_key() -> str:
    cfg = jwt_config()
    mode = _mode()
    if mode == "hs256":
        return _hs256_key()
    if mode in {"rs256", "eddsa"}:
        if not cfg.jwt_private_key_path:
            raise RuntimeError("JWT private key path is not set")
        return _read_key_file(cfg.jwt_private_key_path)
    raise RuntimeError(f"Unsupported JWT mode: {mode}")


def _decode_key() -> str:
    mode = _mode()
    if mode == "hs256":
        return _hs256_key()
    if mode in {"rs256", "eddsa"}:
        cfg = jwt_config()
        if not cfg.jwt_public_key_path:
            raise RuntimeError("JWT public key path is not set")
        return _read_key_file(cfg.jwt_public_key_path)
    raise RuntimeError(f"Unsupported JWT mode: {mode}")


def encode_token(payload: Dict[str, Any]) -> str:
    cfg = jwt_config()
    headers: Dict[str, Any] = {}
    if cfg.jwt_kid:
        headers["kid"] = cfg.jwt_kid
    return jwt.encode(payload, _encode_key(), algorithm=cfg.jwt_alg, headers=headers or None)


def decode_token(
    token: str,
    *,
    issuer: str,
    leeway_seconds: int,
    required_claims: Iterable[str],
) -> Dict[str, Any]:
    return jwt.decode(
        token,
        _decode_key(),
        algorithms=[jwt_config().jwt_alg],
        issuer=issuer,
        leeway=int(leeway_seconds),
        options={
            "verify_aud": False,
            "verify_sub": False,
            "require": list(required_claims),
        },
    )
