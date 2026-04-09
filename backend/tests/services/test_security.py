from unittest.mock import AsyncMock, MagicMock, patch


async def test_delete_user_removes_account():
    from app.services.auth_service import AuthService
    mock_db = AsyncMock()

    mock_user = MagicMock(id="u1", email="test@example.com")
    mock_db.execute = AsyncMock(
        return_value=MagicMock(**{"scalar_one_or_none.return_value": mock_user})
    )

    service = AuthService(db=mock_db)
    await service.delete_user(user_id="u1")

    mock_db.delete.assert_called_once_with(mock_user)
    mock_db.commit.assert_called_once()


async def test_delete_user_raises_when_not_found():
    from app.services.auth_service import AuthService
    from app.core.exceptions import UserNotFoundError
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(**{"scalar_one_or_none.return_value": None})
    )

    service = AuthService(db=mock_db)
    try:
        await service.delete_user(user_id="ghost")
        assert False, "should have raised"
    except UserNotFoundError:
        pass


async def test_rate_limit_middleware_is_registered():
    """Verify SlowAPI limiter is attached to the FastAPI app."""
    from app.main import app
    # SlowAPI attaches state.limiter
    assert hasattr(app.state, "limiter")
