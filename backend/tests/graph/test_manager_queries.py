"""Tests for manager_queries — mocks AsyncSessionLocal (SQLAlchemy/SQLite impl)."""
from unittest.mock import AsyncMock, MagicMock, patch


def _make_db_session(scalars_result):
    """Build an async context-manager mock for AsyncSessionLocal."""
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = scalars_result

    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def test_get_managers_for_company_returns_list():
    from app.graph.manager_queries import get_managers_for_company

    manager = MagicMock()
    manager.name = "Sundar Pichai"
    manager.title = "CEO"
    manager.traits = ["data-driven", "systematic"]

    with patch("app.graph.manager_queries.AsyncSessionLocal", return_value=_make_db_session([manager])):
        result = await get_managers_for_company("Google")

    assert len(result) == 1
    assert result[0]["name"] == "Sundar Pichai"
    assert "traits" in result[0]


async def test_get_managers_returns_empty_for_unknown_company():
    from app.graph.manager_queries import get_managers_for_company

    with patch("app.graph.manager_queries.AsyncSessionLocal", return_value=_make_db_session([])):
        result = await get_managers_for_company("UnknownCorp")

    assert result == []
