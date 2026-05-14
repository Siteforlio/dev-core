from unittest.mock import AsyncMock, MagicMock, patch
from app.services.interview_engine import InterviewEngine


def _mock_persona_engine():
    pe = AsyncMock()
    pe.get_graph_context.return_value = {"company": "Google", "round_type": "behavioral", "sample_questions": []}
    pe.build.return_value = "Professional, direct, values conciseness."
    return pe


async def test_create_session_returns_session_with_questions():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_orchestrator = AsyncMock()
    mock_orchestrator.generate_questions.return_value = ["Q1?", "Q2?", "Q3?"]

    with patch("app.services.interview_engine.ContextAssembler") as MockCA:
        MockCA.return_value.assemble = AsyncMock(return_value={
            "knowledge_profile": {}, "jd_analysis": {},
            "graph_context": {}, "user_weak_dimensions": [],
        })
        engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
        engine._persona_engine = _mock_persona_engine()
        result = await engine.create_session("user1", "Google", "SWE", ["behavioral", "technical"])

    assert result["company"] == "Google"
    assert len(result["questions"]) == 3
    assert result["current_round"] == "behavioral"
    assert result["remaining_rounds"] == ["technical"]
    assert result["career_track"] == "technology"  # default value


async def test_submit_answer_stores_moment_and_grade():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_round = MagicMock(id="r1", type="behavioral")
    mock_session = MagicMock(company="Google", role="SWE")

    # round query, session query, count query (answers for this round)
    results = [
        MagicMock(**{"scalar_one_or_none.return_value": mock_round}),
        MagicMock(**{"scalar_one_or_none.return_value": mock_session}),
        MagicMock(**{"scalar.return_value": 1}),  # 1 answer → not last of 5
    ]
    mock_db.execute = AsyncMock(side_effect=results)

    mock_orchestrator = AsyncMock()
    mock_orchestrator.grade_answer.return_value = {
        "score": 8.0, "passed": True,
        "what_worked": "Good structure.",
        "what_was_missing": "No metrics.",
        "stronger_version": "Add quantified result."
    }

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    result = await engine.submit_answer("s1", "r1", "Tell me about yourself.", "I am a SWE.")

    assert result["passed"] is True
    assert result["score"] == 8.0
