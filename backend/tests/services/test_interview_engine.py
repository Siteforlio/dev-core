from unittest.mock import AsyncMock, MagicMock
from app.services.interview_engine import InterviewEngine


async def test_create_session_returns_session_with_questions():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_orchestrator = AsyncMock()
    mock_orchestrator.generate_questions.return_value = ["Q1?", "Q2?", "Q3?"]
    mock_orchestrator.build_persona.return_value = "Professional, direct, values conciseness."

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    result = await engine.create_session("user1", "Google", "SWE", ["behavioral", "technical"])

    assert result["company"] == "Google"
    assert len(result["questions"]) == 3
    assert result["current_round"] == "behavioral"
    assert result["remaining_rounds"] == ["technical"]


async def test_submit_answer_stores_moment_and_grade():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_round = MagicMock(id="r1", type="behavioral")
    mock_session = MagicMock(company="Google", role="SWE")

    # Return mock_round on first call, mock_session on second
    results = [
        MagicMock(**{"scalar_one_or_none.return_value": mock_round}),
        MagicMock(**{"scalar_one_or_none.return_value": mock_session}),
    ]
    mock_db.execute = AsyncMock(side_effect=results)

    mock_orchestrator = AsyncMock()
    mock_orchestrator.grade_answer.return_value = {"score": 8.0, "passed": True, "feedback": "Great answer."}

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    result = await engine.submit_answer("s1", "r1", "Tell me about yourself.", "I am a SWE.")

    assert result["passed"] is True
    assert result["score"] == 8.0
