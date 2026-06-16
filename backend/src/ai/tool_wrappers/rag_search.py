from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from ...config import agent_config, load_env
from ...db import core_db
from ...usage.extractors import extract_openai_model_name, extract_openai_token_usage, normalize_model_for_billing
from ...usage.usage_service import UsageService
from ..client.openai_clients import get_openai_embeddings_client
from ..logging.agent_audit import audit_log


def _group_hits(rows: List[Dict[str, Any]], *, top_k: int) -> List[Dict[str, Any]]:
    """
    Convert chunk-level hits into madde-level groups.

    Group key: (doc_id, section_type, madde_no)
    Ranking: best (lowest) distance among chunks in the group.
    """
    groups: Dict[Tuple[Any, Any, Any, Any], Dict[str, Any]] = {}

    for r in rows:
        key = (r.get("doc_id"), r.get("section_type"), r.get("madde_no"))
        dist = r.get("distance")
        if key not in groups:
            groups[key] = {
                "doc": {
                    "doc_id": r.get("doc_id"),
                    "doc_type": r.get("doc_type"),
                    "kanun_no": r.get("kanun_no"),
                    "doc_title": r.get("doc_title"),
                },
                "ref": {
                    "section_type": r.get("section_type"),
                    "madde_no": r.get("madde_no"),
                    # DB schema uses madde_no as varchar(32) (e.g. "1", "1/A"); keep legacy field for clients.
                    "madde_ek": None,
                    "madde_baslik": r.get("madde_baslik"),
                },
                "best_distance": float(dist) if dist is not None else None,
                "matched_chunks": [],
            }
        g = groups[key]
        # update best distance
        if dist is not None:
            bd = g.get("best_distance")
            if bd is None or float(dist) < float(bd):
                g["best_distance"] = float(dist)
        # keep up to 1 snippet per group (first ones encountered are already ranked)
        if len(g["matched_chunks"]) < 1:
            txt = (r.get("text") or "").strip()
            g["matched_chunks"].append(
                {
                    "chunk_order": r.get("chunk_order"),
                    "distance": float(dist) if dist is not None else None,
                    "snippet": txt[:350] + ("…" if len(txt) > 350 else ""),
                }
            )

    ranked = sorted(groups.values(), key=lambda x: x.get("best_distance") if x.get("best_distance") is not None else 1e9)
    return ranked[: int(top_k)]


async def rag_search(
    *,
    user_id: int,
    chat_id: int,
    query: str,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    mode: str = "maddes",
    chunk_k: Optional[int] = None,
) -> Dict[str, Any]:
    """
    RAG search: embed query -> vector similarity search in mevzuat_rag.

    filters can include (back-compat + new):
      - doc_type / mevzuat_tur_name
      - kanun_no / mevzuat_no
      - section_type / madde_tip
      - doc_id / mevzuat_id
    """
    if not isinstance(query, str) or not query.strip():
        return {"ok": False, "reason": "empty_query"}

    load_env()
    cfg = agent_config()
    client = await get_openai_embeddings_client()
    try:
        async with asyncio.timeout(cfg.embedding_timeout_seconds):
            emb_resp = await client.embeddings.create(
                model=cfg.embedding_model,
                input=[query.replace("\n", " ").strip()],
            )
    except TimeoutError:
        return {"ok": False, "reason": "openai_timeout"}
    except Exception:
        return {"ok": False, "reason": "openai_unavailable"}
    embedding = emb_resp.data[0].embedding
    vector_str = str(embedding)

    # Best-effort usage accounting for embeddings call
    try:
        in_tok, out_tok, rsn_tok = extract_openai_token_usage(emb_resp)
        model_name = extract_openai_model_name(emb_resp, default=str(cfg.embedding_model))
        billing_model = normalize_model_for_billing(model_name) or model_name
        usage = UsageService()
        if isinstance(in_tok, int) and in_tok > 0:
            await usage.record_token_usage(user_id=user_id, chat_id=chat_id, usage_type="input_tokens", amount=in_tok, model=billing_model)
        if isinstance(out_tok, int) and out_tok > 0:
            await usage.record_token_usage(user_id=user_id, chat_id=chat_id, usage_type="output_tokens", amount=out_tok, model=billing_model)
        if isinstance(rsn_tok, int) and rsn_tok > 0:
            await usage.record_token_usage(user_id=user_id, chat_id=chat_id, usage_type="reasoning_tokens", amount=rsn_tok, model=billing_model)
    except Exception:
        pass

    # Best-effort audit log (do not log embedding vector)
    try:
        audit_log(
            "openai_embeddings_create",
            {
                "tool": "rag_search",
                "user_id": int(user_id),
                "chat_id": int(chat_id),
                "model": str(getattr(emb_resp, "model", None) or cfg.embedding_model),
                "input": query,
                "output": {"embedding_dim": int(len(embedding) if isinstance(embedding, list) else 0)},
                "usage_raw": getattr(emb_resp, "usage", None),
            },
        )
    except Exception:
        pass

    where = ["r.model_name = %s", "r.embedding IS NOT NULL"]
    params: List[Any] = [cfg.embedding_model_name_filter]

    f = filters or {}
    doc_type = f.get("mevzuat_tur_name") or f.get("doc_type")
    if doc_type:
        where.append("r.mevzuat_tur_name = %s")
        params.append(str(doc_type))

    kanun_no = f.get("mevzuat_no")
    if kanun_no is None:
        kanun_no = f.get("kanun_no")
    if kanun_no is not None:
        where.append("r.mevzuat_no = %s")
        params.append(int(kanun_no))

    section_type = f.get("madde_tip") or f.get("section_type")
    if section_type:
        where.append("r.madde_tip = %s")
        params.append(str(section_type))

    doc_id = f.get("mevzuat_id")
    if doc_id is None:
        doc_id = f.get("doc_id")
    if doc_id is not None:
        where.append("r.mevzuat_id = %s")
        params.append(int(doc_id))

    # Fetch more chunk hits than we return, then group/dedupe at madde-level.
    fetch_k = int(chunk_k) if isinstance(chunk_k, int) and chunk_k > 0 else max(30, int(top_k) * 4)

    sql = f"""
        SELECT
            r.id,
            r.mevzuat_id AS doc_id,
            r.mevzuat_tur_name AS doc_type,
            r.mevzuat_no AS kanun_no,
            r.mevzuat_adi AS doc_title,
            r.madde_tip AS section_type,
            r.madde_no,
            NULL AS madde_ek,
            r.madde_basligi AS madde_baslik,
            r.chunk_order,
            r.madde_text AS text,
            VEC_DISTANCE_COSINE(r.embedding, VEC_FromText(%s)) AS distance
        FROM mevzuat_rag r
        WHERE {" AND ".join(where)}
        ORDER BY distance
        LIMIT %s
    """
    params2 = [vector_str] + params + [fetch_k]

    with core_db() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, tuple(params2))
        rows = list(cur.fetchall() or [])

    # Normalize mode
    mode_norm = (mode or "maddes").strip().lower()

    if mode_norm == "chunks":
        hits = []
        for r in rows:
            hits.append(
                {
                    "doc_id": r.get("doc_id"),
                    "doc_type": r.get("doc_type"),
                    "kanun_no": r.get("kanun_no"),
                    "doc_title": r.get("doc_title"),
                    "section_type": r.get("section_type"),
                    "madde_no": r.get("madde_no"),
                    "madde_ek": r.get("madde_ek"),
                    "madde_baslik": r.get("madde_baslik"),
                    "chunk_order": r.get("chunk_order"),
                    "text": r.get("text"),
                    "distance": float(r["distance"]) if r.get("distance") is not None else None,
                }
            )
        return {"ok": True, "mode": "chunks", "query": query, "top_k": top_k, "hits": hits}

    groups = _group_hits(rows, top_k=int(top_k))
    return {
        "ok": True,
        "mode": "maddes",
        "query": query,
        "top_k": int(top_k),
        "groups": groups,
        "note": "Full text is not included. Call get_madde_by_reference with the group's ref to expand when needed.",
    }


