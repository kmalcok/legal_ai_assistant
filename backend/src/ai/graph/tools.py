from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Protocol

from langchain_core.tools import BaseTool, tool

from ...config import agent_config
from ...realtime.ws_manager import chat_ws_manager
from ...utils.dev_logging import dev_log
from ..tool_wrappers.calendar import calendar_add_event as _calendar_add_event
from ..tool_wrappers.documents import (
    doc_get_page_map as _doc_get_page_map,
    doc_get_pages as _doc_get_pages,
    doc_list as _doc_list,
)
from ..tool_wrappers.gerekce import gerekce_get_chunk as _gerekce_get_chunk
from ..tool_wrappers.get_madde import get_madde_by_reference as _get_madde
from ..tool_wrappers.ictihat_get_document import ictihat_get_document as _ictihat_get_document
from ..tool_wrappers.ictihat_push import ictihat_push_to_chat as _ictihat_push_to_chat
from ..tool_wrappers.ictihat_semantic_agent import ictihat_semantic_search as _ictihat_semantic_search
from ..tool_wrappers.petitions import (
    petition_generate as _petition_generate,
    petition_get_summary as _petition_get_summary,
    petition_list as _petition_list,
    petition_revise as _petition_revise,
)
from ..tool_wrappers.rag_search import rag_search as _rag_search
from ..tool_wrappers.word_output import word_render_docx as _word_render_docx
from ..util.ictihat_agent_summarizer import summarize_ictihat_for_agent


class ToolContext(Protocol):
    """Minimal surface the tool closures need from the owning agent."""

    user_id: int
    chat_id: int
    ictihat_summarizer_token_threshold: int
    _ictihat_items_by_id: dict[int, dict[str, Any]]
    _ictihat_text_by_id: dict[int, str]


def build_main_tools(ctx: ToolContext) -> List[BaseTool]:
    """
    LangChain ports of the main law agent's openai-agents function tools.

    Each tool captures ``ctx`` so the per-turn ``user_id`` / ``chat_id`` and the
    ictihat de-dup caches behave exactly like the SDK closures did.
    """

    cfg = agent_config()

    @tool
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
        """Belirli bir kanun maddesini referansına göre getir (sayfalı, ucuz)."""
        res = await _get_madde(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
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

    @tool
    async def rag_search(
        query: str,
        top_k: int = 3,
        filters_json: str | None = None,
        mode: str = "maddes",
        chunk_k: int | None = None,
    ) -> str:
        """Mevzuat/kaynak üzerinde semantik (RAG) arama yap."""
        try:
            filters: Dict[str, Any] | None = json.loads(filters_json) if filters_json else None
        except Exception:
            filters = None
        res = await _rag_search(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            query=query,
            top_k=top_k,
            filters=filters,
            mode=mode,
            chunk_k=chunk_k,
        )
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def ictihat_search(intent_text: str) -> str:
        """Niyet metnine göre yüksek yargı kararlarında (içtihat) semantik arama yap."""
        debug = bool(cfg.ictihat_search_agent_debug)
        if debug:
            dev_log(
                "ictihat_search_agent",
                "law_agent_ictihat_search_tool_call",
                {
                    "user_id": int(ctx.user_id),
                    "chat_id": int(ctx.chat_id),
                    "intent_preview": (intent_text or "")[:600],
                    "intent_len": len(intent_text or ""),
                },
            )
        try:
            await chat_ws_manager.publish(int(ctx.chat_id), {"type": "ictihat_searching", "chat_id": int(ctx.chat_id)})
        except Exception:
            pass
        res = await _ictihat_semantic_search(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            intent_text=intent_text,
        )
        # Cache items[].text so a follow-up ictihat_get_document in the same turn
        # does not re-inject the same document text into context.
        try:
            if isinstance(res, dict) and res.get("ok") and isinstance(res.get("items"), list):
                for it in (res.get("items") or []):
                    if not isinstance(it, dict):
                        continue
                    try:
                        did = int(it.get("document_id"))
                    except Exception:
                        continue
                    if did <= 0:
                        continue
                    ctx._ictihat_items_by_id[did] = dict(it)
                    t = it.get("text")
                    if isinstance(t, str) and t.strip():
                        ctx._ictihat_text_by_id[did] = t
        except Exception:
            pass
        try:
            await chat_ws_manager.publish(
                int(ctx.chat_id),
                {
                    "type": "ictihat_search_done",
                    "chat_id": int(ctx.chat_id),
                    "ok": bool(res.get("ok")) if isinstance(res, dict) else True,
                    "reason": (res.get("reason") if isinstance(res, dict) else None),
                },
            )
        except Exception:
            pass
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def ictihat_get_document(
        document_id: int = 0,
        kurum: str | None = None,
        daire: str | None = None,
        karar_no: int | None = None,
        karar_sira: int | None = None,
        emsal_no: str | int | None = None,
        emsal_sira: str | int | None = None,
        karar_tarihi: str | None = None,
        olay_context: str | None = None,
    ) -> str:
        """Tam içtihat metnini getir (aynı turda ictihat_search ile gelmişse bastırılır)."""
        try:
            did_req = int(document_id or 0)
        except Exception:
            did_req = 0
        try:
            if did_req > 0 and did_req in ctx._ictihat_text_by_id:
                it = ctx._ictihat_items_by_id.get(did_req) if isinstance(ctx._ictihat_items_by_id, dict) else None
                meta = None
                if isinstance(it, dict):
                    meta = {
                        "document_id": did_req,
                        "kurum": it.get("kurum"),
                        "daire": it.get("daire"),
                        "esas": it.get("esas"),
                        "karar": it.get("karar"),
                    }
                return json.dumps(
                    {
                        "ok": True,
                        "reason": "already_in_context_from_ictihat_search",
                        "document_id": did_req,
                        "doc": meta,
                        "note": "Bu document_id için metin aynı tur içinde ictihat_search çıktısında zaten vardı (items[].text). "
                        "Tekrar metin enjekte etmemek için ictihat_get_document bastırıldı; lütfen önce mevcut ictihat_search.items[].text'i kullan.",
                    },
                    ensure_ascii=False,
                )
        except Exception:
            pass
        res = await _ictihat_get_document(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            document_id=int(document_id or 0),
            kurum=kurum,
            daire=daire,
            karar_no=karar_no,
            karar_sira=karar_sira,
            emsal_no=emsal_no,
            emsal_sira=emsal_sira,
            karar_tarihi=karar_tarihi,
        )
        try:
            if isinstance(res, dict) and res.get("ok") and isinstance(res.get("text"), str) and res.get("text"):
                summarized, meta = await summarize_ictihat_for_agent(
                    user_id=int(ctx.user_id),
                    chat_id=int(ctx.chat_id),
                    document_text=str(res.get("text") or ""),
                    olay_context=olay_context,
                    token_threshold=int(ctx.ictihat_summarizer_token_threshold),
                )
                res = dict(res)
                res["text"] = summarized
                try:
                    resolved_document_id = int(document_id or 0)
                    try:
                        if isinstance(res, dict):
                            resolved_document_id = int(((res.get("doc") or {}).get("document_id")) or resolved_document_id)
                    except Exception:
                        pass
                    dev_log(
                        "ictihat",
                        "ictihat_agent_summarization",
                        {
                            "user_id": int(ctx.user_id),
                            "chat_id": int(ctx.chat_id),
                            "document_id": int(resolved_document_id),
                            "meta": meta,
                        },
                    )
                except Exception:
                    pass
        except Exception:
            pass
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def ictihat_present(
        ictihat_list_json: str,
        limit_docs: int = 5,
        limit_chars_per_doc: int = 0,
    ) -> str:
        """Seçilen içtihatları sohbet panelinde kullanıcıya göster.

        ictihat_list_json: JSON list of objects:
        [{document_id, kurum, daire, esas_yil, esas_sira, karar_yil, karar_sira, karar_tarihi}, ...]
        """
        try:
            arr = json.loads(ictihat_list_json or "[]")
            items = arr if isinstance(arr, list) else []
        except Exception:
            items = []
        res = await _ictihat_push_to_chat(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            ictihat_items=items,
            limit_docs=int(limit_docs),
            limit_chars_per_doc=int(limit_chars_per_doc),
        )
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def recommend_ictihat_search(
        query_text: str | None = None,
        title: str | None = None,
        message: str | None = None,
        action_label: str | None = None,
    ) -> str:
        """Kullanıcıyı AI İçtihat Arama özelliğine yönlendiren hafif bir UI ipucu üret."""
        res = {
            "ok": True,
            "feature": "ictihat_search",
            "query_text": str(query_text or "").strip() or None,
            "title": str(title or "").strip() or None,
            "message": str(message or "").strip() or None,
            "action_label": str(action_label or "").strip() or None,
        }
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def gerekce_get_chunk(
        law_no: int,
        kind: str = "genel",
        madde_no: int | str | None = None,
        page_chars: int = 600,
        cursor_char_offset: int = 0,
        include_full_text: bool = False,
    ) -> str:
        """Kanun gerekçesi metnini (genel ya da madde bazlı) sayfalı olarak getir."""
        res = await _gerekce_get_chunk(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            law_no=int(law_no),
            kind=kind,
            madde_no=madde_no,
            page_chars=int(page_chars),
            cursor_char_offset=int(cursor_char_offset),
            include_full_text=bool(include_full_text),
        )
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def word_render_docx(doc_json: str, filename: str | None = None) -> str:
        """Serbest biçimli bir belgeyi (ör. mütalaa) Word (.docx) olarak oluştur."""
        try:
            await chat_ws_manager.publish(int(ctx.chat_id), {"type": "word_preparing", "chat_id": int(ctx.chat_id)})
        except Exception:
            pass
        try:
            await asyncio.sleep(5)
        except Exception:
            pass
        res = await _word_render_docx(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            doc_json=doc_json,
            filename=filename,
        )
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def doc_list() -> str:
        """Bu sohbete eklenmiş kullanıcı belgelerini listele."""
        res = await _doc_list(user_id=ctx.user_id, chat_id=ctx.chat_id)
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def doc_get_pages(
        document_id: int,
        page_start: int,
        page_end: int,
        max_pages: int = 5,
    ) -> str:
        """Eklenmiş bir belgenin belirli sayfa aralığının metnini getir."""
        res = await _doc_get_pages(
            user_id=ctx.user_id,
            document_id=int(document_id),
            page_start=int(page_start),
            page_end=int(page_end),
            max_pages=int(max_pages),
        )
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def doc_get_page_map(
        document_id: int,
        page_start: int = 1,
        page_end: int = 50,
    ) -> str:
        """Eklenmiş bir belgenin sayfa haritasını (başlık/özet) getir."""
        res = await _doc_get_page_map(
            user_id=ctx.user_id,
            document_id=int(document_id),
            page_start=int(page_start),
            page_end=int(page_end),
        )
        return json.dumps(res, ensure_ascii=False)

    return [
        get_madde_by_reference,
        gerekce_get_chunk,
        word_render_docx,
        rag_search,
        ictihat_search,
        ictihat_get_document,
        ictihat_present,
        recommend_ictihat_search,
        doc_list,
        doc_get_pages,
        doc_get_page_map,
    ]


def build_petition_tools(ctx: ToolContext) -> List[BaseTool]:
    """
    LangChain ports of the petition (dilekçe) tools.

    These belong to the *petition agent* — the supervisor hands off here when a
    dilekçe needs to be drafted, revised, summarized or its deadlines tracked.
    """

    @tool
    async def petition_list(limit: int = 20) -> str:
        """Bu sohbetteki dilekçeleri listele."""
        res = await _petition_list(user_id=ctx.user_id, chat_id=ctx.chat_id, limit=limit)
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def petition_generate(petition_json: str, filename: str | None = None) -> str:
        """Verilen dilekçe JSON'undan yeni bir dilekçe (.docx) oluştur ve kaydet."""
        try:
            await chat_ws_manager.publish(
                int(ctx.chat_id),
                {"type": "petition_preparing", "chat_id": int(ctx.chat_id), "op": "generate"},
            )
        except Exception:
            pass
        res = await _petition_generate(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            petition_json=petition_json,
            filename=filename,
        )
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def petition_get_summary(petition_id: int, version_id: int | None = None) -> str:
        """Bir dilekçenin (belirli sürümünün) özetini getir."""
        res = await _petition_get_summary(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            petition_id=int(petition_id),
            version_id=int(version_id) if version_id is not None else None,
        )
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def petition_revise(petition_id: int, petition_json: str, filename: str | None = None) -> str:
        """Var olan bir dilekçeyi revize ederek yeni bir sürüm oluştur."""
        try:
            await chat_ws_manager.publish(
                int(ctx.chat_id),
                {"type": "petition_preparing", "chat_id": int(ctx.chat_id), "op": "revise"},
            )
        except Exception:
            pass
        res = await _petition_revise(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            petition_id=int(petition_id),
            petition_json=petition_json,
            filename=filename,
        )
        return json.dumps(res, ensure_ascii=False)

    @tool
    async def calendar_add_event(
        title: str,
        due_date: str,
        note: str | None = None,
        due_time: str | None = None,
        petition_id: int | None = None,
    ) -> str:
        """Kullanıcının takvimine bir süre/etkinlik ekle.

        Bir dilekçe 'Süre Notu' / 'Zamanaşımı Notu' içeriyorsa veya kullanıcı bir
        tarihi hatırlamanı isterse bunu kullan. `due_date`, GG.AA.YYYY veya
        YYYY-MM-DD biçimini kabul eder.
        """
        res = await _calendar_add_event(
            user_id=ctx.user_id,
            chat_id=ctx.chat_id,
            title=title,
            due_date=due_date,
            note=note,
            due_time=due_time,
            petition_id=int(petition_id) if petition_id is not None else None,
            source="petition_tool",
        )
        return json.dumps(res, ensure_ascii=False)

    return [
        petition_list,
        petition_generate,
        petition_get_summary,
        petition_revise,
        calendar_add_event,
    ]
