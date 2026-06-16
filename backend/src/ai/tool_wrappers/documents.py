from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from ...documents.repository import DocumentRepository


async def doc_list(*, user_id: int, chat_id: int) -> Dict[str, Any]:
    try:
        docs = await asyncio.to_thread(DocumentRepository.list_chat_documents, chat_id=int(chat_id), user_id=int(user_id))
        return {"ok": True, "chat_id": int(chat_id), "documents": docs}
    except ValueError as exc:
        return {"ok": False, "reason": "chat_not_found", "detail": str(exc)}
    except Exception as exc:
        return {"ok": False, "reason": "error", "detail": str(exc)}


async def doc_get_pages(
    *,
    user_id: int,
    document_id: int,
    page_start: int,
    page_end: int,
    max_pages: int = 5,
) -> Dict[str, Any]:
    a = int(page_start)
    b = int(page_end)
    if a < 1:
        a = 1
    if b < a:
        b = a
    if (b - a + 1) > int(max_pages):
        b = a + int(max_pages) - 1
    try:
        pages = await asyncio.to_thread(
            DocumentRepository.get_pages,
            document_id=int(document_id),
            user_id=int(user_id),
            page_start=int(a),
            page_end=int(b),
        )
        return {
            "ok": True,
            "document_id": int(document_id),
            "page_start": int(a),
            "page_end": int(b),
            "pages": pages,
        }
    except ValueError as exc:
        return {"ok": False, "reason": "document_not_found", "detail": str(exc)}
    except Exception as exc:
        return {"ok": False, "reason": "error", "detail": str(exc)}


async def doc_get_page_map(
    *,
    user_id: int,
    document_id: int,
    page_start: int = 1,
    page_end: int = 50,
) -> Dict[str, Any]:
    a = max(1, int(page_start))
    b = max(a, int(page_end))
    b = min(b, a + 199)  # hard cap
    try:
        rows = await asyncio.to_thread(
            DocumentRepository.get_page_map,
            document_id=int(document_id),
            user_id=int(user_id),
            page_start=int(a),
            page_end=int(b),
        )
        return {
            "ok": True,
            "document_id": int(document_id),
            "page_start": int(a),
            "page_end": int(b),
            "page_map": rows,
        }
    except ValueError as exc:
        return {"ok": False, "reason": "document_not_found", "detail": str(exc)}
    except Exception as exc:
        return {"ok": False, "reason": "error", "detail": str(exc)}


