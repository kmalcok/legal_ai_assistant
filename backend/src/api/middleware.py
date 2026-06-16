from __future__ import annotations

import time
from dataclasses import dataclass
from weakref import WeakSet
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .auth import payload_user_id, validate_access_token
from .client_ip import resolve_client_ip
from ..config import agent_config, app_config, jwt_config, load_env
from ..services.public_exchange_rate_service import USD_TRY_RATE_PUBLIC_PATH, USD_TRY_RATE_PUBLIC_RATE_LIMIT_RPM
from ..services.public_stats_service import ACTIVE_USER_COUNT_PUBLIC_PATH, ACTIVE_USER_COUNT_PUBLIC_RATE_LIMIT_RPM

COUPON_REDEEM_RATE_LIMIT_RPM = 5


@dataclass(frozen=True)
class AuthConfig:
    jwt_secret: str
    jwt_alg: str
    jwt_issuer: str


def _load_auth_config() -> AuthConfig:
    load_env()
    cfg = jwt_config()
    return AuthConfig(jwt_secret=cfg.jwt_secret, jwt_alg=cfg.jwt_alg, jwt_issuer=cfg.jwt_issuer)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    - Requires Authorization: Bearer <JWT>
    - Extracts user_id from JWT `sub` claim

    Applies to paths under /v1 by default, excluding docs/health.
    """

    def __init__(self, app):
        super().__init__(app)
        self._auth_cfg: Optional[AuthConfig] = None

    def _ensure_clients(self) -> None:
        if self._auth_cfg is None:
            self._auth_cfg = _load_auth_config()

    @staticmethod
    def _should_enforce(path: str) -> bool:
        if not path.startswith("/v1/"):
            return False
        if path.startswith("/v1/health"):
            return False
        # Ephemeral file downloads are capability-based (token + TTL).
        # Do not require access token here; the route performs its own best-effort checks.
        if path.startswith("/v1/files/ephemeral/") and path.endswith("/download"):
            return False
        if path.startswith("/v1/admin/"):
            return False
        # Public auth endpoints (no access token required)
        if path in {
            "/v1/auth/login",
            "/v1/auth/register",
            "/v1/auth/forgot_password",
            "/v1/auth/reset_password/confirm",
            "/v1/auth/refresh",
            "/v1/auth/logout",
            "/v1/auth/dev/issue",
            ACTIVE_USER_COUNT_PUBLIC_PATH,
            USD_TRY_RATE_PUBLIC_PATH,
        }:
            return False
        return True

    @staticmethod
    def _extract_bearer(request: Request) -> Optional[str]:
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth:
            return None
        parts = auth.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return parts[1].strip()

    async def dispatch(self, request: Request, call_next):
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        if not self._should_enforce(request.url.path):
            return await call_next(request)

        try:
            self._ensure_clients()
        except Exception as exc:
            return JSONResponse({"ok": False, "reason": "server_misconfigured", "message": str(exc)}, status_code=500)

        token = self._extract_bearer(request)
        if not token:
            return JSONResponse({"ok": False, "reason": "missing_authorization"}, status_code=401)

        payload, err = await validate_access_token(token)
        if payload is None:
            # Optional debug info (do not leak secrets)
            if app_config().auth_debug:
                cfg = self._auth_cfg
                return JSONResponse(
                    {
                        "ok": False,
                        "reason": "invalid_token",
                        "detail": err or "",
                        "alg": cfg.jwt_alg if cfg else None,
                        "secret_len": len(cfg.jwt_secret) if cfg else None,
                    },
                    status_code=401,
                )
            reason = str(err or "invalid_token")
            return JSONResponse({"ok": False, "reason": reason}, status_code=401)

        user_id = int(payload_user_id(payload))
        request.state.user_id = user_id
        return await call_next(request)


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global/IP-based HTTP rate limiter middleware.

    - Applies to all `/v1/*` HTTP endpoints except health checks
    - Redis-backed (uses REDIS_URL from agent_config), in-memory fallback
    - Enforces a default requests/second limit per client IP
    - Supports stricter per-path RPM rules, e.g. {"/v1/auth/forgot_password": 2}
    """

    _instances: "WeakSet[GlobalRateLimitMiddleware]" = WeakSet()
    _default_path_rpm: Dict[str, int] = {
        ACTIVE_USER_COUNT_PUBLIC_PATH: ACTIVE_USER_COUNT_PUBLIC_RATE_LIMIT_RPM,
        USD_TRY_RATE_PUBLIC_PATH: USD_TRY_RATE_PUBLIC_RATE_LIMIT_RPM,
        "/v1/coupons/redeem": COUPON_REDEEM_RATE_LIMIT_RPM,
    }

    def __init__(self, app, *, rate_limit_per_sec: int = 50, per_path_rpm: Optional[Dict[str, int]] = None):
        super().__init__(app)
        app_cfg = app_config()
        self.rate_limit_per_sec = int(rate_limit_per_sec)
        merged_path_rpm: Dict[str, int] = dict(self._default_path_rpm)
        merged_path_rpm.update({str(k): int(v) for k, v in (per_path_rpm or {}).items()})
        self.per_path_rpm = merged_path_rpm
        self.trust_proxy = bool(app_cfg.trust_proxy)
        self.trusted_proxy_ips = list(app_cfg.trusted_proxy_ips)
        self._redis: Optional[aioredis.Redis] = None
        self._fallback_rps: Dict[str, int] = {}
        self._fallback_rpm: Dict[str, int] = {}
        self._fallback_sec: int = 0
        self._fallback_min: int = 0
        self.__class__._instances.add(self)

    def _ensure_redis(self) -> None:
        if self._redis is None:
            cfg = agent_config()
            self._redis = aioredis.Redis.from_url(cfg.redis_url, decode_responses=True)

    async def close_redis(self) -> None:
        client = self._redis
        self._redis = None
        if client is None:
            return
        try:
            await client.aclose()
        except Exception:
            pass

    @staticmethod
    def _should_enforce(path: str) -> bool:
        if not path.startswith("/v1/"):
            return False
        if path.startswith("/v1/health"):
            return False
        return True

    async def _allow_rpm(self, *, ip: str, path: str, rpm: int) -> tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds).
        """
        if rpm <= 0:
            return True, 0
        now = int(time.time())
        minute = now // 60
        key = f"rl:ip:{ip}:{path}:{minute}"
        try:
            self._ensure_redis()
            assert self._redis is not None
            n = await self._redis.incr(key)
            if int(n) == 1:
                # expire shortly after the minute rolls over
                await self._redis.expire(key, 120)
            allowed = int(n) <= int(rpm)
        except Exception:
            if self._fallback_min != minute:
                self._fallback_min = minute
                self._fallback_rpm = {}
            n = self._fallback_rpm.get(key, 0) + 1
            self._fallback_rpm[key] = n
            allowed = int(n) <= int(rpm)

        retry_after = 0 if allowed else int(60 - (now % 60))
        return bool(allowed), int(retry_after)

    async def _allow_rps(self, *, ip: str, rps: int) -> tuple[bool, int]:
        if rps <= 0:
            return True, 0
        now = int(time.time())
        key = f"rl:ip:{ip}:{now}"
        try:
            self._ensure_redis()
            assert self._redis is not None
            n = await self._redis.incr(key)
            if int(n) == 1:
                await self._redis.expire(key, 2)
            allowed = int(n) <= int(rps)
        except Exception:
            if self._fallback_sec != now:
                self._fallback_sec = now
                self._fallback_rps = {}
            n = self._fallback_rps.get(key, 0) + 1
            self._fallback_rps[key] = n
            allowed = int(n) <= int(rps)
        retry_after = 0 if allowed else 1
        return bool(allowed), int(retry_after)

    async def dispatch(self, request: Request, call_next):
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if not self._should_enforce(path):
            return await call_next(request)

        ip = resolve_client_ip(
            request,
            trust_proxy=self.trust_proxy,
            trusted_proxy_ips=self.trusted_proxy_ips,
        )
        allowed_rps, retry_after_rps = await self._allow_rps(ip=ip, rps=int(self.rate_limit_per_sec))
        if not allowed_rps:
            return JSONResponse(
                {"ok": False, "reason": "rate_limited", "scope": "ip", "limit_rps": int(self.rate_limit_per_sec), "retry_after_sec": int(retry_after_rps)},
                status_code=429,
                headers={"Retry-After": str(int(retry_after_rps))},
            )

        rpm = int(self.per_path_rpm.get(path, 0) or 0)
        if rpm <= 0:
            return await call_next(request)

        allowed, retry_after = await self._allow_rpm(ip=ip, path=path, rpm=int(rpm))
        if not allowed:
            return JSONResponse(
                {"ok": False, "reason": "rate_limited", "scope": "ip", "limit_rpm": int(rpm), "retry_after_sec": int(retry_after)},
                status_code=429,
                headers={"Retry-After": str(int(retry_after))},
            )

        return await call_next(request)


async def close_global_rate_limit_redis_clients() -> None:
    instances = list(GlobalRateLimitMiddleware._instances)
    for inst in instances:
        try:
            await inst.close_redis()
        except Exception:
            pass

