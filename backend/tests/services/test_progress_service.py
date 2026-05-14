# backend/tests/services/test_progress_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.progress_service import ProgressService


@pytest.mark.asyncio
async def test_write_scores_adds_rows():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    svc = ProgressService(db=mock_db)
    await svc.write_scores(
        user_id="u1", session_id="s1",
        career_track="technology", level="mid_level", stage="hr_interview",
        scores={"domain_knowledge": 8.0, "communication_clarity": 6.5},
    )
    assert mock_db.add.call_count == 2
    mock_db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_get_weak_dimensions_returns_lowest():
    mock_db = AsyncMock()
    rows = [
        MagicMock(skill_dimension="domain_knowledge", score=8.0),
        MagicMock(skill_dimension="communication_clarity", score=4.0),
        MagicMock(skill_dimension="executive_presence", score=3.5),
    ]
    mock_db.execute.return_value.scalars.return_value.all.return_value = rows
    svc = ProgressService(db=mock_db)
    weak = await svc.get_weak_dimensions("u1", "technology", n=2)
    assert "executive_presence" in weak
    assert "communication_clarity" in weak


@pytest.mark.asyncio
async def test_get_summary_returns_correct_structure():
    mock_db = AsyncMock()
    rows = [
        MagicMock(skill_dimension="domain_knowledge", score=8.0, session_id="s1"),
        MagicMock(skill_dimension="communication_clarity", score=6.0, session_id="s1"),
        MagicMock(skill_dimension="domain_knowledge", score=7.0, session_id="s2"),
    ]
    mock_db.execute.return_value.scalars.return_value.all.return_value = rows
    svc = ProgressService(db=mock_db)
    summary = await svc.get_summary("u1")
    assert summary["total_sessions"] == 2
    assert "domain_knowledge" in summary["dimensions"]
    assert summary["average_score"] > 0


@pytest.mark.asyncio
async def test_get_summary_empty_returns_zeros():
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    svc = ProgressService(db=mock_db)
    summary = await svc.get_summary("u1")
    assert summary == {"dimensions": {}, "total_sessions": 0, "average_score": 0.0}
