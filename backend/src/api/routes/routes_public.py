from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ...services.public_exchange_rate_service import PublicExchangeRateService
from ...services.public_stats_service import PublicStatsService


router = APIRouter(prefix="/public", tags=["public"])
_stats_service = PublicStatsService()
_exchange_rate_service = PublicExchangeRateService()


@router.get("/active-user-count", response_model=dict)
async def get_active_user_count() -> Dict[str, Any]:
    payload = await asyncio.to_thread(_stats_service.get_active_user_count_payload)
    return {"ok": True, **payload}


@router.get("/usd-try-rate", response_model=dict)
async def get_usd_try_rate() -> Dict[str, Any]:
    try:
        payload = await asyncio.to_thread(_exchange_rate_service.get_usd_try_rate_payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"usd_try_rate_unavailable: {exc}") from exc
    return {"ok": True, **payload}
