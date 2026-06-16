from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict
from urllib.parse import quote

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...config import log_config
from ...docjson.docjson_text_renderer import docjson_to_text
from ...documents.generated_repository import GeneratedDocumentRepository
from ...petitions.udf_renderer import render_udf_from_text_with_style
from ...utils.pdf_renderer import PdfConversionError, convert_docx_bytes_to_pdf, render_pdf_from_docjson, render_pdf_from_text


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/generated-documents", tags=["generated-documents"])


def _libreoffice_logs_enabled() -> bool:
    try:
        return bool(log_config().libreoffice_logging_enabled)
    except Exception:
        return True


def _reportlab_logs_enabled() -> bool:
    try:
        return bool(log_config().reportlab_logging_enabled)
    except Exception:
        return True


def _ascii_filename_fallback(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "document.docx"
    safe = re.sub(r"[^\x20-\x7E]+", "_", name)
    safe = re.sub(r'[\\/:*?"<>|]+', "_", safe)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe or "document.docx"


def _content_disposition(filename: str) -> str:
    fallback = _ascii_filename_fallback(filename)
    fn_star = quote(filename or "", safe="")
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{fn_star}'


def _pdf_filename(filename: str) -> str:
    base = str(filename or "").strip() or "document.docx"
    if base.lower().endswith(".docx"):
        return base[:-5] + ".pdf"
    if base.lower().endswith(".pdf"):
        return base
    return base + ".pdf"


def _udf_filename(filename: str) -> str:
    base = str(filename or "").strip() or "document.docx"
    if base.lower().endswith(".docx"):
        return base[:-5] + ".udf"
    if base.lower().endswith(".udf"):
        return base
    return base + ".udf"


@router.post("/list", response_model=dict)
async def list_generated_documents(
    request: Request,
    chat_id: int = Body(..., embed=True),
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        rows = await asyncio.to_thread(
            GeneratedDocumentRepository.list_chat_documents,
            user_id=user_id,
            chat_id=int(chat_id),
            limit=50,
        )
        return {"ok": True, "chat_id": int(chat_id), "documents": rows}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.post("/preview", response_model=dict)
async def preview_generated_document(
    request: Request,
    chat_id: int = Body(..., embed=True),
    generated_document_id: int = Body(..., embed=True),
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        row = await asyncio.to_thread(
            GeneratedDocumentRepository.get_document,
            user_id=user_id,
            chat_id=int(chat_id),
            generated_document_id=int(generated_document_id),
        )
        raw_payload = row.get("source_payload_json")
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) and raw_payload.strip() else None
        preview_text, info = docjson_to_text(payload)
        return {
            "ok": True,
            "chat_id": int(chat_id),
            "document": {
                "generated_document_id": int(row["generated_document_id"]),
                "filename": row.get("filename"),
                "mime": row.get("mime"),
                "source_tool": row.get("source_tool"),
                "size_bytes": int(row.get("size_bytes") or 0),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "preview_text": preview_text,
                "has_table": bool((info or {}).get("has_table")),
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.get("/{generated_document_id}/download", response_model=None)
async def download_generated_document(
    request: Request,
    generated_document_id: int,
    chat_id: int,
) -> StreamingResponse:
    user_id = int(getattr(request.state, "user_id"))
    try:
        filename, mime, blob = await asyncio.to_thread(
            GeneratedDocumentRepository.get_document_blob,
            user_id=user_id,
            chat_id=int(chat_id),
            generated_document_id=int(generated_document_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})

    async def _iter():
        yield blob

    headers = {"Content-Disposition": _content_disposition(filename)}
    return StreamingResponse(_iter(), media_type=mime, headers=headers)


@router.get("/{generated_document_id}/download_pdf", response_model=None)
async def download_generated_document_pdf(
    request: Request,
    generated_document_id: int,
    chat_id: int,
) -> StreamingResponse:
    user_id = int(getattr(request.state, "user_id"))
    try:
        original_filename, _original_mime, docx_blob = await asyncio.to_thread(
            GeneratedDocumentRepository.get_document_blob,
            user_id=user_id,
            chat_id=int(chat_id),
            generated_document_id=int(generated_document_id),
        )
        row = await asyncio.to_thread(
            GeneratedDocumentRepository.get_document,
            user_id=user_id,
            chat_id=int(chat_id),
            generated_document_id=int(generated_document_id),
        )
        try:
            pdf_blob = await asyncio.to_thread(
                convert_docx_bytes_to_pdf,
                docx_blob,
                filename=original_filename,
            )
            if _libreoffice_logs_enabled():
                logger.info(
                    "Generated document PDF export converter=libreoffice generated_document_id=%s filename=%s",
                    int(generated_document_id),
                    original_filename,
                )
        except PdfConversionError as exc:
            if _reportlab_logs_enabled():
                logger.warning(
                    "Generated document PDF export fallback converter=reportlab generated_document_id=%s filename=%s reason=%s",
                    int(generated_document_id),
                    original_filename,
                    str(exc),
                )
            raw_payload = row.get("source_payload_json")
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) and raw_payload.strip() else None
            preview_text, _info = docjson_to_text(payload)
            if payload:
                pdf_blob = await asyncio.to_thread(render_pdf_from_docjson, payload)
                if _reportlab_logs_enabled():
                    logger.info(
                        "Generated document PDF export converter=reportlab generated_document_id=%s filename=%s mode=docjson",
                        int(generated_document_id),
                        original_filename,
                    )
            else:
                pdf_blob = await asyncio.to_thread(render_pdf_from_text, preview_text, prefer_monospace=False)
                if _reportlab_logs_enabled():
                    logger.info(
                        "Generated document PDF export converter=reportlab generated_document_id=%s filename=%s mode=text",
                        int(generated_document_id),
                        original_filename,
                    )
        filename = _pdf_filename(str(original_filename or row.get("filename") or "document.docx"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})

    async def _iter():
        yield pdf_blob

    headers = {"Content-Disposition": _content_disposition(filename)}
    return StreamingResponse(_iter(), media_type="application/pdf", headers=headers)


@router.get("/{generated_document_id}/download_udf", response_model=None)
async def download_generated_document_udf(
    request: Request,
    generated_document_id: int,
    chat_id: int,
) -> StreamingResponse:
    user_id = int(getattr(request.state, "user_id"))
    try:
        row = await asyncio.to_thread(
            GeneratedDocumentRepository.get_document,
            user_id=user_id,
            chat_id=int(chat_id),
            generated_document_id=int(generated_document_id),
        )
        raw_payload = row.get("source_payload_json")
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) and raw_payload.strip() else None
        preview_text, info = docjson_to_text(payload)
        has_table = bool((info or {}).get("has_table"))
        font_family = "Consolas" if has_table else "Times New Roman"
        udf_blob = await asyncio.to_thread(
            render_udf_from_text_with_style,
            preview_text,
            font_family=font_family,
        )
        filename = _udf_filename(str(row.get("filename") or "document.docx"))
        logger.info(
            "Generated document UDF export converter=udf_renderer generated_document_id=%s filename=%s has_table=%s font_family=%s",
            int(generated_document_id),
            row.get("filename"),
            has_table,
            font_family,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})

    async def _iter():
        yield udf_blob

    headers = {"Content-Disposition": _content_disposition(filename)}
    return StreamingResponse(_iter(), media_type="application/octet-stream", headers=headers)


@router.delete("/{generated_document_id}", response_model=dict)
async def delete_generated_document(
    request: Request,
    generated_document_id: int,
    chat_id: int,
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        await asyncio.to_thread(
            GeneratedDocumentRepository.delete_document,
            user_id=user_id,
            chat_id=int(chat_id),
            generated_document_id=int(generated_document_id),
        )
        return {"ok": True, "chat_id": int(chat_id), "generated_document_id": int(generated_document_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})
