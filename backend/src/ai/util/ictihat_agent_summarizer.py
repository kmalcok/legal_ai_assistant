from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Dict, Optional, Tuple

from ...config import agent_config, load_env
from ...services.user_app_config_service import sanitize_reasoning_effort
from ...usage.extractors import extract_openai_model_name, extract_openai_token_usage, normalize_model_for_billing
from ...usage.usage_service import UsageService
from ..client.openai_clients import get_openai_responses_client
from ..logging.agent_audit import audit_log
from .instruction_loader import load_prompt_text
from .token_count import count_tokens


async def summarize_ictihat_for_agent(
    *,
    user_id: int,
    chat_id: int,
    document_text: str,
    olay_context: Optional[str] = None,
    token_threshold: int | None = None,
    model: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Summarize very long Yargıtay decision text before sending into the main agent context.
    Triggered only when token_count > token_threshold.

    If `olay_context` is provided (the user's case summary), the summarizer will preserve
    passages directly relevant to that case verbatim, only compressing unrelated parts.

    Returns: (text_for_agent, meta)
    """
    load_env()
    cfg = agent_config()
    resolved_model = str(model or cfg.ictihat_summarizer_model).strip() or cfg.ictihat_summarizer_model
    resolved_threshold = int(
        cfg.ictihat_summarizer_token_threshold if token_threshold is None else token_threshold
    )
    resolved_reasoning_effort = sanitize_reasoning_effort(
        resolved_model,
        cfg.ictihat_summarizer_reasoning_effort,
    )
    text = document_text if isinstance(document_text, str) else str(document_text or "")
    tok = count_tokens(text, model=resolved_model)
    meta: Dict[str, Any] = {
        "summarized": False,
        "input_tokens_est": int(tok),
        "threshold": int(resolved_threshold),
        "model": str(resolved_model),
        "reasoning_effort": resolved_reasoning_effort,
    }
    if tok <= int(resolved_threshold):
        return text, meta

    client = await get_openai_responses_client()

    tmpl = load_prompt_text("ictihat_summarize.md")

    # Build olay context block for the prompt template
    olay_str = (olay_context or "").strip() if isinstance(olay_context, str) else ""
    if olay_str:
        olay_block = f"OLAY BAĞLAMI (kullanıcının somut olayı):\n{olay_str}"
        meta["olay_context_provided"] = True
    else:
        olay_block = ""
        meta["olay_context_provided"] = False

    prompt = tmpl.replace("{{OLAY_CONTEXT_BLOCK}}", olay_block).replace("{{TEXT}}", text)

    try:
        async with asyncio.timeout(cfg.summarizer_timeout_seconds):
            req: Dict[str, Any] = {
                "model": resolved_model,
                "input": prompt,
            }
            if resolved_reasoning_effort:
                req["reasoning"] = {"effort": resolved_reasoning_effort}
            resp = await client.responses.create(**req)
        out_text = (getattr(resp, "output_text", None) or "").strip()
        if not out_text:
            # Fall back: if SDK shape differs, keep original
            return text, meta
    except TimeoutError:
        meta["reason"] = "openai_timeout"
        return text, meta
    except Exception:
        # Never break agent flow; fall back to original
        return text, meta

    # Best-effort audit log (store small prompt fingerprint + output)
    try:
        sha = hashlib.sha256((prompt or "").encode("utf-8", errors="replace")).hexdigest()
        audit_log(
            "openai_responses_create",
            {
                "tool": "ictihat_agent_summarizer",
                "user_id": int(user_id),
                "chat_id": int(chat_id),
                "model": str(getattr(resp, "model", None) or resolved_model),
                "input": {"prompt_len": int(len(prompt or "")), "prompt_sha256": sha, "prompt_head": (prompt or "")[:1500]},
                "output": {"output_text": out_text},
                "usage_raw": getattr(resp, "usage", None),
            },
        )
    except Exception:
        pass

    meta["summarized"] = True
    meta["output_tokens_est"] = int(count_tokens(out_text, model=resolved_model))

    # Best-effort usage accounting
    try:
        in_tok, out_tok, rsn_tok = extract_openai_token_usage(resp)
        model_name = extract_openai_model_name(resp, default=resolved_model)
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

    return out_text, meta

