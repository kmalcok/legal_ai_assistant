from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

from ..db import core_db


_ALLOWED_SOURCES = {"petition_tool", "petition_auto", "manual"}
_ALLOWED_STATUSES = {"pending", "done", "dismissed"}


def _row_to_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize DB row into an API-friendly dict (ISO date strings)."""
    if not row:
        return {}
    out: Dict[str, Any] = dict(row)
    due = out.get("due_date")
    if isinstance(due, (date, datetime)):
        out["due_date"] = due.isoformat()[:10]
    due_t = out.get("due_time")
    if isinstance(due_t, time):
        out["due_time"] = due_t.strftime("%H:%M")
    elif isinstance(due_t, datetime):
        out["due_time"] = due_t.strftime("%H:%M")
    elif due_t is not None and not isinstance(due_t, str):
        # MariaDB connector occasionally returns timedelta for TIME columns
        try:
            total = int(getattr(due_t, "total_seconds")())
            hh = total // 3600
            mm = (total % 3600) // 60
            out["due_time"] = f"{hh:02d}:{mm:02d}"
        except Exception:
            out["due_time"] = str(due_t)
    for k in ("created_at", "updated_at"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat(sep=" ", timespec="seconds")
    for k in ("event_id", "user_id", "chat_id", "petition_id"):
        v = out.get(k)
        if v is not None:
            try:
                out[k] = int(v)
            except Exception:
                pass
    return out


class CalendarRepository:
    @staticmethod
    def add_event(
        *,
        user_id: int,
        title: str,
        due_date: str,
        note: Optional[str] = None,
        due_time: Optional[str] = None,
        chat_id: Optional[int] = None,
        petition_id: Optional[int] = None,
        source: str = "manual",
        status: str = "pending",
        color: Optional[str] = None,
    ) -> int:
        if source not in _ALLOWED_SOURCES:
            source = "manual"
        if status not in _ALLOWED_STATUSES:
            status = "pending"
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO calendar_events
                  (user_id, chat_id, petition_id, title, note, due_date, due_time, source, status, color)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    int(user_id),
                    int(chat_id) if chat_id is not None else None,
                    int(petition_id) if petition_id is not None else None,
                    str(title)[:512],
                    note,
                    due_date,
                    due_time,
                    source,
                    status,
                    color,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    @staticmethod
    def get_event(*, user_id: int, event_id: int) -> Optional[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT event_id, user_id, chat_id, petition_id, title, note,
                       due_date, due_time, source, status, color, created_at, updated_at
                FROM calendar_events
                WHERE event_id=%s AND user_id=%s
                LIMIT 1
                """,
                (int(event_id), int(user_id)),
            )
            row = cur.fetchone()
            return _row_to_event(row) if row else None

    @staticmethod
    def list_events(
        *,
        user_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        clauses = ["user_id=%s"]
        params: List[Any] = [int(user_id)]
        if date_from:
            clauses.append("due_date >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("due_date <= %s")
            params.append(date_to)
        if status and status in _ALLOWED_STATUSES:
            clauses.append("status=%s")
            params.append(status)
        where = " AND ".join(clauses)
        lim = max(1, min(int(limit), 2000))
        params.append(lim)
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                f"""
                SELECT event_id, user_id, chat_id, petition_id, title, note,
                       due_date, due_time, source, status, color, created_at, updated_at
                FROM calendar_events
                WHERE {where}
                ORDER BY due_date ASC, due_time ASC, event_id ASC
                LIMIT %s
                """,
                tuple(params),
            )
            rows = list(cur.fetchall() or [])
            return [_row_to_event(r) for r in rows]

    @staticmethod
    def find_existing_for_petition(
        *,
        user_id: int,
        petition_id: int,
        due_date: str,
    ) -> Optional[Dict[str, Any]]:
        """Used to enforce duplicate prevention when both tool + auto-parser register."""
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT event_id, user_id, chat_id, petition_id, title, note,
                       due_date, due_time, source, status, color, created_at, updated_at
                FROM calendar_events
                WHERE user_id=%s AND petition_id=%s AND due_date=%s
                LIMIT 1
                """,
                (int(user_id), int(petition_id), due_date),
            )
            row = cur.fetchone()
            return _row_to_event(row) if row else None

    @staticmethod
    def update_event(
        *,
        user_id: int,
        event_id: int,
        title: Optional[str] = None,
        note: Optional[str] = None,
        due_date: Optional[str] = None,
        due_time: Optional[str] = None,
        status: Optional[str] = None,
        color: Optional[str] = None,
    ) -> bool:
        sets: List[str] = []
        params: List[Any] = []
        if title is not None:
            sets.append("title=%s")
            params.append(str(title)[:512])
        if note is not None:
            sets.append("note=%s")
            params.append(note)
        if due_date is not None:
            sets.append("due_date=%s")
            params.append(due_date)
        if due_time is not None:
            sets.append("due_time=%s")
            params.append(due_time if due_time else None)
        if status is not None:
            if status not in _ALLOWED_STATUSES:
                raise ValueError("invalid_status")
            sets.append("status=%s")
            params.append(status)
        if color is not None:
            sets.append("color=%s")
            params.append(color or None)
        if not sets:
            return False
        params.extend([int(event_id), int(user_id)])
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                UPDATE calendar_events
                SET {", ".join(sets)}
                WHERE event_id=%s AND user_id=%s
                """,
                tuple(params),
            )
            conn.commit()
            return int(cur.rowcount or 0) > 0

    @staticmethod
    def delete_event(*, user_id: int, event_id: int) -> bool:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM calendar_events WHERE event_id=%s AND user_id=%s",
                (int(event_id), int(user_id)),
            )
            conn.commit()
            return int(cur.rowcount or 0) > 0
