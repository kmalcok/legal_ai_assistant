from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...data.db_account_repository import (
    ACCOUNT_PLAN_ADVANCED,
    ACCOUNT_PLAN_ENTERPRISE,
    ACCOUNT_PLAN_FREE,
    ACCOUNT_PLAN_PROFESSIONAL,
    ACCOUNT_PLAN_STANDARD,
    ACCOUNT_PLAN_STARTER,
    ACCOUNT_PLAN_STUDENT,
    ACCOUNT_TYPE_CHILD,
    ACCOUNT_TYPE_PARENT,
    ACCOUNT_TYPE_STANDALONE,
)
from ...data.db_admin_usage_repository import AdminUsageRepository
from ...data.db_user_repository import UserRepository
from ...security.passwords import hash_password
from ...services.account_service import AdminAccountService
from ...services.coupon_service import CouponService
from ..client_ip import resolve_client_ip
from ..errors import api_error, status_for_reason

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger("mevzuat.api")


class AdminCreateAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(default="", max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    account_type: str = Field(default=ACCOUNT_TYPE_STANDALONE)
    account_plan: str = Field(default=ACCOUNT_PLAN_FREE)
    initial_credit: float = Field(default=0.0, ge=0.0)


class AdminSetCreditRequest(BaseModel):
    credit: float = Field(..., ge=0.0)


class AdminUpdateAccountRequest(BaseModel):
    account_type: str | None = None
    account_plan: str | None = None


class AdminCreateCouponsRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=500)
    campaign_name: str = Field(..., min_length=1, max_length=255)
    credit_amount: float = Field(default=0.0, ge=0.0)
    distribution_mode: str = Field(default="unique")
    campaign_code: str | None = Field(default=None, max_length=64)
    target_account_plan: str | None = None
    created_by_label: str | None = Field(default=None, max_length=255)


class AdminDeleteCouponsRequest(BaseModel):
    coupon_ids: list[int] = Field(default_factory=list, min_length=1, max_length=1000)


def _raise_reason(reason: str, detail: Any | None = None) -> None:
    raise api_error(status_for_reason(reason), reason, detail=detail)


def _get_account_or_raise(*, user_id: int) -> Dict[str, Any]:
    account = UserRepository.get_by_user_id_with_credit(int(user_id))
    if not account:
        _raise_reason("user_not_found")
    return account


def _parse_account_types(raw: str | None) -> List[str]:
    values = [
        str(item or "").strip().lower()
        for item in str(raw or "").split(",")
        if str(item or "").strip()
    ]
    allowed = {ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT, ACCOUNT_TYPE_CHILD}
    filtered = [item for item in values if item in allowed]
    return filtered or [ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT, ACCOUNT_TYPE_CHILD]


def _audit_admin_action(request: Request, *, action: str, target_user_id: int | None = None, extra: Dict[str, Any] | None = None) -> None:
    payload = {
        "event": "admin_action",
        "action": str(action),
        "target_user_id": int(target_user_id) if target_user_id is not None else None,
        "ip": resolve_client_ip(request),
    }
    if extra:
        payload.update({str(k): v for k, v in extra.items() if v is not None})
    try:
        logger.info(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        logger.info("admin_action %s target=%s", action, target_user_id)


@router.get("/accounts", response_model=dict)
async def list_accounts(account_type: str | None = None, q: str = "") -> Dict[str, Any]:
    accounts = await asyncio.to_thread(
        AdminAccountService.list_accounts,
        account_types=_parse_account_types(account_type),
        query=str(q or "").strip(),
    )
    return {"ok": True, "accounts": accounts, "count": len(accounts)}


@router.get("/accounts/{user_id}/usage-overview", response_model=dict)
async def get_account_usage_overview(request: Request, user_id: int) -> Dict[str, Any]:
    account = await asyncio.to_thread(_get_account_or_raise, user_id=int(user_id))
    usage_overview = await asyncio.to_thread(AdminUsageRepository.get_usage_overview, user_id=int(user_id))
    _audit_admin_action(
        request,
        action="view_usage_overview",
        target_user_id=int(user_id),
    )
    return {"ok": True, "account": account, "usage_overview": usage_overview}


@router.get("/accounts/{user_id}/chats", response_model=dict)
async def list_account_chats(request: Request, user_id: int) -> Dict[str, Any]:
    account = await asyncio.to_thread(_get_account_or_raise, user_id=int(user_id))
    chats = await asyncio.to_thread(AdminUsageRepository.list_chats, user_id=int(user_id))
    _audit_admin_action(
        request,
        action="list_usage_chats",
        target_user_id=int(user_id),
        extra={"chat_count": len(chats)},
    )
    return {"ok": True, "account": account, "chats": chats, "count": len(chats)}


@router.get("/accounts/{user_id}/chats/{chat_id}", response_model=dict)
async def get_account_chat_detail(request: Request, user_id: int, chat_id: int) -> Dict[str, Any]:
    account = await asyncio.to_thread(_get_account_or_raise, user_id=int(user_id))
    detail = await asyncio.to_thread(AdminUsageRepository.get_chat_detail, user_id=int(user_id), chat_id=int(chat_id))
    if not detail:
        _raise_reason("chat_not_found")
    _audit_admin_action(
        request,
        action="view_chat_history",
        target_user_id=int(user_id),
        extra={"chat_id": int(chat_id)},
    )
    return {
        "ok": True,
        "account": account,
        "chat": detail["chat"],
        "history": detail["history"],
        "count": len(detail["history"]),
    }


@router.post("/accounts", response_model=dict)
async def create_account(request: Request, payload: AdminCreateAccountRequest) -> Dict[str, Any]:
    username = (payload.username or "").strip()
    email = (payload.email or "").strip()
    full_name = (payload.full_name or "").strip()
    account_type = str(payload.account_type or "").strip().lower()
    account_plan = str(payload.account_plan or "").strip().lower()

    if len(username) < 3 or "@" in username:
        _raise_reason("invalid_username")
    if "@" not in email:
        _raise_reason("invalid_email")
    if account_type not in {ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT}:
        _raise_reason("invalid_account_type")
    if account_plan not in {
        ACCOUNT_PLAN_FREE,
        ACCOUNT_PLAN_STUDENT,
        ACCOUNT_PLAN_STARTER,
        ACCOUNT_PLAN_STANDARD,
        ACCOUNT_PLAN_ADVANCED,
        ACCOUNT_PLAN_PROFESSIONAL,
        ACCOUNT_PLAN_ENTERPRISE,
    }:
        _raise_reason("invalid_account_plan")
    if await asyncio.to_thread(UserRepository.is_username_taken, username=username):
        _raise_reason("username_taken")
    if await asyncio.to_thread(UserRepository.is_email_taken, email=email):
        _raise_reason("email_taken")

    password_hash = await asyncio.to_thread(hash_password, payload.password)
    try:
        account = await asyncio.to_thread(
            AdminAccountService.create_account,
            username=username,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            account_type=account_type,
            account_plan=account_plan,
            initial_credit=float(payload.initial_credit or 0.0),
        )
    except ValueError as exc:
        _raise_reason(str(exc))

    _audit_admin_action(
        request,
        action="create_account",
        target_user_id=int((account or {}).get("user_id") or 0),
        extra={"account_type": account_type, "account_plan": account_plan},
    )
    return {"ok": True, "account": account}


@router.patch("/accounts/{user_id}/account", response_model=dict)
async def update_account_profile(request: Request, user_id: int, payload: AdminUpdateAccountRequest) -> Dict[str, Any]:
    await asyncio.to_thread(_get_account_or_raise, user_id=int(user_id))
    try:
        account = await asyncio.to_thread(
            AdminAccountService.update_user_account_profile,
            user_id=int(user_id),
            account_type=payload.account_type,
            account_plan=payload.account_plan,
        )
    except ValueError as exc:
        _raise_reason(str(exc))

    _audit_admin_action(
        request,
        action="update_account_profile",
        target_user_id=int(user_id),
        extra={
            "account_type": (str(payload.account_type).strip().lower() if payload.account_type is not None else None),
            "account_plan": (str(payload.account_plan).strip().lower() if payload.account_plan is not None else None),
        },
    )
    return {"ok": True, "account": account}


@router.patch("/accounts/{user_id}/credit", response_model=dict)
async def set_account_credit(request: Request, user_id: int, payload: AdminSetCreditRequest) -> Dict[str, Any]:
    try:
        result = await asyncio.to_thread(
            AdminAccountService.set_account_credit,
            user_id=int(user_id),
            desired_credit=float(payload.credit),
        )
    except ValueError as exc:
        _raise_reason(str(exc))

    _audit_admin_action(
        request,
        action="set_credit",
        target_user_id=int(user_id),
        extra={"credit": float(payload.credit)},
    )
    return {"ok": True, **result}


@router.get("/coupons", response_model=dict)
async def list_coupons(
    limit: int = 25,
    page: int = 1,
    campaign_name: str = "",
    used_status: str = "",
) -> Dict[str, Any]:
    result = await asyncio.to_thread(
        CouponService.list_admin_coupons,
        limit=int(limit),
        page=int(page),
        campaign_name=str(campaign_name or "").strip(),
        used_status=str(used_status or "").strip().lower(),
    )
    coupons = list(result.get("items") or [])
    return {
        "ok": True,
        "coupons": coupons,
        "count": len(coupons),
        "total_count": int(result.get("total_count") or 0),
        "page": int(result.get("page") or 1),
        "page_size": int(result.get("page_size") or limit or 25),
    }


@router.post("/coupons", response_model=dict)
async def create_coupons(request: Request, payload: AdminCreateCouponsRequest) -> Dict[str, Any]:
    target_account_plan = (
        str(payload.target_account_plan or "").strip().lower()
        if payload.target_account_plan is not None
        else None
    )
    try:
        coupons = await asyncio.to_thread(
            CouponService.create_admin_coupons,
            quantity=int(payload.quantity),
            campaign_name=payload.campaign_name,
            credit_amount=float(payload.credit_amount or 0.0),
            distribution_mode=str(payload.distribution_mode or "unique").strip().lower(),
            campaign_code=payload.campaign_code,
            target_account_plan=target_account_plan,
            created_by_label=payload.created_by_label,
        )
    except ValueError as exc:
        _raise_reason(str(exc))

    _audit_admin_action(
        request,
        action="create_coupons",
        extra={
            "coupon_count": len(coupons),
            "campaign_name": payload.campaign_name,
            "credit_amount": float(payload.credit_amount or 0.0),
            "distribution_mode": str(payload.distribution_mode or "unique").strip().lower(),
            "campaign_code": payload.campaign_code,
            "target_account_plan": target_account_plan,
        },
    )
    return {"ok": True, "coupons": coupons, "count": len(coupons)}


@router.post("/coupons/delete", response_model=dict)
async def delete_coupons(request: Request, payload: AdminDeleteCouponsRequest) -> Dict[str, Any]:
    try:
        result = await asyncio.to_thread(
            CouponService.delete_admin_coupons,
            coupon_ids=list(payload.coupon_ids or []),
        )
    except ValueError as exc:
        _raise_reason(str(exc))
    _audit_admin_action(
        request,
        action="delete_coupons",
        extra={"deleted_count": int(result.get("deleted_count") or 0)},
    )
    return {"ok": True, **result}


@router.post("/accounts/{user_id}/reset-password", response_model=dict)
async def reset_account_password(request: Request, user_id: int) -> Dict[str, Any]:
    try:
        result = await asyncio.to_thread(
            AdminAccountService.reset_password,
            user_id=int(user_id),
        )
    except ValueError as exc:
        _raise_reason(str(exc))

    _audit_admin_action(
        request,
        action="reset_password",
        target_user_id=int(user_id),
    )
    return {"ok": True, **result}


@router.delete("/accounts/{user_id}", response_model=dict)
async def delete_account(request: Request, user_id: int) -> Dict[str, Any]:
    try:
        result = await AdminAccountService.delete_account(user_id=int(user_id))
    except ValueError as exc:
        _raise_reason(str(exc))

    _audit_admin_action(
        request,
        action="delete_account",
        target_user_id=int(user_id),
        extra={"cascade_count": int(result.get("cascade_count") or 0)},
    )
    return {"ok": True, **result}
