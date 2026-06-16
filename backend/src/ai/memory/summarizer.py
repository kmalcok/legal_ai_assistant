from __future__ import annotations

import asyncio
import hashlib
from typing import List, Optional, Tuple

from ...config import agent_config, load_env
from ...usage.extractors import extract_openai_token_usage, extract_openai_model_name, normalize_model_for_billing
from ...usage.usage_service import UsageService
from ..client.openai_clients import get_openai_responses_client
from ..logging.agent_audit import audit_log
from ..util.instruction_loader import load_prompt_text
from ..util.token_count import count_tokens


class Summarizer:
    """
    Background summarization for memory compression.

    We use the OpenAI Responses API directly here (not the Agents SDK),
    because summarization is an internal maintenance operation.
    """

    def __init__(self):
        load_env()
        self.cfg = agent_config()

    def count_context_tokens(self, context: List[str], *, model: Optional[str] = None) -> int:
        joined = "\n".join([str(x) for x in (context or []) if isinstance(x, str) and x.strip()])
        model_name = (model or self.cfg.base_model or "gpt-5.2").strip() or "gpt-5.2"
        return int(count_tokens(joined, model=model_name))

    async def summarize(
        self,
        *,
        user_id: int,
        chat_id: int,
        context: List[str],
        model: str = "gpt-4.1-mini",
    ) -> str:
        text = "\n".join(context)
        tmpl = load_prompt_text("memory_summarize.md")
        prompt = tmpl.replace("{{CHAT_HISTORY}}", text)
        client = await get_openai_responses_client()
        async with asyncio.timeout(self.cfg.summarizer_timeout_seconds):
            resp = await client.responses.create(
                model=model,
                input=prompt,
                max_output_tokens=1800,
            )

        # Best-effort audit log (store small prompt fingerprint + output)
        try:
            sha = hashlib.sha256((prompt or "").encode("utf-8", errors="replace")).hexdigest()
            audit_log(
                "openai_responses_create",
                {
                    "tool": "memory_summarizer",
                    "user_id": int(user_id),
                    "chat_id": int(chat_id),
                    "model": str(getattr(resp, "model", None) or model),
                    "input": {"prompt_len": int(len(prompt or "")), "prompt_sha256": sha, "prompt_head": (prompt or "")[:1500]},
                    "output": {"output_text": getattr(resp, "output_text", "") or ""},
                    "usage_raw": getattr(resp, "usage", None),
                },
            )
        except Exception:
            pass

        # Best-effort usage accounting
        try:
            in_tok, out_tok, rsn_tok = extract_openai_token_usage(resp)
            model_name = extract_openai_model_name(resp, default=model)
            billing_model = normalize_model_for_billing(model_name) or model_name
            usage = UsageService()
            if isinstance(in_tok, int) and in_tok > 0:
                await usage.record_token_usage(
                    user_id=user_id, chat_id=chat_id, usage_type="input_tokens", amount=in_tok, model=billing_model
                )
            if isinstance(out_tok, int) and out_tok > 0:
                await usage.record_token_usage(
                    user_id=user_id, chat_id=chat_id, usage_type="output_tokens", amount=out_tok, model=billing_model
                )
            if isinstance(rsn_tok, int) and rsn_tok > 0:
                await usage.record_token_usage(
                    user_id=user_id, chat_id=chat_id, usage_type="reasoning_tokens", amount=rsn_tok, model=billing_model
                )
        except Exception:
            pass

        return resp.output_text


