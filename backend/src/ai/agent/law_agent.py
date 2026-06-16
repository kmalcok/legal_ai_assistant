from __future__ import annotations

import json
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from ...config import agent_config, load_env
from ..graph.handoff import transfer_to_main_agent, transfer_to_petition_agent
from ..graph.law_graph import build_law_graph
from ..graph.llm import build_chat_model, openai_web_search_tool
from ..graph.runtime import summarize_final_messages
from ..graph.tools import build_main_tools, build_petition_tools
from ..logging.agent_audit import audit_log

from .instructions import build_main_agent_instructions, build_petition_instructions


class LawAssistantAgent:
    """
    LangGraph multi-agent law assistant (replaces the openai-agents runtime).

    Two agents share one graph state:
      - ``main_agent``     : supervisor / general law assistant (this object's
                             ``instructions_text``); owns statute, gerekçe, RAG,
                             ictihat, document and web-search tools.
      - ``petition_agent`` : dilekçe specialist; owns the petition + calendar
                             tools. The supervisor hands off to it via
                             ``transfer_to_petition_agent``.

    The compiled graph is exposed as ``self.graph``; callers stream it through
    ``ai.graph.runtime.stream_law_graph`` and finalize with
    ``summarize_final_messages``.
    """

    def __init__(
        self,
        *,
        user_id: int,
        chat_id: int,
        model: Optional[str] = None,
        reasoning_pref: str = None,
        verbosity: Optional[str] = None,
        extra_instructions: Optional[str] = None,
    ):
        load_env()
        cfg = agent_config()

        self.user_id = int(user_id)
        self.chat_id = int(chat_id)
        self.ictihat_summarizer_token_threshold = int(cfg.ictihat_summarizer_token_threshold)
        # Per-turn caches shared with the tool closures (see ai.graph.tools).
        self._ictihat_items_by_id: dict[int, dict[str, Any]] = {}
        self._ictihat_text_by_id: dict[int, str] = {}

        self.model = (str(model or cfg.base_model).strip() or cfg.base_model).strip()
        self._reasoning_pref = reasoning_pref
        self._verbosity = verbosity

        extra = (extra_instructions or "").strip()
        main_instr = build_main_agent_instructions()
        petition_instr = build_petition_instructions()
        if extra:
            main_instr = main_instr + "\n\n" + extra
            petition_instr = petition_instr + "\n\n" + extra
        self.instructions_text = main_instr
        self.petition_instructions_text = petition_instr

        # Tools (closures capture `self` for user/chat ids + ictihat caches).
        main_tools = build_main_tools(self)
        petition_tools = build_petition_tools(self)
        to_petition = transfer_to_petition_agent()
        to_main = transfer_to_main_agent()
        main_all_tools = [*main_tools, to_petition]
        petition_all_tools = [*petition_tools, to_main]

        main_system = SystemMessage(content=main_instr)
        petition_system = SystemMessage(content=petition_instr)

        async def main_node(state: Dict[str, Any]) -> Dict[str, Any]:
            # Fresh model per call so the API-key rotator advances each turn.
            llm = build_chat_model(
                model=self.model,
                reasoning_effort=self._reasoning_pref,
                verbosity=self._verbosity,
            )
            bound = llm.bind_tools([*main_all_tools, openai_web_search_tool()])
            response = await bound.ainvoke([main_system, *list(state.get("messages") or [])])
            return {"messages": [response], "active_agent": "main"}

        async def petition_node(state: Dict[str, Any]) -> Dict[str, Any]:
            llm = build_chat_model(
                model=self.model,
                reasoning_effort=self._reasoning_pref,
                verbosity=self._verbosity,
            )
            bound = llm.bind_tools(petition_all_tools)
            response = await bound.ainvoke([petition_system, *list(state.get("messages") or [])])
            return {"messages": [response], "active_agent": "petition"}

        self.graph = build_law_graph(
            main_node=main_node,
            petition_node=petition_node,
            main_tools=main_all_tools,
            petition_tools=petition_all_tools,
        )

    def initial_state(self, *, payload_json: str) -> Dict[str, Any]:
        """Build the starting graph state for one turn."""
        return {
            "messages": [HumanMessage(content=payload_json)],
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "active_agent": "main",
            "petition_draft": {},
        }

    async def run(self, *, history: list[str], message: str, max_turns: int = 99):
        """
        Non-streaming convenience runner (kept for parity / ad-hoc use).
        ``agent_service`` streams the graph directly instead of calling this.
        """
        payload = {"Chat History": history, "User Message": message}
        payload_json = json.dumps(payload, ensure_ascii=False)
        audit_log(
            "law_agent_run_start",
            {
                "user_id": int(self.user_id),
                "chat_id": int(self.chat_id),
                "model": str(self.model),
                "max_turns": int(max_turns),
                "payload_len": len(payload_json),
                "history_count": len(history or []),
                "message_len": len(message or ""),
                "runtime": "langgraph",
            },
        )
        final_state = await self.graph.ainvoke(
            self.initial_state(payload_json=payload_json),
            config={"recursion_limit": int(max_turns) * 2 + 2},
        )
        summary = summarize_final_messages(final_state.get("messages") or [])
        try:
            audit_log(
                "law_agent_run_done",
                {
                    "user_id": int(self.user_id),
                    "chat_id": int(self.chat_id),
                    "model": str(self.model),
                    "final_text_len": len(summary.get("final_text") or ""),
                    "tool_calls": [c.get("tool") for c in summary.get("tool_calls") or []],
                    "usage": summary.get("usage"),
                    "runtime": "langgraph",
                },
            )
        except Exception:
            pass
        return summary
