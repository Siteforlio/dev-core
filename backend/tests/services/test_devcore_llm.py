import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.schemas.cluely import TranscriptEntry
from app.services.cluely.llm_service import LLMService


@pytest.fixture(autouse=True)
def mock_llm_clients():
    with patch('app.services.cluely.llm_service.genai') as mock_genai:
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        yield mock_genai, mock_model


@pytest.mark.asyncio
async def test_stream_suggestion_yields_deltas():
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
async def test_manual_ask_hints_uses_gemini(mock_llm_clients):
    _, mock_model = mock_llm_clients
    mock_response = MagicMock()
    mock_response.text = "Think about binary search approach."
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    svc = LLMService()
    result = await svc.manual_ask("How to find element in sorted array?", mode="hints", context={})
    mock_model.generate_content_async.assert_called_once()
    assert "binary search" in result.lower()


@pytest.mark.asyncio
async def test_manual_ask_solve_uses_gemini(mock_llm_clients):
    _, mock_model = mock_llm_clients
    mock_response = MagicMock()
    mock_response.text = "def binary_search(arr, target): ..."
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    svc = LLMService()
    result = await svc.manual_ask("Implement binary search", mode="solve", context={})
    mock_model.generate_content_async.assert_called_once()
    # prompt should ask for complete solution
    call_args = mock_model.generate_content_async.call_args[0][0]
    assert "complete" in call_args.lower() or "solution" in call_args.lower()


@pytest.mark.asyncio
async def test_manual_ask_ultra_uses_claude():
    svc = LLMService()
    with patch.object(svc, '_ask_claude', new_callable=AsyncMock, return_value="Deep analysis here.") as mock_c:
        result = await svc.manual_ask("Explain CAP theorem deeply", mode="ultra", context={})
    mock_c.assert_called_once()
    assert result == "Deep analysis here."


@pytest.mark.asyncio
async def test_manual_ask_injects_rag_context(mock_llm_clients):
    _, mock_model = mock_llm_clients
    mock_response = MagicMock()
    mock_response.text = "Use Redis as described in context."
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    svc = LLMService()
    await svc.manual_ask("What is Redis?", mode="hints", context={}, rag_chunks=["Redis is a cache."])
    prompt = mock_model.generate_content_async.call_args[0][0]
    assert "Redis is a cache." in prompt
