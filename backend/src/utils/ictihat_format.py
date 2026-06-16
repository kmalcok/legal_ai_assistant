from __future__ import annotations

import re
from typing import Optional


def _ascii_fold_upper(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.upper()
    text = (
        text.replace("Ç", "C")
        .replace("Ğ", "G")
        .replace("İ", "I")
        .replace("İ", "I")
        .replace("Ö", "O")
        .replace("Ş", "S")
        .replace("Ü", "U")
    )
    text = re.sub(r"[\s_-]+", " ", text)
    return text.strip()


def normalize_kurum(value: Optional[str], *, daire: Optional[str] = None) -> str | None:
    raw = _ascii_fold_upper(value)
    if raw:
        aliases = {
            "YARGITAY": "YARGITAY",
            "DANISTAY": "DANISTAY",
            "UYUSMAZLIK": "UYUSMAZLIK MAHKEMESI",
            "UYUSMAZLIK MAHKEMESI": "UYUSMAZLIK MAHKEMESI",
            "ANAYASA": "ANAYASA MAHKEMESI",
            "ANAYASA MAHKEMESI": "ANAYASA MAHKEMESI",
            "YARGITAY CGK": "YARGITAY_CGK",
            "YARGITAY CEZA GENEL KURULU": "YARGITAY_CGK",
            "CEZA GENEL KURULU": "YARGITAY_CGK",
        }
        return aliases.get(raw, raw)

    d_low = str(daire or "").strip().casefold()
    if d_low in {"yargıtay", "yargitay"} or d_low.startswith(("yargıtay ", "yargitay ")):
        return "YARGITAY"
    if d_low in {"danıştay", "danistay"} or d_low.startswith(("danıştay ", "danistay ")):
        return "DANISTAY"
    if d_low in {"uyuşmazlık mahkemesi", "uyusmazlik mahkemesi"} or d_low.startswith(("uyuşmazlık mahkemesi ", "uyusmazlik mahkemesi ")):
        return "UYUSMAZLIK MAHKEMESI"
    if d_low in {"anayasa mahkemesi", "anayasa mahkemesı"} or d_low.startswith(("anayasa mahkemesi ", "anayasa mahkemesı ")):
        return "ANAYASA MAHKEMESI"
    return None


def court_display_name(*, kurum: Optional[str], daire: Optional[str] = None) -> str:
    normalized = normalize_kurum(kurum, daire=daire)
    if not normalized:
        return ""
    return {
        "YARGITAY": "Yargıtay",
        "DANISTAY": "Danıştay",
        "UYUSMAZLIK MAHKEMESI": "Uyuşmazlık Mahkemesi",
        "ANAYASA MAHKEMESI": "Anayasa Mahkemesi",
        "YARGITAY_CGK": "Yargıtay Ceza Genel Kurulu",
    }.get(normalized, normalized)


def daire_label(*, kurum: Optional[str], daire: Optional[str]) -> str:
    """
    Human-facing court+chamber label for UI/citation ("künye").

    - Keeps DB-facing `daire` as-is (may be short like "9. Hukuk Dairesi").
    - Adds a court prefix for display when missing (e.g. "Yargıtay 9. Hukuk Dairesi").
    """
    d = (daire or "").strip()
    court_name = court_display_name(kurum=kurum, daire=d)
    if not d:
        return court_name

    d_low = d.casefold()
    if (
        "yargıtay".casefold() in d_low
        or "danıştay".casefold() in d_low
        or "danistay" in d_low
        or "uyuşmazlık".casefold() in d_low
        or "uyusmazlik" in d_low
        or "anayasa".casefold() in d_low
    ):
        return d

    if not court_name:
        return d
    return f"{court_name} {d}".strip()

