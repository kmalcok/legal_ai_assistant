"""
Calendar reminder background service.

Runs inside the FastAPI process (no separate worker / no compose change).
Every ~15 minutes it scans `calendar_events` for pending events that need
notifications and sends out the right kind of email:

  * 24h reminder — `due_date` equals tomorrow (server local date) and
    `notified_24h_at IS NULL`. Standard heads-up email.
  * 4h follow-up alarm — the event has a `due_time`, the full
    `due_date + due_time` is within the next ~4 hours from NOW(), and
    `notified_4h_at IS NULL`. Sent with an alarm-clock subject as a
    stronger last-mile nudge.

Each notification is tracked in its own column so the two don't suppress
each other; one event normally gets both.

If a send fails the row is intentionally NOT marked as notified so the
next cycle will retry. Once `due_date` (or the full datetime, for the 4h
case) is in the past the row won't match the query anymore so retries
naturally stop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List

from ..db import core_db
from ..services.mail_service import MailService


logger = logging.getLogger("mevzuat")


# How often we wake up to check for upcoming events.
# 15 minutes => worst case the user receives the email at most 15 min after
# the local clock crosses the "one day before" boundary.
_INTERVAL_SECONDS = 15 * 60

# How long to wait after process startup before the very first scan.
# Lets the app finish warm-up tasks and prevents a thundering-herd on cold start.
_INITIAL_DELAY_SECONDS = 30

# Cap per cycle to avoid runaway mail bursts if many events ever line up.
_MAX_PER_CYCLE = 200


def _try_alter(conn, statement: str, fallback_statement: str | None = None) -> None:
    """
    Run an idempotent ALTER. If `IF NOT EXISTS` isn't supported by the
    server/connector we fall back to the unconditional form and swallow the
    duplicate-column / duplicate-key error.
    """
    try:
        cur = conn.cursor()
        cur.execute(statement)
        conn.commit()
        return
    except Exception:
        pass
    if not fallback_statement:
        return
    try:
        cur2 = conn.cursor()
        cur2.execute(fallback_statement)
        conn.commit()
    except Exception:
        # Already exists or another harmless conflict.
        pass


def ensure_notification_column() -> None:
    """
    Idempotently add the notification tracking columns and indexes to an
    existing `calendar_events` table. Safe to call on every startup. New
    installs that create the table via CORE_TABLE_DDL already include the
    columns; this only matters for databases that pre-date them.

    Currently ensures:
      * `notified_24h_at` + `idx_calevt_due_notif`
      * `notified_4h_at`  + `idx_calevt_due_notif4h`
    """
    try:
        with core_db() as conn:
            # 24h column + index
            _try_alter(
                conn,
                "ALTER TABLE `calendar_events` "
                "ADD COLUMN IF NOT EXISTS `notified_24h_at` datetime DEFAULT NULL AFTER `color`",
                "ALTER TABLE `calendar_events` ADD COLUMN `notified_24h_at` datetime DEFAULT NULL",
            )
            _try_alter(
                conn,
                "ALTER TABLE `calendar_events` "
                "ADD KEY IF NOT EXISTS `idx_calevt_due_notif` (`due_date`,`notified_24h_at`)",
                "ALTER TABLE `calendar_events` "
                "ADD KEY `idx_calevt_due_notif` (`due_date`,`notified_24h_at`)",
            )

            # 4h follow-up column + index
            _try_alter(
                conn,
                "ALTER TABLE `calendar_events` "
                "ADD COLUMN IF NOT EXISTS `notified_4h_at` datetime DEFAULT NULL AFTER `notified_24h_at`",
                "ALTER TABLE `calendar_events` ADD COLUMN `notified_4h_at` datetime DEFAULT NULL",
            )
            _try_alter(
                conn,
                "ALTER TABLE `calendar_events` "
                "ADD KEY IF NOT EXISTS `idx_calevt_due_notif4h` (`due_date`,`notified_4h_at`)",
                "ALTER TABLE `calendar_events` "
                "ADD KEY `idx_calevt_due_notif4h` (`due_date`,`notified_4h_at`)",
            )
    except Exception as exc:
        logger.info(
            json.dumps(
                {
                    "ts": int(time.time()),
                    "event": "calendar_reminder_ensure_column_error",
                    "detail": str(exc),
                },
                ensure_ascii=False,
            )
        )


def _fetch_due_tomorrow_unnotified(limit: int = _MAX_PER_CYCLE) -> List[Dict[str, Any]]:
    """
    Pull pending events whose due_date is exactly tomorrow (server CURDATE()+1)
    and that have not yet been emailed, joined with the user's email/name.
    """
    with core_db() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ce.event_id, ce.user_id, ce.title, ce.note,
                   ce.due_date, ce.due_time, ce.petition_id, ce.chat_id,
                   u.email AS user_email,
                   u.full_name AS user_full_name,
                   u.username AS user_username
            FROM calendar_events ce
            JOIN users u ON u.user_id = ce.user_id
            WHERE ce.status = 'pending'
              AND ce.notified_24h_at IS NULL
              AND ce.due_date = DATE_ADD(CURDATE(), INTERVAL 1 DAY)
              AND u.email IS NOT NULL
              AND u.email <> ''
            ORDER BY ce.due_date ASC, ce.due_time ASC, ce.event_id ASC
            LIMIT %s
            """,
            (int(limit),),
        )
        return list(cur.fetchall() or [])


def _mark_notified(event_id: int) -> None:
    with core_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE calendar_events SET notified_24h_at = NOW() WHERE event_id = %s",
            (int(event_id),),
        )
        conn.commit()


# How far ahead the 4h "alarm" follow-up looks. Kept slightly generous so that
# the 15-minute scanner can't miss the boundary if it's a bit late on a cycle.
_ALARM_WINDOW_HOURS = 4


def _fetch_due_within_4h_unnotified(limit: int = _MAX_PER_CYCLE) -> List[Dict[str, Any]]:
    """
    Pull pending events whose full due timestamp (`due_date` + `due_time`)
    falls inside the next ~4 hours from NOW(), are still in the future, and
    have not yet received the 4h alarm follow-up.

    Events without an explicit `due_time` are deliberately skipped — a 4h
    alarm only makes sense when the user pinned an actual time of day; an
    all-day event already got the 24h heads-up.
    """
    with core_db() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT ce.event_id, ce.user_id, ce.title, ce.note,
                   ce.due_date, ce.due_time, ce.petition_id, ce.chat_id,
                   u.email AS user_email,
                   u.full_name AS user_full_name,
                   u.username AS user_username
            FROM calendar_events ce
            JOIN users u ON u.user_id = ce.user_id
            WHERE ce.status = 'pending'
              AND ce.notified_4h_at IS NULL
              AND ce.due_time IS NOT NULL
              AND TIMESTAMP(ce.due_date, ce.due_time) > NOW()
              AND TIMESTAMP(ce.due_date, ce.due_time) <= DATE_ADD(NOW(), INTERVAL %s HOUR)
              AND u.email IS NOT NULL
              AND u.email <> ''
            ORDER BY ce.due_date ASC, ce.due_time ASC, ce.event_id ASC
            LIMIT %s
            """,
            (int(_ALARM_WINDOW_HOURS), int(limit)),
        )
        return list(cur.fetchall() or [])


def _mark_alarm_notified(event_id: int) -> None:
    with core_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE calendar_events SET notified_4h_at = NOW() WHERE event_id = %s",
            (int(event_id),),
        )
        conn.commit()


def _format_due_time(value: Any) -> str:
    """Normalize MariaDB TIME / timedelta / time / str into HH:MM."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:5] if len(value) >= 5 else value
    # datetime.time
    try:
        return value.strftime("%H:%M")  # type: ignore[no-any-return]
    except Exception:
        pass
    # timedelta (MySQL connector occasionally returns this)
    try:
        total = int(value.total_seconds())  # type: ignore[union-attr]
        hh = total // 3600
        mm = (total % 3600) // 60
        return f"{hh:02d}:{mm:02d}"
    except Exception:
        return str(value)


def _format_due_date(value: Any) -> str:
    if value is None:
        return ""
    try:
        return value.isoformat()[:10]  # type: ignore[no-any-return]
    except Exception:
        return str(value)[:10]


async def _dispatch_batch(
    rows: List[Dict[str, Any]],
    *,
    kind: str,
) -> Dict[str, int]:
    """
    Send the appropriate email for each row and mark it as notified on success.

    `kind` selects:
      * "reminder" → 24h heads-up via send_calendar_reminder_email + _mark_notified
      * "alarm"    → 4h follow-up via send_calendar_alarm_email   + _mark_alarm_notified
    """
    sent = 0
    failed = 0
    for row in rows:
        event_id = int(row.get("event_id") or 0)
        if not event_id:
            continue
        email = str(row.get("user_email") or "").strip()
        if not email:
            continue
        full_name = str(
            row.get("user_full_name") or row.get("user_username") or ""
        ).strip()
        title = str(row.get("title") or "Etkinlik").strip()
        note = str(row.get("note") or "").strip()
        due_date = _format_due_date(row.get("due_date"))
        due_time = _format_due_time(row.get("due_time"))

        try:
            if kind == "alarm":
                await MailService.send_calendar_alarm_email(
                    to_email=email,
                    to_name=full_name,
                    title=title,
                    due_date=due_date,
                    due_time=due_time,
                    note=note,
                    hours_remaining=_ALARM_WINDOW_HOURS,
                )
            else:
                await MailService.send_calendar_reminder_email(
                    to_email=email,
                    to_name=full_name,
                    title=title,
                    due_date=due_date,
                    due_time=due_time,
                    note=note,
                )
        except Exception as exc:
            failed += 1
            logger.info(
                json.dumps(
                    {
                        "ts": int(time.time()),
                        "event": "calendar_reminder_send_error",
                        "kind": kind,
                        "event_id": event_id,
                        "detail": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            # Intentionally do NOT mark as notified so the next cycle retries.
            continue

        try:
            if kind == "alarm":
                await asyncio.to_thread(_mark_alarm_notified, event_id)
            else:
                await asyncio.to_thread(_mark_notified, event_id)
            sent += 1
        except Exception as exc:
            # Mail went out but DB update failed. Log it; worst case the user
            # gets a duplicate reminder on the next cycle. Better than silently
            # losing the notification trail.
            logger.info(
                json.dumps(
                    {
                        "ts": int(time.time()),
                        "event": "calendar_reminder_mark_error",
                        "kind": kind,
                        "event_id": event_id,
                        "detail": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            sent += 1

    return {"sent": sent, "failed": failed}


async def _process_once() -> Dict[str, int]:
    """
    Single cycle: fetch pending events for both notification kinds (24h and
    4h follow-up) and dispatch them. Returns counters for logging.
    """
    counters = {
        "fetched": 0,
        "sent": 0,
        "failed": 0,
        "fetched_24h": 0,
        "fetched_4h": 0,
    }

    # 24h reminder pass
    try:
        rows_24h = await asyncio.to_thread(
            _fetch_due_tomorrow_unnotified, _MAX_PER_CYCLE
        )
    except Exception as exc:
        rows_24h = []
        logger.info(
            json.dumps(
                {
                    "ts": int(time.time()),
                    "event": "calendar_reminder_fetch_error",
                    "kind": "reminder",
                    "detail": str(exc),
                },
                ensure_ascii=False,
            )
        )

    if rows_24h:
        result = await _dispatch_batch(rows_24h, kind="reminder")
        counters["fetched_24h"] = len(rows_24h)
        counters["sent"] += result.get("sent", 0)
        counters["failed"] += result.get("failed", 0)

    # 4h follow-up alarm pass
    try:
        rows_4h = await asyncio.to_thread(
            _fetch_due_within_4h_unnotified, _MAX_PER_CYCLE
        )
    except Exception as exc:
        rows_4h = []
        logger.info(
            json.dumps(
                {
                    "ts": int(time.time()),
                    "event": "calendar_reminder_fetch_error",
                    "kind": "alarm",
                    "detail": str(exc),
                },
                ensure_ascii=False,
            )
        )

    if rows_4h:
        result = await _dispatch_batch(rows_4h, kind="alarm")
        counters["fetched_4h"] = len(rows_4h)
        counters["sent"] += result.get("sent", 0)
        counters["failed"] += result.get("failed", 0)

    counters["fetched"] = counters["fetched_24h"] + counters["fetched_4h"]
    return counters


async def run_reminder_loop(*, stop_event: asyncio.Event) -> None:
    """
    Long-running coroutine that drives the reminder scanner. Started as an
    asyncio task at app startup and cancelled / stopped on shutdown.
    """
    logger.info(
        json.dumps(
            {
                "ts": int(time.time()),
                "event": "calendar_reminder_loop_start",
                "interval_seconds": _INTERVAL_SECONDS,
            },
            ensure_ascii=False,
        )
    )

    try:
        await asyncio.to_thread(ensure_notification_column)
    except Exception as exc:
        logger.info(
            json.dumps(
                {
                    "ts": int(time.time()),
                    "event": "calendar_reminder_ensure_column_failed",
                    "detail": str(exc),
                },
                ensure_ascii=False,
            )
        )

    # Initial delay so we don't compete with startup migrations / warm caches.
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=_INITIAL_DELAY_SECONDS)
        return
    except asyncio.TimeoutError:
        pass

    while not stop_event.is_set():
        cycle_start = time.time()
        try:
            counters = await _process_once()
            if counters.get("fetched"):
                logger.info(
                    json.dumps(
                        {
                            "ts": int(time.time()),
                            "event": "calendar_reminder_cycle",
                            **counters,
                        },
                        ensure_ascii=False,
                    )
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.info(
                json.dumps(
                    {
                        "ts": int(time.time()),
                        "event": "calendar_reminder_cycle_error",
                        "detail": str(exc),
                    },
                    ensure_ascii=False,
                )
            )

        elapsed = time.time() - cycle_start
        wait_for = max(5.0, _INTERVAL_SECONDS - elapsed)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=wait_for)
            break
        except asyncio.TimeoutError:
            continue

    logger.info(
        json.dumps(
            {"ts": int(time.time()), "event": "calendar_reminder_loop_stop"},
            ensure_ascii=False,
        )
    )


# Convenience surface so `python -m src.calendar_events.reminder` works for
# one-off testing, though normal operation is the in-process FastAPI task.
if __name__ == "__main__":
    async def _main() -> None:
        stop = asyncio.Event()
        await run_reminder_loop(stop_event=stop)

    asyncio.run(_main())
