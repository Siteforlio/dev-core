import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.main import app
from app.core.database import get_db
from app.core.config import settings


@pytest.fixture
async def client():
    """Fresh DB session per test; truncates users table before each run."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Clean slate — order matters due to FK constraints
    async with session_factory() as session:
        await session.execute(text("TRUNCATE round_moments, rounds, interview_profiles, sessions, community_data, users RESTART IDENTITY CASCADE"))
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()
