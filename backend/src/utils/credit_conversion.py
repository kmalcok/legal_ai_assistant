from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from ..config import credit_config

DEFAULT_ACCOUNT_PLAN = "free"
STUDENT_ACCOUNT_PLAN = "student"


def normalize_account_plan(account_plan: Any) -> str:
    return str(account_plan or "").strip().lower() or DEFAULT_ACCOUNT_PLAN


def _to_decimal(value: Any, *, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def credit_rate_for_plan(account_plan: Any) -> Decimal:
    config = credit_config()
    plan = normalize_account_plan(account_plan)
    raw_rate = (
        config.student_exchange_rate
        if plan == STUDENT_ACCOUNT_PLAN
        else config.default_exchange_rate
    )
    rate = _to_decimal(raw_rate, default="1.0")
    return rate if rate > Decimal("0") else Decimal("1.0")


def usd_to_credit(value: Any, *, account_plan: Any = None) -> float:
    return float(_to_decimal(value) * credit_rate_for_plan(account_plan))


def credit_to_usd(value: Any, *, account_plan: Any = None) -> Decimal:
    rate = credit_rate_for_plan(account_plan)
    credit = _to_decimal(value)
    usd = credit / rate
    return max(Decimal("0.000000"), usd.quantize(Decimal("0.000001")))
