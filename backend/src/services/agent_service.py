from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional, Tuple

from agents import Runner
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.stream_events import RawResponsesStreamEvent, RunItemStreamEvent
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseFunctionWebSearch,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseTextDeltaEvent,
)

from ..ai.agent.law_agent import LawAssistantAgent
from ..ai.agent.law_agent_student import LawStudentAssistantAgent
from ..ai.client.openai_clients import build_agents_run_config
from ..ai.graph.runtime import stream_law_graph, summarize_final_messages
from ..ai.memory.redis_memory import RedisMemory
from ..ai.memory.summarizer import Summarizer
from ..config import agent_config, app_config
from ..data.db_account_repository import (
    ACCOUNT_PLAN_FREE,
    ACCOUNT_PLAN_STUDENT,
    AccountRepository,
)
from ..data.db_chat_context_repository import ChatContextRepository
from ..data.db_chat_repository import ChatRepository
from ..documents.repository import DocumentRepository
from ..documents.utils import shorten
from ..petitions.pipeline import PetitionPipelineError, get_field_text, parse_and_normalize_output_json
from ..petitions.repository import PetitionRepository
from ..ai.tool_wrappers.ictihat_get_document import ictihat_get_document as _ictihat_get_document
from ..services.user_app_config_service import UserAppConfigService
from ..usage.extractors import extract_agents_sdk_usage, normalize_model_for_billing
from ..usage.usage_service import UsageService
from ..utils.ictihat_format import daire_label
from ..utils.dev_logging import dev_log, dev_print_yellow, is_dev
from ..ai.util.ictihat_agent_summarizer import summarize_ictihat_for_agent


class AgentService:
    """
    Orchestrates one turn:
    - ensure chat exists / owned by user
    - persist messages (DB)
    - maintain hot memory (Redis)
    - run agent with openai-agents
    - record usage (tokens + web search)
    - summarize/compress when needed

    Student plan: Redis hafiza ozeti `max_history_tokens` yerine 5000 token esiginde tetiklenir.
    """

    _STUDENT_MAX_HISTORY_TOKENS = 5000
    _CITE_TRACE_PREFIX = "cite"
    _INTERNAL_TRACE_RE = re.compile(
        r"cite.*?|turn\d+[A-Za-z]*to=functions\.[A-Za-z0-9_./=-]+",
        re.DOTALL,
    )

    def __init__(
        self,
        *,
        memory: Optional[RedisMemory] = None,
        summarizer: Optional[Summarizer] = None,
        usage: Optional[UsageService] = None,
    ):
        self.cfg = agent_config()
        self.memory = memory or RedisMemory()
        self.summarizer = summarizer or Summarizer()
        self.usage = usage or UsageService()
        self.user_app_config = UserAppConfigService()
        self._log = logging.getLogger("mevzuat.agent")

    @staticmethod
    def _sha256(s: str) -> str:
        return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

    @staticmethod
    def _strip_internal_trace_tokens(text: str | None) -> str:
        raw = text if isinstance(text, str) else str(text or "")
        cleaned = AgentService._INTERNAL_TRACE_RE.sub("", raw)
        cleaned = cleaned.replace("cite", "").replace("", "").replace("", "")
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r" *\n *", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @classmethod
    def _strip_internal_trace_tokens_stream(cls, text: str | None) -> str:
        raw = text if isinstance(text, str) else str(text or "")
        cleaned = cls._INTERNAL_TRACE_RE.sub("", raw)
        return cleaned.replace("cite", "").replace("", "").replace("", "")

    @classmethod
    def _is_possible_function_trace_prefix(cls, text: str) -> bool:
        if not text.startswith("turn"):
            return False

        rest = text[4:]
        if not rest:
            return True

        i = 0
        while i < len(rest) and rest[i].isdigit():
            i += 1
        if i == 0:
            return False

        j = i
        while j < len(rest) and rest[j].isalpha():
            j += 1

        tail = rest[j:]
        if not tail:
            return True

        expected = "to=functions."
        if expected.startswith(tail):
            return True
        if tail.startswith(expected):
            remainder = tail[len(expected) :]
            return not remainder or bool(re.fullmatch(r"[A-Za-z0-9_./=-]+", remainder))
        return False

    @classmethod
    def _split_stream_trace_carry(cls, text: str) -> tuple[str, str]:
        raw = text if isinstance(text, str) else str(text or "")
        if not raw:
            return "", ""

        carry_start: int | None = None

        cite_idx = raw.rfind("")
        if cite_idx >= 0:
            cite_suffix = raw[cite_idx:]
            if cls._CITE_TRACE_PREFIX.startswith(cite_suffix) or (
                cite_suffix.startswith(cls._CITE_TRACE_PREFIX) and "" not in cite_suffix
            ):
                carry_start = cite_idx

        search_from = 0
        while True:
            idx = raw.find("turn", search_from)
            if idx < 0:
                break
            prev_ok = idx == 0 or not (raw[idx - 1].isalnum() or raw[idx - 1] == "_")
            if prev_ok and cls._is_possible_function_trace_prefix(raw[idx:]):
                carry_start = idx if carry_start is None else min(carry_start, idx)
            search_from = idx + 1

        if carry_start is None:
            return raw, ""
        return raw[:carry_start], raw[carry_start:]

    @classmethod
    def _sanitize_stream_chunk(cls, carry: str, chunk: str, *, final: bool = False) -> tuple[str, str]:
        cleaned = cls._strip_internal_trace_tokens_stream(f"{carry}{chunk or ''}")
        visible, next_carry = cls._split_stream_trace_carry(cleaned)
        if final:
            return visible, ""
        return visible, next_carry

    @staticmethod
    def _normalize_feature_query_text(text: str | None, *, max_len: int = 400) -> str:
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        return compact[:max_len]

    @staticmethod
    def _looks_like_specific_ictihat_reference(text: str | None) -> bool:
        raw = str(text or "")
        patterns = [
            r"\b\d{4}\s*/\s*\d+\s*E\.?\s*[,;/\- ]*\s*\d{4}\s*/\s*\d+\s*K\.?\b",
            r"\bE\s*[:.]?\s*\d{4}\s*/\s*\d+",
            r"\bK\s*[:.]?\s*\d{4}\s*/\s*\d+",
        ]
        return any(re.search(pattern, raw, re.IGNORECASE) for pattern in patterns)

    @classmethod
    def _should_recommend_ictihat_feature(
        cls,
        *,
        original_message: str,
        answer: str,
        tool_calls: list[dict],
        ictihat_items: list[dict],
    ) -> bool:
        message = cls._normalize_feature_query_text(original_message, max_len=800)
        if not message:
            return False

        folded = message.casefold()
        if "ai içtihat arama" in folded or "ai ictihat arama" in folded:
            return False
        if cls._looks_like_specific_ictihat_reference(message):
            return False
        if "içtihat arama" in str(answer or "").casefold() or "ictihat arama" in str(answer or "").casefold():
            return False

        case_terms = (
            "içtihat",
            "ictihat",
            "yargıtay",
            "yargitay",
            "emsal",
            "karar",
            "kararlar",
            "danıştay",
            "danistay",
        )
        search_terms = (
            "bul",
            "ara",
            "tara",
            "listele",
            "getir",
            "göster",
            "goster",
            "karşılaştır",
            "karsilastir",
            "incele",
            "derle",
            "topla",
        )
        breadth_terms = (
            "kararlar",
            "içtihatlar",
            "ictihatlar",
            "emsal karar",
            "güncel",
            "guncel",
            "benzer",
            "çok",
            "cok",
            "birkaç",
            "birkac",
            "liste",
            "karşılaştır",
            "karsilastir",
        )

        has_case_term = any(term in folded for term in case_terms)
        has_search_term = any(term in folded for term in search_terms)
        has_breadth_term = any(term in folded for term in breadth_terms)
        used_ictihat_search = any(str(item.get("tool") or "") == "ictihat_search" for item in (tool_calls or []))
        has_multiple_results = len(ictihat_items or []) >= 3

        return bool(
            (has_case_term and has_search_term and has_breadth_term)
            or (used_ictihat_search and has_case_term and has_multiple_results)
        )

    @classmethod
    def _build_ictihat_feature_recommendation(cls, *, original_message: str) -> dict | None:
        query_text = cls._normalize_feature_query_text(original_message)
        return {
            "feature": "ictihat_search",
            "title": "AI İçtihat Arama ile derinleştirin",
            "message": "Bu talep emsal karar taraması ağırlıklı görünüyor. Daha kapsamlı arama, filtreleme ve karşılaştırma için AI İçtihat Arama özelliğini kullanabilirsiniz.",
            "action_label": "AI İçtihat Arama",
            "query_text": query_text or None,
            "search_mode": "ai",
        }

    def _extract_feature_recommendation_from_tool_calls(
        self,
        tool_calls: list[dict],
        *,
        original_message: str,
    ) -> dict | None:
        for call in reversed(tool_calls or []):
            if str(call.get("tool") or "") != "recommend_ictihat_search":
                continue
            args = call.get("args")
            payload = args if isinstance(args, dict) else {}
            recommendation = self._build_ictihat_feature_recommendation(
                original_message=str(payload.get("query_text") or original_message or "")
            ) or {}
            title = str(payload.get("title") or "").strip()
            message = str(payload.get("message") or "").strip()
            action_label = str(payload.get("action_label") or "").strip()
            if title:
                recommendation["title"] = title
            if message:
                recommendation["message"] = message
            if action_label:
                recommendation["action_label"] = action_label
            self._log.info(
                "recommend_ictihat_search used: feature=%s query_text=%r",
                recommendation.get("feature"),
                recommendation.get("query_text"),
            )
            return recommendation if isinstance(recommendation, dict) and recommendation else None
        return None

    @staticmethod
    def _reason_for_exception(exc: Exception) -> str:
        if isinstance(exc, TimeoutError):
            return "openai_timeout"
        return "stream_failed"

    @staticmethod
    def _max_turns() -> int:
        """Max internal agent/tool turns per API call."""
        return int(app_config().law_agent_max_turns)

    async def _resolve_user_account_plan(self, *, user_id: int) -> str:
        try:
            account = await asyncio.to_thread(AccountRepository.get_user_account, int(user_id))
        except Exception:
            self._log.exception("_resolve_user_account_plan failed: user_id=%s", user_id)
            return ACCOUNT_PLAN_FREE
        if not isinstance(account, dict):
            return ACCOUNT_PLAN_FREE
        return str(account.get("account_plan") or ACCOUNT_PLAN_FREE).strip().lower() or ACCOUNT_PLAN_FREE

    @staticmethod
    def _is_student_plan(account_plan: str | None) -> bool:
        return str(account_plan or "").strip().lower() == ACCOUNT_PLAN_STUDENT

    @staticmethod
    def _build_agent_instance(
        *,
        account_plan: str,
        user_id: int,
        chat_id: int,
        model: str,
        reasoning_pref: str | None,
        verbosity: str | None,
        extra_instructions: str | None,
    ) -> Any:
        agent_cls = LawStudentAssistantAgent if AgentService._is_student_plan(account_plan) else LawAssistantAgent
        return agent_cls(
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            reasoning_pref=reasoning_pref,
            verbosity=verbosity,
            extra_instructions=extra_instructions,
        )

    async def ensure_chat(self, *, user_id: int, chat_id: Optional[int]) -> int:
        if chat_id is None:
            return await asyncio.to_thread(ChatRepository.create_chat, int(user_id), None)
        chat = await asyncio.to_thread(ChatRepository.get_chat, int(chat_id), int(user_id))
        if chat is None:
            raise ValueError("Chat not found for this user.")
        return int(chat_id)

    async def _maybe_seed_history_from_summary(self, *, user_id: int, chat_id: int) -> list[str]:
        history = await self.memory.load(chat_id)
        if history:
            return history
        recent = await asyncio.to_thread(ChatRepository.get_recent_messages, int(chat_id), int(user_id), 8)
        rebuilt: list[str] = []
        for row in recent or []:
            if not isinstance(row, dict):
                continue
            role = str(row.get("role") or "").strip().lower()
            message = str(row.get("message") or "").strip()
            if not message:
                continue
            if role == "user":
                rebuilt.append(f"Human Message: {message}")
            elif role == "assistant":
                rebuilt.append(f"Ai Agent Message: {message}")
        if rebuilt:
            await self.memory.seed_from_messages(chat_id, rebuilt)
            return await self.memory.load(chat_id)
        chat = await asyncio.to_thread(ChatRepository.get_chat, int(chat_id), int(user_id))
        if chat and chat.last_sum:
            await self.memory.seed_from_summary(chat_id, chat.last_sum)
            return await self.memory.load(chat_id)
        return []

    async def _maybe_summarize(
        self,
        *,
        user_id: int,
        chat_id: int,
        max_history_tokens: Optional[int] = None,
    ) -> None:
        history = await self.memory.load(chat_id)
        history_tokens = self.summarizer.count_context_tokens(history, model=self.cfg.base_model)
        threshold = (
            int(max_history_tokens)
            if max_history_tokens is not None
            else int(self.cfg.max_history_tokens)
        )
        if history_tokens < threshold:
            return
        tail_count = max(0, int(self.cfg.memory_raw_tail_items))
        tail_messages = history[-tail_count:] if tail_count > 0 else []
        older_history = history[:-tail_count] if tail_count > 0 else list(history)
        if not older_history:
            return
        try:
            summary = await self.summarizer.summarize(
                user_id=user_id,
                chat_id=chat_id,
                context=older_history,
                model=self.cfg.memory_summarizer_model,
            )
        except Exception:
            return
        await asyncio.to_thread(ChatRepository.update_last_sum, int(chat_id), int(user_id), summary)
        if tail_messages:
            await self.memory.seed_from_summary_and_messages(chat_id, summary, tail_messages)
            return
        await self.memory.seed_from_summary(chat_id, summary)

    @staticmethod
    def _format_selected_ictihat_hint(items: list[dict], *, max_items: int = 8) -> str:
        """Build a small, stable hint string for the agent input payload."""
        cleaned: list[dict] = []
        seen: set[int] = set()
        for it in items or []:
            if not isinstance(it, dict):
                continue
            try:
                did = int(it.get("document_id"))
            except Exception:
                continue
            if did in seen:
                continue
            seen.add(did)
            cleaned.append(it)
            if len(cleaned) >= int(max_items):
                break
        if not cleaned:
            return ""
        lines = ["SELECTED İÇTİHATLAR (sohbette daha önce seçilenler; tekrar arama yapma):"]
        for it in cleaned:
            did = it.get("document_id")
            kurum = (it.get("kurum") or "").strip() if isinstance(it.get("kurum"), str) else ""
            daire_label = (it.get("daire_label") or "").strip() if isinstance(it.get("daire_label"), str) else ""
            daire_raw = (it.get("daire") or "").strip() if isinstance(it.get("daire"), str) else ""
            esas_yil = it.get("esas_yil")
            esas_sira = it.get("esas_sira")
            karar_yil = it.get("karar_yil")
            karar_sira = it.get("karar_sira")
            karar_tarihi = (it.get("karar_tarihi") or "").strip() if isinstance(it.get("karar_tarihi"), str) else ""
            cite_parts = []
            if kurum:
                cite_parts.append(kurum)
            if daire_label or daire_raw:
                cite_parts.append(daire_label or daire_raw)
            if esas_yil and esas_sira:
                cite_parts.append(f"{esas_yil}/{esas_sira} E.")
            if karar_yil and karar_sira:
                cite_parts.append(f"{karar_yil}/{karar_sira} K.")
            if karar_tarihi:
                cite_parts.append(f"T:{karar_tarihi}")
            cite = " ".join(cite_parts).strip()
            lines.append(f"- document_id={did} :: {cite}" if cite else f"- document_id={did}")
        lines.append("KURAL: Kullanıcı 'bu içtihatları dilekçeye ekle' derse, önce bu listeden kullan; yeni arama yapma.")
        return "\n".join(lines).strip()

    @staticmethod
    def _normalize_selected_ictihats_ui(items: Any, *, max_items: int = 8) -> list[dict]:
        """Normalize UI-provided selected_ictihats into a safe, bounded list."""
        if not isinstance(items, list):
            return []
        cleaned: list[dict] = []
        by_id: dict[int, dict] = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                did = int(it.get("document_id"))
            except Exception:
                continue
            if did <= 0:
                continue
            cand = {
                "document_id": did,
                "emsal_no": (str(it.get("emsal_no")).strip() if it.get("emsal_no") is not None else None),
                "karar_no": (str(it.get("karar_no")).strip() if it.get("karar_no") is not None else None),
                "daire": (str(it.get("daire")).strip() if it.get("daire") is not None else None),
                "kurum": (str(it.get("kurum")).strip() if it.get("kurum") is not None else None),
            }
            if did in by_id:
                ex = by_id[did]
                for k in ("emsal_no", "karar_no", "daire", "kurum"):
                    if not ex.get(k) and cand.get(k):
                        ex[k] = cand.get(k)
                continue
            by_id[did] = cand
            cleaned.append(cand)
            if len(cleaned) >= int(max_items):
                break
        return cleaned

    @staticmethod
    def _normalize_selected_petition_contexts(items: Any, *, max_items: int = 12) -> list[dict]:
        if not isinstance(items, list):
            return []
        cleaned: list[dict] = []
        seen: set[tuple[int, int | None, str, str]] = set()
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                petition_id = int(it.get("petition_id"))
            except Exception:
                continue
            version_raw = it.get("version_id")
            try:
                version_id = int(version_raw) if version_raw is not None else None
            except Exception:
                version_id = None
            field_path = str(it.get("field_path") or "").strip()
            if petition_id <= 0 or not field_path:
                continue
            selected_text = str(it.get("selected_text") or "").strip()
            section_title = str(it.get("section_title") or "").strip()
            key = (petition_id, version_id, field_path, selected_text)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(
                {
                    "petition_id": petition_id,
                    "version_id": version_id,
                    "field_path": field_path,
                    "selected_text": selected_text or None,
                    "section_title": section_title or None,
                }
            )
            if len(cleaned) >= int(max_items):
                break
        return cleaned

    @staticmethod
    def _build_injected_ictihat_context_items(items: Any) -> list[dict]:
        normalized = AgentService._normalize_selected_ictihats_ui(items, max_items=8)
        out: list[dict] = []
        for item in normalized:
            kurum = str(item.get("kurum") or "").strip() or None
            daire = str(item.get("daire") or "").strip() or None
            out.append(
                {
                    "kind": "injected_ictihat",
                    "source": "ui",
                    "payload": {
                        "document_id": int(item["document_id"]),
                        "emsal_no": item.get("emsal_no"),
                        "karar_no": item.get("karar_no"),
                        "kurum": kurum,
                        "daire": daire,
                        "daire_label": daire_label(kurum=kurum, daire=daire) or daire,
                    },
                }
            )
        return out

    async def _resolve_selected_petition_context_payload(
        self,
        *,
        user_id: int,
        chat_id: int,
        item: dict,
    ) -> dict | None:
        try:
            row = await asyncio.to_thread(
                PetitionRepository.get_version_document,
                user_id=int(user_id),
                chat_id=int(chat_id),
                petition_id=int(item["petition_id"]),
                version_id=int(item["version_id"]) if item.get("version_id") is not None else None,
            )
            output_obj, _ = parse_and_normalize_output_json(str(row.get("output_json") or ""))
            full_text = get_field_text(output_obj, str(item["field_path"]))
        except (ValueError, PetitionPipelineError):
            return None
        except Exception:
            return None

        selected_text = str(item.get("selected_text") or "").strip()
        resolved_text = full_text
        if selected_text:
            folded_full = full_text.casefold()
            folded_sel = selected_text.casefold()
            if folded_sel and folded_sel in folded_full:
                resolved_text = selected_text

        return {
            "petition_id": int(row["petition_id"]),
            "version_id": int(row["version_id"]),
            "version_no": int(row["version_no"]),
            "field_path": str(item["field_path"]),
            "selected_text": selected_text or None,
            "resolved_text": str(resolved_text or "").strip() or None,
            "section_title": str(item.get("section_title") or "").strip() or None,
            "docx_filename": str(row.get("docx_filename") or "").strip() or None,
            "document_type": str(row.get("document_type") or "").strip() or None,
            "court": str(row.get("court") or "").strip() or None,
        }

    async def _build_injected_petition_context_items(
        self,
        *,
        user_id: int,
        chat_id: int,
        items: Any,
    ) -> list[dict]:
        normalized = self._normalize_selected_petition_contexts(items, max_items=12)
        out: list[dict] = []
        for item in normalized:
            payload = await self._resolve_selected_petition_context_payload(
                user_id=int(user_id),
                chat_id=int(chat_id),
                item=item,
            )
            if not isinstance(payload, dict):
                continue
            out.append({"kind": "injected_petition_context", "source": "ui", "payload": payload})
        return out

    async def _persist_user_message_context_items(
        self,
        *,
        user_id: int,
        chat_id: int,
        message_id: int,
        injected_ictihats: Any = None,
        injected_petition_contexts: Any = None,
    ) -> None:
        items: list[dict] = []
        items.extend(self._build_injected_ictihat_context_items(injected_ictihats))
        items.extend(
            await self._build_injected_petition_context_items(
                user_id=int(user_id),
                chat_id=int(chat_id),
                items=injected_petition_contexts,
            )
        )
        if not items:
            return
        await asyncio.to_thread(
            ChatContextRepository.insert_items,
            chat_id=int(chat_id),
            message_id=int(message_id),
            user_id=int(user_id),
            items=items,
        )

    async def _persist_assistant_message_context_items(
        self,
        *,
        user_id: int,
        chat_id: int,
        message_id: int,
        feature_recommendation: dict | None = None,
    ) -> None:
        if not isinstance(feature_recommendation, dict) or not feature_recommendation:
            return
        await asyncio.to_thread(
            ChatContextRepository.insert_items,
            chat_id=int(chat_id),
            message_id=int(message_id),
            user_id=int(user_id),
            items=[
                {
                    "kind": "feature_recommendation",
                    "source": "agent",
                    "payload": feature_recommendation,
                }
            ],
        )

    async def _chat_already_has_feature_recommendation(self, *, user_id: int, chat_id: int) -> bool:
        try:
            return await asyncio.to_thread(
                ChatContextRepository.chat_has_kind,
                user_id=int(user_id),
                chat_id=int(chat_id),
                kind="feature_recommendation",
            )
        except Exception:
            return False

    async def _build_selected_petition_contexts_block(
        self,
        *,
        user_id: int,
        chat_id: int,
        items: list[dict],
    ) -> str:
        normalized = self._normalize_selected_petition_contexts(items, max_items=12)
        if not normalized:
            return ""

        lines: list[str] = []
        lines.append("THESE ARE THE SELECTED PETITION PASSAGES OF USER FOR THIS CHAT (pinned from UI for this message):")
        lines.append("RULE: Treat them as the user's active draft text. Prefer these passages when revising, explaining, or drafting updates.")

        for idx, item in enumerate(normalized, start=1):
            try:
                row = await asyncio.to_thread(
                    PetitionRepository.get_version_document,
                    user_id=int(user_id),
                    chat_id=int(chat_id),
                    petition_id=int(item["petition_id"]),
                    version_id=int(item["version_id"]) if item.get("version_id") is not None else None,
                )
                output_obj, _ = parse_and_normalize_output_json(str(row.get("output_json") or ""))
                full_text = get_field_text(output_obj, str(item["field_path"]))
            except (ValueError, PetitionPipelineError):
                lines.append(
                    f"\n[{idx}] petition_id={item['petition_id']} field_path={item['field_path']} :: fetch_failed_or_not_found"
                )
                continue
            except Exception:
                lines.append(
                    f"\n[{idx}] petition_id={item['petition_id']} field_path={item['field_path']} :: fetch_failed_or_not_found"
                )
                continue

            selected_text = str(item.get("selected_text") or "").strip()
            injected_text = full_text
            if selected_text:
                folded_full = full_text.casefold()
                folded_sel = selected_text.casefold()
                if folded_sel and folded_sel in folded_full:
                    injected_text = selected_text

            section_title = str(item.get("section_title") or "").strip()
            meta_bits = [
                f"petition_id={int(row['petition_id'])}",
                f"version_id={int(row['version_id'])}",
                f"version_no={int(row['version_no'])}",
                f"field_path={item['field_path']}",
            ]
            if section_title:
                meta_bits.append(f"section={section_title}")
            filename = str(row.get("docx_filename") or "").strip()
            if filename:
                meta_bits.append(f"file={filename}")
            lines.append(f"\n[{idx}] " + " :: ".join(["selected_petition_context", ", ".join(meta_bits)]))
            lines.append(injected_text.strip())

        return "\n".join(lines).strip()

    async def _build_selected_ictihats_ui_block(
        self,
        *,
        user_id: int,
        chat_id: int,
        original_message: str,
        items: list[dict],
    ) -> str:
        """
        Build a pinned-ictihat block to be appended under the user message for THIS turn only.
        Fetches texts from DB so the agent does not need to call ictihat_search again.
        """
        ui_items = self._normalize_selected_ictihats_ui(items, max_items=8)
        if not ui_items:
            return ""

        lines: list[str] = []
        lines.append("THESE ARE THE SELECTED ICTIHATS OF USER FOR THIS CHAT (pinned from UI for this message):")
        lines.append("RULE: Use these texts for the user's request. Do NOT call ictihat_search unless user asks for more precedents.")

        for idx, it in enumerate(ui_items, start=1):
            did = int(it["document_id"])
            fetched = None
            try:
                fetched = await _ictihat_get_document(
                    user_id=int(user_id),
                    chat_id=int(chat_id),
                    document_id=int(did),
                )
            except Exception:
                fetched = None

            if not (isinstance(fetched, dict) and fetched.get("ok") and isinstance(fetched.get("text"), str) and fetched.get("text")):
                lines.append(f"\n[{idx}] document_id={did} :: fetch_failed_or_not_found")
                continue

            doc = fetched.get("doc") if isinstance(fetched.get("doc"), dict) else {}
            text = str(fetched.get("text") or "")

            try:
                text, _meta = await summarize_ictihat_for_agent(
                    user_id=int(user_id),
                    chat_id=int(chat_id),
                    document_text=text,
                    olay_context=str(original_message or "").strip() or None,
                    token_threshold=int(self.cfg.ictihat_summarizer_token_threshold),
                )
            except Exception:
                pass

            try:
                if isinstance(text, str) and len(text) > 140_000:
                    text = text[:140_000] + "\n\n[TRUNCATED_FOR_CONTEXT_LIMIT]"
            except Exception:
                pass

            kurum = (doc.get("kurum") or it.get("kurum") or "").strip() if isinstance((doc.get("kurum") or it.get("kurum")), str) else ""
            daire_label = (doc.get("daire_label") or it.get("daire") or doc.get("daire") or "").strip() if isinstance((doc.get("daire_label") or it.get("daire") or doc.get("daire")), str) else ""
            esas = doc.get("esas") if isinstance(doc.get("esas"), dict) else {}
            karar = doc.get("karar") if isinstance(doc.get("karar"), dict) else {}
            cite_parts: list[str] = []
            if kurum:
                cite_parts.append(str(kurum))
            if daire_label:
                cite_parts.append(str(daire_label))
            if esas.get("yil") and esas.get("sira"):
                cite_parts.append(f"{esas['yil']}/{esas['sira']} E.")
            if karar.get("yil") and karar.get("sira"):
                cite_parts.append(f"{karar['yil']}/{karar['sira']} K.")
            if karar.get("tarih"):
                cite_parts.append(f"T:{karar['tarih']}")
            if it.get("emsal_no"):
                cite_parts.append(f"Emsal:{it.get('emsal_no')}")
            if it.get("karar_no"):
                cite_parts.append(f"KararNo:{it.get('karar_no')}")

            cite = " ".join([p for p in cite_parts if str(p).strip()]).strip()
            lines.append(f"\n[{idx}] document_id={did} :: {cite}" if cite else f"\n[{idx}] document_id={did}")
            lines.append(text.strip())

        return "\n".join(lines).strip()

    # ------------------------------------------------------------------ #
    # Shared helpers for building input payload and processing run output  #
    # ------------------------------------------------------------------ #

    async def _build_input_payload(
        self,
        *,
        user_id: int,
        chat_id: int,
        history: list[str],
        message: str,
        include_petitions: bool = True,
        include_selected_ictihat: bool = True,
    ) -> dict[str, Any]:
        """Build the shared input payload dict (docs, petitions, ictihat hints)."""
        try:
            docs = await asyncio.to_thread(
                DocumentRepository.list_chat_documents, chat_id=int(chat_id), user_id=int(user_id)
            )
        except Exception:
            docs = []

        doc_lines: list[str] = []
        if isinstance(docs, list) and docs:
            doc_lines.append("ATTACHED DOCUMENTS (for this chat):")
            for d in docs[:5]:
                if not isinstance(d, dict):
                    continue
                summ = shorten((d.get("short_summary") or "").strip(), 350)
                line = (
                    f"- id={d.get('document_id')} file={str(d.get('filename') or '').strip()!r}"
                    f" status={str(d.get('status') or '').strip()} pages={d.get('page_count')}"
                )
                if summ:
                    line += f" summary={summ!r}"
                doc_lines.append(line)

        pets = []
        if include_petitions:
            try:
                pets = await asyncio.to_thread(
                    PetitionRepository.list_for_chat, user_id=int(user_id), chat_id=int(chat_id), limit=5
                )
            except Exception:
                pets = []

        pet_lines: list[str] = []
        if isinstance(pets, list) and pets:
            pet_lines.append("DİLEKÇELER (bu sohbet için):")
            for p in pets[:5]:
                if not isinstance(p, dict):
                    continue
                summ = shorten((p.get("latest_summary_text") or "").strip(), 220)
                line = (
                    f"- status={str(p.get('status') or '').strip()}"
                    f" type={str(p.get('document_type') or '').strip()!r}"
                    f" file={str(p.get('latest_filename') or '').strip()!r}"
                )
                if summ:
                    line += f" summary={summ!r}"
                pet_lines.append(line)

        ictihat_hint = ""
        if include_selected_ictihat:
            try:
                recent = await asyncio.to_thread(
                    ChatRepository.get_recent_messages, int(chat_id), int(user_id), 30
                )
                msg_ids = [
                    int(r.get("id")) for r in (recent or []) if isinstance(r, dict) and r.get("id") is not None
                ]
                ictihat_map = await asyncio.to_thread(
                    ChatRepository.get_messages_ictihat_map, message_ids=msg_ids
                )
                flat: list[dict] = [
                    it
                    for mid in msg_ids[-30:]
                    for it in (ictihat_map.get(int(mid)) or [])
                    if isinstance(it, dict)
                ]
                ictihat_hint = self._format_selected_ictihat_hint(flat, max_items=8)
            except Exception:
                ictihat_hint = ""

        return {
            "Chat History": history,
            "User Message": message,
            "Current DateTime (UTC)": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "Attached Documents": "\n".join(doc_lines).strip() if doc_lines else "",
            "Petitions": "\n".join(pet_lines).strip() if pet_lines else "",
            "Selected Ictihat": ictihat_hint,
        }

    def _extract_tool_call_data(
        self, new_items: list[Any]
    ) -> tuple[list[dict], list[dict], int]:
        """
        Process new_items from a completed RunResultStreaming.
        Uses SDK types (ToolCallItem / ToolCallOutputItem) instead of raw event parsing.

        Returns:
            tool_calls: [{tool, args}] for function calls
            tool_outputs: [{tool, output}] for function call outputs
            web_search_count: number of web_search_call items
        """
        name_by_call_id: dict[str, str] = {}
        tool_calls: list[dict] = []
        tool_outputs: list[dict] = []
        web_search_count = 0

        for item in new_items:
            if isinstance(item, ToolCallItem):
                raw = item.raw_item
                if isinstance(raw, ResponseFunctionWebSearch):
                    web_search_count += 1
                elif isinstance(raw, ResponseFunctionToolCall):
                    name_by_call_id[raw.call_id] = raw.name
                    try:
                        args: Any = json.loads(raw.arguments or "{}")
                    except Exception:
                        args = raw.arguments
                    tool_calls.append({"tool": raw.name, "args": args})

            elif isinstance(item, ToolCallOutputItem):
                raw = item.raw_item
                call_id = raw.get("call_id") if isinstance(raw, dict) else getattr(raw, "call_id", None)
                name = name_by_call_id.get(call_id) if call_id else None
                out_s = raw.get("output") if isinstance(raw, dict) else getattr(raw, "output", None)
                if name and isinstance(out_s, str) and out_s.strip():
                    tool_outputs.append({"tool": name, "output": out_s})

        return tool_calls, tool_outputs, web_search_count

    def _extract_ictihat_items(
        self, tool_calls: list[dict], tool_outputs: list[dict]
    ) -> list[dict]:
        """
        Extract and de-dup ictihat document items from:
        - ictihat_present tool call args (explicit selection by agent)
        - ictihat_search tool outputs (auto-cache for chat-level reuse)
        """
        items: list[dict] = []

        for c in tool_calls:
            if c.get("tool") != "ictihat_present":
                continue
            args = c.get("args")
            if not isinstance(args, dict):
                continue
            raw = args.get("ictihat_list_json") or args.get("document_ids_json")
            if not isinstance(raw, str) or not raw.strip():
                continue
            try:
                arr = json.loads(raw)
            except Exception:
                continue
            for it in (arr if isinstance(arr, list) else []):
                if isinstance(it, dict):
                    items.append(it)
                else:
                    try:
                        items.append({"document_id": int(it)})
                    except Exception:
                        pass

        for o in tool_outputs:
            if o.get("tool") != "ictihat_search":
                continue
            try:
                out_obj = json.loads(o.get("output") or "")
            except Exception:
                continue
            if not (isinstance(out_obj, dict) and out_obj.get("ok")):
                continue
            arr: list[Any] = out_obj.get("items") if isinstance(out_obj.get("items"), list) else []
            if not arr and isinstance(out_obj.get("groups"), list):
                arr = [
                    g["doc"]
                    for g in out_obj["groups"]
                    if isinstance(g, dict) and isinstance(g.get("doc"), dict)
                ]
            for it in arr:
                if not isinstance(it, dict):
                    continue
                try:
                    did = int(it.get("document_id"))
                except Exception:
                    continue
                esas = it.get("esas") if isinstance(it.get("esas"), dict) else {}
                karar = it.get("karar") if isinstance(it.get("karar"), dict) else {}
                items.append({
                    "document_id": did,
                    "kurum": it.get("kurum"),
                    "daire": it.get("daire"),
                    "daire_label": it.get("daire_label"),
                    "esas_yil": esas.get("yil"),
                    "esas_sira": esas.get("sira"),
                    "karar_yil": karar.get("yil"),
                    "karar_sira": karar.get("sira"),
                    "karar_tarihi": karar.get("tarih"),
                })

        seen: set[int] = set()
        result: list[dict] = []
        for it in items:
            try:
                did = int(it.get("document_id"))
            except Exception:
                continue
            if did not in seen:
                seen.add(did)
                result.append(it)
        return result

    @staticmethod
    def _is_graph_agent(agent: Any) -> bool:
        """LangGraph main agent exposes a compiled ``.graph``; SDK agents expose ``.agent``."""
        return hasattr(agent, "graph")

    @staticmethod
    def _agent_model_name(agent: Any) -> Optional[str]:
        if AgentService._is_graph_agent(agent):
            return getattr(agent, "model", None)
        return getattr(getattr(agent, "agent", None), "model", None)

    async def _record_run_usage(
        self,
        *,
        user_id: int,
        chat_id: int,
        assistant_message_id: int,
        usage_tuple: tuple[Optional[int], Optional[int], Optional[int]],
        model_name: Optional[str],
        web_search_count: int = 0,
    ) -> None:
        """
        Record token usage (input/output/reasoning) + web search usage.
        ``usage_tuple`` is provider-agnostic so both the LangGraph and the SDK
        (student) paths can feed it. Best-effort: never raises.
        """
        try:
            in_tok, out_tok, rsn_tok = usage_tuple

            resolved_model = model_name or self.cfg.base_model
            billing_model = normalize_model_for_billing(str(resolved_model)) or str(resolved_model)

            for usage_type, amount in [
                ("input_tokens", in_tok),
                ("output_tokens", out_tok),
                ("reasoning_tokens", rsn_tok),
            ]:
                if isinstance(amount, int) and amount > 0:
                    await self.usage.record_token_usage(
                        user_id=user_id,
                        chat_id=chat_id,
                        chat_message_id=assistant_message_id,
                        usage_type=usage_type,
                        amount=amount,
                        model=billing_model,
                    )

            if web_search_count > 0:
                # Must match `model_prices.model_name` (trigger bills on insert).
                await self.usage.record_token_usage(
                    user_id=user_id,
                    chat_id=chat_id,
                    chat_message_id=assistant_message_id,
                    usage_type="output_tokens",
                    amount=web_search_count,
                    model="openai_web_search",
                )
        except Exception:
            self._log.exception(
                "_record_run_usage failed: user_id=%s chat_id=%s", user_id, chat_id
            )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def run_turn(
        self,
        *,
        user_id: int,
        message: str,
        chat_id: Optional[int] = None,
        reasoning_pref: Optional[str] = None,
        extra_instructions: Optional[str] = None,
        injected_ictihats: Optional[list[dict]] = None,
        injected_petition_contexts: Optional[list[dict]] = None,
    ) -> Tuple[int, str, dict | None]:
        user_id = int(user_id)
        chat_id_final = await self.ensure_chat(user_id=user_id, chat_id=chat_id)
        account_plan = await self._resolve_user_account_plan(user_id=user_id)
        is_student_plan = self._is_student_plan(account_plan)

        user_message_id = await asyncio.to_thread(
            ChatRepository.append_message, chat_id_final, user_id, "user", message, ""
        )
        try:
            await self._persist_user_message_context_items(
                user_id=int(user_id),
                chat_id=int(chat_id_final),
                message_id=int(user_message_id),
                injected_ictihats=injected_ictihats,
                injected_petition_contexts=injected_petition_contexts,
            )
        except Exception:
            pass

        history = await self._maybe_seed_history_from_summary(user_id=user_id, chat_id=chat_id_final)
        await self.memory.append_user(chat_id_final, message)

        resolved_cfg = await asyncio.to_thread(
            self.user_app_config.resolve_main_agent_config,
            user_id=int(user_id),
            request_reasoning_effort=reasoning_pref,
            request_extra_instructions=extra_instructions,
        )

        agent = self._build_agent_instance(
            account_plan=account_plan,
            user_id=user_id,
            chat_id=chat_id_final,
            model=resolved_cfg.model,
            reasoning_pref=resolved_cfg.reasoning_effort,
            verbosity=resolved_cfg.verbosity,
            extra_instructions=resolved_cfg.extra_instructions,
        )

        agent_message = message
        try:
            if not is_student_plan and injected_ictihats is not None:
                ictihat_block = await self._build_selected_ictihats_ui_block(
                    user_id=int(user_id),
                    chat_id=int(chat_id_final),
                    original_message=str(message or ""),
                    items=injected_ictihats,
                )
                if ictihat_block:
                    agent_message = (str(agent_message or "").rstrip() + "\n\n" + ictihat_block).strip()
            if not is_student_plan and injected_petition_contexts is not None:
                petition_block = await self._build_selected_petition_contexts_block(
                    user_id=int(user_id),
                    chat_id=int(chat_id_final),
                    items=injected_petition_contexts,
                )
                if petition_block:
                    agent_message = (str(agent_message or "").rstrip() + "\n\n" + petition_block).strip()
        except Exception:
            agent_message = message

        payload = await self._build_input_payload(
            user_id=user_id,
            chat_id=chat_id_final,
            history=history,
            message=agent_message,
            include_petitions=not is_student_plan,
            include_selected_ictihat=not is_student_plan,
        )

        # Intentionally no hard wall-clock timeout here:
        # main user-facing chat runs can legitimately take several minutes.
        payload_json = json.dumps(payload, ensure_ascii=False)
        if self._is_graph_agent(agent):
            # LangGraph multi-agent path (main + petition agents, shared state).
            final_state = await agent.graph.ainvoke(
                agent.initial_state(payload_json=payload_json),
                config={"recursion_limit": self._max_turns() * 2 + 2},
            )
            summary = summarize_final_messages(final_state.get("messages") or [])
            answer = self._strip_internal_trace_tokens(summary["final_text"])
            reasoning_text = summary["reasoning_text"]
            tool_calls = summary["tool_calls"]
            tool_outputs = summary["tool_outputs"]
            web_search_count = summary["web_search_count"]
            usage_tuple = summary["usage"]
        else:
            # openai-agents SDK path (student plan).
            run_config = await build_agents_run_config()
            streamed = Runner.run_streamed(
                agent.agent,
                input=payload_json,
                max_turns=self._max_turns(),
                run_config=run_config,
            )

            reasoning_buf: list[str] = []
            async for event in streamed.stream_events():
                if (
                    isinstance(event, RawResponsesStreamEvent)
                    and isinstance(event.data, ResponseReasoningSummaryTextDeltaEvent)
                ):
                    chunk = event.data.delta or ""
                    if chunk:
                        reasoning_buf.append(chunk)

            answer = self._strip_internal_trace_tokens(streamed.final_output or "")
            reasoning_text = "".join(reasoning_buf).strip()
            tool_calls, tool_outputs, web_search_count = self._extract_tool_call_data(streamed.new_items)
            usage_tuple = extract_agents_sdk_usage(streamed.context_wrapper.usage)

        if not reasoning_text and tool_calls:
            lines = ["Tool trace (safe):"]
            for c in tool_calls:
                args = c.get("args")
                arg_s = (
                    ", ".join(f"{k}={v!r}" for k, v in args.items())
                    if isinstance(args, dict)
                    else repr(args)
                )
                lines.append(f"- {c['tool']}({arg_s})")
            reasoning_text = "\n".join(lines)

        ictihat_items = self._extract_ictihat_items(tool_calls, tool_outputs)

        chat_has_feature_recommendation = await self._chat_already_has_feature_recommendation(
            user_id=int(user_id),
            chat_id=int(chat_id_final),
        )
        feature_recommendation = None
        if not chat_has_feature_recommendation:
            feature_recommendation = self._extract_feature_recommendation_from_tool_calls(
                tool_calls,
                original_message=message,
            )
            if feature_recommendation is None and self._should_recommend_ictihat_feature(
                original_message=message,
                answer=answer,
                tool_calls=tool_calls,
                ictihat_items=ictihat_items,
            ):
                feature_recommendation = self._build_ictihat_feature_recommendation(original_message=message)

        assistant_message_id = await asyncio.to_thread(
            ChatRepository.append_message,
            chat_id_final, user_id, "assistant", answer, reasoning_text,
        )
        await self.memory.append_assistant(chat_id_final, answer)

        try:
            if ictihat_items:
                await asyncio.to_thread(
                    ChatRepository.set_message_ictihat,
                    message_id=int(assistant_message_id),
                    ictihat_items=ictihat_items,
                )
        except Exception:
            pass

        try:
            await self._persist_assistant_message_context_items(
                user_id=int(user_id),
                chat_id=int(chat_id_final),
                message_id=int(assistant_message_id),
                feature_recommendation=feature_recommendation,
            )
        except Exception:
            pass

        await self._record_run_usage(
            user_id=user_id,
            chat_id=chat_id_final,
            assistant_message_id=int(assistant_message_id),
            usage_tuple=usage_tuple,
            model_name=self._agent_model_name(agent),
            web_search_count=web_search_count,
        )

        await self._maybe_summarize(
            user_id=user_id,
            chat_id=chat_id_final,
            max_history_tokens=self._STUDENT_MAX_HISTORY_TOKENS if is_student_plan else None,
        )

        return chat_id_final, answer, feature_recommendation

    async def stream_turn(
        self,
        *,
        user_id: int,
        message: str,
        chat_id: Optional[int] = None,
        reasoning_pref: Optional[str] = None,
        extra_instructions: Optional[str] = None,
        injected_ictihats: Optional[list[dict]] = None,
        injected_petition_contexts: Optional[list[dict]] = None,
    ) -> AsyncIterator[bytes]:
        """
        Stream one turn as NDJSON while guaranteeing persistence.

        Uses a background task so the assistant message + usage are saved
        even if the client disconnects.
        """
        user_id = int(user_id)
        chat_id_final = await self.ensure_chat(user_id=user_id, chat_id=chat_id)
        account_plan = await self._resolve_user_account_plan(user_id=user_id)
        is_student_plan = self._is_student_plan(account_plan)

        user_message_id = await asyncio.to_thread(
            ChatRepository.append_message, chat_id_final, user_id, "user", message, ""
        )
        try:
            await self._persist_user_message_context_items(
                user_id=int(user_id),
                chat_id=int(chat_id_final),
                message_id=int(user_message_id),
                injected_ictihats=injected_ictihats,
                injected_petition_contexts=injected_petition_contexts,
            )
        except Exception:
            pass

        history = await self._maybe_seed_history_from_summary(user_id=user_id, chat_id=chat_id_final)
        await self.memory.append_user(chat_id_final, message)

        resolved_cfg = await asyncio.to_thread(
            self.user_app_config.resolve_main_agent_config,
            user_id=int(user_id),
            request_reasoning_effort=reasoning_pref,
            request_extra_instructions=extra_instructions,
        )

        agent = self._build_agent_instance(
            account_plan=account_plan,
            user_id=user_id,
            chat_id=chat_id_final,
            model=resolved_cfg.model,
            reasoning_pref=resolved_cfg.reasoning_effort,
            verbosity=resolved_cfg.verbosity,
            extra_instructions=resolved_cfg.extra_instructions,
        )

        # Build agent_message: optionally inject UI-selected ictihat block under user message.
        agent_message = message
        ui_injected = False
        ui_block_len = 0
        try:
            if not is_student_plan and injected_ictihats is not None:
                block = await self._build_selected_ictihats_ui_block(
                    user_id=int(user_id),
                    chat_id=int(chat_id_final),
                    original_message=str(message or ""),
                    items=injected_ictihats,
                )
                if block:
                    ui_block_len = len(block)
                    ui_injected = True
                    agent_message = (str(message or "").rstrip() + "\n\n" + block).strip()
            if not is_student_plan and injected_petition_contexts is not None:
                petition_block = await self._build_selected_petition_contexts_block(
                    user_id=int(user_id),
                    chat_id=int(chat_id_final),
                    items=injected_petition_contexts,
                )
                if petition_block:
                    ui_block_len += len(petition_block)
                    ui_injected = True
                    agent_message = (str(agent_message or "").rstrip() + "\n\n" + petition_block).strip()
        except Exception:
            agent_message = message

        if is_dev():
            try:
                def _clip(s: Any, n: int) -> str:
                    txt = s if isinstance(s, str) else str(s or "")
                    txt = txt.strip()
                    return txt if len(txt) <= n else txt[:n] + f"\n…[TRUNCATED {len(txt) - n} chars]"

                raw_sel_count = len(injected_ictihats) if isinstance(injected_ictihats, list) else 0
                norm_sel = (
                    self._normalize_selected_ictihats_ui(injected_ictihats, max_items=8)
                    if injected_ictihats is not None
                    else []
                )
                norm_doc_ids = [int(x.get("document_id")) for x in norm_sel if isinstance(x, dict) and x.get("document_id") is not None]

                dev_print_yellow(
                    "========== CHAT/STREAM DEV INPUT ==========",
                    f"user_id={user_id} chat_id={chat_id_final} reasoning_pref={resolved_cfg.reasoning_effort} model={resolved_cfg.model} verbosity={resolved_cfg.verbosity}",
                    f"injected_ictihats: raw_count={raw_sel_count} normalized_count={len(norm_sel)} document_ids={norm_doc_ids}",
                    "---- user_message (stored to DB, original) ----",
                    _clip(message, 100),
                    "---- injected_ictihats (normalized, UI) ----",
                    json.dumps(norm_sel, ensure_ascii=False, indent=2, default=str),
                    "---- agent_user_message (sent to agent; may include injected block) ----",
                    f"len={len(str(agent_message or ''))} sha256={self._sha256(str(agent_message or ''))} injected={ui_injected} injected_block_chars={ui_block_len}",
                    _clip(agent_message, 100),
                    "==========================================",
                )
                dev_log(
                    "chat",
                    "chat_stream_input_debug",
                    {
                        "user_id": user_id,
                        "chat_id": chat_id_final,
                        "reasoning_pref": resolved_cfg.reasoning_effort,
                        "resolved_model": resolved_cfg.model,
                        "resolved_verbosity": resolved_cfg.verbosity,
                        "injected_ictihats_raw_count": raw_sel_count,
                        "injected_ictihats_normalized": norm_sel,
                        "agent_message_len": len(str(agent_message or "")),
                        "agent_message_sha256": self._sha256(str(agent_message or "")),
                        "ui_injected": ui_injected,
                        "ui_injected_block_chars": ui_block_len,
                        "message_head": _clip(message, 800),
                        "agent_message_head": _clip(agent_message, 800),
                    },
                )
            except Exception:
                pass

        payload = await self._build_input_payload(
            user_id=user_id,
            chat_id=chat_id_final,
            history=history,
            message=agent_message,
            include_petitions=not is_student_plan,
            include_selected_ictihat=not is_student_plan,
        )

        q: asyncio.Queue[Optional[bytes]] = asyncio.Queue()

        def _emit(obj: dict) -> bytes:
            return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

        async def _run_and_persist() -> None:
            answer_buf: list[str] = []
            stream_sanitize_carry = ""
            streamed = None
            usage_tuple: tuple[Optional[int], Optional[int], Optional[int]] = (None, None, None)

            try:
                # Intentionally no hard wall-clock timeout here:
                # main user-facing chat streams can legitimately take several minutes.
                payload_json = json.dumps(payload, ensure_ascii=False)

                if self._is_graph_agent(agent):
                    # LangGraph multi-agent path (main + petition agents, shared state).
                    final_state: dict = {}
                    async for ev in stream_law_graph(
                        agent.graph,
                        agent.initial_state(payload_json=payload_json),
                        recursion_limit=self._max_turns() * 2 + 2,
                    ):
                        kind = ev.get("kind")
                        if kind == "text":
                            chunk = ev.get("text") or ""
                            if chunk:
                                answer_buf.append(chunk)
                                safe_chunk, stream_sanitize_carry = self._sanitize_stream_chunk(
                                    stream_sanitize_carry,
                                    chunk,
                                )
                                if safe_chunk:
                                    await q.put(_emit({"type": "text_delta", "chunk": safe_chunk}))
                        elif kind == "tool_call":
                            await q.put(_emit({"type": "tool_call", "name": ev.get("name"), "args": ev.get("args")}))
                        elif kind == "final":
                            final_state = ev.get("state") or {}

                    tail_chunk, _ = self._sanitize_stream_chunk(stream_sanitize_carry, "", final=True)
                    if tail_chunk:
                        await q.put(_emit({"type": "text_delta", "chunk": tail_chunk}))

                    summary = summarize_final_messages(final_state.get("messages") or [])
                    answer = self._strip_internal_trace_tokens(summary["final_text"] or "".join(answer_buf))
                    tool_calls = summary["tool_calls"]
                    tool_outputs = summary["tool_outputs"]
                    web_search_count = summary["web_search_count"]
                    usage_tuple = summary["usage"]
                else:
                    # openai-agents SDK path (student plan).
                    run_config = await build_agents_run_config()
                    streamed = Runner.run_streamed(
                        agent.agent,
                        input=payload_json,
                        max_turns=self._max_turns(),
                        run_config=run_config,
                    )

                    async for event in streamed.stream_events():
                        if isinstance(event, RawResponsesStreamEvent):
                            if isinstance(event.data, ResponseTextDeltaEvent):
                                chunk = event.data.delta or ""
                                if chunk:
                                    answer_buf.append(chunk)
                                    safe_chunk, stream_sanitize_carry = self._sanitize_stream_chunk(
                                        stream_sanitize_carry,
                                        chunk,
                                    )
                                    if safe_chunk:
                                        await q.put(_emit({"type": "text_delta", "chunk": safe_chunk}))

                        elif isinstance(event, RunItemStreamEvent) and event.name == "tool_called":
                            if isinstance(event.item, ToolCallItem) and isinstance(
                                event.item.raw_item, ResponseFunctionToolCall
                            ):
                                raw = event.item.raw_item
                                try:
                                    args: Any = json.loads(raw.arguments or "{}")
                                except Exception:
                                    args = raw.arguments
                                await q.put(_emit({"type": "tool_call", "name": raw.name, "args": args}))

                    tail_chunk, _ = self._sanitize_stream_chunk(stream_sanitize_carry, "", final=True)
                    if tail_chunk:
                        await q.put(_emit({"type": "text_delta", "chunk": tail_chunk}))

                    answer = self._strip_internal_trace_tokens(streamed.final_output or "".join(answer_buf))
                    tool_calls, tool_outputs, web_search_count = self._extract_tool_call_data(
                        streamed.new_items
                    )
                    usage_tuple = extract_agents_sdk_usage(streamed.context_wrapper.usage)

                ictihat_items: list[dict] = []
                try:
                    ictihat_items = self._extract_ictihat_items(tool_calls, tool_outputs)
                except Exception:
                    ictihat_items = []

                chat_has_feature_recommendation = await self._chat_already_has_feature_recommendation(
                    user_id=int(user_id),
                    chat_id=int(chat_id_final),
                )
                feature_recommendation = None
                if not chat_has_feature_recommendation:
                    feature_recommendation = self._extract_feature_recommendation_from_tool_calls(
                        tool_calls,
                        original_message=message,
                    )
                    if feature_recommendation is None and self._should_recommend_ictihat_feature(
                        original_message=message,
                        answer=answer,
                        tool_calls=tool_calls,
                        ictihat_items=ictihat_items,
                    ):
                        feature_recommendation = self._build_ictihat_feature_recommendation(original_message=message)

                assistant_message_id = await asyncio.to_thread(
                    ChatRepository.append_message,
                    chat_id_final, user_id, "assistant", answer, "",
                )
                await self.memory.append_assistant(chat_id_final, answer)

                try:
                    if ictihat_items:
                        await asyncio.to_thread(
                            ChatRepository.set_message_ictihat,
                            message_id=int(assistant_message_id),
                            ictihat_items=ictihat_items,
                        )
                except Exception:
                    pass

                try:
                    await self._persist_assistant_message_context_items(
                        user_id=int(user_id),
                        chat_id=int(chat_id_final),
                        message_id=int(assistant_message_id),
                        feature_recommendation=feature_recommendation,
                    )
                except Exception:
                    pass

                await self._record_run_usage(
                    user_id=user_id,
                    chat_id=chat_id_final,
                    assistant_message_id=int(assistant_message_id),
                    usage_tuple=usage_tuple,
                    model_name=self._agent_model_name(agent),
                    web_search_count=web_search_count,
                )

                await self._maybe_summarize(
                    user_id=user_id,
                    chat_id=chat_id_final,
                    max_history_tokens=self._STUDENT_MAX_HISTORY_TOKENS if is_student_plan else None,
                )

                await q.put(_emit({
                    "type": "done",
                    "chat_id": chat_id_final,
                    "assistant_message_id": int(assistant_message_id),
                    "final_text": answer,
                    "feature_recommendation": feature_recommendation,
                    "ictihat_items": ictihat_items,
                    "ictihat_document_ids": [
                        int(x["document_id"])
                        for x in ictihat_items
                        if x.get("document_id") is not None
                    ],
                }))

            except Exception as exc:
                self._log.exception(
                    "stream_turn failed: user_id=%s chat_id=%s", user_id, chat_id_final
                )

                partial = (
                    self._strip_internal_trace_tokens(streamed.final_output or "") if streamed is not None else ""
                ) or self._strip_internal_trace_tokens("".join(answer_buf))
                safe_msg = partial or "Cevap üretimi sırasında bir hata oluştu. Lütfen daha kısa bir istekle tekrar deneyin."

                try:
                    await asyncio.to_thread(
                        ChatRepository.append_message,
                        chat_id_final, user_id, "assistant", safe_msg,
                        f"error: {type(exc).__name__}: {exc}",
                    )
                    await self.memory.append_assistant(chat_id_final, safe_msg)
                except Exception:
                    pass

                reason = self._reason_for_exception(exc)
                await q.put(_emit({"type": "error", "ok": False, "reason": reason, "detail": str(exc), "message": str(exc)}))

            finally:
                await q.put(None)

        asyncio.create_task(_run_and_persist())

        try:
            while True:
                item = await q.get()
                if item is None:
                    break
                yield item
        except (asyncio.CancelledError, GeneratorExit):
            raise
