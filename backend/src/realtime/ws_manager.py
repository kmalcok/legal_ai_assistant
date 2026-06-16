from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, Set

import redis.asyncio as aioredis
import redis.exceptions
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

from ..config import agent_config


class ChatWSManager:
    """
    Websocket pub/sub for chat:{chat_id}.

    - Always supports in-process delivery.
    - If Redis is available, also broadcasts via Redis PubSub so multi-worker
      deployments deliver events to sockets connected to *other* processes.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._conns: Dict[int, Set[WebSocket]] = {}
        self._sender_id = uuid.uuid4().hex
        self._redis = aioredis.Redis.from_url(agent_config().redis_url, decode_responses=True)
        self._use_redis_fallback: bool = False
        self._pubsub_task: asyncio.Task[None] | None = None

    @staticmethod
    def _redis_channel(chat_id: int) -> str:
        return f"ws:chat:{int(chat_id)}"

    async def _ensure_pubsub_task(self) -> None:
        if self._use_redis_fallback:
            return
        if self._pubsub_task and not self._pubsub_task.done():
            return
        # Start (or restart) subscriber task lazily within an event loop.
        self._pubsub_task = asyncio.create_task(self._redis_pubsub_loop())

    async def _redis_pubsub_loop(self) -> None:
        """
        Subscribe to ws:chat:* and forward events to local sockets.
        """
        try:
            pubsub = self._redis.pubsub()
            await pubsub.psubscribe("ws:chat:*")
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg:
                    await asyncio.sleep(0.05)
                    continue
                data = msg.get("data")
                if not isinstance(data, str) or not data:
                    continue
                try:
                    payload = json.loads(data)
                except Exception:
                    continue
                if payload.get("sender") == self._sender_id:
                    continue
                chat_id = payload.get("chat_id")
                event = payload.get("event")
                if chat_id is None or not isinstance(event, dict):
                    continue
                await self._publish_local(int(chat_id), event)
        except asyncio.CancelledError:
            raise
        except (redis.exceptions.ConnectionError, OSError):
            # Fall back silently to in-process only.
            self._use_redis_fallback = True
        except Exception:
            # Don't crash the app on pubsub failures.
            self._use_redis_fallback = True

    async def connect(self, chat_id: int, ws: WebSocket, *, subprotocol: str | None = None) -> None:
        if subprotocol:
            await ws.accept(subprotocol=subprotocol)
        else:
            await ws.accept()
        await self._ensure_pubsub_task()
        async with self._lock:
            self._conns.setdefault(int(chat_id), set()).add(ws)

    async def disconnect(self, chat_id: int, ws: WebSocket) -> None:
        async with self._lock:
            s = self._conns.get(int(chat_id))
            if not s:
                return
            s.discard(ws)
            if not s:
                self._conns.pop(int(chat_id), None)

    async def _publish_local(self, chat_id: int, event: Dict[str, Any]) -> int:
        async with self._lock:
            targets = list(self._conns.get(int(chat_id), set()))
        sent = 0
        for ws in targets:
            try:
                # Ensure JSON-serializable payload (dates/datetimes, sets, etc.)
                await ws.send_json(jsonable_encoder(event))
                sent += 1
            except Exception:
                # drop dead sockets
                try:
                    await self.disconnect(int(chat_id), ws)
                except Exception:
                    pass
        return sent

    async def publish(self, chat_id: int, event: Dict[str, Any]) -> int:
        """
        Publish an event to the chat channel.
        Returns number of *local* sockets successfully sent to.
        """
        await self._ensure_pubsub_task()
        sent_local = await self._publish_local(int(chat_id), event)
        if not self._use_redis_fallback:
            try:
                payload = {"sender": self._sender_id, "chat_id": int(chat_id), "event": event}
                await self._redis.publish(self._redis_channel(int(chat_id)), json.dumps(payload, ensure_ascii=False))
            except (redis.exceptions.ConnectionError, OSError):
                self._use_redis_fallback = True
            except Exception:
                # Ignore publish errors (best effort).
                pass
        return int(sent_local)

    async def stats(self, chat_id: int | None = None) -> Dict[str, Any]:
        """
        Debug helper: connection counts + redis status.
        """
        async with self._lock:
            chats = {int(k): len(v) for k, v in self._conns.items()}
        out: Dict[str, Any] = {
            "redis_url": agent_config().redis_url,
            "redis_fallback": bool(self._use_redis_fallback),
            "connected_chats": len(chats),
            "connections_by_chat": chats,
        }
        if chat_id is not None:
            out["chat_id"] = int(chat_id)
            out["connections_for_chat"] = int(chats.get(int(chat_id), 0))
        return out


chat_ws_manager = ChatWSManager()


