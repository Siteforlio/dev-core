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


# ── JWT refresh-token blacklist ────────────────────────────────────────────────

_jti_store: dict[str, float] = {}  # jti → expires_at (monotonic)
_jti_lock = asyncio.Lock()


async def blacklist_jti(jti: str, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    async with _jti_lock:
        _jti_store[jti] = time.monotonic() + ttl_seconds


async def is_jti_blacklisted(jti: str) -> bool:
    async with _jti_lock:
        expires_at = _jti_store.get(jti)
        if expires_at is None:
            return False
        if time.monotonic() > expires_at:
            del _jti_store[jti]
            return False
        return True


# ── Cleanup (called on shutdown — kept for API compat with main.py) ───────────

async def close_redis() -> None:
    """No-op: kept so main.py shutdown hook doesn't break."""
    pass
