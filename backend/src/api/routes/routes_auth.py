from __future__ import annotations
import asyncio
import hashlib
import secrets
import time
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel

from ...data.db_auth_repository import AuthRepository
from ...data.db_user_repository import UserRepository
from ...security.passwords import hash_password, verify_password
from ...services.account_service import AccountService
from ...services.coupon_service import CouponService
from ...services.mail_service import MailService
from ...utils.auth_audit import audit_auth_event, mask_email, mask_identifier, track_burst
from ...utils.dev_logging import dev_log
from ...utils.mail_verification import MailVerification
from ...config import app_config, jwt_config
from ..auth import (
    decode_and_validate_token,
    extract_bearer_token,
    issue_tokens,
    issue_tokens_with_timing,
    payload_exp,
    payload_jti,
    payload_user_id,
    ts_to_utc_datetime,
)
from ..client_ip import resolve_client_ip


router = APIRouter(prefix="/auth", tags=["auth"])


def _new_login_latency_breakdown() -> Dict[str, int]:
    return {
        "user_lookup_ms": 0,
        "password_verify_ms": 0,
        "token_version_ms": 0,
        "token_encode_ms": 0,
        "issue_tokens_ms": 0,
        "refresh_store_ms": 0,
        "track_burst_ms": 0,
    }


def _hash_password_reset_token(raw_token: str) -> str:
    return hashlib.sha256(str(raw_token or "").encode("utf-8")).hexdigest()


def _build_password_reset_url(raw_token: str) -> str:
    base = app_config().password_reset_url_base.strip()
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}token={quote(str(raw_token), safe='')}"

class UpdateMeRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None


class RegisterRequest(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    phone: Optional[str] = None
    coupon_code: Optional[str] = None
    entry_code: Optional[str] = None


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    raw = (value or "").strip()
    if not raw:
        return None
    allowed = set("+0123456789() -")
    if any(ch not in allowed for ch in raw) or len(raw) > 32:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_phone_number"})
    return raw


def _account_plan_for_entry_code(value: Optional[str]) -> str:
    return "student" if str(value or "").strip().lower() == "st1" else "free"


@router.post("/dev/issue", response_model=dict)
async def dev_issue_tokens(
    user_id: int = Body(embed=True),
) -> Dict[str, Any]:
    """
    DEV ONLY: Issue tokens for a given user_id without password login.
    Enabled only when AUTH_DEV_MODE=1.
    """
    if not app_config().auth_dev_mode:
        raise HTTPException(status_code=404, detail="not_found")

    issued = await asyncio.to_thread(issue_tokens, user_id=int(user_id))
    return {
        "ok": True,
        "access_token": issued.access_token,
        "refresh_token": issued.refresh_token,
        "access_expires_at": issued.access_expires_at,
        "refresh_expires_at": issued.refresh_expires_at,
    }


@router.post("/refresh", response_model=dict)
async def refresh_tokens(
    request: Request,
    refresh_token: str = Body(embed=True),
) -> Dict[str, Any]:
    payload, err = decode_and_validate_token(refresh_token, expected_type="refresh")
    if payload is None:
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "invalid_refresh", "detail": err})

    jti = payload_jti(payload)
    if not jti:
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "invalid_refresh", "detail": "missing_jti"})

    # Reuse detection: if a revoked token is presented again, revoke ALL sessions.
    status = await asyncio.to_thread(AuthRepository.get_refresh_token_status, jti=jti)
    if not status:
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "refresh_unknown"})
    if int(status.get("revoked") or 0) == 1:
        # Grace window: concurrent refresh can cause the old token to be used twice.
        # If revoked very recently, treat it as "already rotated" instead of an attack.
        cfg = jwt_config()
        revoked_at = status.get("revoked_at")
        try:
            from datetime import datetime as _dt

            if revoked_at and isinstance(revoked_at, _dt):
                age = (_dt.utcnow() - revoked_at).total_seconds()
                if age <= int(cfg.refresh_reuse_grace_seconds):
                    raise HTTPException(status_code=401, detail={"ok": False, "reason": "refresh_already_rotated"})
        except HTTPException:
            raise
        except Exception:
            pass

        # Token reuse outside grace -> revoke all user refresh tokens as safety measure.
        try:
            await asyncio.to_thread(AuthRepository.revoke_all_refresh_tokens_for_user, user_id=int(status["user_id"]))
        except Exception:
            pass
        try:
            await asyncio.to_thread(AuthRepository.bump_token_version, user_id=int(status["user_id"]))
        except Exception:
            pass
        user_id = int(status.get("user_id") or 0)
        client_ip = resolve_client_ip(request)
        audit_auth_event(
            "refresh_reuse_detected",
            {"user_id": user_id or None, "ip": client_ip, "jti": "[REDACTED]"},
        )
        if user_id > 0:
            await track_burst(
                "refresh_reuse_detected",
                key=str(user_id),
                threshold=3,
                window_seconds=1800,
                payload={"user_id": user_id, "ip": client_ip},
            )
            audit_auth_event("session_revoked", {"user_id": user_id, "reason": "refresh_reuse_detected"})
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "refresh_reuse_detected"})
    if not await asyncio.to_thread(AuthRepository.is_refresh_jti_valid, jti=jti):
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "refresh_revoked_or_expired"})

    user_id = payload_user_id(payload)

    # Rotation: revoke old jti, issue a new refresh token
    await asyncio.to_thread(AuthRepository.revoke_refresh_jti, jti=jti)
    issued = await asyncio.to_thread(issue_tokens, user_id=user_id)

    return {
        "ok": True,
        "access_token": issued.access_token,
        "refresh_token": issued.refresh_token,
        "access_expires_at": issued.access_expires_at,
        "refresh_expires_at": issued.refresh_expires_at,
    }


@router.post("/logout", response_model=dict)
async def logout(
    request: Request,
    refresh_token: str = Body(embed=True),
) -> Dict[str, Any]:
    payload, err = decode_and_validate_token(refresh_token, expected_type="refresh")
    if payload is None:
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "invalid_refresh", "detail": err})
    jti = payload_jti(payload)
    user_id = int(payload_user_id(payload))
    if jti:
        await asyncio.to_thread(AuthRepository.revoke_refresh_jti, jti=jti)
    access_token = extract_bearer_token(request.headers)
    if access_token:
        access_payload, _ = decode_and_validate_token(access_token, expected_type="access")
        if access_payload is not None:
            access_jti = payload_jti(access_payload)
            if access_jti:
                try:
                    await AuthRepository.deny_access_jti(jti=access_jti, expires_at_ts=payload_exp(access_payload))
                except Exception:
                    pass
                audit_auth_event("access_revoked", {"user_id": user_id, "ip": resolve_client_ip(request)})
    return {"ok": True}


@router.get("/me", response_model=dict)
async def me(request: Request) -> Dict[str, Any]:
    """
    Return current user profile (requires access token; middleware sets request.state.user_id).
    """
    user_id = int(getattr(request.state, "user_id"))
    try:
        user = await asyncio.to_thread(AccountService.build_user_profile, user_id=user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "user_not_found"})
    return {"ok": True, "user": user}


@router.patch("/me", response_model=dict)
async def update_me(request: Request, payload: UpdateMeRequest) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    user = await asyncio.to_thread(UserRepository.get_by_user_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "user_not_found"})

    username = payload.username
    email = payload.email
    full_name = payload.full_name

    if username is not None:
        username = (username or "").strip()
        if len(username) < 3 or "@" in username:
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_username"})
        if await asyncio.to_thread(UserRepository.is_username_taken, username=username, exclude_user_id=user_id):
            raise HTTPException(status_code=409, detail={"ok": False, "reason": "username_taken"})

    if email is not None:
        email = (email or "").strip()
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_email"})
        if await asyncio.to_thread(UserRepository.is_email_taken, email=email, exclude_user_id=user_id):
            raise HTTPException(status_code=409, detail={"ok": False, "reason": "email_taken"})

    if full_name is not None:
        full_name = (full_name or "").strip()

    await asyncio.to_thread(UserRepository.update_profile, user_id=user_id, username=username, email=email, full_name=full_name)
    updated = await asyncio.to_thread(AccountService.build_user_profile, user_id=user_id)
    return {"ok": True, "user": updated}


@router.post("/change_password", response_model=dict)
async def change_password(
    request: Request,
    current_password: str = Body(embed=True),
    new_password: str = Body(embed=True),
) -> Dict[str, Any]:
    """
    Change password for the authenticated user and revoke all refresh tokens.
    """
    user_id = int(getattr(request.state, "user_id"))
    user = await asyncio.to_thread(UserRepository.get_by_user_id_with_hash, user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "user_not_found"})

    if not await asyncio.to_thread(verify_password, current_password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "invalid_credentials"})

    if not isinstance(new_password, str) or len(new_password) < 8:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "weak_password"})

    new_hash = await asyncio.to_thread(hash_password, new_password)
    await asyncio.to_thread(UserRepository.update_password_hash, user_id=user_id, password_hash=new_hash)

    # Revoke all refresh tokens to force re-login on other devices/sessions.
    try:
        await asyncio.to_thread(AuthRepository.revoke_all_refresh_tokens_for_user, user_id=user_id)
    except Exception:
        pass
    try:
        await asyncio.to_thread(AuthRepository.bump_token_version, user_id=user_id)
    except Exception:
        pass
    audit_auth_event("password_changed", {"user_id": user_id, "ip": resolve_client_ip(request)})
    audit_auth_event("session_revoked", {"user_id": user_id, "reason": "password_changed"})

    return {"ok": True}


@router.post("/register", response_model=dict)
async def register(payload: RegisterRequest) -> Dict[str, Any]:
    username = (payload.username or "").strip()
    email = (payload.email or "").strip()
    full_name = (payload.full_name or "").strip()
    password = payload.password or ""
    phone = _normalize_phone(payload.phone)
    coupon_code = (payload.coupon_code or "").strip()
    account_plan = _account_plan_for_entry_code(payload.entry_code)

    if not username or len(username) < 3 or "@" in username:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_username"})
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_email"})
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "weak_password"})

    if await asyncio.to_thread(UserRepository.get_by_username_or_email, username) is not None:
        raise HTTPException(status_code=409, detail={"ok": False, "reason": "username_taken"})
    if await asyncio.to_thread(UserRepository.get_by_username_or_email, email) is not None:
        raise HTTPException(status_code=409, detail={"ok": False, "reason": "email_taken"})

    # Deliverability verification (EmailListVerify). When enabled, do not register if not deliverable.
    try:
        verifier = MailVerification()
        if not await asyncio.to_thread(verifier.verify_deliverable, email):
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "email_not_deliverable"})
    except HTTPException:
        raise
    except Exception as exc:
        # Misconfiguration or unexpected error
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "mail_verification_error", "detail": str(exc)})

    pw_hash = await asyncio.to_thread(hash_password, password)
    try:
        user_id = await asyncio.to_thread(
            UserRepository.create_user,
            username=username,
            email=email,
            full_name=full_name,
            password_hash=pw_hash,
            phone=phone,
            account_plan=account_plan,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "db_error", "detail": str(exc)})

    if coupon_code:
        try:
            await asyncio.to_thread(CouponService.redeem_coupon, user_id=user_id, code=coupon_code)
        except ValueError as exc:
            await asyncio.to_thread(UserRepository.delete_user, user_id=user_id)
            reason = str(exc)
            raise HTTPException(status_code=status_for_reason(reason), detail={"ok": False, "reason": reason})
        except Exception as exc:
            await asyncio.to_thread(UserRepository.delete_user, user_id=user_id)
            raise HTTPException(status_code=500, detail={"ok": False, "reason": "db_error", "detail": str(exc)})

    issued = await asyncio.to_thread(issue_tokens, user_id=user_id)
    return {
        "ok": True,
        "user_id": user_id,
        "access_token": issued.access_token,
        "refresh_token": issued.refresh_token,
        "access_expires_at": issued.access_expires_at,
        "refresh_expires_at": issued.refresh_expires_at,
    }


@router.post("/forgot_password", response_model=dict)
async def forgot_password(
    request: Request,
    identifier: str = Body(embed=True),
) -> Dict[str, Any]:
    """
    Password reset flow with single-use reset token.
    Response remains `ok: true` for valid-looking requests to reduce enumeration risk.
    """
    ident = (identifier or "").strip()
    if not ident:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_identifier"})

    client_ip = resolve_client_ip(request)
    audit_auth_event("forgot_password_requested", {"identifier": mask_identifier(ident), "ip": client_ip})
    await track_burst(
        "reset_request_burst",
        key=client_ip,
        threshold=5,
        window_seconds=900,
        payload={"ip": client_ip},
    )

    user = await asyncio.to_thread(UserRepository.get_by_username_or_email, ident)
    if not user:
        return {"ok": True}

    email = (user.get("email") or "").strip()
    if not email:
        return {"ok": True}

    user_id = int(user["user_id"])
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_password_reset_token(raw_token)
    expires_at = ts_to_utc_datetime(int(time.time()) + int(app_config().password_reset_token_ttl_seconds))
    reset_url = _build_password_reset_url(raw_token)

    try:
        await asyncio.to_thread(AuthRepository.revoke_password_reset_tokens_for_user, user_id=user_id)
        await asyncio.to_thread(
            AuthRepository.store_password_reset_token,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            request_ip=client_ip,
        )
        await MailService.send_password_reset_email(
            to_email=email,
            to_name=(user.get("username") or user.get("full_name") or ""),
            reset_url=reset_url,
        )
    except Exception:
        try:
            await asyncio.to_thread(AuthRepository.revoke_password_reset_tokens_for_user, user_id=user_id)
        except Exception:
            pass
        audit_auth_event(
            "forgot_password_request_failed",
            {"user_id": user_id, "email": mask_email(email), "ip": client_ip},
        )
        return {"ok": True}

    return {"ok": True}


@router.post("/reset_password/confirm", response_model=dict)
async def reset_password_confirm(
    request: Request,
    token: str = Body(embed=True),
    new_password: str = Body(embed=True),
) -> Dict[str, Any]:
    raw_token = (token or "").strip()
    if not raw_token:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_reset_token"})
    if not isinstance(new_password, str) or len(new_password) < 8:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "weak_password"})

    row = await asyncio.to_thread(AuthRepository.consume_password_reset_token, token_hash=_hash_password_reset_token(raw_token))
    if not row:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_reset_token"})

    user_id = int(row["user_id"])
    user = await asyncio.to_thread(UserRepository.get_by_user_id_with_hash, user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "user_not_found"})

    new_hash = await asyncio.to_thread(hash_password, new_password)
    await asyncio.to_thread(UserRepository.update_password_hash, user_id=user_id, password_hash=new_hash)
    try:
        await asyncio.to_thread(AuthRepository.revoke_password_reset_tokens_for_user, user_id=user_id)
    except Exception:
        pass
    try:
        await asyncio.to_thread(AuthRepository.revoke_all_refresh_tokens_for_user, user_id=user_id)
    except Exception:
        pass
    try:
        await asyncio.to_thread(AuthRepository.bump_token_version, user_id=user_id)
    except Exception:
        pass

    client_ip = resolve_client_ip(request)
    audit_auth_event("reset_password_completed", {"user_id": user_id, "ip": client_ip})
    audit_auth_event("session_revoked", {"user_id": user_id, "reason": "password_reset_completed"})
    return {"ok": True}


@router.post("/login", response_model=dict)
async def login(
    request: Request,
    identifier: str = Body(embed=True),
    password: str = Body(embed=True),
) -> Dict[str, Any]:
    """
    Login using either username+password or email+password (identifier field).
    """
    t0 = time.perf_counter()
    client_ip = resolve_client_ip(request)
    latency_breakdown = _new_login_latency_breakdown()
    t_lookup0 = time.perf_counter()
    user = await asyncio.to_thread(UserRepository.get_by_username_or_email, identifier)
    latency_breakdown["user_lookup_ms"] = int((time.perf_counter() - t_lookup0) * 1000)
    if not user:
        audit_auth_event("login_failed", {"identifier": mask_identifier(identifier), "ip": client_ip})
        t_burst0 = time.perf_counter()
        await track_burst(
            "login_failed",
            key=client_ip,
            threshold=5,
            window_seconds=300,
            payload={"ip": client_ip},
        )
        latency_breakdown["track_burst_ms"] = int((time.perf_counter() - t_burst0) * 1000)
        dev_log(
            "auth",
            "auth_login_done",
            {
                "ok": False,
                "reason": "invalid_credentials",
                "identifier": mask_identifier(identifier),
                "user_id": None,
                "duration_ms": int((time.perf_counter() - t0) * 1000),
                "latency_breakdown_ms": latency_breakdown,
            },
        )
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "invalid_credentials"})

    t_verify0 = time.perf_counter()
    password_ok = await asyncio.to_thread(verify_password, password, user.get("password_hash") or "")
    latency_breakdown["password_verify_ms"] = int((time.perf_counter() - t_verify0) * 1000)
    if not password_ok:
        audit_auth_event("login_failed", {"identifier": mask_identifier(identifier), "ip": client_ip, "user_id": int(user["user_id"])})
        t_burst0 = time.perf_counter()
        await track_burst(
            "login_failed",
            key=client_ip,
            threshold=5,
            window_seconds=300,
            payload={"ip": client_ip, "user_id": int(user["user_id"])},
        )
        latency_breakdown["track_burst_ms"] = int((time.perf_counter() - t_burst0) * 1000)
        dev_log(
            "auth",
            "auth_login_done",
            {
                "ok": False,
                "reason": "invalid_credentials",
                "identifier": mask_identifier(identifier),
                "user_id": int(user["user_id"]),
                "duration_ms": int((time.perf_counter() - t0) * 1000),
                "latency_breakdown_ms": latency_breakdown,
            },
        )
        raise HTTPException(status_code=401, detail={"ok": False, "reason": "invalid_credentials"})

    user_id = int(user["user_id"])
    issued, token_timing = await asyncio.to_thread(issue_tokens_with_timing, user_id=user_id)
    latency_breakdown["token_version_ms"] = int(token_timing.get("token_version_ms") or 0)
    latency_breakdown["refresh_store_ms"] = int(token_timing.get("refresh_store_ms") or 0)
    latency_breakdown["token_encode_ms"] = int(token_timing.get("token_encode_ms") or 0)
    latency_breakdown["issue_tokens_ms"] = int(token_timing.get("issue_tokens_ms") or 0)
    audit_auth_event("login_success", {"user_id": user_id, "ip": client_ip})
    dev_log(
        "auth",
        "auth_login_done",
        {
            "ok": True,
            "identifier": mask_identifier(identifier),
            "user_id": user_id,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "latency_breakdown_ms": latency_breakdown,
        },
    )
    return {
        "ok": True,
        "user_id": user_id,
        "access_token": issued.access_token,
        "refresh_token": issued.refresh_token,
        "access_expires_at": issued.access_expires_at,
        "refresh_expires_at": issued.refresh_expires_at,
    }

