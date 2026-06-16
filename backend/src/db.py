from __future__ import annotations

import contextlib
import threading
import time
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple, Union, cast

import mariadb

from .config import MysqlConfig, db_config, db_pool_size, db_total_pool_size, db_worker_count, load_env


def _to_connector_dict(cfg: MysqlConfig) -> Dict[str, Any]:
    return {
        "user": cfg.user,
        "password": cfg.password,
        "host": cfg.host,
        "port": cfg.port,
        "database": cfg.database,
    }

_Params = Optional[Union[Sequence[Any], Tuple[Any, ...]]]


def _convert_mysql_placeholders_to_qmark(sql: str, params: _Params) -> str:
    """
    MariaDB Python connector uses qmark paramstyle ('?').
    Our codebase historically uses mysql-connector style '%s'.

    To avoid touching every query, we convert '%s' -> '?' when params are provided.
    """
    if not params:
        return sql
    if not isinstance(sql, str):
        sql = str(sql)
    if "%s" not in sql:
        return sql
    return sql.replace("%s", "?")


class _CursorWrapper:
    def __init__(self, inner: Any, conn: Any):
        self._inner = inner
        self._conn = conn
        self._lastrowid_cache: Any = None

    def execute(self, operation: str, params: _Params = None) -> Any:
        op2 = _convert_mysql_placeholders_to_qmark(operation, params)
        out = self._inner.execute(op2, params)
        # Capture insert id right after execution (more reliable than reading later).
        try:
            v = getattr(self._inner, "lastrowid", None)
        except Exception:
            v = None
        if v is None:
            try:
                v = self._conn.insert_id()
            except Exception:
                v = None
        if not v:
            # Final fallback: SQL function (works on both MySQL/MariaDB).
            try:
                c2 = self._conn.cursor()
                c2.execute("SELECT LAST_INSERT_ID()")
                r = c2.fetchone()
                if r and r[0] is not None:
                    v = r[0]
            except Exception:
                pass
        if v is not None:
            self._lastrowid_cache = v
        return out

    def executemany(self, operation: str, seq_params: Sequence[Sequence[Any]]) -> Any:
        op2 = _convert_mysql_placeholders_to_qmark(operation, seq_params[0] if seq_params else None)
        out = self._inner.executemany(op2, seq_params)
        # executemany lastrowid semantics vary; still try to capture something.
        try:
            v = getattr(self._inner, "lastrowid", None)
            if v is None:
                v = self._conn.insert_id()
            if v is not None:
                self._lastrowid_cache = v
        except Exception:
            pass
        return out

    @property
    def lastrowid(self) -> Any:
        """
        mysql-connector exposes cursor.lastrowid reliably.
        mariadb connector sometimes returns None; fall back to conn.insert_id().
        """
        if self._lastrowid_cache is not None:
            return self._lastrowid_cache
        try:
            v = getattr(self._inner, "lastrowid", None)
            if v is not None:
                return v
        except Exception:
            pass
        try:
            v2 = self._conn.insert_id()
            if v2 is not None:
                return v2
        except Exception:
            pass
        try:
            c2 = self._conn.cursor()
            c2.execute("SELECT LAST_INSERT_ID()")
            r = c2.fetchone()
            return r[0] if r else None
        except Exception:
            return None

    def __getattr__(self, name: str) -> Any:  # pragma: no cover
        return getattr(self._inner, name)


class _ConnectionWrapper:
    def __init__(self, inner: Any):
        self._inner = inner

    def cursor(self, *args: Any, **kwargs: Any) -> _CursorWrapper:
        # Keep compatibility with existing calls like conn.cursor(dictionary=True)
        cur = self._inner.cursor(*args, **kwargs)
        return _CursorWrapper(cur, self._inner)

    def __getattr__(self, name: str) -> Any:  # pragma: no cover
        return getattr(self._inner, name)


_POOL_LOCK = threading.Lock()
_POOL: Any | None = None
_CONN_PING_LOCK = threading.Lock()
_CONN_LAST_PING_TS: dict[int, float] = {}
_DB_PING_INTERVAL_SECONDS = 30.0


def _pool_kwargs(cfg: MysqlConfig) -> Dict[str, Any]:
    kwargs = _to_connector_dict(cfg)
    kwargs.update(
        {
            "pool_name": "mevzuat_backend",
            "pool_size": int(db_pool_size()),
        }
    )
    return kwargs


def _get_pool() -> Any:
    global _POOL
    if _POOL is not None:
        return _POOL
    with _POOL_LOCK:
        if _POOL is None:
            load_env()
            _POOL = mariadb.ConnectionPool(**_pool_kwargs(db_config()))
    return _POOL


def db_pool_info() -> Dict[str, Any]:
    configured_pool_size = int(db_pool_size())
    worker_count = int(db_worker_count())
    total_pool_size = int(db_total_pool_size())
    return {
        "configured_pool_size": configured_pool_size,
        "worker_count": worker_count,
        "configured_total_pool_size": total_pool_size if total_pool_size > 0 else None,
        "estimated_total_connections": configured_pool_size * worker_count,
        "pool_initialized": bool(_POOL is not None),
    }


def close_db_pool() -> None:
    global _POOL
    with _POOL_LOCK:
        pool = _POOL
        _POOL = None
    if pool is None:
        return
    try:
        close = getattr(pool, "close", None)
        if callable(close):
            close()
    except Exception:
        pass


def _mark_connection_pinged(conn: Any) -> None:
    try:
        key = int(id(conn))
    except Exception:
        return
    with _CONN_PING_LOCK:
        _CONN_LAST_PING_TS[key] = float(time.monotonic())


def _should_ping_connection(conn: Any) -> bool:
    try:
        key = int(id(conn))
    except Exception:
        return True
    now = float(time.monotonic())
    with _CONN_PING_LOCK:
        last = _CONN_LAST_PING_TS.get(key)
        if last is None or (now - float(last)) >= float(_DB_PING_INTERVAL_SECONDS):
            _CONN_LAST_PING_TS[key] = now
            return True
        return False


def _get_live_connection() -> Any:
    last_error: Exception | None = None
    for attempt in range(2):
        conn = None
        try:
            conn = _get_pool().get_connection()
            if not bool(getattr(conn, "open", True)):
                conn.reconnect()
                _mark_connection_pinged(conn)
                return conn
            if _should_ping_connection(conn):
                conn.ping()
                _mark_connection_pinged(conn)
            return conn
        except Exception as exc:
            last_error = exc
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            if attempt == 0:
                close_db_pool()
                continue
    raise cast(Exception, last_error)


@contextlib.contextmanager
def db() -> Iterator[Any]:
    conn = _get_live_connection()
    w = _ConnectionWrapper(conn)
    try:
        yield w
    finally:
        try:
            w.close()
        except Exception:
            pass

@contextlib.contextmanager
def core_db() -> Iterator[Any]:
    # Backwards-compatible alias while repositories still import `core_db`.
    with db() as conn:
        yield conn


