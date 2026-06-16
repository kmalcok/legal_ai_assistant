from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...ai.memory.redis_memory import RedisMemory
from ...data.db_chat_context_repository import ChatContextRepository
from ...data.db_chat_repository import ChatRepository
from ...services.agent_service import AgentService
from ...utils.ephemeral_store import ephemeral_files
from ..credit_guard import ensure_sufficient_credits
from ..errors import api_error


router = APIRouter(prefix="/chat", tags=["chat"])


def _pydantic_to_dict(obj: Any) -> Dict[str, Any]:
    # Pydantic v1: .dict(); v2: .model_dump()
    if hasattr(obj, "model_dump"):
        try:
            # Avoid pydantic serializer warnings from nested OpenAI SDK unions.
            return obj.model_dump(warnings=False)
        except TypeError:
            return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj) if isinstance(obj, dict) else {}


class SelectedIctihatItem(BaseModel):
    document_id: int = Field(..., gt=0)
    emsal_no: Optional[str] = None
    karar_no: Optional[str] = None
    daire: Optional[str] = None
    kurum: Optional[str] = None


class SelectedPetitionContextItem(BaseModel):
    petition_id: int = Field(..., gt=0)
    version_id: Optional[int] = Field(default=None, gt=0)
    field_path: str = Field(..., min_length=1)
    selected_text: Optional[str] = None
    section_title: Optional[str] = None


class ChatStreamRequest(BaseModel):
    message: str = Field(..., min_length=1)
    chat_id: Optional[int] = None
    reasoning: Optional[str] = None
    # Pinned ictihats injected into THIS turn's user message.
    injected_ictihats: Optional[List[SelectedIctihatItem]] = Field(
        default=None,
        description="Pinned ictihats to inject into THIS turn's user message.",
    )
    injected_petition_contexts: Optional[List[SelectedPetitionContextItem]] = Field(
        default=None,
        description="Pinned petition selections to inject into THIS turn's user message.",
    )

    # Forbid unknown fields like legacy `selected_ictihats`.
    class Config:
        extra = "forbid"


@router.post("/create", response_model=dict)
async def create_chat(
    request: Request,
    title: Optional[str] = Body(default=None, embed=True),
) -> Dict[str, Any]:
    try:
        user_id = int(getattr(request.state, "user_id"))
        chat_id = await asyncio.to_thread(ChatRepository.create_chat, user_id, title)
        return {"ok": True, "chat_id": int(chat_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/list", response_model=dict)
async def list_chats(
    request: Request,
    limit: int = Body(default=50, embed=True),
    offset: int = Body(default=0, embed=True),
) -> Dict[str, Any]:
    """
    List chats for the current user.

    Response shape example:
    {
      "ok": true,
      "chats": [
        {
          "chat_id": 123,
          "user_id": 45,
          "title": null,
          "first_message": "Dilekceyi duzelt",
          "last_sum": null,
          "archived": 0,
          "created_at": "2026-03-22T16:00:00",
          "updated_at": "2026-03-22T16:05:00",
          "context_items": [
            {
              "context_item_id": 7,
              "chat_id": 123,
              "message_id": 901,
              "user_id": 45,
              "kind": "injected_petition_context",
              "source": "ui",
              "sort_order": 0,
              "payload": {
                "petition_id": 88,
                "version_id": 145,
                "version_no": 3,
                "field_path": "talep_sonucu",
                "selected_text": "faiz ile birlikte tahsiline",
                "resolved_text": "faiz ile birlikte tahsiline",
                "section_title": "Talep Sonucu",
                "docx_filename": "dilekce-v3.docx",
                "document_type": "Dava Dilekcesi",
                "court": "Ankara 3. Asliye Hukuk Mahkemesi"
              },
              "created_at": "2026-03-22T16:04:46"
            },
            {
              "context_item_id": 8,
              "chat_id": 123,
              "message_id": 901,
              "user_id": 45,
              "kind": "injected_ictihat",
              "source": "ui",
              "sort_order": 1,
              "payload": {
                "document_id": 998877,
                "emsal_no": "2016/1577 E.",
                "karar_no": "2021/11917 K.",
                "kurum": "YARGITAY",
                "daire": "3. Hukuk Dairesi",
                "daire_label": "Yargitay 3. Hukuk Dairesi"
              },
              "created_at": "2026-03-22T16:04:46"
            }
          ]
        }
      ],
      "limit": 50,
      "offset": 0
    }
    """
    try:
        user_id = int(getattr(request.state, "user_id"))
        rows = await asyncio.to_thread(ChatRepository.list_chats, user_id, int(limit), int(offset))
        chat_ids = [
            int(row.get("chat_id"))
            for row in (rows or [])
            if isinstance(row, dict) and row.get("chat_id") is not None
        ]
        context_map = await asyncio.to_thread(ChatContextRepository.list_for_chat_ids, user_id=user_id, chat_ids=chat_ids)
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                cid = int(row.get("chat_id"))
            except Exception:
                continue
            row["context_items"] = list(context_map.get(cid) or [])
        return {"ok": True, "chats": rows, "limit": int(limit), "offset": int(offset)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{chat_id}", response_model=dict)
async def delete_chat(request: Request, chat_id: int) -> Dict[str, Any]:
    """
    Hard delete a chat and all related data:
      - chat + messages + petitions + petition_versions + chat_documents (DB cascades)
      - user_usages rows for this chat
      - Redis chat memory
      - optionally deletes documents that were attached to the chat AND not referenced by any other chat (same user)
      - best-effort purges ephemeral files for this chat
    """
    try:
        user_id = int(getattr(request.state, "user_id"))
        # DB deletion first (authoritative)
        res = await asyncio.to_thread(ChatRepository.hard_delete_chat, chat_id=int(chat_id), user_id=int(user_id), delete_documents=True)

        # Clear Redis / fallback chat memory
        try:
            mem = RedisMemory()
            await mem.clear(int(chat_id))
        except Exception:
            pass

        # Best-effort purge ephemeral files created for this chat
        try:
            purged = await ephemeral_files.purge_chat(chat_id=int(chat_id), user_id=int(user_id))
            res["purged_ephemeral_files"] = int(purged)
        except Exception:
            res["purged_ephemeral_files"] = 0

        return {"ok": True, **res}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history/{chat_id}", response_model=dict)
async def get_history(request: Request, chat_id: int) -> Dict[str, Any]:
    """
    Get chat history.

    Response shape example:
    {
      "ok": true,
      "chat_id": 123,
      "history": [
        {
          "id": 901,
          "role": "user",
          "message": "Burayi duzelt",
          "created_at": "2026-03-22T16:04:46",
          "context_items": [
            {
              "context_item_id": 7,
              "chat_id": 123,
              "message_id": 901,
              "user_id": 45,
              "kind": "injected_petition_context",
              "source": "ui",
              "sort_order": 0,
              "payload": {
                "petition_id": 88,
                "version_id": 145,
                "version_no": 3,
                "field_path": "talep_sonucu",
                "selected_text": "faiz ile birlikte tahsiline",
                "resolved_text": "faiz ile birlikte tahsiline",
                "section_title": "Talep Sonucu",
                "docx_filename": "dilekce-v3.docx",
                "document_type": "Dava Dilekcesi",
                "court": "Ankara 3. Asliye Hukuk Mahkemesi"
              },
              "created_at": "2026-03-22T16:04:46"
            }
          ]
        },
        {
          "id": 902,
          "role": "assistant",
          "message": "Ilgili kismi guncelledim.",
          "created_at": "2026-03-22T16:05:10",
          "context_items": [],
          "ictihat_items": [
            {
              "document_id": 998877,
              "kurum": "YARGITAY",
              "daire": "3. Hukuk Dairesi",
              "daire_label": "Yargitay 3. Hukuk Dairesi",
              "esas_yil": 2016,
              "esas_sira": 1577,
              "karar_yil": 2021,
              "karar_sira": 11917,
              "karar_tarihi": "2021-11-02"
            }
          ],
          "ictihat_document_ids": [998877]
        }
      ]
    }
    """
    try:
        user_id = int(getattr(request.state, "user_id"))
        rows = await asyncio.to_thread(ChatRepository.get_recent_messages, int(chat_id), user_id, 200)
        # Attach message-scoped ictihat lists (if any) and do not expose internal reasoning fields.
        safe_rows = []
        msg_ids: list[int] = []
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict) and "reasoning" in r:
                    r = dict(r)
                    r.pop("reasoning", None)
                try:
                    if isinstance(r, dict) and r.get("id") is not None:
                        msg_ids.append(int(r.get("id")))
                except Exception:
                    pass
                if isinstance(r, dict):
                    r.setdefault("context_items", [])
                safe_rows.append(r)

        try:
            ictihat_map = await asyncio.to_thread(ChatRepository.get_messages_ictihat_map, message_ids=msg_ids)
        except Exception:
            ictihat_map = {}
        try:
            context_map = await asyncio.to_thread(
                ChatContextRepository.list_for_message_ids,
                user_id=user_id,
                message_ids=msg_ids,
            )
        except Exception:
            context_map = {}
        if safe_rows and isinstance(ictihat_map, dict) and ictihat_map:
            for r in safe_rows:
                if not isinstance(r, dict):
                    continue
                try:
                    mid = int(r.get("id")) if r.get("id") is not None else None
                except Exception:
                    mid = None
                if mid is None:
                    continue
                if mid in ictihat_map:
                    items = ictihat_map.get(mid) or []
                    r["ictihat_items"] = items
                    # back-compat / convenience
                    try:
                        r["ictihat_document_ids"] = [
                            int(x.get("document_id"))
                            for x in (items or [])
                            if isinstance(x, dict) and x.get("document_id") is not None
                        ]
                    except Exception:
                        r["ictihat_document_ids"] = []
        if safe_rows and isinstance(context_map, dict) and context_map:
            for r in safe_rows:
                if not isinstance(r, dict):
                    continue
                try:
                    mid = int(r.get("id")) if r.get("id") is not None else None
                except Exception:
                    mid = None
                if mid is None:
                    continue
                if mid in context_map:
                    r["context_items"] = list(context_map.get(mid) or [])

        return {"ok": True, "chat_id": int(chat_id), "history": safe_rows}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/stream", response_model=None)
async def stream_chat(
    request: Request,
    payload: ChatStreamRequest,
) -> StreamingResponse:
    """
    Stream a single agent turn as newline-delimited JSON (NDJSON).

    Events:
      - {"type":"text_delta","chunk":"..."}
      - {"type":"tool_call","name":"...","args":{...}}
      - {"type":"done","chat_id":123,"final_text":"..."}
      - {"type":"error","ok":false,"reason":"...","detail":"...","message":"..."}
    """
    svc = AgentService()
    user_id = int(getattr(request.state, "user_id"))
    await ensure_sufficient_credits(user_id)
    injected = payload.injected_ictihats
    injected_dicts = [_pydantic_to_dict(x) for x in (injected or [])] if injected is not None else None
    petition_contexts = payload.injected_petition_contexts
    petition_context_dicts = (
        [_pydantic_to_dict(x) for x in (petition_contexts or [])]
        if petition_contexts is not None
        else None
    )
    gen = svc.stream_turn(
        user_id=user_id,
        chat_id=payload.chat_id,
        message=payload.message,
        reasoning_pref=payload.reasoning,
        injected_ictihats=injected_dicts,
        injected_petition_contexts=petition_context_dicts,
    )
    return StreamingResponse(gen, media_type="application/x-ndjson")


@router.post("/message", response_model=dict)
async def send_message(
    request: Request,
    message: str = Body(embed=True),
    chat_id: Optional[int] = Body(default=None, embed=True),
    reasoning: Optional[str] = Body(default=None, embed=True),
    injected_ictihats: Optional[List[SelectedIctihatItem]] = Body(default=None, embed=True),
    injected_petition_contexts: Optional[List[SelectedPetitionContextItem]] = Body(default=None, embed=True),
) -> Dict[str, Any]:
    """
    Non-streaming variant: runs one agent turn and returns the final message.
    """
    user_id = int(getattr(request.state, "user_id"))
    await ensure_sufficient_credits(user_id)
    svc = AgentService()
    try:
        injected_dicts = (
            [_pydantic_to_dict(x) for x in (injected_ictihats or [])]
            if injected_ictihats is not None
            else None
        )
        petition_context_dicts = (
            [_pydantic_to_dict(x) for x in (injected_petition_contexts or [])]
            if injected_petition_contexts is not None
            else None
        )
        chat_id_final, answer, feature_recommendation = await svc.run_turn(
            user_id=user_id,
            chat_id=chat_id,
            message=message,
            reasoning_pref=reasoning,
            injected_ictihats=injected_dicts,
            injected_petition_contexts=petition_context_dicts,
        )
        return {
            "ok": True,
            "chat_id": int(chat_id_final),
            "final_text": answer,
            "feature_recommendation": feature_recommendation,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


