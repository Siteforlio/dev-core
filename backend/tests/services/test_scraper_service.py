# backend/tests/services/test_scraper_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.job_hunter.scraper_service import ScraperService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

async def test_passes_work_type_filter(mock_db):
    service = ScraperService(mock_db)
    job = {"remote": True, "location_country": "US"}
    assert service.passes_work_type_filter(job, work_type="remote", user_country="GB", anywhere=False) is True

async def test_blocks_onsite_different_country(mock_db):
    service = ScraperService(mock_db)
    job = {"remote": False, "location_country": "US"}
    assert service.passes_work_type_filter(job, work_type="onsite", user_country="GB", anywhere=False) is False

async def test_allows_onsite_same_country(mock_db):
    service = ScraperService(mock_db)
    job = {"remote": False, "location_country": "GB"}
    assert service.passes_work_type_filter(job, work_type="onsite", user_country="GB", anywhere=False) is True

async def test_build_url_hash_is_deterministic(mock_db):
    service = ScraperService(mock_db)
    h1 = service.build_url_hash("u1", "Google", "Engineer", "https://apply.google.com/1")
    h2 = service.build_url_hash("u1", "Google", "Engineer", "https://apply.google.com/1")
    assert h1 == h2

async def test_build_url_hash_differs_by_user(mock_db):
    service = ScraperService(mock_db)
    h1 = service.build_url_hash("u1", "Google", "Engineer", "https://apply.google.com/1")
    h2 = service.build_url_hash("u2", "Google", "Engineer", "https://apply.google.com/1")
    assert h1 != h2

async def test_score_job_match_calls_haiku(mock_db):
    service = ScraperService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value="MATCH")):
        score = await service.score_job_match(
            title="Flutter Developer", description="Build mobile apps with Flutter",
            sub_categories=["Mobile Development"]
        )
    assert score == "MATCH"
