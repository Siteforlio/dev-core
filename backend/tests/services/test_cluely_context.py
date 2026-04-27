import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.cluely.context_manager import ContextManager
from app.schemas.cluely import TranscriptEntry

@pytest.mark.asyncio
async def test_push_transcript_stores_in_redis():
    redis = AsyncMock()
    redis.rpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.expire = AsyncMock()
    cm = ContextManager(redis=redis, session_id="test-123")
    entry = TranscriptEntry(speaker="interviewer", text="Tell me about yourself.", seq=1)
    await cm.push_transcript(entry)
    redis.rpush.assert_called_once()
    redis.ltrim.assert_called_once()

@pytest.mark.asyncio
async def test_get_window_returns_last_n():
    redis = AsyncMock()
    entries = [f'{{"speaker":"interviewer","text":"q{i}","seq":{i}}}' for i in range(15)]
    redis.lrange = AsyncMock(return_value=[e.encode() for e in entries[-10:]])
    cm = ContextManager(redis=redis, session_id="test-123")
    window = await cm.get_window(n=10)
    assert len(window) == 10
