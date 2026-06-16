from __future__ import annotations

import json
from typing import Any, Dict, Optional

from agents import Agent, Runner, WebSearchTool, function_tool, set_tracing_disabled

from ...config import agent_config, load_env
from ...services.user_app_config_service import build_model_settings
from ..client.openai_clients import build_agents_run_config
from ..tool_wrappers.documents import (
    doc_get_page_map as _doc_get_page_map,
    doc_get_pages as _doc_get_pages,
    doc_list as _doc_list,
)
from ..tool_wrappers.get_madde import get_madde_by_reference as _get_madde
from ..tool_wrappers.gerekce import gerekce_get_chunk as _gerekce_get_chunk
from ..tool_wrappers.rag_search import rag_search as _rag_search
from ..logging.agent_audit import audit_log, build_run_audit_payload

from .instructions import build_student_instructions


set_tracing_disabled(disabled=True)


class LawStudentAssistantAgent:
    """
    Lightweight law assistant focused on statute lookup, rationale lookup,
    attached-document reading, and web search.
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

        base_instr = build_student_instructions()
        if extra_instructions:
            base_instr = base_instr + "\n\n" + extra_instructions.strip()
        self.instructions_text = base_instr

        resolved_model = (str(model or cfg.base_model).strip() or cfg.base_model).strip()
        model_settings = build_model_settings(
            resolved_model,
            reasoning_effort=reasoning_pref,
            verbosity=verbosity,
            reasoning_summary="auto",
        )

        @function_tool
        async def get_madde_by_reference(
            kanun_no: int | None = None,
            doc_title_contains: str | None = None,
            section_type: str | None = None,
            madde_no: int | str | None = None,
            madde_ek: str | None = None,
            page_chars: int = 600,
            cursor_chunk_order: int = 0,
            cursor_char_offset: int = 0,
            limit_chunks: int = 200,
            include_full_text: bool = False,
        ) -> str:
            res = await _get_madde(
                user_id=self.user_id,
                chat_id=self.chat_id,
                kanun_no=kanun_no,
                doc_title_contains=doc_title_contains,
                section_type=section_type,
                madde_no=madde_no,
                madde_ek=madde_ek,
                limit_chunks=limit_chunks,
                page_chars=page_chars,
                cursor_chunk_order=cursor_chunk_order,
                cursor_char_offset=cursor_char_offset,
                include_full_text=include_full_text,
            )
            return json.dumps(res, ensure_ascii=False)

        @function_tool
        async def rag_search(
            query: str,
            top_k: int = 3,
            filters_json: str | None = None,
            mode: str = "maddes",
            chunk_k: int | None = None,
        ) -> str:
            try:
                filters: Dict[str, Any] | None = json.loads(filters_json) if filters_json else None
            except Exception:
                filters = None
            res = await _rag_search(
                user_id=self.user_id,
                chat_id=self.chat_id,
                query=query,
                top_k=top_k,
                filters=filters,
                mode=mode,
                chunk_k=chunk_k,
            )
            return json.dumps(res, ensure_ascii=False)

        @function_tool
        async def gerekce_get_chunk(
            law_no: int,
            kind: str = "genel",
            madde_no: int | str | None = None,
            page_chars: int = 600,
            cursor_char_offset: int = 0,
            include_full_text: bool = False,
        ) -> str:
            res = await _gerekce_get_chunk(
                user_id=self.user_id,
                chat_id=self.chat_id,
                law_no=int(law_no),
                kind=kind,
                madde_no=madde_no,
                page_chars=int(page_chars),
                cursor_char_offset=int(cursor_char_offset),
                include_full_text=bool(include_full_text),
            )
            return json.dumps(res, ensure_ascii=False)

        @function_tool
        async def doc_list() -> str:
            res = await _doc_list(user_id=self.user_id, chat_id=self.chat_id)
            return json.dumps(res, ensure_ascii=False)

        @function_tool
        async def doc_get_pages(
            document_id: int,
            page_start: int,
            page_end: int,
            max_pages: int = 5,
        ) -> str:
            res = await _doc_get_pages(
                user_id=self.user_id,
                document_id=int(document_id),
                page_start=int(page_start),
                page_end=int(page_end),
                max_pages=int(max_pages),
            )
            return json.dumps(res, ensure_ascii=False)

        @function_tool
        async def doc_get_page_map(
            document_id: int,
            page_start: int = 1,
            page_end: int = 50,
        ) -> str:
            res = await _doc_get_page_map(
                user_id=self.user_id,
                document_id=int(document_id),
                page_start=int(page_start),
                page_end=int(page_end),
            )
            return json.dumps(res, ensure_ascii=False)

        self.agent = Agent(
            name="Turk Mevzuat Asistani Ogrenci",
            instructions=self.instructions_text,
            model=resolved_model,
            tools=[
                get_madde_by_reference,
                gerekce_get_chunk,
                rag_search,
                WebSearchTool(),
                doc_list,
                doc_get_pages,
                doc_get_page_map,
            ],
            model_settings=model_settings,
        )

    async def run(self, *, history: list[str], message: str, max_turns: int = 99):
        payload = {"Chat History": history, "User Message": message}
        payload_json = json.dumps(payload, ensure_ascii=False)
        model_name = getattr(self.agent, "model", None) or agent_config().base_model
        tools_count = len(getattr(self.agent, "tools", []) or [])
        audit_log(
            "law_student_agent_run_start",
            {
                "user_id": int(self.user_id),
                "chat_id": int(self.chat_id),
                "model": str(model_name),
                "max_turns": int(max_turns),
                "payload_len": len(payload_json),
                "history_count": len(history or []),
                "message_len": len(message or ""),
            },
        )

        run_config = await build_agents_run_config()
        result = await Runner.run(self.agent, payload_json, max_turns=max_turns, run_config=run_config)

        try:
            audit_payload = build_run_audit_payload(
                user_id=int(self.user_id),
                chat_id=int(self.chat_id),
                model=str(model_name),
                instructions=str(self.instructions_text or ""),
                tools_count=int(tools_count),
                history=list(history or []),
                message=str(message or ""),
                runner_payload_json=str(payload_json),
                result_output_text=getattr(result, "output_text", None),
                result_final_output=getattr(result, "final_output", None),
                usage=getattr(result, "usage", None) or getattr(getattr(result, "context_wrapper", None), "usage", None),
            )
            audit_log("law_student_agent_run_done", audit_payload)
        except Exception:
            pass

        return result
