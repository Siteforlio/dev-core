# backend/tests/services/test_kenya_scrapers.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_scrape_all_kenya_boards_returns_list():
    """scrape_all_kenya_boards always returns a list."""
    from app.services.job_hunter import kenya_scrapers

    async def fake_scraper(search_term, client):
        return []

    with patch.object(kenya_scrapers, "scrape_fuzu", fake_scraper), \
         patch.object(kenya_scrapers, "scrape_brightermonday", fake_scraper), \
         patch.object(kenya_scrapers, "scrape_myjobmag", fake_scraper), \
         patch.object(kenya_scrapers, "scrape_kuhustle", fake_scraper), \
         patch.object(kenya_scrapers, "scrape_andela", fake_scraper), \
         patch.object(kenya_scrapers, "scrape_arc", fake_scraper):
        result = await kenya_scrapers.scrape_all_kenya_boards("engineer")

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_scrape_all_kenya_boards_tolerates_individual_failures():
    """If some scrapers return [] (simulating failure), overall call still succeeds."""
    from app.services.job_hunter import kenya_scrapers

    fake_job = {
        "source": "fuzu", "title": "Backend Engineer", "company": "Startup KE",
        "location": "Kenya", "location_country": "KE",
        "remote": False, "url": "https://fuzu.com/job/1", "apply_url": "https://fuzu.com/job/1",
        "description": "desc",
    }

    async def return_one(search_term, client):
        return [fake_job]

    async def return_empty(search_term, client):
        return []

    with patch.object(kenya_scrapers, "scrape_fuzu", return_one), \
         patch.object(kenya_scrapers, "scrape_brightermonday", return_empty), \
         patch.object(kenya_scrapers, "scrape_myjobmag", return_empty), \
         patch.object(kenya_scrapers, "scrape_kuhustle", return_empty), \
         patch.object(kenya_scrapers, "scrape_andela", return_empty), \
         patch.object(kenya_scrapers, "scrape_arc", return_empty):
        result = await kenya_scrapers.scrape_all_kenya_boards("engineer")

    assert len(result) == 1
    assert result[0]["source"] == "fuzu"


@pytest.mark.asyncio
async def test_scrape_all_kenya_boards_aggregates_results():
    """Results from all 6 scrapers are concatenated."""
    from app.services.job_hunter import kenya_scrapers

    def make_job(source):
        return {
            "source": source, "title": "Dev", "company": "Co",
            "location": "Kenya", "location_country": "KE",
            "remote": False, "url": "http://x", "apply_url": "http://x",
            "description": "desc",
        }

    async def return_one_fuzu(s, c): return [make_job("fuzu")]
    async def return_one_bm(s, c): return [make_job("brightermonday")]
    async def return_empty(s, c): return []

    with patch.object(kenya_scrapers, "scrape_fuzu", return_one_fuzu), \
         patch.object(kenya_scrapers, "scrape_brightermonday", return_one_bm), \
         patch.object(kenya_scrapers, "scrape_myjobmag", return_empty), \
         patch.object(kenya_scrapers, "scrape_kuhustle", return_empty), \
         patch.object(kenya_scrapers, "scrape_andela", return_empty), \
         patch.object(kenya_scrapers, "scrape_arc", return_empty):
        result = await kenya_scrapers.scrape_all_kenya_boards("developer")

    assert len(result) == 2
    sources = {j["source"] for j in result}
    assert "fuzu" in sources
    assert "brightermonday" in sources


@pytest.mark.asyncio
async def test_scrape_all_kenya_boards_publishes_counts():
    """publish_fn is called with per-board count message."""
    from app.services.job_hunter import kenya_scrapers

    published = []

    async def fake_publish(msg):
        published.append(msg)

    async def return_empty(s, c):
        return []

    with patch.object(kenya_scrapers, "scrape_fuzu", return_empty), \
         patch.object(kenya_scrapers, "scrape_brightermonday", return_empty), \
         patch.object(kenya_scrapers, "scrape_myjobmag", return_empty), \
         patch.object(kenya_scrapers, "scrape_kuhustle", return_empty), \
         patch.object(kenya_scrapers, "scrape_andela", return_empty), \
         patch.object(kenya_scrapers, "scrape_arc", return_empty):
        await kenya_scrapers.scrape_all_kenya_boards("engineer", publish_fn=fake_publish)

    assert len(published) == 2
    assert "Kenya" in published[0] or "kenya" in published[0].lower()
    assert "Fuzu" in published[1]
    assert "BrighterMonday" in published[1]


@pytest.mark.asyncio
async def test_kenya_job_shape():
    """Jobs returned from kenya boards have all required fields."""
    from app.services.job_hunter import kenya_scrapers

    fake_job = {
        "source": "myjobmag", "title": "Software Engineer", "company": "Tech KE",
        "location": "Kenya", "location_country": "KE",
        "remote": False, "url": "https://myjobmag.co.ke/job/1",
        "apply_url": "https://myjobmag.co.ke/job/1",
        "description": "Build APIs at a Nairobi startup.",
    }

    async def return_one(s, c): return [fake_job]
    async def return_empty(s, c): return []

    with patch.object(kenya_scrapers, "scrape_fuzu", return_empty), \
         patch.object(kenya_scrapers, "scrape_brightermonday", return_empty), \
         patch.object(kenya_scrapers, "scrape_myjobmag", return_one), \
         patch.object(kenya_scrapers, "scrape_kuhustle", return_empty), \
         patch.object(kenya_scrapers, "scrape_andela", return_empty), \
         patch.object(kenya_scrapers, "scrape_arc", return_empty):
        result = await kenya_scrapers.scrape_all_kenya_boards("engineer")

    assert len(result) == 1
    job = result[0]
    for field in ("source", "title", "company", "location", "location_country",
                  "remote", "url", "apply_url", "description"):
        assert field in job, f"Missing field: {field}"
    assert job["source"] == "myjobmag"
    assert job["location_country"] == "KE"


@pytest.mark.asyncio
async def test_scrape_myjobmag_returns_empty_on_non_200():
    """Returns [] on non-200 response."""
    from app.services.job_hunter.kenya_scrapers import scrape_myjobmag
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    result = await scrape_myjobmag("engineer", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_myjobmag_handles_error_gracefully():
    """Returns [] on network error."""
    from app.services.job_hunter.kenya_scrapers import scrape_myjobmag
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))
    result = await scrape_myjobmag("engineer", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_kuhustle_returns_empty_on_non_200():
    """Returns [] on non-200 response."""
    from app.services.job_hunter.kenya_scrapers import scrape_kuhustle
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    result = await scrape_kuhustle("engineer", mock_client)
    assert result == []


@pytest.mark.asyncio
async def test_scrape_kuhustle_handles_error_gracefully():
    """Returns [] on network error."""
    from app.services.job_hunter.kenya_scrapers import scrape_kuhustle
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("timeout"))
    result = await scrape_kuhustle("engineer", mock_client)
    assert result == []
