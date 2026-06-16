from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple
from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect

from ...config import app_config
from ...data.db_chat_repository import ChatRepository
from ...realtime.ws_manager import chat_ws_manager
from ...utils.auth_audit import audit_auth_event
from ..auth import payload_user_id, validate_access_token
from ..client_ip import resolve_client_ip


router = APIRouter(prefix="/ws", tags=["ws"])


def _parse_bearer_auth_header(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    parts = str(raw).split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _extract_ws_access_token(websocket: WebSocket) -> Tuple[Optional[str], Optional[str]]:
    auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    token = _parse_bearer_auth_header(auth_header)
    if token:
        return token, None

    raw_protocols = websocket.headers.get("sec-websocket-protocol") or ""
    offered = [part.strip() for part in raw_protocols.split(",") if part and part.strip()]
    lowered = [item.lower() for item in offered]
    if len(offered) >= 2 and lowered[0] in {"bearer", "access_token"}:
        return offered[1], offered[0]

    return None, None


def _origin_allowed(websocket: WebSocket) -> bool:
    allowed = list(app_config().allowed_ws_origins)
    if not allowed or "*" in allowed:
        return True
    origin = (websocket.headers.get("origin") or websocket.headers.get("Origin") or "").strip()
    if not origin:
        return True
    return origin in allowed


@router.websocket("/chat/{chat_id}")
async def ws_chat_channel(
    websocket: WebSocket,
    chat_id: int,
    token: str = Query(default=""),
) -> None:
    """
    Websocket channel for a chat: chat:{chat_id}
    Preferred auth:
    - Authorization: Bearer <access_token>
    - Sec-WebSocket-Protocol: bearer, <access_token>
    """
    _ = token  # Legacy query token intentionally ignored.
    client_ip = resolve_client_ip(websocket)
    origin = (websocket.headers.get("origin") or websocket.headers.get("Origin") or "").strip()
    if not _origin_allowed(websocket):
        audit_auth_event(
            "ws_origin_denied",
            {"chat_id": int(chat_id), "ip": client_ip, "origin": origin or None},
        )
        await websocket.close(code=4403)
        return

    access_token, accepted_subprotocol = _extract_ws_access_token(websocket)
    payload, err = await validate_access_token(access_token) if access_token else (None, "missing_authorization")
    if payload is None:
        audit_auth_event(
            "ws_auth_failed",
            {"chat_id": int(chat_id), "ip": client_ip, "origin": origin or None, "reason": str(err or "invalid_token")},
        )
        await websocket.close(code=4401)
        return
    user_id = int(payload_user_id(payload))

    # Ownership check
    chat = ChatRepository.get_chat(int(chat_id), int(user_id))
    if chat is None:
        await websocket.close(code=4403)
        return

    await chat_ws_manager.connect(int(chat_id), websocket, subprotocol=accepted_subprotocol)
    try:
        # Keep connection alive; we don't require client messages.
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await chat_ws_manager.disconnect(int(chat_id), websocket)


@router.get("/debug", response_model=dict)
async def ws_debug(request: Request, chat_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Debug endpoint to verify websocket connection counts and redis fallback.
    Requires normal JWT auth middleware (request.state.user_id).
    """
    _ = int(getattr(request.state, "user_id"))  # ensure authenticated
    return {"ok": True, "stats": await chat_ws_manager.stats(int(chat_id) if chat_id is not None else None)}


