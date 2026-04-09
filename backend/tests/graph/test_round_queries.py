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


async def test_get_questions_for_round_returns_list():
    from app.graph.round_queries import get_questions_for_round

    mock_session = AsyncMock()
    mock_session.run.return_value = _make_neo4j_result([
        {"text": "Tell me about a time you led a project.", "difficulty": "medium"},
        {"text": "How do you handle conflict?", "difficulty": "medium"},
    ])

    with patch("app.graph.round_queries.get_driver", new=AsyncMock(return_value=_make_driver(mock_session))):
        result = await get_questions_for_round("Google", "behavioral")

    assert len(result) == 2
    assert result[0]["text"].startswith("Tell me")


async def test_get_questions_returns_empty_for_unknown_round():
    from app.graph.round_queries import get_questions_for_round

    mock_session = AsyncMock()
    mock_session.run.return_value = _make_neo4j_result([])

    with patch("app.graph.round_queries.get_driver", new=AsyncMock(return_value=_make_driver(mock_session))):
        result = await get_questions_for_round("Google", "unknown_round")

    assert result == []


async def test_get_round_context_bundles_questions_and_patterns():
    from app.graph.round_queries import get_round_context

    mock_session = AsyncMock()
    mock_session.run.return_value = _make_neo4j_result([
        {"text": "System design question?", "difficulty": "hard"},
    ])

    with patch("app.graph.round_queries.get_driver", new=AsyncMock(return_value=_make_driver(mock_session))):
        ctx = await get_round_context("Google", "technical")

    assert "company" in ctx
    assert "round_type" in ctx
    assert "sample_questions" in ctx
    assert ctx["company"] == "Google"
