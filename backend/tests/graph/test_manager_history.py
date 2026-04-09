from unittest.mock import AsyncMock, MagicMock, patch


def _make_neo4j_result(rows: list[dict]):
    async def _aiter(self):
        for row in rows:
            rec = MagicMock()
            rec.__getitem__ = lambda s, k: row[k]
            yield rec
    result = MagicMock()
    result.__aiter__ = _aiter
    return result


def _make_driver(mock_session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    driver = MagicMock()
    driver.session.return_value = ctx
    return driver


async def test_get_manager_history_returns_all_companies():
    from app.graph.manager_queries import get_manager_history

    mock_session = AsyncMock()
    mock_session.run.return_value = _make_neo4j_result([
        {"company": "Google", "title": "VP Eng", "relationship": "WORKS_AT"},
        {"company": "Meta", "title": "Director", "relationship": "PREVIOUSLY_AT"},
    ])

    with patch("app.graph.manager_queries.get_driver", new=AsyncMock(return_value=_make_driver(mock_session))):
        history = await get_manager_history("Jane Doe")

    assert len(history) == 2
    companies = [h["company"] for h in history]
    assert "Google" in companies
    assert "Meta" in companies


async def test_get_manager_history_empty_for_unknown():
    from app.graph.manager_queries import get_manager_history

    mock_session = AsyncMock()
    mock_session.run.return_value = _make_neo4j_result([])

    with patch("app.graph.manager_queries.get_driver", new=AsyncMock(return_value=_make_driver(mock_session))):
        history = await get_manager_history("Nobody Known")

    assert history == []


async def test_record_manager_move_creates_previously_at():
    from app.graph.manager_queries import record_manager_move

    mock_session = AsyncMock()
    mock_session.run.return_value = _make_neo4j_result([])

    with patch("app.graph.manager_queries.get_driver", new=AsyncMock(return_value=_make_driver(mock_session))):
        await record_manager_move(
            manager_name="Jeff Bezos",
            from_company="Amazon",
            to_company="Blue Origin",
            new_title="Executive Chairman",
        )

    # Verify run was called (Cypher executed)
    mock_session.run.assert_called_once()
    call_args = mock_session.run.call_args
    assert "PREVIOUSLY_AT" in call_args[0][0]


async def test_persona_engine_merges_history():
    from app.services.persona_engine import PersonaEngine

    engine = PersonaEngine()

    with patch("app.services.persona_engine.get_managers_for_company", new=AsyncMock(return_value=[
        {"name": "Jeff Bezos", "title": "Former CEO", "traits": ["customer-obsessed", "high-standards"]},
    ])):
        with patch("app.services.persona_engine.get_manager_history", new=AsyncMock(return_value=[
            {"company": "Amazon", "title": "CEO", "relationship": "PREVIOUSLY_AT"},
            {"company": "Blue Origin", "title": "Executive Chairman", "relationship": "WORKS_AT"},
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
