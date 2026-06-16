from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..data.db_chat_repository import ChatRepository
from ..db import core_db


class PetitionRepository:
    @staticmethod
    def _get_owned_version_row(
        *, user_id: int, chat_id: int, petition_id: int, version_id: Optional[int] = None
    ) -> Dict[str, Any]:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            if version_id is not None:
                cur.execute(
                    """
                    SELECT
                      p.petition_id,
                      p.chat_id,
                      p.user_id,
                      p.status,
                      p.document_type,
                      p.court,
                      p.updated_at AS petition_updated_at,
                      v.version_id,
                      v.version_no,
                      v.intake_json,
                      v.output_json,
                      v.summary_text,
                      v.docx_filename,
                      v.docx_mime,
                      v.docx_blob,
                      v.udf_filename,
                      v.udf_mime,
                      v.udf_blob,
                      v.created_at
                    FROM petition_versions v
                    JOIN petitions p ON p.petition_id = v.petition_id
                    WHERE v.version_id=%s AND p.petition_id=%s AND p.chat_id=%s AND p.user_id=%s
                    """,
                    (int(version_id), int(petition_id), int(chat_id), int(user_id)),
                )
            else:
                cur.execute(
                    """
                    SELECT
                      p.petition_id,
                      p.chat_id,
                      p.user_id,
                      p.status,
                      p.document_type,
                      p.court,
                      p.updated_at AS petition_updated_at,
                      v.version_id,
                      v.version_no,
                      v.intake_json,
                      v.output_json,
                      v.summary_text,
                      v.docx_filename,
                      v.docx_mime,
                      v.docx_blob,
                      v.udf_filename,
                      v.udf_mime,
                      v.udf_blob,
                      v.created_at
                    FROM petition_versions v
                    JOIN petitions p ON p.petition_id = v.petition_id
                    WHERE p.petition_id=%s AND p.chat_id=%s AND p.user_id=%s
                    ORDER BY v.version_no DESC
                    LIMIT 1
                    """,
                    (int(petition_id), int(chat_id), int(user_id)),
                )
            row = cur.fetchone()
            if not row:
                raise ValueError("Petition/version not found.")
            return row

    @staticmethod
    def create_petition(*, user_id: int, chat_id: int, title: Optional[str] = None) -> int:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO petitions (chat_id, user_id, status, title)
                VALUES (%s,%s,'processing',%s)
                """,
                (int(chat_id), int(user_id), title),
            )
            conn.commit()
            return int(cur.lastrowid)

    @staticmethod
    def delete_petition(*, user_id: int, chat_id: int, petition_id: int) -> None:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM petitions
                WHERE petition_id=%s AND chat_id=%s AND user_id=%s
                """,
                (int(petition_id), int(chat_id), int(user_id)),
            )
            conn.commit()

    @staticmethod
    def set_petition_status(
        *,
        user_id: int,
        chat_id: int,
        petition_id: int,
        status: str,
        error_message: Optional[str] = None,
        document_type: Optional[str] = None,
        court: Optional[str] = None,
    ) -> None:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE petitions
                SET status=%s, error_message=%s, document_type=%s, court=%s
                WHERE petition_id=%s AND chat_id=%s AND user_id=%s
                """,
                (
                    status,
                    error_message,
                    document_type,
                    court,
                    int(petition_id),
                    int(chat_id),
                    int(user_id),
                ),
            )
            conn.commit()

    @staticmethod
    def _get_latest_version_no(*, petition_id: int) -> int:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(MAX(version_no), 0) FROM petition_versions WHERE petition_id=%s",
                (int(petition_id),),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    @staticmethod
    def add_version(
        *,
        user_id: int,
        chat_id: int,
        petition_id: int,
        intake_json: str,
        output_json: str,
        summary_text: str,
        docx_filename: str,
        docx_blob: bytes,
        docx_mime: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        udf_filename: str | None = None,
        udf_blob: bytes | None = None,
        udf_mime: str = "application/octet-stream",
    ) -> Tuple[int, int]:
        """
        Returns (version_id, version_no).
        """
        # Ownership check via petitions row
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT petition_id, chat_id, user_id
                FROM petitions
                WHERE petition_id=%s AND chat_id=%s AND user_id=%s
                """,
                (int(petition_id), int(chat_id), int(user_id)),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Petition not found for this user/chat.")

        next_no = PetitionRepository._get_latest_version_no(petition_id=int(petition_id)) + 1
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO petition_versions
                  (
                    petition_id, version_no, intake_json, output_json, summary_text,
                    docx_filename, docx_mime, docx_blob,
                    udf_filename, udf_mime, udf_blob
                  )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    int(petition_id),
                    int(next_no),
                    intake_json,
                    output_json,
                    summary_text,
                    docx_filename,
                    docx_mime,
                    docx_blob,
                    udf_filename,
                    udf_mime,
                    udf_blob,
                ),
            )
            conn.commit()
            return int(cur.lastrowid), int(next_no)

    @staticmethod
    def list_for_chat(*, user_id: int, chat_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        lim = max(1, min(int(limit), 100))
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT
                  p.petition_id,
                  p.status,
                  p.title,
                  p.document_type,
                  p.court,
                  p.created_at,
                  p.updated_at,
                  v.version_id AS latest_version_id,
                  v.version_no AS latest_version_no,
                  v.docx_filename AS latest_filename,
                  v.summary_text AS latest_summary_text
                FROM petitions p
                LEFT JOIN petition_versions v
                  ON v.version_id = (
                    SELECT vv.version_id
                    FROM petition_versions vv
                    WHERE vv.petition_id = p.petition_id
                    ORDER BY vv.version_no DESC
                    LIMIT 1
                  )
                WHERE p.chat_id=%s AND p.user_id=%s AND p.status='ready'
                ORDER BY p.updated_at DESC
                LIMIT %s
                """,
                (int(chat_id), int(user_id), int(lim)),
            )
            return list(cur.fetchall() or [])

    @staticmethod
    def get_version_summary(
        *, user_id: int, chat_id: int, petition_id: int, version_id: Optional[int] = None
    ) -> Dict[str, Any]:
        return PetitionRepository._get_owned_version_row(
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id) if version_id is not None else None,
        )

    @staticmethod
    def get_version_document(
        *, user_id: int, chat_id: int, petition_id: int, version_id: Optional[int] = None
    ) -> Dict[str, Any]:
        return PetitionRepository._get_owned_version_row(
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id) if version_id is not None else None,
        )

    @staticmethod
    def update_version(
        *,
        user_id: int,
        chat_id: int,
        petition_id: int,
        version_id: int,
        output_json: str,
        summary_text: str,
        docx_filename: str,
        docx_blob: bytes,
        docx_mime: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        udf_filename: str | None = None,
        udf_blob: bytes | None = None,
        udf_mime: str = "application/octet-stream",
    ) -> None:
        PetitionRepository._get_owned_version_row(
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id),
        )
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE petition_versions
                SET output_json=%s,
                    summary_text=%s,
                    docx_filename=%s,
                    docx_mime=%s,
                    docx_blob=%s,
                    udf_filename=%s,
                    udf_mime=%s,
                    udf_blob=%s
                WHERE version_id=%s
                """,
                (
                    output_json,
                    summary_text,
                    docx_filename,
                    docx_mime,
                    docx_blob,
                    udf_filename,
                    udf_mime,
                    udf_blob,
                    int(version_id),
                ),
            )
            conn.commit()

    @staticmethod
    def get_docx_blob(
        *, user_id: int, chat_id: int, petition_id: int, version_id: int
    ) -> Tuple[str, str, bytes]:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT v.docx_filename, v.docx_mime, v.docx_blob
                FROM petition_versions v
                JOIN petitions p ON p.petition_id = v.petition_id
                WHERE v.version_id=%s AND p.petition_id=%s AND p.chat_id=%s AND p.user_id=%s
                """,
                (int(version_id), int(petition_id), int(chat_id), int(user_id)),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Petition/version not found.")
            return str(row["docx_filename"]), str(row["docx_mime"]), bytes(row["docx_blob"])

    @staticmethod
    def get_udf_blob(
        *, user_id: int, chat_id: int, petition_id: int, version_id: int
    ) -> Tuple[str, str, bytes]:
        chat = ChatRepository.get_chat(int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")

        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT v.udf_filename, v.udf_mime, v.udf_blob
                FROM petition_versions v
                JOIN petitions p ON p.petition_id = v.petition_id
                WHERE v.version_id=%s AND p.petition_id=%s AND p.chat_id=%s AND p.user_id=%s
                """,
                (int(version_id), int(petition_id), int(chat_id), int(user_id)),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Petition/version not found.")
            if not row.get("udf_blob"):
                raise ValueError("udf_not_available")
            fn = row.get("udf_filename") or "dilekce.udf"
            mime = row.get("udf_mime") or "application/octet-stream"
            return str(fn), str(mime), bytes(row["udf_blob"])


