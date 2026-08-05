import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

pytestmark = pytest.mark.skipif(
    not settings.database_url.startswith("postgresql"),
    reason="PostgreSQL-only integration tests"
)

@pytest.mark.asyncio
async def test_postgres_connection():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
    await engine.dispose()

@pytest.mark.asyncio
async def test_neo4j_connection():
    from neo4j import AsyncGraphDatabase
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    async with driver.session() as session:
        result = await session.run("RETURN 1 AS n")
        record = await result.single()
        assert record["n"] == 1
    await driver.close()

@pytest.mark.asyncio
async def test_all_tables_exist():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
        tables = {row[0] for row in result}
    expected = {"users", "sessions", "rounds", "round_moments", "interview_profiles", "community_data"}
    assert expected.issubset(tables)
    await engine.dispose()

@pytest.mark.asyncio
async def test_new_tables_exist():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
        tables = {row[0] for row in result}
    assert "knowledge_profiles" in tables
    assert "user_progress" in tables
    await engine.dispose()
