from __future__ import annotations

import re
from typing import Any, Optional, Tuple


# Model isimlerindeki tarih son-eklerini yakalayan desenler.
# OpenAI modelleri donus yanıtlarında tarihli snapshot isimleri dondurur;
# faturalama icin taban model ismine normalize etmemiz gerekir.
_DATE_SUFFIX_ISO = re.compile(r"^(?P<base>.+)-(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})$")   # gpt-5-nano-2025-08-07
_DATE_SUFFIX_COMPACT = re.compile(r"^(?P<base>.+)-(?P<ymd>\d{8})$")                         # gpt-4-turbo-20240409
_DATE_SUFFIX_MMDD = re.compile(r"^(?P<base>.+)-(?P<md>\d{4})$")                             # gpt-4-0613 (eski format)


def normalize_model_for_billing(model: str) -> str:
    """
    Model isimlerini faturalama tablosundaki `model_prices.model_name` ile
    eslestirmek icin normalize eder. Tarih son-eklerini temizler.

    Desteklenen formatlar:
      - "gpt-5-nano-2025-08-07"   -> "gpt-5-nano"   (ISO tarih)
      - "gpt-4-turbo-20240409"    -> "gpt-4-turbo"   (kompakt tarih)
      - "gpt-4-0613"              -> "gpt-4"          (eski MMDD formati)
      - "text-embedding-3-small"  -> "text-embedding-3-small"  (tarihsiz, degismez)
    """
    s = (model or "").strip()
    if not s:
        return ""
    # ISO tarih: YYYY-MM-DD
    m = _DATE_SUFFIX_ISO.match(s)
    if m:
        return (m.group("base") or "").strip()
    # Kompakt tarih: YYYYMMDD (8 haneli sayi son eki)
    m = _DATE_SUFFIX_COMPACT.match(s)
    if m:
        return (m.group("base") or "").strip()
    # Eski format: MMDD (4 haneli sayi son eki, orn. gpt-4-0613)
    m = _DATE_SUFFIX_MMDD.match(s)
    if m:
        return (m.group("base") or "").strip()
    return s


def extract_openai_model_name(response: Any, *, default: str) -> str:
    """
    Extract the provider model string from an OpenAI response-like object.
    Works for Responses API objects and dict-like structures.
    """
    try:
        val = getattr(response, "model", None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass

    if isinstance(response, dict):
        for key in ("model", "model_name"):
            val = response.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    return default


def extract_openai_token_usage(response: Any) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Extract (input_tokens, output_tokens, reasoning_tokens) from an OpenAI
    response-like object.

    Supports:
    - Responses API: usage.input_tokens / output_tokens / reasoning_tokens
    - Embeddings/Completions-style: usage.prompt_tokens / completion_tokens / total_tokens
    - dict-like responses with "usage" mapping
    """
    usage: Any = None
    if isinstance(response, dict):
        usage = response.get("usage")
    else:
        try:
            usage = getattr(response, "usage", None)
        except Exception:
            usage = None

    # Responses API (preferred)
    input_tokens = None
    output_tokens = None
    reasoning_tokens = None
    if usage is not None:
        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            reasoning_tokens = usage.get("reasoning_tokens")
        else:
            input_tokens = getattr(usage, "input_tokens", None)
            output_tokens = getattr(usage, "output_tokens", None)
            reasoning_tokens = getattr(usage, "reasoning_tokens", None)

    # Embeddings / legacy completions usage
    if input_tokens is None and usage is not None:
        if isinstance(usage, dict):
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
        else:
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)

    # Some endpoints only provide total_tokens (treat as input when output is unknown)
    if input_tokens is None and usage is not None and output_tokens is None:
        try:
            total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else getattr(usage, "total_tokens", None)
            if isinstance(total_tokens, int):
                input_tokens = total_tokens
        except Exception:
            pass

    if reasoning_tokens is None and usage is not None:
        try:
            out_details = usage.get("output_tokens_details") if isinstance(usage, dict) else getattr(usage, "output_tokens_details", None)
            reasoning_tokens = (
                out_details.get("reasoning_tokens")
                if isinstance(out_details, dict)
                else getattr(out_details, "reasoning_tokens", None)
            )
        except Exception:
            reasoning_tokens = None

    return (
        int(input_tokens) if isinstance(input_tokens, int) else None,
        int(output_tokens) if isinstance(output_tokens, int) else None,
        int(reasoning_tokens) if isinstance(reasoning_tokens, int) else None,
    )


def extract_agents_sdk_usage(raw_obj: object) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Best-effort extractor for Agents SDK results:
    (input_tokens, output_tokens, reasoning_tokens)

    The Agents SDK often places usage at result.context_wrapper.usage, but the
    shape can vary. We scan common patterns (attrs, mappings, nested usage).
    """
    from collections.abc import Mapping

    visited: set[int] = set()

    def _walk(obj: object) -> Optional[Mapping[str, object]]:
        if obj is None:
            return None
        oid = id(obj)
        if oid in visited:
            return None
        visited.add(oid)

        # Object with token-ish attrs
        has_input = hasattr(obj, "input_tokens")
        has_output = hasattr(obj, "output_tokens")
        has_reasoning = hasattr(obj, "reasoning_tokens")
        has_out_details = hasattr(obj, "output_tokens_details")
        if has_input or has_output or has_reasoning or has_out_details:
            try:
                return {
                    "input_tokens": getattr(obj, "input_tokens", None),
                    "output_tokens": getattr(obj, "output_tokens", None),
                    "reasoning_tokens": getattr(obj, "reasoning_tokens", None),
                    "output_tokens_details": getattr(obj, "output_tokens_details", None),
                }
            except Exception:
                pass

        if isinstance(obj, Mapping):
            if any(k in obj for k in ("input_tokens", "output_tokens", "reasoning_tokens")):
                return obj
            usage_val = obj.get("usage")
            if isinstance(usage_val, Mapping):
                found = _walk(usage_val)
                if found is not None:
                    return found
            for v in obj.values():
                found = _walk(v)
                if found is not None:
                    return found
            return None

        if isinstance(obj, (list, tuple, set)):
            for v in obj:
                found = _walk(v)
                if found is not None:
                    return found
            return None

        if hasattr(obj, "usage"):
            try:
                found = _walk(getattr(obj, "usage"))
                if found is not None:
                    return found
            except Exception:
                pass

        for attr_name in ("model_dump", "dict"):
            if hasattr(obj, attr_name):
                try:
                    dumped = getattr(obj, attr_name)()
                except Exception:
                    dumped = None
                if isinstance(dumped, Mapping):
                    found = _walk(dumped)
                    if found is not None:
                        return found

        return None

    mapping = _walk(raw_obj)
    if not isinstance(mapping, Mapping):
        return None, None, None

    input_tokens = mapping.get("input_tokens")
    output_tokens = mapping.get("output_tokens")
    reasoning_tokens = mapping.get("reasoning_tokens")
    if reasoning_tokens is None:
        out_details = mapping.get("output_tokens_details")
        if isinstance(out_details, Mapping):
            reasoning_tokens = out_details.get("reasoning_tokens")
        elif hasattr(out_details, "reasoning_tokens"):
            try:
                reasoning_tokens = getattr(out_details, "reasoning_tokens")
            except Exception:
                reasoning_tokens = None

    return (
        int(input_tokens) if isinstance(input_tokens, int) else None,
        int(output_tokens) if isinstance(output_tokens, int) else None,
        int(reasoning_tokens) if isinstance(reasoning_tokens, int) else None,
    )


