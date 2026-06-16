from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis

from ..config import agent_config
from ..db import core_db


class AuthRepository:
    """
    Refresh token + auth state persistence.
    """
    _redis: aioredis.Redis | None = None

    @classmethod
    def _redis_client(cls) -> aioredis.Redis:
        if cls._redis is None:
            cls._redis = aioredis.Redis.from_url(agent_config().redis_url, decode_responses=True)
        return cls._redis

    @staticmethod
    def ensure_auth_user_state(*, user_id: int) -> None:
        try:
            with core_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT IGNORE INTO auth_user_state (user_id, token_version)
                    VALUES (%s, 1)
                    """,
                    (int(user_id),),
                )
                conn.commit()
        except Exception:
            return

    @staticmethod
    def get_token_version(*, user_id: int) -> int:
        row = None
        try:
            with core_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT token_version
                    FROM auth_user_state
                    WHERE user_id=%s
                    LIMIT 1
                    """,
                    (int(user_id),),
                )
                row = cur.fetchone()
        except Exception:
            row = None
        if row:
            try:
                return max(1, int(row[0]))
            except Exception:
                return 1
        AuthRepository.ensure_auth_user_state(user_id=int(user_id))
        return 1

    @staticmethod
    def get_token_version_and_store_refresh_jti(*, user_id: int, jti: str, expires_at: datetime) -> tuple[int, dict[str, int]]:
        token_version = 1
        timing = {
            "token_version_ms": 0,
            "refresh_store_ms": 0,
        }
        with core_db() as conn:
            cur = conn.cursor()
            t_ver0 = time.perf_counter()
            cur.execute(
                """
                INSERT IGNORE INTO auth_user_state (user_id, token_version)
                VALUES (%s, 1)
                """,
                (int(user_id),),
            )
            cur.execute(
                """
                SELECT token_version
                FROM auth_user_state
                WHERE user_id=%s
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cur.fetchone()
            try:
                token_version = max(1, int(row[0])) if row else 1
            except Exception:
                token_version = 1
            timing["token_version_ms"] = int((time.perf_counter() - t_ver0) * 1000)
            t_store0 = time.perf_counter()
            cur.execute(
                """
                INSERT INTO auth_refresh_tokens (user_id, jti, expires_at, revoked)
                VALUES (%s, %s, %s, 0)
                """,
                (int(user_id), str(jti), expires_at.replace(tzinfo=None)),
            )
            timing["refresh_store_ms"] = int((time.perf_counter() - t_store0) * 1000)
            conn.commit()
        return int(token_version), timing

    @staticmethod
    def bump_token_version(*, user_id: int) -> int:
        try:
            with core_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE auth_user_state
                    SET token_version = token_version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id=%s
                    """,
                    (int(user_id),),
                )
                updated = int(cur.rowcount or 0)
                if updated == 0:
                    cur.execute(
                        """
                        INSERT IGNORE INTO auth_user_state (user_id, token_version)
                        VALUES (%s, 1)
                        """,
                        (int(user_id),),
                    )
                    cur.execute(
                        """
                        UPDATE auth_user_state
                        SET token_version = token_version + 1, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id=%s
                        """,
                        (int(user_id),),
                    )
                conn.commit()
        except Exception:
            return 1
        return AuthRepository.get_token_version(user_id=int(user_id))

    @classmethod
    async def deny_access_jti(cls, *, jti: str, expires_at_ts: int) -> None:
        ttl = int(expires_at_ts) - int(time.time())
        if ttl <= 0:
            return
        try:
            await cls._redis_client().set(f"auth:access:deny:{jti}", "1", ex=int(ttl))
        except Exception:
            return

    @classmethod
    async def is_access_jti_denied(cls, *, jti: str) -> bool:
        try:
            out = await cls._redis_client().get(f"auth:access:deny:{jti}")
            return bool(out)
        except Exception:
            return False

    @staticmethod
    def revoke_password_reset_tokens_for_user(*, user_id: int) -> None:
        try:
            with core_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE auth_password_reset_tokens
                    SET used_at = COALESCE(used_at, CURRENT_TIMESTAMP)
                    WHERE user_id=%s AND used_at IS NULL
                    """,
                    (int(user_id),),
                )
                conn.commit()
        except Exception:
            return

    @staticmethod
    def store_password_reset_token(*, user_id: int, token_hash: str, expires_at: datetime, request_ip: str | None) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO auth_password_reset_tokens (user_id, token_hash, request_ip, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    int(user_id),
                    str(token_hash),
                    (str(request_ip).strip() if request_ip else None),
                    expires_at.replace(tzinfo=None),
                ),
            )
            conn.commit()

    @staticmethod
    def consume_password_reset_token(*, token_hash: str) -> Optional[dict]:
        try:
            with core_db() as conn:
                cur = conn.cursor(dictionary=True)
                cur.execute(
                    """
                    SELECT id, user_id, expires_at, used_at, request_ip, created_at
                    FROM auth_password_reset_tokens
                    WHERE token_hash=%s AND used_at IS NULL AND expires_at > UTC_TIMESTAMP()
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (str(token_hash),),
                )
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    """
                    UPDATE auth_password_reset_tokens
                    SET used_at = CURRENT_TIMESTAMP
                    WHERE id=%s AND used_at IS NULL
                    """,
                    (int(row["id"]),),
                )
                conn.commit()
                if int(cur.rowcount or 0) != 1:
                    return None
                return row
        except Exception:
            return None

    @staticmethod
    def store_refresh_jti(*, user_id: int, jti: str, expires_at: datetime) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO auth_refresh_tokens (user_id, jti, expires_at, revoked)
                VALUES (%s, %s, %s, 0)
                """,
                (int(user_id), jti, expires_at.replace(tzinfo=None)),
            )
            conn.commit()

    @staticmethod
    def is_refresh_jti_valid(*, jti: str) -> bool:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT revoked, expires_at
                FROM auth_refresh_tokens
                WHERE jti=%s
                """,
                (jti,),
            )
            row = cur.fetchone()
            if not row:
                return False
            revoked, expires_at = row[0], row[1]
            if int(revoked) == 1:
                return False
            # expires_at is naive datetime (server local); compare to now() naive in same timezone.
            from datetime import datetime as _dt

            if expires_at is not None and expires_at <= _dt.utcnow():
                return False
            return True

    @staticmethod
    def revoke_refresh_jti(*, jti: str) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE auth_refresh_tokens
                SET revoked=1, revoked_at=CURRENT_TIMESTAMP
                WHERE jti=%s
                """,
                (jti,),
            )
            conn.commit()

    @staticmethod
    def revoke_all_refresh_tokens_for_user(*, user_id: int) -> None:
        with core_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE auth_refresh_tokens
                SET revoked=1, revoked_at=CURRENT_TIMESTAMP
                WHERE user_id=%s AND revoked=0
                """,
                (int(user_id),),
            )
            conn.commit()

    @staticmethod
    def get_refresh_token_status(*, jti: str) -> Optional[dict]:
        with core_db() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                """
                SELECT user_id, revoked, expires_at, revoked_at
                FROM auth_refresh_tokens
                WHERE jti=%s
                LIMIT 1
                """,
                (jti,),
            )
            return cur.fetchone()


