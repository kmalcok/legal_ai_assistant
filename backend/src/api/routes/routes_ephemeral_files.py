from __future__ import annotations

import base64
import re
from urllib.parse import quote
from typing import Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...utils.ephemeral_store import ephemeral_files
from ..auth import decode_and_validate_token, payload_user_id


router = APIRouter(prefix="/files", tags=["files"])


def _ascii_filename_fallback(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "document.docx"
    safe = re.sub(r"[^\x20-\x7E]+", "_", name)
    safe = re.sub(r'[\\/:*?"<>|]+', "_", safe)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe or "document.docx"


def _content_disposition(filename: str) -> str:
    fallback = _ascii_filename_fallback(filename)
    fn_star = quote(filename or "", safe="")
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{fn_star}'


@router.get("/ephemeral/{token}/download", response_model=None)
async def download_ephemeral_file(request: Request, token: str) -> StreamingResponse:
    """
    Download an ephemeral file produced by tools (e.g. generic Word output).
    """
    # Do NOT consume on download. File should remain available until TTL expires.
    rec = await ephemeral_files.get(str(token))
    if rec is None:
        raise HTTPException(status_code=404, detail={"ok": False, "reason": "not_found"})

    # Best-effort auth: if we can determine user_id from middleware or bearer token,
    # require it to match the file owner. If we cannot, allow download (capability token + TTL).
    uid: int | None = None
    try:
        st = getattr(getattr(request, "state", None), "user_id", None)
        if st is not None:
            uid = int(st)
    except Exception:
        uid = None
    if uid is None:
        try:
            auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
            parts = auth.split(" ", 1)
            if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
                bearer = parts[1].strip()
                payload, _err = decode_and_validate_token(bearer, expected_type="access")
                if payload is not None:
                    uid = int(payload_user_id(payload))
        except Exception:
            uid = None
    if uid is not None and int(uid) != int(rec.user_id):
        raise HTTPException(status_code=403, detail={"ok": False, "reason": "forbidden"})

    try:
        data = base64.b64decode(rec.content_b64.encode("ascii"))
    except Exception:
        raise HTTPException(status_code=500, detail={"ok": False, "reason": "decode_failed"})

    # NOTE: UDF/PDF download variants for ephemeral files were intentionally removed.
    # We keep the old implementation as comments for potential future re-introduction,
    # but the product decision is: ephemeral downloads serve ONLY the original artifact.
    #
    # Previously supported:
    # - ?format=udf  (docx -> udf conversion or cached variant)
    # - ?format=pdf  (docx -> pdf conversion or cached variant)
    #
    out_bytes = data
    out_mime = rec.mime
    out_filename = rec.filename

    async def _iter():
        yield out_bytes

    headers: Dict[str, str] = {"Content-Disposition": _content_disposition(out_filename)}
    return StreamingResponse(_iter(), media_type=out_mime, headers=headers)


