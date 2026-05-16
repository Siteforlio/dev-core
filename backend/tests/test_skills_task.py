"""Tests for skills_task LLM orchestrator methods and interview engine flow."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.llm_orchestrator import LLMOrchestrator
from app.services.interview_engine import InterviewEngine, ROUND_TIME_BUDGETS


# ── LLMOrchestrator unit tests ────────────────────────────────────────────────

class TestGenerateSkillsTask:
    @pytest.mark.asyncio
    async def test_tech_track_returns_code_input_type(self):
        orchestrator = LLMOrchestrator()
        task_json = json.dumps({
            "title": "Build a REST API",
            "brief": "Create a simple REST API using Ruby on Rails.",
            "input_type": "code",
            "language": "ruby",
            "starter_code": "# Your code here",
            "evaluation_criteria": ["correctness", "readability"],
            "time_hint": "60 minutes",
        })
        orchestrator._call_llm = AsyncMock(return_value=task_json)
        result = await orchestrator.generate_skills_task(
            company="Shopify",
            role="Backend Engineer",
            career_track="technology",
            level="mid_level",
        )
        assert result["input_type"] == "code"
        assert result["title"] == "Build a REST API"
        assert "evaluation_criteria" in result

    @pytest.mark.asyncio
    async def test_non_tech_track_returns_text_input_type(self):
        orchestrator = LLMOrchestrator()
        task_json = json.dumps({
            "title": "Financial Analysis Case",
            "brief": "Analyze the provided P&L statement.",
            "input_type": "text",
            "language": None,
            "starter_code": None,
            "evaluation_criteria": ["accuracy", "depth"],
            "time_hint": "45 minutes",
        })
        orchestrator._call_llm = AsyncMock(return_value=task_json)
        result = await orchestrator.generate_skills_task(
            company="Goldman",
            role="Analyst",
            career_track="finance_fintech",
            level="entry_junior",
        )
        assert result["input_type"] == "text"
        assert result["language"] is None

    @pytest.mark.asyncio
    async def test_malformed_llm_response_returns_fallback(self):
        orchestrator = LLMOrchestrator()
        orchestrator._call_llm = AsyncMock(return_value="not valid json at all")
        result = await orchestrator.generate_skills_task(
            company="X",
            role="Y",
            career_track="technology",
            level="senior",
        )
        assert result["title"] == "Skills Assessment"
        assert result["input_type"] == "code"  # technology → code
        assert "evaluation_criteria" in result


class TestGradeSkillsTask:
    @pytest.mark.asyncio
    async def test_grade_returns_score_and_followup(self):
        orchestrator = LLMOrchestrator()
        grade_json = json.dumps({
            "score": 7.5,
            "what_worked": "Good structure.",
            "what_was_missing": "Missing error handling.",
            "stronger_version": "Add try/except blocks.",
            "first_followup": "Why did you choose this approach?",
            "factual_errors": [],
            "confidence_signal": "confident",
        })
        orchestrator._call_llm = AsyncMock(return_value=grade_json)
        task_brief = {
            "title": "Test",
            "brief": "Build something",
            "evaluation_criteria": ["correctness"],
        }
        result = await orchestrator.grade_skills_task(
            task_brief=task_brief,
            submission="def foo(): pass",
            career_track="technology",
            role="Engineer",
            level="mid_level",
        )
        assert result["score"] == 7.5
        assert result["first_followup"] == "Why did you choose this approach?"
        assert result["confidence_signal"] == "confident"

    @pytest.mark.asyncio
    async def test_grade_fallback_on_bad_json(self):
        orchestrator = LLMOrchestrator()
        orchestrator._call_llm = AsyncMock(return_value="garbage")
        result = await orchestrator.grade_skills_task(
            task_brief={"title": "T", "brief": "B", "evaluation_criteria": []},
            submission="some answer",
            career_track="technology",
            role="Engineer",
            level="mid_level",
        )
        assert result["score"] == 5.0
        assert "first_followup" in result


class TestDecideFollowup:
    @pytest.mark.asyncio
    async def test_stop_when_time_exhausted(self):
        orchestrator = LLMOrchestrator()
        orchestrator._call_llm = AsyncMock(return_value='some question?')
        result = await orchestrator.decide_followup(
            task_brief={"title": "T", "brief": "B"},
            submission="code",
            conversation=[],
            time_remaining_pct=0.05,  # < 0.10 → always stop
            career_track="technology",
            evaluation_criteria=["correctness"],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_question_when_time_available(self):
        orchestrator = LLMOrchestrator()
        orchestrator._call_llm = AsyncMock(return_value='Can you explain your choice here?')
        result = await orchestrator.decide_followup(
            task_brief={"title": "T", "brief": "B"},
            submission="code",
            conversation=[],
            time_remaining_pct=0.5,
            career_track="technology",
            evaluation_criteria=["correctness"],
        )
        assert result is not None
        assert "?" in result

    @pytest.mark.asyncio
    async def test_returns_none_on_stop_signal(self):
        orchestrator = LLMOrchestrator()
        orchestrator._call_llm = AsyncMock(return_value='{"stop": true}')
        result = await orchestrator.decide_followup(
            task_brief={"title": "T", "brief": "B"},
            submission="code",
            conversation=[{"role": "interviewer", "content": "Q"}, {"role": "candidate", "content": "A"}],
            time_remaining_pct=0.4,
            career_track="technology",
            evaluation_criteria=["correctness"],
        )
        assert result is None


# ── InterviewEngine unit tests ─────────────────────────────────────────────────

class TestRoundTimeBudgets:
    def test_skills_task_budget_is_5400(self):
        assert ROUND_TIME_BUDGETS["skills_task"] == 5400

    def test_technical_still_present(self):
        # Backwards compat alias
        assert "technical" in ROUND_TIME_BUDGETS

    def test_behavioral_budget(self):
        assert ROUND_TIME_BUDGETS["behavioral"] == 1800


class TestRecordCheatSignal:
    @pytest.mark.asyncio
    async def test_appends_signal_to_round(self):
        from app.models.pg.session import Round

        mock_round = MagicMock(spec=Round)
        mock_round.id = "round-1"
        mock_round.cheating_signals = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_round)))
        mock_db.commit = AsyncMock()

        orchestrator = MagicMock(spec=LLMOrchestrator)
        engine = InterviewEngine(db=mock_db, orchestrator=orchestrator)

        await engine.record_cheat_signal(
            round_id="round-1",
            signal_type="paste",
            paste_chars=120,
        )

        mock_db.commit.assert_called_once()
        assert isinstance(mock_round.cheating_signals, list)
        assert len(mock_round.cheating_signals) == 1
        signal = mock_round.cheating_signals[0]
        assert signal["type"] == "paste"
        assert signal["paste_chars"] == 120
        assert "ts" in signal

    @pytest.mark.asyncio
    async def test_appends_to_existing_signals(self):
        from app.models.pg.session import Round

        existing = [{"type": "focus_lost", "ts": "2026-01-01T00:00:00"}]
        mock_round = MagicMock(spec=Round)
        mock_round.cheating_signals = existing

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_round)))
        mock_db.commit = AsyncMock()

        orchestrator = MagicMock(spec=LLMOrchestrator)
        engine = InterviewEngine(db=mock_db, orchestrator=orchestrator)

        await engine.record_cheat_signal(
            round_id="round-1",
            signal_type="velocity_spike",
            chars_per_second=12.5,
        )

        assert len(mock_round.cheating_signals) == 2
        assert mock_round.cheating_signals[1]["type"] == "velocity_spike"
        assert mock_round.cheating_signals[1]["chars_per_second"] == 12.5

    @pytest.mark.asyncio
    async def test_noop_when_round_not_found(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.commit = AsyncMock()

        orchestrator = MagicMock(spec=LLMOrchestrator)
        engine = InterviewEngine(db=mock_db, orchestrator=orchestrator)

        # Should not raise
        await engine.record_cheat_signal(round_id="nonexistent", signal_type="paste")
        mock_db.commit.assert_not_called()
