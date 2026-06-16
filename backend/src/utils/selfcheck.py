from __future__ import annotations

import argparse
import asyncio

import httpx

from ..ai.memory.redis_memory import RedisMemory
from ..config import agent_config
from ..config import load_env
from ..db import core_db

_BACKEND_QUERY_TIMEOUT_SECONDS = 20


def _build_backend_async_client(*, timeout_seconds: float, verify: bool = True, auth: tuple[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        verify=verify,
        auth=auth,
        follow_redirects=True,
    )


def _check_mysql(label: str, cm, tables: list[str]) -> None:
    try:
        with cm() as conn:
            cur = conn.cursor()
            for t in tables:
                cur.execute(f"SELECT 1 FROM {t} LIMIT 1")
                cur.fetchone()
            print(f"{label}: OK")
    except Exception as exc:
        print(f"{label}: NOT OK ({exc})")
        raise


async def _check_elasticsearch() -> None:
    cfg = agent_config()
    base_url = str(cfg.elasticsearch_url or "").strip().rstrip("/")
    index_name = str(cfg.elasticsearch_index_ictihat or "").strip()
    if not base_url or not index_name:
        raise RuntimeError("missing_elasticsearch_config")
    headers = {"Content-Type": "application/json"}
    auth = None
    api_key = str(cfg.elasticsearch_api_key or "").strip()
    username = str(cfg.elasticsearch_username or "").strip()
    password = str(cfg.elasticsearch_password or "").strip()
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    elif username or password:
        auth = (username, password)
    async with _build_backend_async_client(
        timeout_seconds=float(_BACKEND_QUERY_TIMEOUT_SECONDS),
        verify=bool(cfg.elasticsearch_verify_certs),
        auth=auth,
    ) as client:
        response = await client.post(
            f"{base_url}/{index_name}/_count",
            headers=headers,
            json={"query": {"match_all": {}}},
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or payload.get("count") is None:
        raise RuntimeError("invalid_elasticsearch_response")
    print("Elasticsearch: OK")


async def _check_qdrant() -> None:
    cfg = agent_config()
    base_url = str(cfg.qdrant_url or "").strip().rstrip("/")
    collection = str(cfg.qdrant_index_ictihat or "").strip()
    if not base_url or not collection:
        raise RuntimeError("missing_qdrant_config")
    headers = {}
    api_key = str(cfg.qdrant_api_key or "").strip()
    if api_key:
        headers["api-key"] = api_key
    async with _build_backend_async_client(timeout_seconds=float(_BACKEND_QUERY_TIMEOUT_SECONDS)) as client:
        response = await client.get(
            f"{base_url}/collections/{collection}",
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise RuntimeError("invalid_qdrant_response")
    print("Qdrant: OK")


async def main_async() -> None:
    load_env()
    mem = RedisMemory()
    try:
        await mem.redis.ping()
        print("Redis: OK")
    except Exception as exc:
        print(f"Redis: NOT AVAILABLE ({exc}) - will fall back to in-process memory for CLI")

    await _check_elasticsearch()
    await _check_qdrant()

    # Single DB (mevzuat): check application tables only.
    _check_mysql(
        "DB",
        core_db,
        [
            "users",
            "chats",
            "chat_messages",
            "user_usages",
        ],
    )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()


