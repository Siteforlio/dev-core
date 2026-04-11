import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from app.services.job_hunter.calendar_service import CalendarService

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db

async def test_extract_datetime_from_text(mock_db):
    service = CalendarService(mock_db)
    with patch.object(service, "_call_haiku", new=AsyncMock(return_value='{"date": "2026-04-20", "time": "14:00", "duration_minutes": 60}')):
        result = await service.extract_interview_datetime("We'd like to meet on April 20th at 2pm for 1 hour")
    assert result["date"] == "2026-04-20"
    assert result["time"] == "14:00"

async def test_create_event_stores_in_db(mock_db):
    service = CalendarService(mock_db)
    mock_db.execute = AsyncMock()
    with patch.object(service, "_push_caldav_event", new=AsyncMock(return_value="ext-id-123")):
        await service.create_interview_event(
            application_id="app-1", email_event_id="email-1",
            company="Stripe", role="Engineer",
            scheduled_at=datetime(2026, 4, 20, 14, 0),
            duration_minutes=60, caldav_creds={"url": "https://caldav.example.com"}
        )
    mock_db.add.assert_called_once()
