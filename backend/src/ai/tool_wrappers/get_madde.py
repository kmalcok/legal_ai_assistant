from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from ...db import core_db



def _normalize_ws(s: str) -> str:
    return " ".join((s or "").replace("\x00", " ").split()).strip()


def _parse_madde_no_and_ek(
    madde_no: Optional[Union[int, str]],
    madde_ek: Optional[str],
) -> tuple[Optional[int], Optional[str]]:
    """
    Back-compat parser for callers passing (madde_no, madde_ek).

    Current DB schema stores `madde_no` as varchar(32) in `mevzuat_rag`
    (e.g. "1", "1/A", "GEÇİCİ 1"). We keep parsing to support legacy tool calls,
    but we do NOT rely on a separate `madde_ek` DB column.
    """
    if madde_no is None:
        return None, (madde_ek or None)

    if isinstance(madde_no, int):
        no = int(madde_no)
        ek = (madde_ek or "").strip() or None
        return no, ek

    raw = str(madde_no).strip()
    ek_norm = (madde_ek or "").strip() or None

    # Common forms: "1", "1/A", "1-A"
    m = re.match(r"^\s*(\d+)\s*(?:[/\-]\s*([A-Za-z0-9]+))?\s*$", raw)
    if m:
        no = int(m.group(1))
        ek_from_raw = (m.group(2) or "").strip() or None
        return no, (ek_norm or ek_from_raw)

    # Fallback: grab first number in string (e.g. "GEÇİCİ 1")
    m2 = re.search(r"(\d+)", raw)
    if m2:
        no = int(m2.group(1))
        return no, ek_norm

    return None, ek_norm


def _combine_madde_no(madde_no: Optional[Union[int, str]], madde_ek: Optional[str]) -> Optional[str]:
    """
    Combine legacy inputs into a single DB key for r.madde_no (varchar).
    Examples:
      - (1, "A") -> "1/A"
      - ("1", "A") -> "1/A"
      - ("1/A", None) -> "1/A"
      - ("GEÇİCİ 1", None) -> "GEÇİCİ 1"
    """
    if madde_no is None:
        return None
    raw = str(madde_no).strip()
    ek = (madde_ek or "").strip()
    if not raw:
        return None
    if "/" in raw or "-" in raw:
        return raw
    if ek:
        return f"{raw}/{ek}"
    return raw


def _paginate_from_chunks(
    rows: List[Dict[str, Any]],
    *,
    start_chunk_order: int,
    start_char_offset: int,
    page_chars: int,
) -> tuple[str, dict[str, int], bool]:
    """
    Build a page of length <= page_chars from ordered chunk rows.
    Cursor is (chunk_order, char_offset) into that chunk for the next call.
    """
    page_chars = max(50, int(page_chars))
    co = int(start_chunk_order)
    off = max(0, int(start_char_offset))

    pieces: list[str] = []
    remaining = page_chars
    cursor_chunk = co
    cursor_off = off

    # Find starting index
    idx0 = 0
    for i, r in enumerate(rows):
        try:
            if int(r.get("chunk_order") or 0) >= co:
                idx0 = i
                break
        except Exception:
            continue

    for i in range(idx0, len(rows)):
        r = rows[i]
        try:
            chunk_order = int(r.get("chunk_order") or 0)
        except Exception:
            continue
        txt = (r.get("text") or "")
        if not isinstance(txt, str):
            txt = str(txt)
        txt = txt.strip()
        if not txt:
            continue

        if chunk_order < co:
            continue

        start = 0
        if chunk_order == co:
            start = min(off, len(txt))

        s = txt[start:]
        if not s:
            cursor_chunk = chunk_order + 1
            cursor_off = 0
            continue

        # Add separator between chunks
        sep = "\n"
        if pieces:
            if remaining <= len(sep):
                # no space even for separator -> stop
                cursor_chunk = chunk_order
                cursor_off = start
                break
            pieces.append(sep)
            remaining -= len(sep)

        if len(s) <= remaining:
            pieces.append(s)
            remaining -= len(s)
            cursor_chunk = chunk_order + 1
            cursor_off = 0
            continue

        # Partial consume within this chunk
        pieces.append(s[:remaining])
        cursor_chunk = chunk_order
        cursor_off = start + remaining
        remaining = 0
        break

    page = "".join(pieces).strip()
    cursor = {"chunk_order": int(cursor_chunk), "char_offset": int(cursor_off)}

    # Determine if done: if cursor points beyond last chunk
    last_order = None
    for r in reversed(rows):
        try:
            last_order = int(r.get("chunk_order") or 0)
            break
        except Exception:
            continue
    done = False
    if last_order is not None and cursor_chunk > int(last_order):
        done = True
    if last_order is None:
        done = True
    return page, cursor, done


async def get_madde_by_reference(
    *,
    user_id: int,
    chat_id: int,
    kanun_no: Optional[int] = None,
    doc_title_contains: Optional[str] = None,
    section_type: Optional[str] = None,  # maps to DB: madde_tip
    madde_no: Optional[Union[int, str]] = None,  # DB stores INT; accept legacy "1/A" too
    madde_ek: Optional[str] = None,
    # Backward-compatible chunk cap (used for internal fetching too)
    limit_chunks: int = 200,
    # Paging: return only a small slice of the madde text
    page_chars: int = 600,
    cursor_chunk_order: int = 0,
    cursor_char_offset: int = 0,
    # Optional: include full stitched text (expensive) - default off
    include_full_text: bool = False,
    include_chunks: bool = False,
) -> Dict[str, Any]:
    """
    Deterministic retrieval of a specific law section (madde/ek/gecici/etc).

    If kanun_no is provided, it is the primary filter. If not, doc_title_contains
    should be provided.
    """
    where = []
    params: List[Any] = []

    if kanun_no is not None:
        where.append("r.mevzuat_no = %s")
        params.append(int(kanun_no))
    if doc_title_contains:
        where.append("r.mevzuat_adi LIKE %s")
        params.append(f"%{doc_title_contains}%")
    if section_type:
        where.append("r.madde_tip = %s")
        params.append(str(section_type))

    madde_no_int, madde_ek_norm = _parse_madde_no_and_ek(madde_no, madde_ek)
    # DB stores madde_no as varchar; use combined string to disambiguate 1 vs 1/A.
    madde_no_key = _combine_madde_no(madde_no_int if madde_no_int is not None else madde_no, madde_ek_norm)
    if madde_no_key is not None:
        where.append("r.madde_no = %s")
        params.append(str(madde_no_key))

    if not where:
        return {"ok": False, "reason": "missing_filters"}

    sql = f"""
        SELECT
            r.mevzuat_id AS doc_id,
            r.mevzuat_tur_name AS doc_type,
            r.mevzuat_no AS kanun_no,
            r.mevzuat_adi AS doc_title,
            r.madde_tip AS section_type,
            r.madde_no,
            NULL AS madde_ek,
            r.madde_basligi AS madde_baslik,
            r.chunk_order,
            r.madde_text AS text
        FROM mevzuat_rag r
        WHERE {" AND ".join(where)}
        ORDER BY r.chunk_order
        LIMIT %s
    """
    params.append(int(limit_chunks))

    with core_db() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, tuple(params))
        rows = list(cur.fetchall() or [])

    if not rows:
        return {"ok": False, "reason": "not_found"}

    stitched = "\n".join([(r.get("text") or "").strip() for r in rows]).strip()
    header = rows[0]

    # Build a small paged slice
    page_text, next_cursor, done = _paginate_from_chunks(
        rows,
        start_chunk_order=int(cursor_chunk_order),
        start_char_offset=int(cursor_char_offset),
        page_chars=int(page_chars),
    )
    page_text = _normalize_ws(page_text) if "\n" not in (page_text or "") else page_text.strip()

    out: Dict[str, Any] = {
        "ok": True,
        "doc": {
            "doc_id": header.get("doc_id"),
            "doc_type": header.get("doc_type"),
            "kanun_no": header.get("kanun_no"),
            "doc_title": header.get("doc_title"),
        },
        "ref": {
            "section_type": header.get("section_type"),
            "madde_no": header.get("madde_no"),
            "madde_ek": None,
            "madde_baslik": header.get("madde_baslik"),
        },
        "page": {
            "page_chars": int(page_chars),
            "text": page_text,
            "cursor_in": {"chunk_order": int(cursor_chunk_order), "char_offset": int(cursor_char_offset)},
            "cursor_next": next_cursor,
            "done": bool(done),
        },
        "note": "Use cursor_next to fetch the next slice. Avoid pulling full text unless strictly needed.",
    }

    if include_chunks:
        out["chunks"] = [{"chunk_order": r.get("chunk_order"), "text": r.get("text")} for r in rows]
    if include_full_text:
        out["text"] = stitched
    return out


