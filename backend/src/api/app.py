from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import (
    agent_config,
    app_config,
    config_dir_name,
    db_pool_size,
    db_total_pool_size,
    db_worker_count,
    jwt_config,
    load_env,
    log_config,
    redis_shutdown_flush_mode,
)
from ..db import close_db_pool, core_db, db_pool_info
from ..ai.client.openai_clients import close_openai_clients
from ..ai.memory.redis_memory import RedisMemory
from ..ai.tool_wrappers.ictihat_get_document import close_doc_cache_client
from ..ai.tool_wrappers.ictihat_repository import close_ictihat_search_clients
from ..calendar_events.reminder import run_reminder_loop as run_calendar_reminder_loop
from ..services.ictihat_daire_cache_service import warm_ictihat_daire_cache
from ..services.public_stats_service import PublicStatsService
from .routes.request_logging import RequestLoggingMiddleware, configure_logging
from .routes.routes_accounts import router as accounts_router
from .routes.routes_admin import router as admin_router
from .routes.routes_auth import router as auth_router
from .routes.routes_calendar import router as calendar_router
from .routes.routes_chat import router as chat_router
from .routes.routes_coupons import router as coupons_router
from .routes.routes_documents import router as documents_router
from .routes.routes_ephemeral_files import router as files_router
from .routes.routes_generated_documents import router as generated_documents_router
from .routes.routes_ictihat import router as ictihat_router
from .routes.routes_petitions import router as petitions_router
from .routes.routes_public import router as public_router
from .routes.routes_support import router as support_router
from .routes.routes_user_config import router as user_config_router
from .routes.routes_ws import router as ws_router
from .middleware import AuthMiddleware, GlobalRateLimitMiddleware, close_global_rate_limit_redis_clients
from .errors import (
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)

_BACKEND_QUERY_TIMEOUT_SECONDS = 20


def _build_backend_async_client(*, timeout_seconds: float, verify: bool = True, auth: tuple[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        verify=verify,
        auth=auth,
        follow_redirects=True,
    )


def _jwt_secret_is_weak(secret: str, *, min_length: int) -> bool:
    value = str(secret or "")
    stripped = value.strip()
    if len(stripped) < int(min_length):
        return True
    lowered = stripped.lower()
    if lowered in {
        "jwt_secret",
        "secret",
        "changeme",
        "change-me",
        "dev-secret",
        "test-secret",
        "password",
        "mevzuat",
    }:
        return True
    if len(set(stripped)) <= 3:
        return True
    return False


async def _check_elasticsearch() -> Tuple[bool, str]:
    try:
        cfg = agent_config()
        base_url = str(cfg.elasticsearch_url or "").strip().rstrip("/")
        index_name = str(cfg.elasticsearch_index_ictihat or "").strip()
        if not base_url or not index_name:
            return False, "missing_elasticsearch_config"
        headers = {"Content-Type": "application/json"}
        auth = None
        api_key = str(cfg.elasticsearch_api_key or "").strip()
        username = str(cfg.elasticsearch_username or "").strip()
        password = str(cfg.elasticsearch_password or "").strip()
        if api_key:
            headers["Authorization"] = f"ApiKey {api_key}"
        elif username or password:
            auth = (username, password)
        async with _build_backend_async_client(
            timeout_seconds=float(_BACKEND_QUERY_TIMEOUT_SECONDS),
            verify=bool(cfg.elasticsearch_verify_certs),
            auth=auth,
        ) as client:
            response = await client.post(
                f"{base_url}/{index_name}/_count",
                headers=headers,
                json={"query": {"match_all": {}}},
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("count") is None:
            return False, "invalid_elasticsearch_response"
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


async def _check_qdrant() -> Tuple[bool, str]:
    try:
        cfg = agent_config()
        base_url = str(cfg.qdrant_url or "").strip().rstrip("/")
        collection = str(cfg.qdrant_index_ictihat or "").strip()
        if not base_url or not collection:
            return False, "missing_qdrant_config"
        headers = {}
        api_key = str(cfg.qdrant_api_key or "").strip()
        if api_key:
            headers["api-key"] = api_key
        async with _build_backend_async_client(timeout_seconds=float(_BACKEND_QUERY_TIMEOUT_SECONDS)) as client:
            response = await client.get(
                f"{base_url}/collections/{collection}",
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        return (True, "ok") if isinstance(result, dict) else (False, "missing_result")
    except Exception as exc:
        return False, str(exc)


def create_app() -> FastAPI:
    load_env()
    app_cfg = app_config()
    jwt_cfg = jwt_config()
    log_cfg = log_config()
    if not bool(log_cfg.dev_mode):
        if app_cfg.auth_dev_mode:
            raise RuntimeError("auth_dev_mode must be false when dev_mode=0")
        if app_cfg.auth_debug:
            raise RuntimeError("auth_debug must be false when dev_mode=0")
        if app_cfg.jwt_require_strong_secret and jwt_cfg.jwt_mode == "hs256":
            if _jwt_secret_is_weak(jwt_cfg.jwt_secret, min_length=int(app_cfg.jwt_secret_min_length)):
                raise RuntimeError("JWT_SECRET is too weak for production")
        if app_cfg.trust_proxy and not app_cfg.trusted_proxy_ips:
            raise RuntimeError("trusted_proxy_ips must be configured when trust_proxy=true and dev_mode=0")
        if not app_cfg.allowed_http_origins:
            raise RuntimeError("allowed_http_origins must be configured when dev_mode=0")
        if not app_cfg.allowed_ws_origins:
            raise RuntimeError("allowed_ws_origins must be configured when dev_mode=0")
    configure_logging()
    app = FastAPI(title="Yargucu API", version="0.1.0")
    if app_cfg.cors_enabled:
        allow_all_cors = "*" in app_cfg.allowed_http_origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"] if allow_all_cors else list(app_cfg.allowed_http_origins),
            allow_credentials=not allow_all_cors,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_middleware(RequestLoggingMiddleware)
    # Keep auth and rate limiting separate.
    # Add auth first, then wrap the whole HTTP app with IP-based rate limiting.
    rate = int(app_cfg.rate_limit_rps)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(GlobalRateLimitMiddleware, rate_limit_per_sec=rate, per_path_rpm=app_cfg.path_rate_limits_rpm)
    app.include_router(auth_router, prefix="/v1")
    app.include_router(user_config_router, prefix="/v1")
    app.include_router(chat_router, prefix="/v1")
    app.include_router(documents_router, prefix="/v1")
    app.include_router(generated_documents_router, prefix="/v1")
    app.include_router(petitions_router, prefix="/v1")
    app.include_router(calendar_router, prefix="/v1")
    app.include_router(files_router, prefix="/v1")
    app.include_router(ictihat_router, prefix="/v1")
    app.include_router(ws_router, prefix="/v1")
    app.include_router(public_router, prefix="/v1")
    app.include_router(support_router, prefix="/v1")
    app.include_router(accounts_router, prefix="/v1")
    app.include_router(coupons_router, prefix="/v1")
    app.include_router(admin_router, prefix="/v1")
    public_stats_service = PublicStatsService()

    def _check_mysql(cm, tables: list[str]) -> Tuple[bool, str]:
        try:
            with cm() as conn:
                cur = conn.cursor()
                for t in tables:
                    cur.execute(f"SELECT 1 FROM {t} LIMIT 1")
                    cur.fetchone()
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    @app.get("/v1/health")
    async def health():
        checks: Dict[str, Any] = {}

        # Redis is optional (we have in-process fallback); report but don't fail readiness.
        try:
            mem = RedisMemory()
            await mem.redis.ping()
            checks["redis"] = {"ok": True}
        except Exception as exc:
            checks["redis"] = {"ok": False, "detail": str(exc)}

        es_ok, es_detail = await _check_elasticsearch()
        qdrant_ok, qdrant_detail = await _check_qdrant()
        core_ok, core_detail = await asyncio.to_thread(
            _check_mysql, core_db, ["users", "chats", "chat_messages", "user_usages"]
        )
        checks["elasticsearch_ictihat"] = {"ok": bool(es_ok), "detail": es_detail if not es_ok else None}
        checks["qdrant_ictihat"] = {"ok": bool(qdrant_ok), "detail": qdrant_detail if not qdrant_ok else None}
        checks["database_app_tables"] = {"ok": bool(core_ok), "detail": core_detail if not core_ok else None}

        ok = bool(es_ok and qdrant_ok and core_ok)
        status = 200 if ok else 503
        return JSONResponse(status_code=status, content={"ok": ok, "checks": checks})

    @app.on_event("startup")
    async def _startup_migrations():
        # Log DB connectivity status early (helps debug auth/env issues).
        def _cfg_payload() -> Dict[str, Any]:
            try:
                return {
                    "kind": "db",
                    "config_dir": config_dir_name(),
                    "db_pool_size": int(db_pool_size()),
                    "db_total_pool_size": int(db_total_pool_size()),
                    "db_worker_count": int(db_worker_count()),
                    "jwt_mode": jwt_cfg.jwt_mode,
                    "jwt_alg": jwt_cfg.jwt_alg,
                    "jwt_secret_len": len(jwt_cfg.jwt_secret or ""),
                    "trust_proxy": bool(app_cfg.trust_proxy),
                }
            except Exception:
                return {"kind": "db"}

        def _probe(cm) -> Dict[str, Any]:
            t0 = time.time()
            ok = False
            detail: str | None = None
            try:
                with cm() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT 1")
                    cur.fetchone()
                ok = True
            except Exception as exc:
                ok = False
                detail = str(exc)
            return {
                "ts": int(time.time()),
                "event": "startup_db_probe",
                **_cfg_payload(),
                "ok": bool(ok),
                "duration_ms": int((time.time() - t0) * 1000),
                "detail": detail,
            }

        # Run probes in threads (connectors are blocking).
        payload = await asyncio.to_thread(_probe, core_db)
        logging.getLogger("mevzuat").info(json.dumps(payload, ensure_ascii=False))

        if not bool(log_cfg.dev_mode):
            auth_ok, auth_detail = await asyncio.to_thread(
                _check_mysql,
                core_db,
                ["users", "auth_refresh_tokens", "auth_user_state", "auth_password_reset_tokens"],
            )
            if not auth_ok:
                raise RuntimeError(f"critical_auth_tables_unavailable:{auth_detail}")

        # DB schema/DDL is managed externally. App does not run migrations.
        # Best-effort: warm daire names cache for UI dropdowns.
        # IMPORTANT: do not block app startup on large ictihat tables.
        async def _warm_daire() -> None:
            try:
                await warm_ictihat_daire_cache()
                logging.getLogger("mevzuat").info(
                    json.dumps(
                        {"ts": int(time.time()), "event": "warm_ictihat_daire_cache_done"},
                        ensure_ascii=False,
                    )
                )
            except Exception as exc:
                logging.getLogger("mevzuat").info(
                    json.dumps(
                        {"ts": int(time.time()), "event": "warm_ictihat_daire_cache_error", "detail": str(exc)},
                        ensure_ascii=False,
                    )
                )

        try:
            asyncio.create_task(_warm_daire())
            logging.getLogger("mevzuat").info(
                json.dumps({"ts": int(time.time()), "event": "warm_ictihat_daire_cache_started"}, ensure_ascii=False)
            )
        except Exception:
            pass

        async def _run_active_user_count_updater() -> None:
            try:
                stop_event = getattr(app.state, "active_user_count_stop_event")
                await public_stats_service.run_active_user_count_updater(stop_event=stop_event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logging.getLogger("mevzuat").info(
                    json.dumps(
                        {
                            "ts": int(time.time()),
                            "event": "active_user_count_updater_error",
                            "detail": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )

        try:
            app.state.active_user_count_stop_event = asyncio.Event()
            app.state.active_user_count_task = asyncio.create_task(_run_active_user_count_updater())
            logging.getLogger("mevzuat").info(
                json.dumps({"ts": int(time.time()), "event": "active_user_count_updater_started"}, ensure_ascii=False)
            )
        except Exception:
            pass

        async def _run_calendar_reminder() -> None:
            try:
                stop_event = getattr(app.state, "calendar_reminder_stop_event")
                await run_calendar_reminder_loop(stop_event=stop_event)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logging.getLogger("mevzuat").info(
                    json.dumps(
                        {
                            "ts": int(time.time()),
                            "event": "calendar_reminder_loop_error",
                            "detail": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )

        try:
            app.state.calendar_reminder_stop_event = asyncio.Event()
            app.state.calendar_reminder_task = asyncio.create_task(_run_calendar_reminder())
            logging.getLogger("mevzuat").info(
                json.dumps({"ts": int(time.time()), "event": "calendar_reminder_started"}, ensure_ascii=False)
            )
        except Exception:
            pass

    @app.on_event("shutdown")
    async def _shutdown_cleanup():
        flush_mode = redis_shutdown_flush_mode()
        payload = {
            "ts": int(time.time()),
            "event": "shutdown_cleanup_start",
            "redis_shutdown_flush_mode": flush_mode,
            **db_pool_info(),
        }
        logging.getLogger("mevzuat").info(json.dumps(payload, ensure_ascii=False))
        try:
            await close_doc_cache_client()
        except Exception:
            pass
        try:
            await close_openai_clients()
        except Exception:
            pass
        try:
            await close_ictihat_search_clients()
        except Exception:
            pass
        try:
            await close_global_rate_limit_redis_clients()
        except Exception:
            pass
        stop_event = getattr(app.state, "active_user_count_stop_event", None)
        if stop_event is not None:
            try:
                stop_event.set()
            except Exception:
                pass
        task = getattr(app.state, "active_user_count_task", None)
        if task is not None:
            try:
                await asyncio.wait_for(task, timeout=5)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await asyncio.gather(task, return_exceptions=True)
                except Exception:
                    pass
            except asyncio.CancelledError:
                try:
                    task.cancel()
                except Exception:
                    pass
                try:
                    await asyncio.gather(task, return_exceptions=True)
                except Exception:
                    pass
            except Exception:
                pass

        cal_stop = getattr(app.state, "calendar_reminder_stop_event", None)
        if cal_stop is not None:
            try:
                cal_stop.set()
            except Exception:
                pass
        cal_task = getattr(app.state, "calendar_reminder_task", None)
        if cal_task is not None:
            try:
                await asyncio.wait_for(cal_task, timeout=5)
            except asyncio.TimeoutError:
                cal_task.cancel()
                try:
                    await asyncio.gather(cal_task, return_exceptions=True)
                except Exception:
                    pass
            except asyncio.CancelledError:
                try:
                    cal_task.cancel()
                except Exception:
                    pass
                try:
                    await asyncio.gather(cal_task, return_exceptions=True)
                except Exception:
                    pass
            except Exception:
                pass
        if flush_mode != "off":
            try:
                redis_client = RedisMemory().redis
                try:
                    if flush_mode == "flushall":
                        await redis_client.flushall()
                    else:
                        await redis_client.flushdb()
                finally:
                    await redis_client.aclose()
            except Exception as exc:
                logging.getLogger("mevzuat").info(
                    json.dumps(
                        {
                            "ts": int(time.time()),
                            "event": "shutdown_redis_flush_error",
                            "mode": flush_mode,
                            "detail": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )
        try:
            await asyncio.to_thread(close_db_pool)
        except Exception:
            pass
        logging.getLogger("mevzuat").info(
            json.dumps({"ts": int(time.time()), "event": "shutdown_cleanup_done"}, ensure_ascii=False)
        )
    return app


app = create_app()

