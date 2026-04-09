from unittest.mock import AsyncMock, patch


async def test_set_and_get_session_state():
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.get = AsyncMock(return_value='{"round": "behavioral", "company": "Google"}')

    with patch('app.core.cache.get_redis', new=AsyncMock(return_value=mock_redis)):
        from app.core.cache import set_session_state, get_session_state
        await set_session_state("s1", {"round": "behavioral", "company": "Google"})
        result = await get_session_state("s1")

    assert result == {"round": "behavioral", "company": "Google"}
    mock_redis.setex.assert_called_once()


async def test_get_session_state_returns_none_when_missing():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch('app.core.cache.get_redis', new=AsyncMock(return_value=mock_redis)):
        from app.core.cache import get_session_state
        result = await get_session_state("nonexistent")

    assert result is None


async def test_delete_session_state():
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock()

    with patch('app.core.cache.get_redis', new=AsyncMock(return_value=mock_redis)):
        from app.core.cache import delete_session_state
        await delete_session_state("s1")

    mock_redis.delete.assert_called_once()
