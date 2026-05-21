import json
import logging
import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError, TimeoutError
from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None

SESSION_TTL = 14400  # 4 hours

_RETRY = Retry(ExponentialBackoff(cap=10, base=0.5), retries=3)


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry=_RETRY,
            retry_on_error=[ConnectionError, TimeoutError],
            health_check_interval=30,  # auto-reconnects on stale connections
        )
    return _redis


async def close_redis() -> None:
    """Call on application shutdown to cleanly close the connection pool."""
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None


async def _safe_redis_op(coro):
    """Execute a Redis coroutine, return None on any connection error."""
    try:
        return await coro
    except (ConnectionError, TimeoutError) as e:
        logger.warning("[cache] Redis unavailable: %s — resetting connection", e)
        global _redis
        _redis = None  # force reconnect on next call
        return None
    except Exception as e:
        logger.error("[cache] Redis error: %s", e)
        return None


async def set_session_state(session_id: str, state: dict, ttl: int = SESSION_TTL) -> None:
    r = await get_redis()
    await _safe_redis_op(
        r.setex(f"interview:session:{session_id}:state", ttl, json.dumps(state))
    )


async def get_session_state(session_id: str) -> dict | None:
    r = await get_redis()
    raw = await _safe_redis_op(r.get(f"interview:session:{session_id}:state"))
    return json.loads(raw) if raw else None


async def delete_session_state(session_id: str) -> None:
    r = await get_redis()
    await _safe_redis_op(r.delete(f"interview:session:{session_id}:state"))


# ── Generic key/value cache helpers ──

async def cache_set(key: str, value: dict | list, ttl: int = 86400) -> None:
    r = await get_redis()
    await _safe_redis_op(r.setex(key, ttl, json.dumps(value)))


async def cache_get(key: str) -> dict | list | None:
    r = await get_redis()
    raw = await _safe_redis_op(r.get(key))
    return json.loads(raw) if raw else None


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await _safe_redis_op(r.delete(key))


# ── JWT refresh-token blacklist ───────────────────────────────────────────────

_JTI_PREFIX = "jwt:blacklist:"


async def blacklist_jti(jti: str, ttl_seconds: int) -> None:
    """Mark a refresh-token JTI as used. Expires automatically after token's natural TTL."""
    if ttl_seconds <= 0:
        return
    r = await get_redis()
    await _safe_redis_op(r.setex(f"{_JTI_PREFIX}{jti}", ttl_seconds, "1"))


async def is_jti_blacklisted(jti: str) -> bool:
    """Return True if this JTI has already been used (replay detected)."""
    r = await get_redis()
    result = await _safe_redis_op(r.exists(f"{_JTI_PREFIX}{jti}"))
    # Redis unavailable → fail open (log warning, don't block auth)
    if result is None:
        logger.warning("[cache] Redis unavailable — skipping JTI blacklist check for %s", jti)
        return False
    return bool(result)
