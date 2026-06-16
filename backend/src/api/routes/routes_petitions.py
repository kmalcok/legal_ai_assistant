from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...config import log_config
from ...petitions.pipeline import (
    PetitionPipelineError,
    apply_patch_operations,
    build_preview_response,
    build_summary_text,
    generate_petition_artifacts_from_output_json,
    parse_and_normalize_output_json,
)
from ...petitions.repository import PetitionRepository
from ...realtime.ws_manager import chat_ws_manager
from ...utils.pdf_renderer import PdfConversionError, convert_docx_bytes_to_pdf


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/petitions", tags=["petitions"])


def _libreoffice_logs_enabled() -> bool:
    try:
        return bool(log_config().libreoffice_logging_enabled)
    except Exception:
        return True


class PetitionPatchItem(BaseModel):
    field_path: str = Field(..., min_length=1)
    value: Any = None


class PetitionPatchRequest(BaseModel):
    chat_id: int = Field(..., gt=0)
    petition_id: int = Field(..., gt=0)
    version_id: Optional[int] = Field(default=None, gt=0)
    patches: List[PetitionPatchItem] = Field(..., min_length=1)


def _model_to_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(warnings=False)
        except TypeError:
            return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj) if isinstance(obj, dict) else {}


def _ascii_filename_fallback(name: str) -> str:
    """
    Starlette encodes headers as latin-1. Provide an ASCII-only fallback filename.
    """
    name = (name or "").strip()
    if not name:
        return "dilekce.docx"
    safe = re.sub(r"[^\x20-\x7E]+", "_", name)
    safe = re.sub(r'[\\\\/:*?"<>|]+', "_", safe)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe or "dilekce.docx"


def _content_disposition(filename: str) -> str:
    """
    RFC 5987 filename* for UTF-8 + ASCII fallback for compatibility.
    """
    fallback = _ascii_filename_fallback(filename)
    fn_star = quote(filename or "", safe="")
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{fn_star}'


@router.post("/list", response_model=dict)
async def list_petitions(request: Request, chat_id: int = Body(..., embed=True)) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        rows = await asyncio.to_thread(PetitionRepository.list_for_chat, user_id=user_id, chat_id=int(chat_id), limit=50)
        return {"ok": True, "chat_id": int(chat_id), "petitions": rows}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.delete("/{petition_id}", response_model=dict)
async def delete_petition(
    request: Request,
    petition_id: int,
    chat_id: int,
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        await asyncio.to_thread(
            PetitionRepository.delete_petition,
            user_id=user_id,
            chat_id=int(chat_id),
            petition_id=int(petition_id),
        )
        return {"ok": True, "chat_id": int(chat_id), "petition_id": int(petition_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.get("/{petition_id}/versions/{version_id}/download", response_model=None)
async def download_petition_docx(
    request: Request,
    petition_id: int,
    version_id: int,
    chat_id: int,
) -> StreamingResponse:
    """
    Download DOCX blob for a petition version.
    Requires chat_id to enforce ownership (chat-linked artifacts).
    """
    user_id = int(getattr(request.state, "user_id"))
    try:
        filename, mime, blob = await asyncio.to_thread(
            PetitionRepository.get_docx_blob,
            user_id=user_id,
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})

    async def _iter():
        yield blob

    headers = {"Content-Disposition": _content_disposition(filename)}
    return StreamingResponse(_iter(), media_type=mime, headers=headers)


@router.get("/{petition_id}/versions/{version_id}/download_udf", response_model=None)
async def download_petition_udf(
    request: Request,
    petition_id: int,
    version_id: int,
    chat_id: int,
) -> StreamingResponse:
    """
    Download UDF blob for a petition version (DB-backed).
    Requires chat_id to enforce ownership (chat-linked artifacts).
    """
    user_id = int(getattr(request.state, "user_id"))
    try:
        filename, mime, blob = await asyncio.to_thread(
            PetitionRepository.get_udf_blob,
            user_id=user_id,
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})

    async def _iter():
        yield blob

    headers = {"Content-Disposition": _content_disposition(filename)}
    return StreamingResponse(_iter(), media_type=mime, headers=headers)


@router.get("/{petition_id}/versions/{version_id}/download_pdf", response_model=None)
async def download_petition_pdf(
    request: Request,
    petition_id: int,
    version_id: int,
    chat_id: int,
) -> StreamingResponse:
    """
    Download PDF for a petition version via LibreOffice headless conversion.
    Requires chat_id to enforce ownership (chat-linked artifacts).
    """
    user_id = int(getattr(request.state, "user_id"))
    try:
        filename, _mime, blob = await asyncio.to_thread(
            PetitionRepository.get_docx_blob,
            user_id=user_id,
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id),
        )
        pdf_blob = await asyncio.to_thread(
            convert_docx_bytes_to_pdf,
            blob,
            filename=filename,
        )
        pdf_filename = filename[:-5] + ".pdf" if str(filename).lower().endswith(".docx") else f"{filename}.pdf"
        if _libreoffice_logs_enabled():
            logger.info(
                "Petition PDF export converter=libreoffice petition_id=%s version_id=%s filename=%s",
                int(petition_id),
                int(version_id),
                filename,
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except PdfConversionError as exc:
        if _libreoffice_logs_enabled():
            logger.warning(
                "Petition PDF export failed converter=libreoffice petition_id=%s version_id=%s reason=%s",
                int(petition_id),
                int(version_id),
                str(exc),
            )
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "pdf_convert_failed", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})

    async def _iter():
        yield pdf_blob

    headers = {"Content-Disposition": _content_disposition(pdf_filename)}
    return StreamingResponse(_iter(), media_type="application/pdf", headers=headers)


@router.post("/summary", response_model=dict)
async def petition_summary(
    request: Request,
    chat_id: int = Body(..., embed=True),
    petition_id: int = Body(..., embed=True),
    version_id: Optional[int] = Body(default=None, embed=True),
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        row = await asyncio.to_thread(
            PetitionRepository.get_version_summary,
            user_id=user_id,
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id) if version_id is not None else None,
        )
        # Do not return full output_json by default to clients (keep it light).
        return {
            "ok": True,
            "chat_id": int(chat_id),
            "petition_id": int(petition_id),
            "version": {
                "version_id": int(row["version_id"]),
                "version_no": int(row["version_no"]),
                "docx_filename": row.get("docx_filename"),
                "summary_text": row.get("summary_text"),
                "created_at": row.get("created_at"),
            },
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.post("/preview", response_model=dict)
async def petition_preview(
    request: Request,
    chat_id: int = Body(..., embed=True),
    petition_id: int = Body(..., embed=True),
    version_id: Optional[int] = Body(default=None, embed=True),
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        row = await asyncio.to_thread(
            PetitionRepository.get_version_document,
            user_id=user_id,
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id) if version_id is not None else None,
        )
        return {"ok": True, "chat_id": int(chat_id), "petition": build_preview_response(row)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except PetitionPipelineError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_preview", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


@router.post("/patch", response_model=dict)
async def patch_petition(request: Request, payload: PetitionPatchRequest) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    chat_id = int(payload.chat_id)
    petition_id = int(payload.petition_id)
    try:
        row = await asyncio.to_thread(
            PetitionRepository.get_version_document,
            user_id=user_id,
            chat_id=chat_id,
            petition_id=petition_id,
            version_id=int(payload.version_id) if payload.version_id is not None else None,
        )
        current_obj, _ = parse_and_normalize_output_json(str(row.get("output_json") or ""))
        updated_obj, updated_json = apply_patch_operations(
            current_obj,
            [_model_to_dict(item) for item in payload.patches],
        )
        artifacts = await generate_petition_artifacts_from_output_json(
            output_json=updated_json,
            preferred_filename=str(row.get("docx_filename") or ""),
        )
        version_id = int(row["version_id"])
        summary_text = build_summary_text(
            artifacts.output_obj,
            petition_id=petition_id,
            version_id=version_id,
            filename=artifacts.docx_filename,
        )
        await asyncio.to_thread(
            PetitionRepository.update_version,
            user_id=user_id,
            chat_id=chat_id,
            petition_id=petition_id,
            version_id=version_id,
            output_json=artifacts.output_json,
            summary_text=summary_text,
            docx_filename=artifacts.docx_filename,
            docx_blob=artifacts.docx_bytes,
            udf_filename=artifacts.udf_filename,
            udf_blob=artifacts.udf_bytes,
        )
        meta = updated_obj.get("meta") if isinstance(updated_obj.get("meta"), dict) else {}
        await asyncio.to_thread(
            PetitionRepository.set_petition_status,
            user_id=user_id,
            chat_id=chat_id,
            petition_id=petition_id,
            status="ready",
            error_message=None,
            document_type=(meta.get("document_type") or "").strip() or None,
            court=(meta.get("court") or "").strip() or None,
        )
        refreshed = await asyncio.to_thread(
            PetitionRepository.get_version_document,
            user_id=user_id,
            chat_id=chat_id,
            petition_id=petition_id,
            version_id=version_id,
        )
        try:
            await chat_ws_manager.publish(
                chat_id,
                {
                    "type": "petition_updated",
                    "chat_id": chat_id,
                    "petition_id": petition_id,
                    "version_id": version_id,
                    "filename": artifacts.docx_filename,
                },
            )
        except Exception:
            pass
        return {"ok": True, "chat_id": chat_id, "petition": build_preview_response(refreshed)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})
    except PetitionPipelineError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "invalid_patch", "detail": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "error", "detail": str(exc)})


