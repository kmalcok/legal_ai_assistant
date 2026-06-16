from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from ...docjson.docjson_renderer import render_docjson_to_docx
from ...documents.generated_repository import GeneratedDocumentRepository
from ...realtime.ws_manager import chat_ws_manager
from ...utils.ephemeral_store import ephemeral_files


async def word_render_docx(
    *,
    user_id: int,
    chat_id: int,
    doc_json: str,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Render a DOCX from a DOC-JSON v1 payload (full spec or append-event list).
    Stores the bytes ephemerally (Redis/in-memory TTL) and returns a download token.
    """
    try:
        payload = json.loads(doc_json) if isinstance(doc_json, str) else doc_json
    except Exception as exc:
        await chat_ws_manager.publish(int(chat_id), {"type": "word_failed", "chat_id": int(chat_id), "error": "invalid_json"})
        return {"ok": False, "reason": "invalid_json", "detail": str(exc)}

    try:
        rendered = await asyncio.to_thread(render_docjson_to_docx, payload, filename=filename)
    except Exception as exc:
        await chat_ws_manager.publish(int(chat_id), {"type": "word_failed", "chat_id": int(chat_id), "error": str(exc)})
        return {"ok": False, "reason": "render_failed", "detail": str(exc)}

    try:
        generated_document_id = await asyncio.to_thread(
            GeneratedDocumentRepository.create_document,
            user_id=int(user_id),
            chat_id=int(chat_id),
            filename=rendered.filename,
            mime=rendered.mime,
            content_bytes=rendered.content,
            source_tool="word_render_docx",
            source_payload_json=json.dumps(payload, ensure_ascii=False),
        )
    except Exception as exc:
        await chat_ws_manager.publish(int(chat_id), {"type": "word_failed", "chat_id": int(chat_id), "error": str(exc)})
        return {"ok": False, "reason": "persist_failed", "detail": str(exc)}

    # NOTE: Ephemeral variant generation (UDF/PDF) was intentionally removed.
    # We keep the old code commented out for possible future product experiments.
    #
    # Previously:
    # - Build variants (udf/pdf) and store under the same token in Redis.
    #
    # variants = {}
    # try:
    #     def _build_variants_sync() -> Dict[str, Dict[str, Any]]:
    #         txt, info = docjson_to_text(payload)
    #         has_table = bool((info or {}).get("has_table"))
    #         base = (rendered.filename or "document.docx").strip()
    #         if base.lower().endswith(".docx"):
    #             base = base[:-5]
    #         base = base or "document"
    #         font_family = "Consolas" if has_table else "Times New Roman"
    #         return {
    #             "udf": {"filename": base + ".udf", "mime": "application/octet-stream", "content_bytes": render_udf_from_text_with_style(txt, font_family=font_family)},
    #             "pdf": {"filename": base + ".pdf", "mime": "application/pdf", "content_bytes": render_pdf_from_text(txt, prefer_monospace=has_table)},
    #         }
    #     variants = await asyncio.to_thread(_build_variants_sync)
    # except Exception:
    #     variants = {}

    # Store ephemerally with fixed 10-minute TTL.
    ttl_seconds = 600
    f = await ephemeral_files.put(
        chat_id=int(chat_id),
        user_id=int(user_id),
        filename=rendered.filename,
        mime=rendered.mime,
        content_bytes=rendered.content,
        ttl_seconds=int(ttl_seconds),
    )

    await chat_ws_manager.publish(
        int(chat_id),
        {
            "type": "word_ready",
            "chat_id": int(chat_id),
            "generated_document_id": int(generated_document_id),
            "token": f.token,
            "filename": f.filename,
            "ttl_seconds": int(ttl_seconds),
        },
    )

    return {
        "ok": True,
        "chat_id": int(chat_id),
        "generated_document_id": int(generated_document_id),
        "filename": f.filename,
        "token": f.token,
        "download_hint": "DOCX hazır. İndirme işlemi istemci tarafından websocket 'word_ready' olayı ile yapılır.",
    }


