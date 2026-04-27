import pytest
from unittest.mock import AsyncMock
from app.services.cluely.context_manager import ContextManager
from app.schemas.cluely import TranscriptEntry

SESSION_ID = "test-123"
TRANSCRIPT_KEY = f"cluely:session:{SESSION_ID}:transcript"
STATE_KEY = f"cluely:session:{SESSION_ID}:state"
TRANSCRIPT_TTL = 4 * 3600  # 14400 seconds


@pytest.mark.asyncio
async def test_push_transcript_stores_in_redis():
    redis = AsyncMock()
    redis.rpush = AsyncMock()
    redis.ltrim = AsyncMock()
    redis.expire = AsyncMock()
    cm = ContextManager(redis=redis, session_id=SESSION_ID)
    entry = TranscriptEntry(speaker="interviewer", text="Tell me about yourself.", seq=1)
    await cm.push_transcript(entry)
    redis.rpush.assert_called_once_with(TRANSCRIPT_KEY, entry.model_dump_json())
    redis.ltrim.assert_called_once_with(TRANSCRIPT_KEY, -20, -1)
    redis.expire.assert_called_once_with(TRANSCRIPT_KEY, TRANSCRIPT_TTL)


@pytest.mark.asyncio
async def test_get_window_returns_last_n():
    redis = AsyncMock()
    entries = [f'{{"speaker":"interviewer","text":"q{i}","seq":{i}}}' for i in range(15)]
    redis.lrange = AsyncMock(return_value=[e.encode() for e in entries[-10:]])
    cm = ContextManager(redis=redis, session_id=SESSION_ID)
    window = await cm.get_window(n=10)
    assert len(window) == 10


@pytest.mark.asyncio
async def test_set_state_calls_setex():
    redis = AsyncMock()
    redis.setex = AsyncMock()
    cm = ContextManager(redis=redis, session_id=SESSION_ID)
    await cm.set_state("active")
    redis.setex.assert_called_once_with(STATE_KEY, TRANSCRIPT_TTL, "active")


@pytest.mark.asyncio
async def test_get_state_returns_decoded_value():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"active")
    cm = ContextManager(redis=redis, session_id=SESSION_ID)
    result = await cm.get_state()
    assert result == "active"
    redis.get.assert_called_once_with(STATE_KEY)


@pytest.mark.asyncio
async def test_get_state_returns_none_when_missing():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    cm = ContextManager(redis=redis, session_id=SESSION_ID)
    result = await cm.get_state()
    assert result is None


@pytest.mark.asyncio
async def test_session_exists_returns_true_when_key_present():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=1)
    cm = ContextManager(redis=redis, session_id=SESSION_ID)
    result = await cm.session_exists()
    assert result is True
    redis.exists.assert_called_once_with(STATE_KEY)


@pytest.mark.asyncio
async def test_session_exists_returns_false_when_key_absent():
    redis = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    cm = ContextManager(redis=redis, session_id=SESSION_ID)
    result = await cm.session_exists()
    assert result is False
