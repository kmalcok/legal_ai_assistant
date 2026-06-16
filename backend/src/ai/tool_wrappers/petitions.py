from __future__ import annotations

import asyncio
import json
import hashlib
from typing import Any, Dict, Optional

from ...calendar_events.service import register_from_petition as _calendar_register_from_petition
from ...petitions.pipeline import (
    PetitionPipelineError,
    build_summary_text,
    generate_petition_artifacts_from_output_json,
)
from ...petitions.repository import PetitionRepository
from ...realtime.ws_manager import chat_ws_manager
from ..logging.agent_audit import audit_log


async def _maybe_register_calendar_events(
    *,
    user_id: int,
    chat_id: int,
    petition_id: int,
    output_obj: Dict[str, Any],
) -> None:
    """Best-effort fallback. Never raises; never blocks petition completion."""
    try:
        events = await asyncio.to_thread(
            _calendar_register_from_petition,
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            output_obj=dict(output_obj or {}),
            source="petition_auto",
        )
        if events:
            try:
                await chat_ws_manager.publish(
                    int(chat_id),
                    {
                        "type": "calendar_event_added",
                        "chat_id": int(chat_id),
                        "petition_id": int(petition_id),
                        "count": int(len(events)),
                    },
                )
            except Exception:
                pass
    except Exception:
        pass


async def _safe_publish(chat_id: int, payload: Dict[str, Any]) -> int:
    sent_total = 0
    try:
        sent_total += int(await chat_ws_manager.publish(int(chat_id), payload))
    except Exception:
        pass
    return int(sent_total)


async def petition_list(*, user_id: int, chat_id: int, limit: int = 20) -> Dict[str, Any]:
    try:
        rows = await asyncio.to_thread(PetitionRepository.list_for_chat, user_id=int(user_id), chat_id=int(chat_id), limit=int(limit))
        return {"ok": True, "chat_id": int(chat_id), "petitions": rows}
    except ValueError as exc:
        return {"ok": False, "reason": "chat_not_found", "detail": str(exc)}
    except Exception as exc:
        return {"ok": False, "reason": "error", "detail": str(exc)}


async def petition_get_summary(
    *,
    user_id: int,
    chat_id: int,
    petition_id: int,
    version_id: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        row = await asyncio.to_thread(
            PetitionRepository.get_version_summary,
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            version_id=int(version_id) if version_id is not None else None,
        )
        return {
            "ok": True,
            "chat_id": int(chat_id),
            "petition_id": int(petition_id),
            "version": {
                "version_id": int(row["version_id"]),
                "version_no": int(row["version_no"]),
                "docx_filename": row.get("docx_filename"),
                "summary_text": row.get("summary_text"),
                "created_at": row.get("created_at"),
            },
        }
    except ValueError as exc:
        return {"ok": False, "reason": "not_found", "detail": str(exc)}
    except Exception as exc:
        return {"ok": False, "reason": "error", "detail": str(exc)}


async def petition_generate(
    *,
    user_id: int,
    chat_id: int,
    petition_json: str,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Real-time (awaited) no-LLM pipeline:
    - validate petition_json
    - schema-validate + deterministic normalize
    - render DOCX bytes
    - store in DB (petition + version)
    - publish websocket events to chat:{chat_id}
    """
    pj = (petition_json or "").strip()
    if not pj:
        ws_sent = await _safe_publish(
            int(chat_id),
            {"type": "petition_failed", "op": "generate", "chat_id": int(chat_id), "error": "petition_json_empty"},
        )
        return {"ok": False, "reason": "invalid_petition_json", "detail": "petition_json_empty", "websocket_sent": int(ws_sent)}
    # Persist what the main agent sent for audit/debug.
    sha = hashlib.sha256(pj.encode("utf-8", errors="replace")).hexdigest()
    audit_log(
        "petition_tool_input",
        {
            "tool": "petition_generate",
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "filename": str(filename or ""),
            "petition_json_len": int(len(pj)),
            "petition_json_sha256": sha,
            "petition_json": pj,
        },
    )
    intake_obj: Dict[str, Any] = {"petition_json_provided": True, "petition_json_sha256": sha, "petition_json_len": int(len(pj))}
    petition_id: int | None = None
    try:
        artifacts = await generate_petition_artifacts_from_output_json(output_json=pj, preferred_filename=filename)
        meta = artifacts.output_obj.get("meta") if isinstance(artifacts.output_obj.get("meta"), dict) else {}
        doc_type = (meta.get("document_type") or "").strip() or None
        court = (meta.get("court") or "").strip() or None
        petition_id = await asyncio.to_thread(PetitionRepository.create_petition, user_id=int(user_id), chat_id=int(chat_id), title=None)
        # Add version first with placeholder summary; update summary_text by re-inserting row is expensive.
        # Instead: build summary with IDs after insert, then insert with final summary.
        # We'll insert using final summary directly by computing version after insert id.
        # (We need version_id to include in summary, so we insert once with temp summary then update via second statement.)
        # To keep repository simple, do it as two operations:
        tmp_summary = "petition generated"
        version_id, version_no = await asyncio.to_thread(
            PetitionRepository.add_version,
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            intake_json=json.dumps(intake_obj, ensure_ascii=False),
            output_json=artifacts.output_json,
            summary_text=tmp_summary,
            docx_filename=artifacts.docx_filename,
            docx_blob=artifacts.docx_bytes,
            udf_filename=artifacts.udf_filename,
            udf_blob=artifacts.udf_bytes,
        )
        summary_text = build_summary_text(artifacts.output_obj, petition_id=int(petition_id), version_id=int(version_id), filename=artifacts.docx_filename)

        # Update petition header fields + status; also overwrite summary_text in latest version with a lightweight update.
        await asyncio.to_thread(
            PetitionRepository.set_petition_status,
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            status="ready",
            error_message=None,
            document_type=doc_type,
            court=court,
        )
        # Patch summary_text in petition_versions
        await asyncio.to_thread(_update_version_summary_text, int(version_id), summary_text)

        # Best-effort: scan header_blocks for Süre/Zamanaşımı Notu and register calendar events.
        await _maybe_register_calendar_events(
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            output_obj=artifacts.output_obj,
        )

        ws_sent = await _safe_publish(
            int(chat_id),
            {
                "type": "petition_ready",
                "op": "generate",
                "chat_id": int(chat_id),
                "petition_id": int(petition_id),
                "version_id": int(version_id),
                "filename": artifacts.docx_filename,
            },
        )
        # IMPORTANT: Do not return internal IDs to the main agent to avoid user-facing leakage.
        # The client already receives petition_id/version_id via websocket event.
        return {
            "ok": True,
            "chat_id": int(chat_id),
            "docx_filename": artifacts.docx_filename,
            "summary_text": summary_text,
            "document_type": doc_type,
            "court": court,
            "websocket_sent": int(ws_sent),
            "download_hint": "Dilekçe hazır. İndirme işlemi istemci tarafından websocket 'petition_ready' olayı ile yapılır.",
        }
    except PetitionPipelineError as exc:
        ws_sent = await _safe_publish(
            int(chat_id),
            {"type": "petition_failed", "op": "generate", "chat_id": int(chat_id), "error": str(exc)},
        )
        return {"ok": False, "reason": "pipeline_error", "detail": str(exc), "websocket_sent": int(ws_sent)}
    except Exception as exc:
        if petition_id is not None:
            try:
                await asyncio.to_thread(
                    PetitionRepository.delete_petition,
                    user_id=int(user_id),
                    chat_id=int(chat_id),
                    petition_id=int(petition_id),
                )
            except Exception:
                pass
        ws_sent = await _safe_publish(
            int(chat_id),
            {"type": "petition_failed", "op": "generate", "chat_id": int(chat_id), "error": str(exc)},
        )
        return {"ok": False, "reason": "error", "detail": str(exc), "websocket_sent": int(ws_sent)}


def _update_version_summary_text(version_id: int, summary_text: str) -> None:
    from ...db import core_db

    with core_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE petition_versions SET summary_text=%s WHERE version_id=%s",
            (summary_text, int(version_id)),
        )
        conn.commit()


async def petition_revise(
    *,
    user_id: int,
    chat_id: int,
    petition_id: int,
    petition_json: str,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    No-LLM revision strategy:
    - Validate petition exists
    - Accept revised petition JSON from main agent
    - Validate + normalize + render and store as new version
    """
    try:
        await asyncio.to_thread(
            PetitionRepository.get_version_summary,
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            # latest when version_id None
            version_id=None,
        )
    except Exception as exc:
        ws_sent = await _safe_publish(
            int(chat_id),
            {"type": "petition_failed", "op": "revise", "chat_id": int(chat_id), "error": str(exc)},
        )
        return {"ok": False, "reason": "not_found", "detail": str(exc), "websocket_sent": int(ws_sent)}
    pj = (petition_json or "").strip()
    if not pj:
        ws_sent = await _safe_publish(
            int(chat_id),
            {"type": "petition_failed", "op": "revise", "chat_id": int(chat_id), "error": "petition_json_empty"},
        )
        return {"ok": False, "reason": "invalid_petition_json", "detail": "petition_json_empty", "websocket_sent": int(ws_sent)}
    sha = hashlib.sha256(pj.encode("utf-8", errors="replace")).hexdigest()
    audit_log(
        "petition_tool_input",
        {
            "tool": "petition_revise",
            "user_id": int(user_id),
            "chat_id": int(chat_id),
            "petition_id": int(petition_id),
            "filename": str(filename or ""),
            "petition_json_len": int(len(pj)),
            "petition_json_sha256": sha,
            "petition_json": pj,
        },
    )
    intake_obj = {"petition_json_provided": True, "mode": "revise", "petition_json_sha256": sha, "petition_json_len": int(len(pj))}

    try:
        artifacts = await generate_petition_artifacts_from_output_json(output_json=pj, preferred_filename=filename)

        tmp_summary = "dilekce revize edildi"
        version_id, version_no = await asyncio.to_thread(
            PetitionRepository.add_version,
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            intake_json=json.dumps(intake_obj, ensure_ascii=False),
            output_json=artifacts.output_json,
            summary_text=tmp_summary,
            docx_filename=artifacts.docx_filename,
            docx_blob=artifacts.docx_bytes,
            udf_filename=artifacts.udf_filename,
            udf_blob=artifacts.udf_bytes,
        )
        summary_text = build_summary_text(artifacts.output_obj, petition_id=int(petition_id), version_id=int(version_id), filename=artifacts.docx_filename)
        await asyncio.to_thread(_update_version_summary_text, int(version_id), summary_text)

        meta = artifacts.output_obj.get("meta") if isinstance(artifacts.output_obj.get("meta"), dict) else {}
        doc_type = (meta.get("document_type") or "").strip() or None
        court = (meta.get("court") or "").strip() or None
        await asyncio.to_thread(
            PetitionRepository.set_petition_status,
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            status="ready",
            error_message=None,
            document_type=doc_type,
            court=court,
        )

        # Best-effort: scan header_blocks for Süre/Zamanaşımı Notu and register calendar events.
        await _maybe_register_calendar_events(
            user_id=int(user_id),
            chat_id=int(chat_id),
            petition_id=int(petition_id),
            output_obj=artifacts.output_obj,
        )

        ws_sent = await _safe_publish(
            int(chat_id),
            {
                "type": "petition_ready",
                "chat_id": int(chat_id),
                "op": "revise",
                "petition_id": int(petition_id),
                "version_id": int(version_id),
                "filename": artifacts.docx_filename,
            },
        )
        return {
            "ok": True,
            "chat_id": int(chat_id),
            "docx_filename": artifacts.docx_filename,
            "summary_text": summary_text,
            "document_type": doc_type,
            "court": court,
            "websocket_sent": int(ws_sent),
            "download_hint": "Revize dilekçe hazır. İndirme işlemi istemci tarafından websocket 'petition_ready' olayı ile yapılır.",
        }
    except Exception as exc:
        ws_sent = await _safe_publish(
            int(chat_id),
            {"type": "petition_failed", "op": "revise", "chat_id": int(chat_id), "error": str(exc)},
        )
        return {"ok": False, "reason": "error", "detail": str(exc), "websocket_sent": int(ws_sent)}


