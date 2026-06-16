from __future__ import annotations

from typing import Any, Dict, List

from ...utils.dev_logging import dev_log
from ...utils.ictihat_format import daire_label, normalize_kurum


async def ictihat_push_to_chat(
    *,
    user_id: int,
    chat_id: int,
    ictihat_items: List[Dict[str, Any]],
    limit_docs: int = 5,
    # 0 => unlimited (no truncation)
    limit_chars_per_doc: int = 0,
) -> Dict[str, Any]:
    """
    Agent-controlled tool for selecting which ictihat decisions are relevant.

    IMPORTANT: This tool no longer pushes texts via websocket.
    The selected `document_ids` are persisted as message-scoped metadata by AgentService
    (chat_messages.id -> chat_message_ictihat), and clients should fetch/show them via
    chat history / message metadata.
    """
    # sanitize + shape contract
    cleaned: list[dict] = []
    seen: set[int] = set()
    for it in (ictihat_items or [])[: max(1, int(limit_docs))]:
        if not isinstance(it, dict):
            continue
        try:
            did = int(it.get("document_id"))
        except Exception:
            continue
        if did in seen:
            continue
        seen.add(did)
        kurum = normalize_kurum(it.get("kurum"), daire=it.get("daire"))
        daire = (str(it.get("daire") or "").strip() or None)
        cleaned.append(
            {
                "document_id": did,
                "kurum": kurum,
                "daire": daire,
                "daire_label": daire_label(
                    kurum=kurum,
                    daire=daire,
                )
                or None,
                "esas_yil": int(it.get("esas_yil")) if it.get("esas_yil") is not None else None,
                "esas_sira": int(it.get("esas_sira")) if it.get("esas_sira") is not None else None,
                "karar_yil": int(it.get("karar_yil")) if it.get("karar_yil") is not None else None,
                "karar_sira": int(it.get("karar_sira")) if it.get("karar_sira") is not None else None,
                "karar_tarihi": (str(it.get("karar_tarihi") or "").strip() or None),
            }
        )
    if not cleaned:
        return {"ok": False, "reason": "no_items"}

    dev_log(
        "ictihat",
        "ictihat_present_selected",
        {
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "document_ids": [x.get("document_id") for x in cleaned][:50],
            "limit_chars_per_doc": int(limit_chars_per_doc),
        },
    )

    return {
        "ok": True,
        "chat_id": int(chat_id),
        "count": len(cleaned),
        "items": cleaned,
        "document_ids": [x.get("document_id") for x in cleaned],
    }

