import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.bridge_service import BridgeService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    return db

async def test_get_interview_context_returns_structured_dict(mock_db):
    mock_application = MagicMock(id="app-1")
    mock_listing = MagicMock(company="Stripe", title="Backend Engineer")
    mock_row = (mock_application, mock_listing)
    mock_db.execute.return_value.first = MagicMock(return_value=mock_row)
    with patch("app.services.job_hunter.bridge_service.PersonaEngine") as MockEngine:
        mock_engine = MockEngine.return_value
        mock_engine.get_context = AsyncMock(return_value={
            "managers": [{"name": "John", "title": "VP Eng", "traits": ["direct"]}],
            "round_patterns": {"rounds": ["HR", "Technical"]},
            "persona_string": "John is direct and values clarity.",
        })
        service = BridgeService(mock_db)  # constructed inside patch so PersonaEngine is mocked
        result = await service.get_interview_context("app-1")
    assert "managers" in result
    assert "persona_string" in result
    assert result["company"] == "Stripe"

async def test_get_interview_context_returns_empty_when_not_found(mock_db):
    service = BridgeService(mock_db)
    mock_db.execute.return_value.first = MagicMock(return_value=None)
    with patch("app.services.job_hunter.bridge_service.PersonaEngine"):
        result = await service.get_interview_context("nonexistent-id")
    assert result == {}
