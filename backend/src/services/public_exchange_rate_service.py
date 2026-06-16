from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from forex_python.converter import CurrencyRates


USD_TRY_RATE_PUBLIC_PATH = "/v1/public/usd-try-rate"
USD_TRY_RATE_PUBLIC_RATE_LIMIT_RPM = 60
USD_TRY_RATE_CACHE_TTL_SECONDS = 30 * 60


class PublicExchangeRateService:
    def __init__(self, *, cache_ttl_seconds: int = USD_TRY_RATE_CACHE_TTL_SECONDS) -> None:
        self._client = CurrencyRates(force_decimal=False)
        self._cache_ttl_seconds = int(cache_ttl_seconds)
        self._lock = threading.Lock()
        self._cached_payload: Optional[Dict[str, Any]] = None
        self._cached_at_monotonic: float = 0.0

    def _get_cached_payload(self, *, allow_stale: bool = False) -> Optional[Dict[str, Any]]:
        with self._lock:
            payload = self._cached_payload
            cached_at = self._cached_at_monotonic

        if payload is None:
            return None

        if allow_stale:
            return dict(payload)

        age_seconds = time.monotonic() - cached_at
        if age_seconds <= self._cache_ttl_seconds:
            return dict(payload)
        return None

    def _set_cached_payload(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._cached_payload = dict(payload)
            self._cached_at_monotonic = time.monotonic()

    def get_usd_try_rate_payload(self) -> Dict[str, Any]:
        cached = self._get_cached_payload()
        if cached is not None:
            return {**cached, "stale": False}

        try:
            rate = float(self._client.get_rate("USD", "TRY"))
        except Exception:
            stale_payload = self._get_cached_payload(allow_stale=True)
            if stale_payload is not None:
                return {**stale_payload, "stale": True}
            raise

        payload = {
            "base_currency": "USD",
            "quote_currency": "TRY",
            "rate": float(rate),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._set_cached_payload(payload)
        return {**payload, "stale": False}
