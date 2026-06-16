from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from ...config import log_config


def configure_logging() -> None:
    """
    Minimal structured logging setup (JSON lines).
    Uses standard library only.
    """
    level = log_config().log_level
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format="%(message)s")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Adds:
    - request_id (X-Request-ID) response header
    - JSON log line per request: method, path, status, duration_ms, user_id (if available)
    """

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        try:
            request.state.request_id = req_id
        except Exception:
            pass
        start = time.time()
        status = 500
        try:
            response = await call_next(request)
            status = int(getattr(response, "status_code", 500) or 500)
            try:
                response.headers["X-Request-ID"] = req_id
            except Exception:
                pass
            return response
        except Exception as exc:
            # Log unhandled exception with request_id. Stacktrace only in dev mode.
            duration_ms = int((time.time() - start) * 1000)
            user_id: Optional[int] = None
            try:
                uid = getattr(getattr(request, "state", None), "user_id", None)
                if uid is not None:
                    user_id = int(uid)
            except Exception:
                user_id = None

            payload = {
                "ts": int(time.time()),
                "event": "request_exception",
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": duration_ms,
                "user_id": user_id,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            lg = logging.getLogger("mevzuat")
            if bool(log_config().request_exception_stacktrace_enabled):
                lg.exception(json.dumps(payload, ensure_ascii=False))
            else:
                lg.error(json.dumps(payload, ensure_ascii=False))
            raise
        finally:
            duration_ms = int((time.time() - start) * 1000)
            user_id: Optional[int] = None
            try:
                uid = getattr(getattr(request, "state", None), "user_id", None)
                if uid is not None:
                    user_id = int(uid)
            except Exception:
                user_id = None

            payload = {
                "ts": int(time.time()),
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": status,
                "duration_ms": duration_ms,
                "user_id": user_id,
            }
            if bool(log_config().request_logging_enabled):
                logging.getLogger("mevzuat").info(json.dumps(payload, ensure_ascii=False))


