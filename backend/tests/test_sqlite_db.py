import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.pg.base import Base
from app.models.pg.user import User

@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[User.__table__])
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
