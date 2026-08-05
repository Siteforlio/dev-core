import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.pg.base import Base
from app.models.pg.user import User
from app.models.pg.job_hunter import JobHunterProfile
import app.models.pg.session          # noqa: F401
import app.models.pg.simulation       # noqa: F401
import app.models.pg.meeting_debrief  # noqa: F401
import app.models.pg.knowledge        # noqa: F401
import app.models.pg.community        # noqa: F401
import app.models.pg.progress         # noqa: F401
import app.models.pg.cluely_session   # noqa: F401

@pytest_asyncio.fixture
async def db():
    # Inline engine for test isolation — create all tables now that JSONB has been replaced with JSON
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # create all tables
    session = async_sessionmaker(engine, expire_on_commit=False)
    async with session() as s:
        yield s
    await engine.dispose()

@pytest.mark.asyncio
async def test_user_create_read(db):
    user = User(id="u1", name="Test", email="t@test.com", hashed_password="hash")
    db.add(user)
    await db.commit()
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == "u1"))
    found = result.scalar_one()
    assert found.email == "t@test.com"

@pytest.mark.asyncio
async def test_jsonb_fields_work_as_json(db):
    """JSONB columns must work with SQLite JSON type."""
    from sqlalchemy import select
    # Create parent user first (FK constraint)
    user = User(id="u1", name="Test", email="t@test.com", hashed_password="hash")
    db.add(user)
    await db.commit()
    profile = JobHunterProfile(
        user_id="u1",
        skills=["Python", "FastAPI"],
        work_experience=[{"company": "Acme", "role": "Engineer"}],
    )
    db.add(profile)
    await db.commit()
    result = await db.execute(select(JobHunterProfile).where(JobHunterProfile.user_id == "u1"))
    found = result.scalar_one()
    assert found.skills == ["Python", "FastAPI"]
    assert found.work_experience[0]["company"] == "Acme"
