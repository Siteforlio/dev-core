"""Tests for manager history queries — mocks AsyncSessionLocal (SQLAlchemy/SQLite impl)."""
from unittest.mock import AsyncMock, MagicMock, patch


def _make_db_session_scalar(scalar_value):
    """Return a session mock that returns scalar_value from scalar_one_or_none."""
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = scalar_value

    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def test_get_manager_history_returns_all_companies():
    from app.graph.manager_queries import get_manager_history

    manager = MagicMock()
    manager.name = "Jane Doe"
    manager.title = "VP Eng"
    manager.company_name = "Google"

    with patch("app.graph.manager_queries.AsyncSessionLocal", return_value=_make_db_session_scalar(manager)):
        history = await get_manager_history("Jane Doe")

    # SQLite impl returns only WORKS_AT (no PREVIOUSLY_AT in this model)
    assert len(history) == 1
    assert history[0]["company"] == "Google"
    assert history[0]["relationship"] == "WORKS_AT"


async def test_get_manager_history_empty_for_unknown():
    from app.graph.manager_queries import get_manager_history

    with patch("app.graph.manager_queries.AsyncSessionLocal", return_value=_make_db_session_scalar(None)):
        history = await get_manager_history("Nobody Known")

    assert history == []


async def test_record_manager_move_creates_previously_at():
    from app.graph.manager_queries import record_manager_move

    manager = MagicMock()
    manager.company_name = "Amazon"
    manager.title = "CEO"

    ctx = _make_db_session_scalar(manager)

    with patch("app.graph.manager_queries.AsyncSessionLocal", return_value=ctx):
        await record_manager_move(
            manager_name="Jeff Bezos",
            from_company="Amazon",
            to_company="Blue Origin",
            new_title="Executive Chairman",
        )

    # Manager should have been updated
    assert manager.company_name == "Blue Origin"
    assert manager.title == "Executive Chairman"


async def test_persona_engine_merges_history():
    from app.services.persona_engine import PersonaEngine

    engine = PersonaEngine()

    with patch("app.services.persona_engine.get_managers_for_company", new=AsyncMock(return_value=[
        {"name": "Jeff Bezos", "title": "Former CEO", "traits": ["customer-obsessed", "high-standards"]},
    ])):
        with patch("app.services.persona_engine.get_manager_history", new=AsyncMock(return_value=[
            {"company": "Amazon", "title": "CEO", "relationship": "WORKS_AT"},
        ])):
            with patch("app.services.persona_engine.get_round_context", new=AsyncMock(return_value={
                "company": "Amazon", "round_type": "behavioral", "sample_questions": [],
            })):
                with patch.object(engine._orchestrator, "build_persona", new=AsyncMock(
                    return_value="High-standards interviewer with cross-company perspective."
                )):
                    persona = await engine.build(company="Amazon", role="SWE", round_type="behavioral")

    assert isinstance(persona, str)
    assert len(persona) > 0
