from __future__ import annotations

import os
import re
import threading
from contextvars import ContextVar
from typing import Mapping

OPENAI_KEY_ROTATION = {
    "ratios": {
        "OPENAI_API_KEY_1": 2,
        "OPENAI_API_KEY_2": 3,
    }
}

_OPENAI_KEY_ENV_RE = re.compile(r"^OPENAI_API_KEY_(\d+)$")
_CURRENT_OPENAI_KEY_NAME: ContextVar[str | None] = ContextVar("current_openai_key_name", default=None)


class OpenAIKeyRotator:
    def __init__(self, config: Mapping[str, object] | None = None) -> None:
        self._config = dict(config or OPENAI_KEY_ROTATION)
        self._lock = threading.Lock()
        self._cycle: tuple[str, ...] = ()
        self._index = 0
        self._signature: tuple[tuple[str, int], ...] = ()

    def _configured_ratios(self) -> list[tuple[str, int]]:
        raw = self._config.get("ratios")
        if not isinstance(raw, Mapping):
            return []
        pairs: list[tuple[str, int]] = []
        for env_name, weight in raw.items():
            name = str(env_name or "").strip()
            if not name:
                continue
            try:
                value = int(weight)
            except Exception:
                continue
            if value > 0:
                pairs.append((name, value))
        return pairs

    @staticmethod
    def _available_numbered_keys(env: Mapping[str, str]) -> list[str]:
        numbered_keys: list[tuple[int, str]] = []
        for key, value in env.items():
            match = _OPENAI_KEY_ENV_RE.match(str(key))
            if not match or not str(value or "").strip():
                continue
            numbered_keys.append((int(match.group(1)), str(key)))
        return [key for _, key in sorted(numbered_keys)]

    @classmethod
    def _fallback_ratios(cls, env: Mapping[str, str]) -> list[tuple[str, int]]:
        pairs: list[tuple[str, int]] = []
        for key in cls._available_numbered_keys(env):
            pairs.append((key, 1))
        if pairs:
            return pairs
        if str(env.get("OPENAI_API_KEY") or "").strip():
            return [("OPENAI_API_KEY", 1)]
        return []

    def _resolve_ratios(self, env: Mapping[str, str]) -> list[tuple[str, int]]:
        configured = []
        configured_names: set[str] = set()
        for env_name, weight in self._configured_ratios():
            if str(env.get(env_name) or "").strip():
                configured.append((env_name, weight))
                configured_names.add(env_name)
        if configured:
            for env_name in self._available_numbered_keys(env):
                if env_name not in configured_names:
                    configured.append((env_name, 1))
            return configured
        return self._fallback_ratios(env)

    @staticmethod
    def _expand_cycle(ratios: list[tuple[str, int]]) -> tuple[str, ...]:
        cycle: list[str] = []
        for env_name, weight in ratios:
            cycle.extend([env_name] * int(weight))
        return tuple(cycle)

    def _ensure_cycle(self, env: Mapping[str, str]) -> None:
        ratios = self._resolve_ratios(env)
        signature = tuple(ratios)
        if signature == self._signature and self._cycle:
            return
        self._cycle = self._expand_cycle(ratios)
        self._signature = signature
        self._index = 0

    def next_key_binding(self, env: Mapping[str, str] | None = None) -> tuple[str, str]:
        current_env = env or os.environ
        with self._lock:
            for _ in range(2):
                self._ensure_cycle(current_env)
                if not self._cycle:
                    break
                env_name = self._cycle[self._index % len(self._cycle)]
                self._index += 1
                api_key = str(current_env.get(env_name) or "").strip()
                if api_key:
                    _CURRENT_OPENAI_KEY_NAME.set(env_name)
                    return env_name, api_key
                self._cycle = ()
                self._signature = ()
                self._index = 0
        raise RuntimeError("openai_api_key_missing")


openai_key_rotator = OpenAIKeyRotator()


def get_next_openai_api_key(env: Mapping[str, str] | None = None) -> tuple[str, str]:
    return openai_key_rotator.next_key_binding(env)


def get_current_openai_key_name() -> str | None:
    return _CURRENT_OPENAI_KEY_NAME.get()