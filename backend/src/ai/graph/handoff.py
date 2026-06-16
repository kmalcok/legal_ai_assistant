from __future__ import annotations

from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.types import Command


def make_handoff_tool(*, target_node: str, name: str, description: str) -> BaseTool:
    """
    Build a handoff tool that transfers control to another node in the graph.

    When an agent calls this tool, the ToolNode executes it and returns a
    ``Command`` that both (a) records a ToolMessage answering the tool call and
    (b) routes the graph straight to ``target_node`` while keeping the shared
    state intact. This is how the supervisor (main agent) hands a turn to the
    petition agent and how the petition agent can hand it back.
    """

    @tool(name, description=description)
    def _handoff(tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
        tool_message = ToolMessage(
            content=f"Kontrol '{target_node}' düğümüne devredildi.",
            name=name,
            tool_call_id=tool_call_id,
        )
        active = "petition" if target_node == "petition_agent" else "main"
        return Command(
            goto=target_node,
            update={"messages": [tool_message], "active_agent": active},
        )

    return _handoff


def transfer_to_petition_agent() -> BaseTool:
    return make_handoff_tool(
        target_node="petition_agent",
        name="transfer_to_petition_agent",
        description=(
            "Dilekçe (petition) oluşturma, revize etme, özetleme veya dilekçeye bağlı "
            "süre/zamanaşımı takvimi işlerini DİLEKÇE AJANINA devret. Kullanıcı bir dilekçe "
            "hazırlanmasını/değiştirilmesini istediğinde bu aracı çağır."
        ),
    )


def transfer_to_main_agent() -> BaseTool:
    return make_handoff_tool(
        target_node="main_agent",
        name="transfer_to_main_agent",
        description=(
            "Dilekçe işi tamamlandığında veya talep dilekçe kapsamı dışında kaldığında "
            "kontrolü ANA HUKUK ASİSTANINA geri devret."
        ),
    )
