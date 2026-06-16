from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...calendar_events.parser import normalize_due_date, normalize_due_time
from ...calendar_events.repository import CalendarRepository
from ...calendar_events.service import add_event_for_user


router = APIRouter(prefix="/calendar", tags=["calendar"])


_ALLOWED_STATUSES = {"pending", "done", "dismissed"}


class CalendarEventCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    due_date: str = Field(..., min_length=1, description="GG.AA.YYYY veya YYYY-MM-DD")
    note: Optional[str] = Field(default=None)
    due_time: Optional[str] = Field(default=None, description="HH:MM")
    chat_id: Optional[int] = Field(default=None, gt=0)
    petition_id: Optional[int] = Field(default=None, gt=0)
    color: Optional[str] = Field(default=None, max_length=16)


class CalendarEventUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=512)
    note: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None)
    due_time: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    color: Optional[str] = Field(default=None, max_length=16)


@router.get("/events", response_model=dict)
async def list_calendar_events(
    request: Request,
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    norm_from: Optional[str] = None
    norm_to: Optional[str] = None
    if from_:
        norm_from = normalize_due_date(from_)
        if not norm_from:
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_from"})
    if to:
        norm_to = normalize_due_date(to)
        if not norm_to:
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_to"})
    norm_status: Optional[str] = None
    if status:
        if status not in _ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_status"})
        norm_status = status
    try:
        rows = await asyncio.to_thread(
            CalendarRepository.list_events,
            user_id=user_id,
            date_from=norm_from,
            date_to=norm_to,
            status=norm_status,
            limit=int(limit),
        )
        return {"ok": True, "events": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.get("/events/{event_id}", response_model=dict)
async def get_calendar_event(request: Request, event_id: int) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        row = await asyncio.to_thread(
            CalendarRepository.get_event,
            user_id=user_id,
            event_id=int(event_id),
        )
        if row is None:
            raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found"})
        return {"ok": True, "event": row}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.post("/events", response_model=dict)
async def create_calendar_event(request: Request, payload: CalendarEventCreateRequest) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        ev = await asyncio.to_thread(
            add_event_for_user,
            user_id=user_id,
            title=payload.title,
            due_date=payload.due_date,
            note=payload.note,
            due_time=payload.due_time,
            chat_id=int(payload.chat_id) if payload.chat_id is not None else None,
            petition_id=int(payload.petition_id) if payload.petition_id is not None else None,
            source="manual",
            color=payload.color,
        )
        return {"ok": True, "event": ev}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.patch("/events/{event_id}", response_model=dict)
async def update_calendar_event(
    request: Request,
    event_id: int,
    payload: CalendarEventUpdateRequest,
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))

    norm_due: Optional[str] = None
    if payload.due_date is not None:
        norm_due = normalize_due_date(payload.due_date)
        if not norm_due:
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_due_date"})

    norm_time: Optional[str] = None
    if payload.due_time is not None and payload.due_time != "":
        norm_time = normalize_due_time(payload.due_time)
        if not norm_time:
            raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_due_time"})
    elif payload.due_time == "":
        # explicit empty string clears the time
        norm_time = ""

    if payload.status is not None and payload.status not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_status"})

    try:
        # Verify ownership BEFORE attempting the update so a no-op write
        # (e.g. user re-marks an already-done event) doesn't end up as a 404
        # just because the MariaDB connector reports rowcount=0 for
        # "matched but not changed" rows.
        existing = await asyncio.to_thread(
            CalendarRepository.get_event,
            user_id=user_id,
            event_id=int(event_id),
        )
        if existing is None:
            raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found"})

        await asyncio.to_thread(
            CalendarRepository.update_event,
            user_id=user_id,
            event_id=int(event_id),
            title=payload.title,
            note=payload.note,
            due_date=norm_due,
            due_time=norm_time,
            status=payload.status,
            color=payload.color,
        )
        ev = await asyncio.to_thread(
            CalendarRepository.get_event,
            user_id=user_id,
            event_id=int(event_id),
        )
        return {"ok": True, "event": ev}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.delete("/events/{event_id}", response_model=dict)
async def delete_calendar_event(request: Request, event_id: int) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        ok = await asyncio.to_thread(
            CalendarRepository.delete_event,
            user_id=user_id,
            event_id=int(event_id),
        )
        if not ok:
            raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found"})
        return {"ok": True, "event_id": int(event_id)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})
