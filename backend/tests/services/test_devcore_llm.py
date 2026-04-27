import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.schemas.cluely import TranscriptEntry


@pytest.fixture(autouse=True)
def mock_llm_clients():
    with patch('google.generativeai.configure'), \
         patch('google.generativeai.GenerativeModel') as mock_gemini_cls, \
         patch('anthropic.AsyncAnthropic') as mock_anthropic_cls:
        mock_gemini_cls.return_value = MagicMock()
        mock_anthropic_cls.return_value = AsyncMock()
        yield


@pytest.mark.asyncio
async def test_stream_suggestion_yields_deltas():
    from app.services.cluely.llm_service import LLMService
    svc = LLMService()
    transcript = [TranscriptEntry(speaker="interviewer", text="Tell me about CAP theorem?", seq=1)]
    context = {"job_title": "Backend Engineer", "company": "Stripe", "resume_text": "", "jd_text": ""}
    chunks = ["Lead with", " distributed", " systems."]

    async def aiter(items):
        for item in items:
            yield item

    with patch.object(svc, '_stream_gemini', return_value=aiter(chunks)):
        deltas = []
        async for delta in svc.stream_suggestion(transcript=transcript, context=context, rag_chunks=[]):
            deltas.append(delta)
    assert "".join(deltas) == "Lead with distributed systems."


@pytest.mark.asyncio
async def test_manual_ask_hints_uses_claude():
    from app.services.cluely.llm_service import LLMService
    svc = LLMService()
    with patch.object(svc, '_ask_claude', new_callable=AsyncMock, return_value="Try binary search.") as mock_c:
        result = await svc.manual_ask("How to find element in sorted array?", mode="hints", context={})
    mock_c.assert_called_once()
    assert "binary search" in result.lower()
