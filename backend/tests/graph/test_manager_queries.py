from unittest.mock import AsyncMock, MagicMock, patch


def _make_neo4j_result(rows: list[dict]):
    """Return an async-iterable mock that yields record-like objects."""
    async def _aiter(self):
        for row in rows:
            rec = MagicMock()
            rec.__getitem__ = lambda s, k: row[k]
            yield rec

    result = MagicMock()
    result.__aiter__ = _aiter
    return result


def _make_driver(mock_session):
    """Build a driver mock whose .session() is a sync context manager wrapping mock_session."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    driver = MagicMock()
    driver.session.return_value = ctx
    return driver


async def test_get_managers_for_company_returns_list():
    from app.graph.manager_queries import get_managers_for_company

    mock_session = AsyncMock()
    mock_session.run.return_value = _make_neo4j_result([
        {"name": "Sundar Pichai", "title": "CEO", "traits": ["data-driven", "systematic"]},
    ])

    with patch("app.graph.manager_queries.get_driver", new=AsyncMock(return_value=_make_driver(mock_session))):
        result = await get_managers_for_company("Google")

    assert len(result) == 1
    assert result[0]["name"] == "Sundar Pichai"
    assert "traits" in result[0]


async def test_get_managers_returns_empty_for_unknown_company():
    from app.graph.manager_queries import get_managers_for_company

    mock_session = AsyncMock()
    mock_session.run.return_value = _make_neo4j_result([])

    with patch("app.graph.manager_queries.get_driver", new=AsyncMock(return_value=_make_driver(mock_session))):
        result = await get_managers_for_company("UnknownCorp")

    assert result == []
