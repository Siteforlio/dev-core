"""Tests for round_queries — mocks AsyncSessionLocal (SQLAlchemy/SQLite impl)."""
from unittest.mock import AsyncMock, MagicMock, patch


def _make_db_session_for_questions(round_obj, questions):
    """Return a session mock that returns round_obj on first execute, questions on second."""
    round_execute = MagicMock()
    round_execute.scalar_one_or_none.return_value = round_obj

    q_execute = MagicMock()
    q_execute.scalars.return_value.all.return_value = questions

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[round_execute, q_execute])

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def test_get_questions_for_round_returns_list():
    from app.graph.round_queries import get_questions_for_round

    round_obj = MagicMock()
    round_obj.id = "round-1"

    q1 = MagicMock()
    q1.text = "Tell me about a time you led a project."
    q1.difficulty = "medium"
    q2 = MagicMock()
    q2.text = "How do you handle conflict?"
    q2.difficulty = "medium"

    with patch("app.graph.round_queries.AsyncSessionLocal",
               return_value=_make_db_session_for_questions(round_obj, [q1, q2])):
        result = await get_questions_for_round("Google", "behavioral")

    assert len(result) == 2
    assert result[0]["text"].startswith("Tell me")


async def test_get_questions_returns_empty_for_unknown_round():
    from app.graph.round_queries import get_questions_for_round

    # When round is not found, return None — second execute won't be called
    round_execute = MagicMock()
    round_execute.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute = AsyncMock(return_value=round_execute)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.graph.round_queries.AsyncSessionLocal", return_value=ctx):
        result = await get_questions_for_round("Google", "unknown_round")

    assert result == []


async def test_get_round_context_bundles_questions_and_patterns():
    from app.graph.round_queries import get_round_context

    round_obj = MagicMock()
    round_obj.id = "round-2"

    q = MagicMock()
    q.text = "System design question?"
    q.difficulty = "hard"

    with patch("app.graph.round_queries.AsyncSessionLocal",
               return_value=_make_db_session_for_questions(round_obj, [q])):
        ctx = await get_round_context("Google", "technical")

    assert "company" in ctx
    assert "round_type" in ctx
    assert "sample_questions" in ctx
    assert ctx["company"] == "Google"
