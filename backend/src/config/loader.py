from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict


_JSON_LOCK = threading.Lock()
_JSON_CACHE: dict[str, Dict[str, Any]] = {}


def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def config_dir_name() -> str:
    raw = str(os.getenv("CONFIG_DIR", "config") or "config").strip()
    return raw or "config"


def config_dir() -> Path:
    root = backend_root().resolve()
    raw_name = config_dir_name()
    candidates = [
        (root / raw_name).resolve(),
        (root / "config" / raw_name).resolve(),
    ]
    for target in candidates:
        try:
            target.relative_to(root)
        except Exception:
            continue
        if target.exists() and target.is_dir():
            return target

    target = candidates[0]
    try:
        target.relative_to(root)
    except Exception as exc:
        raise RuntimeError(f"config_dir_invalid:{target}") from exc
    return target


def load_json_config(filename: str) -> Dict[str, Any]:
    name = str(filename or "").strip()
    if not name:
        raise RuntimeError("config_filename_missing")

    cache_key = f"{config_dir_name()}::{name}"
    cached = _JSON_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    path = config_dir() / name
    if not path.exists():
        raise RuntimeError(f"config_file_missing:{path}")

    with _JSON_LOCK:
        cached = _JSON_CACHE.get(cache_key)
        if cached is not None:
            return dict(cached)

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"config_file_invalid:{path}") from exc

        if not isinstance(raw, dict):
            raise RuntimeError(f"config_file_invalid:{path}")

        _JSON_CACHE[cache_key] = raw
        return dict(raw)
