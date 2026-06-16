from __future__ import annotations

from typing import Any, Dict, Optional

from ..db import core_db


DEFAULT_MAIN_AGENT_VERBOSITY = "medium"
DEFAULT_ICTIHAT_AGENT_REASONING_EFFORT = None


class UserAppConfigRepository:
    @staticmethod
    def default_values() -> Dict[str, Any]:
        return {
            "main_agent_verbosity": DEFAULT_MAIN_AGENT_VERBOSITY,
            "main_agent_reasoning_effort": None,
            "ictihat_agent_reasoning_effort": DEFAULT_ICTIHAT_AGENT_REASONING_EFFORT,
            "extra_instructions": None,
        }

    @staticmethod
    def get_by_user_id(*, user_id: int) -> Optional[Dict[str, Any]]:
        try:
            with core_db() as conn:
                cur = conn.cursor(dictionary=True)
                cur.execute(
                    """
                    SELECT
                      user_id,
                      main_agent_verbosity,
                      main_agent_reasoning_effort,
                      ictihat_agent_reasoning_effort,
                      extra_instructions,
                      created_at,
                      updated_at
                    FROM user_app_config
                    WHERE user_id=%s
                    LIMIT 1
                    """,
                    (int(user_id),),
                )
                return cur.fetchone()
        except Exception:
            return None

    @staticmethod
    def upsert(*, user_id: int, values: Dict[str, Any]) -> None:
        allowed = (
            "main_agent_verbosity",
            "main_agent_reasoning_effort",
            "ictihat_agent_reasoning_effort",
            "extra_instructions",
        )
        fields = [name for name in allowed if name in values]
        if not fields:
            return

        insert_cols = ["user_id", *fields]
        insert_values = [int(user_id), *[values.get(name) for name in fields]]
        assignments = ", ".join(f"{name}=VALUES({name})" for name in fields)

        sql = (
            f"INSERT INTO user_app_config ({', '.join(insert_cols)}) "
            f"VALUES ({', '.join(['%s'] * len(insert_cols))}) "
            f"ON DUPLICATE KEY UPDATE {assignments}"
        )
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, tuple(insert_values))
            conn.commit()
