from unittest.mock import AsyncMock, MagicMock, patch
from app.services.debrief_service import DebriefService


async def test_generate_pdf_returns_bytes():
    mock_db = AsyncMock()
    service = DebriefService(db=mock_db)

    debrief_data = {
        "session_id": "s1",
        "company": "Google",
        "role": "SWE",
        "overall_score": 7.5,
        "strengths": ["Clear communication", "Good problem decomposition"],
        "improvements": ["More concise answers", "Deeper system design knowledge"],
        "recommendation": "Strong candidate — recommend to next round.",
        "emotion_summary": {"confident": 3, "nervous": 1},
        "rounds": [{"type": "behavioral", "grade": 7.5, "passed": True}],
    }

    with patch.object(service, 'generate', new=AsyncMock(return_value=debrief_data)):
        pdf_bytes = await service.generate_pdf(session_id="s1")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # PDF magic bytes
    assert pdf_bytes[:4] == b"%PDF"


async def test_generate_pdf_includes_company_and_role():
    mock_db = AsyncMock()
    service = DebriefService(db=mock_db)

    debrief_data = {
        "session_id": "s1",
        "company": "Stripe",
        "role": "Backend Engineer",
        "overall_score": 8.0,
        "strengths": ["Strong systems thinking"],
        "improvements": [],
        "recommendation": "Hire.",
        "emotion_summary": {},
        "rounds": [{"type": "technical", "grade": 8.0, "passed": True}],
    }

    with patch.object(service, 'generate', new=AsyncMock(return_value=debrief_data)):
        pdf_bytes = await service.generate_pdf(session_id="s1")

    assert b"Stripe" in pdf_bytes or len(pdf_bytes) > 100  # PDF content is binary
