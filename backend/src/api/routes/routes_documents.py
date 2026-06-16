from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile

from ...documents.processor import MAX_DOCS_PER_CHAT, MAX_FILE_BYTES, process_document_async, store_upload_bytes
from ...documents.repository import DocumentRepository
from ...documents.utils import guess_ext


router = APIRouter(prefix="/documents", tags=["documents"])


def _file_type_from_filename(filename: str) -> str:
    ext = guess_ext(filename)
    if ext in {"pdf", "docx", "udf"}:
        return ext
    return "unknown"


@router.post("/upload", response_model=dict)
async def upload_documents(
    request: Request,
    chat_id: int = Form(...),
    files: List[UploadFile] = File(...),
) -> Dict[str, Any]:
    """
    Upload up to 5 documents per chat. Max 100MB per file.
    Returns document rows and starts async processing.
    """
    user_id = int(getattr(request.state, "user_id"))

    if not files:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "no_files"})
    if len(files) > MAX_DOCS_PER_CHAT:
        raise HTTPException(status_code=400, detail={"ok": False, "reason": "too_many_files"})

    try:
        existing = await asyncio.to_thread(DocumentRepository.count_chat_documents, chat_id=int(chat_id), user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "chat_not_found", "detail": str(exc)})

    # best-effort pre-check; duplicates may not increase count
    if existing + len(files) > MAX_DOCS_PER_CHAT:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "reason": "chat_doc_limit",
                "limit": MAX_DOCS_PER_CHAT,
                "current": existing,
            },
        )

    created_docs: list[Dict[str, Any]] = []

    for f in files:
        fn = f.filename or "file"
        mime = getattr(f, "content_type", None)

        data = await f.read()
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"ok": False, "reason": "file_too_large", "max_bytes": MAX_FILE_BYTES, "filename": fn},
            )

        stored = store_upload_bytes(original_filename=fn, content=data)
        file_type = _file_type_from_filename(stored.filename)

        # Create row (or reuse existing for same sha256)
        doc_id: Optional[int] = None
        try:
            doc_id = await asyncio.to_thread(
                DocumentRepository.create_document,
                user_id=user_id,
                filename=stored.filename,
                file_type=file_type,
                mime_type=mime,
                size_bytes=stored.size_bytes,
                sha256=stored.sha256,
                storage_path=stored.storage_path,
                status="uploaded",
                raw_blob=data,
            )
        except Exception:
            # likely duplicate (uq_docs_user_sha256); reuse existing doc row
            existing_doc = await asyncio.to_thread(
                DocumentRepository.get_document_by_sha256, user_id=user_id, sha256=stored.sha256
            )
            if existing_doc:
                doc_id = int(existing_doc["document_id"])
                # Ensure raw_blob exists
                try:
                    await asyncio.to_thread(
                        DocumentRepository.set_raw_blob,
                        document_id=int(doc_id),
                        user_id=user_id,
                        raw_blob=data,
                    )
                except Exception:
                    pass
            else:
                raise

        # Attach to chat (idempotent)
        try:
            # enforce limit strictly at attach time too
            cur = await asyncio.to_thread(DocumentRepository.count_chat_documents, chat_id=int(chat_id), user_id=user_id)
            if cur >= MAX_DOCS_PER_CHAT:
                raise HTTPException(
                    status_code=400,
                    detail={"ok": False, "reason": "chat_doc_limit", "limit": MAX_DOCS_PER_CHAT, "current": cur},
                )
            await asyncio.to_thread(
                DocumentRepository.attach_document_to_chat, chat_id=int(chat_id), user_id=user_id, document_id=int(doc_id)
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})

        # Start processing in background (idempotent-ish; processor overwrites pages)
        doc_row = await asyncio.to_thread(DocumentRepository.get_document, document_id=int(doc_id), user_id=user_id)
        if doc_row and doc_row.get("status") in {"uploaded", "failed"}:
            asyncio.create_task(
                process_document_async(
                    user_id=user_id,
                    document_id=int(doc_id),
                )
            )

        created_docs.append(doc_row or {"document_id": int(doc_id), "filename": stored.filename, "status": "uploaded"})

    return {"ok": True, "chat_id": int(chat_id), "documents": created_docs}


@router.get("/{document_id}", response_model=dict)
async def get_document_status(request: Request, document_id: int) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    doc = await asyncio.to_thread(DocumentRepository.get_document, document_id=int(document_id), user_id=user_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "document_not_found"})
    return {"ok": True, "document": doc}


@router.post("/list", response_model=dict)
async def list_chat_documents(
    request: Request,
    chat_id: int = Body(..., embed=True),
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        docs = await asyncio.to_thread(DocumentRepository.list_chat_documents, chat_id=int(chat_id), user_id=user_id)
        return {"ok": True, "chat_id": int(chat_id), "documents": docs}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "chat_not_found", "detail": str(exc)})


@router.post("/detach", response_model=dict)
async def detach_document(
    request: Request,
    chat_id: int = Body(..., embed=True),
    document_id: int = Body(..., embed=True),
) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        await asyncio.to_thread(
            DocumentRepository.detach_document_from_chat,
            chat_id=int(chat_id),
            user_id=user_id,
            document_id=int(document_id),
        )
        return {"ok": True, "chat_id": int(chat_id), "document_id": int(document_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found", "detail": str(exc)})


