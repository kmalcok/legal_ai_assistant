from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request

from ...ai.tool_wrappers.ictihat_api_semantic_agent import ictihat_api_semantic_search as _ictihat_api_semantic_search
from ...ai.tool_wrappers.ictihat_get_document import ictihat_get_document as _ictihat_get_document
from ...ai.tool_wrappers.ictihat_search import ictihat_keyword_search as _ictihat_keyword_search
from ...ai.tool_wrappers.ictihat_search import ictihat_search as _ictihat_search
from ...data.db_ictihat_search_history_repository import IctihatSearchHistoryRepository
from ...services.ictihat_daire_cache_service import get_cached_ictihat_daire_names
from ..credit_guard import ensure_sufficient_credits
from ..errors import api_error, status_for_reason


router = APIRouter(prefix="/ictihat", tags=["ictihat"])


def _raise_result_error(
    res: Dict[str, Any],
    *,
    fallback_reason: str,
    log_extra: Dict[str, Any] | None = None,
) -> None:
    reason = str((res or {}).get("reason") or fallback_reason)
    detail = (res or {}).get("detail")
    extra = {
        str(k): v
        for k, v in (res or {}).items()
        if str(k) not in {"ok", "reason", "detail"} and v is not None
    }
    status = status_for_reason(reason)
    try:
        log_payload: Dict[str, Any] = {
            "event": "ictihat_route_result_error",
            "reason": reason[:2000],
            "http_status": int(status),
            "detail_type": type(detail).__name__ if detail is not None else None,
            "detail_preview": (str(detail)[:800] if detail is not None else None),
            "extra_keys": sorted(str(k) for k in extra.keys())[:40],
        }
        if isinstance(log_extra, dict) and log_extra:
            log_payload.update({str(k): v for k, v in log_extra.items() if v is not None})
        logging.getLogger("mevzuat.api").warning(json.dumps(log_payload, ensure_ascii=False, default=str))
    except Exception:
        pass
    raise api_error(status, reason, detail=detail, **extra)


def _history_result_items(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not isinstance(res, dict):
        return items
    raw_items = res.get("items")
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                items.append(item)
        return items
    raw_groups = res.get("groups")
    if isinstance(raw_groups, list):
        for group in raw_groups:
            if not isinstance(group, dict):
                continue
            doc = group.get("doc")
            if isinstance(doc, dict):
                items.append(doc)
    return items


async def _save_search_history(
    *,
    user_id: int,
    search_type: str,
    query: str | None,
    filters: Dict[str, Any] | None,
    top_k: int,
    res: Dict[str, Any],
) -> None:
    try:
        await asyncio.to_thread(
            IctihatSearchHistoryRepository.insert,
            user_id=int(user_id),
            search_type=str(search_type or ""),
            query_text=(query or ""),
            filters=filters if isinstance(filters, dict) else None,
            top_k=int(top_k),
            result_count=len(_history_result_items(res)),
            return_items=_history_result_items(res),
        )
    except Exception:
        return


@router.get("/get_unique_daire_names", response_model=dict)
async def get_unique_daire_names(request: Request) -> Dict[str, Any]:
    """
    Returns cached court/chamber options across ALL institutions for dropdowns.
    Guarded by auth middleware (requires access token).
    """
    # ownership is per-user for other resources, but daire list is global; only require auth
    _ = int(getattr(request.state, "user_id"))
    return await get_cached_ictihat_daire_names()


@router.post("/search", response_model=dict)
async def search_ictihat(
    request: Request,
    query: Optional[str] = Body(default=None, embed=True),
    top_k: int = Body(default=5, embed=True),
    filters: Optional[Dict[str, Any]] = Body(default=None, embed=True),
    mode: str = Body(default="decisions", embed=True),
    chunk_k: Optional[int] = Body(default=None, embed=True),
    chat_id: Optional[int] = Body(default=None, embed=True),
) -> Dict[str, Any]:
    """
    API access to ictihat search. Supports:
    - semantic search via query text
    - direct citation lookup via filters (esas/karar fields) even if query is empty
    """
    user_id = int(getattr(request.state, "user_id"))
    cid = int(chat_id) if chat_id is not None else 0
    await ensure_sufficient_credits(user_id)
    # UI-facing search should return decision-level results (no chunk ids).
    mode_norm = (mode or "decisions").strip().lower()
    if mode_norm == "chunks":
        mode_norm = "decisions"

    # Search responses should stay lightweight; fetch the full document lazily
    # through `/ictihat/document/{document_id}` when the user opens a result.
    res = await _ictihat_search(
        user_id=user_id,
        chat_id=cid,
        query=(query or ""),
        top_k=int(top_k),
        filters=filters,
        mode=mode_norm,
        chunk_k=chunk_k,
        include_full_text=False,
    )
    if not res.get("ok"):
        _raise_result_error(res, fallback_reason="search_failed", log_extra={"user_id": int(user_id), "chat_id": int(cid)})
    await _save_search_history(
        user_id=int(user_id),
        search_type="semantic",
        query=(query or ""),
        filters=filters,
        top_k=int(top_k),
        res=res,
    )
    return res


@router.post("/keyword_search", response_model=dict)
async def keyword_search_ictihat(
    request: Request,
    query: Optional[str] = Body(default=None, embed=True),
    top_k: int = Body(default=5, embed=True),
    filters: Optional[Dict[str, Any]] = Body(default=None, embed=True),
    mode: str = Body(default="decisions", embed=True),
    chunk_k: Optional[int] = Body(default=None, embed=True),
    chat_id: Optional[int] = Body(default=None, embed=True),
) -> Dict[str, Any]:
    """
    API access to ictihat keyword search using Elasticsearch.
    """
    user_id = int(getattr(request.state, "user_id"))
    cid = int(chat_id) if chat_id is not None else 0
    await ensure_sufficient_credits(user_id)

    mode_norm = (mode or "decisions").strip().lower()
    if mode_norm == "chunks":
        mode_norm = "decisions"

    res = await _ictihat_keyword_search(
        user_id=user_id,
        chat_id=cid,
        query=(query or ""),
        top_k=int(top_k),
        filters=filters,
        mode=mode_norm,
        chunk_k=chunk_k,
        include_full_text=False,
    )
    if not res.get("ok"):
        _raise_result_error(res, fallback_reason="search_failed", log_extra={"user_id": int(user_id), "chat_id": int(cid)})
    await _save_search_history(
        user_id=int(user_id),
        search_type="keyword",
        query=(query or ""),
        filters=filters,
        top_k=int(top_k),
        res=res,
    )
    return res


@router.post("/agent_search", response_model=dict)
async def agent_search_ictihat(
    request: Request,
    query: Optional[str] = Body(default=None, embed=True),
    intent_text: Optional[str] = Body(default=None, embed=True),
    top_k: int = Body(default=20, embed=True),
    filters: Optional[Dict[str, Any]] = Body(default=None, embed=True),
    chat_id: Optional[int] = Body(default=None, embed=True),
) -> Dict[str, Any]:
    """
    LLM-powered iterated search for UI: returns compact `items[]` (no full texts).

    - Use for query expansion, dedupe, and better snippets/summaries.
    - Full decision text should be fetched via `/ictihat/document/{document_id}` when needed.
    """
    user_id = int(getattr(request.state, "user_id"))
    cid = int(chat_id) if chat_id is not None else 0
    await ensure_sufficient_credits(user_id)
    q = (intent_text or query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "empty_query"})

    # `top_k` here is an OPTIONAL EFFORT HINT for the LLM sub-agent, NOT a hard
    # post-filter cap (the agent is instructed to cap its own item list itself).
    # Only 5/10/15/20 are recognized — anything else means "no hint" and the
    # agent falls back to the default exhaustive protocol.
    try:
        effort_candidate = int(top_k) if top_k is not None else None
    except Exception:
        effort_candidate = None
    effort_top_k = effort_candidate if effort_candidate in (5, 10, 15, 20) else None

    res = await _ictihat_api_semantic_search(
        user_id=int(user_id),
        chat_id=int(cid),
        intent_text=q,
        filters=filters if isinstance(filters, dict) else None,
        effort_top_k=effort_top_k,
    )
    if not isinstance(res, dict) or not res.get("ok"):
        _raise_result_error(
            res if isinstance(res, dict) else {},
            fallback_reason="search_failed",
            log_extra={"user_id": int(user_id), "chat_id": int(cid), "route": "agent_search"},
        )
    # Persist the user's effort hint into history so re-runs can restore the chip,
    # falling back to the actual result count when no hint was provided.
    history_top_k = effort_top_k if effort_top_k is not None else max(1, len(_history_result_items(res)))
    await _save_search_history(
        user_id=int(user_id),
        search_type="ai",
        query=q,
        filters=filters,
        top_k=history_top_k,
        res=res,
    )
    return res


@router.get("/history", response_model=dict)
async def list_ictihat_history(
    request: Request,
    limit: int = 10,
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    items = await asyncio.to_thread(IctihatSearchHistoryRepository.list_recent, user_id=int(user_id), limit=max(1, min(int(limit), 50)))
    return {"ok": True, "items": items, "limit": max(1, min(int(limit), 50))}


@router.delete("/history/{history_id}", response_model=dict)
async def delete_ictihat_history(
    request: Request,
    history_id: int,
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    deleted = await asyncio.to_thread(IctihatSearchHistoryRepository.delete, user_id=int(user_id), history_id=int(history_id))
    return {"ok": True, "deleted": bool(deleted)}


@router.get("/document/{document_id}", response_model=dict)
async def get_ictihat_document(
    request: Request,
    document_id: int,
    chat_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Full stitched decision text fetch for UI.
    """
    user_id = int(getattr(request.state, "user_id"))
    cid = int(chat_id) if chat_id is not None else 0
    res = await _ictihat_get_document(
        user_id=user_id,
        chat_id=cid,
        document_id=int(document_id),
    )
    if not res.get("ok"):
        _raise_result_error(res, fallback_reason="not_found", log_extra={"user_id": int(user_id), "chat_id": int(cid)})
    return res

