from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..data.db_chat_repository import ChatRepository
from ..db import core_db


class GeneratedDocumentRepository:
    """
    Storage/retrieval for agent-generated DOCX artifacts persisted per chat.
    """

    @staticmethod
    def create_document(
        *,
        user_id: int,
        chat_id: int,
        filename: str,
        mime: str,
        content_bytes: bytes,
        source_tool: str = "word_render_docx",
        source_payload_json: str | None = None,
    ) -> int:
        ChatRepository.ensure_user_exists(int(user_id))
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO generated_documents
                  (chat_id, user_id, source_tool, filename, mime, size_bytes, source_payload_json, docx_blob)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    int(chat_id),
                    int(user_id),
                    str(source_tool or "word_render_docx"),
                    filename,
                    mime,
                    int(len(content_bytes or b"")),
                    source_payload_json,
                    content_bytes,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    @staticmethod
    def list_chat_documents(*, user_id: int, chat_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        lim = max(1, min(int(limit), 100))
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT
                  generated_document_id,
                  chat_id,
                  user_id,
                  source_tool,
                  filename,
                  mime,
                  size_bytes,
                  created_at,
                  updated_at
                FROM generated_documents
                WHERE chat_id=%s AND user_id=%s
                ORDER BY created_at DESC, generated_document_id DESC
                LIMIT %s
                """,
                (int(chat_id), int(user_id), int(lim)),
            )
            return list(cur.fetchall() or [])

    @staticmethod
    def get_document(*, user_id: int, chat_id: int, generated_document_id: int) -> Dict[str, Any]:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT
                  generated_document_id,
                  chat_id,
                  user_id,
                  source_tool,
                  filename,
                  mime,
                  size_bytes,
                  source_payload_json,
                  created_at,
                  updated_at
                FROM generated_documents
                WHERE generated_document_id=%s AND chat_id=%s AND user_id=%s
                """,
                (int(generated_document_id), int(chat_id), int(user_id)),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Generated document not found.")
            return dict(row)

    @staticmethod
    def get_document_blob(*, user_id: int, chat_id: int, generated_document_id: int) -> Tuple[str, str, bytes]:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT filename, mime, docx_blob
                FROM generated_documents
                WHERE generated_document_id=%s AND chat_id=%s AND user_id=%s
                """,
                (int(generated_document_id), int(chat_id), int(user_id)),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Generated document not found.")
            blob = row.get("docx_blob")
            if blob is None:
                raise ValueError("Generated document blob not found.")
            return str(row.get("filename") or "document.docx"), str(row.get("mime") or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"), bytes(blob)

    @staticmethod
    def delete_document(*, user_id: int, chat_id: int, generated_document_id: int) -> None:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM generated_documents
                WHERE generated_document_id=%s AND chat_id=%s AND user_id=%s
                """,
                (int(generated_document_id), int(chat_id), int(user_id)),
            )
            if int(cur.rowcount or 0) != 1:
                raise ValueError("Generated document not found.")
            conn.commit()
