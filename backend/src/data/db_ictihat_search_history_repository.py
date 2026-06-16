from __future__ import annotations

import json
from typing import Any, Dict, List

from ..db import core_db


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_filters(filters: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(filters, dict):
        return {}
    out: Dict[str, Any] = {}
    for key in ("kurum", "daire", "esas_yil", "esas_sira", "karar_yil", "karar_sira", "karar_tarihi"):
        value = filters.get(key)
        if value is None:
            continue
        if key in {"esas_yil", "esas_sira", "karar_yil", "karar_sira"}:
            try:
                out[key] = int(value)
            except Exception:
                continue
        else:
            text = _safe_text(value)
            if text:
                out[key] = text
    return out


def _normalize_return_items(items: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        try:
            document_id = int(item.get("document_id"))
        except Exception:
            continue
        out.append(
            {
                "document_id": int(document_id),
                "kurum": _safe_text(item.get("kurum")),
                "daire": _safe_text(item.get("daire")),
                "emsal": {
                    "yil": _safe_int(((item.get("esas") or {}).get("yil")), default=0) or None,
                    "sira": _safe_int(((item.get("esas") or {}).get("sira")), default=0) or None,
                },
                "karar": {
                    "yil": _safe_int(((item.get("karar") or {}).get("yil")), default=0) or None,
                    "sira": _safe_int(((item.get("karar") or {}).get("sira")), default=0) or None,
                    "tarih": _safe_text(((item.get("karar") or {}).get("tarih"))),
                },
            }
        )
        if len(out) >= 10:
            break
    return out


class IctihatSearchHistoryRepository:
    @staticmethod
    def insert(
        *,
        user_id: int,
        search_type: str,
        query_text: str | None,
        filters: Dict[str, Any] | None,
        top_k: int,
        result_count: int,
        return_items: List[Dict[str, Any]] | None,
    ) -> None:
        search_type_norm = str(search_type or "").strip().lower()
        if search_type_norm not in {"ai", "semantic", "keyword"}:
            return
        try:
            normalized_filters = _normalize_filters(filters)
            normalized_items = _normalize_return_items(return_items)
            with core_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO ictihat_search_history
                      (user_id, search_type, query_text, filters_json, top_k, result_count, return_items_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        int(user_id),
                        search_type_norm,
                        _safe_text(query_text),
                        json.dumps(normalized_filters, ensure_ascii=False),
                        max(1, int(top_k)),
                        max(0, int(result_count)),
                        json.dumps(normalized_items, ensure_ascii=False),
                    ),
                )
                conn.commit()
        except Exception:
            # Best-effort: missing table or DB migration should never break search.
            return

    @staticmethod
    def list_recent(*, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            with core_db() as conn:
                cur = conn.cursor(dictionary=True)
                cur.execute(
                    """
                    SELECT
                      history_id,
                      user_id,
                      search_type,
                      query_text,
                      filters_json,
                      top_k,
                      result_count,
                      return_items_json,
                      created_at
                    FROM ictihat_search_history
                    WHERE user_id=%s
                    ORDER BY created_at DESC, history_id DESC
                    LIMIT %s
                    """,
                    (int(user_id), max(1, int(limit))),
                )
                rows = list(cur.fetchall() or [])
        except Exception:
            return []

        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                filters = json.loads(row.get("filters_json") or "{}")
            except Exception:
                filters = {}
            try:
                return_items = json.loads(row.get("return_items_json") or "[]")
            except Exception:
                return_items = []
            out.append(
                {
                    "history_id": int(row.get("history_id")),
                    "user_id": int(row.get("user_id")),
                    "search_type": str(row.get("search_type") or ""),
                    "query_text": _safe_text(row.get("query_text")),
                    "filters": filters if isinstance(filters, dict) else {},
                    "top_k": max(1, _safe_int(row.get("top_k"), default=5)),
                    "result_count": max(0, _safe_int(row.get("result_count"), default=0)),
                    "return_items": return_items if isinstance(return_items, list) else [],
                    "created_at": row.get("created_at"),
                }
            )
        return out

    @staticmethod
    def delete(*, user_id: int, history_id: int) -> bool:
        try:
            with core_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM ictihat_search_history WHERE history_id=%s AND user_id=%s",
                    (int(history_id), int(user_id)),
                )
                conn.commit()
                return bool(getattr(cur, "rowcount", 0))
        except Exception:
            return False
