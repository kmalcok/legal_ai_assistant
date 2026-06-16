from __future__ import annotations

from typing import Optional

from ..db import core_db


class SupportMailRepository:
    @staticmethod
    def create(
        *,
        user_id: int,
        username: str,
        email: str,
        message: str,
        request_ip: str,
        user_agent: str,
    ) -> int:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO support_mails (
                    user_id,
                    username,
                    email,
                    message,
                    request_ip,
                    user_agent,
                    is_sent
                )
                VALUES (%s, %s, %s, %s, %s, %s, 0)
                """,
                (
                    int(user_id),
                    (username or "").strip(),
                    (email or "").strip(),
                    (message or "").strip(),
                    (request_ip or "").strip(),
                    (user_agent or "").strip(),
                ),
            )
            mail_id = int(cur.lastrowid)
            conn.commit()
            return mail_id

    @staticmethod
    def mark_sent(*, support_mail_id: int) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE support_mails
                SET is_sent=1, sent_at=UTC_TIMESTAMP(), send_error=NULL
                WHERE support_mail_id=%s
                """,
                (int(support_mail_id),),
            )
            conn.commit()

    @staticmethod
    def mark_send_failed(*, support_mail_id: int, error: Optional[str]) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE support_mails
                SET is_sent=0, send_error=%s
                WHERE support_mail_id=%s
                """,
                ((error or "").strip()[:1000] or None, int(support_mail_id)),
            )
            conn.commit()
