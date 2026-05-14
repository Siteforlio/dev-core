import json
import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_orchestrator import LLMOrchestrator


async def test_generate_questions_returns_list():
    orchestrator = LLMOrchestrator()
    with patch.object(orchestrator, '_call_llm', new=AsyncMock(return_value=[
        "Tell me about yourself.",
        "Why do you want to work at Google?",
        "Describe a challenging technical problem you solved."
    ])):
        questions = await orchestrator.generate_questions(
            company="Google", role="Software Engineer", round_type="behavioral", graph_context=None
        )
    assert isinstance(questions, list)
    assert len(questions) >= 1
    assert all(isinstance(q, str) for q in questions)


async def test_generate_questions_with_no_graph_uses_llm_fallback():
    orchestrator = LLMOrchestrator()
    with patch.object(orchestrator, '_call_llm', new=AsyncMock(return_value=["Question 1"])) as mock_call:
        await orchestrator.generate_questions(
            company="Google", role="SWE", round_type="behavioral", graph_context=None
        )
        assert mock_call.call_args is not None


async def test_grade_answer_returns_score_and_feedback():
    orchestrator = LLMOrchestrator()
    with patch.object(orchestrator, '_call_llm', new=AsyncMock(return_value={
        "score": 7.5, "passed": True, "feedback": "Good answer, lacked specifics."
    })):
        result = await orchestrator.grade_answer(
            question="Tell me about yourself.",
            answer="I am a software engineer with 5 years experience.",
            company="Google", role="SWE", round_type="behavioral"
        )
    assert result["score"] == 7.5
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_grade_answer_returns_three_part_feedback():
    orchestrator = LLMOrchestrator()
    with patch.object(orchestrator, '_call_llm', new=AsyncMock(return_value=json.dumps({
        "score": 7.5,
        "passed": True,
        "what_worked": "Good structure.",
        "what_was_missing": "No metrics.",
        "stronger_version": "Add: 'reduced cost by 30%.'"
    }))):
        result = await orchestrator.grade_answer(
            question="Tell me about yourself.",
            answer="I am an engineer.",
            company="Google", role="SWE", round_type="behavioral"
        )
    assert "what_worked" in result
    assert "what_was_missing" in result
    assert "stronger_version" in result
    assert "feedback" not in result
