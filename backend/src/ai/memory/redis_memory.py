from __future__ import annotations

from typing import List, Optional

import redis.asyncio as aioredis
import redis.exceptions

from ...config import agent_config


class RedisMemory:
    """
    Short-term rolling memory stored in Redis lists.

    Key format:
      law:chat:{chat_id}
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        cfg = agent_config()
        self.redis = redis_client or aioredis.Redis.from_url(cfg.redis_url, decode_responses=True)
        self.max_items = cfg.max_history_items
        self.ttl_seconds = cfg.memory_ttl_seconds
        # If Redis isn't available, fall back to in-process memory so the CLI can still run.
        self._fallback: dict[str, List[str]] = {}
        self._use_fallback: bool = False

    @staticmethod
    def key(chat_id: int) -> str:
        return f"law:chat:{int(chat_id)}"

    async def _refresh_ttl(self, key: str) -> None:
        if self.ttl_seconds <= 0:
            return
        await self.redis.expire(key, int(self.ttl_seconds))

    async def load(self, chat_id: int) -> List[str]:
        k = self.key(chat_id)
        if self._use_fallback:
            return list(self._fallback.get(k, []))
        try:
            return await self.redis.lrange(k, 0, -1)
        except (redis.exceptions.ConnectionError, OSError):
            self._use_fallback = True
            return list(self._fallback.get(k, []))

    async def append_user(self, chat_id: int, message: str) -> None:
        k = self.key(chat_id)
        item = f"Human Message: {message}"
        if self._use_fallback:
            self._fallback.setdefault(k, []).append(item)
            await self.trim(chat_id)
            return
        try:
            await self.redis.rpush(k, item)
            await self.trim(chat_id)
            await self._refresh_ttl(k)
        except (redis.exceptions.ConnectionError, OSError):
            self._use_fallback = True
            self._fallback.setdefault(k, []).append(item)
            await self.trim(chat_id)

    async def append_assistant(self, chat_id: int, message: str) -> None:
        k = self.key(chat_id)
        item = f"Ai Agent Message: {message}"
        if self._use_fallback:
            self._fallback.setdefault(k, []).append(item)
            await self.trim(chat_id)
            return
        try:
            await self.redis.rpush(k, item)
            await self.trim(chat_id)
            await self._refresh_ttl(k)
        except (redis.exceptions.ConnectionError, OSError):
            self._use_fallback = True
            self._fallback.setdefault(k, []).append(item)
            await self.trim(chat_id)

    async def seed_from_summary(self, chat_id: int, summary: str) -> None:
        # Replace list with a single summary seed.
        k = self.key(chat_id)
        item = f"Summarized Context: {summary}"
        if self._use_fallback:
            self._fallback[k] = [item]
            return
        try:
            await self.redis.delete(k)
            await self.redis.rpush(k, item)
            await self._refresh_ttl(k)
        except (redis.exceptions.ConnectionError, OSError):
            self._use_fallback = True
            self._fallback[k] = [item]

    async def seed_from_summary_and_messages(self, chat_id: int, summary: str, messages: List[str]) -> None:
        k = self.key(chat_id)
        items = [f"Summarized Context: {summary}"]
        items.extend(str(x) for x in (messages or []) if isinstance(x, str) and x.strip())
        items = items[-self.max_items :]
        if self._use_fallback:
            self._fallback[k] = items
            return
        try:
            await self.redis.delete(k)
            if items:
                await self.redis.rpush(k, *items)
                await self._refresh_ttl(k)
        except (redis.exceptions.ConnectionError, OSError):
            self._use_fallback = True
            self._fallback[k] = items

    async def seed_from_messages(self, chat_id: int, messages: List[str]) -> None:
        # Replace list with an ordered set of recent message items.
        k = self.key(chat_id)
        items = [str(x) for x in (messages or []) if isinstance(x, str) and x.strip()]
        if self._use_fallback:
            self._fallback[k] = items[-self.max_items :]
            return
        try:
            await self.redis.delete(k)
            if items:
                await self.redis.rpush(k, *items[-self.max_items :])
                await self._refresh_ttl(k)
        except (redis.exceptions.ConnectionError, OSError):
            self._use_fallback = True
            self._fallback[k] = items[-self.max_items :]

    async def trim(self, chat_id: int) -> None:
        # Keep only the last N items.
        k = self.key(chat_id)
        if self._use_fallback:
            items = self._fallback.get(k, [])
            self._fallback[k] = items[-self.max_items :]
            return
        try:
            await self.redis.ltrim(k, -self.max_items, -1)
        except (redis.exceptions.ConnectionError, OSError):
            self._use_fallback = True
            items = self._fallback.get(k, [])
            self._fallback[k] = items[-self.max_items :]

    async def clear(self, chat_id: int) -> None:
        """
        Delete all ephemeral chat memory for a chat (Redis key + fallback).
        """
        k = self.key(chat_id)
        # Always clear fallback as well.
        self._fallback.pop(k, None)
        if self._use_fallback:
            return
        try:
            await self.redis.delete(k)
        except (redis.exceptions.ConnectionError, OSError):
            self._use_fallback = True
            self._fallback.pop(k, None)


