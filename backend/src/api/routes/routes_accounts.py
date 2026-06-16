from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...config import app_config
from ...data.db_user_repository import UserRepository
from ...security.passwords import hash_password
from ...services.account_service import AccountDeletionService, AccountService, UserDataWipeService
from ...services.mail_service import MailService
from ...utils.mail_verification import MailVerification
from ..errors import api_error, status_for_reason

router = APIRouter(prefix="/accounts", tags=["accounts"])


class CreateChildAccountRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(default="", max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    allocated_credit: float = Field(default=0.0, ge=0.0)


class SetChildCreditRequest(BaseModel):
    credit: float = Field(..., ge=0.0)


def _raise_reason(reason: str) -> None:
    raise api_error(status_for_reason(reason), reason)


@router.get("/children", response_model=dict)
async def list_children(request: Request) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        profile = await asyncio.to_thread(AccountService.build_user_profile, user_id=user_id)
    except ValueError as exc:
        _raise_reason(str(exc))
    if not bool(((profile.get("permissions") or {}).get("can_manage_children"))):
        _raise_reason("parent_required")
    managed = profile.get("managed_children") or {}
    return {"ok": True, "children": managed.get("items") or [], "count": int(managed.get("count") or 0), "limit": int(managed.get("limit") or 0)}


@router.post("/children", response_model=dict)
async def create_child_account(request: Request, payload: CreateChildAccountRequest) -> Dict[str, Any]:
    parent_user_id = int(getattr(request.state, "user_id"))
    username = (payload.username or "").strip()
    email = (payload.email or "").strip()
    full_name = (payload.full_name or "").strip()

    if len(username) < 3 or "@" in username:
        _raise_reason("invalid_username")
    if "@" not in email:
        _raise_reason("invalid_email")
    if await asyncio.to_thread(UserRepository.is_username_taken, username=username):
        _raise_reason("username_taken")
    if await asyncio.to_thread(UserRepository.is_email_taken, email=email):
        _raise_reason("email_taken")

    try:
        verifier = MailVerification(enabled=app_config().sub_account_mail_verification)
        if not await asyncio.to_thread(verifier.verify_deliverable, email):
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "email_not_deliverable"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "reason": "mail_verification_error", "detail": str(exc)},
        )

    password_hash = await asyncio.to_thread(hash_password, payload.password)
    try:
        child = await asyncio.to_thread(
            AccountService.create_child_account,
            parent_user_id=parent_user_id,
            username=username,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            allocated_credit=float(payload.allocated_credit or 0.0),
        )
    except ValueError as exc:
        _raise_reason(str(exc))

    parent = await asyncio.to_thread(UserRepository.get_by_user_id, parent_user_id)
    parent_name = (
        str((parent or {}).get("full_name") or "").strip()
        or str((parent or {}).get("username") or "").strip()
        or "Üst hesap"
    )
    try:
        await MailService.send_child_account_created_email(
            to_email=email,
            to_name=full_name or username,
            parent_name=parent_name,
            username=username,
            password=payload.password,
            credit=float((child or {}).get("credit") or 0.0),
        )
    except Exception as exc:
        try:
            await AccountDeletionService.delete_account(
                actor_user_id=int(parent_user_id),
                target_user_id=int((child or {}).get("user_id") or 0),
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "reason": "child_account_email_failed", "detail": str(exc)},
        )

    return {"ok": True, "child": child}


@router.patch("/children/{child_user_id}/credit", response_model=dict)
async def set_child_credit(request: Request, child_user_id: int, payload: SetChildCreditRequest) -> Dict[str, Any]:
    parent_user_id = int(getattr(request.state, "user_id"))
    try:
        result = await asyncio.to_thread(
            AccountService.set_child_credit,
            parent_user_id=parent_user_id,
            child_user_id=int(child_user_id),
            desired_credit=float(payload.credit),
        )
    except ValueError as exc:
        _raise_reason(str(exc))
    return {"ok": True, **result}


@router.delete("/children/{child_user_id}", response_model=dict)
async def delete_child_account(request: Request, child_user_id: int) -> Dict[str, Any]:
    parent_user_id = int(getattr(request.state, "user_id"))
    try:
        result = await AccountDeletionService.delete_account(
            actor_user_id=int(parent_user_id),
            target_user_id=int(child_user_id),
        )
    except ValueError as exc:
        _raise_reason(str(exc))
    return {"ok": True, **result}


@router.post("/me/wipe-data", response_model=dict)
async def wipe_my_data(request: Request) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        deleted = await UserDataWipeService.wipe_user_data(user_id=int(user_id))
    except ValueError as exc:
        _raise_reason(str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise api_error(500, "internal_error", detail=str(exc))
    return {"ok": True, "deleted": deleted}


@router.delete("/me", response_model=dict)
async def delete_my_account(request: Request) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        result = await AccountDeletionService.delete_account(
            actor_user_id=int(user_id),
            target_user_id=int(user_id),
        )
    except ValueError as exc:
        _raise_reason(str(exc))
    return {"ok": True, **result}
