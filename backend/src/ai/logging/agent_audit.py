from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable

from ...config import log_config
from ...usage.extractors import extract_agents_sdk_usage


def _backend_root() -> Path:
    # .../backend/src/utils/agent_audit.py -> parents[2] == backend/
    return Path(__file__).resolve().parents[2]


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


def _truncate_text(s: str, limit: int) -> str:
    if not isinstance(s, str):
        s = str(s)
    limit = max(200, int(limit))
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def _redact_secrets_in_text(s: str) -> str:
    """
    Best-effort redaction for obvious secrets (API keys, bearer tokens).
    We keep this conservative to avoid mangling normal legal texts.
    """
    if not isinstance(s, str) or not s:
        return s
    out = s
    # OpenAI-style keys
    out = out.replace("sk-", "sk-REDACTED-")
    # Authorization: Bearer <token>
    out = out.replace("Authorization: Bearer ", "Authorization: Bearer REDACTED-")
    out = out.replace("authorization: Bearer ", "authorization: Bearer REDACTED-")
    return out


def _summarize_strings(arr: Iterable[str], *, max_items: int = 80) -> Dict[str, Any]:
    items = list(arr) if arr is not None else []
    lengths = [len(str(x or "")) for x in items]
    return {
        "count": len(items),
        "total_chars": int(sum(lengths)),
        "max_chars": int(max(lengths) if lengths else 0),
        "min_chars": int(min(lengths) if lengths else 0),
        "head_chars": int(lengths[0] if lengths else 0),
        "tail_chars": int(lengths[-1] if lengths else 0),
        "sample_head": (items[0] if items else ""),
        "sample_tail": (items[-1] if items else ""),
        "sample_mid": (items[len(items) // 2] if len(items) >= 3 else ""),
        "max_items_capped": int(max_items),
    }


def audit_log(event: str, payload: Dict[str, Any]) -> None:
    """
    Append one JSON object per line to backend/agent.json when AGENT_AUDIT_LOG=1.

    NOTE: File format is JSONL (one JSON object per line) but filename is `agent.json`
    per project convention/request.
    """
    cfg = log_config()
    enabled = bool(cfg.agent_audit_logging_enabled)
    if not enabled:
        return

    max_chars = int(cfg.agent_audit_max_chars)

    try:
        record = {
            "ts": int(time.time()),
            "event": str(event or ""),
            "_audit": {
                "enabled": True,
                "enabled_by": "log_config.agent_audit_logging_enabled",
                "max_chars": int(max_chars),
            },
            **(payload or {}),
        }

        # Redact + truncate large string fields (recursive, best-effort).
        def _clean(obj: Any) -> Any:
            if obj is None:
                return None
            if isinstance(obj, str):
                return _truncate_text(_redact_secrets_in_text(obj), max_chars)
            if isinstance(obj, (int, float, bool)):
                return obj
            if isinstance(obj, list):
                return [_clean(x) for x in obj[:500]]  # hard cap to avoid huge dumps
            if isinstance(obj, dict):
                out: Dict[str, Any] = {}
                for k, v in list(obj.items())[:500]:
                    out[str(k)] = _clean(v)
                return out
            # fallback
            return _truncate_text(_redact_secrets_in_text(str(obj)), max_chars)

        cleaned = _clean(record)
        path = _backend_root() / "agent.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(cleaned, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # Never break the app due to logging.
        return


def build_run_audit_payload(
    *,
    user_id: int,
    chat_id: int,
    model: str,
    instructions: str,
    tools_count: int,
    history: list[str],
    message: str,
    runner_payload_json: str,
    result_output_text: str | None,
    result_final_output: Any,
    usage: Any,
) -> Dict[str, Any]:
    """
    Build a rich payload for debugging why main-agent input tokens are high.
    """
    try:
        hist_summary = _summarize_strings(history, max_items=80)
    except Exception:
        hist_summary = {"count": len(history or [])}
    in_tok, out_tok, rsn_tok = extract_agents_sdk_usage(usage)
    total_tok = None
    try:
        parts = [x for x in (in_tok, out_tok, rsn_tok) if isinstance(x, int)]
        total_tok = int(sum(parts)) if parts else None
    except Exception:
        total_tok = None
    return {
        "user_id": int(user_id),
        "chat_id": int(chat_id),
        "model": str(model or ""),
        "instructions_len": len(instructions or ""),
        "tools_count": int(tools_count),
        "history": hist_summary,
        "message": str(message or ""),
        "message_len": len(message or ""),
        "runner_payload_json": str(runner_payload_json or ""),
        "runner_payload_len": len(runner_payload_json or ""),
        "result": {
            "output_text": (result_output_text or ""),
            "output_text_len": len(result_output_text or ""),
            "final_output": result_final_output,
        },
        "usage_raw": usage,
        "usage": {
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "reasoning_tokens": rsn_tok,
            "total_tokens": total_tok,
        },
    }

