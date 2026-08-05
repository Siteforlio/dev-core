import pytest
import app.core.cache as _cache
from app.services.cluely.context_manager import ContextManager
from app.schemas.cluely import TranscriptEntry

SESSION_ID = "test-123"
TRANSCRIPT_KEY = f"cluely:session:{SESSION_ID}:transcript"
STATE_KEY = f"cluely:session:{SESSION_ID}:state"


@pytest.fixture(autouse=True)
def clear_cache_state():
    _cache._store.clear()
    _cache._jti_store.clear()
    yield
    _cache._store.clear()
    _cache._jti_store.clear()


@pytest.mark.asyncio
async def test_push_transcript_stores_entry():
    """push_transcript appends a dict to the in-memory list."""
    cm = ContextManager(session_id=SESSION_ID)
    entry = TranscriptEntry(speaker="interviewer", text="Tell me about yourself.", seq=1)
    await cm.push_transcript(entry)
    result = await _cache.cache_get(TRANSCRIPT_KEY)
    assert result is not None
    assert len(result) == 1
    assert result[0]["speaker"] == "interviewer"
    assert result[0]["text"] == "Tell me about yourself."


@pytest.mark.asyncio
async def test_push_transcript_multiple_entries():
    """Subsequent pushes append rather than replace."""
    cm = ContextManager(session_id=SESSION_ID)
    for i in range(3):
        entry = TranscriptEntry(speaker="user", text=f"Message {i}.", seq=i)
        await cm.push_transcript(entry)
    result = await _cache.cache_get(TRANSCRIPT_KEY)
    assert result is not None
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_window_returns_last_n():
    """get_window returns the most recent n entries."""
    cm = ContextManager(session_id=SESSION_ID)
    for i in range(15):
        entry = TranscriptEntry(speaker="interviewer", text=f"q{i}", seq=i)
        await cm.push_transcript(entry)
    window = await cm.get_window(n=10)
    assert len(window) == 10
    assert window[-1].text == "q14"


@pytest.mark.asyncio
async def test_set_state_and_get_state():
    """set_state stores a value; get_state retrieves it."""
    cm = ContextManager(session_id=SESSION_ID)
    await cm.set_state("active")
    result = await cm.get_state()
    assert result == "active"


@pytest.mark.asyncio
async def test_get_state_returns_none_when_missing():
    """get_state returns None when no state has been set."""
    cm = ContextManager(session_id=SESSION_ID)
    result = await cm.get_state()
    assert result is None


@pytest.mark.asyncio
async def test_session_exists_returns_true_when_state_set():
    """session_exists returns True after set_state is called."""
    cm = ContextManager(session_id=SESSION_ID)
    await cm.set_state("active")
    result = await cm.session_exists()
    assert result is True


@pytest.mark.asyncio
async def test_session_exists_returns_false_when_no_state():
    """session_exists returns False when no state key exists."""
    cm = ContextManager(session_id=SESSION_ID)
    result = await cm.session_exists()
    assert result is False
