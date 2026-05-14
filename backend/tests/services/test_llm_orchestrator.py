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
    """Legacy test updated: passed is no longer returned by grade_answer (engine derives it)."""
    orchestrator = LLMOrchestrator()
    with patch.object(orchestrator, '_call_llm', new=AsyncMock(return_value=json.dumps({
        "score": 8.0,
        "what_worked": "Clear explanation.",
        "what_was_missing": "No metrics.",
        "stronger_version": "Add quantified result.",
        "follow_up": None,
        "factual_errors": [],
        "confidence_signal": "confident",
    }))):
        result = await orchestrator.grade_answer(
            question="Tell me about yourself.",
            answer="I am a software engineer with 5 years experience.",
            company="Google", role="SWE", round_type="behavioral"
        )
    assert result["score"] == 8.0
    assert "passed" not in result  # engine derives this from score >= PASS_THRESHOLD


@pytest.mark.asyncio
async def test_grade_answer_returns_three_part_feedback():
    orchestrator = LLMOrchestrator()
    with patch.object(orchestrator, '_call_llm', new=AsyncMock(return_value=json.dumps({
        "score": 7.5,
        "what_worked": "Good structure.",
        "what_was_missing": "No metrics.",
        "stronger_version": "Add: 'reduced cost by 30%.'",
        "follow_up": None,
        "factual_errors": [],
        "confidence_signal": "confident",
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


@pytest.mark.asyncio
async def test_grade_answer_includes_confidence_signal_and_follow_up():
    """grade_answer returns confidence_signal and follow_up fields"""
    orch = LLMOrchestrator()
    mock_response = {
        "score": 5.5,
        "what_worked": "Some structure.",
        "what_was_missing": "No metrics.",
        "stronger_version": "Add numbers.",
        "follow_up": "Can you give a specific example?",
        "factual_errors": [],
        "confidence_signal": "hesitant",
    }
    with patch.object(orch, '_call_llm', new=AsyncMock(return_value=json.dumps(mock_response))):
        result = await orch.grade_answer(
            question="Tell me about yourself.",
            answer="I am a developer.",
            company="Stripe",
            role="SWE",
            round_type="behavioral",
            time_taken_seconds=150,
            rewrite_count=2,
        )
    assert "confidence_signal" in result
    assert "follow_up" in result
    assert "passed" not in result  # engine derives passed — LLM does not return it
    assert result["confidence_signal"] == "hesitant"


@pytest.mark.asyncio
async def test_grade_answer_fast_response_timing_note():
    """time_taken_seconds < 10 triggers 'answered suspiciously fast' note"""
    orch = LLMOrchestrator()
    captured_prompt = {}

    async def mock_call_llm(prompt, think=False):
        captured_prompt['value'] = prompt
        return json.dumps({"score": 7.0, "what_worked": "x", "what_was_missing": "", "stronger_version": "", "follow_up": None, "factual_errors": [], "confidence_signal": "confident"})

    with patch.object(orch, '_call_llm', new=mock_call_llm):
        await orch.grade_answer("Q?", "A.", "Co", "Role", "behavioral", time_taken_seconds=5)

    assert "suspiciously fast" in captured_prompt['value']


@pytest.mark.asyncio
async def test_grade_answer_slow_response_timing_note():
    """time_taken_seconds > 180 triggers 'significantly over time' note"""
    orch = LLMOrchestrator()
    captured_prompt = {}

    async def mock_call_llm(prompt, think=False):
        captured_prompt['value'] = prompt
        return json.dumps({"score": 4.0, "what_worked": "", "what_was_missing": "slow", "stronger_version": "", "follow_up": None, "factual_errors": [], "confidence_signal": "uncertain"})

    with patch.object(orch, '_call_llm', new=mock_call_llm):
        await orch.grade_answer("Q?", "A.", "Co", "Role", "behavioral", time_taken_seconds=200)

    assert "significantly over time" in captured_prompt['value']


@pytest.mark.asyncio
async def test_grade_answer_rewrite_note():
    """rewrite_count >= 2 includes rewrite note in prompt"""
    orch = LLMOrchestrator()
    captured_prompt = {}

    async def mock_call_llm(prompt, think=False):
        captured_prompt['value'] = prompt
        return json.dumps({"score": 6.0, "what_worked": "x", "what_was_missing": "", "stronger_version": "", "follow_up": None, "factual_errors": [], "confidence_signal": "hesitant"})

    with patch.object(orch, '_call_llm', new=mock_call_llm):
        await orch.grade_answer("Q?", "A.", "Co", "Role", "behavioral", rewrite_count=3)

    assert "rewrote" in captured_prompt['value'].lower()


@pytest.mark.asyncio
async def test_evaluate_candidate_returns_hire_recommendation():
    """evaluate_candidate returns valid hire_recommendation enum value"""
    orch = LLMOrchestrator()
    mock_eval = {
        "hire_recommendation": "yes",
        "confidence_rating": "high",
        "overall_score": 7.5,
        "summary": "Strong candidate.",
        "strengths": ["clear communication"],
        "concerns": [],
        "time_management": "efficient",
    }
    moments = [
        {"question": "Q1?", "answer": "A1.", "score": 7.0, "time_taken_seconds": 60, "rewrite_count": 0, "is_followup": False},
    ]
    with patch.object(orch, '_call_llm', new=AsyncMock(return_value=json.dumps(mock_eval))):
        result = await orch.evaluate_candidate(
            company="Stripe", role="SWE", round_type="behavioral",
            moments=moments, time_budget_seconds=1800, actual_duration_seconds=900,
        )
    assert result["hire_recommendation"] in {"strong_yes", "yes", "borderline", "no", "strong_no"}
    assert "overall_score" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_react_to_rewrite_returns_string():
    """react_to_rewrite returns a non-empty string reaction"""
    orch = LLMOrchestrator()
    with patch.object(orch, '_call_llm', new=AsyncMock(return_value="Take your time, there's no rush.")):
        result = await orch.react_to_rewrite(company="Stripe", role="SWE", rewrite_count=2)
    assert isinstance(result, str)
    assert len(result) > 0
