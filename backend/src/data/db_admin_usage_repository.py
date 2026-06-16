from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from ..db import core_db
from ..utils.credit_conversion import normalize_account_plan, usd_to_credit


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _to_float(value: Any) -> float:
    return float(_to_decimal(value))


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _build_usage_summary(row: Optional[Dict[str, Any]], *, account_plan: Any) -> Dict[str, Any]:
    payload = row or {}
    input_tokens = _to_int(payload.get("input_tokens"))
    output_tokens = _to_int(payload.get("output_tokens"))
    reasoning_tokens = _to_int(payload.get("reasoning_tokens"))
    usage_row_count = _to_int(payload.get("usage_row_count"))
    cost_tx_count = _to_int(payload.get("cost_tx_count"))
    spent_usd = _to_float(payload.get("spent_usd"))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": input_tokens + output_tokens + reasoning_tokens,
        "spent_usd": spent_usd,
        "spent_credit": usd_to_credit(spent_usd, account_plan=account_plan),
        "usage_row_count": usage_row_count,
        "cost_tx_count": cost_tx_count,
        "has_cost_data": bool(cost_tx_count > 0 or usage_row_count == 0),
    }


class AdminUsageRepository:
    @staticmethod
    def get_usage_overview(*, user_id: int) -> Dict[str, Any]:
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
            user_row = cur.fetchone() or {}

            cur.execute(
                """
                SELECT
                  COUNT(DISTINCT c.chat_id) AS chat_count,
                  COUNT(cm.id) AS message_count,
                  MAX(COALESCE(cm.created_at, c.updated_at, c.created_at)) AS last_activity_at
                FROM chats c
                LEFT JOIN chat_messages cm ON cm.chat_id = c.chat_id
                WHERE c.user_id=%s AND c.archived=0
                """,
                (int(user_id),),
            )
            activity_row = cur.fetchone() or {}

            cur.execute(
                """
                SELECT
                  COUNT(*) AS usage_row_count,
                  COALESCE(SUM(CASE WHEN type='input_tokens' THEN amount ELSE 0 END), 0) AS input_tokens,
                  COALESCE(SUM(CASE WHEN type='output_tokens' THEN amount ELSE 0 END), 0) AS output_tokens,
                  COALESCE(SUM(CASE WHEN type='reasoning_tokens' THEN amount ELSE 0 END), 0) AS reasoning_tokens,
                  MAX(created_at) AS last_usage_at
                FROM user_usages
                WHERE user_id=%s
                """,
                (int(user_id),),
            )
            usage_row = cur.fetchone() or {}

            cur.execute(
                """
                SELECT
                  COUNT(tx.tx_id) AS cost_tx_count,
                  COALESCE(SUM(CASE WHEN tx.amount_usd < 0 THEN -tx.amount_usd ELSE 0 END), 0.000000) AS spent_usd
                FROM user_usages uu
                JOIN user_credits_transactions tx
                  ON tx.user_id = uu.user_id
                 AND tx.reference_type = 'user_usage'
                 AND tx.reference_id = uu.id
                WHERE uu.user_id=%s
                """,
                (int(user_id),),
            )
            cost_row = cur.fetchone() or {}

        account_plan = normalize_account_plan(user_row.get("account_plan"))
        summary = _build_usage_summary({**usage_row, **cost_row}, account_plan=account_plan)
        return {
            **summary,
            "chat_count": _to_int(activity_row.get("chat_count")),
            "message_count": _to_int(activity_row.get("message_count")),
            "last_activity_at": activity_row.get("last_activity_at") or usage_row.get("last_usage_at"),
        }

    @staticmethod
    def list_chats(*, user_id: int) -> List[Dict[str, Any]]:
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
            user_row = cur.fetchone() or {}
            cur.execute(
                """
                SELECT
                  c.chat_id,
                  c.user_id,
                  c.title,
                  c.first_message,
                  c.last_sum,
                  c.archived,
                  c.created_at,
                  c.updated_at,
                  COALESCE(msg.message_count, 0) AS message_count,
                  COALESCE(usage_stats.usage_row_count, 0) AS usage_row_count,
                  COALESCE(usage_stats.input_tokens, 0) AS input_tokens,
                  COALESCE(usage_stats.output_tokens, 0) AS output_tokens,
                  COALESCE(usage_stats.reasoning_tokens, 0) AS reasoning_tokens,
                  usage_stats.last_usage_at,
                  COALESCE(cost.cost_tx_count, 0) AS cost_tx_count,
                  COALESCE(cost.spent_usd, 0.000000) AS spent_usd
                FROM chats c
                LEFT JOIN (
                  SELECT
                    chat_id,
                    COUNT(*) AS message_count
                  FROM chat_messages
                  GROUP BY chat_id
                ) msg ON msg.chat_id = c.chat_id
                LEFT JOIN (
                  SELECT
                    chat_id,
                    COUNT(*) AS usage_row_count,
                    SUM(CASE WHEN type='input_tokens' THEN amount ELSE 0 END) AS input_tokens,
                    SUM(CASE WHEN type='output_tokens' THEN amount ELSE 0 END) AS output_tokens,
                    SUM(CASE WHEN type='reasoning_tokens' THEN amount ELSE 0 END) AS reasoning_tokens,
                    MAX(created_at) AS last_usage_at
                  FROM user_usages
                  WHERE user_id=%s AND chat_id IS NOT NULL
                  GROUP BY chat_id
                ) usage_stats ON usage_stats.chat_id = c.chat_id
                LEFT JOIN (
                  SELECT
                    uu.chat_id,
                    COUNT(tx.tx_id) AS cost_tx_count,
                    COALESCE(SUM(CASE WHEN tx.amount_usd < 0 THEN -tx.amount_usd ELSE 0 END), 0.000000) AS spent_usd
                  FROM user_usages uu
                  JOIN user_credits_transactions tx
                    ON tx.user_id = uu.user_id
                   AND tx.reference_type = 'user_usage'
                   AND tx.reference_id = uu.id
                  WHERE uu.user_id=%s AND uu.chat_id IS NOT NULL
                  GROUP BY uu.chat_id
                ) cost ON cost.chat_id = c.chat_id
                WHERE c.user_id=%s AND c.archived=0
                ORDER BY c.updated_at DESC, c.chat_id DESC
                """,
                (int(user_id), int(user_id), int(user_id)),
            )
            rows = list(cur.fetchall() or [])

        account_plan = normalize_account_plan(user_row.get("account_plan"))
        chats: List[Dict[str, Any]] = []
        for row in rows:
            summary = _build_usage_summary(row, account_plan=account_plan)
            chats.append(
                {
                    "chat_id": _to_int(row.get("chat_id")),
                    "user_id": _to_int(row.get("user_id")),
                    "title": row.get("title"),
                    "first_message": row.get("first_message"),
                    "last_sum": row.get("last_sum"),
                    "archived": bool(row.get("archived")),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                    "message_count": _to_int(row.get("message_count")),
                    "last_usage_at": row.get("last_usage_at"),
                    "usage": summary,
                }
            )
        return chats

    @staticmethod
    def get_chat_detail(*, user_id: int, chat_id: int) -> Optional[Dict[str, Any]]:
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
            user_row = cur.fetchone() or {}
            cur.execute(
                """
                SELECT
                  c.chat_id,
                  c.user_id,
                  c.title,
                  c.first_message,
                  c.last_sum,
                  c.archived,
                  c.created_at,
                  c.updated_at,
                  COALESCE(msg.message_count, 0) AS message_count,
                  COALESCE(usage_stats.usage_row_count, 0) AS usage_row_count,
                  COALESCE(usage_stats.input_tokens, 0) AS input_tokens,
                  COALESCE(usage_stats.output_tokens, 0) AS output_tokens,
                  COALESCE(usage_stats.reasoning_tokens, 0) AS reasoning_tokens,
                  usage_stats.last_usage_at,
                  COALESCE(cost.cost_tx_count, 0) AS cost_tx_count,
                  COALESCE(cost.spent_usd, 0.000000) AS spent_usd
                FROM chats c
                LEFT JOIN (
                  SELECT
                    chat_id,
                    COUNT(*) AS message_count
                  FROM chat_messages
                  GROUP BY chat_id
                ) msg ON msg.chat_id = c.chat_id
                LEFT JOIN (
                  SELECT
                    chat_id,
                    COUNT(*) AS usage_row_count,
                    SUM(CASE WHEN type='input_tokens' THEN amount ELSE 0 END) AS input_tokens,
                    SUM(CASE WHEN type='output_tokens' THEN amount ELSE 0 END) AS output_tokens,
                    SUM(CASE WHEN type='reasoning_tokens' THEN amount ELSE 0 END) AS reasoning_tokens,
                    MAX(created_at) AS last_usage_at
                  FROM user_usages
                  WHERE user_id=%s AND chat_id=%s
                  GROUP BY chat_id
                ) usage_stats ON usage_stats.chat_id = c.chat_id
                LEFT JOIN (
                  SELECT
                    uu.chat_id,
                    COUNT(tx.tx_id) AS cost_tx_count,
                    COALESCE(SUM(CASE WHEN tx.amount_usd < 0 THEN -tx.amount_usd ELSE 0 END), 0.000000) AS spent_usd
                  FROM user_usages uu
                  JOIN user_credits_transactions tx
                    ON tx.user_id = uu.user_id
                   AND tx.reference_type = 'user_usage'
                   AND tx.reference_id = uu.id
                  WHERE uu.user_id=%s AND uu.chat_id=%s
                  GROUP BY uu.chat_id
                ) cost ON cost.chat_id = c.chat_id
                WHERE c.user_id=%s AND c.chat_id=%s
                LIMIT 1
                """,
                (int(user_id), int(chat_id), int(user_id), int(chat_id), int(user_id), int(chat_id)),
            )
            chat_row = cur.fetchone()
            if not chat_row:
                return None

            cur.execute(
                """
                SELECT
                  cm.id,
                  cm.chat_id,
                  cm.role,
                  cm.message,
                  cm.created_at,
                  COALESCE(message_usage_stats.usage_row_count, 0) AS usage_row_count,
                  COALESCE(message_usage_stats.input_tokens, 0) AS input_tokens,
                  COALESCE(message_usage_stats.output_tokens, 0) AS output_tokens,
                  COALESCE(message_usage_stats.reasoning_tokens, 0) AS reasoning_tokens,
                  COALESCE(cost.cost_tx_count, 0) AS cost_tx_count,
                  COALESCE(cost.spent_usd, 0.000000) AS spent_usd
                FROM chat_messages cm
                LEFT JOIN (
                  SELECT
                    chat_message_id,
                    COUNT(*) AS usage_row_count,
                    SUM(CASE WHEN type='input_tokens' THEN amount ELSE 0 END) AS input_tokens,
                    SUM(CASE WHEN type='output_tokens' THEN amount ELSE 0 END) AS output_tokens,
                    SUM(CASE WHEN type='reasoning_tokens' THEN amount ELSE 0 END) AS reasoning_tokens
                  FROM user_usages
                  WHERE user_id=%s AND chat_id=%s AND chat_message_id IS NOT NULL
                  GROUP BY chat_message_id
                ) message_usage_stats ON message_usage_stats.chat_message_id = cm.id
                LEFT JOIN (
                  SELECT
                    uu.chat_message_id,
                    COUNT(tx.tx_id) AS cost_tx_count,
                    COALESCE(SUM(CASE WHEN tx.amount_usd < 0 THEN -tx.amount_usd ELSE 0 END), 0.000000) AS spent_usd
                  FROM user_usages uu
                  JOIN user_credits_transactions tx
                    ON tx.user_id = uu.user_id
                   AND tx.reference_type = 'user_usage'
                   AND tx.reference_id = uu.id
                  WHERE uu.user_id=%s AND uu.chat_id=%s AND uu.chat_message_id IS NOT NULL
                  GROUP BY uu.chat_message_id
                ) cost ON cost.chat_message_id = cm.id
                WHERE cm.chat_id=%s
                ORDER BY cm.created_at ASC, cm.id ASC
                """,
                (int(user_id), int(chat_id), int(user_id), int(chat_id), int(chat_id)),
            )
            message_rows = list(cur.fetchall() or [])

        account_plan = normalize_account_plan(user_row.get("account_plan"))
        messages: List[Dict[str, Any]] = []
        for row in message_rows:
            usage = _build_usage_summary(row, account_plan=account_plan)
            messages.append(
                {
                    "id": _to_int(row.get("id")),
                    "chat_id": _to_int(row.get("chat_id")),
                    "role": row.get("role"),
                    "message": row.get("message") or "",
                    "created_at": row.get("created_at"),
                    "usage": usage,
                }
            )

        chat_summary = _build_usage_summary(chat_row, account_plan=account_plan)
        return {
            "chat": {
                "chat_id": _to_int(chat_row.get("chat_id")),
                "user_id": _to_int(chat_row.get("user_id")),
                "title": chat_row.get("title"),
                "first_message": chat_row.get("first_message"),
                "last_sum": chat_row.get("last_sum"),
                "archived": bool(chat_row.get("archived")),
                "created_at": chat_row.get("created_at"),
                "updated_at": chat_row.get("updated_at"),
                "message_count": _to_int(chat_row.get("message_count")),
                "last_usage_at": chat_row.get("last_usage_at"),
                "usage": chat_summary,
            },
            "history": messages,
        }
