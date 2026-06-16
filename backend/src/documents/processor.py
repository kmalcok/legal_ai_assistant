from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .extractors import DocumentExtractError, extract_document
from .repository import DocumentRepository
from .utils import first_sentence, join_lines, normalize_text, safe_filename, sha256_bytes, shorten


MAX_FILE_BYTES = 100 * 1024 * 1024  # 100MB
MAX_DOCS_PER_CHAT = 5
DEFAULT_PSEUDO_PAGE_CHARS = 5000


@dataclass(frozen=True)
class StoredUpload:
    storage_path: str
    size_bytes: int
    sha256: str
    filename: str


def store_upload_bytes(*, original_filename: str, content: bytes) -> StoredUpload:
    if not isinstance(content, (bytes, bytearray)):
        raise ValueError("content must be bytes")
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("file_too_large")

    fn = safe_filename(original_filename)
    digest = sha256_bytes(bytes(content))

    # DB storage only: we don't write to disk; storage_path is informational only.
    storage_path = f"db://{digest}_{fn}"

    return StoredUpload(storage_path=storage_path, size_bytes=len(content), sha256=digest, filename=fn)


def _build_doc_short_summary(page_summaries: list[str]) -> str:
    # Heuristic: join first ~20 page summaries within a char budget.
    return join_lines(page_summaries, max_chars=2500)


def _process_document_sync(*, user_id: int, document_id: int) -> None:
    """
    CPU-heavy extraction and large DB writes stay off the event loop.
    """
    DocumentRepository.set_status(document_id=document_id, user_id=user_id, status="processing", error_message=None)
    doc = DocumentRepository.get_document(document_id=int(document_id), user_id=int(user_id))
    if not doc:
        raise ValueError("document_not_found")

    filename = str(doc.get("filename") or "file")
    blob = DocumentRepository.get_raw_blob(document_id=int(document_id), user_id=int(user_id))

    extracted = extract_document(blob, filename, pseudo_page_chars=DEFAULT_PSEUDO_PAGE_CHARS)

    page_rows: list[Dict[str, Any]] = []
    page_summaries: list[str] = []
    for p in extracted.pages:
        txt = normalize_text(p.text)
        summ = first_sentence(txt) if txt else ""
        if not summ:
            summ = shorten(txt, 180) if txt else ""
        page_summaries.append(f"Sayfa {p.page_no}: {summ}".strip())
        page_rows.append({"page_no": int(p.page_no), "text": txt, "page_summary": summ or None})

    short_summary = _build_doc_short_summary(page_summaries)
    if not short_summary:
        short_summary = shorten("\n".join(p.text for p in extracted.pages if p.text), 1200)

    DocumentRepository.replace_pages(
        document_id=document_id,
        user_id=user_id,
        pages=page_rows,
        page_count=len(extracted.pages),
        short_summary=short_summary or None,
    )
    DocumentRepository.set_status(document_id=document_id, user_id=user_id, status="ready", error_message=None)


async def process_document_async(*, user_id: int, document_id: int) -> None:
    """
    Background processor: run extraction and page writes in a worker thread.
    """
    try:
        await asyncio.to_thread(_process_document_sync, user_id=int(user_id), document_id=int(document_id))
    except DocumentExtractError as exc:
        await asyncio.to_thread(
            DocumentRepository.set_status,
            document_id=int(document_id),
            user_id=int(user_id),
            status="failed",
            error_message=str(exc),
        )
    except Exception as exc:
        await asyncio.to_thread(
            DocumentRepository.set_status,
            document_id=int(document_id),
            user_id=int(user_id),
            status="failed",
            error_message=str(exc),
        )


