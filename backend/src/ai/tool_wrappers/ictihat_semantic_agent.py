from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Tuple

from agents import Runner

from ..client.openai_clients import build_agents_run_config
from ..agent.ictihat_search_agent import IctihatSearchAgent
from ..tool_wrappers.ictihat_get_document import ictihat_get_document as _ictihat_get_document
from ...config import agent_config, load_env
from ...services.ictihat_daire_cache_service import get_cached_ictihat_daire_names
from ...services.user_app_config_service import UserAppConfigService
from ..util.rotator import get_current_openai_key_name
from ...usage.extractors import extract_agents_sdk_usage, normalize_model_for_billing
from ...usage.usage_service import UsageService, log_token_usage_bundle
from ...utils.dev_logging import dev_log, dev_log_exception
from ..logging.agent_audit import audit_log
from ..util.ictihat_agent_summarizer import summarize_ictihat_for_agent


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

    # Strip common code fences if the model violates instructions.
    if s.startswith("```"):
        # remove leading ```json / ``` and trailing ```
        s2 = s
        s2 = s2.replace("```json", "```").replace("```JSON", "```")
        if s2.startswith("```"):
            s2 = s2[3:]
        if s2.endswith("```"):
            s2 = s2[:-3]
        s = s2.strip()

    # Fast path: whole string is JSON
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # Find first balanced {...}
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


def _validate_contract(obj: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Ensure we return {ok: bool, items?: list, reason?: str}.
    Normalize types defensively.
    """
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
        # Required: document_id
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
                "snippet": str(it.get("snippet") or ""),
                "why": str(it.get("why") or ""),
                "summary": str(it.get("summary") or ""),
                "key_terms": it.get("key_terms") if isinstance(it.get("key_terms"), list) else [],
                # Filled after normalization (deterministic enrich step).
                "text": None,
            }
        )

    if not cleaned:
        return False, {"ok": False, "reason": "no_results"}

    def _sort_key(x: Dict[str, Any]) -> Tuple[int, int, int]:
        # 5-star scale: 5 = most relevant, 1 = marginal.
        # Negate tier so higher-star items sort first.
        try:
            t = int(x.get("tier") or 3)
        except Exception:
            t = 3
        if t not in (1, 2, 3, 4, 5):
            t = 3
        karar = x.get("karar") if isinstance(x.get("karar"), dict) else {}
        try:
            y = int(karar.get("yil")) if karar.get("yil") is not None else 0
        except Exception:
            y = 0
        try:
            d = int(x.get("document_id") or 0)
        except Exception:
            d = 0
        return (-t, -y, -d)

    cleaned.sort(key=_sort_key)
    return True, {"ok": True, "items": cleaned}


async def _enrich_items_with_texts(*, user_id: int, chat_id: int, items: list[dict[str, Any]], olay_context: str | None = None, debug: bool) -> None:
    """
    Deterministically attach full decision texts to the items returned by the search sub-agent.
    Applies conditional summarization if token_count > 5000.
    When olay_context is provided, the summarizer preserves case-relevant passages verbatim.
    """

    async def _one(it: dict[str, Any]) -> None:
        did = it.get("document_id")
        try:
            did_i = int(did)
        except Exception:
            return
        if did_i <= 0:
            return
        try:
            doc_res = await _ictihat_get_document(
                user_id=int(user_id),
                chat_id=int(chat_id),
                document_id=int(did_i),
            )
        except Exception as e:
            if debug:
                dev_log_exception(
                    "ictihat_search_agent",
                    "ictihat_semantic_search_get_document_error",
                    {"user_id": int(user_id), "chat_id": int(chat_id), "document_id": int(did_i)},
                    e,
                )
            return

        text = ""
        try:
            if isinstance(doc_res, dict) and doc_res.get("ok") and isinstance(doc_res.get("text"), str):
                text = str(doc_res.get("text") or "")
        except Exception:
            text = ""

        if not text:
            it["text"] = ""
            return

        summarized = text
        try:
            summarized, meta = await summarize_ictihat_for_agent(
                user_id=int(user_id),
                chat_id=int(chat_id),
                document_text=text,
                olay_context=olay_context,
                token_threshold=int(cfg.ictihat_summarizer_token_threshold),
            )
            if debug:
                # Do not log the text itself (can be huge).
                dev_log(
                    "ictihat_search_agent",
                    "ictihat_semantic_search_text_summarization",
                    {
                        "user_id": int(user_id),
                        "chat_id": int(chat_id),
                        "document_id": int(did_i),
                        "meta": meta,
                    },
                )
        except Exception:
            summarized = text

        it["text"] = summarized

    # Keep concurrency small; stitching can be CPU-heavy.
    sem = asyncio.Semaphore(3)

    async def _guarded(it: dict[str, Any]) -> None:
        async with sem:
            await _one(it)

    await asyncio.gather(*[_guarded(it) for it in items if isinstance(it, dict)])


async def ictihat_semantic_search(
    *,
    user_id: int,
    chat_id: int,
    intent_text: str,
) -> Dict[str, Any]:
    """
    Runs the mini "ictihat search agent" to perform iterative semantic search,
    then returns a compact, refined JSON contract for the main agent.
    """
    if not isinstance(intent_text, str) or not intent_text.strip():
        return {"ok": False, "reason": "empty_intent"}

    load_env()
    cfg = agent_config()

    model = cfg.ictihat_search_agent_model
    max_turns = int(cfg.ictihat_search_agent_max_turns)
    debug = bool(cfg.ictihat_search_agent_debug)

    resolved_effort = await asyncio.to_thread(
        UserAppConfigService().resolve_ictihat_reasoning_effort,
        user_id=int(user_id),
        model=str(model),
        default_effort=str(cfg.ictihat_search_agent_default_reasoning_effort or "medium"),
    )
    daire_cache = await get_cached_ictihat_daire_names()
    agent = IctihatSearchAgent(
        user_id=int(user_id),
        chat_id=int(chat_id),
        model=model,
        reasoning_effort=resolved_effort,
        daire_names=list(daire_cache.get("names") or []),
    )
    agent.intent_text = intent_text.strip()

    payload = json.dumps({"Intent Text": intent_text.strip()}, ensure_ascii=False)
    if debug:
        dev_log(
            "ictihat_search_agent",
            "ictihat_semantic_search_start",
            {
                "user_id": int(user_id),
                "chat_id": int(chat_id),
                "model": model,
                "max_turns": int(max_turns),
                "intent_preview": intent_text.strip()[:300],
                "intent_len": len(intent_text.strip()),
            },
        )

    try:
        async with asyncio.timeout(cfg.search_agent_timeout_seconds):
            run_config = await build_agents_run_config()
            result = await Runner.run(agent.agent, payload, max_turns=int(max_turns), run_config=run_config)
    except TimeoutError as e:
        if debug:
            dev_log_exception(
                "ictihat_search_agent",
                "ictihat_semantic_search_runner_timeout",
                {"user_id": int(user_id), "chat_id": int(chat_id), "model": model, "timeout_seconds": cfg.search_agent_timeout_seconds},
                e,
            )
        return {"ok": False, "reason": "openai_timeout"}
    except Exception as e:
        if debug:
            dev_log_exception(
                "ictihat_search_agent",
                "ictihat_semantic_search_runner_error",
                {"user_id": int(user_id), "chat_id": int(chat_id), "model": model},
                e,
            )
        raise

    # Agents SDK may return the final assistant content in different fields depending on version.
    # Prefer output_text, then final_output.
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
                "tool": "ictihat_semantic_search",
                "user_id": int(user_id),
                "chat_id": int(chat_id),
                "model": str(getattr(agent.agent, "model", None) or model),
                "max_turns": int(max_turns),
                "input": {"intent_text": intent_text.strip(), "payload_len": int(len(payload))},
                "output": {"source": source, "output_text": output_text},
                "usage_raw": getattr(result, "usage", None) or getattr(getattr(result, "context_wrapper", None), "usage", None),
            },
        )
    except Exception:
        pass

    if debug:
        dev_log(
            "ictihat_search_agent",
            "ictihat_semantic_search_raw_output",
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
        if debug:
            dev_log(
                "ictihat_search_agent",
                "ictihat_semantic_search_bad_json",
                {"user_id": int(user_id), "chat_id": int(chat_id), "model": model},
            )
        return {"ok": False, "reason": "bad_json"}

    ok, normalized = _validate_contract(obj)
    if debug:
        try:
            ids = [int(it.get("document_id")) for it in (normalized.get("items") or []) if isinstance(it, dict) and it.get("document_id") is not None]
        except Exception:
            ids = []
        dev_log(
            "ictihat_search_agent",
            "ictihat_semantic_search_normalized",
            {
                "user_id": int(user_id),
                "chat_id": int(chat_id),
                "ok": bool(normalized.get("ok")),
                "reason": normalized.get("reason"),
                "items_count": len(normalized.get("items") or []) if isinstance(normalized.get("items"), list) else 0,
                "document_ids": ids[:12],
            },
        )

    # Best-effort usage recording for the sub-agent run
    try:
        # Prefer extracting from the whole RunResult (SDK versions differ on where usage lives).
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

    # Deterministically attach full texts for the main agent.
    # Pass intent_text as olay_context so the summarizer preserves case-relevant passages.
    if ok and isinstance(normalized, dict) and isinstance(normalized.get("items"), list):
        try:
            # Enriching every returned item can be extremely expensive when recall is high.
            await _enrich_items_with_texts(
                user_id=int(user_id),
                chat_id=int(chat_id),
                items=normalized["items"],  # type: ignore[arg-type]
                olay_context=intent_text.strip() if isinstance(intent_text, str) else None,
                debug=bool(debug),
            )
        except Exception:
            pass

    return normalized

