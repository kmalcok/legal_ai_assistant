from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple

from ..data.db_auth_repository import AuthRepository
from ..config import jwt_config, load_env
from ..security.jwt_provider import decode_token, encode_token


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    access_expires_at: int
    refresh_expires_at: int
    access_jti: str
    refresh_jti: str


def _now_ts() -> int:
    return int(time.time())


def issue_tokens_with_timing(*, user_id: int) -> tuple[IssuedTokens, dict[str, int]]:
    t0 = time.perf_counter()
    timing = {
        "token_version_ms": 0,
        "refresh_store_ms": 0,
        "token_encode_ms": 0,
        "issue_tokens_ms": 0,
    }
    load_env()
    cfg = jwt_config()
    now = _now_ts()
    access_exp = now + int(cfg.access_ttl_seconds)
    refresh_exp = now + int(cfg.refresh_ttl_seconds)
    access_jti = str(uuid.uuid4())
    refresh_jti = str(uuid.uuid4())

    token_version, db_timing = AuthRepository.get_token_version_and_store_refresh_jti(
            user_id=int(user_id),
            jti=refresh_jti,
            expires_at=datetime.fromtimestamp(refresh_exp, tz=timezone.utc),
        )
    timing["token_version_ms"] = int(db_timing.get("token_version_ms") or 0)
    timing["refresh_store_ms"] = int(db_timing.get("refresh_store_ms") or 0)

    access_payload = {
        "iss": cfg.jwt_issuer,
        "sub": str(int(user_id)),
        "iat": now,
        "exp": access_exp,
        "jti": access_jti,
        "ver": token_version,
        "token_type": "access",
    }
    refresh_payload = {
        "iss": cfg.jwt_issuer,
        "sub": str(int(user_id)),
        "iat": now,
        "exp": refresh_exp,
        "jti": refresh_jti,
        "token_type": "refresh",
    }

    t_enc0 = time.perf_counter()
    access_token = encode_token(access_payload)
    refresh_token = encode_token(refresh_payload)
    timing["token_encode_ms"] = int((time.perf_counter() - t_enc0) * 1000)
    timing["issue_tokens_ms"] = int((time.perf_counter() - t0) * 1000)

    return (
        IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
            access_jti=access_jti,
            refresh_jti=refresh_jti,
        ),
        timing,
    )


def issue_tokens(*, user_id: int) -> IssuedTokens:
    """
    Issue a short-lived access token and long-lived refresh token.
    """
    issued, _timing = issue_tokens_with_timing(user_id=int(user_id))
    return issued


def decode_and_validate_token(token: str, *, expected_type: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate JWT signature + required claims (iss, exp, sub) and token_type.
    Returns (payload, error_string).
    """
    load_env()
    cfg = jwt_config()
    try:
        payload = decode_token(
            token,
            issuer=cfg.jwt_issuer,
            leeway_seconds=int(cfg.leeway_seconds),
            required_claims=["iss", "sub", "exp", "iat"],
        )
    except Exception as exc:
        return None, str(exc)

    if payload.get("token_type") != expected_type:
        return None, "wrong_token_type"

    sub = payload.get("sub")
    try:
        _ = int(sub)
    except Exception:
        return None, "invalid_sub"

    return payload, None


def payload_user_id(payload: Dict[str, Any]) -> int:
    return int(payload["sub"])


def payload_jti(payload: Dict[str, Any]) -> Optional[str]:
    jti = payload.get("jti")
    return jti if isinstance(jti, str) and jti else None


def payload_token_version(payload: Dict[str, Any]) -> int:
    try:
        return int(payload.get("ver"))
    except Exception:
        return 0


def payload_exp(payload: Dict[str, Any]) -> int:
    return int(payload["exp"])


def extract_bearer_token(headers: Mapping[str, Any]) -> Optional[str]:
    raw = headers.get("authorization") or headers.get("Authorization")
    if not raw:
        return None
    parts = str(raw).split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


async def validate_access_token(token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload, err = decode_and_validate_token(token, expected_type="access")
    if payload is None:
        return None, err

    jti = payload_jti(payload)
    if not jti:
        return None, "missing_jti"
    if await AuthRepository.is_access_jti_denied(jti=jti):
        return None, "access_revoked"

    user_id = payload_user_id(payload)
    token_version = payload_token_version(payload)
    if token_version <= 0:
        return None, "invalid_access_version"

    current_version = await asyncio.to_thread(AuthRepository.get_token_version, user_id=int(user_id))
    if int(current_version) != int(token_version):
        return None, "session_revoked"

    return payload, None


def ts_to_utc_datetime(ts: int) -> datetime:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


