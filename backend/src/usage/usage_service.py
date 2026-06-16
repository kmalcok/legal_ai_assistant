from __future__ import annotations

import logging
from typing import Optional

from ..ai.util.rotator import get_current_openai_key_name
from ..db import core_db

_logger = logging.getLogger("usage")

_GREEN = "\033[92m"
_RESET = "\033[0m"


def _log_token(
    user_id: int,
    chat_id: Optional[int],
    usage_type: str,
    amount: int,
    model: Optional[str],
    openai_key_name: Optional[str] = None,
) -> None:
    _logger.info(
        "%s[USAGE] u=%s c=%s  %-18s  %7d tok  model=%s  openai_key=%s%s",
        _GREEN,
        user_id,
        chat_id if isinstance(chat_id, int) and chat_id > 0 else "-",
        usage_type,
        amount,
        model or "?",
        openai_key_name or "-",
        _RESET,
    )


def log_token_usage_bundle(
    user_id: int,
    chat_id: Optional[int],
    *,
    input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    model: Optional[str],
    openai_key_name: Optional[str] = None,
) -> None:
    """Single console line for input/output/reasoning (avoids interleaved spam)."""
    c = chat_id if isinstance(chat_id, int) and chat_id > 0 else "-"
    _logger.info(
        "%s[USAGE] u=%s c=%s  in=%s out=%s rsn=%s tok  model=%s  openai_key=%s%s",
        _GREEN,
        user_id,
        c,
        int(input_tokens) if input_tokens else 0,
        int(output_tokens) if output_tokens else 0,
        int(reasoning_tokens) if reasoning_tokens else 0,
        model or "?",
        openai_key_name or "-",
        _RESET,
    )



# --------------------------------------------------------------------------- #
# user_tool_usages mantigi kaldirildi.
# Artik tum kullanim takibi token bazinda user_usages tablosuna kaydedilir.
# _log_tool ve record_tool_usage metodu devre disi birakildi.
# --------------------------------------------------------------------------- #


class UsageService:
    """
    Best-effort usage recording into user_usages in the application database.
    Tum LLM/embedding/agent cagrilari token bazinda bu tabloya kaydedilir.
    """

    async def record_token_usage(
        self,
        *,
        user_id: int,
        chat_id: int,
        chat_message_id: Optional[int] = None,
        usage_type: str,
        amount: int,
        model: Optional[str] = None,
        emit_log: bool = True,
    ) -> None:
        if not isinstance(amount, int) or amount <= 0:
            return

        # chat_id bazen "bagimsiz" cagirilarda 0/None gibi gelebiliyor (ornegin /ictihat/search).
        # user_usages.chat_id FK ile chats.chat_id'ye bagli oldugu icin gecersiz id insert'i sessizce
        # fail edebilir. Bu durumda chat_id'yi NULL yaziyoruz.
        chat_id_db: Optional[int]
        try:
            chat_id_db = int(chat_id)
        except Exception:
            chat_id_db = None
        if isinstance(chat_id_db, int) and chat_id_db <= 0:
            chat_id_db = None

        with core_db() as conn:
            cur = conn.cursor()
            # Backwards-compatible insert:
            # - Newer schema has chat_message_id column.
            # - Older installs may not; fall back to legacy insert on failure.
            try:
                cur.execute(
                    """
                    INSERT INTO user_usages (user_id, chat_id, chat_message_id, type, model, amount)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        int(user_id),
                        chat_id_db,
                        int(chat_message_id) if chat_message_id is not None else None,
                        usage_type,
                        model,
                        int(amount),
                    ),
                )
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur.execute(
                    """
                    INSERT INTO user_usages (user_id, chat_id, type, model, amount)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (int(user_id), chat_id_db, usage_type, model, int(amount)),
                )
            conn.commit()
        if emit_log:
            _log_token(
                int(user_id),
                chat_id_db,
                usage_type,
                int(amount),
                model,
                get_current_openai_key_name(),
            )

    # record_tool_usage kaldirildi - tum kullanim token bazinda takip edilir.
    # Eski imza referans icin:
    # async def record_tool_usage(self, *, user_id, chat_id, tool_type, amount=1)


