from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional


_DEADLINE_LABELS = {
    "süre notu",
    "sure notu",
    "zamanaşımı notu",
    "zamanasimi notu",
    "süre",
    "sure",
    "zamanaşımı",
    "zamanasimi",
    "deadline",
}

# Capture patterns (most specific first):
# "Son gün: 20.02.2026", "Son gun: 20.02.2026", "Son tarih: 20/02/2026", "Son: 2026-02-20"
_RE_LAST_DAY_TR = re.compile(
    r"son\s*(?:g[uü]n|tarih)\s*[:\-]?\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})",
    re.IGNORECASE,
)
_RE_LAST_DAY_ISO = re.compile(
    r"son\s*(?:g[uü]n|tarih)\s*[:\-]?\s*(\d{4})-(\d{1,2})-(\d{1,2})",
    re.IGNORECASE,
)
# Generic date patterns as fallback if "son gün" prefix is missing
_RE_DATE_TR = re.compile(r"\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\b")
_RE_DATE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")


def _normalize_label(s: Any) -> str:
    if not isinstance(s, str):
        return ""
    return s.strip().lower()


def _is_deadline_label(label: str) -> bool:
    norm = _normalize_label(label)
    if not norm:
        return False
    if norm in _DEADLINE_LABELS:
        return True
    # Loose containment for variants like "Süre Notu (Son gün)" etc.
    return any(d in norm for d in ("süre", "sure", "zamanaşı", "zamanasi", "deadline"))


def _to_iso_date(year: int, month: int, day: int) -> Optional[str]:
    try:
        if year < 100:
            year += 2000
        d = date(int(year), int(month), int(day))
        return d.isoformat()
    except Exception:
        return None


def _parse_date_from_value(value: str) -> Optional[str]:
    """Return ISO YYYY-MM-DD if a date can be extracted from value, else None.

    Priority:
    1) "Son gün/tarih: GG.AA.YYYY" or "GG/AA/YYYY" or "GG-AA-YYYY"
    2) "Son gün/tarih: YYYY-MM-DD"
    3) Any GG.AA.YYYY in the string
    4) Any YYYY-MM-DD in the string
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()

    m = _RE_LAST_DAY_TR.search(text)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        iso = _to_iso_date(int(y), int(mo), int(d))
        if iso:
            return iso

    m = _RE_LAST_DAY_ISO.search(text)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        iso = _to_iso_date(int(y), int(mo), int(d))
        if iso:
            return iso

    m = _RE_DATE_TR.search(text)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        iso = _to_iso_date(int(y), int(mo), int(d))
        if iso:
            return iso

    m = _RE_DATE_ISO.search(text)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        iso = _to_iso_date(int(y), int(mo), int(d))
        if iso:
            return iso

    return None


def normalize_due_date(value: str) -> Optional[str]:
    """Public helper used by tool wrappers.

    Accepts GG.AA.YYYY, GG/AA/YYYY, GG-AA-YYYY, YYYY-MM-DD, or any string
    containing one of those. Returns ISO `YYYY-MM-DD` or None.
    """
    return _parse_date_from_value(value)


def normalize_due_time(value: Optional[str]) -> Optional[str]:
    """Accepts HH:MM or HH.MM, returns HH:MM or None."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    m = re.match(r"^(\d{1,2})[:.](\d{2})$", s)
    if not m:
        return None
    h = int(m.group(1))
    mi = int(m.group(2))
    if 0 <= h < 24 and 0 <= mi < 60:
        return f"{h:02d}:{mi:02d}"
    return None


def extract_deadlines_from_header_blocks(
    header_blocks: Any,
    *,
    document_type: Optional[str] = None,
    court: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Scan a petition's header_blocks list for deadline-style entries.

    Returns a list of dicts: { title, note, due_date }.

    - title: short descriptor (e.g. "Süre Notu - Dava Dilekçesi")
    - note: original block value (preserved for tooltip display)
    - due_date: ISO YYYY-MM-DD if extractable, else None (caller may skip)
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(header_blocks, list):
        return out

    doc_label = (document_type or "").strip()
    court_label = (court or "").strip()

    for block in header_blocks:
        if not isinstance(block, dict):
            continue
        label = block.get("label")
        value = block.get("value")
        if not _is_deadline_label(label):
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        iso = _parse_date_from_value(value)
        if not iso:
            # No usable date; skip silently. The agent prompt should pass dates explicitly via tool.
            continue
        title_parts: List[str] = [str(label).strip() or "Süre Notu"]
        if doc_label:
            title_parts.append(doc_label)
        elif court_label:
            title_parts.append(court_label)
        title = " - ".join(title_parts)[:512]
        out.append(
            {
                "title": title,
                "note": value.strip(),
                "due_date": iso,
            }
        )
    return out
