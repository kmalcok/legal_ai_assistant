from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...data.db_user_repository import UserRepository
from ...services.user_app_config_service import UserAppConfigService
from ..errors import api_error


router = APIRouter(prefix="/user", tags=["user"])
_service = UserAppConfigService()


class UserAppConfigPatchRequest(BaseModel):
    main_agent_verbosity: Optional[str] = None
    main_agent_reasoning_effort: Optional[str] = None
    ictihat_agent_reasoning_effort: Optional[str] = None
    extra_instructions: Optional[str] = None


def _config_to_payload(cfg: Any) -> Dict[str, Any]:
    return {
        "main_agent_verbosity": cfg.main_agent_verbosity,
        "main_agent_reasoning_effort": cfg.main_agent_reasoning_effort,
        "ictihat_agent_reasoning_effort": cfg.ictihat_agent_reasoning_effort,
        "extra_instructions": cfg.extra_instructions or "",
    }


@router.get("/app-config", response_model=dict)
async def get_user_app_config(request: Request) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    cfg = _service.get_user_config(user_id=user_id)
    return {"ok": True, "config": _config_to_payload(cfg)}


@router.patch("/app-config", response_model=dict)
async def patch_user_app_config(request: Request, payload: UserAppConfigPatchRequest) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    if hasattr(payload, "model_dump"):
        patch = payload.model_dump(exclude_unset=True)
    else:
        patch = payload.dict(exclude_unset=True)
    try:
        cfg = _service.update_user_config(user_id=user_id, patch=patch)
    except ValueError as exc:
        reason = str(exc or "bad_request")
        if reason == "user_not_found":
            raise api_error(404, reason)
        raise api_error(400, reason)
    except HTTPException:
        raise
    return {"ok": True, "config": _config_to_payload(cfg)}


@router.get("/credit-usage-summary", response_model=dict)
async def get_credit_usage_summary(request: Request) -> Dict[str, Any]:
    user_id = int(getattr(request.state, "user_id"))
    try:
        summary = UserRepository.get_credit_usage_summary(user_id=user_id, lookback_days=14)
    except ValueError as exc:
        reason = str(exc or "bad_request")
        if reason == "user_not_found":
            raise api_error(404, reason)
        raise api_error(400, reason)
    except HTTPException:
        raise
    return {"ok": True, "summary": summary}
