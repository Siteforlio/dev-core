import pytest
from unittest.mock import AsyncMock, patch
import json


@pytest.mark.asyncio
async def test_set_and_get_returns_value():
    with patch("app.core.cache.get_redis") as mock_factory:
        mock_r = AsyncMock()
        mock_r.setex = AsyncMock()
        mock_r.get = AsyncMock(return_value='{"key": "value"}')
        mock_factory.return_value = mock_r

        from app.core.cache import cache_set, cache_get
        await cache_set("test:key", {"key": "value"}, ttl=60)
        result = await cache_get("test:key")
        assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_get_missing_key_returns_none():
    with patch("app.core.cache.get_redis") as mock_factory:
        mock_r = AsyncMock()
        mock_r.get = AsyncMock(return_value=None)
        mock_factory.return_value = mock_r

        from app.core.cache import cache_get
        result = await cache_get("missing:key")
        assert result is None


@pytest.mark.asyncio
async def test_cache_delete_calls_redis_delete():
    with patch("app.core.cache.get_redis") as mock_factory:
        mock_r = AsyncMock()
        mock_r.delete = AsyncMock()
        mock_factory.return_value = mock_r

        from app.core.cache import cache_delete
        await cache_delete("some:key")
        mock_r.delete.assert_called_once_with("some:key")
