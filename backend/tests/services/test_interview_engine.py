from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
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
    mock_round = MagicMock(id="r1", type="behavioral", started_at=None, time_budget_seconds=1800)
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
        "score": 8.0,
        "what_worked": "Good structure.",
        "what_was_missing": "No metrics.",
        "stronger_version": "Add quantified result.",
        "follow_up": None,
        "factual_errors": [],
        "confidence_signal": "confident",
    }

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    result = await engine.submit_answer("s1", "r1", "Tell me about yourself.", "I am a SWE.")

    assert result["passed"] is True
    assert result["score"] == 8.0


import pytest


@pytest.mark.asyncio
async def test_submit_answer_follow_up_moments_not_counted_toward_total():
    """follow-up moments do not advance the prepared question counter"""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_round = MagicMock(
        id="r1", type="behavioral",
        started_at=datetime(2026, 1, 1, 0, 0, 0),  # far in the past is fine
        time_budget_seconds=1800,
    )
    mock_session = MagicMock(company="Google", role="SWE")

    # Simulate: 2 prepared answers already stored (count query for non-followup)
    results = [
        MagicMock(**{"scalar_one_or_none.return_value": mock_round}),
        MagicMock(**{"scalar_one_or_none.return_value": mock_session}),
        MagicMock(**{"scalar.return_value": 2}),   # 2 prepared answers so far (not last of 5)
    ]
    mock_db.execute = AsyncMock(side_effect=results)

    mock_orchestrator = AsyncMock()
    mock_orchestrator.grade_answer.return_value = {
        "score": 8.0,
        "what_worked": "Good.",
        "what_was_missing": "",
        "stronger_version": "",
        "follow_up": None,
        "factual_errors": [],
        "confidence_signal": "confident",
    }

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    from unittest.mock import patch
    with patch("app.services.interview_engine._utcnow", return_value=datetime(2026, 1, 1, 0, 5, 0)):
        result = await engine.submit_answer(
            "s1", "r1", "Q?", "A.", total_questions=5, is_followup=True
        )
    # Round should NOT be complete — follow-up does not count
    assert result["round_complete"] is False


@pytest.mark.asyncio
async def test_submit_answer_time_budget_forces_last():
    """expired time budget forces round completion regardless of question count"""
    from datetime import datetime, timedelta
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    # started_at 31 minutes ago, budget 1800s (30 min) → time_elapsed > budget
    started_at = datetime(2026, 1, 1, 0, 0, 0)
    mock_round = MagicMock(
        id="r1", type="behavioral",
        started_at=started_at,
        time_budget_seconds=1800,
    )
    mock_session = MagicMock(company="Google", role="SWE")

    results = [
        MagicMock(**{"scalar_one_or_none.return_value": mock_round}),
        MagicMock(**{"scalar_one_or_none.return_value": mock_session}),
        MagicMock(**{"scalar.return_value": 1}),   # only 1 prepared answer — normally not last
        MagicMock(**{"scalars.return_value.all.return_value": []}),  # moments for evaluate_candidate
    ]
    mock_db.execute = AsyncMock(side_effect=results)

    mock_orchestrator = AsyncMock()
    mock_orchestrator.grade_answer.return_value = {
        "score": 6.0, "what_worked": "ok", "what_was_missing": "", "stronger_version": "",
        "follow_up": None, "factual_errors": [], "confidence_signal": "confident",
    }
    mock_orchestrator.evaluate_candidate.return_value = {
        "hire_recommendation": "yes", "confidence_rating": "high", "overall_score": 6.0,
        "summary": "Good.", "strengths": [], "concerns": [], "time_management": "over_time",
    }

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)

    # Patch _utcnow to return 31 minutes after started_at
    from unittest.mock import patch
    with patch("app.services.interview_engine._utcnow", return_value=datetime(2026, 1, 1, 0, 31, 0)):
        result = await engine.submit_answer("s1", "r1", "Q?", "A.", total_questions=5)

    assert result["round_complete"] is True


@pytest.mark.asyncio
async def test_submit_answer_passed_derived_from_score():
    """passed is derived from score >= PASS_THRESHOLD, not from LLM"""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_round = MagicMock(
        id="r1", type="behavioral",
        started_at=datetime(2026, 1, 1, 0, 0, 0),
        time_budget_seconds=1800,
    )
    mock_session = MagicMock(company="Google", role="SWE")

    results = [
        MagicMock(**{"scalar_one_or_none.return_value": mock_round}),
        MagicMock(**{"scalar_one_or_none.return_value": mock_session}),
        MagicMock(**{"scalar.return_value": 1}),  # 1 prepared answer, not last
    ]
    mock_db.execute = AsyncMock(side_effect=results)

    mock_orchestrator = AsyncMock()
    # Score is 5.0 — at or above new PASS_THRESHOLD of 5.0
    mock_orchestrator.grade_answer.return_value = {
        "score": 5.0, "what_worked": "ok", "what_was_missing": "", "stronger_version": "",
        "follow_up": None, "factual_errors": [], "confidence_signal": "hesitant",
    }

    engine = InterviewEngine(db=mock_db, orchestrator=mock_orchestrator)
    from unittest.mock import patch
    with patch("app.services.interview_engine._utcnow", return_value=datetime(2026, 1, 1, 0, 5, 0)):
        result = await engine.submit_answer("s1", "r1", "Q?", "A.", total_questions=5)

    assert result["passed"] is True  # 5.0 >= PASS_THRESHOLD (5.0)
