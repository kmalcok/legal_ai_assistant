from __future__ import annotations

import asyncio

from fastapi import HTTPException

from .errors import api_error
from ..data.db_user_repository import UserRepository


async def ensure_sufficient_credits(user_id: int) -> None:
    try:
        snap = await asyncio.to_thread(UserRepository.get_credit_snapshot, user_id=int(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if float(snap.get("credit") or 0.0) <= 0.0:
        raise api_error(
            402,
            "insufficient_credits",
            detail={
                "credit": float(snap.get("credit") or 0.0),
            },
        )
