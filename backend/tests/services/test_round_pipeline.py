from unittest.mock import AsyncMock, MagicMock, patch
from app.services.interview_engine import InterviewEngine


def _mock_persona_engine():
    pe = AsyncMock()
    pe.get_graph_context.return_value = {"company": "Google", "round_type": "technical", "sample_questions": []}
    pe.build.return_value = "Direct and technical."
    return pe


async def test_advance_to_next_round_creates_new_round():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    mock_session = MagicMock(id="s1", company="Google", role="SWE")
    results = [
        MagicMock(**{"scalar_one_or_none.return_value": mock_session}),
    ]
    mock_db.execute = AsyncMock(side_effect=results)

    mock_orchestrator = AsyncMock()
    mock_orchestrator.generate_questions.return_value = ["Q1?", "Q2?"]

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    engine._persona_engine = _mock_persona_engine()

    result = await engine.advance_to_next_round(session_id="s1", next_round_type="technical")

    assert result["current_round"] == "technical"
    assert len(result["questions"]) == 2


async def test_submit_answer_signals_round_complete_on_last_question():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_round = MagicMock(id="r1", type="behavioral", grade=None, passed=None)
    mock_session = MagicMock(company="Google", role="SWE")

    results = [
        MagicMock(**{"scalar_one_or_none.return_value": mock_round}),
        MagicMock(**{"scalar_one_or_none.return_value": mock_session}),
        # count query for questions answered
        MagicMock(**{"scalar.return_value": 4}),  # 4 prior answers → this is 5th (last of 5)
    ]
    mock_db.execute = AsyncMock(side_effect=results)

    mock_orchestrator = AsyncMock()
    mock_orchestrator.grade_answer.return_value = {
        "score": 8.0, "passed": True, "feedback": "Excellent."
    }

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    result = await engine.submit_answer(
        session_id="s1", round_id="r1",
        question="Q5?", answer="Great answer.",
        total_questions=5,
    )
    assert result["score"] == 8.0
    assert "round_complete" in result


async def test_submit_answer_flags_round_failed_on_low_score():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_round = MagicMock(id="r1", type="behavioral", grade=None, passed=None)
    mock_session = MagicMock(company="Google", role="SWE")

    results = [
        MagicMock(**{"scalar_one_or_none.return_value": mock_round}),
        MagicMock(**{"scalar_one_or_none.return_value": mock_session}),
        MagicMock(**{"scalar.return_value": 4}),
    ]
    mock_db.execute = AsyncMock(side_effect=results)

    mock_orchestrator = AsyncMock()
    mock_orchestrator.grade_answer.return_value = {
        "score": 2.0, "passed": False, "feedback": "Very poor answer."
    }

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    result = await engine.submit_answer(
        session_id="s1", round_id="r1",
        question="Q5?", answer="Bad.",
        total_questions=5,
    )
    assert result["round_complete"] is True
    assert result["round_passed"] is False


async def test_code_reaction_test():
    """react_to_code already exists — verify it returns a string."""
    from app.services.llm_orchestrator import LLMOrchestrator
    orchestrator = LLMOrchestrator()
    with patch.object(orchestrator, '_call_claude', new=AsyncMock(
        return_value="Looks good, consider edge cases for empty input."
    )):
        comment = await orchestrator.react_to_code(
            code_snapshot="def two_sum(nums, target):\n    pass",
            question="Implement two sum",
            company="Google",
        )
    assert isinstance(comment, str)
    assert len(comment) > 0
