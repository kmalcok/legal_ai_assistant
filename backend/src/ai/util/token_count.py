from __future__ import annotations

import tiktoken


def count_tokens(text: str, *, model: str = "gpt-5-nano") -> int:
    """
    Best-effort token counter for OpenAI text models.
    Falls back to o200k_base if model mapping is unknown.
    """
    s = text if isinstance(text, str) else str(text or "")
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("o200k_base")
    try:
        return int(len(enc.encode(s)))
    except Exception:
        return int(max(0, len(s) // 4))
