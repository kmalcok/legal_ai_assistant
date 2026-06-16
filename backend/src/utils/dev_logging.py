from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict

from ..config import log_config


def log_level() -> str:
    return log_config().log_level


def is_dev() -> bool:
    return bool(log_config().dev_mode)


def _ensure_basic_logging_configured() -> None:
    root = logging.getLogger()
    if getattr(root, "handlers", None):
        return
    level = log_level()
    logging.basicConfig(level=getattr(logging, level, logging.INFO), format="%(message)s")


def _maybe_colorize_event(event: str, message: str) -> str:
    event_name = str(event or "").strip()
    search_prefixes = (
        "ictihat_search_",
        "ictihat_keyword_search_",
        "ictihat_api_semantic_search_",
        "ictihat_semantic_search_",
        "ictihat_db_search_",
    )
    if not event_name.startswith(search_prefixes):
        return message
    if not bool(log_config().colorize_search_logs):
        return message
    pink = "\x1b[95m"
    reset = "\x1b[0m"
    return pink + message + reset


def dev_print_yellow(*lines: str, logger_name: str = "dev.pretty") -> None:
    """
    Print a human-readable, yellow-colored block when LOG_MODE=dev.

    Uses ANSI escape codes (works in most modern terminals, including recent Windows).
    """
    cfg = log_config()
    if not (bool(cfg.dev_mode) and bool(cfg.dev_logging_enabled)):
        return
    try:
        _ensure_basic_logging_configured()
        yellow = "\x1b[33m"
        reset = "\x1b[0m"
        msg = "\n".join([str(x) for x in lines if x is not None])
        logging.getLogger(str(logger_name or "dev.pretty")).info(yellow + msg + reset)
    except Exception:
        return


def dev_log(logger_name: str, event: str, payload: Dict[str, Any]) -> None:
    """
    Emit a JSON log line only when LOG_MODE=dev.
    """
    cfg = log_config()
    if not (bool(cfg.dev_mode) and bool(cfg.dev_logging_enabled)):
        return
    try:
        # Ensure logs are visible even when running outside FastAPI.
        _ensure_basic_logging_configured()
        out = {"ts": int(time.time()), "event": str(event or ""), **(payload or {})}
        msg = json.dumps(out, ensure_ascii=False, default=str)
        logging.getLogger(logger_name).info(_maybe_colorize_event(str(event or ""), msg))
    except Exception:
        return


def dev_log_exception(logger_name: str, event: str, payload: Dict[str, Any], exc: Exception) -> None:
    cfg = log_config()
    if not (bool(cfg.dev_mode) and bool(cfg.dev_logging_enabled)):
        return
    try:
        _ensure_basic_logging_configured()
        out = {"ts": int(time.time()), "event": str(event or ""), **(payload or {})}
        logging.getLogger(logger_name).exception(json.dumps(out, ensure_ascii=False, default=str))
    except Exception:
        return

