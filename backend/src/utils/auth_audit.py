from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict

import redis.asyncio as aioredis

from ..config import agent_config, log_config

_redis_client: aioredis.Redis | None = None
_fallback_counters: dict[str, tuple[int, int]] = {}


def _redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.Redis.from_url(agent_config().redis_url, decode_responses=True)
    return _redis_client


def mask_email(value: str | None) -> str:
    text = str(value or "").strip()
    if not text or "@" not in text:
        return ""
    local, domain = text.split("@", 1)
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


def mask_identifier(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "@" in text:
        return mask_email(text)
    if len(text) <= 2:
        return "*" * len(text)
    return f"{text[:1]}***{text[-1:]}"


def _clean_payload(obj: Any) -> Any:
    if obj is None or isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return [_clean_payload(item) for item in obj[:100]]
    if isinstance(obj, dict):
        cleaned: Dict[str, Any] = {}
        for key, value in list(obj.items())[:100]:
            name = str(key)
            lowered = name.lower()
            if lowered in {"token", "access_token", "refresh_token", "authorization", "auth_header", "password"}:
                cleaned[name] = "[REDACTED]"
                continue
            if lowered == "email":
                cleaned[name] = mask_email(str(value or ""))
                continue
            if lowered == "identifier":
                cleaned[name] = mask_identifier(str(value or ""))
                continue
            cleaned[name] = _clean_payload(value)
        return cleaned
    return str(obj)


def audit_auth_event(event: str, payload: Dict[str, Any] | None = None) -> None:
    if not bool(log_config().auth_audit_logging_enabled):
        return
    record = {
        "ts": int(time.time()),
        "event": str(event or ""),
        **_clean_payload(payload or {}),
    }
    try:
        logging.getLogger("mevzuat.auth").info(json.dumps(record, ensure_ascii=False, default=str))
    except Exception:
        return


async def track_burst(
    signal: str,
    *,
    key: str,
    threshold: int,
    window_seconds: int,
    payload: Dict[str, Any] | None = None,
) -> None:
    if threshold <= 0 or window_seconds <= 0:
        return

    count = 0
    cache_key = f"auth:burst:{signal}:{key}"
    now = int(time.time())
    try:
        client = _redis()
        count = int(await client.incr(cache_key))
        if count == 1:
            await client.expire(cache_key, int(window_seconds))
    except Exception:
        expires_at, prev_count = _fallback_counters.get(cache_key, (0, 0))
        if expires_at <= now:
            prev_count = 0
            expires_at = now + int(window_seconds)
        count = int(prev_count) + 1
        _fallback_counters[cache_key] = (expires_at, count)

    if count < int(threshold):
        return

    audit_auth_event(
        "auth_abuse_signal",
        {
            "signal": str(signal),
            "key": str(key),
            "count": int(count),
            "window_seconds": int(window_seconds),
            **(payload or {}),
        },
    )
