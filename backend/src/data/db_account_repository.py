from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from ..db import core_db
from .db_app_config_repository import AppConfigRepository
from .db_user_app_config_repository import UserAppConfigRepository

ACCOUNT_TYPE_STANDALONE = "standalone"
ACCOUNT_TYPE_PARENT = "parent"
ACCOUNT_TYPE_CHILD = "child"

ACCOUNT_PLAN_FREE = "free"
ACCOUNT_PLAN_STUDENT = "student"
ACCOUNT_PLAN_STARTER = "starter"
ACCOUNT_PLAN_STANDARD = "standard"
ACCOUNT_PLAN_ADVANCED = "advanced"
ACCOUNT_PLAN_PROFESSIONAL = "professional"
ACCOUNT_PLAN_ENTERPRISE = "enterprise"

DEFAULT_CHILD_LIMITS_BY_PLAN = {
    ACCOUNT_PLAN_FREE: 3,
    ACCOUNT_PLAN_STUDENT: 3,
    ACCOUNT_PLAN_STARTER: 3,
    ACCOUNT_PLAN_STANDARD: 3,
    ACCOUNT_PLAN_ADVANCED: 3,
    ACCOUNT_PLAN_PROFESSIONAL: 5,
    ACCOUNT_PLAN_ENTERPRISE: 10,
}


def _to_decimal(value: Any, *, default: str = "0.000000") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _to_float(value: Any) -> float:
    try:
        return float(_to_decimal(value))
    except Exception:
        return 0.0


class AccountRepository:
    @staticmethod
    def _ensure_credit_rows(cur: Any, *, user_ids: list[int]) -> None:
        rows = [(int(user_id), Decimal("0.000000")) for user_id in user_ids if int(user_id) > 0]
        if not rows:
            return
        cur.executemany(
            """
            INSERT IGNORE INTO user_credits (user_id, balance_usd)
            VALUES (%s, %s)
            """,
            rows,
        )

    @staticmethod
    def _get_credit_type_id(cur: Any, *, code: str, default_name: str) -> int:
        cur.execute(
            """
            SELECT type_id
            FROM credit_transaction_types
            WHERE code=%s
            LIMIT 1
            """,
            (str(code),),
        )
        row = cur.fetchone()
        if row:
            if isinstance(row, dict):
                return int(row.get("type_id") or 0)
            return int(row[0])
        cur.execute("SELECT COALESCE(MAX(type_id), 0) FROM credit_transaction_types")
        max_row = cur.fetchone()
        if isinstance(max_row, dict):
            next_id = int((next(iter(max_row.values()), 0) or 0)) + 1 if max_row else 1
        else:
            next_id = int((max_row[0] or 0)) + 1 if max_row else 1
        cur.execute(
            """
            INSERT INTO credit_transaction_types (type_id, code, name)
            VALUES (%s, %s, %s)
            """,
            (int(next_id), str(code), str(default_name)),
        )
        return int(next_id)

    @staticmethod
    def _list_children_rows(*, parent_user_id: int) -> List[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT
                  u.user_id,
                  u.username,
                  u.email,
                  u.full_name,
                  u.account_type,
                  u.account_plan,
                  u.parent_user_id,
                  parent.username AS parent_username,
                  u.created_at,
                  COALESCE(uc.balance_usd, 0.000000) AS balance_usd,
                  COALESCE(cca.allocated_balance_usd, 0.000000) AS allocated_balance_usd
                FROM users u
                LEFT JOIN users parent ON parent.user_id = u.parent_user_id
                LEFT JOIN user_credits uc ON uc.user_id = u.user_id
                LEFT JOIN child_credit_allocations cca
                  ON cca.child_user_id = u.user_id AND cca.parent_user_id = %s
                WHERE u.parent_user_id = %s AND u.account_type = 'child'
                ORDER BY u.created_at ASC, u.user_id ASC
                """,
                (int(parent_user_id), int(parent_user_id)),
            )
            return list(cur.fetchall() or [])

    @staticmethod
    def get_plan_child_limit(*, account_plan: Optional[str], override_limit: Any = None) -> int:
        override_value = _to_decimal(override_limit, default="-1")
        if override_value >= Decimal("0"):
            return max(0, int(override_value))

        plan_code = str(account_plan or "").strip().lower() or ACCOUNT_PLAN_FREE
        fallback_limit = int(DEFAULT_CHILD_LIMITS_BY_PLAN.get(plan_code, DEFAULT_CHILD_LIMITS_BY_PLAN[ACCOUNT_PLAN_FREE]))
        row = AppConfigRepository.get_by_key(key=f"account_plan_{plan_code}_child_limit") or {}
        config_limit = _to_decimal(row.get("value_decimal"), default=str(fallback_limit))
        return max(0, int(config_limit))

    @staticmethod
    def list_admin_accounts(*, account_types: Optional[List[str]] = None, query: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        normalized_types = [
            str(item or "").strip().lower()
            for item in (account_types or [ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT, ACCOUNT_TYPE_CHILD])
            if str(item or "").strip().lower() in {ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT, ACCOUNT_TYPE_CHILD}
        ]
        if not normalized_types:
            normalized_types = [ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT, ACCOUNT_TYPE_CHILD]

        lookup = str(query or "").strip()
        sql = [
            """
            SELECT u.user_id
            FROM users u
            WHERE u.account_type IN ({placeholders})
            """.format(placeholders=", ".join(["%s"] * len(normalized_types)))
        ]
        params: List[Any] = list(normalized_types)

        if lookup:
            like = f"%{lookup}%"
            sql.append(
                """
                AND (
                  u.username LIKE %s
                  OR u.email LIKE %s
                  OR COALESCE(u.full_name, '') LIKE %s
                )
                """
            )
            params.extend([like, like, like])

        sql.append("ORDER BY u.created_at DESC, u.user_id DESC LIMIT %s")
        params.append(max(1, min(int(limit or 200), 500)))

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute("\n".join(sql), tuple(params))
            rows = list(cur.fetchall() or [])

        accounts: List[Dict[str, Any]] = []
        for row in rows:
            user_id = int((row or {}).get("user_id") or 0)
            if user_id <= 0:
                continue
            account = AccountRepository.get_user_account(user_id)
            if account:
                accounts.append(account)
        return accounts

    @staticmethod
    def create_admin_account(
        *,
        username: str,
        email: str,
        full_name: str,
        password_hash: str,
        account_type: str,
        account_plan: str,
    ) -> int:
        normalized_type = str(account_type or "").strip().lower()
        normalized_plan = str(account_plan or "").strip().lower()
        if normalized_type not in {ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT}:
            raise ValueError("invalid_account_type")
        if normalized_plan not in DEFAULT_CHILD_LIMITS_BY_PLAN:
            raise ValueError("invalid_account_plan")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (
                    username,
                    email,
                    full_name,
                    password_hash,
                    account_type,
                    account_plan,
                    parent_user_id,
                    child_account_limit_override
                )
                VALUES (%s, %s, %s, %s, %s, %s, NULL, NULL)
                """,
                (
                    (username or "").strip(),
                    (email or "").strip(),
                    (full_name or "").strip(),
                    password_hash,
                    normalized_type,
                    normalized_plan,
                ),
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
            AccountRepository._ensure_credit_rows(cur, user_ids=[user_id])
            conn.commit()
            return user_id

    @staticmethod
    def admin_count_managed_children(*, parent_user_id: int) -> int:
        return len(AccountRepository._list_children_rows(parent_user_id=int(parent_user_id)))

    @staticmethod
    def admin_apply_user_account_update(
        *,
        user_id: int,
        account_type: str,
        account_plan: str,
        clear_parent_user_id: bool,
    ) -> None:
        normalized_type = str(account_type or "").strip().lower()
        normalized_plan = str(account_plan or "").strip().lower()
        if normalized_type not in {ACCOUNT_TYPE_STANDALONE, ACCOUNT_TYPE_PARENT, ACCOUNT_TYPE_CHILD}:
            raise ValueError("invalid_account_type")
        if normalized_plan not in DEFAULT_CHILD_LIMITS_BY_PLAN:
            raise ValueError("invalid_account_plan")

        with core_db() as conn:
            cur = conn.cursor()
            if clear_parent_user_id:
                cur.execute(
                    """
                    UPDATE users
                    SET account_type=%s, account_plan=%s, parent_user_id=NULL
                    WHERE user_id=%s
                    """,
                    (normalized_type, normalized_plan, int(user_id)),
                )
            else:
                cur.execute(
                    """
                    UPDATE users
                    SET account_type=%s, account_plan=%s
                    WHERE user_id=%s
                    """,
                    (normalized_type, normalized_plan, int(user_id)),
                )
            if cur.rowcount == 0:
                cur.execute(
                    """
                    SELECT 1
                    FROM users
                    WHERE user_id=%s
                    LIMIT 1
                    """,
                    (int(user_id),),
                )
                if cur.fetchone() is None:
                    raise ValueError("user_not_found")
            conn.commit()

    @staticmethod
    def get_user_account(user_id: int) -> Optional[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute(
                    """
                    SELECT
                      u.user_id,
                      u.username,
                      u.email,
                      u.full_name,
                      u.phone,
                      u.created_at,
                      u.account_type,
                      u.account_plan,
                      u.parent_user_id,
                      parent.username AS parent_username,
                      u.child_account_limit_override,
                      COALESCE(uc.balance_usd, 0.000000) AS balance_usd
                    FROM users u
                    LEFT JOIN users parent ON parent.user_id = u.parent_user_id
                    LEFT JOIN user_credits uc ON uc.user_id = u.user_id
                    WHERE u.user_id=%s
                    LIMIT 1
                    """,
                    (int(user_id),),
                )
                row = cur.fetchone()
            except Exception:
                return None
        if not row:
            return None

        account_type = str(row.get("account_type") or ACCOUNT_TYPE_STANDALONE).strip() or ACCOUNT_TYPE_STANDALONE
        account_plan = str(row.get("account_plan") or ACCOUNT_PLAN_FREE).strip().lower() or ACCOUNT_PLAN_FREE
        available_usd = _to_decimal(row.get("balance_usd"))
        children = AccountRepository._list_children_rows(parent_user_id=int(user_id)) if account_type == ACCOUNT_TYPE_PARENT else []
        reserved_usd = sum((_to_decimal(child.get("balance_usd")) for child in children), Decimal("0.000000"))
        total_usd = available_usd + reserved_usd
        child_limit = AccountRepository.get_plan_child_limit(
            account_plan=account_plan,
            override_limit=row.get("child_account_limit_override"),
        )

        managed_children = [
            {
                "user_id": int(child["user_id"]),
                "username": child.get("username"),
                "email": child.get("email"),
                "full_name": child.get("full_name"),
                "account_type": child.get("account_type") or ACCOUNT_TYPE_CHILD,
                "account_plan": child.get("account_plan") or account_plan,
                "credit": _to_float(child.get("balance_usd")),
                "allocated_credit": _to_float(child.get("allocated_balance_usd")),
                "created_at": child.get("created_at"),
            }
            for child in children
        ]

        return {
            "user_id": int(row["user_id"]),
            "username": row.get("username"),
            "email": row.get("email"),
            "full_name": row.get("full_name"),
            "phone": row.get("phone"),
            "created_at": row.get("created_at"),
            "account_type": account_type,
            "account_plan": account_plan,
            "parent_user_id": int(row["parent_user_id"]) if row.get("parent_user_id") is not None else None,
            "parent_username": row.get("parent_username"),
            "child_account_limit_override": int(row["child_account_limit_override"]) if row.get("child_account_limit_override") is not None else None,
            "balance_usd": _to_float(available_usd),
            "credit_summary": {
                "available_credit": _to_float(available_usd),
                "reserved_credit": _to_float(reserved_usd),
                "total_credit": _to_float(total_usd),
            },
            "managed_children": {
                "count": len(managed_children),
                "limit": int(child_limit),
                "items": managed_children,
            },
        }

    @staticmethod
    def get_child_account(*, parent_user_id: int, child_user_id: int) -> Optional[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT
                  u.user_id,
                  u.username,
                  u.email,
                  u.full_name,
                  u.account_type,
                  u.account_plan,
                  u.parent_user_id,
                  parent.username AS parent_username,
                  u.created_at,
                  COALESCE(uc.balance_usd, 0.000000) AS balance_usd,
                  COALESCE(cca.allocated_balance_usd, 0.000000) AS allocated_balance_usd
                FROM users u
                LEFT JOIN users parent ON parent.user_id = u.parent_user_id
                LEFT JOIN user_credits uc ON uc.user_id = u.user_id
                LEFT JOIN child_credit_allocations cca
                  ON cca.child_user_id = u.user_id AND cca.parent_user_id = %s
                WHERE u.user_id=%s AND u.parent_user_id=%s AND u.account_type='child'
                LIMIT 1
                """,
                (int(parent_user_id), int(child_user_id), int(parent_user_id)),
            )
            row = cur.fetchone()
        if not row:
            return None
        row["user_id"] = int(row["user_id"])
        row["parent_user_id"] = int(row["parent_user_id"])
        row["account_plan"] = str(row.get("account_plan") or ACCOUNT_PLAN_FREE).strip().lower() or ACCOUNT_PLAN_FREE
        row["balance_usd"] = _to_float(row.get("balance_usd"))
        row["allocated_balance_usd"] = _to_float(row.get("allocated_balance_usd"))
        return row

    @staticmethod
    def list_children(*, parent_user_id: int) -> List[Dict[str, Any]]:
        parent = AccountRepository.get_user_account(int(parent_user_id))
        if not parent or str(parent.get("account_type")) != ACCOUNT_TYPE_PARENT:
            return []
        return list((parent.get("managed_children") or {}).get("items") or [])

    @staticmethod
    def create_child_account(
        *,
        parent_user_id: int,
        username: str,
        email: str,
        full_name: str,
        password_hash: str,
        allocated_credit_usd: Decimal | None = None,
    ) -> int:
        parent = AccountRepository.get_user_account(int(parent_user_id))
        if not parent:
            raise ValueError("user_not_found")
        if str(parent.get("account_type")) != ACCOUNT_TYPE_PARENT:
            raise ValueError("parent_required")
        limit = int((parent.get("managed_children") or {}).get("limit") or 0)
        current_count = int((parent.get("managed_children") or {}).get("count") or 0)
        if limit > 0 and current_count >= limit:
            raise ValueError("child_limit_reached")
        desired_allocation = _to_decimal(allocated_credit_usd)
        parent_available = _to_decimal((parent.get("credit_summary") or {}).get("available_credit"))
        if desired_allocation > parent_available:
            raise ValueError("insufficient_parent_credits")
        parent_plan = str(parent.get("account_plan") or ACCOUNT_PLAN_FREE).strip().lower() or ACCOUNT_PLAN_FREE

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (username, email, full_name, password_hash, account_type, account_plan, parent_user_id)
                VALUES (%s, %s, %s, %s, 'child', %s, %s)
                """,
                (
                    (username or "").strip(),
                    (email or "").strip(),
                    (full_name or "").strip(),
                    password_hash,
                    parent_plan,
                    int(parent_user_id),
                ),
            )
            child_user_id = int(cur.lastrowid)
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
                    int(child_user_id),
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
                (int(child_user_id),),
            )
            AccountRepository._ensure_credit_rows(cur, user_ids=[int(parent_user_id), int(child_user_id)])
            cur.execute(
                """
                INSERT IGNORE INTO child_credit_allocations (parent_user_id, child_user_id, allocated_balance_usd)
                VALUES (%s, %s, 0.000000)
                """,
                (int(parent_user_id), int(child_user_id)),
            )

            # Child accounts should start with parent-managed credit only.
            # If a welcome-credit trigger created balance on insert, reverse it here.
            cur.execute(
                "SELECT balance_usd FROM user_credits WHERE user_id=%s LIMIT 1 FOR UPDATE",
                (int(child_user_id),),
            )
            child_credit_row = cur.fetchone()
            existing_child_balance = (
                _to_decimal(child_credit_row.get("balance_usd"))
                if isinstance(child_credit_row, dict)
                else _to_decimal(child_credit_row[0] if child_credit_row else None)
            )
            if existing_child_balance > Decimal("0.000000"):
                adjust_type_id = AccountRepository._get_credit_type_id(
                    cur,
                    code="adjust",
                    default_name="Manual Adjustment",
                )
                cur.execute(
                    "UPDATE user_credits SET balance_usd=0.000000 WHERE user_id=%s",
                    (int(child_user_id),),
                )
                cur.execute(
                    """
                    INSERT INTO user_credits_transactions
                      (user_id, type_id, amount_usd, balance_after_usd, reference_type, reference_id, meta)
                    VALUES (%s, %s, %s, %s, %s, %s, JSON_OBJECT('source', 'child_welcome_reversal'))
                    """,
                    (
                        int(child_user_id),
                        int(adjust_type_id),
                        -existing_child_balance,
                        Decimal("0.000000"),
                        "child_welcome_reversal",
                        int(child_user_id),
                    ),
                )
            conn.commit()

        if allocated_credit_usd is not None and desired_allocation > Decimal("0.000000"):
            try:
                AccountRepository.set_child_credit_balance(
                    parent_user_id=int(parent_user_id),
                    child_user_id=int(child_user_id),
                    desired_balance_usd=desired_allocation,
                )
            except Exception:
                with core_db() as cleanup_conn:
                    cleanup_cur = cleanup_conn.cursor()
                    cleanup_cur.execute("DELETE FROM users WHERE user_id=%s", (int(child_user_id),))
                    cleanup_conn.commit()
                raise
        return int(child_user_id)

    @staticmethod
    def set_child_credit_balance(*, parent_user_id: int, child_user_id: int, desired_balance_usd: Decimal) -> Dict[str, float]:
        desired = max(Decimal("0.000000"), _to_decimal(desired_balance_usd))
        reference_id = int(time.time_ns())

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            AccountRepository._ensure_credit_rows(cur, user_ids=[int(parent_user_id), int(child_user_id)])
            cur.execute(
                """
                SELECT user_id, account_type
                FROM users
                WHERE user_id=%s
                LIMIT 1
                FOR UPDATE
                """,
                (int(parent_user_id),),
            )
            parent = cur.fetchone()
            if not parent:
                raise ValueError("user_not_found")
            if str(parent.get("account_type") or "") != ACCOUNT_TYPE_PARENT:
                raise ValueError("parent_required")

            cur.execute(
                """
                SELECT user_id, account_type, parent_user_id
                FROM users
                WHERE user_id=%s
                LIMIT 1
                FOR UPDATE
                """,
                (int(child_user_id),),
            )
            child = cur.fetchone()
            if not child:
                raise ValueError("user_not_found")
            if str(child.get("account_type") or "") != ACCOUNT_TYPE_CHILD or int(child.get("parent_user_id") or 0) != int(parent_user_id):
                raise ValueError("child_not_found")

            cur.execute(
                "SELECT balance_usd FROM user_credits WHERE user_id=%s LIMIT 1 FOR UPDATE",
                (int(parent_user_id),),
            )
            parent_credit_row = cur.fetchone() or {}
            cur.execute(
                "SELECT balance_usd FROM user_credits WHERE user_id=%s LIMIT 1 FOR UPDATE",
                (int(child_user_id),),
            )
            child_credit_row = cur.fetchone() or {}

            parent_balance = _to_decimal(parent_credit_row.get("balance_usd"))
            child_balance = _to_decimal(child_credit_row.get("balance_usd"))
            delta = desired - child_balance

            allocate_type_id = AccountRepository._get_credit_type_id(
                cur,
                code="PARENT_CHILD_ALLOCATE",
                default_name="Parent -> Child Credit Allocation",
            )
            deallocate_type_id = AccountRepository._get_credit_type_id(
                cur,
                code="PARENT_CHILD_DEALLOCATE",
                default_name="Child -> Parent Credit Return",
            )

            if delta > Decimal("0.000000"):
                if parent_balance < delta:
                    raise ValueError("insufficient_parent_credits")
                parent_balance -= delta
                child_balance += delta
                cur.execute(
                    "UPDATE user_credits SET balance_usd=%s WHERE user_id=%s",
                    (parent_balance, int(parent_user_id)),
                )
                cur.execute(
                    "UPDATE user_credits SET balance_usd=%s WHERE user_id=%s",
                    (child_balance, int(child_user_id)),
                )
                cur.execute(
                    """
                    INSERT INTO user_credits_transactions
                      (user_id, type_id, amount_usd, balance_after_usd, reference_type, reference_id, meta)
                    VALUES (%s, %s, %s, %s, %s, %s, JSON_OBJECT('counterparty_user_id', %s))
                    """,
                    (
                        int(parent_user_id),
                        int(allocate_type_id),
                        -delta,
                        parent_balance,
                        "parent_child_allocate_parent",
                        int(reference_id),
                        int(child_user_id),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO user_credits_transactions
                      (user_id, type_id, amount_usd, balance_after_usd, reference_type, reference_id, meta)
                    VALUES (%s, %s, %s, %s, %s, %s, JSON_OBJECT('counterparty_user_id', %s))
                    """,
                    (
                        int(child_user_id),
                        int(allocate_type_id),
                        delta,
                        child_balance,
                        "parent_child_allocate_child",
                        int(reference_id),
                        int(parent_user_id),
                    ),
                )
            elif delta < Decimal("0.000000"):
                refund = abs(delta)
                parent_balance += refund
                child_balance -= refund
                cur.execute(
                    "UPDATE user_credits SET balance_usd=%s WHERE user_id=%s",
                    (parent_balance, int(parent_user_id)),
                )
                cur.execute(
                    "UPDATE user_credits SET balance_usd=%s WHERE user_id=%s",
                    (child_balance, int(child_user_id)),
                )
                cur.execute(
                    """
                    INSERT INTO user_credits_transactions
                      (user_id, type_id, amount_usd, balance_after_usd, reference_type, reference_id, meta)
                    VALUES (%s, %s, %s, %s, %s, %s, JSON_OBJECT('counterparty_user_id', %s))
                    """,
                    (
                        int(child_user_id),
                        int(deallocate_type_id),
                        -refund,
                        child_balance,
                        "parent_child_deallocate_child",
                        int(reference_id),
                        int(parent_user_id),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO user_credits_transactions
                      (user_id, type_id, amount_usd, balance_after_usd, reference_type, reference_id, meta)
                    VALUES (%s, %s, %s, %s, %s, %s, JSON_OBJECT('counterparty_user_id', %s))
                    """,
                    (
                        int(parent_user_id),
                        int(deallocate_type_id),
                        refund,
                        parent_balance,
                        "parent_child_deallocate_parent",
                        int(reference_id),
                        int(child_user_id),
                    ),
                )

            cur.execute(
                """
                INSERT INTO child_credit_allocations (parent_user_id, child_user_id, allocated_balance_usd)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  parent_user_id=VALUES(parent_user_id),
                  allocated_balance_usd=VALUES(allocated_balance_usd)
                """,
                (int(parent_user_id), int(child_user_id), desired),
            )
            conn.commit()

        return {
            "parent_available_credit": _to_float(parent_balance),
            "child_credit": _to_float(child_balance),
            "allocated_credit": _to_float(desired),
        }

    @staticmethod
    def set_available_credit_balance(
        *,
        user_id: int,
        desired_balance_usd: Decimal,
        allowed_account_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        desired = max(Decimal("0.000000"), _to_decimal(desired_balance_usd))
        reference_id = int(time.time_ns())
        normalized_allowed = {
            str(item or "").strip().lower()
            for item in (allowed_account_types or [])
            if str(item or "").strip()
        }

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            AccountRepository._ensure_credit_rows(cur, user_ids=[int(user_id)])
            cur.execute(
                """
                SELECT user_id, account_type
                FROM users
                WHERE user_id=%s
                LIMIT 1
                FOR UPDATE
                """,
                (int(user_id),),
            )
            user = cur.fetchone()
            if not user:
                raise ValueError("user_not_found")

            account_type = str(user.get("account_type") or ACCOUNT_TYPE_STANDALONE).strip().lower() or ACCOUNT_TYPE_STANDALONE
            if normalized_allowed and account_type not in normalized_allowed:
                raise ValueError("unsupported_account_type")

            cur.execute(
                "SELECT balance_usd FROM user_credits WHERE user_id=%s LIMIT 1 FOR UPDATE",
                (int(user_id),),
            )
            credit_row = cur.fetchone() or {}
            current_balance = _to_decimal(credit_row.get("balance_usd"))
            delta = desired - current_balance

            if delta != Decimal("0.000000"):
                type_id = AccountRepository._get_credit_type_id(
                    cur,
                    code="ADMIN_CREDIT_SET",
                    default_name="Admin Credit Set",
                )
                cur.execute(
                    "UPDATE user_credits SET balance_usd=%s WHERE user_id=%s",
                    (desired, int(user_id)),
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
                        'source', 'admin_panel',
                        'previous_balance_usd', %s,
                        'target_balance_usd', %s
                      )
                    )
                    """,
                    (
                        int(user_id),
                        int(type_id),
                        delta,
                        desired,
                        "admin_credit_set",
                        int(reference_id),
                        current_balance,
                        desired,
                    ),
                )
            conn.commit()

        return {
            "user_id": int(user_id),
            "account_type": account_type,
            "previous_balance_usd": _to_float(current_balance),
            "balance_usd": _to_float(desired),
        }

    @staticmethod
    def delete_support_mail_rows(*, user_id: int) -> int:
        with core_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM support_mails WHERE user_id=%s", (int(user_id),))
                deleted = int(cur.rowcount or 0)
                conn.commit()
                return deleted
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return 0

