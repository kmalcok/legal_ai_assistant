from __future__ import annotations

from typing import Any, Dict, List, Optional

from .parser import (
    extract_deadlines_from_header_blocks,
    normalize_due_date,
    normalize_due_time,
)
from .repository import CalendarRepository


def add_event_for_user(
    *,
    user_id: int,
    title: str,
    due_date: str,
    note: Optional[str] = None,
    due_time: Optional[str] = None,
    chat_id: Optional[int] = None,
    petition_id: Optional[int] = None,
    source: str = "manual",
    color: Optional[str] = None,
) -> Dict[str, Any]:
    """Validated single-event creation. Returns the persisted event dict.

    Raises ValueError with codes: 'invalid_title', 'invalid_due_date'.
    """
    title_clean = (title or "").strip()
    if not title_clean:
        raise ValueError("invalid_title")
    iso_date = normalize_due_date(due_date or "")
    if not iso_date:
        raise ValueError("invalid_due_date")
    iso_time = normalize_due_time(due_time)

    # If a petition_id + same date already has an event for this user, return it (idempotent).
    if petition_id is not None:
        existing = CalendarRepository.find_existing_for_petition(
            user_id=int(user_id),
            petition_id=int(petition_id),
            due_date=iso_date,
        )
        if existing:
            return existing

    event_id = CalendarRepository.add_event(
        user_id=int(user_id),
        title=title_clean,
        due_date=iso_date,
        note=(note or None),
        due_time=iso_time,
        chat_id=int(chat_id) if chat_id is not None else None,
        petition_id=int(petition_id) if petition_id is not None else None,
        source=source,
        color=color,
    )
    saved = CalendarRepository.get_event(user_id=int(user_id), event_id=int(event_id))
    return saved or {"event_id": int(event_id)}


def register_from_petition(
    *,
    user_id: int,
    chat_id: int,
    petition_id: int,
    output_obj: Dict[str, Any],
    source: str = "petition_auto",
) -> List[Dict[str, Any]]:
    """Best-effort fallback: scan a petition's header_blocks and persist deadlines.

    Returns the list of persisted/existing events. Never raises; on errors returns [].
    """
    try:
        if not isinstance(output_obj, dict):
            return []
        header_blocks = output_obj.get("header_blocks")
        meta = output_obj.get("meta") if isinstance(output_obj.get("meta"), dict) else {}
        doc_type = (meta.get("document_type") or "").strip() or None
        court = (meta.get("court") or "").strip() or None

        candidates = extract_deadlines_from_header_blocks(
            header_blocks,
            document_type=doc_type,
            court=court,
        )
        saved: List[Dict[str, Any]] = []
        for c in candidates:
            try:
                ev = add_event_for_user(
                    user_id=int(user_id),
                    title=c["title"],
                    due_date=c["due_date"],
                    note=c.get("note"),
                    chat_id=int(chat_id),
                    petition_id=int(petition_id),
                    source=source,
                )
                if ev:
                    saved.append(ev)
            except Exception:
                continue
        return saved
    except Exception:
        return []
