from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Mapping

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


_SLUG_RE = re.compile(r"^[a-z0-9_:-]+$")


def _mask_value(key: str, value: Any) -> Any:
    lowered = str(key or "").strip().lower()
    if lowered in {"password", "token", "access_token", "refresh_token", "authorization"}:
        return "[REDACTED]"
    if lowered == "email":
        text = str(value or "").strip()
        if not text or "@" not in text:
            return ""
        local, domain = text.split("@", 1)
        if not local:
            return f"***@{domain}"
        if len(local) == 1:
            return f"{local}***@{domain}"
        return f"{local[0]}***{local[-1]}@{domain}"
    return value


def _sanitize_validation_body(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _mask_value(str(k), _sanitize_validation_body(v)) for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        return [_sanitize_validation_body(item) for item in value[:50]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


async def _build_validation_log_payload(request: Request, exc: RequestValidationError) -> Dict[str, Any]:
    raw_body = b""
    try:
        raw_body = await request.body()
    except Exception:
        raw_body = b""

    parsed_body: Any = None
    if raw_body:
        try:
            parsed_body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            parsed_body = raw_body.decode("utf-8", errors="replace")[:500]

    body_keys: list[str] = []
    if isinstance(parsed_body, dict):
        body_keys = sorted(str(key) for key in parsed_body.keys())[:50]

    return {
        "event": "request_validation_error",
        "request_id": getattr(getattr(request, "state", None), "request_id", None),
        "method": request.method,
        "path": request.url.path,
        "content_type": request.headers.get("content-type"),
        "body_keys": body_keys,
        "body": _sanitize_validation_body(parsed_body),
        "errors": exc.errors(),
    }


def reason_for_status(status_code: int) -> str:
    mapping = {
        402: "insufficient_credits",
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
        502: "bad_gateway",
        503: "service_unavailable",
        504: "gateway_timeout",
    }
    return mapping.get(int(status_code), "error")


def status_for_reason(reason: str) -> int:
    r = (reason or "").strip().lower()
    if not r:
        return 500
    if r in {
        "bad_request",
        "empty_query",
        "empty_intent",
        "invalid_identifier",
        "invalid_email",
        "invalid_phone_number",
        "invalid_username",
        "weak_password",
        "invalid_reset_token",
        "invalid_main_agent_verbosity",
        "invalid_main_agent_reasoning_effort",
        "invalid_ictihat_agent_reasoning_effort",
        "extra_instructions_too_long",
        "missing_document_id_or_filters",
        "wrong_token_type",
        "invalid_parent_plan",
        "invalid_account_type",
        "invalid_account_plan",
        "invalid_coupon_quantity",
        "invalid_coupon_plan",
        "invalid_coupon_code",
        "invalid_coupon_payload",
        "invalid_coupon_campaign_name",
        "invalid_coupon_distribution_mode",
        "invalid_coupon_selection",
        "unsupported_account_type",
        "no_patch_fields",
        "invalid_account_type_transition",
        "bad_contract",
    }:
        return 400
    if r in {"unauthorized", "invalid_token", "invalid_refresh", "invalid_credentials", "refresh_unknown", "refresh_already_rotated", "refresh_reuse_detected", "refresh_revoked_or_expired", "missing_authorization"}:
        return 401
    if r in {"access_revoked", "session_revoked", "missing_jti", "invalid_access_version"}:
        return 401
    if r in {"insufficient_credits", "insufficient_parent_credits"}:
        return 402
    if r in {"forbidden", "parent_required", "child_account_delete_forbidden"}:
        return 403
    if r in {"not_found", "user_not_found", "document_not_found", "chat_not_found", "no_results", "child_not_found", "coupon_not_found"}:
        return 404
    if r in {"username_taken", "email_taken", "conflict", "ambiguous", "child_limit_reached", "parent_has_children", "child_credit_detach_failed", "coupon_already_used", "coupon_already_redeemed_by_user", "coupon_plan_change_confirmation_required", "coupon_code_exists"}:
        return 409
    if r == "validation_error":
        return 422
    if r == "rate_limited":
        return 429
    if r == "openai_timeout":
        return 504
    if r in {"openai_unavailable", "agent_failed", "bad_json", "search_failed"}:
        return 502
    if r in {"elasticsearch_unavailable", "qdrant_unavailable", "search_unavailable"}:
        return 503
    # LLM/agent free-form or localized messages are not internal server errors.
    if r and not _SLUG_RE.match(r):
        return 400
    return 500


def api_error(status_code: int, reason: str, detail: Any | None = None, **extra: Any) -> HTTPException:
    payload: Dict[str, Any] = {"ok": False, "reason": str(reason)}
    if detail is not None:
        payload["detail"] = detail
    payload.update({k: v for k, v in extra.items() if v is not None})
    return HTTPException(status_code=int(status_code), detail=payload)


def _normalize_http_exception_detail(status_code: int, detail: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": False}
    default_reason = reason_for_status(int(status_code))

    if isinstance(detail, Mapping):
        for key, value in detail.items():
            if key == "ok":
                continue
            payload[str(key)] = value
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            payload["reason"] = default_reason
        return payload

    if isinstance(detail, str) and detail.strip():
        raw = detail.strip()
        if _SLUG_RE.match(raw):
            payload["reason"] = raw
            return payload
        payload["reason"] = default_reason
        if int(status_code) < 500:
            payload["detail"] = raw
        return payload

    payload["reason"] = default_reason
    return payload


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    content = jsonable_encoder(_normalize_http_exception_detail(int(exc.status_code), exc.detail))
    headers = dict(exc.headers or {})
    return JSONResponse(status_code=int(exc.status_code), content=content, headers=headers or None)


async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    try:
        payload = await _build_validation_log_payload(request, exc)
        logging.getLogger("mevzuat.api").warning(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        logging.getLogger("mevzuat.api").warning("Failed to log request validation error")
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"ok": False, "reason": "validation_error", "detail": exc.errors()}),
    )


async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    logging.getLogger("mevzuat.api").exception("Unhandled API exception")
    return JSONResponse(status_code=500, content=jsonable_encoder({"ok": False, "reason": "internal_error"}))
