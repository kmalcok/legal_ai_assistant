from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict

from ..data.db_app_config_repository import AppConfigRepository


ACTIVE_USER_COUNT_PUBLIC_PATH = "/v1/public/active-user-count"
ACTIVE_USER_COUNT_PUBLIC_RATE_LIMIT_RPM = 60
ACTIVE_USER_COUNT_MIN_INCREMENT = 1
ACTIVE_USER_COUNT_MAX_INCREMENT = 5
ACTIVE_USER_COUNT_BASE_INTERVAL_SECONDS = 60 * 60
ACTIVE_USER_COUNT_JITTER_SECONDS = 15 * 60
ACTIVE_USER_COUNT_POLL_INTERVAL_SECONDS = 60


class PublicStatsService:
    def get_active_user_count_payload(self) -> Dict[str, Any]:
        current = AppConfigRepository.get_active_user_count()
        return {
            "active_user_count": int(current.get("value") or 0),
            "updated_at": current.get("updated_at"),
        }

    @staticmethod
    def next_increment_amount() -> int:
        return random.randint(ACTIVE_USER_COUNT_MIN_INCREMENT, ACTIVE_USER_COUNT_MAX_INCREMENT)

    @staticmethod
    def next_delay_seconds() -> int:
        return ACTIVE_USER_COUNT_BASE_INTERVAL_SECONDS + random.randint(
            -ACTIVE_USER_COUNT_JITTER_SECONDS,
            ACTIVE_USER_COUNT_JITTER_SECONDS,
        )

    async def run_active_user_count_updater(self, *, stop_event: asyncio.Event) -> None:
        logger = logging.getLogger("mevzuat")
        while not stop_event.is_set():
            increment_by = self.next_increment_amount()
            next_delay_seconds = self.next_delay_seconds()

            try:
                result = await asyncio.to_thread(
                    AppConfigRepository.process_active_user_count_tick,
                    now_ts=int(time.time()),
                    increment_by=int(increment_by),
                    next_delay_seconds=int(next_delay_seconds),
                )
            except asyncio.CancelledError:
                if stop_event.is_set():
                    break
                raise
            except Exception as exc:
                logger.info(
                    json.dumps(
                        {
                            "ts": int(time.time()),
                            "event": "active_user_count_tick_error",
                            "detail": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )
            else:
                status = str(result.get("status") or "")
                if status in {"scheduled", "incremented"}:
                    logger.info(
                        json.dumps(
                            {
                                "ts": int(time.time()),
                                "event": "active_user_count_tick",
                                **result,
                            },
                            ensure_ascii=False,
                        )
                    )

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=ACTIVE_USER_COUNT_POLL_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                if stop_event.is_set():
                    break
                raise
