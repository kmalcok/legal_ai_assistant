from __future__ import annotations

import asyncio
import datetime
import time
from typing import Any, Dict, List, Optional

from ...config import agent_config, load_env
from ...usage.extractors import extract_openai_model_name, extract_openai_token_usage, normalize_model_for_billing
from ...usage.usage_service import UsageService
from ...utils.dev_logging import dev_log, dev_log_exception
from ...utils.ictihat_format import daire_label
from ..client.openai_clients import get_openai_embeddings_client
from ..logging.agent_audit import audit_log
from .ictihat_repository import (
    fetch_document_stats,
    fetch_stitched_text_rows,
    has_citation_filters,
    search_citation_rows,
    search_keyword_rows,
    search_vector_rows,
)
from .ictihat_text import stitch_decision_text


def _iso_date(v: Any) -> Any:
    if isinstance(v, (datetime.date, datetime.datetime)):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    return v


async def _fetch_full_texts(document_ids: List[int], *, limit_chars_per_doc: int) -> Dict[int, Dict[str, Any]]:
    if not document_ids:
        return {}

    ids = [int(x) for x in document_ids if x is not None]
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}

    limit: int | None = None
    try:
        v = int(limit_chars_per_doc)
    except Exception:
        v = 0
    if v > 0:
        limit = max(2000, v)

    rows = await fetch_stitched_text_rows(ids)
    by_doc: Dict[int, List[str]] = {}
    for row in rows:
        try:
            did = int(row.get("document_id"))
        except Exception:
            continue
        txt = row.get("rag_text") or ""
        if not isinstance(txt, str):
            txt = str(txt)
        txt = txt.strip()
        if txt:
            by_doc.setdefault(did, []).append(txt)

    out: Dict[int, Dict[str, Any]] = {}
    for did in ids:
        st = stitch_decision_text(by_doc.get(int(did)) or [], limit_chars=limit)
        out[int(did)] = {"text": st.text, "truncated": bool(st.truncated)}
    return out


def _group_hits(
    rows: List[Dict[str, Any]],
    *,
    top_k: int,
    metric_name: str = "distance",
    best_field: Optional[str] = None,
    higher_is_better: bool = False,
) -> List[Dict[str, Any]]:
    metric_key = str(metric_name or "distance").strip() or "distance"
    best_metric_field = str(best_field or f"best_{metric_key}")
    groups: Dict[Any, Dict[str, Any]] = {}
    for r in rows:
        doc_id = r.get("document_id")
        if doc_id is None:
            continue
        metric = r.get(metric_key)
        if doc_id not in groups:
            groups[doc_id] = {
                "doc": {
                    "document_id": doc_id,
                    "kurum": r.get("kurum"),
                    "daire": r.get("daire"),
                    "daire_label": daire_label(kurum=r.get("kurum"), daire=r.get("daire")),
                    "esas": {"yil": r.get("esas_yil"), "sira": r.get("esas_sira")},
                    "karar": {
                        "yil": r.get("karar_yil"),
                        "sira": r.get("karar_sira"),
                        "tarih": _iso_date(r.get("karar_tarihi")),
                    },
                },
                best_metric_field: float(metric) if metric is not None else None,
                "matched_chunks": [],
                "chunk_count": None,
                "total_chars": None,
            }
        g = groups[doc_id]
        if metric is not None:
            metric_f = float(metric)
            current_best = g.get(best_metric_field)
            if current_best is None:
                g[best_metric_field] = metric_f
            elif higher_is_better and metric_f > float(current_best):
                g[best_metric_field] = metric_f
            elif (not higher_is_better) and metric_f < float(current_best):
                g[best_metric_field] = metric_f
        if len(g["matched_chunks"]) < 2:
            g["matched_chunks"].append(
                {
                    metric_key: float(metric) if metric is not None else None,
                    "snippet": str(r.get("rag_text") or "").strip(),
                }
            )

    sentinel = -1e18 if higher_is_better else 1e18
    ranked = sorted(
        groups.values(),
        key=lambda x: x.get(best_metric_field) if x.get(best_metric_field) is not None else sentinel,
        reverse=bool(higher_is_better),
    )
    return ranked[: int(top_k)]


async def _attach_doc_stats(groups: List[Dict[str, Any]]) -> None:
    doc_ids: list[int] = []
    for g in groups:
        try:
            doc_ids.append(int((g.get("doc") or {}).get("document_id")))
        except Exception:
            continue
    stats = await fetch_document_stats(list(dict.fromkeys(doc_ids)))
    for g in groups:
        try:
            did = int((g.get("doc") or {}).get("document_id"))
        except Exception:
            continue
        stat = stats.get(did)
        if stat:
            g["chunk_count"] = int(stat["chunk_count"])
            g["total_chars"] = int(stat["total_chars"])


async def _attach_group_full_texts(groups: List[Dict[str, Any]], *, limit_chars_per_doc: int) -> None:
    try:
        doc_ids = [int((g.get("doc") or {}).get("document_id")) for g in groups if isinstance(g, dict)]
    except Exception:
        doc_ids = []
    texts = await _fetch_full_texts(doc_ids, limit_chars_per_doc=int(limit_chars_per_doc))
    for g in groups:
        try:
            did = int((g.get("doc") or {}).get("document_id"))
        except Exception:
            continue
        t = texts.get(did) or {}
        g["text"] = t.get("text")
        g["truncated"] = bool(t.get("truncated"))


def _rows_to_chunk_hits(rows: List[Dict[str, Any]], *, metric_name: str) -> List[Dict[str, Any]]:
    metric_key = str(metric_name or "distance").strip() or "distance"
    hits: List[Dict[str, Any]] = []
    for r in rows:
        metric = r.get(metric_key)
        hits.append(
            {
                "document_id": r.get("document_id"),
                "chunk_id": r.get("chunk_id"),
                "kurum": r.get("kurum"),
                "daire": r.get("daire"),
                "daire_label": daire_label(kurum=r.get("kurum"), daire=r.get("daire")),
                "esas": {"yil": r.get("esas_yil"), "sira": r.get("esas_sira")},
                "karar": {
                    "yil": r.get("karar_yil"),
                    "sira": r.get("karar_sira"),
                    "tarih": _iso_date(r.get("karar_tarihi")),
                },
                "text": r.get("rag_text"),
                metric_key: float(metric) if metric is not None else None,
            }
        )
    return hits


def _new_latency_breakdown() -> Dict[str, int]:
    return {
        "embedding_ms": 0,
        "qdrant_ms": 0,
        "elasticsearch_ms": 0,
        "hydration_ms": 0,
        "grouping_ms": 0,
        "stats_ms": 0,
        "full_text_ms": 0,
    }


async def ictihat_search(
    *,
    user_id: int,
    chat_id: int,
    query: str,
    top_k: int = 3,
    filters: Optional[Dict[str, Any]] = None,
    mode: str = "decisions",
    chunk_k: Optional[int] = None,
    include_full_text: bool = False,
    limit_chars_per_doc: int = 20000,
) -> Dict[str, Any]:
    t0 = time.time()
    load_env()
    f = filters or {}
    has_citation_filter = has_citation_filters(f)
    if (not isinstance(query, str) or not query.strip()) and not has_citation_filter:
        return {"ok": False, "reason": "empty_query"}
    query_text = (query or "").strip()
    use_citation_lookup = bool(has_citation_filter and not query_text)

    dev_log(
        "ictihat",
        "ictihat_search_start",
        {
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "mode": (mode or "decisions"),
            "top_k": int(top_k),
            "chunk_k": int(chunk_k) if isinstance(chunk_k, int) else None,
            "has_citation_filter": bool(has_citation_filter),
            "query_head": (query or "").strip().replace("\n", " ")[:500],
            "filters": f,
        },
    )

    latency_breakdown = _new_latency_breakdown()
    if use_citation_lookup:
        fetch_k = int(chunk_k) if isinstance(chunk_k, int) and chunk_k > 0 else max(200, int(top_k) * 50)
        try:
            rows, backend_timing = await search_citation_rows(filters=f, limit=int(fetch_k))
            latency_breakdown.update(backend_timing)
        except Exception as exc:
            dev_log_exception("ictihat", "ictihat_search_elasticsearch_error", {"kind": "citation_lookup", "filters": f}, exc)
            raise
        note = "Resolved by citation filters (no embedding search)."
        kind = "citation_lookup"
        strategy = "meta_only"
    else:
        client = await get_openai_embeddings_client()
        cfg = agent_config()
        model_name = (cfg.ictihat_embedding_model or "text-embedding-3-small").strip() or "text-embedding-3-small"
        try:
            t_embed0 = time.perf_counter()
            async with asyncio.timeout(cfg.embedding_timeout_seconds):
                emb_resp = await client.embeddings.create(model=model_name, input=[query.replace("\n", " ").strip()])
            latency_breakdown["embedding_ms"] = int((time.perf_counter() - t_embed0) * 1000)
        except TimeoutError as exc:
            dev_log_exception(
                "ictihat",
                "ictihat_search_embed_timeout",
                {"model": model_name, "timeout_seconds": cfg.embedding_timeout_seconds},
                exc,
            )
            return {"ok": False, "reason": "openai_timeout"}
        except Exception as exc:
            dev_log_exception("ictihat", "ictihat_search_embed_error", {"model": model_name}, exc)
            return {"ok": False, "reason": "openai_unavailable"}

        embedding = emb_resp.data[0].embedding
        try:
            in_tok, out_tok, rsn_tok = extract_openai_token_usage(emb_resp)
            model_used = extract_openai_model_name(emb_resp, default=model_name)
            billing_model = normalize_model_for_billing(model_used) or model_used
            usage = UsageService()
            if isinstance(in_tok, int) and in_tok > 0:
                await usage.record_token_usage(user_id=user_id, chat_id=chat_id, usage_type="input_tokens", amount=in_tok, model=billing_model)
            if isinstance(out_tok, int) and out_tok > 0:
                await usage.record_token_usage(user_id=user_id, chat_id=chat_id, usage_type="output_tokens", amount=out_tok, model=billing_model)
            if isinstance(rsn_tok, int) and rsn_tok > 0:
                await usage.record_token_usage(user_id=user_id, chat_id=chat_id, usage_type="reasoning_tokens", amount=rsn_tok, model=billing_model)
        except Exception:
            pass
        try:
            audit_log(
                "openai_embeddings_create",
                {
                    "tool": "ictihat_search",
                    "user_id": int(user_id),
                    "chat_id": int(chat_id),
                    "model": str(getattr(emb_resp, "model", None) or model_name),
                    "input": query,
                    "output": {"embedding_dim": int(len(embedding) if isinstance(embedding, list) else 0)},
                    "usage_raw": getattr(emb_resp, "usage", None),
                },
            )
        except Exception:
            pass

        fetch_k = int(chunk_k) if isinstance(chunk_k, int) and chunk_k > 0 else max(20, int(top_k) * 4)
        try:
            rows, strategy, backend_timing = await search_vector_rows(
                vector=embedding,
                filters=f,
                limit=int(fetch_k),
            )
            latency_breakdown.update(backend_timing)
        except Exception as exc:
            dev_log_exception("ictihat", "ictihat_search_qdrant_error", {"kind": "vector", "filters": f}, exc)
            return {"ok": False, "reason": "qdrant_unavailable"}
        note = "Full text is included." if bool(include_full_text) else "Full text is not included. Call ictihat_get_document to expand as needed."
        kind = "vector"

    mode_norm = (mode or "decisions").strip().lower()
    if mode_norm == "chunks":
        hits = _rows_to_chunk_hits(rows, metric_name="distance")
        return {"ok": True, "mode": "chunks", "query": query or "", "top_k": int(top_k), "hits": hits, "note": note}

    t_group0 = time.perf_counter()
    groups = _group_hits(rows, top_k=int(top_k))
    latency_breakdown["grouping_ms"] = int((time.perf_counter() - t_group0) * 1000)
    try:
        t_stats0 = time.perf_counter()
        await _attach_doc_stats(groups)
        latency_breakdown["stats_ms"] = int((time.perf_counter() - t_stats0) * 1000)
    except Exception:
        pass
    if bool(include_full_text):
        try:
            t_text0 = time.perf_counter()
            await _attach_group_full_texts(groups, limit_chars_per_doc=int(limit_chars_per_doc))
            latency_breakdown["full_text_ms"] = int((time.perf_counter() - t_text0) * 1000)
        except Exception:
            pass
    try:
        doc_ids = [int((g.get("doc") or {}).get("document_id")) for g in groups if isinstance(g, dict)]
    except Exception:
        doc_ids = []
    dev_log(
        "ictihat",
        "ictihat_search_done",
        {
            "kind": kind,
            "duration_ms": int((time.time() - t0) * 1000),
            "group_count": len(groups),
            "document_ids": doc_ids[:50],
            "strategy": strategy,
            "latency_breakdown_ms": latency_breakdown,
        },
    )
    return {"ok": True, "mode": "decisions", "query": query or "", "top_k": int(top_k), "groups": groups, "note": note}


async def ictihat_keyword_search(
    *,
    user_id: int,
    chat_id: int,
    query: str,
    top_k: int = 3,
    filters: Optional[Dict[str, Any]] = None,
    mode: str = "decisions",
    chunk_k: Optional[int] = None,
    include_full_text: bool = False,
    limit_chars_per_doc: int = 20000,
) -> Dict[str, Any]:
    t0 = time.time()
    load_env()
    f = filters or {}
    q = (query or "").strip()
    has_citation_filter = has_citation_filters(f)
    if not q and not has_citation_filter:
        return {"ok": False, "reason": "empty_query"}
    use_citation_lookup = bool(has_citation_filter and not q)

    dev_log(
        "ictihat",
        "ictihat_keyword_search_start",
        {
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "mode": (mode or "decisions"),
            "top_k": int(top_k),
            "chunk_k": int(chunk_k) if isinstance(chunk_k, int) else None,
            "has_citation_filter": bool(has_citation_filter),
            "query_head": q.replace("\n", " ")[:500],
            "filters": f,
        },
    )

    latency_breakdown = _new_latency_breakdown()
    if use_citation_lookup:
        fetch_k = int(chunk_k) if isinstance(chunk_k, int) and chunk_k > 0 else max(200, int(top_k) * 50)
        try:
            rows, backend_timing = await search_citation_rows(filters=f, limit=int(fetch_k))
            latency_breakdown.update(backend_timing)
            strategy = "meta_only"
        except Exception as exc:
            dev_log_exception(
                "ictihat",
                "ictihat_keyword_search_elasticsearch_error",
                {"kind": "citation_lookup", "filters": f},
                exc,
            )
            return {"ok": False, "reason": "elasticsearch_unavailable"}
        search_note = "Resolved by citation filters (no keyword query)."
    else:
        fetch_k = int(chunk_k) if isinstance(chunk_k, int) and chunk_k > 0 else max(80, int(top_k) * 16)
        try:
            rows, strategy, backend_timing = await search_keyword_rows(query=q, filters=f, limit=int(fetch_k))
            latency_breakdown.update(backend_timing)
        except Exception as exc:
            dev_log_exception("ictihat", "ictihat_keyword_search_elasticsearch_error", {"filters": f}, exc)
            return {"ok": False, "reason": "elasticsearch_unavailable"}
        search_note = "Resolved by Elasticsearch keyword search."
    mode_norm = (mode or "decisions").strip().lower()
    if mode_norm == "chunks":
        hits = _rows_to_chunk_hits(rows, metric_name="score")
        return {"ok": True, "mode": "chunks", "query": q, "top_k": int(top_k), "hits": hits, "note": search_note}

    t_group0 = time.perf_counter()
    groups = _group_hits(rows, top_k=int(top_k), metric_name="score", best_field="best_score", higher_is_better=True)
    latency_breakdown["grouping_ms"] = int((time.perf_counter() - t_group0) * 1000)
    try:
        t_stats0 = time.perf_counter()
        await _attach_doc_stats(groups)
        latency_breakdown["stats_ms"] = int((time.perf_counter() - t_stats0) * 1000)
    except Exception:
        pass
    if bool(include_full_text):
        try:
            t_text0 = time.perf_counter()
            await _attach_group_full_texts(groups, limit_chars_per_doc=int(limit_chars_per_doc))
            latency_breakdown["full_text_ms"] = int((time.perf_counter() - t_text0) * 1000)
        except Exception:
            pass
    try:
        doc_ids = [int((g.get("doc") or {}).get("document_id")) for g in groups if isinstance(g, dict)]
    except Exception:
        doc_ids = []
    dev_log(
        "ictihat",
        "ictihat_keyword_search_done",
        {
            "kind": "keyword",
            "duration_ms": int((time.time() - t0) * 1000),
            "group_count": len(groups),
            "document_ids": doc_ids[:50],
            "strategy": strategy,
            "latency_breakdown_ms": latency_breakdown,
        },
    )
    note = search_note if not bool(include_full_text) else f"{search_note} Full text is included."
    return {"ok": True, "mode": "decisions", "query": q, "top_k": int(top_k), "groups": groups, "note": note}

