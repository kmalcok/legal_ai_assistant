from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from ...calendar_events.service import add_event_for_user
from ...realtime.ws_manager import chat_ws_manager
from ..logging.agent_audit import audit_log


async def _safe_publish(chat_id: int, payload: Dict[str, Any]) -> int:
    try:
        return int(await chat_ws_manager.publish(int(chat_id), payload))
    except Exception:
        return 0


async def calendar_add_event(
    *,
    user_id: int,
    chat_id: Optional[int],
    title: str,
    due_date: str,
    note: Optional[str] = None,
    due_time: Optional[str] = None,
    petition_id: Optional[int] = None,
    source: str = "petition_tool",
) -> Dict[str, Any]:
    """Persist a new deadline/event for the user and notify the chat over websocket.

    Used by the agent tool `calendar_add_event`. Idempotent w.r.t. (petition_id, due_date).
    """
    audit_log(
        "calendar_tool_input",
        {
            "tool": "calendar_add_event",
            "user_id": int(user_id),
            "chat_id": int(chat_id) if chat_id is not None else None,
            "title_len": len(str(title or "")),
            "due_date": str(due_date or ""),
            "due_time": str(due_time or ""),
            "petition_id": int(petition_id) if petition_id is not None else None,
            "source": str(source or "petition_tool"),
        },
    )
    try:
        ev = await asyncio.to_thread(
            add_event_for_user,
            user_id=int(user_id),
            title=title,
            due_date=due_date,
            note=note,
            due_time=due_time,
            chat_id=int(chat_id) if chat_id is not None else None,
            petition_id=int(petition_id) if petition_id is not None else None,
            source=source,
        )
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}
    except Exception as exc:
        return {"ok": False, "reason": "error", "detail": str(exc)}

    if chat_id is not None:
        await _safe_publish(
            int(chat_id),
            {
                "type": "calendar_event_added",
                "chat_id": int(chat_id),
                "event_id": int(ev.get("event_id") or 0),
                "due_date": ev.get("due_date"),
                "title": ev.get("title"),
            },
        )

    return {
        "ok": True,
        "event_id": int(ev.get("event_id") or 0),
        "due_date": ev.get("due_date"),
        "title": ev.get("title"),
        "note": ev.get("note"),
        "petition_id": ev.get("petition_id"),
        "status": ev.get("status"),
        "info_hint": "Süre takvime kaydedildi. Kullanıcıya teknik kimlik göstermeyin; yalnızca tarih ve kısa not yeterlidir.",
    }
