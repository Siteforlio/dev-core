import json
import redis.asyncio as redis
from app.core.config import settings

_redis: redis.Redis | None = None

SESSION_TTL = 14400  # 4 hours


async def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def set_session_state(session_id: str, state: dict, ttl: int = SESSION_TTL) -> None:
    r = await get_redis()
    await r.setex(
        f"interview:session:{session_id}:state",
        ttl,
        json.dumps(state),
    )


async def get_session_state(session_id: str) -> dict | None:
    r = await get_redis()
    raw = await r.get(f"interview:session:{session_id}:state")
    return json.loads(raw) if raw else None


async def delete_session_state(session_id: str) -> None:
    r = await get_redis()
    await r.delete(f"interview:session:{session_id}:state")


# ── Generic key/value cache helpers (used by JD parser, knowledge service, etc.) ──

async def cache_set(key: str, value: dict | list, ttl: int = 86400) -> None:
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value))


async def cache_get(key: str) -> dict | list | None:
    r = await get_redis()
    raw = await r.get(key)
    return json.loads(raw) if raw else None


async def cache_delete(key: str) -> None:
    r = await get_redis()
    await r.delete(key)
