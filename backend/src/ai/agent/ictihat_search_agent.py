from __future__ import annotations

import re
import json
from typing import Any, Dict, Optional

from agents import Agent, function_tool, set_tracing_disabled

from ...config import agent_config, load_env
from ...services.user_app_config_service import build_model_settings, sanitize_reasoning_effort
from ..tool_wrappers.ictihat_search import ictihat_keyword_search as _ictihat_keyword_search
from ..tool_wrappers.ictihat_search import ictihat_search as _ictihat_search
from ..tool_wrappers.ictihat_get_document import ictihat_get_document as _ictihat_get_document
from ..util.ictihat_agent_summarizer import summarize_ictihat_for_agent
from ..util.instruction_loader import load_instruction_text
from ...utils.dev_logging import dev_log, dev_log_exception


set_tracing_disabled(disabled=True)


ICTIHAT_SEARCH_AGENT_INSTRUCTIONS = load_instruction_text("ictihat_search_agent.md").strip()


def _build_daire_names_instruction_block(daire_names: list[str] | None) -> str:
    unique_names = sorted({str(name or "").strip() for name in (daire_names or []) if str(name or "").strip()})
    if not unique_names:
        return ""

    limited = unique_names[:200]
    return (
        "\n\n---\n\n"
        "## Daire Adı Referans Listesi (Best-effort)\n\n"
        "Aşağıdaki daire/kurul adları sistemde mevcut ve cache'den gelmektedir. Bunları sadece yardımcı referans olarak kullan.\n"
        "Kullanıcı açıkça belirtmedikçe veya arama sinyali güçlü olmadıkça sırf bu listede var diye daire uydurma.\n"
        "Gerektiğinde sorgu varyantlarında ve filtre oluştururken bu kanonik adları tercih et:\n\n"
        + "\n".join(f"- {name}" for name in limited)
    )


class IctihatSearchAgent:
    """
    Mini agent that iteratively searches ictihat backends and returns a refined JSON list.
    """

    def __init__(
        self,
        *,
        user_id: int,
        chat_id: int,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        daire_names: Optional[list[str]] = None,
    ) -> None:
        load_env()
        cfg = agent_config()
        self.user_id = int(user_id)
        self.chat_id = int(chat_id)
        self.model = (model or cfg.ictihat_search_agent_model).strip()
        self.top_k = int(cfg.ictihat_search_agent_top_k)
        self.summarize_token_threshold = int(cfg.ictihat_search_agent_summarizer_token_threshold)
        self.summarize_for_agent_enabled = bool(cfg.ictihat_agent_summarize_for_agent_enabled)
        self.intent_text = ""
        self.debug = bool(cfg.ictihat_search_agent_debug)
        self.instructions_text = ICTIHAT_SEARCH_AGENT_INSTRUCTIONS + _build_daire_names_instruction_block(daire_names)
        # Per-run in-memory caches to avoid duplicate DB calls within the mini-agent loop.
        self._doc_cache: dict[int, Dict[str, Any]] = {}
        self._search_cache: dict[str, Dict[str, Any]] = {}

        def _extract_citation_filters(text: str) -> Dict[str, Any]:
            """
            Best-effort extraction of E/K + date from free text.
            If present, we can use ictihat_search() citation-lookup path (no embeddings).
            """
            s = str(text or "")
            # E: 2015/16102 E.  or 2015/16102 E
            m_e = re.search(r"\b(19|20)\d{2}\s*/\s*(\d{1,7})\s*E\b", s, flags=re.IGNORECASE)
            # K: 2016/8916 K.   or 2016/8916 K
            m_k = re.search(r"\b(19|20)\d{2}\s*/\s*(\d{1,7})\s*K\b", s, flags=re.IGNORECASE)
            # Date: 26/05/2016 or 26.05.2016 or 2016-05-26
            m_d1 = re.search(r"\b(\d{2})[./](\d{2})[./]((19|20)\d{2})\b", s)
            m_d2 = re.search(r"\b((19|20)\d{2})-(\d{2})-(\d{2})\b", s)

            filters: Dict[str, Any] = {}
            if m_e:
                try:
                    filters["esas_yil"] = int(m_e.group(0).split("/")[0])
                    # safer parse for sira
                    filters["esas_sira"] = int(re.search(r"/\s*(\d+)", m_e.group(0)).group(1))  # type: ignore[union-attr]
                except Exception:
                    pass
            if m_k:
                try:
                    filters["karar_yil"] = int(m_k.group(0).split("/")[0])
                    filters["karar_sira"] = int(re.search(r"/\s*(\d+)", m_k.group(0)).group(1))  # type: ignore[union-attr]
                except Exception:
                    pass
            if m_d1:
                dd, mm, yyyy = m_d1.group(1), m_d1.group(2), m_d1.group(3)
                filters["karar_tarihi"] = f"{yyyy}-{mm}-{dd}"
            elif m_d2:
                yyyy, mm, dd = m_d2.group(1), m_d2.group(3), m_d2.group(4)
                filters["karar_tarihi"] = f"{yyyy}-{mm}-{dd}"

            # Try to extract daire text (optional, can be inconsistent in DB; keep only if explicit).
            m_da = re.search(r"\b(\d{1,2})\.\s*Ceza\s+Dairesi\b", s, flags=re.IGNORECASE)
            if m_da:
                # We do NOT force the "Yargıtay " prefix; DB may store either.
                filters["kurum"] = "YARGITAY"
                filters["daire"] = f"{int(m_da.group(1))}. Ceza Dairesi"
            if re.search(r"\bCeza\s+Genel\s+Kurulu\b", s, flags=re.IGNORECASE):
                filters["kurum"] = "YARGITAY"
                filters["daire"] = "Ceza Genel Kurulu"

            # Only return if we have at least one strong citation key.
            strong = any(k in filters for k in ("esas_yil", "esas_sira", "karar_yil", "karar_sira", "karar_tarihi"))
            return filters if strong else {}

        resolved_effort = sanitize_reasoning_effort(self.model, reasoning_effort or "medium") or "medium"
        model_settings = build_model_settings(
            self.model,
            reasoning_effort=resolved_effort,
            reasoning_summary="concise",
        )

        @function_tool
        async def ictihat_db_search(
            search_type: str,
            query: str = "",
            filters_json: str | None = None,
        ) -> str:
            """
            Low-level decision search across the configured ictihat backends.

            - query can be empty ONLY if filters_json contains a direct citation (esas/karar).
            - filters_json is a JSON object (optional).
            - `search_type` is required and must be `semantic` or `keyword`.
            """
            top_k = int(self.top_k)
            try:
                filters: Dict[str, Any] | None = json.loads(filters_json) if filters_json else None
            except Exception:
                filters = None

            # If the model didn't provide structured filters, try to auto-extract E/K + date
            # from the query to use the fast citation-lookup path (no embeddings).
            if not isinstance(filters, dict) or not filters:
                auto = _extract_citation_filters(query or "")
                if auto:
                    filters = auto
            chosen_search_type = str(search_type or "").strip().lower()
            if chosen_search_type not in {"semantic", "keyword"}:
                return json.dumps({"ok": False, "reason": "invalid_search_type"}, ensure_ascii=False)

            # Cache key (query+filters). Keep it deterministic and bounded.
            try:
                cache_key = json.dumps(
                    {"q": (query or ""), "f": (filters or {}), "search_type": chosen_search_type},
                    ensure_ascii=False,
                    sort_keys=True,
                )
            except Exception:
                cache_key = f"q={query!r}|search_type={chosen_search_type}"
            if cache_key in self._search_cache:
                return json.dumps(self._search_cache[cache_key], ensure_ascii=False)

            if self.debug:
                dev_log(
                    "ictihat_search_agent",
                    "ictihat_db_search_call",
                    {
                        "user_id": int(self.user_id),
                        "chat_id": int(self.chat_id),
                        "query_preview": (query or "")[:240],
                        "query_len": len(query or ""),
                        "top_k": int(top_k),
                        "search_type": chosen_search_type,
                        "has_filters": bool(filters),
                    },
                )
            try:
                if chosen_search_type == "keyword":
                    res = await _ictihat_keyword_search(
                        user_id=self.user_id,
                        chat_id=self.chat_id,
                        query=(query or ""),
                        top_k=int(top_k),
                        filters=filters,
                        mode="decisions",
                        chunk_k=None,
                        include_full_text=False,
                    )
                else:
                    # If we have citation filters, don't spend embeddings; query can be empty.
                    q2 = (query or "")
                    if isinstance(filters, dict) and any(
                        filters.get(k) is not None for k in ("esas_yil", "esas_sira", "karar_yil", "karar_sira", "karar_tarihi")
                    ):
                        q2 = ""
                    res = await _ictihat_search(
                        user_id=self.user_id,
                        chat_id=self.chat_id,
                        query=q2,
                        top_k=int(top_k),
                        filters=filters,
                        mode="decisions",
                        chunk_k=None,
                        include_full_text=False,
                    )
            except Exception as e:
                if self.debug:
                    dev_log_exception(
                        "ictihat_search_agent",
                        "ictihat_db_search_error",
                        {"user_id": int(self.user_id), "chat_id": int(self.chat_id)},
                        e,
                    )
                raise

            if self.debug:
                dev_log(
                    "ictihat_search_agent",
                    "ictihat_db_search_result",
                    {
                        "user_id": int(self.user_id),
                        "chat_id": int(self.chat_id),
                        "ok": bool(res.get("ok")),
                        "groups": len(res.get("groups") or []) if isinstance(res.get("groups"), list) else None,
                    },
                )
            if isinstance(res, dict):
                self._search_cache[cache_key] = res
            return json.dumps(res, ensure_ascii=False)

        @function_tool
        async def ictihat_get_document(
            document_id: int = 0,
            kurum: str | None = None,
            daire: str | None = None,
            karar_no: int | None = None,
            karar_sira: int | None = None,
            emsal_no: str | int | None = None,
            emsal_sira: str | int | None = None,
            karar_tarihi: str | None = None,
        ) -> str:
            """
            Fetch the FULL stitched decision text for a given document_id.
            Use this only when needed to improve snippet/summary accuracy.
            """
            try:
                did = int(document_id or 0)
            except Exception:
                did = 0

            # Cache: if we already fetched this document_id in this agent loop, reuse it.
            if did > 0 and did in self._doc_cache:
                return json.dumps(self._doc_cache[did], ensure_ascii=False)

            if self.debug:
                dev_log(
                    "ictihat_search_agent",
                    "ictihat_get_document_call",
                    {
                        "user_id": int(self.user_id),
                        "chat_id": int(self.chat_id),
                        "document_id": int(did),
                        "has_filters": bool(kurum or daire or karar_no or karar_sira or emsal_no or emsal_sira or karar_tarihi),
                    },
                )
            try:
                res = await _ictihat_get_document(
                    user_id=self.user_id,
                    chat_id=self.chat_id,
                    document_id=int(did),
                    kurum=kurum,
                    daire=daire,
                    karar_no=karar_no,
                    karar_sira=karar_sira,
                    emsal_no=emsal_no,
                    emsal_sira=emsal_sira,
                    karar_tarihi=karar_tarihi,
                )
            except Exception as e:
                if self.debug:
                    dev_log_exception(
                        "ictihat_search_agent",
                        "ictihat_get_document_error",
                        {"user_id": int(self.user_id), "chat_id": int(self.chat_id), "document_id": int(did)},
                        e,
                    )
                raise

            if self.summarize_for_agent_enabled:
                try:
                    if isinstance(res, dict) and res.get("ok") and isinstance(res.get("text"), str) and res.get("text"):
                        summarized, meta = await summarize_ictihat_for_agent(
                            user_id=int(self.user_id),
                            chat_id=int(self.chat_id),
                            document_text=str(res.get("text") or ""),
                            olay_context=(self.intent_text or None),
                            token_threshold=int(self.summarize_token_threshold),
                        )
                        res = dict(res)
                        res["text"] = summarized
                        if self.debug:
                            try:
                                resolved = did
                                try:
                                    resolved = int(((res.get("doc") or {}).get("document_id")) or resolved)
                                except Exception:
                                    resolved = did
                                dev_log(
                                    "ictihat_search_agent",
                                    "ictihat_get_document_summarized_for_agent",
                                    {
                                        "user_id": int(self.user_id),
                                        "chat_id": int(self.chat_id),
                                        "document_id": int(resolved),
                                        "meta": meta,
                                    },
                                )
                            except Exception:
                                pass
                except Exception:
                    pass

            # Cache successful fetches (by resolved document_id when possible)
            try:
                if isinstance(res, dict) and res.get("ok"):
                    resolved = did
                    try:
                        resolved = int(((res.get("doc") or {}).get("document_id")) or resolved)
                    except Exception:
                        resolved = did
                    if resolved > 0:
                        self._doc_cache[int(resolved)] = res
            except Exception:
                pass

            # Avoid dumping full text into debug logs (can be huge).
            if self.debug:
                try:
                    ok = bool(res.get("ok")) if isinstance(res, dict) else False
                    text_len = len(res.get("text") or "") if ok and isinstance(res, dict) else None
                except Exception:
                    ok, text_len = False, None
                dev_log(
                    "ictihat_search_agent",
                    "ictihat_get_document_result",
                    {"user_id": int(self.user_id), "chat_id": int(self.chat_id), "ok": ok, "text_len": text_len},
                )
            return json.dumps(res, ensure_ascii=False)

        self.agent = Agent(
            name="Ictihat Search Agent",
            instructions=self.instructions_text,
            model=self.model,
            tools=[ictihat_db_search, ictihat_get_document],
            model_settings=model_settings,
        )

