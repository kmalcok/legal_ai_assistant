from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class MysqlConfig:
    user: str
    password: Optional[str]
    host: str
    port: int
    database: str


@dataclass(frozen=True)
class JwtConfig:
    jwt_mode: str
    jwt_secret: str
    jwt_alg: str
    jwt_kid: Optional[str]
    jwt_private_key_path: Optional[str]
    jwt_public_key_path: Optional[str]
    jwt_issuer: str
    access_ttl_seconds: int
    refresh_ttl_seconds: int
    leeway_seconds: int
    refresh_reuse_grace_seconds: int


@dataclass(frozen=True)
class AgentConfig:
    base_model: str
    embedding_model: str
    embedding_model_name_filter: str
    openai_http_timeout_seconds: float
    openai_http_max_connections: int
    openai_http_max_keepalive_connections: int
    openai_http_max_retries: int
    ictihat_embedding_model: str
    ictihat_summarizer_model: str
    ictihat_summarizer_reasoning_effort: str
    ictihat_summarizer_token_threshold: int
    ictihat_search_agent_summarizer_token_threshold: int
    ictihat_agent_summarize_for_agent_enabled: bool
    redis_url: str
    max_history_items: int
    memory_ttl_seconds: int
    max_history_tokens: int
    memory_summarizer_model: str
    memory_raw_tail_items: int
    embedding_timeout_seconds: float
    summarizer_timeout_seconds: float
    search_agent_timeout_seconds: float
    ictihat_search_agent_model: str
    ictihat_search_agent_top_k: int
    ictihat_search_agent_max_turns: int
    ictihat_search_agent_debug: bool
    ictihat_search_agent_default_reasoning_effort: str
    ictihat_api_search_agent_model: str
    ictihat_api_search_agent_top_k: int
    ictihat_api_search_agent_max_turns: int
    ictihat_api_search_agent_debug: bool
    ictihat_api_search_agent_default_reasoning_effort: str
    elasticsearch_url: str
    elasticsearch_username: str
    elasticsearch_password: str
    elasticsearch_api_key: str
    elasticsearch_index_ictihat: str
    elasticsearch_verify_certs: bool
    qdrant_url: str
    qdrant_api_key: str
    qdrant_index_ictihat: str


@dataclass(frozen=True)
class AppConfig:
    rate_limit_rps: int
    path_rate_limits_rpm: Dict[str, int]
    law_agent_max_turns: int
    cors_enabled: bool
    auth_dev_mode: bool
    auth_debug: bool
    mail_verification_enabled: bool
    sub_account_mail_verification: bool
    jwt_secret_min_length: int
    jwt_require_strong_secret: bool
    trust_proxy: bool
    trusted_proxy_ips: list[str]
    allowed_http_origins: list[str]
    allowed_ws_origins: list[str]
    password_reset_token_ttl_seconds: int
    password_reset_url_base: str
    support_sender_name: str


@dataclass(frozen=True)
class LogConfig:
    log_level: str
    dev_mode: bool
    request_logging_enabled: bool
    request_exception_stacktrace_enabled: bool
    dev_logging_enabled: bool
    colorize_search_logs: bool
    auth_audit_logging_enabled: bool
    agent_audit_logging_enabled: bool
    agent_audit_max_chars: int
    libreoffice_logging_enabled: bool
    reportlab_logging_enabled: bool


@dataclass(frozen=True)
class MailConfig:
    verification_enabled: bool
    verification_api_key: str
    mailtrap_api_key: str
    sender_email: str
    sender_name: str
    support_receiver_email: str
    support_sender_name: str


@dataclass(frozen=True)
class CreditConfig:
    default_exchange_rate: float
    student_exchange_rate: float
