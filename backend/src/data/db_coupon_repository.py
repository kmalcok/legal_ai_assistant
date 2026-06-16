from __future__ import annotations

import secrets
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from ..db import core_db
from ..utils.credit_conversion import credit_to_usd, normalize_account_plan
from .db_account_repository import AccountRepository, DEFAULT_CHILD_LIMITS_BY_PLAN

COUPON_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
COUPON_CODE_LENGTH = 12


def _to_decimal(value: Any, *, default: str = "0.000000") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _normalize_coupon_code(code: Any) -> str:
    raw = str(code or "").strip().upper()
    return "".join(ch for ch in raw if ch.isalnum())


def _looks_like_generated_unique_code(code: Any) -> bool:
    normalized = _normalize_coupon_code(code)
    return len(normalized) == COUPON_CODE_LENGTH and all(ch in COUPON_CODE_ALPHABET for ch in normalized)


def _normalize_campaign_name(name: Any) -> str:
    return str(name or "").strip()


def _normalize_distribution_mode(mode: Any) -> str:
    value = str(mode or "").strip().lower() or "unique"
    return value if value in {"unique", "counter"} else ""


def _build_coupon_payload(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = row or {}
    coupon_id_raw = payload.get("coupon_id")
    used_by_raw = payload.get("used_by_id")
    code = str(payload.get("code") or "")
    max_redemptions = max(1, int(payload.get("max_redemptions") or 1))
    redemption_count = max(0, int(payload.get("redemption_count") or 0))
    is_campaign_code = max_redemptions > 1 or not _looks_like_generated_unique_code(code)
    return {
        "coupon_id": int(coupon_id_raw or 0),
        "code": code,
        "campaign_name": str(payload.get("campaign_name") or ""),
        "credit_amount": float(_to_decimal(payload.get("credit_amount"))),
        "distribution_mode": "counter" if is_campaign_code else "unique",
        "max_redemptions": max_redemptions,
        "redemption_count": redemption_count,
        "target_account_plan": payload.get("target_account_plan"),
        "created_by_label": payload.get("created_by_label"),
        "used_by_id": int(used_by_raw) if used_by_raw is not None else None,
        "used_by_username": payload.get("used_by_username"),
        "used_by_full_name": payload.get("used_by_full_name"),
        "used_at": payload.get("used_at"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "is_used": bool(redemption_count > 0),
        "is_exhausted": bool(redemption_count >= max_redemptions),
    }


class CouponRepository:
    @staticmethod
    def _ensure_coupon_code_available(*, cur: Any, code: str) -> None:
        normalized_code = _normalize_coupon_code(code)
        if not normalized_code or len(normalized_code) < 3 or len(normalized_code) > 64:
            raise ValueError("invalid_coupon_code")
        cur.execute(
            """
            SELECT coupon_id
            FROM coupons
            WHERE code=%s
            LIMIT 1
            """,
            (normalized_code,),
        )
        if cur.fetchone() is not None:
            raise ValueError("coupon_code_exists")

    @staticmethod
    def _has_user_redeemed_coupon(*, cur: Any, coupon_id: int, user_id: int, for_update: bool = False) -> bool:
        sql = """
            SELECT redemption_id
            FROM coupon_redemptions
            WHERE coupon_id=%s AND user_id=%s
            LIMIT 1
        """
        if for_update:
            sql += " FOR UPDATE"
        cur.execute(sql, (int(coupon_id), int(user_id)))
        return cur.fetchone() is not None

    @staticmethod
    def _validate_target_account_plan(target_account_plan: Any) -> str | None:
        if target_account_plan is None:
            return None
        normalized = normalize_account_plan(target_account_plan)
        if normalized not in DEFAULT_CHILD_LIMITS_BY_PLAN:
            raise ValueError("invalid_coupon_plan")
        return normalized

    @staticmethod
    def _generate_unique_codes(*, cur: Any, quantity: int) -> list[str]:
        codes: set[str] = set()
        while len(codes) < int(quantity):
            code = "".join(secrets.choice(COUPON_CODE_ALPHABET) for _ in range(COUPON_CODE_LENGTH))
            codes.add(code)

        placeholders = ", ".join(["%s"] * len(codes))
        cur.execute(
            f"SELECT code FROM coupons WHERE code IN ({placeholders})",
            tuple(codes),
        )
        existing = {
            str((row or {}).get("code") or "").strip().upper()
            for row in (cur.fetchall() or [])
            if isinstance(row, dict)
        }
        while existing:
            codes.difference_update(existing)
            while len(codes) < int(quantity):
                code = "".join(secrets.choice(COUPON_CODE_ALPHABET) for _ in range(COUPON_CODE_LENGTH))
                if code not in codes:
                    codes.add(code)
            placeholders = ", ".join(["%s"] * len(codes))
            cur.execute(
                f"SELECT code FROM coupons WHERE code IN ({placeholders})",
                tuple(codes),
            )
            existing = {
                str((row or {}).get("code") or "").strip().upper()
                for row in (cur.fetchall() or [])
                if isinstance(row, dict)
            }
        return sorted(codes)

    @staticmethod
    def create_coupons(
        *,
        quantity: int,
        campaign_name: str,
        credit_amount: Any,
        distribution_mode: str = "unique",
        campaign_code: Any = None,
        target_account_plan: Any = None,
        created_by_label: str | None = None,
    ) -> List[Dict[str, Any]]:
        qty = int(quantity or 0)
        if qty <= 0:
            raise ValueError("invalid_coupon_quantity")
        normalized_campaign_name = _normalize_campaign_name(campaign_name)
        if not normalized_campaign_name:
            raise ValueError("invalid_coupon_campaign_name")
        normalized_mode = _normalize_distribution_mode(distribution_mode)
        if not normalized_mode:
            raise ValueError("invalid_coupon_distribution_mode")

        normalized_plan = CouponRepository._validate_target_account_plan(target_account_plan)
        normalized_credit = max(Decimal("0.000000"), _to_decimal(credit_amount))

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            if normalized_mode == "counter":
                normalized_campaign_code = _normalize_coupon_code(campaign_code)
                CouponRepository._ensure_coupon_code_available(cur=cur, code=normalized_campaign_code)
                codes = [normalized_campaign_code]
                max_redemptions = qty
            else:
                codes = CouponRepository._generate_unique_codes(cur=cur, quantity=qty)
                max_redemptions = 1
            rows = [
                (
                    code,
                    normalized_campaign_name,
                    normalized_credit,
                    int(max_redemptions),
                    0,
                    normalized_plan,
                    str(created_by_label or "").strip() or None,
                )
                for code in codes
            ]
            cur.executemany(
                """
                INSERT INTO coupons (
                  code,
                  campaign_name,
                  credit_amount,
                  max_redemptions,
                  redemption_count,
                  target_account_plan,
                  created_by_label
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
            conn.commit()

        return CouponRepository.list_coupons_by_codes(codes=codes)

    @staticmethod
    def list_coupons(
        *,
        limit: int = 25,
        page: int = 1,
        campaign_name: str | None = None,
        used_status: str | None = None,
    ) -> Dict[str, Any]:
        safe_limit = max(1, min(int(limit or 200), 1000))
        safe_page = max(1, int(page or 1))
        offset = (safe_page - 1) * safe_limit
        filters: list[str] = []
        params: list[Any] = []
        normalized_campaign_name = _normalize_campaign_name(campaign_name)
        if normalized_campaign_name:
            filters.append("c.campaign_name=%s")
            params.append(normalized_campaign_name)
        normalized_used_status = str(used_status or "").strip().lower()
        if normalized_used_status == "used":
            filters.append("c.redemption_count > 0")
        elif normalized_used_status == "unused":
            filters.append("c.redemption_count = 0")
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
            cur.execute(
                f"""
                SELECT COUNT(*) AS total_count
                FROM coupons c
                {where_clause}
                """,
                tuple(params),
            )
            count_row = cur.fetchone() or {}
            cur.execute(
                f"""
                SELECT
                  c.coupon_id,
                  c.code,
                  c.campaign_name,
                  c.credit_amount,
                  c.max_redemptions,
                  c.redemption_count,
                  c.target_account_plan,
                  c.created_by_label,
                  c.used_by_id,
                  c.used_at,
                  c.created_at,
                  c.updated_at,
                  u.username AS used_by_username,
                  u.full_name AS used_by_full_name
                FROM coupons c
                LEFT JOIN users u ON u.user_id = c.used_by_id
                {where_clause}
                ORDER BY c.created_at DESC, c.coupon_id DESC
                LIMIT %s OFFSET %s
                """,
                tuple([*params, safe_limit, offset]),
            )
            rows = list(cur.fetchall() or [])
        total_count = int((count_row or {}).get("total_count") or 0)
        return {
            "items": [_build_coupon_payload(row) for row in rows],
            "total_count": total_count,
            "page": safe_page,
            "page_size": safe_limit,
        }

    @staticmethod
    def list_coupons_by_codes(*, codes: list[str]) -> List[Dict[str, Any]]:
        normalized_codes = [_normalize_coupon_code(code) for code in codes if _normalize_coupon_code(code)]
        if not normalized_codes:
            return []
        placeholders = ", ".join(["%s"] * len(normalized_codes))
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                f"""
                SELECT
                  c.coupon_id,
                  c.code,
                  c.campaign_name,
                  c.credit_amount,
                  c.max_redemptions,
                  c.redemption_count,
                  c.target_account_plan,
                  c.created_by_label,
                  c.used_by_id,
                  c.used_at,
                  c.created_at,
                  c.updated_at,
                  u.username AS used_by_username,
                  u.full_name AS used_by_full_name
                FROM coupons c
                LEFT JOIN users u ON u.user_id = c.used_by_id
                WHERE c.code IN ({placeholders})
                ORDER BY c.created_at DESC, c.coupon_id DESC
                """,
                tuple(normalized_codes),
            )
            rows = list(cur.fetchall() or [])
        return [_build_coupon_payload(row) for row in rows]

    @staticmethod
    def get_coupon_by_code(*, code: str) -> Optional[Dict[str, Any]]:
        normalized_code = _normalize_coupon_code(code)
        if not normalized_code:
            return None
        rows = CouponRepository.list_coupons_by_codes(codes=[normalized_code])
        return rows[0] if rows else None

    @staticmethod
    def delete_coupons(*, coupon_ids: list[int]) -> Dict[str, Any]:
        normalized_ids: list[int] = []
        for coupon_id in coupon_ids or []:
            try:
                parsed = int(coupon_id)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                normalized_ids.append(parsed)
        normalized_ids = sorted(set(normalized_ids))
        if not normalized_ids:
            raise ValueError("invalid_coupon_selection")
        placeholders = ", ".join(["%s"] * len(normalized_ids))
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                f"""
                SELECT coupon_id, code, campaign_name
                FROM coupons
                WHERE coupon_id IN ({placeholders})
                """,
                tuple(normalized_ids),
            )
            rows = list(cur.fetchall() or [])
            cur.execute(
                f"DELETE FROM coupons WHERE coupon_id IN ({placeholders})",
                tuple(normalized_ids),
            )
            deleted_count = int(cur.rowcount or 0)
            conn.commit()
        return {
            "deleted_count": deleted_count,
            "deleted_coupon_ids": [int((row or {}).get('coupon_id') or 0) for row in rows],
        }

    @staticmethod
    def get_redeem_preview(*, user_id: int, code: str) -> Dict[str, Any]:
        normalized_code = _normalize_coupon_code(code)
        if not normalized_code:
            raise ValueError("invalid_coupon_code")
        coupon = CouponRepository.get_coupon_by_code(code=normalized_code)
        if not coupon:
            raise ValueError("coupon_not_found")
        if coupon.get("is_exhausted"):
            raise ValueError("coupon_already_used")
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT account_plan
                FROM users
                WHERE user_id=%s
                LIMIT 1
                """,
                (int(user_id),),
            )
            user_row = cur.fetchone()
            already_redeemed = CouponRepository._has_user_redeemed_coupon(
                cur=cur,
                coupon_id=int(coupon["coupon_id"]),
                user_id=int(user_id),
            )
        if not user_row:
            raise ValueError("user_not_found")
        if already_redeemed:
            raise ValueError("coupon_already_redeemed_by_user")
        current_plan = normalize_account_plan(user_row.get("account_plan"))
        target_plan = CouponRepository._validate_target_account_plan(coupon.get("target_account_plan")) or current_plan
        return {
            "coupon": coupon,
            "current_account_plan": current_plan,
            "target_account_plan": target_plan,
            "requires_account_plan_change_confirmation": bool(target_plan != current_plan),
        }

    @staticmethod
    def redeem_coupon(*, user_id: int, code: str) -> Dict[str, Any]:
        normalized_code = _normalize_coupon_code(code)
        if not normalized_code:
            raise ValueError("invalid_coupon_code")

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT user_id, account_plan
                FROM users
                WHERE user_id=%s
                LIMIT 1
                FOR UPDATE
                """,
                (int(user_id),),
            )
            user_row = cur.fetchone()
            if not user_row:
                raise ValueError("user_not_found")

            cur.execute(
                """
                SELECT
                  coupon_id,
                  code,
                  campaign_name,
                  credit_amount,
                  max_redemptions,
                  redemption_count,
                  target_account_plan,
                  created_by_label,
                  used_by_id,
                  used_at,
                  created_at,
                  updated_at
                FROM coupons
                WHERE code=%s
                LIMIT 1
                FOR UPDATE
                """,
                (normalized_code,),
            )
            coupon_row = cur.fetchone()
            if not coupon_row:
                raise ValueError("coupon_not_found")
            max_redemptions = max(1, int(coupon_row.get("max_redemptions") or 1))
            redemption_count = max(0, int(coupon_row.get("redemption_count") or 0))
            if redemption_count >= max_redemptions:
                raise ValueError("coupon_already_used")
            if CouponRepository._has_user_redeemed_coupon(
                cur=cur,
                coupon_id=int(coupon_row["coupon_id"]),
                user_id=int(user_id),
                for_update=True,
            ):
                raise ValueError("coupon_already_redeemed_by_user")

            current_plan = normalize_account_plan(user_row.get("account_plan"))
            target_plan = CouponRepository._validate_target_account_plan(coupon_row.get("target_account_plan")) or current_plan
            credit_amount = max(Decimal("0.000000"), _to_decimal(coupon_row.get("credit_amount")))
            credit_amount_usd = (
                credit_to_usd(credit_amount, account_plan=target_plan)
                if credit_amount > Decimal("0.000000")
                else Decimal("0.000000")
            )

            AccountRepository._ensure_credit_rows(cur, user_ids=[int(user_id)])
            cur.execute(
                "SELECT balance_usd FROM user_credits WHERE user_id=%s LIMIT 1 FOR UPDATE",
                (int(user_id),),
            )
            credit_row = cur.fetchone() or {}
            previous_balance_usd = _to_decimal(credit_row.get("balance_usd"))
            next_balance_usd = previous_balance_usd + credit_amount_usd

            if credit_amount_usd > Decimal("0.000000"):
                reference_id = int(time.time_ns())
                type_id = AccountRepository._get_credit_type_id(
                    cur,
                    code="COUPON_REDEMPTION",
                    default_name="Coupon Redemption",
                )
                cur.execute(
                    "UPDATE user_credits SET balance_usd=%s WHERE user_id=%s",
                    (next_balance_usd, int(user_id)),
                )
                cur.execute(
                    """
                    INSERT INTO user_credits_transactions
                      (user_id, type_id, amount_usd, balance_after_usd, reference_type, reference_id, meta)
                    VALUES (
                      %s,
                      %s,
                      %s,
                      %s,
                      %s,
                      %s,
                      JSON_OBJECT(
                        'coupon_id', %s,
                        'coupon_code', %s,
                        'credit_amount', %s,
                        'target_account_plan', %s
                      )
                    )
                    """,
                    (
                        int(user_id),
                        int(type_id),
                        credit_amount_usd,
                        next_balance_usd,
                        "coupon_redemption",
                        int(reference_id),
                        int(coupon_row["coupon_id"]),
                        normalized_code,
                        credit_amount,
                        target_plan if coupon_row.get("target_account_plan") is not None else None,
                    ),
                )
            cur.execute(
                """
                INSERT INTO coupon_redemptions (coupon_id, user_id)
                VALUES (%s, %s)
                """,
                (int(coupon_row["coupon_id"]), int(user_id)),
            )

            if target_plan != current_plan:
                cur.execute(
                    "UPDATE users SET account_plan=%s WHERE user_id=%s",
                    (target_plan, int(user_id)),
                )

            cur.execute(
                """
                UPDATE coupons
                SET used_by_id=%s, used_at=UTC_TIMESTAMP(), redemption_count=redemption_count + 1
                WHERE coupon_id=%s
                """,
                (int(user_id), int(coupon_row["coupon_id"])),
            )
            conn.commit()

        refreshed_coupon = next(iter(CouponRepository.list_coupons_by_codes(codes=[normalized_code])), None)
        account = AccountRepository.get_user_account(int(user_id))
        return {
            "coupon": refreshed_coupon or _build_coupon_payload(coupon_row),
            "credit_amount": float(credit_amount),
            "credit_amount_usd": float(credit_amount_usd),
            "previous_account_plan": current_plan,
            "current_account_plan": target_plan,
            "account": account,
        }
