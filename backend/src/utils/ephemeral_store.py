from __future__ import annotations

import base64
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
import redis.exceptions

from ..config import agent_config


@dataclass(frozen=True)
class EphemeralFile:
    token: str
    chat_id: int
    user_id: int
    filename: str
    mime: str
    content_b64: str
    created_at_ts: float
    expires_at_ts: float
    # Optional pre-rendered variants stored under the same token.
    # Shape: {"udf": {"filename": "...", "mime": "...", "content_b64": "..."}, "pdf": {...}}
    variants: Optional[Dict[str, Dict[str, str]]] = None


class EphemeralFileStore:
    """
    Ephemeral file store for "downloadable once" artifacts (DOCX etc).
    Backed by Redis when available, with in-process fallback.

    NOTE: This is intentionally not persisted to DB (per product requirements).
    """

    def __init__(self) -> None:
        cfg = agent_config()
        # store as JSON (base64 content) to avoid binary handling differences on Windows
        self._redis = aioredis.Redis.from_url(cfg.redis_url, decode_responses=True)
        self._fallback: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _key(token: str) -> str:
        return f"ephemeral:file:{token}"

    async def put(
        self,
        *,
        chat_id: int,
        user_id: int,
        filename: str,
        mime: str,
        content_bytes: bytes,
        variants: Optional[Dict[str, Dict[str, Any]]] = None,
        ttl_seconds: int = 900,
    ) -> EphemeralFile:
        ttl = max(30, min(int(ttl_seconds), 6 * 3600))
        now = time.time()
        token = uuid.uuid4().hex
        payload = {
            "token": token,
            "chat_id": int(chat_id),
            "user_id": int(user_id),
            "filename": str(filename or "document.docx"),
            "mime": str(mime or "application/octet-stream"),
            "content_b64": base64.b64encode(content_bytes).decode("ascii"),
            "variants": None,
            "created_at_ts": float(now),
            "expires_at_ts": float(now + ttl),
        }
        if variants:
            # Normalize variants into JSON-serializable base64 payloads.
            norm: Dict[str, Dict[str, str]] = {}
            for k, v in variants.items():
                try:
                    kk = str(k or "").strip().lower()
                    if not kk:
                        continue
                    if not isinstance(v, dict):
                        continue
                    fn = str(v.get("filename") or "")
                    mm = str(v.get("mime") or "application/octet-stream")
                    b = v.get("content_bytes")
                    if isinstance(b, str):
                        # accept pre-b64 too
                        b64 = b
                    else:
                        if not isinstance(b, (bytes, bytearray)):
                            continue
                        b64 = base64.b64encode(bytes(b)).decode("ascii")
                    norm[kk] = {"filename": fn, "mime": mm, "content_b64": b64}
                except Exception:
                    continue
            payload["variants"] = norm or None
        key = self._key(token)
        try:
            await self._redis.set(key, json.dumps(payload, ensure_ascii=False), ex=ttl)
        except (redis.exceptions.ConnectionError, OSError):
            self._fallback[key] = payload
        return EphemeralFile(**payload)  # type: ignore[arg-type]

    async def get(self, token: str) -> Optional[EphemeralFile]:
        key = self._key(token)
        raw = None
        try:
            raw = await self._redis.get(key)
        except (redis.exceptions.ConnectionError, OSError):
            raw = None
        if raw is None:
            raw = self._fallback.get(key)
            if raw is None:
                return None
            # expire fallback
            if float(raw.get("expires_at_ts") or 0) < time.time():
                self._fallback.pop(key, None)
                return None
            return EphemeralFile(**raw)  # type: ignore[arg-type]
        try:
            obj = json.loads(raw) if isinstance(raw, str) else raw
            if float(obj.get("expires_at_ts") or 0) < time.time():
                return None
            return EphemeralFile(**obj)  # type: ignore[arg-type]
        except Exception:
            return None

    async def consume(self, token: str) -> Optional[EphemeralFile]:
        """
        Fetch and delete.
        """
        f = await self.get(token)
        if f is None:
            return None
        key = self._key(token)
        try:
            await self._redis.delete(key)
        except (redis.exceptions.ConnectionError, OSError):
            self._fallback.pop(key, None)
        return f

    async def purge_chat(self, *, chat_id: int, user_id: int) -> int:
        """
        Best-effort: delete ephemeral files belonging to (chat_id,user_id).
        This is a rare operation (chat deletion), so we accept a scan.
        """
        deleted = 0
        chat_id = int(chat_id)
        user_id = int(user_id)

        # Fallback store
        try:
            for k, v in list(self._fallback.items()):
                try:
                    if int(v.get("chat_id")) == chat_id and int(v.get("user_id")) == user_id:
                        self._fallback.pop(k, None)
                        deleted += 1
                except Exception:
                    continue
        except Exception:
            pass

        # Redis store
        try:
            async for key in self._redis.scan_iter(match="ephemeral:file:*", count=200):
                try:
                    raw = await self._redis.get(key)
                except Exception:
                    raw = None
                if not raw:
                    continue
                try:
                    obj = json.loads(raw) if isinstance(raw, str) else raw
                    if int(obj.get("chat_id")) == chat_id and int(obj.get("user_id")) == user_id:
                        await self._redis.delete(key)
                        deleted += 1
                except Exception:
                    continue
        except (redis.exceptions.ConnectionError, OSError):
            # Redis not available; fallback already cleared.
            pass
        return deleted


ephemeral_files = EphemeralFileStore()


