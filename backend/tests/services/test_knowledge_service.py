# backend/tests/services/test_knowledge_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.knowledge_service import KnowledgeService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_profile_returns_profile(mock_db):
    fake_profile = MagicMock()
    fake_profile.profile = {
        "core_competencies": ["coding", "system design"],
        "skill_dimensions": ["domain_knowledge", "communication_clarity"],
    }
    # scalar_one_or_none() is a sync call on the SQLAlchemy result — use MagicMock
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=fake_profile)
    svc = KnowledgeService(db=mock_db)
    result = await svc.get_profile("technology", "mid_level", "skills_domain")
    assert result["core_competencies"] == ["coding", "system design"]


@pytest.mark.asyncio
async def test_get_profile_returns_fallback_when_missing(mock_db):
    fake_fallback = MagicMock()
    fake_fallback.profile = {"core_competencies": ["communication"], "skill_dimensions": ["communication_clarity"]}
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(side_effect=[None, fake_fallback])
    svc = KnowledgeService(db=mock_db)
    result = await svc.get_profile("technology", "mid_level", "panel_interview")
    assert result is not None


@pytest.mark.asyncio
async def test_get_profile_returns_none_when_no_fallback(mock_db):
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(side_effect=[None, None])
    svc = KnowledgeService(db=mock_db)
    result = await svc.get_profile("technology", "mid_level", "unknown_stage")
    assert result is None
