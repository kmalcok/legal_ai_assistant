from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..data.db_chat_repository import ChatRepository
from ..db import core_db


@dataclass(frozen=True)
class DocumentRow:
    document_id: int
    user_id: int
    filename: str
    file_type: str
    size_bytes: int
    sha256: str
    storage_path: str
    status: str
    error_message: Optional[str]
    page_count: int
    short_summary: Optional[str]


class DocumentRepository:
    """
    Storage/retrieval for user-uploaded documents and their page-level text.
    """

    PAGE_INSERT_BATCH_SIZE = 100

    @staticmethod
    def create_document(
        *,
        user_id: int,
        filename: str,
        file_type: str,
        mime_type: Optional[str],
        size_bytes: int,
        sha256: str,
        storage_path: str,
        status: str = "uploaded",
        raw_blob: Optional[bytes] = None,
    ) -> int:
        ChatRepository.ensure_user_exists(int(user_id))
        with core_db() as conn:
            cur = conn.cursor()
            # Newer schema includes raw_blob; older installs ignore this column until migrated.
            try:
                cur.execute(
                    """
                    INSERT INTO documents
                      (user_id, filename, file_type, mime_type, size_bytes, sha256, storage_path, status, raw_blob)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        int(user_id),
                        filename,
                        file_type,
                        mime_type,
                        int(size_bytes),
                        sha256,
                        storage_path,
                        status,
                        raw_blob,
                    ),
                )
            except Exception:
                # Fallback for older schema (no raw_blob)
                cur.execute(
                    """
                    INSERT INTO documents
                      (user_id, filename, file_type, mime_type, size_bytes, sha256, storage_path, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        int(user_id),
                        filename,
                        file_type,
                        mime_type,
                        int(size_bytes),
                        sha256,
                        storage_path,
                        status,
                    ),
                )
            conn.commit()
            return int(cur.lastrowid)

    @staticmethod
    def set_raw_blob(*, document_id: int, user_id: int, raw_blob: bytes) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE documents
                SET raw_blob=%s
                WHERE document_id=%s AND user_id=%s
                """,
                (raw_blob, int(document_id), int(user_id)),
            )
            conn.commit()

    @staticmethod
    def get_raw_blob(*, document_id: int, user_id: int) -> bytes:
        doc = DocumentRepository.get_document(document_id=int(document_id), user_id=int(user_id))
        if doc is None:
            raise ValueError("Document not found for this user.")
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT raw_blob FROM documents WHERE document_id=%s AND user_id=%s",
                (int(document_id), int(user_id)),
            )
            row = cur.fetchone()
            b = row[0] if row else None
            if b is None:
                raise ValueError("raw_blob_missing")
            return bytes(b)

    @staticmethod
    def get_document_by_sha256(*, user_id: int, sha256: str) -> Optional[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT document_id, user_id, filename, file_type, mime_type, size_bytes, sha256,
                       storage_path, status, error_message, page_count, short_summary, created_at, updated_at
                FROM documents
                WHERE user_id=%s AND sha256=%s
                """,
                (int(user_id), sha256),
            )
            row = cur.fetchone()
            return row if isinstance(row, dict) else None

    @staticmethod
    def get_document(*, document_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT document_id, user_id, filename, file_type, mime_type, size_bytes, sha256,
                       storage_path, status, error_message, page_count, short_summary, created_at, updated_at
                FROM documents
                WHERE document_id=%s AND user_id=%s
                """,
                (int(document_id), int(user_id)),
            )
            row = cur.fetchone()
            return row if isinstance(row, dict) else None

    @staticmethod
    def list_chat_documents(*, chat_id: int, user_id: int) -> List[Dict[str, Any]]:
        # Ownership check
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT d.document_id, d.filename, d.file_type, d.size_bytes, d.status, d.error_message,
                       d.page_count, d.short_summary, d.created_at
                FROM chat_documents cd
                JOIN documents d ON d.document_id = cd.document_id
                WHERE cd.chat_id=%s AND d.user_id=%s
                ORDER BY cd.created_at DESC
                """,
                (int(chat_id), int(user_id)),
            )
            return list(cur.fetchall() or [])

    @staticmethod
    def count_chat_documents(*, chat_id: int, user_id: int) -> int:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*)
                FROM chat_documents cd
                JOIN documents d ON d.document_id = cd.document_id
                WHERE cd.chat_id=%s AND d.user_id=%s
                """,
                (int(chat_id), int(user_id)),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    @staticmethod
    def attach_document_to_chat(*, chat_id: int, user_id: int, document_id: int) -> None:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")
        doc = DocumentRepository.get_document(document_id=int(document_id), user_id=int(user_id))
        if doc is None:
            raise ValueError("Document not found for this user.")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT IGNORE INTO chat_documents (chat_id, document_id)
                VALUES (%s,%s)
                """,
                (int(chat_id), int(document_id)),
            )
            conn.commit()

    @staticmethod
    def detach_document_from_chat(*, chat_id: int, user_id: int, document_id: int) -> None:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE cd
                FROM chat_documents cd
                JOIN documents d ON d.document_id = cd.document_id
                WHERE cd.chat_id=%s AND cd.document_id=%s AND d.user_id=%s
                """,
                (int(chat_id), int(document_id), int(user_id)),
            )
            conn.commit()

    @staticmethod
    def set_status(*, document_id: int, user_id: int, status: str, error_message: Optional[str] = None) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE documents
                SET status=%s, error_message=%s
                WHERE document_id=%s AND user_id=%s
                """,
                (status, error_message, int(document_id), int(user_id)),
            )
            conn.commit()

    @staticmethod
    def replace_pages(
        *,
        document_id: int,
        user_id: int,
        pages: List[Dict[str, Any]],
        page_count: int,
        short_summary: Optional[str],
    ) -> None:
        # pages: [{page_no:int, text:str, page_summary:str|None}]
        with core_db() as conn:
            cur = conn.cursor()
            # clear old pages
            cur.execute(
                """
                DELETE dp
                FROM document_pages dp
                JOIN documents d ON d.document_id = dp.document_id
                WHERE dp.document_id=%s AND d.user_id=%s
                """,
                (int(document_id), int(user_id)),
            )

            if pages:
                payload = [
                    (int(document_id), int(p["page_no"]), p["text"], p.get("page_summary"))
                    for p in pages
                ]
                batch_size = max(1, int(DocumentRepository.PAGE_INSERT_BATCH_SIZE))
                for start in range(0, len(payload), batch_size):
                    cur.executemany(
                        """
                        INSERT INTO document_pages (document_id, page_no, text, page_summary)
                        VALUES (%s,%s,%s,%s)
                        """,
                        payload[start : start + batch_size],
                    )

            cur.execute(
                """
                UPDATE documents
                SET page_count=%s, short_summary=%s
                WHERE document_id=%s AND user_id=%s
                """,
                (int(page_count), short_summary, int(document_id), int(user_id)),
            )
            conn.commit()

    @staticmethod
    def get_pages(
        *,
        document_id: int,
        user_id: int,
        page_start: int,
        page_end: int,
    ) -> List[Dict[str, Any]]:
        doc = DocumentRepository.get_document(document_id=int(document_id), user_id=int(user_id))
        if doc is None:
            raise ValueError("Document not found for this user.")

        a = max(1, int(page_start))
        b = max(a, int(page_end))
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT page_no, text, page_summary
                FROM document_pages
                WHERE document_id=%s AND page_no BETWEEN %s AND %s
                ORDER BY page_no ASC
                """,
                (int(document_id), int(a), int(b)),
            )
            return list(cur.fetchall() or [])

    @staticmethod
    def get_page_map(
        *,
        document_id: int,
        user_id: int,
        page_start: int = 1,
        page_end: int = 200,
    ) -> List[Dict[str, Any]]:
        doc = DocumentRepository.get_document(document_id=int(document_id), user_id=int(user_id))
        if doc is None:
            raise ValueError("Document not found for this user.")
        a = max(1, int(page_start))
        b = max(a, int(page_end))
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT page_no, page_summary
                FROM document_pages
                WHERE document_id=%s AND page_no BETWEEN %s AND %s
                ORDER BY page_no ASC
                """,
                (int(document_id), int(a), int(b)),
            )
            return list(cur.fetchall() or [])



