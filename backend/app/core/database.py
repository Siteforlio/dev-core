from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    # Pool sizing — tuned for a single-node FastAPI server.
    # asyncpg multiplexes async queries over fewer real connections,
    # so pool_size=10 handles ~100 concurrent requests comfortably.
    # Raise pool_size when running multiple uvicorn workers.
    pool_size=10,
    max_overflow=20,        # burst headroom: up to 30 total connections
    pool_timeout=30,        # raise after 30s waiting for a connection
    pool_recycle=1800,      # recycle connections every 30 min to avoid stale TCP
    pool_pre_ping=True,     # health-check connection before checkout
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
