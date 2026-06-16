from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from ..db import core_db
from ..utils.credit_conversion import normalize_account_plan, usd_to_credit
from .db_account_repository import AccountRepository
from .db_user_app_config_repository import UserAppConfigRepository


class UserRepository:
    @staticmethod
    def _account_plan_for_user(*, user_id: int) -> str:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT account_plan
                FROM users
                WHERE user_id=%s
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cur.fetchone()
        if not row:
            raise ValueError("user_not_found")
        if isinstance(row, dict):
            return normalize_account_plan(row.get("account_plan"))
        return normalize_account_plan(row[0] if row else None)

    @staticmethod
    def get_credit_snapshot(*, user_id: int) -> Dict[str, float]:
        """
        Return the current user credit snapshot.
        Missing `user_credits` rows are treated as zero balance.
        This method intentionally exposes only credit-facing fields.
        """
        row = UserRepository.get_by_user_id_with_credit(int(user_id))
        if not row:
            raise ValueError("user_not_found")

        try:
            credit = float(Decimal(str(row.get("credit", 0) or 0)))
        except (InvalidOperation, ValueError, TypeError):
            credit = 0.0

        return {
            "credit": float(credit),
        }

    @staticmethod
    def get_credit_usage_summary(*, user_id: int, lookback_days: int = 14) -> Dict[str, Any]:
        lookback = max(1, int(lookback_days))
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT
                  COUNT(*) AS usage_tx_count,
                  COALESCE(SUM(CASE WHEN amount_usd < 0 THEN -amount_usd ELSE 0 END), 0.000000) AS spent_usd,
                  MIN(created_at) AS first_usage_at,
                  MAX(created_at) AS last_usage_at,
                  COUNT(DISTINCT DATE(created_at)) AS active_days
                FROM user_credits_transactions
                WHERE user_id=%s
                  AND reference_type='user_usage'
                  AND created_at >= (UTC_TIMESTAMP() - INTERVAL %s DAY)
                """,
                (int(user_id), int(lookback)),
            )
            row = cur.fetchone() or {}

        spent_usd = float(Decimal(str(row.get("spent_usd") or 0)))
        active_days = int(row.get("active_days") or 0)
        usage_tx_count = int(row.get("usage_tx_count") or 0)
        first_usage_at = row.get("first_usage_at")
        last_usage_at = row.get("last_usage_at")

        window_days = lookback
        if first_usage_at and last_usage_at:
            try:
                delta_days = int((last_usage_at.date() - first_usage_at.date()).days) + 1
                window_days = max(1, min(lookback, delta_days))
            except Exception:
                window_days = lookback

        daily_average_usd = spent_usd / float(window_days or 1)
        account_plan = UserRepository._account_plan_for_user(user_id=int(user_id))
        spent_credit = usd_to_credit(spent_usd, account_plan=account_plan)
        daily_average_credit = usd_to_credit(daily_average_usd, account_plan=account_plan)

        return {
            "lookback_days": int(lookback),
            "window_days": int(window_days),
            "active_days": int(active_days),
            "usage_tx_count": int(usage_tx_count),
            "spent_credit": float(spent_credit),
            "daily_average_credit": float(daily_average_credit),
            "has_enough_data": bool(usage_tx_count > 0 and spent_usd > 0),
        }

    @staticmethod
    def has_available_credit(*, user_id: int) -> bool:
        snap = UserRepository.get_credit_snapshot(user_id=int(user_id))
        return float(snap.get("credit") or 0.0) > 0.0

    @staticmethod
    def is_username_taken(*, username: str, exclude_user_id: Optional[int] = None) -> bool:
        username = (username or "").strip()
        if not username:
            return False
        with core_db() as conn:
            cur = conn.cursor()
            if exclude_user_id is None:
                cur.execute(
                    """
                    SELECT 1
                    FROM users
                    WHERE username=%s OR email=%s
                    LIMIT 1
                    """,
                    (username, username),
                )
            else:
                cur.execute(
                    """
                    SELECT 1
                    FROM users
                    WHERE (username=%s OR email=%s) AND user_id<>%s
                    LIMIT 1
                    """,
                    (username, username, int(exclude_user_id)),
                )
            return cur.fetchone() is not None

    @staticmethod
    def is_email_taken(*, email: str, exclude_user_id: Optional[int] = None) -> bool:
        email = (email or "").strip()
        if not email:
            return False
        with core_db() as conn:
            cur = conn.cursor()
            if exclude_user_id is None:
                cur.execute("SELECT 1 FROM users WHERE email=%s LIMIT 1", (email,))
            else:
                cur.execute(
                    "SELECT 1 FROM users WHERE email=%s AND user_id<>%s LIMIT 1",
                    (email, int(exclude_user_id)),
                )
            return cur.fetchone() is not None

    @staticmethod
    def get_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT user_id, username, email, full_name, created_at
                FROM users
                WHERE user_id=%s
                LIMIT 1
                """,
                (int(user_id),),
            )
            return cur.fetchone()

    @staticmethod
    def get_by_user_id_with_credit(user_id: int) -> Optional[Dict[str, Any]]:
        """
        Returns user profile plus the app-facing credit balance.
        USD storage details stay inside the repository layer.
        """
        account = AccountRepository.get_user_account(int(user_id))
        if not account:
            return None

        credit_summary = account.get("credit_summary") or {}
        managed_children = account.get("managed_children") or {}
        account_plan = account.get("account_plan")
        return {
            "user_id": int(account["user_id"]),
            "username": account.get("username"),
            "email": account.get("email"),
            "full_name": account.get("full_name"),
            "created_at": account.get("created_at"),
            "account_type": account.get("account_type"),
            "account_plan": account_plan,
            "parent_user_id": account.get("parent_user_id"),
            "child_account_limit_override": account.get("child_account_limit_override"),
            "credit": usd_to_credit(credit_summary.get("available_credit"), account_plan=account_plan),
            "credit_summary": {
                "available_credit": usd_to_credit(credit_summary.get("available_credit"), account_plan=account_plan),
                "reserved_credit": usd_to_credit(credit_summary.get("reserved_credit"), account_plan=account_plan),
                "total_credit": usd_to_credit(credit_summary.get("total_credit"), account_plan=account_plan),
            },
            "managed_children": {
                "count": int(managed_children.get("count") or 0),
                "limit": int(managed_children.get("limit") or 0),
                "items": [
                    {
                        **item,
                        "credit": usd_to_credit(item.get("credit"), account_plan=item.get("account_plan")),
                        "allocated_credit": usd_to_credit(item.get("allocated_credit"), account_plan=item.get("account_plan")),
                    }
                    for item in (managed_children.get("items") or [])
                    if isinstance(item, dict)
                ],
            },
            "permissions": {
                "can_manage_children": str(account.get("account_type") or "") == "parent",
                "can_delete_account": str(account.get("account_type") or "") != "child",
                "can_wipe_data": True,
            },
        }

    @staticmethod
    def get_by_user_id_with_hash(user_id: int) -> Optional[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT user_id, username, email, full_name, password_hash, created_at
                FROM users
                WHERE user_id=%s
                LIMIT 1
                """,
                (int(user_id),),
            )
            return cur.fetchone()

    @staticmethod
    def get_by_username_or_email(identifier: str) -> Optional[Dict[str, Any]]:
        ident = (identifier or "").strip()
        if not ident:
            return None
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            if "@" in ident:
                cur.execute(
                    """
                    SELECT user_id, username, email, full_name, password_hash, created_at
                    FROM users
                    WHERE email=%s
                    LIMIT 1
                    """,
                    (ident,),
                )
            else:
                cur.execute(
                    """
                    SELECT user_id, username, email, full_name, password_hash, created_at
                    FROM users
                    WHERE username=%s
                    LIMIT 1
                    """,
                    (ident,),
                )
            return cur.fetchone()

    @staticmethod
    def create_user(
        *,
        username: str,
        email: str,
        full_name: str,
        password_hash: str,
        phone: str | None = None,
        account_plan: str = "free",
    ) -> int:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (username, email, full_name, phone, password_hash, account_plan)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (username, email, full_name, phone, password_hash, account_plan),
            )
            user_id = int(cur.lastrowid)
            defaults = UserAppConfigRepository.default_values()
            cur.execute(
                """
                INSERT INTO user_app_config (
                    user_id,
                    main_agent_verbosity,
                    main_agent_reasoning_effort,
                    ictihat_agent_reasoning_effort,
                    extra_instructions
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    defaults.get("main_agent_verbosity"),
                    defaults.get("main_agent_reasoning_effort"),
                    defaults.get("ictihat_agent_reasoning_effort"),
                    defaults.get("extra_instructions"),
                ),
            )
            cur.execute(
                """
                INSERT IGNORE INTO auth_user_state (user_id, token_version)
                VALUES (%s, 1)
                """,
                (user_id,),
            )
            conn.commit()
            return user_id

    @staticmethod
    def delete_user(*, user_id: int) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM users WHERE user_id=%s", (int(user_id),))
            conn.commit()

    @staticmethod
    def update_password_hash(*, user_id: int, password_hash: str) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE user_id=%s",
                (password_hash, int(user_id)),
            )
            conn.commit()

    @staticmethod
    def update_profile(
        *,
        user_id: int,
        username: Optional[str] = None,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> None:
        fields = []
        params = []

        if username is not None:
            fields.append("username=%s")
            params.append((username or "").strip())
        if email is not None:
            fields.append("email=%s")
            params.append((email or "").strip())
        if full_name is not None:
            fields.append("full_name=%s")
            params.append((full_name or "").strip())

        if not fields:
            return

        sql = "UPDATE users SET " + ", ".join(fields) + " WHERE user_id=%s"
        params.append(int(user_id))
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            conn.commit()

