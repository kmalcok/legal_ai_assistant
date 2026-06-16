from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from ...services.coupon_service import CouponService
from ..errors import api_error, status_for_reason

router = APIRouter(prefix="/coupons", tags=["coupons"])


class RedeemCouponRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=64)
    confirm_account_plan_change: bool = False


def _raise_reason(reason: str) -> None:
    raise api_error(status_for_reason(reason), reason)


@router.post("/redeem", response_model=dict)
async def redeem_coupon(request: Request, payload: RedeemCouponRequest) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        preview = await asyncio.to_thread(
            CouponService.get_redeem_preview,
            user_id=int(user_id),
            code=payload.code,
        )
        if bool(preview.get("requires_account_plan_change_confirmation")) and not bool(payload.confirm_account_plan_change):
            raise api_error(
                status_for_reason("coupon_plan_change_confirmation_required"),
                "coupon_plan_change_confirmation_required",
                detail=preview,
            )
        result = await asyncio.to_thread(
            CouponService.redeem_coupon,
            user_id=int(user_id),
            code=payload.code,
        )
    except ValueError as exc:
        _raise_reason(str(exc))
    return {"ok": True, **result}
