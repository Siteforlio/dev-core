# backend/tests/services/test_startup_scrapers.py
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_scrape_weworkremotely_job_shape():
    """Jobs from WWR have required fields and correct source."""
    from app.services.job_hunter.startup_scrapers import scrape_weworkremotely

    rss_xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Acme Corp: Senior Python Developer</title>
        <link>https://weworkremotely.com/job/123</link>
        <description>We need a senior developer...</description>
        <category>Programming</category>
      </item>
    </channel></rss>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = rss_xml

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    result = await scrape_weworkremotely("developer", mock_client)
    assert len(result) >= 1
    job = result[0]
    assert job["source"] == "weworkremotely"
    assert job["remote"] is True
    assert "url" in job
    assert "title" in job
    assert job["company"] == "Acme Corp"
    assert job["title"] == "Senior Python Developer"


@pytest.mark.asyncio
async def test_scrape_weworkremotely_handles_error_gracefully():
    """Returns [] on HTTP error."""
    from app.services.job_hunter.startup_scrapers import scrape_weworkremotely
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("network error"))
    result = await scrape_weworkremotely("developer", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_zindi_handles_error_gracefully():
    """Returns [] on HTTP error."""
    from app.services.job_hunter.startup_scrapers import scrape_zindi
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))
    result = await scrape_zindi("data", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_zindi_returns_empty_on_non_200():
    """Returns [] on non-200 response."""
    from app.services.job_hunter.startup_scrapers import scrape_zindi
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    result = await scrape_zindi("data", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_startupdeals_africa_handles_error_gracefully():
    """Returns [] on HTTP error."""
    from app.services.job_hunter.startup_scrapers import scrape_startupdeals_africa
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))
    result = await scrape_startupdeals_africa("engineer", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_startupdeals_africa_returns_empty_on_non_200():
    """Returns [] on non-200 response."""
    from app.services.job_hunter.startup_scrapers import scrape_startupdeals_africa
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    result = await scrape_startupdeals_africa("engineer", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_all_startup_boards_includes_new_sources():
    """scrape_all_startup_boards calls all 6 scrapers (3 existing + 3 new)."""
    from app.services.job_hunter import startup_scrapers

    called = []

    async def fake_scraper(search_term, client):
        called.append(search_term)
        return []

    with patch.object(startup_scrapers, "scrape_remotive", fake_scraper), \
         patch.object(startup_scrapers, "scrape_remoteok", fake_scraper), \
         patch.object(startup_scrapers, "scrape_hn_who_is_hiring", fake_scraper), \
         patch.object(startup_scrapers, "scrape_weworkremotely", fake_scraper), \
         patch.object(startup_scrapers, "scrape_zindi", fake_scraper), \
         patch.object(startup_scrapers, "scrape_startupdeals_africa", fake_scraper):
        result = await startup_scrapers.scrape_all_startup_boards("engineer")

    assert len(called) == 6
    assert result == []


@pytest.mark.asyncio
async def test_scrape_all_startup_boards_aggregates_results():
    """Results from all 6 scrapers are concatenated."""
    from app.services.job_hunter import startup_scrapers

    fake_job = {
        "source": "weworkremotely", "title": "Dev", "company": "Acme",
        "location": "Remote", "location_country": None,
        "remote": True, "url": "http://x", "apply_url": "http://x",
        "description": "desc",
    }

    async def return_one(search_term, client):
        return [fake_job]

    async def return_empty(search_term, client):
        return []

    with patch.object(startup_scrapers, "scrape_remotive", return_one), \
         patch.object(startup_scrapers, "scrape_remoteok", return_empty), \
         patch.object(startup_scrapers, "scrape_hn_who_is_hiring", return_empty), \
         patch.object(startup_scrapers, "scrape_weworkremotely", return_one), \
         patch.object(startup_scrapers, "scrape_zindi", return_empty), \
         patch.object(startup_scrapers, "scrape_startupdeals_africa", return_empty):
        result = await startup_scrapers.scrape_all_startup_boards("engineer")

    assert len(result) == 2
