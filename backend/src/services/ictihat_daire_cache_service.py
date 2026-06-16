from __future__ import annotations

import json
from typing import Any, Dict, List

import redis.asyncio as aioredis
import redis.exceptions

from ..ai.tool_wrappers.ictihat_repository import load_unique_daire_names
from ..config import agent_config
from ..utils.ictihat_format import daire_label, normalize_kurum

_DAIRE_CACHE_KEY = "ictihat:daire_names:v4:all"
_daire_fallback: List[Dict[str, Any]] = []


async def _redis_client() -> aioredis.Redis:
    cfg = agent_config()
    return aioredis.Redis.from_url(cfg.redis_url, decode_responses=True)


async def _load_daire_names_from_search() -> List[Dict[str, Any]]:
    rows = await load_unique_daire_names()
    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        daire = str(r.get("daire") or "").strip() or None
        kurum = normalize_kurum(r.get("kurum"), daire=daire)
        if not kurum:
            continue
        out.append(
            {
                "kurum": kurum,
                "daire": daire,
                "daire_label": daire_label(kurum=kurum, daire=daire),
            }
        )
    return out


async def warm_ictihat_daire_cache() -> None:
    """
    Best-effort: refresh distinct daire names into Redis at startup.
    Falls back to in-process memory if Redis is unavailable.
    """
    global _daire_fallback
    try:
        items = await _load_daire_names_from_search()
    except Exception:
        items = []

    if items:
        _daire_fallback = list(items)
    try:
        client = await _redis_client()
        try:
            await client.set(_DAIRE_CACHE_KEY, json.dumps(items, ensure_ascii=False), ex=24 * 3600)
        finally:
            await client.aclose()
    except (redis.exceptions.ConnectionError, OSError):
        return
    except Exception:
        return


async def get_cached_ictihat_daire_names() -> Dict[str, Any]:
    # Try Redis first.
    try:
        client = await _redis_client()
        try:
            raw = await client.get(_DAIRE_CACHE_KEY)
        finally:
            await client.aclose()
        if raw:
            try:
                arr = json.loads(raw)
                if isinstance(arr, list):
                    items = [x for x in arr if isinstance(x, dict)]
                    names = [str(x.get("daire_label") or "") for x in items if str(x.get("daire_label") or "").strip()]
                    return {"ok": True, "items": items, "names": names}
            except Exception:
                pass
    except (redis.exceptions.ConnectionError, OSError):
        pass
    except Exception:
        pass

    items = list(_daire_fallback or [])
    names = [str(x.get("daire_label") or "") for x in items if isinstance(x, dict) and str(x.get("daire_label") or "").strip()]
    return {"ok": True, "items": items, "names": names}
