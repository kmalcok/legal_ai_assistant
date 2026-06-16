from __future__ import annotations

import re
from typing import Any, Dict, Optional, Union

from ...db import core_db



def _normalize_ws(s: str) -> str:
    return " ".join((s or "").replace("\x00", " ").split()).strip()


def _parse_madde_no_and_ek(madde_no: Optional[Union[int, str]]) -> tuple[Optional[int], Optional[str]]:
    """
    Accept legacy inputs like "1/A" and return (1, "A").
    """
    if madde_no is None:
        return None, None
    if isinstance(madde_no, int):
        return int(madde_no), None
    raw = str(madde_no).strip()
    m = re.match(r"^\s*(\d+)\s*(?:[/\-]\s*([A-Za-z0-9]+))?\s*$", raw)
    if m:
        return int(m.group(1)), ((m.group(2) or "").strip() or None)
    m2 = re.search(r"(\d+)", raw)
    if m2:
        return int(m2.group(1)), None
    return None, None


async def gerekce_get_chunk(
    *,
    user_id: int,
    chat_id: int,
    law_no: int,
    kind: str = "genel",  # "genel" | "madde"
    madde_no: Optional[Union[int, str]] = None,
    # paging (cheap)
    page_chars: int = 600,
    cursor_char_offset: int = 0,
    include_full_text: bool = False,
) -> Dict[str, Any]:
    """
    Fetch Genel Gerekçe or a specific Madde Gerekçesi from mevzuat_rag DB tables,
    but return only a small slice (page) to keep tool output cheap.
    """
    kind_norm = (kind or "genel").strip().lower()
    if kind_norm not in {"genel", "madde"}:
        return {"ok": False, "reason": "invalid_kind", "detail": "kind must be 'genel' or 'madde'"}

    page_chars = max(100, min(int(page_chars), 2000))
    cursor_char_offset = max(0, int(cursor_char_offset))

    row: Dict[str, Any] | None = None
    if kind_norm == "genel":
        sql = """
            SELECT
                mevzuat_no AS law_no,
                genel_gerekce_text AS text
            FROM mevzuat_rag
            WHERE mevzuat_no = %s AND genel_gerekce_text IS NOT NULL
            LIMIT 1
        """
        params = (int(law_no),)
    else:
        if madde_no is None:
            return {"ok": False, "reason": "missing_madde_no"}
        m_no, m_ek = _parse_madde_no_and_ek(madde_no)
        if m_no is None:
            return {"ok": False, "reason": "invalid_madde_no"}
        # DB schema stores madde_no as varchar; represent suffix as "1/A" within madde_no.
        madde_key = f"{int(m_no)}/{m_ek}" if m_ek else str(int(m_no))
        sql = """
            SELECT
                mevzuat_no AS law_no,
                madde_no,
                NULL AS madde_ek,
                gerekce_text AS text
            FROM mevzuat_rag
            WHERE
                mevzuat_no = %s
                AND madde_no = %s
                AND gerekce_text IS NOT NULL
                AND (chunk_order = 0 OR chunk_order = 1)
            ORDER BY chunk_order
            LIMIT 1
        """
        params = (int(law_no), str(madde_key))

    with core_db() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        row = cur.fetchone()

    if not row:
        return {"ok": False, "reason": "not_found", "law_no": int(law_no), "kind": kind_norm, "madde_no": madde_no}

    text = row.get("text") or ""
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()

    start = min(cursor_char_offset, len(text))
    end = min(start + page_chars, len(text))
    page_text = text[start:end]
    page_text = _normalize_ws(page_text) if "\n" not in (page_text or "") else page_text.strip()

    done = end >= len(text)
    next_cursor = {"char_offset": int(end)}

    out: Dict[str, Any] = {
        "ok": True,
        "ref": {
            "law_no": int(law_no),
            "kind": kind_norm,
            "madde_no": int(row.get("madde_no")) if kind_norm == "madde" and row.get("madde_no") is not None else None,
            "madde_ek": (row.get("madde_ek") or None) if kind_norm == "madde" else None,
        },
        "source_files": None,
        "page": {
            "page_chars": int(page_chars),
            "text": page_text,
            "cursor_in": {"char_offset": int(cursor_char_offset)},
            "cursor_next": next_cursor,
            "done": bool(done),
            "total_chars": int(len(text)),
        },
        "note": "Use cursor_next to fetch the next slice. Avoid pulling full text unless strictly needed.",
    }
    if include_full_text:
        out["text"] = text
    return out


