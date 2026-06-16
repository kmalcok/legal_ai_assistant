from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

# Handoff/control tools are internal plumbing; never surface them to the UI or
# to the downstream tool-call analytics.
HANDOFF_TOOL_NAMES = {"transfer_to_petition_agent", "transfer_to_main_agent"}


def _content_blocks(content: Any) -> List[Any]:
    if content is None:
        return []
    if isinstance(content, list):
        return content
    return [content]


def extract_text_from_message(message: Any) -> str:
    """Concatenate user-visible text from a (chunk) message's content."""
    content = getattr(message, "content", message)
    parts: list[str] = []
    for block in _content_blocks(content):
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            btype = block.get("type")
            if btype in ("text", "output_text") and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "".join(parts)


def extract_reasoning_from_message(message: Any) -> str:
    """Best-effort reasoning-summary extraction (Responses API blocks)."""
    parts: list[str] = []
    for block in _content_blocks(getattr(message, "content", None)):
        if not isinstance(block, dict):
            continue
        if block.get("type") != "reasoning":
            continue
        summary = block.get("summary")
        if isinstance(summary, list):
            for s in summary:
                if isinstance(s, dict) and isinstance(s.get("text"), str):
                    parts.append(s["text"])
        elif isinstance(block.get("text"), str):
            parts.append(block["text"])

    if not parts:
        extra = getattr(message, "additional_kwargs", None)
        if isinstance(extra, dict):
            rsn = extra.get("reasoning")
            if isinstance(rsn, dict):
                summary = rsn.get("summary")
                if isinstance(summary, list):
                    for s in summary:
                        if isinstance(s, dict) and isinstance(s.get("text"), str):
                            parts.append(s["text"])
    return "".join(parts)


def _count_web_search(message: AIMessage) -> int:
    count = 0
    for block in _content_blocks(getattr(message, "content", None)):
        if isinstance(block, dict) and "web_search" in str(block.get("type") or ""):
            count += 1
    extra = getattr(message, "additional_kwargs", None)
    if isinstance(extra, dict):
        for item in (extra.get("tool_outputs") or []):
            if isinstance(item, dict) and "web_search" in str(item.get("type") or ""):
                count += 1
    return count


def _stringify_tool_output(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in _content_blocks(content):
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)


def summarize_final_messages(messages: List[BaseMessage]) -> Dict[str, Any]:
    """
    Reduce a finished graph run's messages into the shapes ``AgentService``
    expects (mirrors the old ``_extract_tool_call_data`` + usage extraction).

    Returns a dict with:
      - final_text:        user-facing answer (last AIMessage without tool calls)
      - reasoning_text:    concatenated reasoning summaries (best-effort)
      - tool_calls:        [{"tool", "args"}]   (handoff tools excluded)
      - tool_outputs:      [{"tool", "output"}] (handoff tools excluded)
      - web_search_count:  built-in web search invocations
      - usage:             (input_tokens, output_tokens, reasoning_tokens)
    """
    name_by_call_id: dict[str, str] = {}
    tool_calls: list[dict] = []
    tool_outputs: list[dict] = []
    web_search_count = 0

    in_tok = 0
    out_tok = 0
    rsn_tok = 0
    have_usage = False

    reasoning_parts: list[str] = []

    for message in messages or []:
        if isinstance(message, AIMessage):
            for tc in (message.tool_calls or []):
                name = tc.get("name")
                if not name or name in HANDOFF_TOOL_NAMES:
                    continue
                call_id = tc.get("id")
                if call_id:
                    name_by_call_id[call_id] = name
                tool_calls.append({"tool": name, "args": tc.get("args")})

            web_search_count += _count_web_search(message)

            rsn = extract_reasoning_from_message(message)
            if rsn:
                reasoning_parts.append(rsn)

            usage = getattr(message, "usage_metadata", None)
            if isinstance(usage, dict):
                have_usage = True
                in_tok += int(usage.get("input_tokens") or 0)
                out_tok += int(usage.get("output_tokens") or 0)
                details = usage.get("output_token_details")
                if isinstance(details, dict):
                    rsn_tok += int(details.get("reasoning") or 0)

        elif isinstance(message, ToolMessage):
            name = name_by_call_id.get(message.tool_call_id) or getattr(message, "name", None)
            if not name or name in HANDOFF_TOOL_NAMES:
                continue
            out_s = _stringify_tool_output(message.content)
            if out_s.strip():
                tool_outputs.append({"tool": name, "output": out_s})

    final_text = ""
    for message in reversed(messages or []):
        if isinstance(message, AIMessage) and not (message.tool_calls or []):
            final_text = extract_text_from_message(message)
            if final_text.strip():
                break

    usage_tuple = (
        (in_tok if in_tok else None, out_tok if out_tok else None, rsn_tok if rsn_tok else None)
        if have_usage
        else (None, None, None)
    )

    return {
        "final_text": final_text,
        "reasoning_text": "".join(reasoning_parts).strip(),
        "tool_calls": tool_calls,
        "tool_outputs": tool_outputs,
        "web_search_count": web_search_count,
        "usage": usage_tuple,
    }


async def stream_law_graph(
    graph: Any,
    initial_state: Dict[str, Any],
    *,
    recursion_limit: int,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Stream a compiled law graph, yielding normalized events:

      {"kind": "text",      "text": <delta>}        token of the visible answer
      {"kind": "reasoning", "text": <delta>}        reasoning-summary delta
      {"kind": "tool_call", "name": <str>, "args": <dict>}
      {"kind": "final",     "state": <final AgentState>}

    The trailing ``final`` event carries the full state so callers can run
    ``summarize_final_messages(state["messages"])`` for persistence/usage.
    """
    config = {"recursion_limit": int(recursion_limit)}
    final_state: Dict[str, Any] | None = None

    async for mode, data in graph.astream(
        initial_state,
        stream_mode=["messages", "updates", "values"],
        config=config,
    ):
        if mode == "messages":
            message, _meta = data
            text = extract_text_from_message(message)
            if text:
                yield {"kind": "text", "text": text}
            reasoning = extract_reasoning_from_message(message)
            if reasoning:
                yield {"kind": "reasoning", "text": reasoning}

        elif mode == "updates":
            for _node, update in (data or {}).items():
                if not isinstance(update, dict):
                    continue
                for message in (update.get("messages") or []):
                    for tc in (getattr(message, "tool_calls", None) or []):
                        name = tc.get("name")
                        if not name or name in HANDOFF_TOOL_NAMES:
                            continue
                        yield {"kind": "tool_call", "name": name, "args": tc.get("args")}

        elif mode == "values":
            final_state = data

    yield {"kind": "final", "state": final_state or {}}
