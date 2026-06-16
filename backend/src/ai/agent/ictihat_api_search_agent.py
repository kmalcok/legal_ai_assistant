from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from agents import Agent, function_tool, set_tracing_disabled

from ...config import agent_config, load_env
from ...services.user_app_config_service import build_model_settings, sanitize_reasoning_effort
from ..tool_wrappers.ictihat_get_document import ictihat_get_document as _ictihat_get_document
from ..tool_wrappers.ictihat_search import ictihat_keyword_search as _ictihat_keyword_search
from ..tool_wrappers.ictihat_search import ictihat_search as _ictihat_search
from ..util.ictihat_agent_summarizer import summarize_ictihat_for_agent
from ..util.instruction_loader import load_instruction_text
from ...utils.dev_logging import dev_log, dev_log_exception


set_tracing_disabled(disabled=True)

ICTIHAT_API_SEARCH_AGENT_INSTRUCTIONS = load_instruction_text("ictihat_api_search_agent.md").strip()


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


# Allowed effort tiers — match the chip values exposed by the frontend.
_EFFORT_TIERS = (5, 10, 15, 20)


def _build_effort_instruction_block(effort_top_k: int | None) -> str:
    """
    Per-request override that scales the agent's search effort according to a user-picked
    target result count. Appended AFTER the base instructions so its directives take
    precedence over the default ("Toplam tavan YOK") protocol.

    Returns an empty string when the user hasn't picked a tier — in that case the agent
    falls back to the base instructions (full exhaustive protocol).
    """
    if effort_top_k is None:
        return ""
    try:
        n = int(effort_top_k)
    except Exception:
        return ""
    if n not in _EFFORT_TIERS:
        return ""

    tier_blocks = {
        5: (
            "**N = 5 — Hızlı:** Toplam **2–3 `ictihat_db_search` çağrısı** yeterli. "
            "Yalnızca **5★ ve 4★** kararları topla ve en güçlü 5 tanesini ver. "
            "3★/2★/1★ ekleme. Citation-lookup geliyorsa tek çağrı + 1–2 destek varyantı yeter."
        ),
        10: (
            "**N = 10 — Standart:** Toplam **3–5 `ictihat_db_search` çağrısı**. "
            "Ağırlıklı **5★/4★** + en fazla 1–2 adet **3★**. 2★/1★ ekleme. Toplam ~10 item."
        ),
        15: (
            "**N = 15 — Geniş:** Toplam **5–7 `ictihat_db_search` çağrısı**. "
            "5★/4★/3★ karışımı + birkaç adet **2★**. 1★ ekleme. Toplam ~15 item."
        ),
        20: (
            "**N = 20 — Kapsamlı (standart protokol):** Base instruction'lardaki "
            "tam \"ARAMA PROTOKOLÜ\" geçerli. 5+ tool çağrısı, beş yıldız seviyesinin tamamı. "
            "Toplam ~20 item (havuz daha büyükse de bu istekte üstünü kesip 20'de tut)."
        ),
    }

    body = tier_blocks[n]
    return (
        "\n\n---\n\n"
        "## EFOR AYARI (Kullanıcı isteği — base instruction'ları ÜZERİNE YAZAR)\n\n"
        f"Bu aramada kullanıcı **hedef sonuç sayısı = {n}** istedi. "
        "Bu blok, base instruction'lardaki sayım / iterasyon / \"Toplam tavan YOK\" kuralını "
        "**bu istek için** geçersiz kılar; aşağıdaki kurala göre ölçekle:\n\n"
        f"{body}\n\n"
        "**Genel kurallar (her tier için):**\n"
        f"- `items[]` uzunluğu **{n}'i AŞMASIN**. Daha az olabilir (konu darsa); fazla OLAMAZ.\n"
        "- Yıldız sıralaması her zaman 5★ → 1★ azalan kalır.\n"
        "- Yıldız enflasyonu yine YASAK. Yıldız atamaları base instruction'larla aynı kıstaslara tabi.\n"
        "- Hedefe ulaşmak için kalitesiz/seviye-dışı karar EKLEME — eksik bırak.\n"
        "- Çağrı bütçesini aşma; agentın iç notlarını çıktıya yazma."
    )


def _to_int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed


def _compact_group_payload(group: Dict[str, Any]) -> Dict[str, Any]:
    doc = group.get("doc") if isinstance(group.get("doc"), dict) else {}
    esas = doc.get("esas") if isinstance(doc.get("esas"), dict) else {}
    karar = doc.get("karar") if isinstance(doc.get("karar"), dict) else {}
    snippets: list[str] = []
    for chunk in group.get("matched_chunks") or []:
        if not isinstance(chunk, dict):
            continue
        snippet = str(chunk.get("snippet") or "").strip()
        if snippet:
            snippets.append(snippet[:600])

    return {
        "document_id": _to_int_or_none(doc.get("document_id")),
        "kurum": doc.get("kurum"),
        "daire": doc.get("daire_label") or doc.get("daire"),
        "esas": {
            "yil": _to_int_or_none(esas.get("yil")),
            "sira": _to_int_or_none(esas.get("sira")),
        },
        "karar": {
            "yil": _to_int_or_none(karar.get("yil")),
            "sira": _to_int_or_none(karar.get("sira")),
            "tarih": karar.get("tarih"),
        },
        "matched_snippets": snippets[:2],
    }


def _compact_search_payload(payload: Dict[str, Any], *, search_type: str, query: str, filters: Dict[str, Any] | None) -> Dict[str, Any]:
    groups = payload.get("groups") if isinstance(payload.get("groups"), list) else []
    items = [_compact_group_payload(group) for group in groups if isinstance(group, dict)]
    return {
        "ok": bool(payload.get("ok")),
        "search_type": str(search_type or "").strip().lower(),
        "query": str(query or ""),
        "filters": filters or {},
        "count": len(items),
        "items": items,
        "note": payload.get("note"),
    }


class IctihatApiSearchAgent:
    """
    API/UI oriented mini-agent for iterated ictihat search.
    Segregated from the internal (main-agent) ictihat search sub-agent on purpose.
    """

    def __init__(
        self,
        *,
        user_id: int,
        chat_id: int,
        model: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        daire_names: Optional[list[str]] = None,
        effort_top_k: Optional[int] = None,
    ) -> None:
        load_env()
        cfg = agent_config()
        self.user_id = int(user_id)
        self.chat_id = int(chat_id)
        self.model = (model or cfg.ictihat_api_search_agent_model).strip() or cfg.ictihat_api_search_agent_model
        self.top_k = int(cfg.ictihat_api_search_agent_top_k)
        self.summarize_token_threshold = int(cfg.ictihat_search_agent_summarizer_token_threshold)
        self.summarize_for_agent_enabled = bool(cfg.ictihat_agent_summarize_for_agent_enabled)
        self.intent_text = ""
        self.debug = bool(cfg.ictihat_api_search_agent_debug)
        self.effort_top_k = int(effort_top_k) if effort_top_k in _EFFORT_TIERS else None
        # Instruction injection order matters: base instructions first, then the (optional)
        # effort override block — later blocks intentionally take precedence in the LLM read.
        self.instructions_text = (
            ICTIHAT_API_SEARCH_AGENT_INSTRUCTIONS
            + _build_daire_names_instruction_block(daire_names)
            + _build_effort_instruction_block(self.effort_top_k)
        )

        # Per-run caches (avoid duplicate DB calls within the loop).
        self._doc_cache: dict[int, Dict[str, Any]] = {}
        self._search_cache: dict[str, Dict[str, Any]] = {}

        def _extract_citation_filters(text: str) -> Dict[str, Any]:
            """
            Best-effort extraction of E/K + date from free text.
            If present, we can take the fast citation-lookup path (no embeddings).
            """
            s = str(text or "")
            m_e = re.search(r"\b(19|20)\d{2}\s*/\s*(\d{1,7})\s*E\b", s, flags=re.IGNORECASE)
            m_k = re.search(r"\b(19|20)\d{2}\s*/\s*(\d{1,7})\s*K\b", s, flags=re.IGNORECASE)
            m_d1 = re.search(r"\b(\d{2})[./](\d{2})[./]((19|20)\d{2})\b", s)
            m_d2 = re.search(r"\b((19|20)\d{2})-(\d{2})-(\d{2})\b", s)

            filters: Dict[str, Any] = {}
            if m_e:
                try:
                    filters["esas_yil"] = int(m_e.group(0).split("/")[0])
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

            # Optional daire extraction (keep only if explicit).
            m_da = re.search(r"\b(\d{1,2})\.\s*Ceza\s+Dairesi\b", s, flags=re.IGNORECASE)
            if m_da:
                filters["kurum"] = "YARGITAY"
                filters["daire"] = f"{int(m_da.group(1))}. Ceza Dairesi"
            if re.search(r"\bCeza\s+Genel\s+Kurulu\b", s, flags=re.IGNORECASE):
                filters["kurum"] = "YARGITAY"
                filters["daire"] = "Ceza Genel Kurulu"

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
            Decision-level search across the configured ictihat backends.
            `search_type` is required and must be `semantic` or `keyword`.
            Returns compact decision metadata, including `karar.tarih` when available.
            """
            top_k = int(self.top_k)
            try:
                filters: Dict[str, Any] | None = json.loads(filters_json) if filters_json else None
            except Exception:
                filters = None

            if not isinstance(filters, dict) or not filters:
                auto = _extract_citation_filters(query or "")
                if auto:
                    filters = auto
            chosen_search_type = str(search_type or "").strip().lower()
            if chosen_search_type not in {"semantic", "keyword"}:
                return json.dumps({"ok": False, "reason": "invalid_search_type"}, ensure_ascii=False)

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
                    "ictihat_api_search_agent",
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
                        "ictihat_api_search_agent",
                        "ictihat_db_search_error",
                        {"user_id": int(self.user_id), "chat_id": int(self.chat_id)},
                        e,
                    )
                raise

            compact_res = _compact_search_payload(res, search_type=chosen_search_type, query=(query or ""), filters=filters) if isinstance(res, dict) else res
            if isinstance(compact_res, dict):
                self._search_cache[cache_key] = compact_res
            return json.dumps(compact_res, ensure_ascii=False)

        @function_tool
        async def ictihat_get_document(
            document_id: int = 0,
        ) -> str:
            """
            Fetch FULL stitched decision text for a given document_id.
            Use only when needed for relevance/snippet verification.
            """
            try:
                did = int(document_id or 0)
            except Exception:
                did = 0
            if did > 0 and did in self._doc_cache:
                return json.dumps(self._doc_cache[did], ensure_ascii=False)

            if self.debug:
                dev_log(
                    "ictihat_api_search_agent",
                    "ictihat_get_document_call",
                    {"user_id": int(self.user_id), "chat_id": int(self.chat_id), "document_id": int(did)},
                )
            try:
                res = await _ictihat_get_document(
                    user_id=self.user_id,
                    chat_id=self.chat_id,
                    document_id=int(did),
                )
            except Exception as e:
                if self.debug:
                    dev_log_exception(
                        "ictihat_api_search_agent",
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
                                    "ictihat_api_search_agent",
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

            try:
                if isinstance(res, dict) and res.get("ok") and did > 0:
                    self._doc_cache[int(did)] = res
            except Exception:
                pass
            return json.dumps(res, ensure_ascii=False)

        self.agent = Agent(
            name="Ictihat API Search Agent",
            instructions=self.instructions_text,
            model=self.model,
            tools=[ictihat_db_search, ictihat_get_document],
            model_settings=model_settings,
        )

