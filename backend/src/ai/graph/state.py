from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """
    Shared state for the multi-agent law graph.

    Both the main agent and the petition agent read/write this same dict, so
    anything one agent discovers (messages, selected ictihat docs, the active
    petition draft, ...) is visible to the other.
    """

    # Conversation transcript. ``add_messages`` merges/append-reduces on update,
    # so each node only returns the *new* messages it produced.
    messages: Annotated[list[Any], add_messages]

    # Per-turn identity, propagated into every tool call.
    user_id: int
    chat_id: int

    # Which agent is currently driving the turn ("main" | "petition").
    active_agent: str

    # Free-form shared scratchpad the petition agent can use to stash the
    # in-progress dilekçe JSON / metadata so the supervisor can reference it.
    petition_draft: dict[str, Any]
