from __future__ import annotations

import asyncio
import json
import time
from functools import lru_cache
from typing import Any, Dict, List, Tuple

import httpx

from ...config import agent_config, load_env
from ...utils.ictihat_format import normalize_kurum


_ES_SOURCE_FIELDS = [
    "document_id",
    "chunk_id",
    "kurum",
    "daire",
    "emsal",
    "esas_no",
    "esas_yil",
    "esas_sira",
    "karar_no",
    "karar_yil",
    "karar_sira",
    "karar_tarihi",
    "rag_text",
]
_HTTP_POOL_CONNECTIONS = 32
_HTTP_POOL_MAXSIZE = 64
_ELASTICSEARCH_TIMEOUT_SECONDS = 30
_QDRANT_TIMEOUT_SECONDS = 30
_http_clients_lock = asyncio.Lock()
_elasticsearch_client: httpx.AsyncClient | None = None
_qdrant_client: httpx.AsyncClient | None = None


def _normalize_keyword_query(query: str) -> str:
    return " ".join(str(query or "").strip().split())


def _normalize_filters(filters: Dict[str, Any] | None) -> Dict[str, Any]:
    return dict(filters or {})


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_only(value: Any) -> str | None:
    text = _string_or_none(value)
    if not text:
        return None
    return text[:10]


def _normalize_row(source: Dict[str, Any], *, score: float | None = None, distance: float | None = None) -> Dict[str, Any] | None:
    if not isinstance(source, dict):
        return None
    document_id = _int_or_none(source.get("document_id"))
    chunk_id = _int_or_none(source.get("chunk_id"))
    if document_id is None or chunk_id is None:
        return None
    row: Dict[str, Any] = {
        "document_id": int(document_id),
        "chunk_id": int(chunk_id),
        "kurum": normalize_kurum(_string_or_none(source.get("kurum")), daire=_string_or_none(source.get("daire"))),
        "daire": _string_or_none(source.get("daire")),
        "esas_yil": _int_or_none(source.get("esas_yil")),
        "esas_sira": _int_or_none(source.get("esas_sira")),
        "karar_yil": _int_or_none(source.get("karar_yil")),
        "karar_sira": _int_or_none(source.get("karar_sira")),
        "karar_tarihi": _date_only(source.get("karar_tarihi")),
        "rag_text": str(source.get("rag_text") or ""),
    }
    if score is not None:
        row["score"] = float(score)
    if distance is not None:
        row["distance"] = float(distance)
    return row


@lru_cache(maxsize=1)
def _ictihat_elasticsearch_config() -> tuple[str, dict[str, str], bool, tuple[str, str] | None]:
    load_env()
    cfg = agent_config()
    base_url = str(cfg.elasticsearch_url or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("elasticsearch_unavailable")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    auth: tuple[str, str] | None = None
    api_key = str(cfg.elasticsearch_api_key or "").strip()
    username = str(cfg.elasticsearch_username or "").strip()
    password = str(cfg.elasticsearch_password or "").strip()
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    elif username or password:
        auth = (username, password)
    return base_url, headers, bool(cfg.elasticsearch_verify_certs), auth


@lru_cache(maxsize=1)
def _qdrant_http_config() -> tuple[str, dict[str, str]]:
    load_env()
    cfg = agent_config()
    url = str(cfg.qdrant_url or "").strip().rstrip("/")
    if not url:
        raise RuntimeError("qdrant_unavailable")
    headers = {"Content-Type": "application/json"}
    api_key = str(cfg.qdrant_api_key or "").strip()
    if api_key:
        headers["api-key"] = api_key
    return url, headers


def _ictihat_index_name() -> str:
    cfg = agent_config()
    index_name = str(cfg.elasticsearch_index_ictihat or "").strip()
    if not index_name:
        raise RuntimeError("elasticsearch_unavailable")
    return index_name


def _build_async_client(
    *,
    timeout_seconds: float,
    verify: bool = True,
    auth: tuple[str, str] | None = None,
) -> httpx.AsyncClient:
    limits = httpx.Limits(
        max_connections=int(_HTTP_POOL_MAXSIZE),
        max_keepalive_connections=int(_HTTP_POOL_CONNECTIONS),
    )
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        verify=verify,
        auth=auth,
        limits=limits,
        follow_redirects=True,
    )


async def _elasticsearch_async_client() -> httpx.AsyncClient:
    global _elasticsearch_client
    client = _elasticsearch_client
    if client is not None:
        return client
    _base_url, _headers, verify, auth = _ictihat_elasticsearch_config()
    async with _http_clients_lock:
        if _elasticsearch_client is None:
            _elasticsearch_client = _build_async_client(
                timeout_seconds=float(_ELASTICSEARCH_TIMEOUT_SECONDS),
                verify=verify,
                auth=auth,
            )
        return _elasticsearch_client


async def _qdrant_async_client() -> httpx.AsyncClient:
    global _qdrant_client
    client = _qdrant_client
    if client is not None:
        return client
    async with _http_clients_lock:
        if _qdrant_client is None:
            _qdrant_client = _build_async_client(timeout_seconds=float(_QDRANT_TIMEOUT_SECONDS))
        return _qdrant_client


async def close_ictihat_search_clients() -> None:
    global _elasticsearch_client, _qdrant_client
    async with _http_clients_lock:
        clients = [client for client in (_elasticsearch_client, _qdrant_client) if client is not None]
        _elasticsearch_client = None
        _qdrant_client = None
    for client in clients:
        try:
            await client.aclose()
        except Exception:
            pass


def _empty_backend_timing() -> Dict[str, int]:
    return {
        "elasticsearch_ms": 0,
        "qdrant_ms": 0,
        "hydration_ms": 0,
    }


async def _elasticsearch_request(*, path: str, json_body: dict[str, Any]) -> Dict[str, Any]:
    base_url, headers, _verify, _auth = _ictihat_elasticsearch_config()
    try:
        client = await _elasticsearch_async_client()
        response = await client.post(
            f"{base_url}/{path.lstrip('/')}",
            headers=headers,
            json=json_body,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        raise RuntimeError("elasticsearch_unavailable") from exc


def _qdrant_collection_name() -> str:
    cfg = agent_config()
    name = str(cfg.qdrant_index_ictihat or "").strip()
    if not name:
        raise RuntimeError("qdrant_unavailable")
    return name


def _es_meta_filter_clauses(filters: Dict[str, Any] | None) -> list[dict[str, Any]]:
    f = _normalize_filters(filters)
    clauses: list[dict[str, Any]] = []

    kurum = normalize_kurum(_string_or_none(f.get("kurum") or f.get("court")), daire=_string_or_none(f.get("daire")))
    if kurum:
        clauses.append({"term": {"kurum": kurum}})

    daire = _string_or_none(f.get("daire"))
    if daire:
        clauses.append({"term": {"daire.raw": daire}})

    for key in ("esas_yil", "esas_sira", "karar_yil", "karar_sira"):
        value = _int_or_none(f.get(key))
        if value is not None:
            clauses.append({"term": {key: value}})

    karar_tarihi = _date_only(f.get("karar_tarihi"))
    if karar_tarihi:
        clauses.append({"term": {"karar_tarihi": karar_tarihi}})

    date_range: dict[str, Any] = {}
    tarih_from = _date_only(f.get("karar_tarihi_from"))
    if tarih_from:
        date_range["gte"] = tarih_from
    tarih_to = _date_only(f.get("karar_tarihi_to"))
    if tarih_to:
        date_range["lte"] = tarih_to
    if date_range:
        clauses.append({"range": {"karar_tarihi": date_range}})
    return clauses


def _qdrant_filter_must(filters: Dict[str, Any] | None) -> list[dict[str, Any]]:
    f = _normalize_filters(filters)
    must: list[dict[str, Any]] = []

    kurum = normalize_kurum(_string_or_none(f.get("kurum") or f.get("court")), daire=_string_or_none(f.get("daire")))
    if kurum:
        must.append({"key": "kurum", "match": {"value": kurum}})

    daire = _string_or_none(f.get("daire"))
    if daire:
        must.append({"key": "daire", "match": {"value": daire}})

    for key in ("esas_yil", "esas_sira", "karar_yil", "karar_sira"):
        value = _int_or_none(f.get(key))
        if value is not None:
            must.append({"key": key, "match": {"value": value}})

    karar_tarihi = _date_only(f.get("karar_tarihi"))
    if karar_tarihi:
        must.append(
            {
                "key": "karar_tarihi",
                "range": {
                    "gte": f"{karar_tarihi}T00:00:00",
                    "lte": f"{karar_tarihi}T23:59:59",
                },
            }
        )

    tarih_from = _date_only(f.get("karar_tarihi_from"))
    if tarih_from:
        must.append({"key": "karar_tarihi", "range": {"gte": tarih_from}})

    tarih_to = _date_only(f.get("karar_tarihi_to"))
    if tarih_to:
        must.append({"key": "karar_tarihi", "range": {"lte": tarih_to}})
    return must


def has_citation_filters(filters: Dict[str, Any] | None) -> bool:
    f = _normalize_filters(filters)
    return any(
        f.get(key) is not None
        for key in ("esas_yil", "esas_sira", "karar_yil", "karar_sira", "karar_tarihi")
    )


def _normalize_key_pairs(keys: List[Any]) -> List[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for item in keys or []:
        try:
            if isinstance(item, dict):
                did = int(item.get("document_id"))
                cid = int(item.get("chunk_id"))
            else:
                did = int(item[0])
                cid = int(item[1])
        except Exception:
            continue
        key = (did, cid)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


async def _search_elasticsearch(
    *,
    query: dict[str, Any],
    size: int,
    sort: list[dict[str, Any]] | None = None,
) -> tuple[List[Dict[str, Any]], int]:
    t0 = time.perf_counter()
    body: dict[str, Any] = {
        "size": int(size),
        "track_total_hits": False,
        "query": query,
        "_source": list(_ES_SOURCE_FIELDS),
    }
    if sort:
        body["sort"] = sort
    payload = await _elasticsearch_request(path=f"{_ictihat_index_name()}/_search", json_body=body)
    hits = (((payload or {}).get("hits") or {}).get("hits") or [])
    out: list[Dict[str, Any]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        row = _normalize_row(hit.get("_source") or {}, score=hit.get("_score"))
        if row:
            out.append(row)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return out, elapsed_ms


async def _fetch_rows_by_keys(keys: List[Any]) -> tuple[List[Dict[str, Any]], int]:
    norm_keys = _normalize_key_pairs(keys)
    if not norm_keys:
        return [], 0
    t0 = time.perf_counter()
    rows: list[Dict[str, Any]] = []
    batch_size = 128
    for i in range(0, len(norm_keys), batch_size):
        batch = norm_keys[i : i + batch_size]
        should = [
            {
                "bool": {
                    "filter": [
                        {"term": {"document_id": did}},
                        {"term": {"chunk_id": cid}},
                    ]
                }
            }
            for did, cid in batch
        ]
        batch_rows, _ = await _search_elasticsearch(
            query={"bool": {"should": should, "minimum_should_match": 1}},
            size=len(batch),
        )
        rows.extend(batch_rows)
    by_key = {(int(row["document_id"]), int(row["chunk_id"])): row for row in rows}
    ordered: list[Dict[str, Any]] = []
    for did, cid in norm_keys:
        row = by_key.get((did, cid))
        if row:
            ordered.append(row)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    return ordered, elapsed_ms


async def merge_candidate_rows(
    candidates: List[Dict[str, Any]],
    *,
    metric_name: str,
    limit: int,
) -> tuple[List[Dict[str, Any]], int]:
    metric_key = str(metric_name or "").strip()
    if not candidates:
        return [], 0
    ordered_keys = _normalize_key_pairs(candidates)
    hydrated_rows, hydration_ms = await _fetch_rows_by_keys(ordered_keys)
    row_map = {(int(row["document_id"]), int(row["chunk_id"])): row for row in hydrated_rows}
    merged: list[Dict[str, Any]] = []
    for cand in candidates:
        did = _int_or_none(cand.get("document_id"))
        cid = _int_or_none(cand.get("chunk_id"))
        if did is None or cid is None:
            continue
        row = row_map.get((did, cid))
        if not row:
            continue
        merged_row = dict(row)
        for key, value in cand.items():
            if key in {"document_id", "chunk_id"}:
                continue
            merged_row[key] = value
        if metric_key and metric_key not in merged_row:
            merged_row[metric_key] = None
        merged.append(merged_row)
        if len(merged) >= int(limit):
            break
    return merged, int(hydration_ms)


async def fetch_document_chunks(document_id: int) -> List[Dict[str, Any]]:
    did = _int_or_none(document_id)
    if did is None or did <= 0:
        return []
    # Full decisions can be large; fetch in reasonably sized batches.
    size = 1000
    offset = 0
    out: list[Dict[str, Any]] = []
    while True:
        payload = await _elasticsearch_request(
            path=f"{_ictihat_index_name()}/_search",
            json_body={
                "size": size,
                "from": offset,
                "query": {"term": {"document_id": int(did)}},
                "sort": [{"chunk_id": {"order": "asc"}}],
                "_source": list(_ES_SOURCE_FIELDS),
            },
        )
        hits = (((payload or {}).get("hits") or {}).get("hits") or [])
        if not hits:
            break
        batch_count = 0
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            row = _normalize_row(hit.get("_source") or {}, score=hit.get("_score"))
            if row:
                out.append(row)
                batch_count += 1
        if batch_count < size:
            break
        offset += size
    return out


async def fetch_stitched_text_rows(document_ids: List[int]) -> List[Dict[str, Any]]:
    ids = [_int_or_none(x) for x in document_ids if x is not None]
    normalized_ids = [int(x) for x in ids if x is not None]
    normalized_ids = list(dict.fromkeys(normalized_ids))
    out: list[Dict[str, Any]] = []
    for document_id in normalized_ids:
        rows = await fetch_document_chunks(int(document_id))
        out.extend(
            {
                "document_id": row["document_id"],
                "chunk_id": row["chunk_id"],
                "rag_text": row.get("rag_text") or "",
            }
            for row in rows
        )
    return out


async def fetch_document_stats(document_ids: List[int]) -> Dict[int, Dict[str, int]]:
    ids = [_int_or_none(x) for x in document_ids if x is not None]
    normalized_ids = [int(x) for x in ids if x is not None]
    normalized_ids = list(dict.fromkeys(normalized_ids))
    if not normalized_ids:
        return {}
    try:
        payload = await _elasticsearch_request(
            path=f"{_ictihat_index_name()}/_search",
            json_body={
                "size": 0,
                "query": {"terms": {"document_id": normalized_ids}},
                "aggs": {
                    "documents": {
                        "terms": {"field": "document_id", "size": len(normalized_ids)},
                        "aggs": {
                            "chunk_count": {"value_count": {"field": "chunk_id"}},
                            "total_chars": {
                                "sum": {
                                    "script": {
                                        "lang": "painless",
                                        "source": "def v = params._source['rag_text']; return v != null ? v.length() : 0;"
                                    }
                                }
                            },
                        },
                    }
                },
            },
        )
        buckets = ((((payload or {}).get("aggregations") or {}).get("documents") or {}).get("buckets") or [])
        stats: Dict[int, Dict[str, int]] = {}
        for bucket in buckets:
            if not isinstance(bucket, dict):
                continue
            document_id = _int_or_none(bucket.get("key"))
            if document_id is None:
                continue
            chunk_count = _int_or_none(((bucket.get("chunk_count") or {}).get("value"))) or 0
            total_chars = _int_or_none(((bucket.get("total_chars") or {}).get("value"))) or 0
            stats[int(document_id)] = {
                "chunk_count": int(chunk_count),
                "total_chars": int(total_chars),
            }
        return stats
    except Exception:
        stats = {}
        for document_id in normalized_ids:
            chunks = await fetch_document_chunks(int(document_id))
            stats[int(document_id)] = {
                "chunk_count": len(chunks),
                "total_chars": sum(len(str(row.get("rag_text") or "")) for row in chunks),
            }
        return stats


async def load_unique_daire_names() -> List[Dict[str, Any]]:
    body = {
        "size": 0,
        "aggs": {
            "kurumlar": {
                "terms": {"field": "kurum", "size": 20},
                "aggs": {
                    "daireler": {"terms": {"field": "daire.raw", "size": 500, "missing": "__NONE__"}},
                },
            }
        },
    }
    payload = await _elasticsearch_request(path=f"{_ictihat_index_name()}/_search", json_body=body)
    buckets = ((((payload or {}).get("aggregations") or {}).get("kurumlar") or {}).get("buckets") or [])
    out: list[Dict[str, Any]] = []
    for kurum_bucket in buckets:
        if not isinstance(kurum_bucket, dict):
            continue
        kurum = normalize_kurum(_string_or_none(kurum_bucket.get("key")))
        daire_buckets = ((kurum_bucket.get("daireler") or {}).get("buckets") or [])
        for daire_bucket in daire_buckets:
            if not isinstance(daire_bucket, dict):
                continue
            daire = _string_or_none(daire_bucket.get("key"))
            if daire == "__NONE__":
                daire = None
            if kurum:
                out.append({"kurum": kurum, "daire": daire})
    out.sort(key=lambda item: (str(item.get("kurum") or ""), str(item.get("daire") or "")))
    return out


async def lookup_document_ids(
    *,
    kurum: str | None = None,
    daire: str | None = None,
    karar_no: int | None = None,
    karar_sira: int | None = None,
    emsal_no: str | int | None = None,
    emsal_sira: str | int | None = None,
    karar_tarihi: str | None = None,
    limit: int = 6,
) -> List[int]:
    filters: dict[str, Any] = {}
    if kurum:
        filters["kurum"] = kurum
    if daire:
        filters["daire"] = daire
    if karar_no is not None:
        filters["karar_yil"] = karar_no
    if karar_sira is not None:
        filters["karar_sira"] = karar_sira
    if karar_tarihi:
        filters["karar_tarihi"] = karar_tarihi

    filter_clauses = _es_meta_filter_clauses(filters)
    must: list[dict[str, Any]] = []
    emsal_no_text = _string_or_none(emsal_no)
    emsal_sira_text = _string_or_none(emsal_sira)
    if emsal_no_text or emsal_sira_text:
        filter_clauses.append({"range": {"chunk_id": {"lte": 5}}})
        should: list[dict[str, Any]] = []
        if emsal_no_text:
            should.extend(
                [
                    {"match_phrase": {"emsal": emsal_no_text}},
                    {"match_phrase": {"rag_text": emsal_no_text}},
                ]
            )
        if emsal_sira_text:
            should.extend(
                [
                    {"match_phrase": {"emsal": emsal_sira_text}},
                    {"match_phrase": {"rag_text": emsal_sira_text}},
                ]
            )
        if should:
            must.append({"bool": {"should": should, "minimum_should_match": 1}})

    if not filter_clauses and not must:
        return []

    rows, _ = await _search_elasticsearch(
        query={"bool": {"filter": filter_clauses, "must": must}},
        size=max(int(limit) * 6, int(limit)),
        sort=[
            {"document_id": {"order": "desc"}},
            {"chunk_id": {"order": "asc"}},
        ],
    )
    out: list[int] = []
    seen: set[int] = set()
    for row in rows:
        did = _int_or_none(row.get("document_id"))
        if did is None or did in seen:
            continue
        seen.add(did)
        out.append(int(did))
        if len(out) >= int(limit):
            break
    return out


async def search_citation_rows(*, filters: Dict[str, Any] | None, limit: int) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    rows, elasticsearch_ms = await _search_elasticsearch(
        query={"bool": {"filter": _es_meta_filter_clauses(filters)}},
        size=int(limit),
        sort=[
            {"document_id": {"order": "asc"}},
            {"chunk_id": {"order": "asc"}},
        ],
    )
    out: list[Dict[str, Any]] = []
    for row in rows:
        citation_row = dict(row)
        citation_row["distance"] = None
        out.append(citation_row)
    timing = _empty_backend_timing()
    timing["elasticsearch_ms"] = int(elasticsearch_ms)
    return out[: int(limit)], timing


async def _search_keyword_candidates(
    query: str,
    *,
    filters: Dict[str, Any] | None,
    limit: int,
) -> tuple[List[Dict[str, Any]], int]:
    normalized_query = _normalize_keyword_query(query)
    if not normalized_query:
        return [], 0

    overfetch = max(int(limit) * 4, 40)
    overfetch = min(overfetch, 300)
    query_body = {
        "bool": {
            "must": [
                {
                    "multi_match": {
                        "query": normalized_query,
                        "fields": [
                            "rag_text^4",
                            "emsal^2",
                            "daire^2",
                            "esas_no",
                            "karar_no",
                        ],
                        "type": "best_fields",
                    }
                }
            ],
            "filter": _es_meta_filter_clauses(filters),
        }
    }
    rows, elapsed_ms = await _search_elasticsearch(
        query=query_body,
        size=overfetch,
    )
    return rows[: int(limit)], int(elapsed_ms)


def _parse_vector_input(vector_text: str | None = None, vector: list[float] | None = None) -> list[float]:
    if isinstance(vector, list) and vector:
        return [float(x) for x in vector]
    if isinstance(vector_text, str) and vector_text.strip():
        try:
            raw = json.loads(vector_text)
            if isinstance(raw, list):
                return [float(x) for x in raw]
        except Exception as exc:
            raise RuntimeError("qdrant_unavailable") from exc
    raise RuntimeError("qdrant_unavailable")


async def _qdrant_query(*, vector: list[float], filters: Dict[str, Any] | None, limit: int) -> tuple[List[Dict[str, Any]], int]:
    base_url, headers = _qdrant_http_config()
    body: dict[str, Any] = {
        "query": vector,
        "limit": int(limit),
        "with_payload": True,
        "with_vector": False,
    }
    must = _qdrant_filter_must(filters)
    if must:
        body["filter"] = {"must": must}

    endpoints = [
        (f"{base_url}/collections/{_qdrant_collection_name()}/points/query", body),
        (
            f"{base_url}/collections/{_qdrant_collection_name()}/points/search",
            {
                "vector": vector,
                "limit": int(limit),
                "with_payload": True,
                "with_vector": False,
                **({"filter": {"must": must}} if must else {}),
            },
        ),
    ]
    last_error: Exception | None = None
    for url, payload in endpoints:
        try:
            t0 = time.perf_counter()
            client = await _qdrant_async_client()
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("result", {})
            points = result.get("points") if isinstance(result, dict) else result
            if not isinstance(points, list):
                points = []
            out: list[Dict[str, Any]] = []
            for point in points:
                if not isinstance(point, dict):
                    continue
                payload_obj = point.get("payload") if isinstance(point.get("payload"), dict) else {}
                document_id = _int_or_none(payload_obj.get("document_id"))
                chunk_id = _int_or_none(payload_obj.get("chunk_id"))
                if document_id is None or chunk_id is None:
                    continue
                out.append(
                    {
                        "document_id": int(document_id),
                        "chunk_id": int(chunk_id),
                        "distance": float(point.get("score") or 0.0),
                    }
                )
            if out:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                return out, elapsed_ms
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError("qdrant_unavailable") from last_error


async def search_vector_rows(
    *,
    vector_text: str | None = None,
    vector: list[float] | None = None,
    filters: Dict[str, Any] | None = None,
    limit: int,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, int]]:
    parsed_vector = _parse_vector_input(vector_text=vector_text, vector=vector)
    candidates, qdrant_ms = await _qdrant_query(vector=parsed_vector, filters=filters, limit=max(int(limit), 1))
    rows, hydration_ms = await merge_candidate_rows(candidates, metric_name="distance", limit=int(limit))
    timing = _empty_backend_timing()
    timing["qdrant_ms"] = int(qdrant_ms)
    timing["hydration_ms"] = int(hydration_ms)
    return rows, "qdrant", timing


async def search_keyword_rows(
    *,
    query: str,
    filters: Dict[str, Any] | None,
    limit: int,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, int]]:
    rows, elasticsearch_ms = await _search_keyword_candidates(query, filters=filters, limit=int(limit))
    timing = _empty_backend_timing()
    timing["elasticsearch_ms"] = int(elasticsearch_ms)
    return rows[: int(limit)], "elasticsearch", timing
