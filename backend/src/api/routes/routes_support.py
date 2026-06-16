from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ...data.db_support_mail_repository import SupportMailRepository
from ...data.db_user_repository import UserRepository
from ...services.mail_service import MailService
from ..client_ip import resolve_client_ip
from ..errors import api_error


router = APIRouter(prefix="/support", tags=["support"])


class SupportMailRequest(BaseModel):
    message: str


@router.post("/mail", response_model=dict)
async def send_support_mail(request: Request, payload: SupportMailRequest) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    message = (payload.message or "").strip()
    if not message:
        raise api_error(400, "empty_message")
    if len(message) > 4000:
        raise api_error(400, "message_too_long")

    user = await asyncio.to_thread(UserRepository.get_by_user_id, user_id)
    if not user:
        raise api_error(404, "user_not_found")

    username = (user.get("username") or "").strip()
    email = (user.get("email") or "").strip()
    client_ip = resolve_client_ip(request)
    user_agent = (request.headers.get("user-agent") or "").strip()
    requested_at = datetime.now(timezone.utc).isoformat()

    support_mail_id = await asyncio.to_thread(
        SupportMailRepository.create,
        user_id=user_id,
        username=username,
        email=email,
        message=message,
        request_ip=client_ip,
        user_agent=user_agent,
    )

    subject = f"[Yargucu Support] user_id={user_id} username={username or '-'}"
    body = (
        f"requested_at_utc: {requested_at}\n"
        f"user_id: {user_id}\n"
        f"username: {username}\n"
        f"email: {email}\n"
        f"ip: {client_ip}\n"
        f"user_agent: {user_agent}\n"
        f"support_mail_id: {support_mail_id}\n\n"
        "message:\n"
        f"{message}\n"
    )

    try:
        await MailService.send_support_email(subject=subject, body=body)
        await asyncio.to_thread(SupportMailRepository.mark_sent, support_mail_id=support_mail_id)
    except Exception as exc:
        await asyncio.to_thread(
            SupportMailRepository.mark_send_failed,
            support_mail_id=support_mail_id,
            error=str(exc),
        )
        raise api_error(500, "support_mail_send_failed")

    return {"ok": True, "support_mail_id": support_mail_id}
