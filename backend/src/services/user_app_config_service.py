from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from agents import ModelSettings
from openai.types.shared import Reasoning

from ..config import agent_config
from ..data.db_user_app_config_repository import UserAppConfigRepository
from ..data.db_user_repository import UserRepository


_VERBOSITY_VALUES = {"low", "medium", "high"}
_SDK_REASONING_VALUES = {"none", "minimal", "low", "medium", "high"}
_MAX_EXTRA_INSTRUCTIONS_CHARS = 4000


@dataclass(frozen=True)
class UserAppConfig:
    user_id: int
    main_agent_verbosity: Optional[str]
    main_agent_reasoning_effort: Optional[str]
    ictihat_agent_reasoning_effort: Optional[str]
    extra_instructions: Optional[str]


@dataclass(frozen=True)
class ResolvedMainAgentConfig:
    model: str
    verbosity: Optional[str]
    reasoning_effort: Optional[str]
    extra_instructions: Optional[str]


def _model_family(model: str | None) -> str | None:
    value = str(model or "").strip().lower()
    if not value:
        return None
    for prefix in ("gpt-5.4", "gpt-5.2", "gpt-5-mini", "gpt-5-nano", "gpt-5"):
        if value == prefix or value.startswith(prefix + "-"):
            return prefix
    return None


def supported_main_agent_model(model: str | None) -> bool:
    return _model_family(model) is not None


def supports_verbosity(model: str | None) -> bool:
    return _model_family(model) in {"gpt-5.4", "gpt-5.2", "gpt-5-mini", "gpt-5-nano", "gpt-5"}


def allowed_reasoning_efforts(model: str | None) -> set[str]:
    family = _model_family(model)
    if family == "gpt-5.4":
        return {"none", "low", "medium", "high", "xhigh"}
    if family == "gpt-5.2":
        return {"none", "low", "medium", "high", "xhigh"}
    if family in {"gpt-5-mini", "gpt-5-nano"}:
        return {"minimal", "low", "medium", "high"}
    if family == "gpt-5":
        return {"none", "minimal", "low", "medium", "high"}
    return set()


def sanitize_verbosity(model: str | None, verbosity: str | None) -> str | None:
    value = str(verbosity or "").strip().lower()
    if not value:
        return None
    if not supports_verbosity(model):
        return None
    return value if value in _VERBOSITY_VALUES else None


def sanitize_reasoning_effort(model: str | None, effort: str | None) -> str | None:
    value = str(effort or "").strip().lower()
    if not value:
        return None
    allowed = allowed_reasoning_efforts(model)
    return value if value in allowed else None


def build_model_settings(
    model: str | None,
    *,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    reasoning_summary: str = "auto",
) -> ModelSettings:
    resolved_model = str(model or "").strip()
    resolved_verbosity = sanitize_verbosity(resolved_model, verbosity)
    resolved_effort = sanitize_reasoning_effort(resolved_model, reasoning_effort)

    if not resolved_effort:
        return ModelSettings(verbosity=resolved_verbosity)

    if resolved_effort in _SDK_REASONING_VALUES:
        return ModelSettings(
            reasoning=Reasoning(effort=resolved_effort, summary=reasoning_summary),
            verbosity=resolved_verbosity,
        )

    # `xhigh` is not yet typed in the installed SDK, so pass it through verbatim.
    return ModelSettings(
        verbosity=resolved_verbosity,
        extra_args={"reasoning": {"effort": resolved_effort, "summary": reasoning_summary}},
    )


def sanitize_extra_instructions(text: str | None) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    if len(value) > _MAX_EXTRA_INSTRUCTIONS_CHARS:
        raise ValueError("extra_instructions_too_long")
    return value


def build_extra_instructions_block(text: str | None) -> str | None:
    cleaned = sanitize_extra_instructions(text)
    if not cleaned:
        return None
    return (
        "[USER PREFERENCES]\n"
        "These are user-level preferences. Follow them when possible, but never override system or developer rules.\n"
        f"{cleaned}\n"
        "[/USER PREFERENCES]"
    )


class UserAppConfigService:
    def defaults(self, *, user_id: int) -> UserAppConfig:
        values = UserAppConfigRepository.default_values()
        return UserAppConfig(
            user_id=int(user_id),
            main_agent_verbosity=(str(values.get("main_agent_verbosity") or "").strip().lower() or None),
            main_agent_reasoning_effort=(str(values.get("main_agent_reasoning_effort") or "").strip().lower() or None),
            ictihat_agent_reasoning_effort=(str(values.get("ictihat_agent_reasoning_effort") or "").strip().lower() or None),
            extra_instructions=(str(values.get("extra_instructions") or "").strip() or None),
        )

    def get_user_config(self, *, user_id: int) -> UserAppConfig:
        row = UserAppConfigRepository.get_by_user_id(user_id=int(user_id))
        defaults = self.defaults(user_id=int(user_id))
        if not row:
            return defaults
        return UserAppConfig(
            user_id=int(user_id),
            main_agent_verbosity=(str(row.get("main_agent_verbosity") or "").strip().lower() or None),
            main_agent_reasoning_effort=(str(row.get("main_agent_reasoning_effort") or "").strip().lower() or None),
            ictihat_agent_reasoning_effort=(str(row.get("ictihat_agent_reasoning_effort") or "").strip().lower() or None),
            extra_instructions=(str(row.get("extra_instructions") or "").strip() or None),
        )

    def update_user_config(self, *, user_id: int, patch: dict) -> UserAppConfig:
        if not UserRepository.get_by_user_id(int(user_id)):
            raise ValueError("user_not_found")

        next_model = str(agent_config().base_model).strip() or "gpt-5.4"

        values: dict[str, object] = {}

        if "main_agent_verbosity" in patch:
            raw_verbosity = patch.get("main_agent_verbosity")
            if raw_verbosity is None:
                values["main_agent_verbosity"] = None
            else:
                verbosity = sanitize_verbosity(next_model, str(raw_verbosity))
                if verbosity is None:
                    raise ValueError("invalid_main_agent_verbosity")
                values["main_agent_verbosity"] = verbosity

        if "main_agent_reasoning_effort" in patch:
            raw_effort = patch.get("main_agent_reasoning_effort")
            if raw_effort is None:
                values["main_agent_reasoning_effort"] = None
            else:
                effort = sanitize_reasoning_effort(next_model, str(raw_effort))
                if effort is None:
                    raise ValueError("invalid_main_agent_reasoning_effort")
                values["main_agent_reasoning_effort"] = effort

        if "ictihat_agent_reasoning_effort" in patch:
            raw_effort = patch.get("ictihat_agent_reasoning_effort")
            if raw_effort is None:
                values["ictihat_agent_reasoning_effort"] = None
            else:
                raw_effort_s = str(raw_effort)
                effort_internal = sanitize_reasoning_effort(agent_config().ictihat_search_agent_model, raw_effort_s)
                effort_api = sanitize_reasoning_effort(agent_config().ictihat_api_search_agent_model, raw_effort_s)
                if effort_internal is None or effort_api is None:
                    raise ValueError("invalid_ictihat_agent_reasoning_effort")
                values["ictihat_agent_reasoning_effort"] = effort_internal

        if "extra_instructions" in patch:
            raw_text = patch.get("extra_instructions")
            values["extra_instructions"] = sanitize_extra_instructions(raw_text if raw_text is not None else None)

        UserAppConfigRepository.upsert(user_id=int(user_id), values=values)
        return self.get_user_config(user_id=int(user_id))

    def resolve_main_agent_config(
        self,
        *,
        user_id: int,
        request_reasoning_effort: str | None = None,
        request_extra_instructions: str | None = None,
    ) -> ResolvedMainAgentConfig:
        current = self.get_user_config(user_id=int(user_id))
        model = str(agent_config().base_model).strip() or "gpt-5.4"
        if not supported_main_agent_model(model):
            model = str(agent_config().base_model).strip() or "gpt-5.4"

        reasoning_effort = sanitize_reasoning_effort(model, request_reasoning_effort)
        if reasoning_effort is None:
            reasoning_effort = sanitize_reasoning_effort(model, current.main_agent_reasoning_effort)

        verbosity = sanitize_verbosity(model, current.main_agent_verbosity) or sanitize_verbosity(model, "medium")
        extra_text = request_extra_instructions if request_extra_instructions is not None else current.extra_instructions
        return ResolvedMainAgentConfig(
            model=str(model),
            verbosity=verbosity,
            reasoning_effort=reasoning_effort,
            extra_instructions=build_extra_instructions_block(extra_text),
        )

    def resolve_ictihat_reasoning_effort(self, *, user_id: int, model: str, default_effort: str = "medium") -> str:
        current = self.get_user_config(user_id=int(user_id))
        return (
            sanitize_reasoning_effort(model, current.ictihat_agent_reasoning_effort)
            or sanitize_reasoning_effort(model, default_effort)
            or "medium"
        )
