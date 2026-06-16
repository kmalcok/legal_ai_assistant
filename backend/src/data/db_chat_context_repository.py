from __future__ import annotations

import json
from typing import Any, Dict, List

from ..db import core_db


class ChatContextRepository:
    @staticmethod
    def insert_items(*, chat_id: int, message_id: int, user_id: int, items: List[Dict[str, Any]]) -> None:
        rows: list[tuple[Any, ...]] = []
        for idx, item in enumerate(items or []):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            payload = item.get("payload")
            source = str(item.get("source") or "ui").strip() or "ui"
            if not kind or not isinstance(payload, dict):
                continue
            rows.append(
                (
                    int(chat_id),
                    int(message_id),
                    int(user_id),
                    kind,
                    source[:16],
                    int(idx),
                    json.dumps(payload, ensure_ascii=False),
                )
            )
        if not rows:
            return

        with core_db() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT INTO chat_context_items
                  (chat_id, message_id, user_id, kind, source, sort_order, payload_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
            conn.commit()

    @staticmethod
    def list_for_chat_ids(*, user_id: int, chat_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        ids: list[int] = []
        for value in chat_ids or []:
            try:
                ids.append(int(value))
            except Exception:
                continue
        ids = list(dict.fromkeys(ids))
        if not ids:
            return {}

        placeholders = ",".join(["%s"] * len(ids))
        sql = f"""
            SELECT
              context_item_id,
              chat_id,
              message_id,
              user_id,
              kind,
              source,
              sort_order,
              payload_json,
              created_at
            FROM chat_context_items
            WHERE user_id=%s AND chat_id IN ({placeholders})
            ORDER BY created_at ASC, context_item_id ASC
        """
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, (int(user_id), *ids))
            rows = list(cur.fetchall() or [])

        out: Dict[int, List[Dict[str, Any]]] = {}
        for row in rows:
            try:
                chat_id = int(row.get("chat_id"))
            except Exception:
                continue
            raw_payload = row.get("payload_json")
            try:
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else {}
            except Exception:
                payload = {}
            out.setdefault(chat_id, []).append(
                {
                    "context_item_id": int(row.get("context_item_id")),
                    "chat_id": chat_id,
                    "message_id": int(row.get("message_id")),
                    "user_id": int(row.get("user_id")),
                    "kind": str(row.get("kind") or ""),
                    "source": str(row.get("source") or ""),
                    "sort_order": int(row.get("sort_order") or 0),
                    "payload": payload if isinstance(payload, dict) else {},
                    "created_at": row.get("created_at"),
                }
            )
        return out

    @staticmethod
    def list_for_message_ids(*, user_id: int, message_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        ids: list[int] = []
        for value in message_ids or []:
            try:
                ids.append(int(value))
            except Exception:
                continue
        ids = list(dict.fromkeys(ids))
        if not ids:
            return {}

        placeholders = ",".join(["%s"] * len(ids))
        sql = f"""
            SELECT
              context_item_id,
              chat_id,
              message_id,
              user_id,
              kind,
              source,
              sort_order,
              payload_json,
              created_at
            FROM chat_context_items
            WHERE user_id=%s AND message_id IN ({placeholders})
            ORDER BY created_at ASC, context_item_id ASC
        """
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, (int(user_id), *ids))
            rows = list(cur.fetchall() or [])

        out: Dict[int, List[Dict[str, Any]]] = {}
        for row in rows:
            try:
                message_id = int(row.get("message_id"))
            except Exception:
                continue
            raw_payload = row.get("payload_json")
            try:
                payload = json.loads(raw_payload) if isinstance(raw_payload, str) else {}
            except Exception:
                payload = {}
            out.setdefault(message_id, []).append(
                {
                    "context_item_id": int(row.get("context_item_id")),
                    "chat_id": int(row.get("chat_id")),
                    "message_id": message_id,
                    "user_id": int(row.get("user_id")),
                    "kind": str(row.get("kind") or ""),
                    "source": str(row.get("source") or ""),
                    "sort_order": int(row.get("sort_order") or 0),
                    "payload": payload if isinstance(payload, dict) else {},
                    "created_at": row.get("created_at"),
                }
            )
        return out

    @staticmethod
    def chat_has_kind(*, user_id: int, chat_id: int, kind: str) -> bool:
        kind_text = str(kind or "").strip()
        if not kind_text:
            return False
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 1
                FROM chat_context_items
                WHERE user_id=%s AND chat_id=%s AND kind=%s
                LIMIT 1
                """,
                (int(user_id), int(chat_id), kind_text),
            )
            row = cur.fetchone()
        return bool(row)
