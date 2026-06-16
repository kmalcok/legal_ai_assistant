from __future__ import annotations
import datetime
import json
import time
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
import redis.exceptions

from ...config import agent_config
from ...utils.dev_logging import dev_log, dev_log_exception
from ...utils.ictihat_format import daire_label, normalize_kurum
from .ictihat_repository import fetch_document_chunks, lookup_document_ids
from .ictihat_text import stitch_decision_text


def _normalize_ws(s: str) -> str:
    return " ".join((s or "").replace("\x00", " ").split()).strip()


def _iso_date(v: Any) -> Any:
    if isinstance(v, (datetime.date, datetime.datetime)):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    return v


_DOC_CACHE_TTL_SECONDS = 24 * 3600
_DOC_CACHE_KEY_PREFIX = "ictihat:document:v3:"
_doc_cache_fallback: Dict[str, Dict[str, Any]] = {}
_doc_cache_use_fallback: bool = False
_doc_cache_redis: Optional[aioredis.Redis] = None


def _doc_cache_key(document_id: int) -> str:
    return f"{_DOC_CACHE_KEY_PREFIX}{int(document_id)}"


async def _doc_cache_client() -> aioredis.Redis:
    global _doc_cache_redis
    if _doc_cache_redis is not None:
        return _doc_cache_redis
    cfg = agent_config()
    _doc_cache_redis = aioredis.Redis.from_url(cfg.redis_url, decode_responses=True)
    return _doc_cache_redis


async def close_doc_cache_client() -> None:
    global _doc_cache_redis
    client = _doc_cache_redis
    _doc_cache_redis = None
    if client is None:
        return
    try:
        await client.aclose()
    except Exception:
        pass


def _doc_cache_fallback_get(key: str) -> Optional[Dict[str, Any]]:
    obj = _doc_cache_fallback.get(key)
    if not isinstance(obj, dict):
        return None
    try:
        if float(obj.get("_expires_at_ts") or 0) < time.time():
            _doc_cache_fallback.pop(key, None)
            return None
    except Exception:
        return None
    return obj


def _normalize_cached_doc(obj: Dict[str, Any]) -> Dict[str, Any]:
    try:
        doc = obj.get("doc")
        if not isinstance(doc, dict):
            return obj
        normalized_kurum = normalize_kurum(doc.get("kurum"), daire=doc.get("daire"))
        if normalized_kurum:
            doc["kurum"] = normalized_kurum
        if "daire_label" not in doc:
            doc["daire_label"] = daire_label(kurum=doc.get("kurum"), daire=doc.get("daire"))
        obj["doc"] = doc
    except Exception:
        return obj
    return obj


async def _doc_cache_get(document_id: int) -> Optional[Dict[str, Any]]:
    global _doc_cache_use_fallback
    key = _doc_cache_key(document_id)
    if _doc_cache_use_fallback:
        return _doc_cache_fallback_get(key)
    raw = None
    try:
        r = await _doc_cache_client()
        raw = await r.get(key)
    except (redis.exceptions.ConnectionError, OSError):
        _doc_cache_use_fallback = True
        return _doc_cache_fallback_get(key)
    except Exception:
        return None
    if not raw:
        return None
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(obj, dict):
            return None
        return _normalize_cached_doc(obj)
    except Exception:
        return None


async def _doc_cache_put(document_id: int, payload: Dict[str, Any]) -> None:
    global _doc_cache_use_fallback
    key = _doc_cache_key(document_id)
    skip_fallback_store = False
    try:
        skip_fallback_store = isinstance(payload.get("text"), str) and len(payload["text"]) > 300_000
    except Exception:
        skip_fallback_store = False
    if _doc_cache_use_fallback:
        if skip_fallback_store:
            return
        try:
            _doc_cache_fallback[key] = dict(payload, _expires_at_ts=float(time.time() + _DOC_CACHE_TTL_SECONDS))
        except Exception:
            pass
        return
    try:
        r = await _doc_cache_client()
        await r.set(key, json.dumps(payload, ensure_ascii=False), ex=int(_DOC_CACHE_TTL_SECONDS))
    except (redis.exceptions.ConnectionError, OSError):
        _doc_cache_use_fallback = True
        if skip_fallback_store:
            return
        try:
            _doc_cache_fallback[key] = dict(payload, _expires_at_ts=float(time.time() + _DOC_CACHE_TTL_SECONDS))
        except Exception:
            pass
    except Exception:
        return


async def ictihat_get_document(
    *,
    user_id: int,
    chat_id: int,
    document_id: int = 0,
    kurum: str | None = None,
    daire: str | None = None,
    karar_no: int | None = None,
    karar_sira: int | None = None,
    emsal_no: str | int | None = None,
    emsal_sira: str | int | None = None,
    karar_tarihi: str | None = None,
) -> Dict[str, Any]:
    t0 = time.time()
    latency_breakdown = {
        "lookup_ms": 0,
        "cache_read_ms": 0,
        "fetch_ms": 0,
        "stitch_ms": 0,
        "cache_write_ms": 0,
    }
    try:
        did = int(document_id or 0)
    except Exception:
        did = 0

    if did <= 0:
        try:
            t_lookup0 = time.perf_counter()
            candidates = await lookup_document_ids(
                kurum=kurum,
                daire=daire,
                karar_no=karar_no,
                karar_sira=karar_sira,
                emsal_no=emsal_no,
                emsal_sira=emsal_sira,
                karar_tarihi=karar_tarihi,
                limit=6,
            )
            latency_breakdown["lookup_ms"] = int((time.perf_counter() - t_lookup0) * 1000)
        except Exception as exc:
            dev_log_exception(
                "ictihat",
                "ictihat_get_document_lookup_elasticsearch_error",
                {
                    "kurum": kurum,
                    "daire": daire,
                    "karar_no": karar_no,
                    "karar_sira": karar_sira,
                    "karar_tarihi": karar_tarihi,
                },
                exc,
            )
            raise

        if not candidates:
            return {
                "ok": False,
                "reason": "not_found",
                "filters": {
                    "kurum": normalize_kurum(kurum, daire=daire),
                    "daire": daire,
                    "karar_no": karar_no,
                    "karar_sira": karar_sira,
                    "karar_tarihi": karar_tarihi,
                    "emsal_no": emsal_no,
                    "emsal_sira": emsal_sira,
                },
            }
        if len(candidates) > 1:
            return {
                "ok": False,
                "reason": "ambiguous",
                "candidates": candidates[:10],
                "filters": {
                    "kurum": normalize_kurum(kurum, daire=daire),
                    "daire": daire,
                    "karar_no": karar_no,
                    "karar_sira": karar_sira,
                    "karar_tarihi": karar_tarihi,
                    "emsal_no": emsal_no,
                    "emsal_sira": emsal_sira,
                },
            }
        did = int(candidates[0])

    try:
        t_cache0 = time.perf_counter()
        cached = await _doc_cache_get(int(did))
        latency_breakdown["cache_read_ms"] = int((time.perf_counter() - t_cache0) * 1000)
        if isinstance(cached, dict) and cached.get("document_id") == int(did) and isinstance(cached.get("text"), str):
            out_cached: Dict[str, Any] = {
                "ok": True,
                "doc": cached.get("doc"),
                "chunk_count": int(cached.get("chunk_count") or 0),
                "total_chars": int(cached.get("total_chars") or 0),
                "text": str(cached.get("text") or ""),
                "note": "Full text included.",
                "cache": {"hit": True},
            }
            dev_log(
                "ictihat",
                "ictihat_get_document_cache_hit",
                {
                    "document_id": int(did),
                    "duration_ms": int((time.time() - t0) * 1000),
                    "latency_breakdown_ms": latency_breakdown,
                },
            )
            return out_cached
    except Exception:
        pass

    t_fetch0 = time.time()
    try:
        rows = await fetch_document_chunks(int(did))
    except Exception as exc:
        dev_log_exception("ictihat", "ictihat_get_document_elasticsearch_error", {"document_id": int(did)}, exc)
        raise
    t_fetch1 = time.time()
    latency_breakdown["fetch_ms"] = int((t_fetch1 - t_fetch0) * 1000)

    if not rows:
        return {"ok": False, "reason": "not_found", "document_id": int(did)}

    header = rows[0]
    chunk_count = len(rows)
    total_chars = 0
    for row in rows:
        txt = row.get("rag_text") or ""
        if not isinstance(txt, str):
            txt = str(txt)
        total_chars += len(txt)

    t_st0 = time.time()
    st = stitch_decision_text([(row.get("rag_text") or "") for row in rows], limit_chars=None)
    stitched = st.text
    stitched = _normalize_ws(stitched) if "\n" not in stitched else stitched.strip()
    t_st1 = time.time()
    latency_breakdown["stitch_ms"] = int((t_st1 - t_st0) * 1000)

    out: Dict[str, Any] = {
        "ok": True,
        "doc": {
            "document_id": int(did),
            "kurum": header.get("kurum"),
            "daire": header.get("daire"),
            "daire_label": daire_label(kurum=header.get("kurum"), daire=header.get("daire")),
            "esas": {"yil": header.get("esas_yil"), "sira": header.get("esas_sira")},
            "karar": {
                "yil": header.get("karar_yil"),
                "sira": header.get("karar_sira"),
                "tarih": _iso_date(header.get("karar_tarihi")),
            },
        },
        "chunk_count": int(chunk_count),
        "total_chars": int(total_chars),
        "text": stitched,
        "note": "Full text included.",
    }
    try:
        t_cachew0 = time.perf_counter()
        await _doc_cache_put(
            int(did),
            {
                "document_id": int(did),
                "doc": out.get("doc"),
                "chunk_count": int(chunk_count),
                "total_chars": int(total_chars),
                "text": stitched,
            },
        )
        latency_breakdown["cache_write_ms"] = int((time.perf_counter() - t_cachew0) * 1000)
    except Exception:
        pass
    dev_log(
        "ictihat",
        "ictihat_get_document_done",
        {
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "document_id": int(did),
            "duration_ms": int((time.time() - t0) * 1000),
            "fetch_ms": int((t_fetch1 - t_fetch0) * 1000),
            "stitch_ms": int((t_st1 - t_st0) * 1000),
            "chunk_count": int(chunk_count),
            "total_chars": int(total_chars),
            "stitched_chars": int(len(stitched or "")),
            "latency_breakdown_ms": latency_breakdown,
        },
    )
    return out
