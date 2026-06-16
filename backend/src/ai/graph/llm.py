from __future__ import annotations

from typing import Any, Optional

from langchain_openai import ChatOpenAI

from ...config import agent_config, load_env
from ..util.rotator import get_next_openai_api_key

# Reasoning efforts the OpenAI Responses API accepts directly under `reasoning.effort`.
_RESPONSES_REASONING_VALUES = {"none", "minimal", "low", "medium", "high", "xhigh"}


def build_chat_model(
    *,
    model: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None,
    streaming: bool = True,
) -> ChatOpenAI:
    """
    Build a ``ChatOpenAI`` bound to a freshly rotated OpenAI API key.

    This is the LangGraph replacement for the openai-agents
    ``build_agents_run_config`` + ``ModelSettings`` plumbing. We resolve the
    next key from the same rotator the rest of the app uses, then map the
    project's reasoning/verbosity preferences onto the Responses API.
    """
    # Imported lazily to avoid a circular import at module load time
    # (services package -> agent_service -> law_agent -> graph.llm).
    from ...services.user_app_config_service import (
        sanitize_reasoning_effort,
        sanitize_verbosity,
    )

    load_env()
    cfg = agent_config()

    resolved_model = (str(model or cfg.base_model).strip() or cfg.base_model).strip()
    _, api_key = get_next_openai_api_key()

    effort = sanitize_reasoning_effort(resolved_model, reasoning_effort)
    resolved_verbosity = sanitize_verbosity(resolved_model, verbosity)

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "api_key": api_key,
        # Use the Responses API so reasoning summaries + built-in web search work.
        "use_responses_api": True,
        "output_version": "responses/v1",
        "streaming": bool(streaming),
        "max_retries": int(cfg.openai_http_max_retries),
        "timeout": float(cfg.openai_http_timeout_seconds),
    }

    if effort and effort in _RESPONSES_REASONING_VALUES:
        kwargs["reasoning"] = {"effort": effort, "summary": "auto"}

    model_kwargs: dict[str, Any] = {}
    if resolved_verbosity:
        # Text verbosity lives under `text.verbosity` in the Responses API.
        model_kwargs["text"] = {"verbosity": resolved_verbosity}
    if model_kwargs:
        kwargs["model_kwargs"] = model_kwargs

    return ChatOpenAI(**kwargs)


def openai_web_search_tool() -> dict[str, Any]:
    """
    Built-in OpenAI web search tool descriptor for ``ChatOpenAI.bind_tools``.

    Mirrors the openai-agents ``WebSearchTool()`` that the main agent used.
    """
    return {"type": "web_search_preview"}
