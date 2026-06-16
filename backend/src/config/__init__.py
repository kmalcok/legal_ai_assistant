from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .loader import config_dir_name, load_json_config
from .schemas import AgentConfig, AppConfig, CreditConfig, JwtConfig, LogConfig, MailConfig, MysqlConfig


def load_env() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    load_dotenv(dotenv_path=backend_root / ".env", override=True)


def _int_env(name: str, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        value = int((os.getenv(name, str(default)) or str(default)).strip())
    except Exception:
        value = int(default)
    if min_value is not None:
        value = max(int(min_value), value)
    if max_value is not None:
        value = min(int(max_value), value)
    return int(value)


def _float_env(name: str, default: float, *, min_value: float | None = None, max_value: float | None = None) -> float:
    try:
        value = float((os.getenv(name, str(default)) or str(default)).strip())
    except Exception:
        value = float(default)
    if min_value is not None:
        value = max(float(min_value), value)
    if max_value is not None:
        value = min(float(max_value), value)
    return float(value)


def _str_env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _bool_json(source: dict[str, Any], key: str, default: bool = False) -> bool:
    raw = source.get(key, default)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _int_json(source: dict[str, Any], key: str, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        value = int(source.get(key, default))
    except Exception:
        value = int(default)
    if min_value is not None:
        value = max(int(min_value), value)
    if max_value is not None:
        value = min(int(max_value), value)
    return int(value)


def _float_json(
    source: dict[str, Any],
    key: str,
    default: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    try:
        value = float(source.get(key, default))
    except Exception:
        value = float(default)
    if min_value is not None:
        value = max(float(min_value), value)
    if max_value is not None:
        value = min(float(max_value), value)
    return float(value)


def _str_json(source: dict[str, Any], key: str, default: str) -> str:
    raw = source.get(key, default)
    value = str(raw if raw is not None else default).strip()
    return value or str(default)


def _optional_str_json(source: dict[str, Any], key: str) -> str | None:
    raw = source.get(key)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _dict_int_json(source: dict[str, Any], key: str) -> dict[str, int]:
    raw = source.get(key)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = int(v)
        except Exception:
            continue
    return out


def _list_str_json(source: dict[str, Any], key: str) -> list[str]:
    raw = source.get(key)
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        value = str(item or "").strip()
        if value:
            out.append(value)
    return out


def _mysql_from_env(default_db: str) -> MysqlConfig:
    load_env()
    return MysqlConfig(
        user=_str_env("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        host=_str_env("DB_HOST", "127.0.0.1"),
        port=_int_env("DB_PORT", 3307, min_value=1, max_value=65535),
        database=_str_env("DB_NAME", default_db),
    )


def db_config() -> MysqlConfig:
    return _mysql_from_env(default_db="mevzuat")


def db_worker_count() -> int:
    load_env()
    raw = _str_env("APP_WORKER_COUNT", "") or _str_env("WEB_CONCURRENCY", "")
    try:
        value = int(raw) if raw else 1
    except Exception:
        value = 1
    return max(1, min(64, int(value)))


def db_total_pool_size() -> int:
    load_env()
    return _int_env("DB_TOTAL_POOL_SIZE", 0, min_value=0, max_value=512)


def db_pool_size() -> int:
    load_env()
    total = db_total_pool_size()
    if total > 0:
        workers = db_worker_count()
        per_process = total // max(1, workers)
        if per_process <= 0:
            per_process = 1
        return max(1, min(64, int(per_process)))
    return _int_env("DB_POOL_SIZE", 10, min_value=1, max_value=64)


def redis_shutdown_flush_mode() -> str:
    load_env()
    mode = _str_env("REDIS_SHUTDOWN_FLUSH_MODE", "off").lower()
    if mode not in {"off", "flushdb", "flushall"}:
        return "off"
    return mode


def jwt_config() -> JwtConfig:
    load_env()
    app_cfg = load_json_config("api_config.json")
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return JwtConfig(
        jwt_mode=_str_json(app_cfg, "jwt_mode", "hs256").lower(),
        jwt_secret=secret,
        jwt_alg=_str_env("JWT_ALG", "HS256"),
        jwt_kid=_optional_str_json(app_cfg, "jwt_kid"),
        jwt_private_key_path=_optional_str_json(app_cfg, "jwt_private_key_path"),
        jwt_public_key_path=_optional_str_json(app_cfg, "jwt_public_key_path"),
        jwt_issuer=_str_env("JWT_ISSUER", "mevzuat-agent"),
        access_ttl_seconds=_int_env("JWT_ACCESS_TTL_SECONDS", 900, min_value=60),
        refresh_ttl_seconds=_int_env("JWT_REFRESH_TTL_SECONDS", 30 * 24 * 3600, min_value=300),
        leeway_seconds=_int_env("JWT_LEEWAY_SECONDS", 30, min_value=0, max_value=300),
        refresh_reuse_grace_seconds=_int_env("JWT_REFRESH_REUSE_GRACE_SECONDS", 5, min_value=0, max_value=300),
    )


def app_config() -> AppConfig:
    cfg = load_json_config("api_config.json")
    return AppConfig(
        rate_limit_rps=_int_json(cfg, "rate_limit_rps", 50, min_value=1, max_value=1000),
        path_rate_limits_rpm=_dict_int_json(cfg, "path_rate_limits_rpm"),
        law_agent_max_turns=_int_json(cfg, "law_agent_max_turns", 99, min_value=1, max_value=200),
        cors_enabled=_bool_json(cfg, "cors_enabled", True),
        auth_dev_mode=_bool_json(cfg, "auth_dev_mode", False),
        auth_debug=_bool_json(cfg, "auth_debug", False),
        mail_verification_enabled=_bool_json(cfg, "mail_verification_enabled", False),
        sub_account_mail_verification=_bool_json(
            cfg,
            "sub_account_mail_verification",
            _bool_json(cfg, "mail_verification_enabled", False),
        ),
        jwt_secret_min_length=_int_json(cfg, "jwt_secret_min_length", 32, min_value=8, max_value=256),
        jwt_require_strong_secret=_bool_json(cfg, "jwt_require_strong_secret", False),
        trust_proxy=_bool_json(cfg, "trust_proxy", False),
        trusted_proxy_ips=_list_str_json(cfg, "trusted_proxy_ips"),
        allowed_http_origins=_list_str_json(cfg, "allowed_http_origins"),
        allowed_ws_origins=_list_str_json(cfg, "allowed_ws_origins"),
        password_reset_token_ttl_seconds=_int_json(
            cfg, "password_reset_token_ttl_seconds", 3600, min_value=300, max_value=86400
        ),
        password_reset_url_base=_str_json(cfg, "password_reset_url_base", "http://localhost:3000/reset-password"),
        support_sender_name=_str_json(cfg, "support_sender_name", "Yargucu Support"),
    )


def log_config() -> LogConfig:
    cfg = load_json_config("log_config.json")
    return LogConfig(
        log_level=_str_json(cfg, "log_level", "INFO").upper(),
        dev_mode=_bool_json(cfg, "dev_mode", False),
        request_logging_enabled=_bool_json(cfg, "request_logging_enabled", True),
        request_exception_stacktrace_enabled=_bool_json(cfg, "request_exception_stacktrace_enabled", False),
        dev_logging_enabled=_bool_json(cfg, "dev_logging_enabled", False),
        colorize_search_logs=_bool_json(cfg, "colorize_search_logs", False),
        auth_audit_logging_enabled=_bool_json(cfg, "auth_audit_logging_enabled", True),
        agent_audit_logging_enabled=_bool_json(cfg, "agent_audit_logging_enabled", False),
        agent_audit_max_chars=_int_json(cfg, "agent_audit_max_chars", 20000, min_value=1000, max_value=200000),
        libreoffice_logging_enabled=_bool_json(cfg, "libreoffice_logging_enabled", True),
        reportlab_logging_enabled=_bool_json(cfg, "reportlab_logging_enabled", True),
    )


def mail_config() -> MailConfig:
    load_env()
    app = app_config()
    return MailConfig(
        verification_enabled=bool(app.mail_verification_enabled),
        verification_api_key=_str_env("MAIL_VERIF_API_KEY", ""),
        mailtrap_api_key=_str_env("MAILTRAP_API_KEY", ""),
        sender_email=_str_env("MAILTRAP_SENDER_EMAIL", "noreply@mevzuat.local"),
        sender_name=_str_env("MAILTRAP_SENDER_NAME", "Mevzuat"),
        support_receiver_email=_str_env("SUPPORT_MAIL_RECEIVER", ""),
        support_sender_name=str(app.support_sender_name or "").strip() or "Yargucu Support",
    )


def credit_config() -> CreditConfig:
    load_env()
    default_rate = _float_env("CREDIT_EXCHANGE_RATE", 1.0, min_value=0.000001)
    student_rate = _float_env("STUDENT_CREDIT_EXCHANGE_RATE", default_rate, min_value=0.000001)
    return CreditConfig(
        default_exchange_rate=default_rate,
        student_exchange_rate=student_rate,
    )


def agent_config() -> AgentConfig:
    load_env()
    ai = load_json_config("ai_config.json")
    timeouts = load_json_config("timeout_config.json")
    max_history_items = _int_json(ai, "max_history_items", 30, min_value=1, max_value=500)
    return AgentConfig(
        base_model=_str_json(ai, "base_model", "gpt-5.2"),
        embedding_model=_str_json(ai, "mevzuat_embedding_model", "text-embedding-3-large"),
        embedding_model_name_filter=_str_json(ai, "mevzuat_embedding_model_name_filter", "text-embedding-3-large"),
        openai_http_timeout_seconds=_float_json(ai, "openai_http_timeout_seconds", 120.0, min_value=5.0, max_value=600.0),
        openai_http_max_connections=_int_json(ai, "openai_http_max_connections", 64, min_value=1, max_value=512),
        openai_http_max_keepalive_connections=_int_json(ai, "openai_http_max_keepalive_connections", 16, min_value=1, max_value=256),
        openai_http_max_retries=_int_json(ai, "openai_http_max_retries", 2, min_value=0, max_value=10),
        ictihat_embedding_model=_str_json(ai, "ictihat_embedding_model", "text-embedding-3-small"),
        ictihat_summarizer_model=_str_json(ai, "ictihat_summarizer_model", "gpt-5-nano"),
        ictihat_summarizer_reasoning_effort=_str_json(ai, "ictihat_summarizer_reasoning_effort", "minimal").lower(),
        ictihat_summarizer_token_threshold=_int_json(ai, "ictihat_summarizer_token_threshold", 5000, min_value=100, max_value=200000),
        ictihat_search_agent_summarizer_token_threshold=_int_json(
            ai,
            "ictihat_search_agent_summarizer_token_threshold",
            _int_json(ai, "ictihat_summarizer_token_threshold", 5000, min_value=100, max_value=200000),
            min_value=100,
            max_value=200000,
        ),
        ictihat_agent_summarize_for_agent_enabled=_bool_json(ai, "ictihat_agent_summarize_for_agent_enabled", True),
        redis_url=_str_env("REDIS_URL", "redis://localhost:6379/0"),
        max_history_items=max_history_items,
        memory_ttl_seconds=_int_json(ai, "memory_ttl_seconds", 7200, min_value=300, max_value=86400),
        max_history_tokens=_int_json(ai, "max_history_tokens", 50000, min_value=1000, max_value=500000),
        memory_summarizer_model=_str_json(ai, "memory_summarizer_model", "gpt-4.1-mini"),
        memory_raw_tail_items=_int_json(ai, "memory_raw_tail_items", 4, min_value=0, max_value=max_history_items),
        embedding_timeout_seconds=_float_json(timeouts, "embeddings_seconds", 10.0, min_value=1.0, max_value=120.0),
        summarizer_timeout_seconds=_float_json(timeouts, "summarizer_seconds", 20.0, min_value=1.0, max_value=180.0),
        search_agent_timeout_seconds=_float_json(timeouts, "search_agent_seconds", 30.0, min_value=1.0, max_value=300.0),
        ictihat_search_agent_model=_str_json(ai, "ictihat_search_agent_model", "gpt-5-mini"),
        ictihat_search_agent_top_k=_int_json(ai, "ictihat_search_agent_top_k", 5, min_value=1, max_value=100),
        ictihat_search_agent_max_turns=_int_json(ai, "ictihat_search_agent_max_turns", 50, min_value=2, max_value=100),
        ictihat_search_agent_debug=_bool_json(ai, "ictihat_search_agent_debug", False),
        ictihat_search_agent_default_reasoning_effort=_str_json(
            ai, "ictihat_search_agent_default_reasoning_effort", "medium"
        ).lower(),
        ictihat_api_search_agent_model=_str_json(ai, "ictihat_api_search_agent_model", "gpt-5-mini"),
        ictihat_api_search_agent_top_k=_int_json(ai, "ictihat_api_search_agent_top_k", 20, min_value=1, max_value=100),
        ictihat_api_search_agent_max_turns=_int_json(ai, "ictihat_api_search_agent_max_turns", 50, min_value=2, max_value=100),
        ictihat_api_search_agent_debug=_bool_json(ai, "ictihat_api_search_agent_debug", False),
        ictihat_api_search_agent_default_reasoning_effort=_str_json(
            ai, "ictihat_api_search_agent_default_reasoning_effort", "medium"
        ).lower(),
        elasticsearch_url=_str_env("ELASTICSEARCH_URL", ""),
        elasticsearch_username=_str_env("ELASTICSEARCH_USERNAME", ""),
        elasticsearch_password=_str_env("ELASTICSEARCH_PASSWORD", ""),
        elasticsearch_api_key=_str_env("ELASTICSEARCH_API_KEY", ""),
        elasticsearch_index_ictihat=_str_env("ELASTICSEARCH_INDEX_ICTIHAT", "ictihat"),
        elasticsearch_verify_certs=_bool_env("ELASTICSEARCH_VERIFY_CERTS", True),
        qdrant_url=_str_env("QDRANT_URL", ""),
        qdrant_api_key=_str_env("QDRANT_API_KEY", ""),
        qdrant_index_ictihat=_str_env("QDRANT_INDEX_ICTIHAT", "ictihat"),
    )


__all__ = [
    "AgentConfig",
    "AppConfig",
    "CreditConfig",
    "JwtConfig",
    "LogConfig",
    "MailConfig",
    "MysqlConfig",
    "agent_config",
    "app_config",
    "config_dir_name",
    "credit_config",
    "db_config",
    "db_pool_size",
    "jwt_config",
    "load_env",
    "log_config",
    "mail_config",
]
