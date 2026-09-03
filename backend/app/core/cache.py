"""
In-process cache — replaces Redis for single-user desktop app.

Session state and generic cache: TTL dict in-memory (fast, ephemeral).
JWT blacklist: in-memory with expiry (single-user — restart clears old tokens safely).
"""
import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── In-memory TTL store ────────────────────────────────────────────────────────
SESSION_TTL = 14400  # 4 hours (seconds)

_store: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
# Requires Python 3.10+: asyncio.Lock binds to event loop lazily (not at creation time)
_store_lock = asyncio.Lock()


async def _mem_set(key: str, value: Any, ttl: int) -> None:
    async with _store_lock:
        _store[key] = (value, time.monotonic() + ttl)


async def _mem_get(key: str) -> Any | None:
    async with _store_lock:
        entry = _store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del _store[key]
            return None
        return value


async def _mem_delete(key: str) -> None:
    async with _store_lock:
        _store.pop(key, None)


# ── Session state ──────────────────────────────────────────────────────────────

async def set_session_state(session_id: str, state: dict, ttl: int = SESSION_TTL) -> None:
    await _mem_set(f"interview:session:{session_id}:state", state, ttl)


async def get_session_state(session_id: str) -> dict | None:
    return await _mem_get(f"interview:session:{session_id}:state")


async def delete_session_state(session_id: str) -> None:
    await _mem_delete(f"interview:session:{session_id}:state")


# ── Generic key/value cache ────────────────────────────────────────────────────

async def cache_set(key: str, value: dict | list, ttl: int = 86400) -> None:
    await _mem_set(key, value, ttl)


async def cache_get(key: str) -> dict | list | None:
    return await _mem_get(key)


async def cache_delete(key: str) -> None:
    await _mem_delete(key)


async def list_append(key: str, item: Any, ttl: int = SESSION_TTL) -> None:
    """Atomically append an item to a cached list. Creates the list if absent."""
    async with _store_lock:
        entry = _store.get(key)
        if entry is None or time.monotonic() > entry[1]:
            lst: list = []
        else:
            lst = list(entry[0])  # copy to avoid mutating cached value
        lst.append(item)
        _store[key] = (lst, time.monotonic() + ttl)


# ── JWT refresh-token blacklist ────────────────────────────────────────────────

_jti_store: dict[str, float] = {}  # jti → expires_at (monotonic)
_jti_lock = asyncio.Lock()


def _blacklist_db_path() -> str:
    """Extract the SQLite file path from the database URL."""
    from app.core.config import settings as _settings
    url = _settings.database_url
    # sqlite+aiosqlite:///./devcore.db  → ./devcore.db
    # sqlite+aiosqlite:////abs/path/devcore.db → /abs/path/devcore.db
    if "///" in url:
        return url.split("///", 1)[1]
    return "devcore.db"


async def _ensure_blacklist_table() -> None:
    """Create the jwt_blacklist table if it doesn't exist. Called at startup."""
    import aiosqlite
    path = _blacklist_db_path()
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS jwt_blacklist (
                jti TEXT PRIMARY KEY,
                expires_at INTEGER NOT NULL
            )"""
        )
        await db.commit()


async def blacklist_jti(jti: str, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    expires_at = int(time.time()) + ttl_seconds
    # In-memory for fast lookups in current session
    async with _jti_lock:
        _jti_store[jti] = time.monotonic() + ttl_seconds
    # Persist to SQLite so the blacklist survives restarts
    try:
        import aiosqlite
        path = _blacklist_db_path()
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO jwt_blacklist (jti, expires_at) VALUES (?, ?)",
                (jti, expires_at),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist JTI blacklist entry to SQLite: %s", exc)


async def is_jti_blacklisted(jti: str) -> bool:
    # Fast in-memory check first (avoids DB hit for recently-revoked tokens)
    async with _jti_lock:
        mono_expires = _jti_store.get(jti)
        if mono_expires is not None:
            if time.monotonic() <= mono_expires:
                return True
            # Expired in memory — remove it
            del _jti_store[jti]

    # Fall through to SQLite — covers tokens revoked before this process started
    try:
        import aiosqlite
        path = _blacklist_db_path()
        async with aiosqlite.connect(path) as db:
            async with db.execute(
                "SELECT expires_at FROM jwt_blacklist WHERE jti = ?", (jti,)
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return False
        if int(time.time()) > row[0]:
            # Expired — clean it up lazily
            async with aiosqlite.connect(path) as db:
                await db.execute("DELETE FROM jwt_blacklist WHERE jti = ?", (jti,))
                await db.commit()
            return False
        # Warm up the memory cache for subsequent lookups
        remaining = row[0] - int(time.time())
        async with _jti_lock:
            _jti_store[jti] = time.monotonic() + remaining
        return True
    except Exception as exc:
        logger.warning("Failed to query JTI blacklist from SQLite: %s", exc)
        return False


# ── Cleanup (called on shutdown — kept for API compat with main.py) ───────────

async def close_redis() -> None:
    """No-op: kept so main.py shutdown hook doesn't break."""
    pass
