import pytest


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
