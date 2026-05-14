from unittest.mock import AsyncMock, MagicMock, patch
from app.services.debrief_service import DebriefService


def _exec_scalars(rows):
    m = MagicMock()
    m.scalars.return_value.all.return_value = rows
    return m


def _exec_scalar_one(value):
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    return m


async def test_generate_debrief_returns_structured_report():
    mock_db = AsyncMock()
    mock_session = MagicMock(id="s1", company="Google", role="SWE")
    mock_round = MagicMock(id="r1", type="behavioral", grade=7.5, passed=True)
    mock_moment = MagicMock(
        question="Tell me about yourself.",
        answer="I am a SWE.",
        emotion_state="confident",
        round_id="r1",
    )

    mock_db.execute = AsyncMock(side_effect=[
        _exec_scalar_one(mock_session),
        _exec_scalars([mock_round]),
    ])

    service = DebriefService(db=mock_db)
    with patch.object(service, '_get_moments', new=AsyncMock(return_value=[mock_moment])):
        with patch.object(service, '_call_llm', new=AsyncMock(return_value={
            "overall_score": 7.5,
            "strengths": ["Clear communication"],
            "improvements": ["More specifics"],
            "recommendation": "Strong candidate",
        })):
            result = await service.generate(session_id="s1")

    assert "overall_score" in result
    assert "strengths" in result
    assert "rounds" in result


async def test_generate_debrief_includes_emotion_summary():
    mock_db = AsyncMock()
    mock_session = MagicMock(id="s1", company="Meta", role="PM")

    mock_db.execute = AsyncMock(side_effect=[
        _exec_scalar_one(mock_session),
        _exec_scalars([]),
    ])

    service = DebriefService(db=mock_db)
    with patch.object(service, '_get_moments', new=AsyncMock(return_value=[])):
        with patch.object(service, '_call_llm', new=AsyncMock(return_value={
            "overall_score": 5.0, "strengths": [], "improvements": [], "recommendation": "Needs work"
        })):
            result = await service.generate(session_id="s1")
    assert "emotion_summary" in result
