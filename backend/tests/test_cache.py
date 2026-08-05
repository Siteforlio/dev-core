import pytest
import app.core.cache as _cache
import app.core.event_bus as _ebus


@pytest.fixture(autouse=True)
def clear_cache_state():
    _cache._store.clear()
    _cache._jti_store.clear()
    _ebus._subscribers.clear()
    yield
    _cache._store.clear()
    _cache._jti_store.clear()
    _ebus._subscribers.clear()


@pytest.mark.asyncio
async def test_session_state_set_get():
    from app.core.cache import set_session_state, get_session_state
    await set_session_state("sess-1", {"question": "tell me about yourself"})
    result = await get_session_state("sess-1")
    assert result == {"question": "tell me about yourself"}


@pytest.mark.asyncio
async def test_session_state_delete():
    from app.core.cache import set_session_state, get_session_state, delete_session_state
    await set_session_state("sess-2", {"x": 1})
    await delete_session_state("sess-2")
    result = await get_session_state("sess-2")
    assert result is None


@pytest.mark.asyncio
async def test_cache_generic():
    from app.core.cache import cache_set, cache_get, cache_delete
    await cache_set("my-key", {"foo": "bar"})
    result = await cache_get("my-key")
    assert result == {"foo": "bar"}
    await cache_delete("my-key")
    assert await cache_get("my-key") is None


@pytest.mark.asyncio
async def test_jti_blacklist():
    from app.core.cache import blacklist_jti, is_jti_blacklisted
    jti = "test-jti-123"
    assert not await is_jti_blacklisted(jti)
    await blacklist_jti(jti, ttl_seconds=3600)
    assert await is_jti_blacklisted(jti)


@pytest.mark.asyncio
async def test_cache_ttl_expiry():
    import asyncio
    from app.core.cache import cache_set, cache_get
    await cache_set("ttl-key", {"v": 1}, ttl=1)
    assert await cache_get("ttl-key") == {"v": 1}
    await asyncio.sleep(1.1)
    assert await cache_get("ttl-key") is None
