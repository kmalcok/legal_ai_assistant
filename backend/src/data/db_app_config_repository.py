from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from ..db import core_db


ACTIVE_USER_COUNT_KEY = "active_user_count"
ACTIVE_USER_COUNT_NEXT_UPDATE_TS_KEY = "active_user_count_next_update_ts"
ACTIVE_USER_COUNT_LOCK_NAME = "app_config:active_user_count:tick"


def _int_from_value(value: Any, *, default: int = 0) -> int:
    if value is None:
        return int(default)
    try:
        if isinstance(value, Decimal):
            return int(value)
        return int(Decimal(str(value)))
    except Exception:
        return int(default)


def _serialize_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


class AppConfigRepository:
    @staticmethod
    def get_by_key(*, key: str) -> Optional[Dict[str, Any]]:
        try:
            with core_db() as conn:
                cur = conn.cursor(dictionary=True)
                cur.execute(
                    """
                    SELECT
                      config_key,
                      value_bool,
                      value_decimal,
                      value_text,
                      updated_at
                    FROM app_config
                    WHERE config_key=%s
                    LIMIT 1
                    """,
                    (str(key),),
                )
                return cur.fetchone()
        except Exception:
            return None

    @staticmethod
    def get_active_user_count() -> Dict[str, Any]:
        row = AppConfigRepository.get_by_key(key=ACTIVE_USER_COUNT_KEY) or {}
        return {
            "config_key": ACTIVE_USER_COUNT_KEY,
            "value": _int_from_value(row.get("value_decimal"), default=0),
            "updated_at": _serialize_datetime(row.get("updated_at")),
        }

    @staticmethod
    def process_active_user_count_tick(*, now_ts: int, increment_by: int, next_delay_seconds: int) -> Dict[str, Any]:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT GET_LOCK(%s, 0)", (ACTIVE_USER_COUNT_LOCK_NAME,))
            lock_row = cur.fetchone()
            if not lock_row or int(lock_row[0] or 0) != 1:
                return {"status": "busy"}

            try:
                cur_dict = conn.cursor(dictionary=True)
                cur_dict.execute(
                    """
                    SELECT value_decimal
                    FROM app_config
                    WHERE config_key=%s
                    LIMIT 1
                    """,
                    (ACTIVE_USER_COUNT_NEXT_UPDATE_TS_KEY,),
                )
                next_row = cur_dict.fetchone()
                next_ts = _int_from_value((next_row or {}).get("value_decimal"), default=0)

                if next_ts <= 0:
                    scheduled_ts = int(now_ts) + max(1, int(next_delay_seconds))
                    cur.execute(
                        """
                        INSERT INTO app_config (config_key, value_decimal)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE value_decimal=VALUES(value_decimal)
                        """,
                        (ACTIVE_USER_COUNT_NEXT_UPDATE_TS_KEY, int(scheduled_ts)),
                    )
                    conn.commit()
                    return {"status": "scheduled", "next_run_ts": int(scheduled_ts)}

                if next_ts > int(now_ts):
                    return {"status": "not_due", "next_run_ts": int(next_ts)}

                cur.execute(
                    """
                    INSERT INTO app_config (config_key, value_decimal)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE value_decimal=COALESCE(value_decimal, 0) + %s
                    """,
                    (ACTIVE_USER_COUNT_KEY, int(increment_by), int(increment_by)),
                )
                scheduled_ts = int(now_ts) + max(1, int(next_delay_seconds))
                cur.execute(
                    """
                    INSERT INTO app_config (config_key, value_decimal)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE value_decimal=VALUES(value_decimal)
                    """,
                    (ACTIVE_USER_COUNT_NEXT_UPDATE_TS_KEY, int(scheduled_ts)),
                )
                conn.commit()

                cur_dict.execute(
                    """
                    SELECT value_decimal, updated_at
                    FROM app_config
                    WHERE config_key=%s
                    LIMIT 1
                    """,
                    (ACTIVE_USER_COUNT_KEY,),
                )
                row = cur_dict.fetchone() or {}
                return {
                    "status": "incremented",
                    "value": _int_from_value(row.get("value_decimal"), default=0),
                    "updated_at": _serialize_datetime(row.get("updated_at")),
                    "next_run_ts": int(scheduled_ts),
                    "increment_by": int(increment_by),
                }
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
            finally:
                try:
                    cur.execute("SELECT RELEASE_LOCK(%s)", (ACTIVE_USER_COUNT_LOCK_NAME,))
                except Exception:
                    pass
