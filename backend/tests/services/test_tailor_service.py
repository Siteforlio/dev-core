# backend/tests/services/test_tailor_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.tailor_service import TailorService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db

async def test_extract_keywords_returns_list(mock_db):
    service = TailorService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value='["Python", "Django", "REST API"]')):
        keywords = await service.extract_keywords("We need a Python Django developer...")
    assert isinstance(keywords, list)
    assert "Python" in keywords

async def test_rewrite_bullets_calls_haiku(mock_db):
    service = TailorService(mock_db)
    bullets = ["Built web apps", "Managed databases"]
    keywords = ["Django", "PostgreSQL"]
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value='["Built Django web apps", "Managed PostgreSQL databases"]')):
        result = await service.rewrite_bullets(bullets, keywords)
    assert isinstance(result, list)
    assert len(result) == 2

async def test_infer_salary_returns_string(mock_db):
    service = TailorService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="$90,000 - $120,000")):
        salary = await service.infer_salary(seniority="mid", location="London", company="Startup")
    assert isinstance(salary, str)
    assert len(salary) > 0
