from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from agents import Runner

from ..client.openai_clients import build_agents_run_config
from ..agent.ictihat_api_search_agent import IctihatApiSearchAgent
from ..tool_wrappers.ictihat_search import ictihat_keyword_search as _ictihat_keyword_search
from ..tool_wrappers.ictihat_search import ictihat_search as _ictihat_search
from ...config import agent_config, load_env
from ...services.ictihat_daire_cache_service import get_cached_ictihat_daire_names
from ...services.user_app_config_service import UserAppConfigService
from ..util.rotator import get_current_openai_key_name
from ...usage.extractors import extract_agents_sdk_usage, normalize_model_for_billing
from ...usage.usage_service import UsageService, log_token_usage_bundle
from ...utils.dev_logging import dev_log, dev_log_exception
from ..logging.agent_audit import audit_log


def _log_ictihat_api_semantic(
    *,
    event: str,
    user_id: int,
    chat_id: int,
    **fields: Any,
) -> None:
    try:
        payload: Dict[str, Any] = {
            "event": str(event),
            "user_id": int(user_id),
            "chat_id": int(chat_id),
        }
        for k, v in fields.items():
            if v is not None:
                payload[str(k)] = v
        logging.getLogger("mevzuat.api").warning(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        logging.getLogger("mevzuat.api").warning("ictihat_api_semantic_search log_emit_failed", exc_info=True)


def _extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort: extract the first JSON object from a string.
    We expect the agent to output JSON only, but keep this robust.
    """
    if not isinstance(text, str):
        return None
    s = text.strip()
    if not s:
        return None

    if s.startswith("```"):
        s2 = s.replace("```json", "```").replace("```JSON", "```")
        if s2.startswith("```"):
            s2 = s2[3:]
        if s2.endswith("```"):
            s2 = s2[:-3]
        s = s2.strip()

    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    cand = s[start : i + 1].strip()
                    try:
                        obj = json.loads(cand)
                        return obj if isinstance(obj, dict) else None
                    except Exception:
                        return None
    return None


def _tier_sort_key(item: Dict[str, Any]) -> Tuple[int, int, int]:
    """Deterministic ordering: tier DESC (5★ first -> 1★ last), newer karar year first, then document_id DESC.

    Note: 5-star scale. 5 = most relevant (Bull's-eye), 1 = marginal relevance. The sort key
    negates tier so that the natural ASC sort places higher-star items first.
    """
    try:
        tier = int(item.get("tier") or 3)
    except Exception:
        tier = 3
    if tier not in (1, 2, 3, 4, 5):
        tier = 3
    karar = item.get("karar") if isinstance(item.get("karar"), dict) else {}
    try:
        yil = int(karar.get("yil")) if karar.get("yil") is not None else 0
    except Exception:
        yil = 0
    try:
        did = int(item.get("document_id") or 0)
    except Exception:
        did = 0
    return (-tier, -yil, -did)


def _validate_contract(obj: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    ok = bool(obj.get("ok"))
    if not ok:
        reason = obj.get("reason") or "search_failed"
        return False, {"ok": False, "reason": str(reason)}

    items = obj.get("items")
    if not isinstance(items, list):
        return False, {"ok": False, "reason": "bad_contract"}

    cleaned = []
    for it in items:
        if not isinstance(it, dict):
            continue
        did = it.get("document_id")
        try:
            did_i = int(did)
        except Exception:
            continue
        tier_raw = it.get("tier")
        try:
            tier_val = int(tier_raw)
            if tier_val not in (1, 2, 3, 4, 5):
                tier_val = 3
        except Exception:
            tier_val = 3
        cleaned.append(
            {
                "document_id": did_i,
                "kurum": it.get("kurum"),
                "daire": it.get("daire"),
                "esas": it.get("esas") if isinstance(it.get("esas"), dict) else {"yil": None, "sira": None},
                "karar": it.get("karar") if isinstance(it.get("karar"), dict) else {"yil": None, "sira": None, "tarih": None},
                "tier": tier_val,
                "why": str(it.get("why") or ""),
                "summary": str(it.get("summary") or ""),
            }
        )

    if not cleaned:
        return False, {"ok": False, "reason": "no_results"}

    cleaned.sort(key=lambda x: _tier_sort_key(x))

    # Contract: keep response minimal for UI.
    return True, {"ok": True, "items": cleaned}


def _fallback_from_search(res: Dict[str, Any]) -> Dict[str, Any]:
    groups = res.get("groups") if isinstance(res, dict) else None
    if not isinstance(groups, list) or not groups:
        return {"ok": False, "reason": "no_results"}
    items = []
    for g in groups:
        if not isinstance(g, dict):
            continue
        doc = g.get("doc") if isinstance(g.get("doc"), dict) else {}
        try:
            did = int(doc.get("document_id"))
        except Exception:
            continue
        items.append(
            {
                "document_id": did,
                "kurum": doc.get("kurum"),
                "daire": doc.get("daire"),
                "esas": doc.get("esas") if isinstance(doc.get("esas"), dict) else {"yil": None, "sira": None},
                "karar": doc.get("karar") if isinstance(doc.get("karar"), dict) else {"yil": None, "sira": None, "tarih": None},
                # Neutral middle when no AI grading was performed (5-star scale).
                "tier": 3,
                "why": "",
                "summary": "",
            }
        )
    items.sort(key=lambda x: _tier_sort_key(x))
    return {"ok": True, "items": items}


async def _fallback_from_deterministic_searches(
    *,
    user_id: int,
    chat_id: int,
    intent_text: str,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    retryable_reasons = {"no_results", "openai_unavailable", "openai_timeout"}
    for search_fn in (_ictihat_search, _ictihat_keyword_search):
        try:
            res = await search_fn(
                user_id=int(user_id),
                chat_id=int(chat_id),
                query=intent_text.strip(),
                top_k=20,
                filters=filters,
                mode="decisions",
                chunk_k=None,
                include_full_text=False,
            )
        except Exception:
            continue
        if isinstance(res, dict) and res.get("ok"):
            normalized = _fallback_from_search(res)
            if normalized.get("ok"):
                return normalized
        reason = str(res.get("reason") or "") if isinstance(res, dict) else ""
        if reason and reason not in retryable_reasons:
            return {"ok": False, "reason": str(res.get("reason")), "detail": res.get("detail")}
    return {"ok": False, "reason": "no_results"}


async def ictihat_api_semantic_search(
    *,
    user_id: int,
    chat_id: int,
    intent_text: str,
    filters: Optional[Dict[str, Any]] = None,
    effort_top_k: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Runs the API/UI oriented ictihat search sub-agent.
    Returns a compact contract (no full decision texts).

    ``effort_top_k`` is an OPTIONAL hint from the UI (one of 5/10/15/20).
    When provided, an effort-scaling instruction block is appended to the
    agent's system prompt so the LLM caps tool-call count and result size.
    Any other value (None, 0, out-of-range) means "no hint" and the agent
    runs the default exhaustive protocol.
    """
    if not isinstance(intent_text, str) or not intent_text.strip():
        return {"ok": False, "reason": "empty_intent"}

    load_env()
    cfg = agent_config()
    model = cfg.ictihat_api_search_agent_model
    max_turns = int(cfg.ictihat_api_search_agent_max_turns)
    debug = bool(cfg.ictihat_api_search_agent_debug)

    # Normalize effort hint up front so downstream callers see a clean value.
    normalized_effort_top_k: Optional[int]
    try:
        candidate = int(effort_top_k) if effort_top_k is not None else None
    except Exception:
        candidate = None
    normalized_effort_top_k = candidate if candidate in (5, 10, 15, 20) else None

    resolved_effort = await asyncio.to_thread(
        UserAppConfigService().resolve_ictihat_reasoning_effort,
        user_id=int(user_id),
        model=str(model),
        default_effort=str(cfg.ictihat_api_search_agent_default_reasoning_effort or "medium"),
    )
    daire_cache = await get_cached_ictihat_daire_names()
    agent = IctihatApiSearchAgent(
        user_id=int(user_id),
        chat_id=int(chat_id),
        model=model,
        reasoning_effort=resolved_effort,
        daire_names=list(daire_cache.get("names") or []),
        effort_top_k=normalized_effort_top_k,
    )
    agent.intent_text = intent_text.strip()
    payload_obj: Dict[str, Any] = {"Intent Text": intent_text.strip()}
    if isinstance(filters, dict) and filters:
        payload_obj["Filters"] = filters
    payload = json.dumps(payload_obj, ensure_ascii=False)

    if debug:
        dev_log(
            "ictihat_api_search_agent",
            "ictihat_api_semantic_search_start",
            {
                "user_id": int(user_id),
                "chat_id": int(chat_id),
                "model": model,
                "max_turns": int(max_turns),
                "intent_preview": intent_text.strip()[:600],
                "intent_len": len(intent_text.strip()),
                "has_filters": bool(filters),
                "effort_top_k": normalized_effort_top_k,
            },
        )

    result = None
    try:
        async with asyncio.timeout(cfg.search_agent_timeout_seconds):
            run_config = await build_agents_run_config()
            result = await Runner.run(agent.agent, payload, max_turns=int(max_turns), run_config=run_config)
    except TimeoutError as e:
        _log_ictihat_api_semantic(
            event="ictihat_api_semantic_search_runner_timeout",
            user_id=int(user_id),
            chat_id=int(chat_id),
            model=str(model),
            timeout_seconds=float(cfg.search_agent_timeout_seconds),
            exc_type=type(e).__name__,
        )
        if debug:
            dev_log_exception(
                "ictihat_api_search_agent",
                "ictihat_api_semantic_search_runner_timeout",
                {
                    "user_id": int(user_id),
                    "chat_id": int(chat_id),
                    "model": model,
                    "timeout_seconds": cfg.search_agent_timeout_seconds,
                },
                e,
            )
        fallback = await _fallback_from_deterministic_searches(
            user_id=int(user_id),
            chat_id=int(chat_id),
            intent_text=intent_text,
            filters=filters,
        )
        if isinstance(fallback, dict) and fallback.get("ok"):
            return fallback
        return {"ok": False, "reason": "openai_timeout"}
    except Exception as e:
        _log_ictihat_api_semantic(
            event="ictihat_api_semantic_search_runner_error",
            user_id=int(user_id),
            chat_id=int(chat_id),
            model=str(model),
            exc_type=type(e).__name__,
            exc_message=str(e)[:2000],
        )
        if debug:
            dev_log_exception(
                "ictihat_api_search_agent",
                "ictihat_api_semantic_search_runner_error",
                {"user_id": int(user_id), "chat_id": int(chat_id), "model": model},
                e,
            )
        # Fallback: deterministic single search (no full text).
        fallback = await _fallback_from_deterministic_searches(
            user_id=int(user_id),
            chat_id=int(chat_id),
            intent_text=intent_text,
            filters=filters,
        )
        if isinstance(fallback, dict) and fallback.get("ok"):
            return fallback
        return {"ok": False, "reason": "agent_failed"}

    raw_out: Any = getattr(result, "output_text", None)
    source = "output_text"
    if not raw_out:
        raw_out = getattr(result, "final_output", None)
        source = "final_output"
    if raw_out is None:
        raw_out = ""
        source = "none"

    if isinstance(raw_out, (dict, list)):
        output_text = json.dumps(raw_out, ensure_ascii=False)
    else:
        output_text = str(raw_out or "")
    output_text = output_text.strip()

    # Best-effort audit log (input + output for the sub-agent run)
    try:
        audit_log(
            "openai_agents_runner_run",
            {
                "tool": "ictihat_api_semantic_search",
                "user_id": int(user_id),
                "chat_id": int(chat_id),
                "model": str(getattr(agent.agent, "model", None) or model),
                "max_turns": int(max_turns),
                "input": {"intent_text": intent_text.strip(), "filters": (filters or {}), "payload_len": int(len(payload))},
                "output": {"source": source, "output_text": output_text},
                "usage_raw": getattr(result, "usage", None) or getattr(getattr(result, "context_wrapper", None), "usage", None),
            },
        )
    except Exception:
        pass

    if debug:
        dev_log(
            "ictihat_api_search_agent",
            "ictihat_api_semantic_search_raw_output",
            {
                "user_id": int(user_id),
                "chat_id": int(chat_id),
                "model": model,
                "output_source": source,
                "output_preview": output_text[:400],
                "output_len": len(output_text),
            },
        )

    obj = _extract_first_json_object(output_text)
    if not isinstance(obj, dict):
        _log_ictihat_api_semantic(
            event="ictihat_api_semantic_search_bad_json",
            user_id=int(user_id),
            chat_id=int(chat_id),
            model=str(model),
            output_preview=output_text[:1200],
            output_len=len(output_text),
        )
        return {"ok": False, "reason": "bad_json"}

    ok, normalized = _validate_contract(obj)
    if not ok:
        _log_ictihat_api_semantic(
            event="ictihat_api_semantic_search_contract_rejected",
            user_id=int(user_id),
            chat_id=int(chat_id),
            model=str(model),
            contract_reason=str((normalized or {}).get("reason") or ""),
            parsed_ok=bool(obj.get("ok")),
            parsed_keys=sorted(str(k) for k in obj.keys())[:40],
            output_preview=output_text[:800],
        )

    # Best-effort usage recording
    try:
        in_tok, out_tok, rsn_tok = extract_agents_sdk_usage(result)
        if in_tok is None and out_tok is None and rsn_tok is None:
            usage_source = getattr(result, "usage", None)
            if usage_source is None:
                ctx = getattr(result, "context_wrapper", None)
                usage_source = getattr(ctx, "usage", None) if ctx is not None else None
            in_tok, out_tok, rsn_tok = extract_agents_sdk_usage(usage_source)
        usage = UsageService()
        raw_model = getattr(agent.agent, "model", None) or model
        billing_model = normalize_model_for_billing(str(raw_model)) or str(raw_model)
        in_v = int(in_tok) if isinstance(in_tok, int) and in_tok > 0 else 0
        out_v = int(out_tok) if isinstance(out_tok, int) and out_tok > 0 else 0
        rsn_v = int(rsn_tok) if isinstance(rsn_tok, int) and rsn_tok > 0 else 0
        if in_v > 0:
            await usage.record_token_usage(
                user_id=int(user_id),
                chat_id=int(chat_id),
                usage_type="input_tokens",
                amount=in_v,
                model=billing_model,
                emit_log=False,
            )
        if out_v > 0:
            await usage.record_token_usage(
                user_id=int(user_id),
                chat_id=int(chat_id),
                usage_type="output_tokens",
                amount=out_v,
                model=billing_model,
                emit_log=False,
            )
        if rsn_v > 0:
            await usage.record_token_usage(
                user_id=int(user_id),
                chat_id=int(chat_id),
                usage_type="reasoning_tokens",
                amount=rsn_v,
                model=billing_model,
                emit_log=False,
            )
        if in_v or out_v or rsn_v:
            log_token_usage_bundle(
                int(user_id),
                int(chat_id),
                input_tokens=in_v,
                output_tokens=out_v,
                reasoning_tokens=rsn_v,
                model=billing_model,
                openai_key_name=get_current_openai_key_name(),
            )
    except Exception:
        pass

    return normalized

