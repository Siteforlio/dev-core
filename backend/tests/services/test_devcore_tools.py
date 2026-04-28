import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.cluely.search_service import SearchService
from app.services.cluely.code_runner import CodeRunner
from app.core.exceptions import CodeRunnerError

@pytest.mark.asyncio
async def test_search_returns_snippets():
    svc = SearchService()
    with patch('app.services.cluely.search_service.settings') as mock_settings, \
         patch('app.services.cluely.search_service.httpx.AsyncClient') as mock_client:
        mock_settings.serp_api_key = "fake-serp-key"
        mock_resp = AsyncMock()
        mock_resp.json = MagicMock(return_value={"organic_results": [{"snippet": "Python is great"}]})
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        results = await svc.search("Python basics")
    assert "Python is great" in results[0]

@pytest.mark.asyncio
async def test_code_runner_returns_output():
    runner = CodeRunner()
    with patch('app.services.cluely.code_runner.settings') as mock_settings, \
         patch('app.services.cluely.code_runner.httpx.AsyncClient') as mock_client:
        mock_settings.judge0_api_key = "fake-judge0-key"
        mock_resp = AsyncMock()
        mock_resp.json = MagicMock(return_value={"stdout": "hello\n", "stderr": "", "status": {"id": 3}})
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        result = await runner.execute("print('hello')", language="python")
    assert result["output"] == "hello\n"

@pytest.mark.asyncio
async def test_code_runner_raises_on_quota():
    runner = CodeRunner()
    with patch('app.services.cluely.code_runner.settings') as mock_settings, \
         patch('app.services.cluely.code_runner.httpx.AsyncClient') as mock_client:
        mock_settings.judge0_api_key = "fake-judge0-key"
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("429", request=None, response=MagicMock(status_code=429)))
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        with pytest.raises(CodeRunnerError) as exc:
            await runner.execute("print(1)", language="python")
    assert exc.value.code == "CODE_RUNNER_QUOTA_EXCEEDED"

@pytest.mark.asyncio
async def test_filesystem_service_search_delegates_to_rag():
    from app.services.cluely.filesystem_service import FilesystemService
    from unittest.mock import AsyncMock, patch
    svc = FilesystemService()
    svc._rag.retrieve = AsyncMock(return_value=["chunk about Python"])
    results = await svc.search("Python", k=1)
    assert results == ["chunk about Python"]
    svc._rag.retrieve.assert_called_once_with("Python", k=1)
