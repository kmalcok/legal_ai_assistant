from __future__ import annotations

from typing import Awaitable, Callable, List

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .state import AgentState

AgentNode = Callable[[AgentState], Awaitable[dict]]


def _route_after_agent(state: AgentState, *, tools_node: str) -> str:
    """Route to the agent's ToolNode if the last message has tool calls, else end."""
    messages = state.get("messages") or []
    if not messages:
        return END
    last = messages[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return tools_node
    return END


def build_law_graph(
    *,
    main_node: AgentNode,
    petition_node: AgentNode,
    main_tools: List[BaseTool],
    petition_tools: List[BaseTool],
):
    """
    Wire the two-agent supervisor/handoff graph and compile it.

        START -> main_agent
        main_agent --(tool calls)--> main_tools --> main_agent
        main_agent --(no tool calls)--> END
        main_tools  --(transfer_to_petition_agent)--> petition_agent   [via Command]
        petition_agent --(tool calls)--> petition_tools --> petition_agent
        petition_agent --(no tool calls)--> END
        petition_tools --(transfer_to_main_agent)--> main_agent         [via Command]

    The handoff tools (included in ``main_tools`` / ``petition_tools``) return a
    ``Command(goto=...)`` so the ToolNode itself reroutes across agents while the
    shared ``AgentState`` is preserved.
    """
    graph = StateGraph(AgentState)

    graph.add_node("main_agent", main_node)
    graph.add_node("main_tools", ToolNode(main_tools))
    graph.add_node("petition_agent", petition_node)
    graph.add_node("petition_tools", ToolNode(petition_tools))

    graph.add_edge(START, "main_agent")

    graph.add_conditional_edges(
        "main_agent",
        lambda state: _route_after_agent(state, tools_node="main_tools"),
        {"main_tools": "main_tools", END: END},
    )
    graph.add_edge("main_tools", "main_agent")

    graph.add_conditional_edges(
        "petition_agent",
        lambda state: _route_after_agent(state, tools_node="petition_tools"),
        {"petition_tools": "petition_tools", END: END},
    )
    graph.add_edge("petition_tools", "petition_agent")

    return graph.compile()
