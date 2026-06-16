from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from ..data.db_account_repository import DEFAULT_CHILD_LIMITS_BY_PLAN
from ..data.db_coupon_repository import CouponRepository
from .account_service import AccountService


def _to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


class CouponService:
    @staticmethod
    def list_admin_coupons(
        *,
        limit: int = 25,
        page: int = 1,
        campaign_name: Optional[str] = None,
        used_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        return CouponRepository.list_coupons(
            limit=limit,
            page=page,
            campaign_name=campaign_name,
            used_status=used_status,
        )

    @staticmethod
    def create_admin_coupons(
        *,
        quantity: int,
        campaign_name: str,
        credit_amount: Any,
        distribution_mode: str = "unique",
        campaign_code: Optional[str] = None,
        target_account_plan: Optional[str] = None,
        created_by_label: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        qty = int(quantity or 0)
        if qty <= 0:
            raise ValueError("invalid_coupon_quantity")
        if not str(campaign_name or "").strip():
            raise ValueError("invalid_coupon_campaign_name")
        normalized_mode = str(distribution_mode or "").strip().lower() or "unique"
        if normalized_mode not in {"unique", "counter"}:
            raise ValueError("invalid_coupon_distribution_mode")

        normalized_plan = str(target_account_plan or "").strip().lower() or None
        if normalized_plan is not None and normalized_plan not in DEFAULT_CHILD_LIMITS_BY_PLAN:
            raise ValueError("invalid_coupon_plan")

        normalized_credit = max(Decimal("0.000000"), _to_decimal(credit_amount))
        if normalized_credit <= Decimal("0.000000") and normalized_plan is None:
            raise ValueError("invalid_coupon_payload")

        return CouponRepository.create_coupons(
            quantity=qty,
            campaign_name=campaign_name,
            credit_amount=normalized_credit,
            distribution_mode=normalized_mode,
            campaign_code=campaign_code,
            target_account_plan=normalized_plan,
            created_by_label=created_by_label,
        )

    @staticmethod
    def delete_admin_coupons(*, coupon_ids: list[int]) -> Dict[str, Any]:
        return CouponRepository.delete_coupons(coupon_ids=coupon_ids)

    @staticmethod
    def get_redeem_preview(*, user_id: int, code: str) -> Dict[str, Any]:
        return CouponRepository.get_redeem_preview(user_id=int(user_id), code=code)

    @staticmethod
    def redeem_coupon(*, user_id: int, code: str) -> Dict[str, Any]:
        result = CouponRepository.redeem_coupon(user_id=int(user_id), code=code)
        return {
            **result,
            "account": AccountService.build_user_profile(user_id=int(user_id)),
        }
