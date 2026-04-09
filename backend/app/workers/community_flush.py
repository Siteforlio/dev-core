import asyncio
import logging
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_SECONDS = 60


async def flush_loop():
    """Background task: flush pending CommunityData rows to Neo4j every 60s."""
    from app.services.community_pipeline import CommunityPipeline

    while True:
        try:
            async with AsyncSessionLocal() as db:
                pipeline = CommunityPipeline(db=db)
                flushed = await pipeline.flush_pending()
                if flushed:
                    logger.info("community_flush: flushed %d rows to Neo4j", flushed)
        except Exception as exc:
            logger.warning("community_flush: error during flush: %s", exc)

        await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
