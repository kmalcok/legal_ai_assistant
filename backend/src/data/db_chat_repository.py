from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..db import core_db
from ..utils.ictihat_format import daire_label, normalize_kurum


@dataclass(frozen=True)
class ChatRow:
    chat_id: int
    user_id: int
    title: Optional[str]
    first_message: Optional[str]
    last_sum: Optional[str]
    archived: bool


class ChatRepository:
    """
    Persistent chat/message storage in the application database.

    This repository is intentionally small and synchronous; callers can wrap
    it in asyncio.to_thread(...) if needed.
    """

    @staticmethod
    def ensure_user_exists(user_id: int) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT user_id FROM users WHERE user_id=%s", (int(user_id),))
            row = cur.fetchone()
            if row:
                return
            # Insert minimal user row (for system-created users). Username/password_hash must exist,
            # so we create a placeholder that must be updated later by registration flow.
            cur.execute(
                "INSERT INTO users (user_id, username, password_hash) VALUES (%s, %s, %s)",
                (int(user_id), f"user{int(user_id)}", ""),
            )
            conn.commit()

    @staticmethod
    def create_chat(user_id: int, title: Optional[str] = None) -> int:
        ChatRepository.ensure_user_exists(user_id)
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO chats (user_id, title) VALUES (%s, %s)", (int(user_id), title))
            conn.commit()
            return int(cur.lastrowid)

    @staticmethod
    def get_chat(chat_id: int, user_id: int) -> Optional[ChatRow]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT chat_id, user_id, title, first_message, last_sum, archived
                FROM chats
                WHERE chat_id=%s AND user_id=%s
                """,
                (int(chat_id), int(user_id)),
            )
            row = cur.fetchone()
            if not row:
                return None
            return ChatRow(
                chat_id=int(row["chat_id"]),
                user_id=int(row["user_id"]),
                title=row.get("title"),
                first_message=row.get("first_message"),
                last_sum=row.get("last_sum"),
                archived=bool(row.get("archived")),
            )

    @staticmethod
    def list_chats(user_id: int, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT chat_id, user_id, title, first_message, last_sum, archived, created_at, updated_at
                FROM chats
                WHERE user_id=%s AND archived=0
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (int(user_id), int(limit), int(offset)),
            )
            return list(cur.fetchall() or [])

    @staticmethod
    def append_message(chat_id: int, user_id: int, role: str, message: str, reasoning: str = "") -> int:
        # Ownership check
        chat = ChatRepository.get_chat(chat_id=chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_messages (chat_id, role, message, reasoning) VALUES (%s, %s, %s, %s)",
                (int(chat_id), role, message, reasoning or ""),
            )
            # Persist first user message for previews
            if role == "user" and not chat.first_message:
                cur.execute(
                    "UPDATE chats SET first_message=%s WHERE chat_id=%s",
                    (message, int(chat_id)),
                )
            conn.commit()
            return int(cur.lastrowid)

    @staticmethod
    def get_recent_messages(chat_id: int, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        chat = ChatRepository.get_chat(chat_id=chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT id, role, message, reasoning, created_at
                FROM chat_messages
                WHERE chat_id=%s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (int(chat_id), int(limit)),
            )
            rows = list(cur.fetchall() or [])
            rows.reverse()
            return rows

    @staticmethod
    def set_message_ictihat(*, message_id: int, ictihat_items: List[Dict[str, Any]]) -> None:
        """
        Persist ictihat items for a specific chat_messages.id.

        Item shape (stored as JSON array):
        - document_id
        - kurum
        - daire
        - esas_yil, esas_sira
        - karar_yil, karar_sira
        - karar_tarihi

        NOTE: Table column is named `chat_id` but actually stores message_id (FK -> chat_messages.id).
        """
        mid = int(message_id)
        cleaned: list[dict] = []
        seen: set[int] = set()
        for it in ictihat_items or []:
            if not isinstance(it, dict):
                continue
            try:
                did = int(it.get("document_id"))
            except Exception:
                continue
            if did in seen:
                continue
            seen.add(did)
            try:
                kurum = normalize_kurum(it.get("kurum"), daire=it.get("daire"))
                daire = (str(it.get("daire") or "").strip() or None)
                cleaned.append(
                    {
                        "document_id": did,
                        "kurum": kurum,
                        "daire": daire,
                        "daire_label": str(it.get("daire_label") or "").strip() or daire_label(kurum=kurum, daire=daire),
                        "esas_yil": int(it.get("esas_yil")) if it.get("esas_yil") is not None else None,
                        "esas_sira": int(it.get("esas_sira")) if it.get("esas_sira") is not None else None,
                        "karar_yil": int(it.get("karar_yil")) if it.get("karar_yil") is not None else None,
                        "karar_sira": int(it.get("karar_sira")) if it.get("karar_sira") is not None else None,
                        "karar_tarihi": (str(it.get("karar_tarihi") or "").strip() or None),
                    }
                )
            except Exception:
                # If any field conversion fails, still keep document_id only.
                cleaned.append({"document_id": did})

        payload = json.dumps(cleaned, ensure_ascii=False)

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO chat_message_ictihat (chat_id, ictihat_list_json)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE ictihat_list_json = VALUES(ictihat_list_json)
                """,
                (mid, payload),
            )
            conn.commit()

    @staticmethod
    def get_messages_ictihat_map(*, message_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Bulk load ictihat lists for message ids. Returns {message_id: [item, ...]}.
        """
        ids: list[int] = []
        for x in message_ids or []:
            try:
                ids.append(int(x))
            except Exception:
                continue
        ids = list(dict.fromkeys(ids))
        if not ids:
            return {}

        placeholders = ",".join(["%s"] * len(ids))
        sql = f"""
            SELECT chat_id, ictihat_list_json
            FROM chat_message_ictihat
            WHERE chat_id IN ({placeholders})
        """
        out: Dict[int, List[Dict[str, Any]]] = {}
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, tuple(ids))
            rows = list(cur.fetchall() or [])
        for r in rows:
            try:
                mid = int(r.get("chat_id"))
            except Exception:
                continue
            raw = r.get("ictihat_list_json")
            try:
                arr = json.loads(raw) if isinstance(raw, str) else []
            except Exception:
                arr = []
            items: list[dict] = []
            if isinstance(arr, list):
                for it in arr[:50]:
                    if not isinstance(it, dict):
                        continue
                    items.append(it)
            out[mid] = items
        return out

    @staticmethod
    def get_last_assistant_message(chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Return the most recent assistant message for a chat (ownership-checked).
        """
        chat = ChatRepository.get_chat(chat_id=chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found for this user.")
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT id, role, message, reasoning, created_at
                FROM chat_messages
                WHERE chat_id=%s AND role='assistant'
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(chat_id),),
            )
            return cur.fetchone()

    @staticmethod
    def update_last_sum(chat_id: int, user_id: int, summary: str) -> None:
        chat = ChatRepository.get_chat(chat_id=chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE chats SET last_sum=%s WHERE chat_id=%s", (summary, int(chat_id)))
            conn.commit()

    @staticmethod
    def archive_chat(chat_id: int, user_id: int) -> None:
        chat = ChatRepository.get_chat(chat_id=chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found for this user.")
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE chats SET archived=1 WHERE chat_id=%s", (int(chat_id),))
            conn.commit()

    @staticmethod
    def hard_delete_chat(*, chat_id: int, user_id: int, delete_documents: bool = True) -> Dict[str, Any]:
        """
        Hard delete a chat and all related data:
          - chat row (cascades chat_messages, chat_documents, petitions, petition_versions)
          - user_usages rows for this chat
          - optionally delete documents attached to the chat IF they are not attached to any other chat
            for the same user (prevents deleting shared uploads).
        """
        chat = ChatRepository.get_chat(chat_id=int(chat_id), user_id=int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        deleted_docs: list[int] = []
        candidate_doc_ids: list[int] = []
        deleted_usages = 0

        with core_db() as conn:
            cur = conn.cursor()

            # Capture candidate documents BEFORE deleting chat (ownership enforced via documents.user_id)
            if delete_documents:
                cur.execute(
                    """
                    SELECT cd.document_id
                    FROM chat_documents cd
                    JOIN documents d ON d.document_id = cd.document_id
                    WHERE cd.chat_id=%s AND d.user_id=%s
                    """,
                    (int(chat_id), int(user_id)),
                )
                candidate_doc_ids = [int(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None]

            # Remove usage rows linked to this chat (privacy)
            cur.execute("DELETE FROM user_usages WHERE user_id=%s AND chat_id=%s", (int(user_id), int(chat_id)))
            deleted_usages = int(cur.rowcount or 0)
            # user_tool_usages kaldirildi - artik tum kullanim token bazinda takip edilir.

            # Delete the chat (cascades: messages, chat_documents, petitions, petition_versions)
            cur.execute("DELETE FROM chats WHERE chat_id=%s AND user_id=%s", (int(chat_id), int(user_id)))
            if int(cur.rowcount or 0) != 1:
                raise ValueError("Chat not found for this user.")

            # Optionally delete orphan docs (only if no other chat references remain)
            if delete_documents and candidate_doc_ids:
                for doc_id in candidate_doc_ids:
                    # If the document is still attached to ANY chat (after cascade), keep it.
                    cur.execute(
                        """
                        SELECT COUNT(*)
                        FROM chat_documents cd
                        JOIN chats c ON c.chat_id = cd.chat_id
                        WHERE cd.document_id=%s AND c.user_id=%s
                        """,
                        (int(doc_id), int(user_id)),
                    )
                    row = cur.fetchone()
                    still_used = int(row[0]) if row else 0
                    if still_used > 0:
                        continue
                    # Safe to delete. This cascades document_pages + chat_documents (if any).
                    cur.execute("DELETE FROM documents WHERE document_id=%s AND user_id=%s", (int(doc_id), int(user_id)))
                    if int(cur.rowcount or 0) > 0:
                        deleted_docs.append(int(doc_id))

            conn.commit()

        return {
            "chat_id": int(chat_id),
            "deleted": True,
            "deleted_user_usages": int(deleted_usages),
            "deleted_document_ids": deleted_docs,
            "deleted_document_count": int(len(deleted_docs)),
        }


