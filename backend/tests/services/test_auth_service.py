import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.auth_service import AuthService
from app.core.exceptions import InvalidCredentialsError, UserAlreadyExistsError


def _make_execute_result(value):
    """Return a sync-callable mock that simulates SQLAlchemy Result."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def auth_service(mock_db):
    return AuthService(db=mock_db)


async def test_register_returns_user(auth_service, mock_db):
    mock_db.execute = AsyncMock(return_value=_make_execute_result(None))
    user = await auth_service.register(
        name="Sam", email="sam@test.com", password="secret123",
        language_pref="en", consent_given=True
    )
    assert user.email == "sam@test.com"
    assert user.name == "Sam"
    assert user.consent_given_at is not None


async def test_register_raises_if_email_taken(auth_service, mock_db):
    mock_db.execute = AsyncMock(return_value=_make_execute_result(MagicMock()))
    with pytest.raises(UserAlreadyExistsError):
        await auth_service.register(
            name="Sam", email="sam@test.com", password="secret123",
            language_pref="en", consent_given=True
        )


async def test_login_raises_on_wrong_password(auth_service, mock_db):
    from app.models.pg.user import User
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"])
    fake_user = User(
        id="u1", name="Sam", email="sam@test.com",
        hashed_password=pwd_context.hash("correct"),
        language_pref="en"
    )
    mock_db.execute = AsyncMock(return_value=_make_execute_result(fake_user))
    with pytest.raises(InvalidCredentialsError):
        await auth_service.login(email="sam@test.com", password="wrong")
