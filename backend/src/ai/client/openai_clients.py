from __future__ import annotations

import asyncio

import httpx
from agents import MultiProvider, RunConfig, set_default_openai_client, set_default_openai_key
from openai import AsyncOpenAI

from ...config import agent_config, load_env
from ..util.rotator import get_next_openai_api_key

_openai_clients_lock = asyncio.Lock()
_openai_clients_by_env_name: dict[str, tuple[str, AsyncOpenAI]] = {}


def _build_http_client() -> httpx.AsyncClient:
    cfg = agent_config()
    limits = httpx.Limits(
        max_connections=int(cfg.openai_http_max_connections),
        max_keepalive_connections=int(cfg.openai_http_max_keepalive_connections),
    )
    return httpx.AsyncClient(
        timeout=httpx.Timeout(float(cfg.openai_http_timeout_seconds)),
        limits=limits,
        follow_redirects=True,
    )


def _build_openai_client(*, api_key: str) -> AsyncOpenAI:
    load_env()
    cfg = agent_config()
    return AsyncOpenAI(
        api_key=api_key,
        http_client=_build_http_client(),
        max_retries=int(cfg.openai_http_max_retries),
    )


async def _get_openai_client_for_binding(*, env_name: str, api_key: str) -> AsyncOpenAI:
    cached = _openai_clients_by_env_name.get(env_name)
    if cached is not None and cached[0] == api_key:
        return cached[1]
    async with _openai_clients_lock:
        cached = _openai_clients_by_env_name.get(env_name)
        if cached is not None and cached[0] == api_key:
            return cached[1]
        if cached is not None:
            try:
                await cached[1].close()
            except Exception:
                pass
        client = _build_openai_client(api_key=api_key)
        _openai_clients_by_env_name[env_name] = (api_key, client)
        return client


async def _get_rotating_openai_client() -> AsyncOpenAI:
    load_env()
    env_name, api_key = get_next_openai_api_key()
    return await _get_openai_client_for_binding(env_name=env_name, api_key=api_key)


async def get_openai_responses_client() -> AsyncOpenAI:
    return await _get_rotating_openai_client()


async def get_openai_embeddings_client() -> AsyncOpenAI:
    return await _get_rotating_openai_client()


async def build_agents_run_config() -> RunConfig:
    load_env()
    env_name, api_key = get_next_openai_api_key()
    client = await _get_openai_client_for_binding(env_name=env_name, api_key=api_key)
    # Configure the SDK-wide defaults so any internal lazy provider path
    # resolves our rotating client instead of falling back to OPENAI_API_KEY.
    set_default_openai_key(api_key, use_for_tracing=False)
    set_default_openai_client(client, use_for_tracing=False)
    return RunConfig(model_provider=MultiProvider(openai_client=client))


async def close_openai_clients() -> None:
    async with _openai_clients_lock:
        clients = [client for _, client in _openai_clients_by_env_name.values()]
        _openai_clients_by_env_name.clear()
    for client in clients:
        try:
            await client.close()
        except Exception:
            pass
